from typing import Literal

from pydantic import BaseModel

Tone = Literal["professional", "friendly", "bold", "minimal"]


class GeneratePlanRequest(BaseModel):
    prompt: str
    tone: Tone


class Section(BaseModel):
    id: str
    name: str
    type: str
    fields: dict
    visual_direction: str


class GeneratePlanResponse(BaseModel):
    sections: list[Section]
