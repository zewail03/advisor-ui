from typing import Optional

from pydantic import BaseModel, Field


class EvaluationSubmit(BaseModel):
    enrollment_id: str
    rating_content: int = Field(ge=1, le=5)
    rating_teaching: int = Field(ge=1, le=5)
    rating_materials: int = Field(ge=1, le=5)
    rating_assessment: int = Field(ge=1, le=5)
    rating_engagement: int = Field(ge=1, le=5)
    rating_overall: int = Field(ge=1, le=5)
    best_aspect: Optional[str] = None
    improvement_note: Optional[str] = None
    anonymous: bool = True
