from pydantic import BaseModel


class ParseSectionRequest(BaseModel):
    sectionId: str
    rawText: str
    sectionType: str

# Output: Section — imported from schemas.generate_plan
