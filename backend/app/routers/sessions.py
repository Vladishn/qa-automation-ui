"""Session lifecycle endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from ..regression_snapshots import save_session_snapshot
from ..models import SessionModel
from ..schemas import Session, SessionCreateRequest
from ..storage import storage

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/", response_model=Session, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreateRequest) -> Session:
    now = datetime.utcnow()
    session = SessionModel(
        id=str(uuid4()),
        domain=payload.domain,
        platform_id=payload.platform_id,
        version_id=payload.version_id,
        tester_id=payload.tester_id,
        status="NOT_STARTED",
        created_at=now,
        updated_at=now,
        scenarios=payload.scenarios or [],
        comment=payload.comment,
    )
    storage.add_session(session)
    return _map_session(session)


@router.get("/", response_model=List[Session])
def list_sessions() -> List[Session]:
    return [_map_session(session) for session in storage.list_sessions()]


@router.get("/sessions/{session_id}/snapshot")
def get_session_snapshot(session_id: str):
    """
    Export a full JSON snapshot for the given session_id and
    persist it as a regression artifact.
    """
    session = storage.get_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Produce a JSON-serializable payload via the Pydantic schema to keep parity with other endpoints.
    data = _map_session(session).model_dump(mode="json", by_alias=True)

    artifact_path = save_session_snapshot(session_id, data)
    data["artifact_path"] = artifact_path
    return data


def _map_session(model: SessionModel) -> Session:
    return Session(
        id=model.id,
        domain=model.domain,
        platformId=model.platform_id,
        versionId=model.version_id,
        testerId=model.tester_id,
        status=model.status,
        createdAt=model.created_at,
        updatedAt=model.updated_at,
    )
