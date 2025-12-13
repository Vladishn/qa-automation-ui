"""QuickSet scenario execution endpoints wired to TvAutoSyncScenario."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import re
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from ..adb_service import AdbPrecheckResult, AdbPrecheckStatus, precheck
from ..config import settings
from ..models import (
    QuickSetInfraCheck,
    QuickSetQuestion,
    QuickSetSession as QuickSetRuntimeSession,
    QuickSetStep,
)
from ..quickset_timeline_analyzer import build_timeline_and_summary
from ..regression_snapshots import save_session_snapshot
from ..schemas import (
    TvAutoSyncSession,
    TvAutoSyncSessionResponse,
    TvAutoSyncTimelineEvent,
)
from ..storage import quickset_session_store
from ..timeline_loader import load_session_events

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.adb.adb_client import ADBClient  # noqa: E402
from src.qa.step_logger import StepLogger  # noqa: E402
from src.quickset.scenarios.tv_auto_sync import TvAutoSyncScenario  # noqa: E402

from ..live_button_workflow import configure_live_mapping, live_phase_press

RAW_LOG_DIR = PROJECT_ROOT / "artifacts" / "quickset_logs"
LIVE_LOG_DIR = PROJECT_ROOT / "backend" / "artifacts" / "live_logs"
STEP_LOG_DIR = Path(settings.quickset_steps_dir)
KNOWLEDGE_PATH = PROJECT_ROOT / "knowledge" / "scenarios" / "tv_auto_sync.yaml"

RAW_LOG_DIR.mkdir(parents=True, exist_ok=True)
LIVE_LOG_DIR.mkdir(parents=True, exist_ok=True)
STEP_LOG_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/quickset", tags=["quickset"])
logger = logging.getLogger(__name__)
_workflow_threads: Dict[str, threading.Thread] = {}

BOOLEAN_QUESTION_IDS = {
    "tv_volume_changed",
    "tv_osd_seen",
    "pairing_screen_seen",
}
TEXT_QUESTION_IDS = {"tv_brand_ui", "notes"}
CONTINUE_QUESTION_IDS = {"manual_trigger"}


class RunScenarioRequest(BaseModel):
    tester_id: str = Field(..., alias="tester_id")
    stb_ip: str = Field(..., alias="stb_ip")
    scenario_name: str = Field(..., alias="scenario_name")
    expected_channel: Optional[int] = Field(None, alias="expected_channel")

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
    api_key: str = Depends(require_api_key),
) -> RunScenarioResponse:
    scenario_name = payload.scenario_name.upper()
    handler_map: Dict[str, Callable[..., None]] = {
        "TV_AUTO_SYNC": _execute_tv_auto_sync,
        "LIVE_BUTTON_MAPPING": _execute_live_button_mapping,
    }
    handler = handler_map.get(scenario_name)
    if handler is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported scenario")

    expected_channel_value: Optional[int] = None
    if scenario_name == "LIVE_BUTTON_MAPPING":
        expected_channel_value = _safe_int(payload.expected_channel, 3)

    session = quickset_session_store.create_session(
        tester_id=payload.tester_id,
        stb_ip=payload.stb_ip,
        scenario_name=scenario_name,
    )
    quickset_session_store.create_quickset_runtime(session.session_id)
    _record_test_started_step(session.session_id, scenario_name, payload.tester_id)

    if scenario_name == "LIVE_BUTTON_MAPPING":
        _launch_workflow_thread(
            handler,
            session.session_id,
            payload.tester_id,
            payload.stb_ip,
            expected_channel_value,
        )
    else:
        _launch_workflow_thread(handler, session.session_id, payload.tester_id, payload.stb_ip)

    return RunScenarioResponse(session_id=session.session_id, scenario_name=session.scenario_name)


@router.get("/sessions/{session_id}", response_model=TvAutoSyncSessionResponse)
def get_session(
    session_id: str,
    api_key: str = Depends(require_api_key),
) -> TvAutoSyncSessionResponse:
    session = quickset_session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QuickSet session not found")
    dto, _ = _build_tv_autosync_envelope(session, include_runtime=True)
    return dto


@router.get("/sessions/{session_id}/snapshot")
def get_quickset_session_snapshot(session_id: str) -> Dict[str, Any]:
    """
    Export a full JSON snapshot for the given QuickSet session_id and
    persist it as a regression artifact for later diffing.
    """
    session = quickset_session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QuickSet session not found")

    dto, analyzer_ready = _build_tv_autosync_envelope(session, include_runtime=False)
    if not analyzer_ready:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Analyzer data not available for snapshot")

    data = dto.model_dump(mode="json", by_alias=True)
    artifact_path = save_session_snapshot(session_id, data)
    data["artifact_path"] = artifact_path
    return data


@router.post("/sessions/{session_id}/answer", response_model=TvAutoSyncSessionResponse)
def answer_question(
    session_id: str,
    payload: QuickSetAnswer,
    api_key: str = Depends(require_api_key),
) -> TvAutoSyncSessionResponse:
    session = quickset_session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QuickSet session not found")
    if session.pending_question is None or session.state != "awaiting_input":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not awaiting input")

    quickset_session_store.deliver_answer(session_id, payload.answer)
    updated = quickset_session_store.get_session(session_id)
    runtime_session = updated if updated else session
    dto, _ = _build_tv_autosync_envelope(runtime_session, include_runtime=True)
    return dto


def _build_tv_autosync_envelope(
    session: QuickSetRuntimeSession,
    *,
    include_runtime: bool,
) -> Tuple[TvAutoSyncSessionResponse, bool]:
    analyzer_payload = _load_analyzer_payload(session.session_id, session.scenario_name)
    analyzer_ready = False

    if analyzer_payload:
        raw_summary = TvAutoSyncSession(**analyzer_payload["session"])
        timeline = [
            TvAutoSyncTimelineEvent(**row)
            for row in analyzer_payload.get("timeline", [])
        ]
        analysis_result = analyzer_payload.get("analysis_result")
        if analysis_result:
            _inject_analysis_details(timeline, analysis_result)
        has_failure = bool(analyzer_payload.get("has_failure", raw_summary.has_failure))
        analyzer_ready = _is_analyzer_ready(raw_summary, timeline)
        awaiting_tester_input = _is_awaiting_input(session, raw_summary)
        if awaiting_tester_input:
            pending_text = raw_summary.analysis_text or "TV auto-sync in progress – awaiting tester input."
            summary = raw_summary.model_copy(
                update={
                    "overall_status": "PENDING",
                    "has_failure": False,
                    "analysis_text": pending_text,
                    "analyzer_ready": False,
                }
            )
            has_failure = False
            analyzer_ready = False
        else:
            summary = raw_summary.model_copy(update={"analyzer_ready": analyzer_ready})
    else:
        summary = _build_pending_summary(session)
        timeline = []
        has_failure = summary.has_failure

    runtime_dump = session.model_dump(mode="json", by_alias=True) if include_runtime else None
    dto = TvAutoSyncSessionResponse(
        session=summary,
        timeline=timeline,
        has_failure=has_failure,
        quickset_session=runtime_dump,
    )
    return dto, analyzer_ready


def _load_analyzer_payload(session_id: str, scenario_name: Optional[str]) -> Optional[Dict[str, Any]]:
    events = load_session_events(session_id)
    if not events:
        return None
    resolved = scenario_name or "UNKNOWN"
    return build_timeline_and_summary(
        session_id=session_id,
        scenario_name=resolved,
        raw_events=events,
    )


def _build_pending_summary(session: QuickSetRuntimeSession) -> TvAutoSyncSession:
    running = session.state != "completed"
    analysis = "Analyzer is still running."
    if running:
        analysis = "Session is still running. Analyzer will start shortly."
    return TvAutoSyncSession(
        session_id=session.session_id,
        scenario_name=session.scenario_name,
        started_at=_to_iso(session.start_time),
        finished_at=_to_iso(session.end_time),
        overall_status="PENDING",
        has_failure=False,
        brand_mismatch=False,
        tv_brand_user=None,
        tv_brand_log=None,
        has_volume_issue=False,
        has_osd_issue=False,
        analysis_text=analysis,
        notes=None,
        analyzer_ready=False,
    )


def _is_analyzer_ready(summary: TvAutoSyncSession, timeline: List[TvAutoSyncTimelineEvent]) -> bool:
    if summary.overall_status in {"PASS", "FAIL"}:
        return True
    return any(row.name == "analysis_summary" and row.status in {"PASS", "FAIL"} for row in timeline)


def _is_awaiting_input(session: QuickSetRuntimeSession, summary: TvAutoSyncSession) -> bool:
    return session.state == "awaiting_input" or summary.overall_status == "AWAITING_INPUT"


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.isoformat()


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


def _inject_analysis_details(
    timeline: List[TvAutoSyncTimelineEvent],
    analysis_result: Dict[str, Any],
) -> None:
    summary_row = next((row for row in timeline if row.name == "analysis_summary"), None)
    if not summary_row:
        return
    details = dict(summary_row.details or {})
    failure_insights = analysis_result.get("failure_insights")
    evidence = analysis_result.get("evidence")
    recommendations = analysis_result.get("recommendations")
    confidence = analysis_result.get("confidence")
    if failure_insights:
        details["failure_insights"] = failure_insights
    if evidence:
        details["evidence"] = evidence
    if recommendations:
        details["recommendations"] = recommendations
    if confidence:
        details["confidence"] = confidence
        details["confidence_level"] = confidence
    summary_row.details = details


def _make_ask(session_id: str, step_logger: QuickSetStepLogger):
    def _ask(question_id: str, prompt_text: str) -> str:
        step_logger.log_step(
            f"question_{question_id}",
            "INFO",
            {"prompt": prompt_text, "question_id": question_id, "tester_visible": True},
        )
        answer = ask_via_session(session_id, question_id, prompt_text, {"question_id": question_id})
        step_logger.log_step(
            f"question_{question_id}_answer",
            "INFO",
            {"prompt": prompt_text, "answer": answer, "question_id": question_id, "tester_visible": True},
        )
        return answer

    return _ask


def _execute_tv_auto_sync(session_id: str, tester_id: str, stb_ip: str) -> None:
    raw_dir = RAW_LOG_DIR / session_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    step_logger = QuickSetStepLogger(session_id=session_id, output_dir=STEP_LOG_DIR)
    quickset_session_store.set_state(session_id, "running")

    precheck_result = _run_adb_precheck(session_id, step_logger, stb_ip)
    if precheck_result.status is not AdbPrecheckStatus.OK:
        return

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

    tv_model = _extract_tv_model_from_text(logcat_log)
    if tv_model:
        quickset_session_store.set_tv_model(session_id, tv_model)

    remote_keys = _extract_remote_keys(logcat_log)
    if remote_keys:
        quickset_session_store.set_remote_keys(session_id, remote_keys)

    snapshot = quickset_session_store.get_session(session_id)
    final_summary = ""
    if snapshot:
        evidence = _collect_session_evidence(snapshot)
        decision_result, decision_summary = compute_quickset_result(*evidence)
        final_status = decision_result
        final_summary = decision_summary
        _sync_analysis_summary_step(session_id, snapshot.steps, final_status, final_summary)

    quickset_session_store.finalize_session(
        session_id,
        result=final_status,
        logs={"adb": adb_log, "logcat": logcat_log},
        summary=final_summary or None,
    )


def _execute_live_button_mapping(
    session_id: str,
    tester_id: str,
    stb_ip: str,
    expected_channel_override: Optional[int] = None,
) -> None:
    raw_dir = RAW_LOG_DIR / session_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    step_logger = QuickSetStepLogger(session_id=session_id, output_dir=STEP_LOG_DIR)
    quickset_session_store.set_state(session_id, "running")

    precheck_result = _run_adb_precheck(session_id, step_logger, stb_ip)
    if precheck_result.status is not AdbPrecheckStatus.OK:
        return

    logcat_path = LIVE_LOG_DIR / f"live_{session_id}.log"
    final_status = "fail"
    final_summary = ""
    adb_client = ADBClient(stb_ip)
    expected_channel = _safe_int(expected_channel_override, 3)
    live_log_proc: Optional[subprocess.Popen] = None
    live_log_handle: Optional[Any] = None
    logcat_started = False
    restart_live_log_capture_cb: Optional[Callable[[], None]] = None

    step_logger.log_step(
        "live_expected_channel",
        "INFO",
        {
            "expected_channel": expected_channel,
            "source": "session_start_payload",
            "tester_visible": False,
        },
    )

    try:
        step_logger.log_step(
            "logcat_capture_start",
            "INFO",
            {"log_path": str(logcat_path), "tester_visible": False},
        )
        try:
            logcat_path, live_log_proc, live_log_handle = _start_live_log_capture(adb_client, session_id)
            logcat_started = True
            step_logger.log_step(
                "logcat_capture_start",
                "PASS",
                {"log_path": str(logcat_path), "tester_visible": False},
            )

            def _restart_live_log_capture_inner() -> None:
                nonlocal live_log_proc, live_log_handle, logcat_path, logcat_started
                try:
                    _stop_live_log_capture(live_log_proc, live_log_handle)
                except Exception:
                    pass
                logcat_path, live_log_proc, live_log_handle = _start_live_log_capture(
                    adb_client,
                    session_id,
                    append=True,
                    existing_path=logcat_path,
                )
                logcat_started = True

            restart_live_log_capture_cb = _restart_live_log_capture_inner

        except Exception as exc:  # noqa: BLE001
            step_logger.log_step(
                "logcat_capture_start",
                "FAIL",
                {"error": str(exc), "log_path": str(logcat_path), "tester_visible": False},
            )
            raise

        phase_steps = [
            ("phase1_live_press", "PHASE1", {"do_force_stop": False, "do_reboot": False}),
            ("phase2_kill_and_relaunch", "PHASE2", {"do_force_stop": True, "do_reboot": False}),
            (
                "phase3_reboot_persist",
                "PHASE3",
                {
                    "do_force_stop": False,
                    "do_reboot": True,
                    "post_reboot_callback": restart_live_log_capture_cb,
                },
            ),
        ]

        step_logger.log_step(
            "configure_live_mapping",
            "RUNNING",
            {"expected_channel": expected_channel, "tester_visible": False},
        )
        try:
            configure_live_mapping(adb_client, expected_channel)
            step_logger.log_step(
                "configure_live_mapping",
                "PASS",
                {"expected_channel": expected_channel, "tester_visible": False},
            )
        except Exception as exc:
            step_logger.log_step(
                "configure_live_mapping",
                "FAIL",
                {"expected_channel": expected_channel, "error": str(exc), "tester_visible": False},
            )
            _mark_live_phases_skipped(step_logger, phase_steps, expected_channel, str(exc))
            raise

        for step_name, phase_label, options in phase_steps:
            step_logger.log_step(
                step_name,
                "RUNNING",
                {"expected_channel": expected_channel, "phase": phase_label, "tester_visible": False},
            )
            try:
                live_phase_press(
                    adb_client,
                    phase_label,
                    expected_channel,
                    do_force_stop=options.get("do_force_stop", False),
                    do_reboot=options.get("do_reboot", False),
                    post_reboot_callback=options.get("post_reboot_callback"),
                )
                step_logger.log_step(
                    step_name,
                    "PASS",
                    {"expected_channel": expected_channel, "phase": phase_label, "tester_visible": False},
                )
            except Exception as exc:
                step_logger.log_step(
                    step_name,
                    "FAIL",
                    {
                        "expected_channel": expected_channel,
                        "phase": phase_label,
                        "error": str(exc),
                        "tester_visible": False,
                    },
                )
                raise

        final_summary = (
            f"Live button automation completed for expected channel {expected_channel}. "
            "Analyzer will determine the final verdict from logs."
        )
        final_status = "pass"
    except Exception as exc:  # noqa: BLE001
        final_summary = f"Live button automation failed: {exc}"
        step_logger.log_step("scenario_exception", "FAIL", {"error": str(exc)})
        final_status = "fail"
    finally:
        if logcat_started:
            try:
                _stop_live_log_capture(live_log_proc, live_log_handle)
                step_logger.log_step(
                    "logcat_capture_stop",
                    "PASS",
                    {"log_path": str(logcat_path), "tester_visible": False},
                )
            except Exception as exc:  # noqa: BLE001
                step_logger.log_step("logcat_capture_stop", "FAIL", {"error": str(exc)})
        summary_status = "INFO" if final_status == "pass" else "FAIL"
        step_logger.log_step(
            "analysis_summary",
            summary_status,
            {"analysis": final_summary, "expected_channel": expected_channel, "tester_visible": False},
        )
        step_logger.log_step(
            "test_completed",
            summary_status,
            {"expected_channel": expected_channel, "tester_visible": False},
        )
        step_logger.close()

    adb_log = _read_text(step_logger.log_path)
    logcat_log = _read_text(logcat_path)

    remote_keys = _extract_remote_keys(logcat_log)
    if remote_keys:
        quickset_session_store.set_remote_keys(session_id, remote_keys)

    if not final_summary:
        final_summary = "Live Button Mapping run completed."

    snapshot = quickset_session_store.get_session(session_id)
    if snapshot:
        _sync_analysis_summary_step(session_id, snapshot.steps, final_status, final_summary)

    quickset_session_store.finalize_session(
        session_id,
        result=final_status,
        logs={"adb": adb_log, "logcat": logcat_log},
        summary=final_summary or None,
    )


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _start_live_log_capture(
    adb_client: ADBClient,
    session_id: str,
    *,
    append: bool = False,
    existing_path: Optional[Path] = None,
) -> Tuple[Path, subprocess.Popen, Any]:
    LIVE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = existing_path or (LIVE_LOG_DIR / f"live_{session_id}.log")
    mode = "a" if append and log_path.exists() else "w"
    log_file = open(log_path, mode, encoding="utf-8", errors="ignore")
    cmd = [adb_client.adb_path, "-s", adb_client.target, "logcat", "-b", "all", "-v", "threadtime"]
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, text=True)
    return log_path, proc, log_file


def _stop_live_log_capture(proc: Optional[subprocess.Popen], handle: Optional[Any]) -> None:
    if proc is not None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        proc = None
    if handle is not None and not handle.closed:
        handle.close()


def _mark_live_phases_skipped(
    step_logger: QuickSetStepLogger,
    phase_steps: List[Tuple[str, str, Dict[str, Any]]],
    expected_channel: int,
    reason: str,
) -> None:
    for step_name, phase_label, _ in phase_steps:
        step_logger.log_step(
            step_name,
            "INFO",
            {
                "expected_channel": expected_channel,
                "phase": phase_label,
                "skipped_due_to_config_error": True,
                "reason": reason,
                "tester_visible": False,
            },
        )
# --------------------------------------------------------------------------- #
# Worker orchestration helpers
# --------------------------------------------------------------------------- #


def _launch_workflow_thread(
    handler: Callable[..., None],
    session_id: str,
    *args: Any,
) -> None:
    thread = threading.Thread(
        target=_run_workflow_safe,
        args=(handler, session_id, *args),
        name=f"quickset-{session_id}",
        daemon=True,
    )
    _workflow_threads[session_id] = thread
    thread.start()


def _run_workflow_safe(
    handler: Callable[..., None],
    session_id: str,
    *args: Any,
) -> None:
    try:
        handler(session_id, *args)
    except asyncio.CancelledError:
        logger.info("QuickSet session %s cancelled", session_id)
        _ensure_session_completed(
            session_id,
            result="fail",
            summary="QuickSet session cancelled before completion.",
            metadata={"cancelled": True},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("QuickSet session %s crashed: %s", session_id, exc)
        _ensure_session_completed(
            session_id,
            result="fail",
            summary=f"QuickSet automation failed: {exc}",
            metadata={"error": str(exc)},
        )
    finally:
        _workflow_threads.pop(session_id, None)


def _record_test_started_step(session_id: str, scenario_name: str, tester_id: str) -> None:
    _append_quickset_step(
        session_id,
        "test_started",
        "info",
        {
            "scenario_name": scenario_name,
            "tester_id": tester_id,
            "tester_visible": False,
        },
    )


def _append_quickset_step(session_id: str, name: str, status: str, metadata: Dict[str, Any] | None = None) -> None:
    quickset_session_store.append_step(
        session_id,
        QuickSetStep(
            name=name,
            status=status,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
        ),
    )


def _ensure_session_completed(
    session_id: str,
    *,
    result: str,
    summary: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    session = quickset_session_store.get_session(session_id)
    if not session or session.state == "completed":
        return
    merged_metadata = {"tester_visible": False}
    if metadata:
        merged_metadata.update(metadata)
    _append_quickset_step(session_id, "test_completed", result or "fail", merged_metadata)
    existing_logs = dict(session.logs or {})
    quickset_session_store.finalize_session(
        session_id,
        result=result or "fail",
        logs=existing_logs,
        summary=summary or result.upper(),
    )



def _safe_int(value: Optional[str], default: int = 3) -> int:
    if value is None:
        return default
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _split_target(raw: str) -> tuple[str, int]:
    if ":" in raw:
        host, port_str = raw.rsplit(":", 1)
        try:
            return host, int(port_str)
        except ValueError:
            return host, 5555
    return raw, 5555


def _run_adb_precheck(session_id: str, step_logger: QuickSetStepLogger, raw_target: str) -> AdbPrecheckResult:
    host, port = _split_target(raw_target)
    result = precheck(host, port)
    metadata = {
        "status": result.status.value,
        "message": result.message,
        "ping_ok": result.ping_ok,
        "tcp_port_open": result.tcp_port_open,
        "adb_stdout": result.adb_stdout,
        "adb_stderr": result.adb_stderr,
        "tester_visible": False,
    }

    infra_status = "ok" if result.status is AdbPrecheckStatus.OK else "fail"
    quickset_session_store.add_infra_check(
        session_id,
        QuickSetInfraCheck(name="adb_precheck", status=infra_status, message=result.message),
    )

    if result.status is AdbPrecheckStatus.OK:
        step_logger.log_step("adb_precheck", "PASS", metadata)
        return result

    step_logger.log_step("adb_precheck", "FAIL", metadata)
    quickset_session_store.finalize_session(
        session_id,
        result="fail",
        logs={"adb": "", "logcat": ""},
        summary=result.message,
    )
    return result


TV_BRAND_MODEL_PATTERNS = [
    re.compile(r"brand\s*[:=]\s*(?P<brand>[A-Za-z0-9 _-]+).*model\s*[:=]\s*(?P<model>[A-Za-z0-9 _-]+)", re.IGNORECASE),
    re.compile(r"tv[_ ]?model(?:name)?\s*[:=\-]\s*(?P<model>[A-Za-z0-9 _-]+)", re.IGNORECASE),
    re.compile(r"modelName\s*=\s*(?P<model>[A-Za-z0-9 _-]+)", re.IGNORECASE),
]

REMOTE_KEY_PATTERNS = [
    re.compile(r"KEYCODE_[A-Z0-9_]+"),
    re.compile(r"keycode\s+([A-Z0-9_]+)", re.IGNORECASE),
]


def _extract_tv_model_from_text(log_text: str) -> Optional[str]:
    if not log_text:
        return None
    for pattern in TV_BRAND_MODEL_PATTERNS:
        match = pattern.search(log_text)
        if match:
            brand = match.groupdict().get("brand")
            model = match.groupdict().get("model")
            if brand and model:
                return f"{brand.strip()} {model.strip()}".strip()
            if model:
                return model.strip()
    return None


def _extract_remote_keys(log_text: str) -> List[str]:
    if not log_text:
        return []
    seen: set[str] = set()
    detected: List[str] = []
    upper_text = log_text.upper()
    for pattern in REMOTE_KEY_PATTERNS:
        for match in pattern.finditer(upper_text):
            key = match.group(1) if match.lastindex else match.group(0)
            if not key:
                continue
            cleaned = key.upper().strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                detected.append(cleaned)
    return detected


def compute_session_decision(session: QuickSetRuntimeSession) -> QuickSetRuntimeSession:
    if session.state != "completed":
        return session

    has_log_analysis = any(step.name == "log_analysis_complete" for step in session.steps)
    if not has_log_analysis:
        return session

    evidence = _collect_session_evidence(session)
    result, summary = compute_quickset_result(*evidence)
    final_summary = summary or ""
    if session.tv_model and session.tv_model not in final_summary:
        suffix = f"TV model detected: {session.tv_model}."
        final_summary = f"{final_summary} {suffix}".strip()

    updated_steps: List[QuickSetStep] = []
    last_summary_idx: Optional[int] = None
    for idx, step in enumerate(session.steps):
        updated_steps.append(step)
        if step.name == "analysis_summary":
            last_summary_idx = idx

    if last_summary_idx is not None:
        step = updated_steps[last_summary_idx]
        metadata = dict(step.metadata or {})
        metadata["analysis"] = final_summary or result.upper()
        updated_steps[last_summary_idx] = step.model_copy(update={"metadata": metadata})

    return session.model_copy(update={"result": result, "summary": final_summary, "steps": updated_steps})


def _collect_session_evidence(
    session: QuickSetRuntimeSession,
) -> Tuple[Optional[str], Optional[dict], Optional[dict], Optional[dict], Optional[dict]]:
    log_meta = _extract_latest_metadata(session.steps, "log_analysis_complete")
    log_state = None
    terminal_state = None
    if isinstance(log_meta, dict):
        potential_state = log_meta.get("state")
        if isinstance(potential_state, dict):
            log_state = potential_state
            term = potential_state.get("terminal_state")
            if isinstance(term, str):
                terminal_state = term

    tester_meta = _extract_latest_metadata(session.steps, "tester_questions")
    observations: Optional[dict] = None
    if isinstance(tester_meta, dict):
        obs = tester_meta.get("observations") or tester_meta
        if isinstance(obs, dict):
            observations = obs

    probe_meta = _extract_latest_metadata(session.steps, "volume_probe_result")
    tv_meta = _extract_latest_metadata(session.steps, "tv_metadata")

    return terminal_state, log_state, observations, probe_meta, tv_meta


def _sync_analysis_summary_step(
    session_id: str,
    steps: List[QuickSetStep],
    final_status: str,
    final_summary: str,
) -> None:
    summary_text = final_summary or final_status.upper()
    for step in reversed(steps):
        if step.name == "analysis_summary":
            metadata = dict(step.metadata or {})
            metadata["analysis"] = summary_text
            metadata["tester_visible"] = True
            quickset_session_store.replace_step(
                session_id,
                "analysis_summary",
                QuickSetStep(
                    name="analysis_summary",
                    status=final_status,
                    timestamp=step.timestamp or datetime.utcnow(),
                    metadata=metadata,
                ),
            )
            return

    quickset_session_store.append_step(
        session_id,
        QuickSetStep(
            name="analysis_summary",
            status=final_status,
            timestamp=datetime.utcnow(),
            metadata={"analysis": summary_text, "tester_visible": True},
        ),
    )


def _extract_latest_metadata(steps: List[QuickSetStep], step_name: str) -> Optional[dict]:
    for step in reversed(steps):
        if step.name == step_name and isinstance(step.metadata, dict):
            return step.metadata
    return None


def _normalize_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"yes", "y", "true", "1", "on"}:
            return True
        if normalized in {"no", "n", "false", "0", "off"}:
            return False
    return None


def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def compute_quickset_result(
    log_terminal_state: Optional[str],
    log_state: Optional[dict],
    observations: Optional[dict],
    volume_probe: Optional[dict],
    tv_metadata: Optional[dict],
) -> Tuple[str, str]:
    terminal = (log_terminal_state or "").upper()
    tv_volume_changed = _normalize_bool((observations or {}).get("tv_volume_changed"))
    tv_osd_seen = _normalize_bool((observations or {}).get("tv_osd_seen"))
    pairing_screen_seen = _normalize_bool((observations or {}).get("pairing_screen_seen"))
    tv_brand_ui = _clean_str((observations or {}).get("tv_brand_ui"))
    tester_brand = _clean_str((observations or {}).get("tester_brand"))
    notes = _clean_str((observations or {}).get("notes"))

    probe_source = _clean_str((volume_probe or {}).get("volume_source"))
    probe_source_upper = (probe_source or "").upper()
    probe_confidence = _safe_float((volume_probe or {}).get("confidence"))

    tv_brand_logs = _clean_str((tv_metadata or {}).get("tv_brand_logs"))
    tv_model_logs = _clean_str((tv_metadata or {}).get("tv_model_logs"))

    def _failure_summary() -> str:
        reasons: List[str] = []
        if isinstance(log_state, dict):
            failures = log_state.get("matched_failure") or log_state.get("matched_failures")
            if isinstance(failures, list):
                reasons = [str(item) for item in failures if item]
        if reasons:
            return f"TV_AUTO_SYNC failed: {', '.join(reasons)}."
        return "TV_AUTO_SYNC failed: QuickSet logs reported a failure state."

    if terminal == "FAILURE":
        summary = _failure_summary()
        summary = _append_brand_line(summary, tv_brand_ui, tv_brand_logs, tester_brand, tv_model_logs)
        return "fail", summary

    pass_conditions = all(flag is True for flag in (tv_volume_changed, tv_osd_seen, pairing_screen_seen))
    probe_tv = probe_source_upper == "TV" and probe_confidence >= 0.7

    if terminal == "SUCCESS" and probe_tv and pass_conditions:
        summary = (
            "TV_AUTO_SYNC succeeded: logs show a full scan/pairing sequence,"
            " volume probe detected control on the TV, and the tester confirmed TV volume, TV OSD,"
            " and the pairing screen."
        )
        if tv_brand_ui and tv_brand_logs and tv_brand_ui.lower() != tv_brand_logs.lower():
            summary += f" Note: UI brand '{tv_brand_ui}' does not match logs brand '{tv_brand_logs}'."
        elif tv_brand_ui:
            summary += f" Detected TV brand: {tv_brand_ui}."
        elif tv_brand_logs:
            summary += f" Detected TV brand from logs: {tv_brand_logs}."
        if notes:
            summary += f" Tester notes: {notes}."
        summary = _append_brand_line(summary, tv_brand_ui, tv_brand_logs, tester_brand, tv_model_logs)
        return "pass", summary

    # Probe disagrees while tester reported positives
    tester_positive = any(flag is True for flag in (tv_volume_changed, tv_osd_seen, pairing_screen_seen))
    if probe_source_upper and probe_source_upper != "TV" and probe_confidence >= 0.7 and tester_positive:
        summary = (
            "TV_AUTO_SYNC failed: volume probe indicates control remained on the "
            f"{probe_source_upper} despite positive tester observations."
        )
        summary = _append_brand_line(summary, tv_brand_ui, tv_brand_logs, tester_brand, tv_model_logs)
        return "fail", summary

    if terminal == "SUCCESS":
        summary = (
            "QuickSet logs reported a successful sequence, but tester observations or probe results were"
            " insufficient to confirm TV control."
        )
        summary = _append_brand_line(summary, tv_brand_ui, tv_brand_logs, tester_brand, tv_model_logs)
        return "inconclusive", summary

    summary = (
        "Not enough evidence from logs, probe, or tester observations to decide."
        " Please review the captured logs and observations manually."
    )
    summary = _append_brand_line(summary, tv_brand_ui, tv_brand_logs, tester_brand, tv_model_logs)
    return "inconclusive", summary


def _append_brand_line(
    summary: str,
    ui_brand: Optional[str],
    logs_brand: Optional[str],
    tester_brand: Optional[str],
    logs_model: Optional[str],
) -> str:
    ui_value = ui_brand or "N/A"
    logs_value = logs_brand or logs_model or "N/A"
    tester_value = tester_brand or "N/A"
    brand_line = (
        f"TV brand/model: UI='{ui_value}' • Logs='{logs_value}' • Tester='{tester_value}'."
    )
    summary = f"{summary} {brand_line}".strip()
    if ui_brand and logs_brand and ui_brand.lower() != logs_brand.lower():
        summary = f"{summary} Note: brand mismatch (UI vs Logs)."
    return summary
