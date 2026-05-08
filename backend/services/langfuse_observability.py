import os
from contextlib import nullcontext
from typing import Any, ContextManager

try:
    from langfuse import get_client
except ImportError:  # pragma: no cover - optional dependency
    get_client = None  # type: ignore[assignment]


def _has_langfuse_credentials() -> bool:
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
        and os.getenv("LANGFUSE_BASE_URL")
    )


def _get_langfuse_client() -> Any | None:
    if get_client is None or not _has_langfuse_credentials():
        return None
    try:
        return get_client()
    except Exception:
        return None


def flush_langfuse() -> None:
    client = _get_langfuse_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        pass


def start_llm_generation(
    *,
    name: str,
    model: str,
    provider: str,
    input_payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> ContextManager[Any | None]:
    """Return a Langfuse generation context manager, or a no-op fallback."""
    client = _get_langfuse_client()
    if client is None:
        return nullcontext(None)

    try:
        return client.start_as_current_observation(
            as_type="generation",
            name=name,
            model=model,
            input=input_payload,
            metadata={"provider": provider, **(metadata or {})},
        )
    except Exception:
        # Langfuse setup errors must never break API requests.
        return nullcontext(None)
