"""Timeline endpoints for QuickSet sessions."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from ..quickset_timeline_analyzer import build_timeline_and_summary
from ..timeline_loader import ARTIFACTS_ROOT, load_session_events

router = APIRouter(prefix="/sessions", tags=["timeline"])
logger = logging.getLogger(__name__)


@router.get("/{session_id}")
def get_session_timeline(session_id: str) -> Dict[str, Any]:
    events = load_session_events(session_id)

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
