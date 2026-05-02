# Landing Page Builder — LLM Plan

## Overview

Total LLM calls: **2 required + 1 optional**

```
User prompt + tone
        ↓
[Call 1: Generate plan]   ← PLAN_LLM_PROVIDER (Anthropic/OpenAI)
        ↓ landingPlan JSON
        ↓ (optional — only if user edits a section)
[Call 1b: Re-parse section] ← PARSE_LLM_PROVIDER (Anthropic/OpenAI)
        ↓
[Call 2: Generate page]   ← Sonnet (Anthropic)
        ↓ final landing page
```

---

## Call 1 — Generate landing plan

**Triggered by:** "Generate landing plan" tap on Screen 1.1
**Visible to user:** Screen 1.2 popup with progress steps
**Model:** Provider-switched via `PLAN_LLM_PROVIDER`  
Anthropic path: `claude-sonnet-4-6`  
OpenAI path: `OPENAI_MODEL_PLAN` (default `gpt-4.1`)
**Type:** Single call, streaming optional

### Goal

Parse the user's free-text prompt and tone into a structured landing page plan. Dynamically select which sections to include based on user intent — do not force a fixed template. For each section produce: name, type, copy fields, and a visual direction that reflects any preferences mentioned in the prompt. Return between 3 and 8 sections in logical landing page order.

### Input

```json
{
  "prompt": "A SaaS tool for freelancers to send invoices in 60 seconds. Bold feel, dark hero.",
  "tone": "bold"
}
```

### Output schema

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
        "cta_text": "Start for free",
        "cta_sub": "No credit card needed"
      },
      "visual_direction": "Split layout — product screenshot left, headline right. Dark purple gradient background."
    },
    {
      "id": "features",
      "name": "Features",
      "type": "features",
      "fields": {
        "items": [
          { "label": "One-tap creation", "description": "Create and send in seconds" },
          { "label": "Auto-fill clients", "description": "Save time on every invoice" },
          { "label": "Stripe link", "description": "Get paid instantly online" }
        ]
      },
      "visual_direction": "3-column icon cards, light green tint background."
    },
    {
      "id": "testimonial",
      "name": "Social proof",
      "type": "testimonial",
      "fields": {
        "quote": "I used to spend 30 mins per invoice. Now it's one click.",
        "author": "Maria K.",
        "role": "Freelance designer"
      },
      "visual_direction": "Horizontal quote card, avatar left, subtle green tint."
    },
    {
      "id": "cta",
      "name": "CTA",
      "type": "cta",
      "fields": {
        "headline": "Ready to save time on invoices?",
        "cta_text": "Start for free"
      },
      "visual_direction": "Full-width dark purple banner, centered button."
    }
  ]
}
```

### Progress steps shown in popup

1. Analyzing your product
2. Defining page structure
3. Writing section copy
4. Generating visual directions

### On success
Store `landingPlan` in session. Navigate to Screen 3.1.

### On error
Show error state in popup with "Try again" button. Resubmit same prompt.

### Parse robustness behavior
- Backend normalizes the model payload (`sections`, `landingPlan.sections`, or plain list).
- Sections are validated one-by-one.
- Invalid sections are skipped and logged; valid sections are still returned.
- Request fails with `PARSE_ERROR` only if no valid sections remain.

---

## Call 1b — Re-parse edited section (optional)

**Triggered by:** "Re-generate" in Screen 3.3 popup
**Visible to user:** Spinner inside popup
**Model:** Provider-switched via `PARSE_LLM_PROVIDER`  
Anthropic path: `claude-haiku-4-5-20251001`  
OpenAI path: `OPENAI_MODEL_PARSE` (default `gpt-4.1-mini`)
**Type:** Single lightweight call

### When it fires

Only when:
1. User opened a section in edit mode (Screen 3.2)
2. Made changes to the textarea content
3. Tapped "Save changes" → dirty check detected a change
4. Confirmed in the Screen 3.3 popup

If content is unchanged, this call is skipped entirely — navigate directly back to Screen 3.1.

### Goal

Parse the free-text textarea back into structured section JSON. Extract labeled fields (`Headline: ...`, `Visual: ...`). Do not invent values for fields not present in the text.

### Input

```json
{
  "sectionId": "hero",
  "sectionType": "hero",
  "rawText": "Headline: 60-second invoices. Zero templates.\nSubheadline: Built for freelancers who bill by the hour.\nVisual: Full-width dark hero, white headline, purple CTA button."
}
```

### Output

Single section object — same schema as one item in Call 1 output.

### Why lightweight parse model

Parsing labeled text into JSON is deterministic and requires minimal creativity. This stage is optimized for low latency and low cost.

### On success
Merge updated section into `landingPlan` in session. Navigate to Screen 3.1.

### On error
Show inline error inside popup. Keep textarea intact so user can retry.

---

## Call 2 — Generate final landing page

**Triggered by:** "Approve & generate page" tap on Screen 3.1
**Visible to user:** Loading transition to Screen 4
**Model:** Claude Sonnet (`claude-sonnet-4-6`, current fixed path)
**Type:** Single call, streaming optional

### Goal

Transform the structured plan into a complete, self-contained HTML/CSS landing page. The output is a full HTML document with inline styles — no external CSS, no JS frameworks. Prioritize copy clarity, CTA strength, and mobile-first layout.

### Input

Full `landingPlan` JSON from session (output of Call 1, with any edits from Call 1b applied).

### Output schema

```json
{
  "html": "<!DOCTYPE html><html lang=\"en\">...</html>"
}
```

The `html` value is a complete standalone document. The frontend renders it via:

```html
<iframe srcdoc={html} sandbox="allow-scripts" />
```

### On success
Store `finalPage` (`{ html: string }`) in session. Render Screen 4.

### On error
Show error state with "Try again" button. Do not navigate away from Screen 3.1.

---

## Full Summary

| Call | Model | Type | Trigger | Optional |
|------|-------|------|---------|----------|
| Call 1 | `PLAN_LLM_PROVIDER` | Single call | "Generate landing plan" tap | No |
| Call 1b | `PARSE_LLM_PROVIDER` | Single call | "Re-generate" in edit popup | Yes |
| Call 2 | Sonnet (Anthropic) | Single call | "Approve & generate page" tap | No |

---

## Model Rationale

| Model | Used for | Reason |
|-------|---------|--------|
| **Plan model (provider-switched)** | Call 1 | Creative + structural task: prompt interpretation, section planning, copy, and visual directions |
| **Parse model (provider-switched)** | Call 1b | Deterministic parsing task: low latency and low cost are prioritized |
| **Sonnet (Anthropic)** | Call 2 | Full-page HTML/CSS generation benefits from stronger long-form synthesis |

---

## v2 Enhancements (out of scope for MVP)

The following were considered and deliberately excluded to keep the pipeline simple:

- **Research Agent** — Sonnet with `web_search` and `fetch_page` tools to enrich the user prompt with market context before Call 1. High quality improvement but adds latency and complexity.
- **Critique cycles** — Generate → Critique (Sonnet) → Refine (Sonnet) pattern for both Call 1 and Call 2. Improves output quality at the cost of 2 additional calls per pipeline stage.
- **Model upgrade** — Replacing Sonnet with Opus for Call 1 and Call 2 when output quality needs to be maximized.

---

## Session State

| Key | Set on | Read on |
|-----|--------|---------|
| `prompt` | Screen 1.1 submit | Screen 1.1 restore ("Edit prompt") |
| `tone` | Screen 1.1 submit | Screen 1.1 restore, Call 1 input |
| `landingPlan` | Call 1 success | Screen 3.1, 3.2, Call 1b merge, Call 2 input |
| `finalPage` | Call 2 success | Screen 4 render (`{ html: string }`) |
