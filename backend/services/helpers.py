import json
import os
import re
import uuid

from fastapi.responses import JSONResponse

_DEFAULT_LOG_PREVIEW_CHARS = 200


def _get_log_preview_chars() -> int:
    raw = os.getenv("LOG_TEXT_PREVIEW_CHARS", str(_DEFAULT_LOG_PREVIEW_CHARS))
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_LOG_PREVIEW_CHARS
    return max(0, value)


def text_preview(text: str) -> str:
    """Return a log-safe preview truncated to LOG_TEXT_PREVIEW_CHARS."""
    return text[:_get_log_preview_chars()]


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping optional markdown code fences."""
    text = text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extract the first top-level JSON value from mixed text.
        json_text = _extract_first_json_value(text)
        if not json_text:
            raise
        return json.loads(json_text)


def _extract_first_json_value(text: str) -> str | None:
    start = -1
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start == -1:
        return None

    in_string = False
    escape = False
    stack: list[str] = []

    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            stack.append("}")
            continue
        if ch == "[":
            stack.append("]")
            continue
        if ch in "}]":
            if not stack or stack[-1] != ch:
                return None
            stack.pop()
            if not stack:
                return text[start:i + 1]
    return None


def normalize_generate_plan_payload(payload: object) -> dict:
    sections_raw: object

    if isinstance(payload, list):
        sections_raw = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("sections"), list):
            sections_raw = payload["sections"]
        elif isinstance(payload.get("landingPlan"), dict) and isinstance(payload["landingPlan"].get("sections"), list):
            sections_raw = payload["landingPlan"]["sections"]
        elif isinstance(payload.get("plan"), dict) and isinstance(payload["plan"].get("sections"), list):
            sections_raw = payload["plan"]["sections"]
        else:
            sections_raw = [payload]
    else:
        sections_raw = []

    sections: list[dict] = []
    if isinstance(sections_raw, list):
        for idx, item in enumerate(sections_raw, start=1):
            section = normalize_section_payload(item, section_id_hint=f"section-{idx}")
            sections.append(section)

    return {"sections": sections}


def normalize_section_payload(
    payload: object,
    section_id_hint: str | None = None,
    section_type_hint: str | None = None,
) -> dict:
    if isinstance(payload, dict) and isinstance(payload.get("section"), dict):
        payload = payload["section"]

    data = payload if isinstance(payload, dict) else {}

    section_type_raw = data.get("type") or section_type_hint or "section"
    section_type = _slugify(str(section_type_raw), fallback="section")

    section_id_raw = data.get("id") or section_id_hint or section_type
    section_id = _slugify(str(section_id_raw), fallback="section")

    section_name_raw = data.get("name")
    section_name = str(section_name_raw).strip() if section_name_raw else _humanize_type(section_type)

    visual_raw = data.get("visual_direction")
    if visual_raw is None:
        visual_raw = data.get("visualDirection")
    visual_direction = str(visual_raw or "")

    fields = data.get("fields")
    if isinstance(fields, dict):
        normalized_fields = fields
    elif isinstance(fields, list):
        normalized_fields = {"items": fields}
    elif fields is None:
        normalized_fields = {}
    else:
        normalized_fields = {"value": fields}

    if not normalized_fields:
        ignored = {"id", "name", "type", "fields", "visual_direction", "visualDirection"}
        extras = {k: v for k, v in data.items() if k not in ignored}
        if extras:
            normalized_fields = extras

    return {
        "id": section_id,
        "name": section_name,
        "type": section_type,
        "fields": normalized_fields,
        "visual_direction": visual_direction,
    }


def _slugify(value: str, fallback: str) -> str:
    s = value.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or fallback


def _humanize_type(section_type: str) -> str:
    return section_type.replace("-", " ").title()


def error_json(
    error: str,
    code: str,
    status: int,
    request_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": error,
            "code": code,
            "request_id": request_id or str(uuid.uuid4()),
        },
    )
