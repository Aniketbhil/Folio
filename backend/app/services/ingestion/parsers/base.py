from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedUnit:
    """Represents an atomic extracted unit (page, slide, or transcript window)

    prior to database chunking.
    """

    text: str
    source_type: str  # "pdf" | "slide" | "video"
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    section_title: Optional[str] = None


@dataclass
class ParserResult:
    """Aggregated output from a document parser."""

    units: List[ParsedUnit] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    num_units: int = 0
