"""QuickSet scenario execution endpoints wired to the real TvAutoSyncScenario."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status

from ..models import QuickSetQuestionModel, QuickSetStepModel
from ..schemas import (
    QuickSetRunRequest,
    QuickSetRunResponse,
    QuickSetSession,
    QuickSetStep,
    QuickSetAnswer,
)
from ..storage import quickset_session_store

# Ensure the project root (containing src/) is importable
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.adb.adb_client import ADBClient  # noqa: E402
from src.qa.step_logger import StepLogger  # noqa: E402
from src.quickset.scenarios.tv_auto_sync import TvAutoSyncScenario  # noqa: E402

RAW_LOG_DIR = PROJECT_ROOT / "artifacts" / "quickset_logs"
STEP_LOG_DIR = PROJECT_ROOT / "artifacts" / "quickset_steps"
KNOWLEDGE_PATH = PROJECT_ROOT / "knowledge" / "scenarios" / "tv_auto_sync.yaml"

RAW_LOG_DIR.mkdir(parents=True, exist_ok=True)
STEP_LOG_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/quickset", tags=["quickset"])


@router.post("/scenarios/run", response_model=QuickSetRunResponse, status_code=status.HTTP_201_CREATED)
def run_scenario(
    payload: QuickSetRunRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Header(..., alias="X-QuickSet-Api-Key"),
) -> QuickSetRunResponse:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    if payload.scenario_name != "TV_AUTO_SYNC":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported scenario")

    session = quickset_session_store.create_session(
        tester_id=payload.tester_id,
        stb_ip=payload.stb_ip,
        scenario_name=payload.scenario_name,
        steps=[],
    )
    quickset_session_store.create_runtime(session.session_id)

    background_tasks.add_task(_execute_tv_auto_sync, session.session_id, payload.tester_id, payload.stb_ip)

    return QuickSetRunResponse(session_id=session.session_id, scenario_name=session.scenario_name)


@router.get("/sessions/{session_id}", response_model=QuickSetSession)
def get_session(
    session_id: str,
    api_key: str = Header(..., alias="X-QuickSet-Api-Key"),
) -> QuickSetSession:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    session = quickset_session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _map_session(session)


@router.post("/sessions/{session_id}/answer", response_model=QuickSetSession)
def answer_question(
    session_id: str,
    payload: QuickSetAnswer,
    api_key: str = Header(..., alias="X-QuickSet-Api-Key"),
) -> QuickSetSession:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    session = quickset_session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    runtime = quickset_session_store.get_runtime(session_id)
    runtime.answer_value = payload.answer
    runtime.answer_event.set()
    session = quickset_session_store.get_session(session_id)
    return _map_session(session)


class QuickSetStepLogger(StepLogger):
    """Step logger that mirrors entries into the QuickSet session store."""

    def __init__(self, session_id: str, output_dir: Path, store) -> None:  # type: ignore[no-untyped-def]
        super().__init__(session_id=session_id, output_dir=output_dir)
        self._store = store

    def log_step(self, step_name: str, status: str, details: Dict | None = None) -> None:  # type: ignore[override]
        super().log_step(step_name, status, details)
        quickset_status = _map_step_status(status)
        step_model = QuickSetStepModel(
            name=step_name,
            status=quickset_status,
            timestamp=datetime.utcnow(),
            metadata=details or {},
        )
        self._store.upsert_step(self.session_id, step_model)


def _map_step_status(status: str) -> str:
    normalized = (status or '').strip().upper()
    if normalized in {"PASS", "SUCCESS", "OK", "DONE"}:
        return "pass"
    if normalized in {"FAIL", "FAILED", "ERROR"}:
        return "fail"
    if normalized in {"RUNNING", "IN_PROGRESS"}:
        return "running"
    if normalized in {"INFO", "DEBUG", "START"}:
        return "info"
    return "pending"


def _make_ask(session_id: str, step_logger: StepLogger):
    runtime = quickset_session_store.get_runtime(session_id)

    def _ask(question_id: str, prompt_text: str) -> str:
        question = QuickSetQuestionModel(
            id=str(uuid4()),
            prompt=prompt_text,
            metadata={"question_id": question_id},
        )
        step_logger.log_step(
            f"question_{question_id}",
            "INFO",
            {
                "prompt": prompt_text,
                "status": "awaiting_input",
            },
        )
        quickset_session_store.set_pending_question(session_id, question)
        runtime.answer_value = None
        runtime.answer_event.clear()
        runtime.answer_event.wait()
        answer = runtime.answer_value or ""
        step_logger.log_step(
            f"question_{question_id}_answer",
            "INFO",
            {
                "prompt": prompt_text,
                "answer": answer,
            },
        )
        quickset_session_store.clear_pending_question(session_id)
        return answer

    return _ask


def _execute_tv_auto_sync(session_id: str, tester_id: str, stb_ip: str) -> None:
    raw_session_dir = RAW_LOG_DIR / session_id
    raw_session_dir.mkdir(parents=True, exist_ok=True)
    step_logger = QuickSetStepLogger(session_id=session_id, output_dir=STEP_LOG_DIR, store=quickset_session_store)
    quickset_session_store.set_state(session_id, "running")

    logcat_path = raw_session_dir / f"{session_id}_tv_auto_sync.log"
    final_status = "fail"
    try:
        adb_client = ADBClient(stb_ip)
        scenario = TvAutoSyncScenario(
            adb_client=adb_client,
            step_logger=step_logger,
            knowledge_path=KNOWLEDGE_PATH,
            raw_log_dir=raw_session_dir,
            session_id=session_id,
        )
        ask_fn = _make_ask(session_id, step_logger)
        result = scenario.run(ask=ask_fn)
        if result.get("analysis"):
            step_logger.log_step("analysis_summary", "INFO", {"analysis": result["analysis"]})
        status = (result.get("status") or "").upper()
        final_status = "pass" if status == "PASS" else "fail"
    except Exception as exc:  # noqa: BLE001
        step_logger.log_step("scenario_exception", "FAIL", {"error": str(exc)})
        final_status = "fail"
    finally:
        step_logger.close()

    adb_log = _read_text(step_logger.log_path)
    logcat_log = _read_text(logcat_path)
    session_snapshot = quickset_session_store.get_session(session_id)
    if session_snapshot:
        summary_metadata = None
        summary_timestamp = datetime.utcnow()
        for step in reversed(session_snapshot.steps):
            if step.name == "analysis_summary":
                summary_metadata = step.metadata
                summary_timestamp = step.timestamp or datetime.utcnow()
                break
        if summary_metadata is not None:
            quickset_session_store.upsert_step(
                session_id,
                QuickSetStepModel(
                    name="analysis_summary",
                    status=final_status,
                    timestamp=summary_timestamp,
                    metadata=summary_metadata,
                ),
            )
    quickset_session_store.complete_session(
        session_id=session_id,
        result=final_status,
        logs={"adb": adb_log, "logcat": logcat_log},
    )


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _map_session(model) -> QuickSetSession:  # type: ignore[no-untyped-def]
    return QuickSetSession(
        session_id=model.session_id,
        tester_id=model.tester_id,
        stb_ip=model.stb_ip,
        scenario_name=model.scenario_name,
        start_time=model.start_time,
        end_time=model.end_time,
        steps=[
            QuickSetStep(
                name=step.name,
                status=step.status,
                timestamp=step.timestamp,
                metadata=step.metadata,
            )
            for step in model.steps
        ],
        result=model.result,
        logs=model.logs,
    )
