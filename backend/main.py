import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from logging_config import setup_logging
setup_logging()

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import generate_plan, parse_section, generate_page
from services.langfuse_observability import flush_langfuse


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    flush_langfuse()


app = FastAPI(title="Landing Page Builder API", lifespan=lifespan)

allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "x-anonymous-token"],
)

app.include_router(generate_plan.router)
app.include_router(parse_section.router)
app.include_router(generate_page.router)


@app.exception_handler(HTTPException)
async def unified_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 422: "VALIDATION_ERROR"}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.detail),
            "code": code_map.get(exc.status_code, "HTTP_ERROR"),
            "request_id": str(uuid.uuid4()),
        },
    )


@app.exception_handler(RequestValidationError)
async def unified_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Collapse Pydantic's detail list into a single readable string
    messages = "; ".join(
        f"{' → '.join(str(loc) for loc in e['loc'] if loc != 'body')}: {e['msg']}"
        for e in exc.errors()
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": messages or "Request validation failed.",
            "code": "VALIDATION_ERROR",
            "request_id": str(uuid.uuid4()),
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}
