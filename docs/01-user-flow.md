# Landing Page Builder — User Flow

## Overview

User describes a product → AI generates a structured landing page plan with copy and visual directions → User reviews and optionally edits sections → AI generates the final landing page.

**LLM calls: 2 required, 1 optional**

---

## Screen 1.1 — Prompt input

**Route:** `/new`

User opens the app and fills in two inputs:

- **Prompt** (textarea, free text) — describes the product, offer, target audience, and any visual preferences. Example: *"A SaaS tool for freelancers to send invoices in 60 seconds. Bold and modern feel, dark hero section."*
- **Tone** (single select) — Professional / Friendly / Bold / Minimal

User taps **"Generate landing plan"**.

---

## Screen 1.2 — Generating (popup over Screen 1.1)

**Route:** `/new` (same, popup overlay)

Triggered immediately on submit. Screen 1.1 blurs behind a centered popup showing step-by-step progress.

### 🤖 LLM Call 1 — Generate landing plan

| Parameter | Value |
|-----------|-------|
| Type | Single call, streaming optional |
| Endpoint | `POST /api/generate-plan` |
| Input | `{ prompt: string, tone: string }` |
| Output | Structured JSON (see schema below) |
| Model | `PLAN_LLM_PROVIDER` route (Anthropic/OpenAI) |
| When | On "Generate landing plan" tap |

**System prompt goal:** Parse the user's free-text description into a structured landing page plan. Dynamically select sections based on user intent (e.g. hero, features, faq, pricing, testimonials, cta — whatever fits). For each section generate: name, type, copy fields, and a visual direction hint. Return 3–8 sections.

**Output schema:**
```json
{
  "sections": [
    {
      "id": "hero",
      "name": "Hero",
      "type": "hero",
      "fields": {
        "headline": "Invoice faster. Get paid sooner.",
        "subheadline": "Send invoices in under 60 seconds — no templates.",
        "cta_text": "Start for free"
      },
      "visual_direction": "Split layout — dashboard screenshot left, headline right. Purple gradient background."
    },
    {
      "id": "features",
      "name": "Features",
      "type": "features",
      "fields": {
        "items": [
          { "label": "One-tap invoice creation", "description": "Create and send in seconds" },
          { "label": "Auto-fill client details", "description": "Save time on every invoice" },
          { "label": "PDF + Stripe link", "description": "Get paid instantly online" }
        ]
      },
      "visual_direction": "3-column icon cards, light green tint background."
    }
  ]
}
```

**Progress steps shown in popup:**
1. Analyzing your product
2. Defining page structure
3. Writing section copy
4. Generating visual directions ← last step, stays until response arrives

**On success:** Navigate to Screen 3.1, pass plan JSON via session storage (`key: landingPlan`).
**On error:** Replace spinner with error state, show "Try again" button.

---

## Screen 3.1 — View mode (Landing plan)

**Route:** `/review`

User sees the generated plan as a list of section cards. Each card shows:

- Section name + type tag
- Copy fields (headline, subheadline, items, quote, etc.)
- Visual direction (color swatch + description text)
- Edit icon → navigates to Screen 3.2 for that section
- Delete icon → removes section from plan (local state only, no API call)

User can scroll through all sections. Two actions at the bottom:

- **"Approve & generate page"** → explicit approval of the plan as-is. Commits the current state of `landingPlan` and triggers LLM Call 2. This tap is the user's approval gate — satisfies the "review and approve draft" requirement.
- **"Edit prompt"** → navigates back to Screen 1.1 with prompt and tone restored from session

---

## Screen 3.2 — Edit mode

**Route:** `/review` (same route, different view state)

Triggered by tapping the edit icon on any section card.

User sees a single focused editor for the selected section:

- Card header shows section name + type (non-editable)
- Textarea pre-filled with section content as structured free text:

```
Headline: Invoice faster. Get paid sooner.
Subheadline: Send invoices in under 60 seconds — no templates.
Visual: Split layout, purple gradient background.
```

- On **desktop**: sidebar shows all section names for quick switching without going back
- **"Save changes"** → dirty check: if content changed → Screen 3.3 popup; if unchanged → back to Screen 3.1
- **"Undo"** → restore textarea to snapshot taken on mount, no API call

---

## Screen 3.3 — Save popup (over Screen 3.2)

**Route:** `/review` (same, popup overlay)

Shown only when user has made changes to the section text.

Popup asks: *"Apply changes? AI will re-generate the Hero card based on your edits."*

- **"Re-generate"** → triggers LLM Call 1b
- **"Cancel"** → dismiss popup, return to Screen 3.2 unchanged

### 🤖 LLM Call 1b — Re-parse edited section (optional)

| Parameter | Value |
|-----------|-------|
| Type | Single call, lightweight |
| Endpoint | `POST /api/parse-section` |
| Input | `{ sectionId: string, rawText: string, sectionType: string }` |
| Output | Updated section JSON (same schema as LLM Call 1 single section) |
| Model | `PARSE_LLM_PROVIDER` route (Anthropic/OpenAI) |
| When | Only if user edited a section and confirmed in popup |

**System prompt goal:** Parse the free-text textarea back into structured section JSON. Extract field values from labeled lines (`Headline: ...`, `Visual: ...`, etc.). Return updated section object.

**On success:** Merge updated section into `landingPlan` in session. Navigate to Screen 3.1.
**On error:** Show inline error in popup. Keep textarea content intact.

---

## Screen 4 — Final page

**Route:** `/preview`

Triggered by "Approve & generate page" on Screen 3.1.

### 🤖 LLM Call 2 — Generate final landing page

| Parameter | Value |
|-----------|-------|
| Type | Single call, can be streamed |
| Endpoint | `POST /api/generate-page` |
| Input | Full `landingPlan` JSON from session |
| Output | `{ html: string }` — complete standalone HTML/CSS page |
| Model | Claude Sonnet (`claude-sonnet-4-6`, current fixed path) |
| When | On "Approve & generate page" tap |

**System prompt goal:** Take the structured plan and generate a complete, self-contained landing page as a single HTML string with inline CSS. The HTML must be a full document (`<!DOCTYPE html>` … `</html>`) that renders correctly on its own, with no external dependencies.

**Page structure:**
- App header: "Final page" title with green success badge
- Preview area: `<iframe srcdoc={html} sandbox="allow-scripts" />` — renders the full landing page in isolation
- Footer: "Back to plan" (→ Screen 3.1) and "Edit prompt" (→ Screen 1.1)

**Responsive behavior:**
- The generated HTML itself handles responsive layout via inline CSS (the LLM prompt specifies mobile-first)
- The iframe is full-width on mobile; on desktop it is centered at max-width 480px to preserve mobile-first feel

---

## LLM Calls Summary

| Call | Screen | Trigger | Model | Purpose |
|------|--------|---------|-------|---------|
| Call 1 | 1.2 | "Generate landing plan" tap | `PLAN_LLM_PROVIDER` | Parse prompt → structured plan JSON |
| Call 1b | 3.3 | "Re-generate" in popup | `PARSE_LLM_PROVIDER` | Re-parse edited section free text → section JSON |
| Call 2 | 4 | "Approve & generate page" tap | Sonnet (Anthropic) | Structured plan → complete HTML/CSS landing page |

Call 1b is optional — only fires if user edits a section and confirms. Calls 1 and 2 are always required.

---

## Session State

| Key | Set on | Used on |
|-----|--------|---------|
| `prompt` | Screen 1.1 submit | Screen 1.1 restore (from "Edit prompt") |
| `tone` | Screen 1.1 submit | Screen 1.1 restore (from "Edit prompt") |
| `landingPlan` | LLM Call 1 success | Screen 3.1, 3.2, LLM Call 2 |
| `finalPage` | LLM Call 2 success | Screen 4 render (`{ html: string }`) |
