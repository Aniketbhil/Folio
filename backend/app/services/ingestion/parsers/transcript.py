import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from app.core.errors import AppError
from app.services.ingestion.parsers.base import ParsedUnit, ParserResult


def _parse_timestamp(ts: str) -> float:
    """Parse timestamp string (hh:mm:ss.sss or mm:ss.sss) into total seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600.0 + float(m) * 60.0 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return float(m) * 60.0 + float(s)
        elif len(parts) == 1:
            return float(parts[0])
    except ValueError:
        pass
    return 0.0


def _clean_text(raw_text: str) -> str:
    """Strip markup tags, annotations, and extraneous spaces."""
    cleaned = re.sub(r"<[^>]+>", "", raw_text)
    cleaned = re.sub(r"\[[0-9a-zA-Z_:.]+\]", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def _estimate_tokens(text: str) -> int:
    """Heuristic token estimation: ceil(words * 1.3)."""
    words = len(text.split())
    return math.ceil(words * 1.3)


def _deduplicate_cues(cues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate consecutive repeated cues (common in YouTube auto-captions)."""
    deduped: List[Dict[str, Any]] = []
    last_text = ""

    for cue in cues:
        text = cue["text"].strip()
        if not text:
            continue

        # If identical to previous cue text, skip
        if text == last_text:
            continue

        # If rolling duplicate: cue starts with previous cue text followed by new content
        if last_text and text.startswith(last_text + " "):
            text = text[len(last_text) + 1 :].strip()

        if text:
            deduped.append({
                "start": cue["start"],
                "end": cue["end"],
                "text": text,
            })
            last_text = cue["text"].strip()

    return deduped


def _window_cues(
    cues: List[Dict[str, Any]],
    window_sec: float = 60.0,
    max_tokens: int = 400,
) -> List[ParsedUnit]:
    """Group cues into windows of ~window_sec (capped by max_tokens) with 1-cue overlap."""
    if not cues:
        return []

    window_sec = float(window_sec)
    max_tokens = int(max_tokens)
    units: List[ParsedUnit] = []
    idx = 0
    total = len(cues)

    while idx < total:
        window_start = cues[idx]["start"]
        current_texts = [cues[idx]["text"]]
        window_end = cues[idx]["end"]
        last_idx = idx

        next_idx = idx + 1
        while next_idx < total:
            next_cue = cues[next_idx]
            proposed_text = " ".join(current_texts + [next_cue["text"]])
            proposed_duration = next_cue["end"] - window_start

            # Check window duration and token cap
            if proposed_duration > window_sec or _estimate_tokens(proposed_text) > max_tokens:
                break

            current_texts.append(next_cue["text"])
            window_end = next_cue["end"]
            last_idx = next_idx
            next_idx += 1

        combined_text = " ".join(current_texts).strip()
        if combined_text:
            units.append(
                ParsedUnit(
                    text=combined_text,
                    source_type="video",
                    start_sec=round(window_start, 2),
                    end_sec=round(window_end, 2),
                )
            )

        # Overlap: start next window from last cue of current window, or advance if single cue
        if last_idx > idx:
            idx = last_idx
        else:
            idx += 1

    return units


def _parse_vtt(content: str) -> List[Dict[str, Any]]:
    """Parse WebVTT formatted cues."""
    lines = content.splitlines()
    cues: List[Dict[str, Any]] = []

    # Regex for VTT timestamp arrow
    ts_pattern = re.compile(
        r"((?:\d{1,2}:)?\d{2}:\d{2}(?:[.,]\d+)?)\s*-->\s*((?:\d{1,2}:)?\d{2}:\d{2}(?:[.,]\d+)?)"
    )

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Skip header or notes
        if line.startswith("WEBVTT") or line.startswith("NOTE"):
            i += 1
            continue

        match = ts_pattern.search(line)
        if match:
            start = _parse_timestamp(match.group(1))
            end = _parse_timestamp(match.group(2))
            cue_text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                clean_l = _clean_text(lines[i])
                if clean_l:
                    cue_text_lines.append(clean_l)
                i += 1

            text = " ".join(cue_text_lines).strip()
            if text:
                cues.append({"start": start, "end": end, "text": text})
        else:
            i += 1

    return cues


def _parse_srt(content: str) -> List[Dict[str, Any]]:
    """Parse SubRip (SRT) formatted cues."""
    lines = content.splitlines()
    cues: List[Dict[str, Any]] = []

    ts_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s*-->\s*(\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)"
    )

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = ts_pattern.search(line)
        if match:
            start = _parse_timestamp(match.group(1))
            end = _parse_timestamp(match.group(2))
            cue_text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                clean_l = _clean_text(lines[i])
                if clean_l:
                    cue_text_lines.append(clean_l)
                i += 1

            text = " ".join(cue_text_lines).strip()
            if text:
                cues.append({"start": start, "end": end, "text": text})
        else:
            i += 1

    return cues


def _parse_json_transcript(content: str) -> List[Dict[str, Any]]:
    """Parse JSON transcript structures."""
    try:
        data = json.loads(content)
    except Exception as exc:
        raise AppError(
            f"Invalid JSON transcript: {exc}",
            code="invalid_transcript_format",
            status_code=400,
        )

    # Whisper shape: {"segments": [...]}
    if isinstance(data, dict) and "segments" in data and isinstance(data["segments"], list):
        items = data["segments"]
    elif isinstance(data, list):
        items = data
    else:
        raise AppError(
            "Invalid transcript JSON format. Expected list of cues or {'segments': [...]}.",
            code="invalid_transcript_format",
            status_code=400,
        )

    cues: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or "text" not in item:
            continue

        raw_text = _clean_text(str(item["text"]))
        if not raw_text:
            continue

        start = float(item.get("start", 0.0))
        if "end" in item:
            end = float(item["end"])
        elif "duration" in item:
            end = start + float(item["duration"])
        else:
            end = start + 3.0

        cues.append({"start": start, "end": end, "text": raw_text})

    if not cues:
        raise AppError(
            "No valid cues found in JSON transcript.",
            code="invalid_transcript_format",
            status_code=400,
        )

    return cues


def _parse_txt(content: str) -> tuple[List[Dict[str, Any]], bool, List[str]]:
    """Parse plain text or timestamped text lines."""
    lines = content.splitlines()
    ts_line_pattern = re.compile(
        r"^(?:\[)?((?:\d{1,2}:)?\d{2}:\d{2}(?:[.,]\d+)?)(?:\])?\s+(.+)$"
    )

    cues: List[Dict[str, Any]] = []
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        m = ts_line_pattern.match(line_str)
        if m:
            start_sec = _parse_timestamp(m.group(1))
            text = _clean_text(m.group(2))
            if text:
                cues.append({"start": start_sec, "end": start_sec + 5.0, "text": text})

    if cues:
        # Adjust end timestamps so each cue ends at next cue start
        for i in range(len(cues) - 1):
            if cues[i]["end"] <= cues[i]["start"] or cues[i]["end"] > cues[i + 1]["start"]:
                cues[i]["end"] = cues[i + 1]["start"]
        return cues, True, []

    # If no timestamps matched, split into paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    return [], False, paragraphs


def parse_transcript(
    file_path: str,
    window_sec: float = 60.0,
    chunk_target_tokens: int = 400,
) -> ParserResult:
    """Parse transcript from .vtt, .srt, .json, or .txt file into timed or paragraph units."""
    path = Path(file_path)
    if not path.is_file():
        raise AppError(f"Transcript file not found: {file_path}", code="file_not_found", status_code=404)

    suffix = path.suffix.lower()
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise AppError(f"Failed to read transcript file: {exc}", code="file_read_error", status_code=400)

    cues: List[Dict[str, Any]] = []
    has_timestamps = True
    paragraphs: List[str] = []
    warning = None

    if suffix == ".vtt":
        cues = _parse_vtt(content)
    elif suffix == ".srt":
        cues = _parse_srt(content)
    elif suffix == ".json":
        cues = _parse_json_transcript(content)
    elif suffix == ".txt":
        cues, has_timestamps, paragraphs = _parse_txt(content)
        if not has_timestamps:
            warning = "No timestamps found; citations cannot seek to a time."
    else:
        raise AppError(
            f"Unsupported transcript extension '{suffix}'. Expected .vtt, .srt, .json, or .txt",
            code="unsupported_file_type",
            status_code=415,
        )

    if has_timestamps:
        cues = _deduplicate_cues(cues)
        if not cues:
            raise AppError("No extractable cues found in transcript.", code="no_extractable_text")

        units = _window_cues(cues, window_sec=window_sec, max_tokens=chunk_target_tokens)
        cue_count = len(cues)
        duration_sec = cues[-1]["end"] if cues else 0.0

        meta: Dict[str, Any] = {
            "duration_sec": round(duration_sec, 2),
            "cue_count": cue_count,
            "has_timestamps": True,
        }
        return ParserResult(units=units, meta=meta, num_units=cue_count)
    else:
        # Untimed text: emit paragraph units
        if not paragraphs:
            raise AppError("No extractable text found in file.", code="no_extractable_text")

        units = [
            ParsedUnit(
                text=p,
                source_type="video",
                start_sec=None,
                end_sec=None,
            )
            for p in paragraphs
        ]

        meta = {
            "duration_sec": 0.0,
            "cue_count": len(paragraphs),
            "has_timestamps": False,
            "warning": warning,
        }
        return ParserResult(units=units, meta=meta, num_units=len(paragraphs))
