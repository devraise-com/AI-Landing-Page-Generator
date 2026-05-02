import logging
import time
import uuid

from fastapi import APIRouter, Depends

from middleware.anon_token import verify_token
from schemas.generate_page import GeneratePageRequest, GeneratePageResponse
from services.guardrails import validate_landing_plan
from services.helpers import error_json
from services.llm_client import (
    SONNET,
    LLMAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    call_sonnet,
    estimate_cost_usd,
    provider_for_model,
)
from services.prompt_loader import load_prompt

router = APIRouter()
logger = logging.getLogger(__name__)

ENDPOINT = "/api/generate-page"


@router.post(ENDPOINT)
async def generate_page(
    req: GeneratePageRequest,
    _: None = Depends(verify_token),
):
    request_id = str(uuid.uuid4())
    t0 = time.monotonic()
    logger.info("request.start", extra={
        "event": "request.start", "request_id": request_id,
        "endpoint": ENDPOINT, "section_count": len(req.landingPlan.sections),
        "llm_provider_target": "anthropic",
        "llm_model_target": SONNET,
    })

    ok, msg = validate_landing_plan(req.landingPlan.model_dump())
    if not ok:
        logger.warning("guardrails.rejected", extra={
            "event": "guardrails.rejected", "request_id": request_id, "endpoint": ENDPOINT,
        })
        return error_json(msg, "PROMPT_REJECTED", 400, request_id)

    system = load_prompt("page_prompt.txt")
    user_msg = f"Landing page plan:\n{req.landingPlan.model_dump_json(indent=2)}"

    try:
        result = call_sonnet(system, user_msg, max_tokens=16000)
    except LLMRateLimitError:
        logger.error("llm.error", extra={
            "event": "llm.error", "request_id": request_id,
            "error_code": "RATE_LIMITED",
            "llm_provider_target": "anthropic",
            "llm_model_target": SONNET,
        })
        return error_json("Rate limit exceeded. Please try again shortly.", "RATE_LIMITED", 429, request_id)
    except LLMTimeoutError:
        logger.error("llm.error", extra={
            "event": "llm.error", "request_id": request_id,
            "error_code": "TIMEOUT",
            "llm_provider_target": "anthropic",
            "llm_model_target": SONNET,
        })
        return error_json("Request timed out. Please try again.", "TIMEOUT", 504, request_id)
    except LLMAPIError as exc:
        logger.error("llm.error", extra={
            "event": "llm.error", "request_id": request_id,
            "error_code": "LLM_ERROR", "detail": str(exc),
            "llm_provider_target": "anthropic",
            "llm_model_target": SONNET,
        })
        return error_json("LLM service error. Please try again.", "LLM_ERROR", 502, request_id)

    estimated_cost_usd = estimate_cost_usd(result.model, result.input_tokens, result.output_tokens)

    logger.info("llm.ok", extra={
        "event": "llm.ok", "request_id": request_id, "model": result.model,
        "llm_provider": provider_for_model(result.model),
        "llm_provider_target": "anthropic",
        "llm_model_target": SONNET,
        "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
        "duration_ms": result.duration_ms, "stop_reason": result.stop_reason,
        "estimated_cost_usd": round(estimated_cost_usd, 6) if estimated_cost_usd is not None else None,
    })
    if result.stop_reason == "max_tokens":
        logger.warning("llm.truncated", extra={
            "event": "llm.truncated", "request_id": request_id,
            "output_tokens": result.output_tokens,
        })

    html = result.text.strip()
    if html.startswith("```"):
        html = html.split("\n", 1)[-1]
        html = html.rsplit("```", 1)[0].strip()

    response = GeneratePageResponse(html=html)

    logger.info("request.done", extra={
        "event": "request.done", "request_id": request_id,
        "endpoint": ENDPOINT, "status": 200,
        "duration_ms": int((time.monotonic() - t0) * 1000),
    })
    return response
