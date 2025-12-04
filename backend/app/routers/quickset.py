"""QuickSet scenario execution endpoints wired to TvAutoSyncScenario."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from ..adb_service import AdbPrecheckResult, AdbPrecheckStatus, precheck
from ..config import settings
from ..models import (
    QuickSetInfraCheck,
    QuickSetQuestion,
    QuickSetSession,
    QuickSetStep,
)
from ..storage import quickset_session_store

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.adb.adb_client import ADBClient  # noqa: E402
from src.qa.step_logger import StepLogger  # noqa: E402
from src.quickset.scenarios.tv_auto_sync import TvAutoSyncScenario  # noqa: E402

RAW_LOG_DIR = PROJECT_ROOT / "artifacts" / "quickset_logs"
STEP_LOG_DIR = Path(settings.quickset_steps_dir)
KNOWLEDGE_PATH = PROJECT_ROOT / "knowledge" / "scenarios" / "tv_auto_sync.yaml"

RAW_LOG_DIR.mkdir(parents=True, exist_ok=True)
STEP_LOG_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/quickset", tags=["quickset"])

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QuickSet session not found")
    return compute_session_decision(session)


@router.post("/sessions/{session_id}/answer", response_model=QuickSetSession)
def answer_question(
    session_id: str,
    payload: QuickSetAnswer,
    api_key: str = Depends(require_api_key),
) -> QuickSetSession:
    session = quickset_session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QuickSet session not found")
    if session.pending_question is None or session.state != "awaiting_input":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not awaiting input")

    quickset_session_store.deliver_answer(session_id, payload.answer)
    updated = quickset_session_store.get_session(session_id)
    return compute_session_decision(updated if updated else session)


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


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


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


def compute_session_decision(session: QuickSetSession) -> QuickSetSession:
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
    session: QuickSetSession,
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
