from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load a prompt file by name from backend/prompts/. Cached after first read."""
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")
