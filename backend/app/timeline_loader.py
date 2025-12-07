"""Helpers for loading QuickSet session timeline events from disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings

ARTIFACTS_ROOT = Path(settings.quickset_steps_dir)


def load_session_events(session_id: str) -> Optional[List[Dict[str, Any]]]:
    """Return the raw timeline events for a session, or None if no file was found."""
    direct_file = ARTIFACTS_ROOT / f"{session_id}.jsonl"
    log_file: Path | None = None

    if direct_file.exists() and direct_file.is_file():
        log_file = direct_file
    else:
        matches = list(ARTIFACTS_ROOT.glob(f"{session_id}*.jsonl"))
        if matches:
            matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            log_file = matches[0]

    if log_file is None:
        return None

    events: List[Dict[str, Any]] = []
    with log_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            events.append(json.loads(line))

    return events
