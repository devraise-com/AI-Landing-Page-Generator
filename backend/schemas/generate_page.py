from pydantic import BaseModel

from schemas.generate_plan import Section


class LandingPlan(BaseModel):
    sections: list[Section]


class GeneratePageRequest(BaseModel):
    landingPlan: LandingPlan


class GeneratePageResponse(BaseModel):
    html: str
