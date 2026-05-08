# AI Landing Page Generator

Two-step pipeline: user provides a product description → AI generates a structured section plan → user approves/edits → AI generates a full HTML page.

## Structure

```
backend/   FastAPI, Python — LLM orchestration, prompt building, guardrails
frontend/  Vite + React + TypeScript — three-page flow (New → Review → Preview)
```

## Running locally

**Backend**
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```
Requires `backend/.env` — copy from `backend/.env.example`.

**Frontend**
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```
Requires `frontend/.env` — copy from `frontend/.env.example`.

## Key design decisions

- **Two LLM providers in use**: OpenAI (GPT-4.1) for plan generation and section parsing; Anthropic Claude Sonnet for HTML page generation. This split is intentional and fixed — do not add provider switching.
- **Auth**: every API request requires an `x-anonymous-token` header matching `ANONYMOUS_TOKEN` in env. No user accounts.
- **Frontend ↔ backend**: REST only, no websockets. The base URL is configured via `VITE_API_BASE_URL` in the frontend env.
