import os
import time
from dataclasses import dataclass
from typing import Any

import anthropic
import openai as _openai_lib

from services.langfuse_observability import start_llm_generation

# max_retries=1 -> 2 total attempts; SDK retries on 429 and 5xx by default
_anthropic_client = anthropic.Anthropic(max_retries=1)
_openai_client: _openai_lib.OpenAI | None = None

SONNET = "claude-sonnet-4-6"
OPENAI_MODEL_PLAN = os.getenv("OPENAI_MODEL_PLAN", "gpt-4.1")
OPENAI_MODEL_PARSE = os.getenv("OPENAI_MODEL_PARSE", "gpt-4.1-mini")


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


_SONNET_TIMEOUT = _get_float_env("SONNET_TIMEOUT_SECONDS", 120.0)
_OPENAI_PLAN_TIMEOUT = _get_float_env("OPENAI_PLAN_TIMEOUT_SECONDS", 120.0)
_OPENAI_PARSE_TIMEOUT = _get_float_env("OPENAI_PARSE_TIMEOUT_SECONDS", 30.0)


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    stop_reason: str  # "end_turn" | "max_tokens" | "stop_sequence"


class LLMRateLimitError(Exception):
    pass


class LLMTimeoutError(Exception):
    pass


class LLMAPIError(Exception):
    pass


def _safe_observation_update(observation: Any | None, **kwargs: Any) -> None:
    if observation is None:
        return
    try:
        observation.update(**kwargs)
    except Exception:
        return


def _observation_name(trace_meta: dict[str, Any] | None) -> str:
    operation = (trace_meta or {}).get("operation")
    if isinstance(operation, str) and operation.strip():
        return f"llm.{operation.strip()}"
    return "llm.call"


def _get_openai_client() -> _openai_lib.OpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMAPIError("OPENAI_API_KEY is not set.")
        _openai_client = _openai_lib.OpenAI(api_key=api_key, max_retries=1)
    return _openai_client


def _call_anthropic(
    model: str,
    timeout_seconds: float,
    system: str,
    user: str,
    max_tokens: int,
    trace_meta: dict[str, Any] | None,
) -> LLMResult:
    t0 = time.monotonic()
    with start_llm_generation(
        name=_observation_name(trace_meta),
        model=model,
        provider="anthropic",
        input_payload={"system": system, "user": user, "max_tokens": max_tokens},
        metadata=trace_meta,
    ) as observation:
        try:
            msg = _anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=timeout_seconds,
            )
        except anthropic.RateLimitError as exc:
            _safe_observation_update(observation, metadata={"error_code": "RATE_LIMITED", "error": str(exc)})
            raise LLMRateLimitError(str(exc)) from exc
        except anthropic.APITimeoutError as exc:
            _safe_observation_update(observation, metadata={"error_code": "TIMEOUT", "error": str(exc)})
            raise LLMTimeoutError(str(exc)) from exc
        except anthropic.APIError as exc:
            _safe_observation_update(observation, metadata={"error_code": "LLM_ERROR", "error": str(exc)})
            raise LLMAPIError(str(exc)) from exc

        result = LLMResult(
            text=msg.content[0].text,
            model=model,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            duration_ms=int((time.monotonic() - t0) * 1000),
            stop_reason=msg.stop_reason,
        )
        _safe_observation_update(
            observation,
            output=result.text,
            usage_details={"input": result.input_tokens, "output": result.output_tokens},
            metadata={"duration_ms": result.duration_ms, "stop_reason": result.stop_reason},
        )
        return result


def _extract_openai_text(resp: Any) -> str:
    chunks: list[str] = []
    for item in (resp.output or []):
        for block in getattr(item, "content", None) or []:
            if getattr(block, "type", None) == "output_text":
                text = getattr(block, "text", "")
                if text:
                    chunks.append(text)
    return "\n".join(chunks)


def _call_openai(
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    timeout_seconds: float,
    trace_meta: dict[str, Any] | None = None,
) -> LLMResult:
    t0 = time.monotonic()
    with start_llm_generation(
        name=_observation_name(trace_meta),
        model=model,
        provider="openai",
        input_payload={"system": system, "user": user, "max_tokens": max_tokens},
        metadata=trace_meta,
    ) as observation:
        try:
            resp = _get_openai_client().responses.create(
                model=model,
                max_output_tokens=max_tokens,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user}]},
                ],
                timeout=timeout_seconds,
            )
        except _openai_lib.RateLimitError as exc:
            _safe_observation_update(observation, metadata={"error_code": "RATE_LIMITED", "error": str(exc)})
            raise LLMRateLimitError(str(exc)) from exc
        except _openai_lib.APITimeoutError as exc:
            _safe_observation_update(observation, metadata={"error_code": "TIMEOUT", "error": str(exc)})
            raise LLMTimeoutError(str(exc)) from exc
        except _openai_lib.APIError as exc:
            _safe_observation_update(observation, metadata={"error_code": "LLM_ERROR", "error": str(exc)})
            raise LLMAPIError(str(exc)) from exc

        stop_reason = (
            "max_tokens"
            if getattr(getattr(resp, "incomplete_details", None), "reason", None) == "max_output_tokens"
            else "end_turn"
        )
        usage = resp.usage
        result = LLMResult(
            text=_extract_openai_text(resp),
            model=model,
            input_tokens=usage.input_tokens if usage is not None else 0,
            output_tokens=usage.output_tokens if usage is not None else 0,
            duration_ms=int((time.monotonic() - t0) * 1000),
            stop_reason=stop_reason,
        )
        _safe_observation_update(
            observation,
            output=result.text,
            usage_details={
                "input": result.input_tokens,
                "output": result.output_tokens,
                "total": result.input_tokens + result.output_tokens,
            },
            metadata={"duration_ms": result.duration_ms, "stop_reason": result.stop_reason},
        )
        return result


def call_sonnet(
    system: str,
    user: str,
    max_tokens: int = 4096,
    trace_meta: dict[str, Any] | None = None,
) -> LLMResult:
    return _call_anthropic(SONNET, _SONNET_TIMEOUT, system, user, max_tokens, trace_meta)


def call_plan_llm(
    system: str,
    user: str,
    max_tokens: int = 4096,
    trace_meta: dict[str, Any] | None = None,
) -> LLMResult:
    return _call_openai(OPENAI_MODEL_PLAN, system, user, max_tokens, _OPENAI_PLAN_TIMEOUT, trace_meta=trace_meta)


def call_parse_llm(
    system: str,
    user: str,
    max_tokens: int = 1024,
    trace_meta: dict[str, Any] | None = None,
) -> LLMResult:
    return _call_openai(OPENAI_MODEL_PARSE, system, user, max_tokens, _OPENAI_PARSE_TIMEOUT, trace_meta=trace_meta)
