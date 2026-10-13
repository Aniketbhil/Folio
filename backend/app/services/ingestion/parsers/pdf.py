from collections import Counter
from pathlib import Path
import re
from typing import List, Optional
import pymupdf

from app.core.errors import AppError
from app.services.ingestion.parsers.base import ParsedUnit, ParserResult


def _clean_page_text(text: str) -> str:
    """Normalize whitespace and reconnect hyphenated linebreaks."""
    # Reconnect words split across lines with hyphen
    text = re.sub(r"(\b\w+)-\s*\n\s*(\w+\b)", r"\1\2", text)
    # Normalize excessive carriage returns and horizontal whitespace
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def parse_pdf(file_path: str) -> ParserResult:
    """Extract page-by-page text from a PDF with TOC section tracking and header/footer stripping."""
    path = Path(file_path)
    if not path.is_file():
        raise AppError(f"PDF file not found at {file_path}", code="file_not_found", status_code=404)

    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:
        raise AppError(f"Failed to open PDF document: {exc}", code="pdf_open_error", status_code=400)

    try:
        page_count = len(doc)
        if page_count == 0:
            raise AppError(
                "No extractable text found. This looks like a scanned PDF; OCR is not supported yet.",
                code="no_extractable_text",
            )

        # 1. Parse Table of Contents for section titles
        toc = doc.get_toc()  # [[lvl, title, page_1based], ...]
        toc_entries = []
        if toc:
            for item in toc:
                if len(item) >= 3 and isinstance(item[2], int):
                    toc_entries.append((item[2], str(item[1]).strip()))
            toc_entries.sort(key=lambda x: x[0])

        def get_section_title(page_num: int) -> Optional[str]:
            current_title = None
            for entry_page, title in toc_entries:
                if entry_page <= page_num:
                    current_title = title
                else:
                    break
            return current_title

        # 2. Extract raw text and image counts per page
        raw_pages: List[dict] = []
        total_images = 0

        for page_idx in range(page_count):
            page = doc[page_idx]
            page_num = page_idx + 1
            images = page.get_images()
            total_images += len(images)
            text = page.get_text("text")
            cleaned = _clean_page_text(text)
            lines = [l for l in cleaned.split("\n") if l.strip()]

            raw_pages.append({
                "page_num": page_num,
                "lines": lines,
                "section_title": get_section_title(page_num),
            })

        # 3. Detect repeated headers / footers on documents with at least 3 pages
        header_candidates = Counter()
        footer_candidates = Counter()
        if page_count >= 3:
            for p in raw_pages:
                if p["lines"]:
                    header_candidates[p["lines"][0]] += 1
                    footer_candidates[p["lines"][-1]] += 1

            majority_threshold = page_count * 0.5
            repeated_headers = {
                line for line, cnt in header_candidates.items() if cnt >= majority_threshold and cnt > 1
            }
            repeated_footers = {
                line for line, cnt in footer_candidates.items() if cnt >= majority_threshold and cnt > 1
            }
        else:
            repeated_headers = set()
            repeated_footers = set()

        # 4. Construct parsed units
        units: List[ParsedUnit] = []
        pages_with_text = 0

        for p in raw_pages:
            filtered_lines = p["lines"]
            if filtered_lines and filtered_lines[0] in repeated_headers:
                filtered_lines = filtered_lines[1:]
            if filtered_lines and filtered_lines[-1] in repeated_footers:
                filtered_lines = filtered_lines[:-1]

            final_text = "\n".join(filtered_lines).strip()
            if final_text:
                pages_with_text += 1
                units.append(
                    ParsedUnit(
                        text=final_text,
                        source_type="pdf",
                        page_number=p["page_num"],
                        section_title=p["section_title"],
                    )
                )

        if pages_with_text == 0 or not units:
            raise AppError(
                "No extractable text found. This looks like a scanned PDF; OCR is not supported yet.",
                code="no_extractable_text",
            )

        meta = {
            "page_count": page_count,
            "pages_with_text": pages_with_text,
            "image_count": total_images,
        }

        return ParserResult(units=units, meta=meta, num_units=page_count)
    finally:
        doc.close()
