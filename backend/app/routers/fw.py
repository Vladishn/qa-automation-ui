"""Firmware-focused API endpoints."""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status

from ..models import TestRunModel, VersionModel
from ..schemas import (
    TestRunCreate,
    TestRunSummary,
    VersionCreate,
    VersionUnderTest,
    Platform,
)
from ..storage import storage

router = APIRouter(prefix="/fw", tags=["firmware"])


@router.get("/platforms", response_model=List[Platform])
def list_platforms() -> List[Platform]:
    return [
        Platform(
            id=platform.id,
            label=platform.label,
            family=platform.family,
            vendor=platform.vendor,
            model=platform.model,
        )
        for platform in storage.list_platforms("FIRMWARE")
    ]


@router.get("/versions", response_model=List[VersionUnderTest])
def list_versions(platform_id: Optional[str] = Query(None), channel: Optional[str] = Query(None)) -> List[VersionUnderTest]:
    versions = storage.list_versions("FIRMWARE", platform_id=platform_id, channel=channel)  # type: ignore[arg-type]
    return [_map_version(v) for v in versions]


@router.post("/versions", response_model=VersionUnderTest, status_code=status.HTTP_201_CREATED)
def create_version(payload: VersionCreate) -> VersionUnderTest:
    version = VersionModel(
        id=str(uuid4()),
        domain="FIRMWARE",
        platform_id=payload.platform_id,
        version_label=payload.version_label,
        release_channel=payload.release_channel,
        is_active=payload.is_active,
    )
    try:
        storage.add_version(version)
    except ValueError as exc:  # downgrade prevention
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _map_version(version)


@router.get("/runs", response_model=List[TestRunSummary])
def list_runs(
    platform_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
) -> List[TestRunSummary]:
    runs = storage.list_runs(
        "FIRMWARE",
        platform_id=platform_id,
        version_id=version_id,
        session_id=session_id,
    )
    return [_map_run(run) for run in runs]


@router.post("/runs", response_model=TestRunSummary, status_code=status.HTTP_201_CREATED)
def create_run(payload: TestRunCreate) -> TestRunSummary:
    if payload.domain != "FIRMWARE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain must be FIRMWARE")
    run = TestRunModel(
        id=str(uuid4()),
        session_id=payload.session_id,
        domain="FIRMWARE",
        platform_id=payload.platform_id,
        version_id=payload.version_id,
        tester_id=payload.tester_id,
        status=payload.status,
        pass_rate=payload.pass_rate,
        passed_scenarios=payload.passed_scenarios,
        failed_scenarios=payload.failed_scenarios,
        total_scenarios=payload.total_scenarios,
    )
    storage.add_run(run)
    return _map_run(run)


def _map_version(model: VersionModel) -> VersionUnderTest:
    return VersionUnderTest(
        id=model.id,
        domain=model.domain,
        platformId=model.platform_id,
        versionLabel=model.version_label,
        releaseChannel=model.release_channel,
        isActive=model.is_active,
    )


def _map_run(model: TestRunModel) -> TestRunSummary:
    return TestRunSummary(
        id=model.id,
        sessionId=model.session_id,
        domain=model.domain,
        platformId=model.platform_id,
        versionId=model.version_id,
        testerId=model.tester_id,
        status=model.status,
        passRate=model.pass_rate,
        passedScenarios=model.passed_scenarios,
        failedScenarios=model.failed_scenarios,
        totalScenarios=model.total_scenarios,
        startedAt=model.started_at,
        finishedAt=model.finished_at,
    )
