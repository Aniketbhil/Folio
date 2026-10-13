"""Testset schema definitions for Folio evaluation."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TestsetItem(BaseModel):
    """Single test evaluation item."""

    id: str = Field(..., description="Unique test item identifier")
    question: str = Field(..., description="Student query or question prompt")
    ground_truth_answer: str = Field(..., description="Expected canonical answer")
    expected_chunk_ids: List[int] = Field(default_factory=list, description="IDs of ground-truth chunks")
    expected_key_phrases: List[str] = Field(default_factory=list, description="Key phrases expected in retrieved text")
    expected_topic: str = Field(..., description="Expected course topic")
    question_type: str = Field(
        ...,
        description="Type: factual | conceptual | adversarial_out_of_scope | adversarial_unsupported",
    )
    expected_refusal: bool = Field(
        default=False,
        description="Whether tutor should refuse to answer",
    )


class Testset(BaseModel):
    """Collection of test items."""

    items: List[TestsetItem] = Field(default_factory=list)

    @classmethod
    def load_from_file(cls, path: str | Path) -> "Testset":
        p = Path(path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return cls(items=[TestsetItem(**item) for item in data])
        elif isinstance(data, dict) and "items" in data:
            return cls(**data)
        raise ValueError(f"Invalid testset format in {path}")

    def save_to_file(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2)
