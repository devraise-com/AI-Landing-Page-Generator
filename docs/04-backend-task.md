# Backend Implementation Task

## Objective

Build a production-ready MVP backend for the AI Landing Page Generator.  
The backend should expose 3 API endpoints that orchestrate LLM calls and return structured JSON for the frontend flow.

## Context

Frontend state is kept in browser session storage (`prompt`, `tone`, `landingPlan`).  
Backend is stateless and should process each request independently.

## Tech Requirements

- Framework: FastAPI (Python 3.11+)
- LLM providers: Anthropic + OpenAI (switchable via env)
- API style: JSON over HTTP
- Deployment target: Railway (or equivalent)

## Functional Scope

Implement these endpoints:

1. `POST /api/generate-plan`
Input:
- `prompt: string`
- `tone: "professional" | "friendly" | "bold" | "minimal"`

Output:
- `sections: Section[]` where each section includes:
  - `id`
  - `name`
  - `type` (dynamic kebab-case string, e.g. `hero`, `features`, `faq`, `pricing`, `testimonial`, `cta`)
  - `fields` (object)
  - `visual_direction` (string)

2. `POST /api/parse-section`
Input:
- `sectionId: string`
- `rawText: string`
- `sectionType: string`

Output:
- one updated `Section` object in the same schema as above

3. `POST /api/generate-page`
Input:
- `landingPlan: object` (full approved plan)

Output:
- `{ html: string }` — complete standalone HTML/CSS document

## Security Requirement (Mandatory)

All `POST /api/*` endpoints must require header:

- `x-anonymous-token: <token>`

Behavior:

- If header is missing: return `401 Unauthorized`
- If token value is invalid: return `401 Unauthorized`
- If token is valid: continue normal request handling

Token source:

- Validate against environment variable `ANONYMOUS_TOKEN`

Constraints:

- Do not log the raw token value
- Keep validation centralized (middleware or shared dependency)
- Never execute code, shell commands, SQL, or external tool calls from user prompt content

## Prompt Safety Guardrails (Mandatory)

Apply validation before any LLM call:

1. Prompt length limit (via environment variable)
- Use env var: `INPUT_PROMPT_MAX_CHARS` (fallback to legacy `PROMPT_MAX_CHARS`)
- If `prompt` length exceeds this limit, return `400 Bad Request` with a clear validation error

2. Topic gating (landing-page use case only)
- Accept only requests relevant to landing page generation/editing
- If request is out of scope, return `400 Bad Request`

3. Red-flag blocking
- Block obvious malicious or policy-violating intent, including:
  - exploit instructions
  - malware creation/distribution
  - SQL injection payload crafting
  - prompt leaking / system prompt exfiltration attempts
  - command-execution instructions
- On detection, return `400 Bad Request`

## Non-Functional Requirements

- Structured request/response validation via Pydantic models
- Unified error response format: `{ "error": "string", "code": "string", "request_id": "string(uuid)" }`
- LLM provider routing:
  - `generate-plan`: `PLAN_LLM_PROVIDER` (`anthropic|openai`)
  - `parse-section`: `PARSE_LLM_PROVIDER` (`anthropic|openai`)
  - `generate-page`: Anthropic Sonnet (fixed)
- Timeouts for LLM calls are env-driven:
  - `SONNET_TIMEOUT_SECONDS`, `HAIKU_TIMEOUT_SECONDS`
  - `OPENAI_PLAN_TIMEOUT_SECONDS`, `OPENAI_PARSE_TIMEOUT_SECONDS`
- Retry strategy: 2 attempts total (`max_retries=1` equivalent), only on `429` and `5xx` (Anthropic SDK retries + OpenAI client retry loop)
- CORS configuration via environment (`ALLOWED_ORIGINS`); `allow_headers` must include `Content-Type` and `x-anonymous-token`
- Health endpoint: `GET /health`
- Clear JSON logs with request IDs and LLM metadata (`provider/model/tokens/duration/cost`)
- If plan parsing returns partially invalid sections, log skipped section errors and return valid sections instead of failing entire request

## Suggested Project Structure

```text
backend/
  main.py
  logging_config.py
  routers/
    generate_plan.py
    parse_section.py
    generate_page.py
  schemas/
    generate_plan.py
    parse_section.py
    generate_page.py
  services/
    llm_client.py
    guardrails.py
    helpers.py
    prompt_loader.py
  middleware/
    anon_token.py
  prompts/
    plan_prompt.txt
    parse_prompt.txt
    page_prompt.txt
  .env.example
  requirements.txt
```

## Environment Variables

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY` (required only when any provider switch uses OpenAI)
- `ANONYMOUS_TOKEN`
- `ALLOWED_ORIGINS`
- `INPUT_PROMPT_MAX_CHARS` (with fallback `PROMPT_MAX_CHARS`)
- `LANDING_PLAN_MAX_CHARS`
- `LOG_TEXT_PREVIEW_CHARS`
- `PORT` (optional)
- `PLAN_LLM_PROVIDER` (`anthropic|openai`)
- `PARSE_LLM_PROVIDER` (`anthropic|openai`)
- `OPENAI_MODEL_PLAN`
- `OPENAI_MODEL_PARSE`
- `SONNET_TIMEOUT_SECONDS`
- `HAIKU_TIMEOUT_SECONDS`
- `OPENAI_PLAN_TIMEOUT_SECONDS`
- `OPENAI_PARSE_TIMEOUT_SECONDS`
- `ANTHROPIC_COST_SONNET_INPUT_PER_MTOKENS` (optional, default `3.0`)
- `ANTHROPIC_COST_SONNET_OUTPUT_PER_MTOKENS` (optional, default `15.0`)
- `ANTHROPIC_COST_HAIKU_INPUT_PER_MTOKENS` (optional, default `0.8`)
- `ANTHROPIC_COST_HAIKU_OUTPUT_PER_MTOKENS` (optional, default `4.0`)
- `OPENAI_PLAN_COST_INPUT_PER_MTOKENS` (optional, default `2.0`)
- `OPENAI_PLAN_COST_OUTPUT_PER_MTOKENS` (optional, default `8.0`)
- `OPENAI_PARSE_COST_INPUT_PER_MTOKENS` (optional, default `0.4`)
- `OPENAI_PARSE_COST_OUTPUT_PER_MTOKENS` (optional, default `1.6`)
- `LOG_LEVEL` (optional, default `INFO`)

## Acceptance Criteria

1. All 3 endpoints are implemented and return validated JSON responses.
2. `x-anonymous-token` is enforced on all `POST /api/*` routes.
3. Missing or wrong token always returns `401`.
4. Valid token allows normal processing.
5. Prompts are loaded from files in `backend/prompts/`, not hardcoded inline.
6. `.env.example` and README backend setup are updated.
7. Basic smoke tests (or curl examples) confirm endpoint behavior.
8. Prompt longer than `INPUT_PROMPT_MAX_CHARS` (or fallback `PROMPT_MAX_CHARS`) returns `400`.
9. Out-of-scope or red-flag prompts are rejected with `400` before LLM call.
10. User prompt text is never executed as code/commands.
11. Logs include `llm_provider_target`/`llm_model_target` on request start and `llm_provider`/`model` on LLM success.

## Deliverables

- Working backend code
- Updated documentation for local run and environment setup
- Example requests/responses for each endpoint
