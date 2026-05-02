# Frontend Implementation Task

## Objective

Build a production-ready MVP frontend for the AI Landing Page Generator.  
The frontend should implement the full user flow from prompt input to final page preview, using the existing backend API.

## Context

- Frontend is the orchestration layer for UX and session state.
- Backend is stateless and returns structured JSON.
- Security is based on `x-anonymous-token` (shared secret model for MVP).

## Tech Requirements

- Framework: React + TypeScript (Vite)
- Routing: React Router v6
- State: React Context + `sessionStorage` (no external state library required)
- API: `fetch` with typed request/response handling

## Functional Scope

Implement these screens and routes:

1. `Screen 1.1 / 1.2` on `/new`
- Prompt textarea
- Tone selector (`professional | friendly | bold | minimal`)
- "Generate landing plan" action
- Loading popup with step progress

2. `Screen 3.1 / 3.2 / 3.3` on `/review`
- Plan cards list
- Edit section flow (free-text textarea)
- Save popup with optional re-parse call
- "Approve & generate page" action

3. `Screen 4` on `/preview`
- Render final page via `<iframe srcdoc={html} sandbox="allow-scripts" />`
- "Back to plan" and "Edit prompt" navigation actions

## API Integration

Use backend endpoints:

1. `POST /api/generate-plan`
- Input: `{ prompt, tone }`
- Output: `{ sections: Section[] }`

2. `POST /api/parse-section`
- Input: `{ sectionId, rawText, sectionType }`
- Output: `Section`

3. `POST /api/generate-page`
- Input: `{ landingPlan }`
- Output: `{ html: string }`

Headers:

- `Content-Type: application/json`
- `x-anonymous-token: <VITE_ANONYMOUS_TOKEN>`

## Required Session State

Store and restore:

- `prompt`
- `tone`
- `landingPlan`
- `finalPage`

State must survive page refresh and be restored on route re-entry.

## Error Handling (Mandatory)

All API calls must:

1. Check `response.ok`
- Do not treat `400/401/429/5xx` as success.
- Parse error payload and throw typed `ApiError`.

2. Map backend errors to UI behavior
- `400` (validation/gating): show clear user-facing message in current screen/popup
- `401` (missing/invalid token): show access/configuration error
- `429` (budget/rate exceeded): show retry-later message
- `5xx`/network: show generic retry state

3. Preserve user input on failure
- Do not clear prompt/textarea when calls fail.

## Prompt Safety UX Requirements

- If backend rejects prompt due to length/gating/red flags, show backend message inline.
- Keep user on the same screen and allow immediate edit + retry.
- Never execute or interpret user text as code on client side.

## Final Page Rendering

Screen 4 renders the HTML string from Call 2 inside a sandboxed iframe:

```tsx
<iframe
  srcdoc={finalPage.html}
  sandbox="allow-scripts"
  style={{ width: '100%', border: 'none' }}
/>
```

- No section components needed for preview
- The `sandbox="allow-scripts"` attribute isolates the page from the parent app
- The iframe is full-width on mobile; centered at max-width 480px on desktop

## Suggested Frontend Structure

```text
frontend/
  src/
    api/
      client.ts
      errors.ts
    components/
      PlanCard.tsx
      Popup.tsx
    pages/
      NewPage.tsx
      ReviewPage.tsx
      PreviewPage.tsx
    store/
      session.ts
    types/
      api.ts
      ui.ts
    App.tsx
    main.tsx
```

## Environment Variables

- `VITE_API_URL`
- `VITE_ANONYMOUS_TOKEN`

## Acceptance Criteria

1. Full 3-route flow works end-to-end with backend.
2. All requests include `x-anonymous-token`.
3. API client checks `response.ok` and throws typed errors.
4. `400`/`401`/`429` are displayed correctly in UI.
5. Session state persists and restores on refresh.
6. Edit-section re-parse flow works and merges updated section.
7. Final preview renders `html` response inside sandboxed iframe.
8. iframe uses `sandbox="allow-scripts"` and no parent-context access.

## Deliverables

- Working frontend code
- `.env.example` with required frontend vars
- Short run instructions for local development
- Basic manual test checklist for success and error paths
