"""Timeline endpoints for QuickSet sessions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from ..config import settings
from ...quickset_timeline_analyzer import build_timeline_and_summary

router = APIRouter(prefix="/sessions", tags=["timeline"])
logger = logging.getLogger(__name__)

ARTIFACTS_ROOT = Path(settings.quickset_steps_dir)


def _load_session_events(session_id: str) -> Optional[List[Dict[str, Any]]]:
    logger.debug(
        "[timeline] load_session_events: session_id=%s, root=%s",
        session_id,
        ARTIFACTS_ROOT.resolve(),
    )

    direct_file = ARTIFACTS_ROOT / f"{session_id}.jsonl"
    logger.debug("[timeline] trying direct file: %s", direct_file)

    log_file: Path | None = None
    if direct_file.exists() and direct_file.is_file():
        log_file = direct_file
    else:
        logger.debug("[timeline] direct file missing for %s", session_id)
        matches = list(ARTIFACTS_ROOT.glob(f"{session_id}*.jsonl"))
        logger.debug(
            "[timeline] glob matches for %s: %s",
            session_id,
            [p.name for p in matches],
        )
        if matches:
            matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            log_file = matches[0]

    if log_file is None:
        logger.warning(
            "[timeline] no session file found for %s in %s",
            session_id,
            ARTIFACTS_ROOT,
        )
        return None

    logger.debug("[timeline] using log_file=%s", log_file)

    events: List[Dict[str, Any]] = []
    with log_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

    if not events:
        logger.warning("[timeline] session file is empty: %s", log_file)
        return []

    return events


@router.get("/{session_id}")
def get_session_timeline(session_id: str) -> Dict[str, Any]:
    events = _load_session_events(session_id)

    if events is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Session file not found under {ARTIFACTS_ROOT} for id {session_id}"
            ),
        )
    if len(events) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No events in session file",
        )

    scenario_name = "UNKNOWN"
    if events:
        first = events[0]
        scenario_name = (
            first.get("scenario_name")
            or (first.get("details") or {}).get("scenario_name")
            or "UNKNOWN"
        )

    payload = build_timeline_and_summary(
        session_id=session_id,
        scenario_name=scenario_name,
        raw_events=events,
    )
    return payload
