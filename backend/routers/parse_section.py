import logging
import uuid

from fastapi import APIRouter, Depends

from middleware.anon_token import verify_token
from schemas.generate_plan import Section
from schemas.parse_section import ParseSectionRequest
from services.guardrails import validate_prompt
from services.helpers import error_json, extract_json, normalize_section_payload, text_preview
from services.llm_error_handler import handle_llm_exception
from services.llm_client import (
    OPENAI_MODEL_PARSE,
    LLMAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    call_parse_llm,
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
        result = call_parse_llm(
            system,
            user_msg,
            trace_meta={"request_id": request_id, "endpoint": ENDPOINT, "operation": "parse-section"},
        )
    except (LLMRateLimitError, LLMTimeoutError, LLMAPIError) as exc:
        return handle_llm_exception(
            logger=logger,
            exc=exc,
            request_id=request_id,
            llm_provider_target="openai",
            llm_model_target=OPENAI_MODEL_PARSE,
        )

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
    return response
