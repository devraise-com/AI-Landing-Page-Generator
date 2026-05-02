import os
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

import anthropic
try:
    import certifi
except ImportError:
    certifi = None

# max_retries=1 → 2 total attempts; SDK retries on 429 and 5xx by default
_client = anthropic.Anthropic(max_retries=1)

SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


_SONNET_TIMEOUT = _get_float_env("SONNET_TIMEOUT_SECONDS", 120.0)
_HAIKU_TIMEOUT = _get_float_env("HAIKU_TIMEOUT_SECONDS", 30.0)
_OPENAI_PLAN_TIMEOUT = _get_float_env("OPENAI_PLAN_TIMEOUT_SECONDS", _SONNET_TIMEOUT)
_OPENAI_PARSE_TIMEOUT = _get_float_env("OPENAI_PARSE_TIMEOUT_SECONDS", _HAIKU_TIMEOUT)

_PLAN_PROVIDER = os.getenv("PLAN_LLM_PROVIDER", "anthropic").strip().lower()
_PARSE_PROVIDER = os.getenv("PARSE_LLM_PROVIDER", "anthropic").strip().lower()
_OPENAI_MODEL_PLAN = os.getenv("OPENAI_MODEL_PLAN", "gpt-4.1")
_OPENAI_MODEL_PARSE = os.getenv("OPENAI_MODEL_PARSE", "gpt-4.1-mini")
_OPENAI_PLAN_COST_INPUT_PER_MTOKENS = _get_float_env("OPENAI_PLAN_COST_INPUT_PER_MTOKENS", 2.0)
_OPENAI_PLAN_COST_OUTPUT_PER_MTOKENS = _get_float_env("OPENAI_PLAN_COST_OUTPUT_PER_MTOKENS", 8.0)
_OPENAI_PARSE_COST_INPUT_PER_MTOKENS = _get_float_env("OPENAI_PARSE_COST_INPUT_PER_MTOKENS", 0.4)
_OPENAI_PARSE_COST_OUTPUT_PER_MTOKENS = _get_float_env("OPENAI_PARSE_COST_OUTPUT_PER_MTOKENS", 1.6)

_DEFAULT_PRICING_PER_MTOKENS = {
    SONNET: (
        _get_float_env("ANTHROPIC_COST_SONNET_INPUT_PER_MTOKENS", 3.0),
        _get_float_env("ANTHROPIC_COST_SONNET_OUTPUT_PER_MTOKENS", 15.0),
    ),
    HAIKU: (
        _get_float_env("ANTHROPIC_COST_HAIKU_INPUT_PER_MTOKENS", 0.8),
        _get_float_env("ANTHROPIC_COST_HAIKU_OUTPUT_PER_MTOKENS", 4.0),
    ),
}


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


def get_plan_llm_config() -> dict[str, str]:
    if _PLAN_PROVIDER == "openai":
        return {"provider": "openai", "model": _OPENAI_MODEL_PLAN}
    return {"provider": "anthropic", "model": SONNET}


def get_parse_llm_config() -> dict[str, str]:
    if _PARSE_PROVIDER == "openai":
        return {"provider": "openai", "model": _OPENAI_MODEL_PARSE}
    return {"provider": "anthropic", "model": HAIKU}


def provider_for_model(model: str) -> str:
    if model.startswith(("gpt-", "o")):
        return "openai"
    if model.startswith("claude-"):
        return "anthropic"
    return "unknown"


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate request cost from token usage and per-model pricing.
    Returns None when model pricing is unknown."""
    pricing = _DEFAULT_PRICING_PER_MTOKENS.get(model)
    if not pricing:
        if model == _OPENAI_MODEL_PARSE:
            pricing = (_OPENAI_PARSE_COST_INPUT_PER_MTOKENS, _OPENAI_PARSE_COST_OUTPUT_PER_MTOKENS)
        elif model == _OPENAI_MODEL_PLAN or model.startswith(("gpt-", "o")):
            pricing = (_OPENAI_PLAN_COST_INPUT_PER_MTOKENS, _OPENAI_PLAN_COST_OUTPUT_PER_MTOKENS)
        else:
            return None
    input_per_mtok, output_per_mtok = pricing
    return (input_tokens / 1_000_000) * input_per_mtok + (output_tokens / 1_000_000) * output_per_mtok


def call_sonnet(system: str, user: str, max_tokens: int = 4096) -> LLMResult:
    """Call Claude Sonnet with env-configured timeout."""
    t0 = time.monotonic()
    try:
        msg = _client.messages.create(
            model=SONNET,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            timeout=_SONNET_TIMEOUT,
        )
    except anthropic.RateLimitError as exc:
        raise LLMRateLimitError(str(exc)) from exc
    except anthropic.APITimeoutError as exc:
        raise LLMTimeoutError(str(exc)) from exc
    except anthropic.APIError as exc:
        raise LLMAPIError(str(exc)) from exc
    return LLMResult(
        text=msg.content[0].text,
        model=SONNET,
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
        duration_ms=int((time.monotonic() - t0) * 1000),
        stop_reason=msg.stop_reason,
    )


def call_haiku(system: str, user: str, max_tokens: int = 1024) -> LLMResult:
    """Call Claude Haiku with env-configured timeout."""
    t0 = time.monotonic()
    try:
        msg = _client.messages.create(
            model=HAIKU,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            timeout=_HAIKU_TIMEOUT,
        )
    except anthropic.RateLimitError as exc:
        raise LLMRateLimitError(str(exc)) from exc
    except anthropic.APITimeoutError as exc:
        raise LLMTimeoutError(str(exc)) from exc
    except anthropic.APIError as exc:
        raise LLMAPIError(str(exc)) from exc
    return LLMResult(
        text=msg.content[0].text,
        model=HAIKU,
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
        duration_ms=int((time.monotonic() - t0) * 1000),
        stop_reason=msg.stop_reason,
    )


def call_plan_llm(system: str, user: str, max_tokens: int = 4096) -> LLMResult:
    if _PLAN_PROVIDER == "openai":
        return _call_openai(_OPENAI_MODEL_PLAN, system, user, max_tokens, _OPENAI_PLAN_TIMEOUT)
    return call_sonnet(system, user, max_tokens)


def call_parse_llm(system: str, user: str, max_tokens: int = 1024) -> LLMResult:
    if _PARSE_PROVIDER == "openai":
        return _call_openai(_OPENAI_MODEL_PARSE, system, user, max_tokens, _OPENAI_PARSE_TIMEOUT)
    return call_haiku(system, user, max_tokens)


def _call_openai(model: str, system: str, user: str, max_tokens: int, timeout_seconds: float) -> LLMResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMAPIError("OPENAI_API_KEY is not set.")

    body = {
        "model": model,
        "max_output_tokens": max_tokens,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user}],
            },
        ],
    }
    data = json.dumps(body).encode("utf-8")

    t0 = time.monotonic()
    resp = _openai_post_with_retry(api_key=api_key, data=data, timeout_seconds=timeout_seconds)
    usage = resp.get("usage", {}) if isinstance(resp, dict) else {}

    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)

    stop_reason = "end_turn"
    incomplete = resp.get("incomplete_details") if isinstance(resp, dict) else None
    if isinstance(incomplete, dict) and incomplete.get("reason") == "max_output_tokens":
        stop_reason = "max_tokens"

    return LLMResult(
        text=_extract_openai_text(resp),
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=int((time.monotonic() - t0) * 1000),
        stop_reason=stop_reason,
    )


def _openai_post_with_retry(api_key: str, data: bytes, timeout_seconds: float) -> dict:
    max_attempts = 2
    ssl_context = _openai_ssl_context()
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds, context=ssl_context) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            code = exc.code
            body = exc.read().decode("utf-8", errors="replace")
            retriable = code == 429 or code >= 500
            if retriable and attempt < max_attempts:
                time.sleep(0.5 * attempt)
                continue
            if code == 429:
                raise LLMRateLimitError(body) from exc
            raise LLMAPIError(body) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            is_timeout = isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout) or "timed out" in str(exc).lower()
            if attempt < max_attempts:
                time.sleep(0.5 * attempt)
                continue
            if is_timeout:
                raise LLMTimeoutError(str(exc)) from exc
            raise LLMAPIError(str(exc)) from exc
    raise LLMAPIError("OpenAI request failed.")


def _extract_openai_text(resp: dict) -> str:
    output_text = resp.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    chunks: list[str] = []
    for item in resp.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def _openai_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()
