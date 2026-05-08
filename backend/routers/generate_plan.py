import json
import logging
import uuid

from fastapi import APIRouter, Depends

from middleware.anon_token import verify_token
from schemas.generate_plan import GeneratePlanRequest, GeneratePlanResponse, Section
from services.guardrails import validate_prompt
from services.helpers import error_json, extract_json, normalize_generate_plan_payload, text_preview
from services.llm_error_handler import handle_llm_exception
from services.llm_client import (
    OPENAI_MODEL_PLAN,
    LLMAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    call_plan_llm,
)
from services.prompt_loader import load_prompt

router = APIRouter()
logger = logging.getLogger(__name__)

ENDPOINT = "/api/generate-plan"


@router.post(ENDPOINT)
async def generate_plan(
    req: GeneratePlanRequest,
    _: None = Depends(verify_token),
):
    request_id = str(uuid.uuid4())

    ok, msg = validate_prompt(req.prompt)
    if not ok:
        logger.warning("guardrails.rejected", extra={
            "event": "guardrails.rejected", "request_id": request_id, "endpoint": ENDPOINT,
        })
        return error_json(msg, "PROMPT_REJECTED", 400, request_id)

    system = load_prompt("plan_prompt.txt")
    user_msg = f"Prompt: {req.prompt}\nTone: {req.tone}"

    try:
        result = call_plan_llm(
            system,
            user_msg,
            max_tokens=8192,
            trace_meta={"request_id": request_id, "endpoint": ENDPOINT, "operation": "generate-plan"},
        )
    except (LLMRateLimitError, LLMTimeoutError, LLMAPIError) as exc:
        return handle_llm_exception(
            logger=logger,
            exc=exc,
            request_id=request_id,
            llm_provider_target="openai",
            llm_model_target=OPENAI_MODEL_PLAN,
        )

    try:
        data = normalize_generate_plan_payload(extract_json(result.text))
    except Exception as exc:
        logger.error("parse.error", extra={
            "event": "parse.error", "request_id": request_id,
            "error": str(exc), "raw_prefix": text_preview(result.text),
        })
        return error_json("Failed to parse model response. Please try again.", "PARSE_ERROR", 502, request_id)

    raw_sections = data.get("sections", []) if isinstance(data, dict) else []
    valid_sections: list[Section] = []
    skipped_sections = 0

    for idx, raw_section in enumerate(raw_sections):
        try:
            valid_sections.append(Section(**raw_section))
        except Exception as exc:
            skipped_sections += 1
            logger.warning("section.skipped", extra={
                "event": "section.skipped",
                "request_id": request_id,
                "endpoint": ENDPOINT,
                "section_index": idx,
                "error": str(exc),
                "section_raw_prefix": text_preview(json.dumps(raw_section, ensure_ascii=False)),
            })

    if not valid_sections:
        logger.error("parse.error", extra={
            "event": "parse.error",
            "request_id": request_id,
            "error": "No valid sections after normalization/validation.",
            "raw_prefix": text_preview(result.text),
        })
        return error_json("Failed to parse model response. Please try again.", "PARSE_ERROR", 502, request_id)

    if skipped_sections > 0:
        logger.warning("sections.partial", extra={
            "event": "sections.partial",
            "request_id": request_id,
            "endpoint": ENDPOINT,
            "sections_returned": len(valid_sections),
            "sections_skipped": skipped_sections,
        })

    response = GeneratePlanResponse(sections=valid_sections)
    return response
