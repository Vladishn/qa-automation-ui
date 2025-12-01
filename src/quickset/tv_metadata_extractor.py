from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

TV_BRAND_ALLOWLIST = {
    "lg",
    "samsung",
    "sony",
    "philips",
    "hisense",
    "tcl",
    "panasonic",
    "sharp",
    "toshiba",
    "vizio",
}

BRAND_PATTERNS = [
    r'tvBrandName=([A-Za-z0-9 _\-]+)',
    r'"brands":\["([^"]+)"\]',
    r'"brand":"([^"]+)"',
]

MODEL_PATTERNS = [
    r'tvModelName=([A-Za-z0-9 _\-]+)',
    r'"models":\["([^"]+)"\]',
    r'"model":"([^"]+)"',
]

INVALID_SUBSTRINGS = {"partnertv", "partnerrc", "stb", "box", "quickset"}


def _looks_like_tv_brand(value: str) -> bool:
    lower = value.lower()
    if any(token in lower for token in INVALID_SUBSTRINGS):
        return False
    if TV_BRAND_ALLOWLIST and lower not in TV_BRAND_ALLOWLIST:
        return False
    return True


def _search_first(text: str, patterns: list[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def extract_tv_metadata_from_log(log_path: Path) -> Dict[str, Optional[str]]:
    """Parse log text and return detected brand/model information."""
    if not log_path.exists():
        return {"tv_brand_logs": None, "tv_model_logs": None}

    text = log_path.read_text(encoding="utf-8", errors="ignore")
    brand = _search_first(text, BRAND_PATTERNS)
    if brand and not _looks_like_tv_brand(brand):
        brand = None

    model = _search_first(text, MODEL_PATTERNS)
    if model and any(token in model.lower() for token in INVALID_SUBSTRINGS):
        model = None

    return {
        "tv_brand_logs": brand,
        "tv_model_logs": model,
    }
