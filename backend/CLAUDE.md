# Backend

FastAPI service. Entry point: `main.py`. Run with:
```bash
python -m uvicorn main:app --reload --port 8000
```

## Endpoints

| Route | Router | LLM |
|---|---|---|
| `POST /api/generate-plan` | `routers/generate_plan.py` | OpenAI `OPENAI_MODEL_PLAN` (default: gpt-4.1) |
| `POST /api/parse-section` | `routers/parse_section.py` | OpenAI `OPENAI_MODEL_PARSE` (default: gpt-4.1-mini) |
| `POST /api/generate-page` | `routers/generate_page.py` | Anthropic `SONNET` (claude-sonnet-4-6) |
| `GET /health` | `main.py` | — |

## Architecture

```
routers/          HTTP layer — validation, LLM call, response shaping
schemas/          Pydantic request/response models
services/
  llm_client.py         call_plan_llm / call_parse_llm / call_sonnet — only entry points for LLM calls
  llm_error_handler.py  handle_llm_exception() — maps LLM exceptions to HTTP responses
  langfuse_observability.py  optional AI tracing (no-ops when env vars absent)
  guardrails.py         validate_prompt / validate_landing_plan — input safety checks
  helpers.py            extract_json, normalize_*_payload, error_json, text_preview
  prompt_loader.py      load_prompt(name) — cached reads from prompts/
middleware/
  anon_token.py         verify_token FastAPI dependency
prompts/          .txt system prompts — plan_prompt.txt, parse_prompt.txt, page_prompt.txt
```

## Conventions

**Adding a new endpoint** — follow the existing pattern:
1. Pydantic schema in `schemas/`
2. Router in `routers/` — validate input with guardrails, call llm via `llm_client`, return structured response
3. Register router in `main.py`

**LLM calls** — always go through `llm_client.py` public functions. Never instantiate Anthropic/OpenAI clients elsewhere.

**Error handling** — use `handle_llm_exception()` for LLM errors, `error_json()` for everything else. Both return `JSONResponse` directly.

**Logging** — every `logger.*` call must include `extra={"event": "<event.name>", "request_id": request_id, ...}`. The `_StructuredFormatter` in `logging_config.py` appends these fields to terminal output. Without `extra`, structured context is lost.

**Observability** — pass `trace_meta={"request_id": ..., "endpoint": ..., "operation": ...}` to every LLM call. This feeds Langfuse when credentials are present; ignored otherwise.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | For generate-page (Sonnet) |
| `OPENAI_API_KEY` | yes | For generate-plan and parse-section |
| `ANONYMOUS_TOKEN` | yes | Shared token for `x-anonymous-token` header |
| `ALLOWED_ORIGINS` | yes | Comma-separated CORS origins |
| `LOG_LEVEL` | no | Default `INFO` |
| `INPUT_PROMPT_MAX_CHARS` | no | Default 1000 |
| `LANDING_PLAN_MAX_CHARS` | no | Default 5× input limit |
| `LOG_TEXT_PREVIEW_CHARS` | no | Default 200 — truncation in parse error logs |
| `SONNET_TIMEOUT_SECONDS` | no | Default 120 |
| `OPENAI_PLAN_TIMEOUT_SECONDS` | no | Default 120 |
| `OPENAI_PARSE_TIMEOUT_SECONDS` | no | Default 30 |
| `OPENAI_MODEL_PLAN` | no | Default `gpt-4.1` |
| `OPENAI_MODEL_PARSE` | no | Default `gpt-4.1-mini` |
| `LANGFUSE_PUBLIC_KEY` | no | Langfuse tracing (all three required to enable) |
| `LANGFUSE_SECRET_KEY` | no | |
| `LANGFUSE_BASE_URL` | no | |
