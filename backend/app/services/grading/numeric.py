"""Numerical parsing and evaluation for quantitative assessment questions."""

import math
import re
from typing import Optional, Tuple


def parse_number(text: str) -> Optional[float]:
    """Extract and parse a numerical value from student input.

    Handles:
    - European decimal commas ("9,8" -> 9.8) vs thousands commas ("1,000.5" -> 1000.5)
    - Scientific notation ("3e8", "3E8", "-2.5e-3")
    - Power of ten notation ("3 x 10^8", "3 × 10^8", "3 * 10^8")
    - Fractions ("1/2" -> 0.5, "-3/4" -> -0.75)
    - Trailing units ("9.8 m/s^2" -> 9.8)
    - Percentages ("50%" -> 50.0)
    - Leading/trailing whitespace and negative signs ("- 9.8" -> -9.8)

    Returns None if no valid number can be parsed.
    """
    if not text or not isinstance(text, str):
        return None

    clean = text.strip()
    if not clean:
        return None

    # 1. Normalize spaces around minus sign
    clean = re.sub(r"^\s*-\s+", "-", clean)
    clean = re.sub(r"^\s*\+\s+", "+", clean)

    # 2. Check for power-of-10 notation: e.g. "3 x 10^8", "3 × 10^8", "3 * 10^8", "-1.5 x 10^-4"
    pow10_match = re.search(
        r"^\s*([-+]?(?:\d+(?:[\.,]\d+)?|\.\d+))\s*(?:[xX*×]|\b(?:times)\b)\s*10\s*(?:\^|\*\*)\s*([-+]?\d+)",
        clean,
    )
    if pow10_match:
        try:
            coeff_str = pow10_match.group(1).replace(",", ".")
            coeff = float(coeff_str)
            exp = int(pow10_match.group(2))
            val = coeff * (10.0 ** exp)
            if math.isfinite(val):
                return val
        except (ValueError, OverflowError):
            pass

    # 3. Check for simple fraction: e.g. "1/2", "-3/4", "5 / 2"
    frac_match = re.search(r"^\s*([-+]?\d+)\s*/\s*([-+]?\d+)\s*(?:[a-zA-Z/%\^].*)?$", clean)
    if frac_match:
        try:
            num = int(frac_match.group(1))
            denom = int(frac_match.group(2))
            if denom != 0:
                val = num / denom
                if math.isfinite(val):
                    return val
        except (ValueError, ZeroDivisionError):
            pass

    # 4. Handle European comma vs thousands comma
    # If the string contains a single comma surrounded by digits and no dot (e.g. "9,8" or "9,8 m/s^2"),
    # interpret as decimal comma.
    comma_count = clean.count(",")
    dot_count = clean.count(".")
    if comma_count == 1 and dot_count == 0:
        # Check if comma looks like a decimal separator (e.g. 1-3 digits after comma or followed by unit)
        if re.search(r"\d+,\d+", clean):
            clean = clean.replace(",", ".")
    elif comma_count > 0:
        # Multiple commas or commas with dot: remove commas as thousands separators (e.g. 1,000,000.5)
        clean = clean.replace(",", "")

    # 5. Remove trailing percent sign if present
    clean = re.sub(r"%\s*(?:[a-zA-Z].*)?$", "", clean).strip()

    # 6. Extract leading float with optional scientific notation (e.g. "9.8 m/s^2" -> "9.8", "-3e8 m/s" -> "-3e8")
    float_match = re.search(r"^([-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?)", clean)
    if float_match:
        try:
            val = float(float_match.group(1))
            if math.isfinite(val):
                return val
        except ValueError:
            pass

    return None


def grade_numeric(
    answer: str,
    expected_value: float,
    tolerance_pct: float = 1.0,
) -> Tuple[float, Optional[float]]:
    """Evaluate a student's numerical answer against an expected value.

    Args:
        answer: Student's raw answer string
        expected_value: Ground truth number
        tolerance_pct: Percentage tolerance (default 1.0%)

    Returns:
        (score, parsed_value) where score is 1.0 or 0.0, and parsed_value is the parsed float.
    """
    parsed = parse_number(answer)
    if parsed is None:
        return 0.0, None

    if abs(expected_value) < 1e-9:
        # Expected value is 0: use small absolute tolerance
        tol = 1e-9
    else:
        tol = abs(expected_value) * (tolerance_pct / 100.0)

    is_correct = abs(parsed - expected_value) <= (tol + 1e-12)
    return (1.0 if is_correct else 0.0), parsed
