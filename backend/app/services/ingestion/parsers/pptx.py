from pathlib import Path
from typing import List, Optional
import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.core.errors import AppError
from app.services.ingestion.parsers.base import ParsedUnit, ParserResult


def parse_pptx(file_path: str) -> ParserResult:
    """Extract slide-by-slide text, tables, and speaker notes from a PowerPoint presentation."""
    path = Path(file_path)
    if not path.is_file():
        raise AppError(f"PPTX file not found at {file_path}", code="file_not_found", status_code=404)

    try:
        prs = pptx.Presentation(str(path))
    except Exception as exc:
        raise AppError(f"Failed to open PowerPoint presentation: {exc}", code="pptx_open_error", status_code=400)

    slide_count = len(prs.slides)
    if slide_count == 0:
        raise AppError("No extractable text found in presentation.", code="no_extractable_text")

    units: List[ParsedUnit] = []
    slides_with_text = 0
    picture_count = 0

    for slide_idx, slide in enumerate(prs.slides):
        slide_num = slide_idx + 1
        slide_parts: List[str] = []
        slide_title: Optional[str] = None
        title_shape_id = None

        # 1. Identify slide title
        if slide.shapes.title and slide.shapes.title.text:
            title_text = slide.shapes.title.text.strip()
            if title_text:
                slide_title = title_text
                title_shape_id = slide.shapes.title.shape_id
                slide_parts.append(title_text)

        # 2. Iterate through shapes in reading order
        for shape in slide.shapes:
            # Count images / pictures
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                picture_count += 1

            # Skip title shape already processed
            if shape.shape_id == title_shape_id:
                continue

            # Process table
            if shape.has_table:
                table_lines: List[str] = []
                for row in shape.table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        table_lines.append(" | ".join(row_cells))
                if table_lines:
                    slide_parts.append("\n".join(table_lines))

            # Process text frame
            elif shape.has_text_frame:
                frame_text = shape.text_frame.text.strip()
                if frame_text:
                    slide_parts.append(frame_text)

        # 3. Speaker notes
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()
            if notes_text:
                slide_parts.append(f"Speaker notes: {notes_text}")

        # Combine text for the slide
        combined_text = "\n\n".join(p for p in slide_parts if p.strip()).strip()

        if combined_text:
            slides_with_text += 1
            units.append(
                ParsedUnit(
                    text=combined_text,
                    source_type="slide",
                    slide_number=slide_num,
                    section_title=slide_title,
                )
            )

    if slides_with_text == 0 or not units:
        raise AppError("No extractable text found in presentation.", code="no_extractable_text")

    meta = {
        "slide_count": slide_count,
        "slides_with_text": slides_with_text,
        "picture_count": picture_count,
    }

    return ParserResult(units=units, meta=meta, num_units=slide_count)
