from __future__ import annotations

import re
import unicodedata
from datetime import datetime, time, timedelta


_DASHES = "-–—−"
_MULTI_DASH_PATTERN = re.compile(r"(?:^|\s)[-–—−]\s*")
_SPLIT_PATTERN = re.compile(r"\s+[-–—−]\s+|\s*/\s*|\s*,\s*|\s*;\s*|\n+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_TIMECODE_PATTERN = re.compile(
    r"^\s*(\d{1,2}):(\d{2}):(\d{2})(?:[,.](\d{1,3}))?\s*$"
)


def clean_text(value: object) -> str:
    """Clean a cell while preserving meaningful dialogue line breaks."""
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

    while lines and not lines[0]:
        lines.pop(0)

    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)


def normalize_key(value: object) -> str:
    """Case-insensitive normalized key for character/talent lookups."""
    text = clean_text(value).strip()
    text = re.sub(rf"^[{re.escape(_DASHES)}•·]+\s*", "", text)
    text = text.translate(str.maketrans({dash: "-" for dash in _DASHES}))
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text.casefold()


def normalize_dialogue_key(value: object) -> str:
    """Stable text representation used in dialog_uid fingerprints."""
    return _WHITESPACE_PATTERN.sub(" ", clean_text(value)).strip().casefold()


def clean_name(value: object) -> str:
    text = clean_text(value).strip()
    text = re.sub(rf"^[{re.escape(_DASHES)}•·]+\s*", "", text)
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def split_cast_value(value: object) -> list[str]:
    """
    Split a character/talent cell conservatively.

    Handles variants such as:
    - ``Hendra - Joko``
    - ``-Indah -Teguh``
    - ``Hendra / Joko``
    - line-separated names

    A single leading dash is treated as decoration, not a separator.
    """
    text = clean_text(value)

    if not text:
        return []

    dash_markers = list(_MULTI_DASH_PATTERN.finditer(text))

    if text.lstrip()[:1] in _DASHES and len(dash_markers) >= 2:
        parts = [part for part in _MULTI_DASH_PATTERN.split(text) if part.strip()]
    else:
        parts = _SPLIT_PATTERN.split(text)

    cleaned: list[str] = []
    seen: set[str] = set()

    for part in parts:
        name = clean_name(part)
        key = normalize_key(name)

        if not key or key in seen:
            continue

        cleaned.append(name)
        seen.add(key)

    return cleaned


def normalize_timecode(value: object) -> str:
    if value is None or value == "":
        return ""

    if isinstance(value, datetime):
        value = value.time()

    if isinstance(value, time):
        milliseconds = value.microsecond // 1000
        return (
            f"{value.hour:02d}:{value.minute:02d}:{value.second:02d},"
            f"{milliseconds:03d}"
        )

    if isinstance(value, timedelta):
        total_ms = max(0, round(value.total_seconds() * 1000))
        return _milliseconds_to_timecode(total_ms)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)

        # Excel usually stores clock time as a fraction of a day.
        if 0 <= number < 1:
            return _milliseconds_to_timecode(round(number * 86_400_000))

        return clean_text(value)

    text = clean_text(value)
    match = _TIMECODE_PATTERN.match(text)

    if not match:
        return text

    hour, minute, second, fraction = match.groups()
    milliseconds = int((fraction or "0").ljust(3, "0")[:3])

    return f"{int(hour):02d}:{int(minute):02d}:{int(second):02d},{milliseconds:03d}"


def looks_like_timecode(value: object) -> bool:
    if value in (None, ""):
        return False

    if isinstance(value, (datetime, time, timedelta)):
        return True

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return 0 <= float(value) < 1

    return bool(_TIMECODE_PATTERN.match(clean_text(value)))


def _milliseconds_to_timecode(total_ms: int) -> str:
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
