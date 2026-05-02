import logging
import time
import uuid

from fastapi import APIRouter, Depends

from middleware.anon_token import verify_token
from schemas.generate_plan import Section
from schemas.parse_section import ParseSectionRequest
from services.guardrails import validate_prompt
from services.helpers import error_json, extract_json, normalize_section_payload, text_preview
from services.llm_client import (
    LLMAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    call_parse_llm,
    estimate_cost_usd,
    get_parse_llm_config,
    provider_for_model,
)
from services.prompt_loader import load_prompt

router = APIRouter()
logger = logging.getLogger(__name__)

ENDPOINT = "/api/parse-section"


@router.post(ENDPOINT)
async def parse_section(
    req: ParseSectionRequest,
    _: None = Depends(verify_token),
):
    request_id = str(uuid.uuid4())
    t0 = time.monotonic()
    llm_cfg = get_parse_llm_config()
    logger.info("request.start", extra={
        "event": "request.start", "request_id": request_id,
        "endpoint": ENDPOINT, "section_id": req.sectionId, "section_type": req.sectionType,
        "raw_prefix": text_preview(req.rawText),
        "llm_provider_target": llm_cfg["provider"],
        "llm_model_target": llm_cfg["model"],
    })

    ok, msg = validate_prompt(req.rawText)
    if not ok:
        logger.warning("guardrails.rejected", extra={
            "event": "guardrails.rejected", "request_id": request_id, "endpoint": ENDPOINT,
        })
        return error_json(msg, "PROMPT_REJECTED", 400, request_id)

    system = load_prompt("parse_prompt.txt")
    user_msg = (
        f"Section ID: {req.sectionId}\n"
        f"Current section type (hint): {req.sectionType}\n\n"
        f"Content:\n{req.rawText}"
    )

    try:
        result = call_parse_llm(system, user_msg)
    except LLMRateLimitError:
        logger.error("llm.error", extra={
            "event": "llm.error", "request_id": request_id,
            "error_code": "RATE_LIMITED",
            "llm_provider_target": llm_cfg["provider"],
            "llm_model_target": llm_cfg["model"],
        })
        return error_json("Rate limit exceeded. Please try again shortly.", "RATE_LIMITED", 429, request_id)
    except LLMTimeoutError:
        logger.error("llm.error", extra={
            "event": "llm.error", "request_id": request_id,
            "error_code": "TIMEOUT",
            "llm_provider_target": llm_cfg["provider"],
            "llm_model_target": llm_cfg["model"],
        })
        return error_json("Request timed out. Please try again.", "TIMEOUT", 504, request_id)
    except LLMAPIError as exc:
        logger.error("llm.error", extra={
            "event": "llm.error", "request_id": request_id,
            "error_code": "LLM_ERROR", "detail": str(exc),
            "llm_provider_target": llm_cfg["provider"],
            "llm_model_target": llm_cfg["model"],
        })
        return error_json("LLM service error. Please try again.", "LLM_ERROR", 502, request_id)

    estimated_cost_usd = estimate_cost_usd(result.model, result.input_tokens, result.output_tokens)

    logger.info("llm.ok", extra={
        "event": "llm.ok", "request_id": request_id, "model": result.model,
        "llm_provider": provider_for_model(result.model),
        "llm_provider_target": llm_cfg["provider"],
        "llm_model_target": llm_cfg["model"],
        "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
        "duration_ms": result.duration_ms,
        "stop_reason": result.stop_reason,
        "estimated_cost_usd": round(estimated_cost_usd, 6) if estimated_cost_usd is not None else None,
    })
    if result.stop_reason == "max_tokens":
        logger.warning("llm.truncated", extra={
            "event": "llm.truncated",
            "request_id": request_id,
            "endpoint": ENDPOINT,
            "model": result.model,
            "output_tokens": result.output_tokens,
        })

    try:
        data = normalize_section_payload(
            extract_json(result.text),
            section_id_hint=req.sectionId,
            section_type_hint=req.sectionType,
        )
        response = Section(**data)
    except Exception as exc:
        logger.error("parse.error", extra={
            "event": "parse.error", "request_id": request_id,
            "error": str(exc), "raw_prefix": text_preview(result.text),
        })
        return error_json("Failed to parse model response. Please try again.", "PARSE_ERROR", 502, request_id)

    logger.info("request.done", extra={
        "event": "request.done", "request_id": request_id,
        "endpoint": ENDPOINT, "status": 200,
        "duration_ms": int((time.monotonic() - t0) * 1000),
    })
    return response
