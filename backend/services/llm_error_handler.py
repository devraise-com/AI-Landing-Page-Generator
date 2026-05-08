import logging

from fastapi.responses import JSONResponse

from services.helpers import error_json
from services.llm_client import LLMAPIError, LLMRateLimitError, LLMTimeoutError

_LLM_ERROR_MAP: dict[type[Exception], tuple[str, int, str]] = {
    LLMRateLimitError: ("RATE_LIMITED", 429, "Rate limit exceeded. Please try again shortly."),
    LLMTimeoutError: ("TIMEOUT", 504, "Request timed out. Please try again."),
    LLMAPIError: ("LLM_ERROR", 502, "LLM service error. Please try again."),
}


def handle_llm_exception(
    *,
    logger: logging.Logger,
    exc: LLMRateLimitError | LLMTimeoutError | LLMAPIError,
    request_id: str,
    llm_provider_target: str,
    llm_model_target: str,
) -> JSONResponse:
    code, status, message = _LLM_ERROR_MAP.get(type(exc), _LLM_ERROR_MAP[LLMAPIError])

    extra: dict[str, str] = {
        "event": "llm.error",
        "request_id": request_id,
        "error_code": code,
        "llm_provider_target": llm_provider_target,
        "llm_model_target": llm_model_target,
    }
    if isinstance(exc, LLMAPIError):
        extra["detail"] = str(exc)

    logger.error("llm.error", extra=extra)
    return error_json(message, code, status, request_id)
