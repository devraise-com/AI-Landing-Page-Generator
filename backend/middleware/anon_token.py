import os

from fastapi import Header, HTTPException


def verify_token(x_anonymous_token: str | None = Header(default=None)) -> None:
    """FastAPI dependency: validates x-anonymous-token header.
    Raises 401 for both missing and invalid token. Never logs the token value."""
    expected = os.getenv("ANONYMOUS_TOKEN", "")
    if not x_anonymous_token or x_anonymous_token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
