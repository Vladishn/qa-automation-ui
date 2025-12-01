"""QuickSet scenario execution endpoints wired to TvAutoSyncScenario."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from ..models import QuickSetQuestion, QuickSetSession, QuickSetStep
from ..storage import quickset_session_store

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

BOOLEAN_QUESTION_IDS = {
    "tv_volume_changed",
    "tv_osd_seen",
    "pairing_screen_seen",
    "volume_probe",
}
TEXT_QUESTION_IDS = {"tv_brand_ui", "notes"}
CONTINUE_QUESTION_IDS = {"manual_trigger"}


class RunScenarioRequest(BaseModel):
    tester_id: str = Field(..., alias="tester_id")
    stb_ip: str = Field(..., alias="stb_ip")
    scenario_name: str = Field(..., alias="scenario_name")

    class Config:
        allow_population_by_field_name = True


class RunScenarioResponse(BaseModel):
    session_id: str = Field(..., alias="session_id")
    scenario_name: str = Field(..., alias="scenario_name")

    class Config:
        allow_population_by_field_name = True


class QuickSetAnswer(BaseModel):
    answer: str


def require_api_key(x_quickset_api_key: str = Header(..., alias="X-QuickSet-Api-Key")) -> str:
    if not x_quickset_api_key.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    return x_quickset_api_key


@router.post("/scenarios/run", response_model=RunScenarioResponse, status_code=status.HTTP_201_CREATED)
def run_scenario(
    payload: RunScenarioRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(require_api_key),
) -> RunScenarioResponse:
    scenario_name = payload.scenario_name.upper()
    if scenario_name != "TV_AUTO_SYNC":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported scenario")

    session = quickset_session_store.create_session(
        tester_id=payload.tester_id,
        stb_ip=payload.stb_ip,
        scenario_name=scenario_name,
    )
    quickset_session_store.create_quickset_runtime(session.session_id)

    background_tasks.add_task(_execute_tv_auto_sync, session.session_id, payload.tester_id, payload.stb_ip)

    return RunScenarioResponse(session_id=session.session_id, scenario_name=session.scenario_name)


@router.get("/sessions/{session_id}", response_model=QuickSetSession)
def get_session(
    session_id: str,
    api_key: str = Depends(require_api_key),
) -> QuickSetSession:
    session = quickset_session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/answer", response_model=QuickSetSession)
def answer_question(
    session_id: str,
    payload: QuickSetAnswer,
    api_key: str = Depends(require_api_key),
) -> QuickSetSession:
    session = quickset_session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.pending_question is None or session.state != "awaiting_input":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not awaiting input")

    quickset_session_store.deliver_answer(session_id, payload.answer)
    updated = quickset_session_store.get_session(session_id)
    return updated if updated else session


def ask_via_session(
    session_id: str,
    question_id: str,
    prompt: str,
    metadata: Dict[str, Any] | None = None,
) -> str:
    step_name = f"question_{question_id}"
    input_kind, choices = _resolve_input_kind(question_id)
    meta = {"question_id": question_id}
    if metadata:
        meta.update(metadata)
    question = QuickSetQuestion(
        id=str(uuid4()),
        prompt=prompt,
        step_name=step_name,
        input_kind=input_kind,
        choices=choices,
        metadata=meta,
    )
    return quickset_session_store.wait_for_answer(session_id, question)


class QuickSetStepLogger(StepLogger):
    """Mirrors StepLogger output into the session store."""

    def log_step(self, step_name: str, status: str, details: Dict[str, Any] | None = None) -> None:  # type: ignore[override]
        super().log_step(step_name, status, details)
        quickset_session_store.append_step(
            self.session_id,
            QuickSetStep(
                name=step_name,
                status=_map_step_status(status),
                timestamp=datetime.utcnow(),
                metadata=details or {},
            ),
        )


def _map_step_status(status: str) -> str:
    normalized = (status or "").strip().upper()
    if normalized in {"PASS", "SUCCESS", "OK"}:
        return "pass"
    if normalized in {"FAIL", "FAILED", "ERROR"}:
        return "fail"
    if normalized in {"RUNNING", "IN_PROGRESS"}:
        return "running"
    if normalized in {"INFO", "DEBUG", "START"}:
        return "info"
    return "pending"


def _resolve_input_kind(question_id: str) -> tuple[str, list[str] | None]:
    if question_id in CONTINUE_QUESTION_IDS:
        return "continue", None
    if question_id in BOOLEAN_QUESTION_IDS:
        return "boolean", ["yes", "no"]
    if question_id in TEXT_QUESTION_IDS:
        return "text", None
    return "text", None


def _make_ask(session_id: str, step_logger: QuickSetStepLogger):
    def _ask(question_id: str, prompt_text: str) -> str:
        step_logger.log_step(
            f"question_{question_id}",
            "INFO",
            {"prompt": prompt_text, "question_id": question_id},
        )
        answer = ask_via_session(session_id, question_id, prompt_text, {"question_id": question_id})
        step_logger.log_step(
            f"question_{question_id}_answer",
            "INFO",
            {"prompt": prompt_text, "answer": answer, "question_id": question_id},
        )
        return answer

    return _ask


def _execute_tv_auto_sync(session_id: str, tester_id: str, stb_ip: str) -> None:
    raw_dir = RAW_LOG_DIR / session_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    step_logger = QuickSetStepLogger(session_id=session_id, output_dir=STEP_LOG_DIR)
    quickset_session_store.set_state(session_id, "running")

    logcat_path = raw_dir / f"{session_id}_tv_auto_sync.log"
    final_status = "fail"

    try:
        adb_client = ADBClient(stb_ip)
        scenario = TvAutoSyncScenario(
            adb_client=adb_client,
            step_logger=step_logger,
            knowledge_path=KNOWLEDGE_PATH,
            raw_log_dir=raw_dir,
            session_id=session_id,
        )
        ask_fn = _make_ask(session_id, step_logger)
        result = scenario.run(ask=ask_fn)
        status_value = (result.get("status") or "").strip().lower()
        final_status = "pass" if status_value == "pass" else "fail"
        analysis = result.get("analysis")
        if analysis:
            step_logger.log_step("analysis_summary", "INFO", {"analysis": analysis})
    except Exception as exc:  # noqa: BLE001
        step_logger.log_step("scenario_exception", "FAIL", {"error": str(exc)})
        final_status = "fail"
    finally:
        step_logger.close()

    adb_log = _read_text(step_logger.log_path)
    logcat_log = _read_text(logcat_path)

    snapshot = quickset_session_store.get_session(session_id)
    if snapshot:
        for step in reversed(snapshot.steps):
            if step.name == "analysis_summary":
                quickset_session_store.replace_step(
                    session_id,
                    "analysis_summary",
                    QuickSetStep(
                        name="analysis_summary",
                        status=final_status,
                        timestamp=step.timestamp or datetime.utcnow(),
                        metadata=step.metadata,
                    ),
                )
                break

    quickset_session_store.finalize_session(
        session_id,
        result=final_status,
        logs={"adb": adb_log, "logcat": logcat_log},
    )


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")
