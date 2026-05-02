import os
import re

# Red-flag patterns: malicious or policy-violating intent
_RED_FLAG_PATTERNS = [
    r"(?:drop\s+table|select\s+\*\s+from|insert\s+into|union\s+select)",          # SQLi
    r"(?:ignore\s+(?:previous|prior|above)\s+instructions|forget\s+everything)",   # prompt injection
    r"(?:reveal|show|print|output)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)",  # prompt leak
    r"(?:malware|ransomware|shellcode|rootkit|keylogger|exploit\s+code)",           # malware
    r"(?:\brm\s+-rf\b|exec\s*\(|eval\s*\(|os\.system\s*\(|subprocess\.(?:call|run|Popen))",  # code exec
]

# Off-topic patterns: clearly not a product/service description
_OFF_TOPIC_PATTERNS = [
    r"\bdebug\b.{0,40}\b(?:code|bug|error)\b",
    r"\b(?:write|generate)\b.{0,20}\b(?:python|javascript|typescript|java|bash)\b.{0,20}\b(?:code|script|function|class|program)\b",
    r"\bsolve\b.{0,20}\b(?:equation|math\s+problem)\b",
    r"\b(?:translate|summarize)\b.{0,20}\b(?:text|document|article|passage)\b",
]

_RED_FLAG_RE = [re.compile(p, re.IGNORECASE) for p in _RED_FLAG_PATTERNS]
_OFF_TOPIC_RE = [re.compile(p, re.IGNORECASE) for p in _OFF_TOPIC_PATTERNS]


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _input_prompt_max_chars() -> int:
    # Backward-compatible fallback to PROMPT_MAX_CHARS.
    legacy = _get_int_env("PROMPT_MAX_CHARS", 2000)
    return _get_int_env("INPUT_PROMPT_MAX_CHARS", legacy)


def _extract_strings(obj: object, depth: int = 0) -> list[str]:
    """Recursively extract all string values from a nested dict/list."""
    if depth > 10:
        return []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _extract_strings(v, depth + 1)]
    if isinstance(obj, list):
        return [s for item in obj for s in _extract_strings(item, depth + 1)]
    return []


def validate_landing_plan(plan: dict) -> tuple[bool, str]:
    """Size + red-flag + topic-gating check on all text fields of a landingPlan.
    Uses a 5x size limit since a plan is inherently larger than a single prompt."""
    max_chars = _get_int_env("LANDING_PLAN_MAX_CHARS", _input_prompt_max_chars() * 5)
    texts = _extract_strings(plan)
    combined = " ".join(texts)

    if len(combined) > max_chars:
        return False, "Plan content exceeds the allowed size limit."

    for pattern in _RED_FLAG_RE:
        if pattern.search(combined):
            return False, "Plan contains disallowed content and cannot be processed."

    for pattern in _OFF_TOPIC_RE:
        if pattern.search(combined):
            return False, "Only landing page generation requests are accepted."

    return True, ""


def validate_prompt(text: str) -> tuple[bool, str]:
    """Check user-provided text before passing to LLM.
    Returns (True, "") on pass, or (False, error_message) on fail."""
    max_chars = _input_prompt_max_chars()
    if len(text) > max_chars:
        return False, f"Prompt exceeds the {max_chars}-character limit."

    for pattern in _RED_FLAG_RE:
        if pattern.search(text):
            return False, "Request contains disallowed content and cannot be processed."

    for pattern in _OFF_TOPIC_RE:
        if pattern.search(text):
            return False, "Only landing page generation requests are accepted."

    return True, ""
