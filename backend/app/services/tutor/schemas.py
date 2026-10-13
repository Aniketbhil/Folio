from typing import List, Optional
from pydantic import BaseModel, Field


class TutorLLMOutput(BaseModel):
    """Structured response schema expected from the tutor answer LLM call."""

    grounding: str = Field(
        ...,
        description="'grounded' | 'partial' | 'unsupported'",
    )
    answer: str = Field(
        ...,
        description="Markdown-formatted answer with inline [n] citation markers.",
    )
    used_sources: List[int] = Field(
        default_factory=list,
        description="1-based indices of sources directly cited in the answer.",
    )
    outside_knowledge_note: Optional[str] = Field(
        default=None,
        description="One sentence summary of content derived outside the material, or null.",
    )
    followups: List[str] = Field(
        default_factory=list,
        description="2-3 short suggested next questions answerable by course material.",
    )
