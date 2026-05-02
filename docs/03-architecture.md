# Landing Page Builder — Architecture

## Stack

| Layer | Technology | Deploy |
|-------|-----------|--------|
| Frontend | Vite + React + TypeScript | Vercel |
| Backend | FastAPI (Python) | Railway |
| LLM | Anthropic Claude API + OpenAI Responses API | — |

---

## Repository Structure

```
AI-Landing-Page-Generator/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PlanCard.tsx
│   │   │   └── Popup.tsx
│   │   ├── pages/
│   │   │   ├── NewPage.tsx        # Screen 1.1 + 1.2
│   │   │   ├── ReviewPage.tsx     # Screen 3.1 + 3.2 + 3.3
│   │   │   └── PreviewPage.tsx    # Screen 4
│   │   ├── api/
│   │   │   ├── client.ts          # fetch wrappers for 3 endpoints
│   │   │   └── errors.ts          # typed ApiError helpers
│   │   ├── store/
│   │   │   └── session.ts         # landingPlan, prompt, tone
│   │   ├── types/
│   │   │   ├── api.ts
│   │   │   └── ui.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── vite.config.ts
│   └── package.json
│
├── backend/
│   ├── main.py
│   ├── logging_config.py          # JSON log formatter, setup_logging()
│   ├── routers/
│   │   ├── generate_plan.py       # POST /api/generate-plan
│   │   ├── parse_section.py       # POST /api/parse-section
│   │   └── generate_page.py       # POST /api/generate-page
│   ├── schemas/
│   │   ├── generate_plan.py       # request/response models
│   │   ├── parse_section.py
│   │   └── generate_page.py
│   ├── services/
│   │   ├── llm_client.py          # LLM calls, timeout/retry policy, cost estimation
│   │   ├── guardrails.py          # prompt length / topic / red-flag validation
│   │   ├── helpers.py             # error_json, extract_json, normalize helpers, text_preview
│   │   └── prompt_loader.py
│   ├── middleware/
│   │   └── anon_token.py          # x-anonymous-token validation
│   ├── prompts/
│   │   ├── plan_prompt.txt
│   │   ├── parse_prompt.txt
│   │   └── page_prompt.txt
│   ├── .env.example
│   └── requirements.txt
│
├── docs/
│   ├── 01-user-flow.md
│   ├── 02-llm-plan.md
│   ├── 03-architecture.md
│   ├── 04-backend-task.md
│   └── 05-frontend-task.md
│
└── README.md
```

---

## Frontend

### Routing

React Router v6. Three routes map directly to app screens:

| Route | Page | Screens |
|-------|------|---------|
| `/new` | `NewPage.tsx` | 1.1 Prompt input, 1.2 Generating popup |
| `/review` | `ReviewPage.tsx` | 3.1 View mode, 3.2 Edit mode, 3.3 Save popup |
| `/preview` | `PreviewPage.tsx` | 4 Final page |

### State Management

React Context + sessionStorage. No external state library needed for this scope.

```ts
// store/session.ts
interface SessionState {
  prompt: string
  tone: string
  landingPlan: LandingPlan | null
  finalPage: FinalPage | null
}
```

```ts
// types/api.ts
interface FinalPage {
  html: string
}
```

All state persists in `sessionStorage` — survives page refresh, cleared on tab close. "Edit prompt" and "Back to plan" navigation restores state from session without re-fetching.

### Final Page Rendering

Screen 4 renders the HTML returned by Call 2 inside a sandboxed iframe:

```tsx
// pages/PreviewPage.tsx
<iframe
  srcdoc={finalPage.html}
  sandbox="allow-scripts"
  style={{ width: '100%', border: 'none' }}
/>
```

The `html` value is a complete standalone document with inline CSS produced by the LLM. No React section components are needed for the preview — the iframe handles rendering in full isolation.

### API Client

```ts
// api/client.ts
const BASE_URL = import.meta.env.VITE_API_URL
const TOKEN = import.meta.env.VITE_ANONYMOUS_TOKEN

const authHeaders = {
  'Content-Type': 'application/json',
  'x-anonymous-token': TOKEN
}

type ApiErrorBody = { error?: string; code?: string; request_id?: string }

class ApiError extends Error {
  status: number
  code?: string
  requestId?: string

  constructor(status: number, body: ApiErrorBody) {
    super(body.error ?? `Request failed with status ${status}`)
    this.status = status
    this.code = body.code
    this.requestId = body.request_id
  }
}

async function requestJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify(body),
  })

  const payload = await response.json()
  if (!response.ok) throw new ApiError(response.status, payload)
  return payload as T
}

export const generatePlan = (prompt: string, tone: string) =>
  requestJson<GeneratePlanResponse>('/api/generate-plan', { prompt, tone })

export const parseSection = (sectionId: string, rawText: string, sectionType: string) =>
  requestJson<Section>('/api/parse-section', { sectionId, rawText, sectionType })

export const generatePage = (landingPlan: LandingPlan) =>
  requestJson<GeneratePageResponse>('/api/generate-page', { landingPlan })
```

---

## Backend

### FastAPI Structure

```python
# main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import generate_plan, parse_section, generate_page

app = FastAPI()
allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
  CORSMiddleware,
  allow_origins=allowed_origins,
  allow_methods=["GET", "POST"],
  allow_headers=["Content-Type", "x-anonymous-token"],
)

app.include_router(generate_plan.router)
app.include_router(parse_section.router)
app.include_router(generate_page.router)
```

### Prompt Safety Guardrails

Before any LLM call, backend validates user input:

- Prompt length limit from env var `INPUT_PROMPT_MAX_CHARS` (fallback: `PROMPT_MAX_CHARS`)
- Topic gating: only landing-page generation/editing requests are accepted
- Red-flag blocking: reject exploit/malware/SQLi/prompt-leak/command-execution intent
- On violation, return `400 Bad Request` using the unified error format

### LLM Reliability Policy

- Provider switching:
  - `PLAN_LLM_PROVIDER` controls `POST /api/generate-plan` (`anthropic|openai`)
  - `PARSE_LLM_PROVIDER` controls `POST /api/parse-section` (`anthropic|openai`)
  - `POST /api/generate-page` stays on Anthropic Sonnet
- Timeout config (env):
  - Anthropic: `SONNET_TIMEOUT_SECONDS`, `HAIKU_TIMEOUT_SECONDS`
  - OpenAI: `OPENAI_PLAN_TIMEOUT_SECONDS`, `OPENAI_PARSE_TIMEOUT_SECONDS`
- Retry policy: `2` attempts total, only for `429` and `5xx`
- Backoff:
  - Anthropic: SDK-managed retries (`max_retries=1`)
  - OpenAI: client-level retry loop for `429`/`5xx`
- Parsing robustness:
  - JSON extraction tolerates fenced/mixed output
  - `generate-plan` validates sections one-by-one, skips invalid sections, logs partial results, and returns `PARSE_ERROR` only if all sections are invalid

### Observability

- JSON logs for each request lifecycle:
  - `request.start`
  - `llm.ok` or `llm.error`
  - `request.done`
- `request.start` includes target routing metadata:
  - `llm_provider_target`
  - `llm_model_target`
- `llm.ok` includes execution metadata:
  - `llm_provider`, `model`
  - `input_tokens`, `output_tokens`, `duration_ms`
  - `stop_reason`
  - `estimated_cost_usd`
- Truncation warnings:
  - `llm.truncated` is logged when `stop_reason == "max_tokens"`
- Preview length of logged prompt/output snippets is controlled by `LOG_TEXT_PREVIEW_CHARS`

### Endpoints

#### `POST /api/generate-plan`

```python
# Input
class GeneratePlanRequest(BaseModel):
    prompt: str
    tone: str  # "professional" | "friendly" | "bold" | "minimal"

# Output
class Section(BaseModel):
    id: str
    name: str
    type: str  # dynamic kebab-case, e.g. "hero", "features", "faq", "pricing", "cta"
    fields: dict
    visual_direction: str

class GeneratePlanResponse(BaseModel):
    sections: list[Section]
```

Model route:
- Anthropic: `claude-sonnet-4-6`
- OpenAI: `OPENAI_MODEL_PLAN` (default `gpt-4.1`)
System prompt: `prompts/plan_prompt.txt`

---

#### `POST /api/parse-section`

```python
# Input
class ParseSectionRequest(BaseModel):
    sectionId: str
    rawText: str
    sectionType: str

# Output: single Section object (same schema as above)
```

Model route:
- Anthropic: `claude-haiku-4-5-20251001`
- OpenAI: `OPENAI_MODEL_PARSE` (default `gpt-4.1-mini`)
System prompt: `prompts/parse_prompt.txt`

---

#### `POST /api/generate-page`

```python
# Input
class LandingPlan(BaseModel):
    sections: list[Section]

class GeneratePageRequest(BaseModel):
    landingPlan: LandingPlan

# Output
class GeneratePageResponse(BaseModel):
    html: str
```

Model: `claude-sonnet-4-6` (current fixed provider path)
System prompt: `prompts/page_prompt.txt`

---

### Prompts

System prompts are stored as plain `.txt` files in `backend/prompts/`. Loaded at startup, not hardcoded inline. This makes them easy to iterate without touching application code.

```python
# routers/generate_plan.py
from services.llm_client import call_plan_llm
from services.prompt_loader import load_prompt  # cached at first read via lru_cache

system = load_prompt("plan_prompt.txt")

@router.post("/api/generate-plan")
async def generate_plan(req: GeneratePlanRequest):
    result = call_plan_llm(system, f"Prompt: {req.prompt}\nTone: {req.tone}")
    # parse JSON from result.text; result also carries .model, .input_tokens,
    # .output_tokens, .duration_ms used for structured logging + cost estimation
    ...
```

---

## Data Flow

```
Browser (Vite + React)
    │
    │  POST /api/generate-plan { prompt, tone }
    ▼
FastAPI
    │
    │  provider-router (PLAN_LLM_PROVIDER)
    ▼
Anthropic API or OpenAI API
    │
    │  { sections: [...] }
    ▼
FastAPI  ──────────────────────────────────────────►  Browser
                                                  sessionStorage.landingPlan
                                                       │
                                          (optional)   │  POST /api/parse-section
                                                       │  { sectionId, rawText, sectionType }
                                                       ▼
                                                   FastAPI → provider-router (PARSE_LLM_PROVIDER)
                                                       │
                                                  merge into landingPlan
                                                       │
                                                       │  POST /api/generate-page
                                                       │  { landingPlan }
                                                       ▼
                                                   FastAPI → Anthropic Sonnet
                                                       │
                                                  { html: string }
                                                       │
                                                  render in sandboxed iframe
```

---

## Environment Variables

```bash
# .env.example
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ANONYMOUS_TOKEN=your_token_here
INPUT_PROMPT_MAX_CHARS=1000
PROMPT_MAX_CHARS=1000
LANDING_PLAN_MAX_CHARS=5000
ALLOWED_ORIGINS=http://localhost:5173
LOG_TEXT_PREVIEW_CHARS=200

# Provider switch (anthropic|openai)
PLAN_LLM_PROVIDER=anthropic
PARSE_LLM_PROVIDER=anthropic

# OpenAI models
OPENAI_MODEL_PLAN=gpt-4.1
OPENAI_MODEL_PARSE=gpt-4.1-mini

# Timeouts (seconds)
SONNET_TIMEOUT_SECONDS=120
HAIKU_TIMEOUT_SECONDS=30
OPENAI_PLAN_TIMEOUT_SECONDS=120
OPENAI_PARSE_TIMEOUT_SECONDS=30

# Optional — override default per-model pricing for cost logging (USD per 1M tokens)
ANTHROPIC_COST_SONNET_INPUT_PER_MTOKENS=3.0
ANTHROPIC_COST_SONNET_OUTPUT_PER_MTOKENS=15.0
ANTHROPIC_COST_HAIKU_INPUT_PER_MTOKENS=0.8
ANTHROPIC_COST_HAIKU_OUTPUT_PER_MTOKENS=4.0
OPENAI_PLAN_COST_INPUT_PER_MTOKENS=2.0
OPENAI_PLAN_COST_OUTPUT_PER_MTOKENS=8.0
OPENAI_PARSE_COST_INPUT_PER_MTOKENS=0.4
OPENAI_PARSE_COST_OUTPUT_PER_MTOKENS=1.6

# Optional — log verbosity
LOG_LEVEL=INFO
```

```bash
# frontend/.env.example
VITE_API_URL=http://localhost:8000
VITE_ANONYMOUS_TOKEN=your_token_here
```

---

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev          # starts at localhost:5173
```

---

## Deploy

| Service | What | Config |
|---------|------|--------|
| Vercel | Frontend | Set `VITE_API_URL` and `VITE_ANONYMOUS_TOKEN` in env vars |
| Railway | Backend | Set `ANONYMOUS_TOKEN`, `INPUT_PROMPT_MAX_CHARS`, `ALLOWED_ORIGINS`, provider/model/timeouts; set `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY` based on provider selection |

CORS `allow_origins` in `main.py` must include the Vercel deployment URL.
