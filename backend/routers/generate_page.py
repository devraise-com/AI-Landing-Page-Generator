import logging
import uuid

from fastapi import APIRouter, Depends

from middleware.anon_token import verify_token
from schemas.generate_page import GeneratePageRequest, GeneratePageResponse
from services.guardrails import validate_landing_plan
from services.helpers import error_json
from services.llm_error_handler import handle_llm_exception
from services.llm_client import (
    SONNET,
    LLMAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    call_sonnet,
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

    ok, msg = validate_landing_plan(req.landingPlan.model_dump())
    if not ok:
        logger.warning("guardrails.rejected", extra={
            "event": "guardrails.rejected", "request_id": request_id, "endpoint": ENDPOINT,
        })
        return error_json(msg, "PROMPT_REJECTED", 400, request_id)

    system = load_prompt("page_prompt.txt")
    user_msg = f"Landing page plan:\n{req.landingPlan.model_dump_json(indent=2)}"

    try:
        result = call_sonnet(
            system,
            user_msg,
            max_tokens=16000,
            trace_meta={"request_id": request_id, "endpoint": ENDPOINT, "operation": "generate-page"},
        )
    except (LLMRateLimitError, LLMTimeoutError, LLMAPIError) as exc:
        return handle_llm_exception(
            logger=logger,
            exc=exc,
            request_id=request_id,
            llm_provider_target="anthropic",
            llm_model_target=SONNET,
        )

    html = result.text.strip()
    if html.startswith("```"):
        html = html.split("\n", 1)[-1]
        html = html.rsplit("```", 1)[0].strip()

    response = GeneratePageResponse(html=html)
    return response
