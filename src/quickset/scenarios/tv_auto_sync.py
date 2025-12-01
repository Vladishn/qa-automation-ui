# File: src/quickset/scenarios/tv_auto_sync.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

import yaml  # make sure PyYAML is in requirements.txt

from src.qa.step_logger import StepLogger
from src.quickset.log_analyzer import analyze_quickset_logs
from src.quickset.log_signature_matcher import match_signatures
from src.quickset.reasoning_engine import reason_autosync
from src.quickset.state_evaluator import evaluate_states
from src.quickset.state_snapshot import capture_quickset_state, diff_quickset_state
from src.quickset.tv_metadata_extractor import extract_tv_metadata_from_log
from src.quickset.volume_behavior_probe import VolumeBehaviorProbe

QuestionCallback = Callable[[str, str], str]


class TvAutoSyncScenario:
    """Knowledge-driven implementation of the TV Auto Sync flow."""

    def __init__(
        self,
        adb_client: Any,
        step_logger: StepLogger,
        knowledge_path: Path,
        raw_log_dir: Path,
        session_id: str,
        knowledge_root: Path | None = None,
    ) -> None:
        self.name = "tv_auto_sync"
        self.adb_client = adb_client
        self.step_logger = step_logger
        self.knowledge_path = knowledge_path
        self.knowledge_root = knowledge_root or knowledge_path.parent.parent
        self.raw_log_dir = raw_log_dir
        self.session_id = session_id
        self.knowledge: Dict[str, Any] = self._load_knowledge()
        self._logs_cfg: Dict[str, Any] = self.knowledge.get("expected_outcomes", {}).get("logs", {})

    def _load_knowledge(self) -> Dict[str, Any]:
        if not self.knowledge_path.exists():
            raise FileNotFoundError(f"Knowledge file not found: {self.knowledge_path}")
        with self.knowledge_path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh.read()) or {}

    def _ask_tester_questions(self, ask: QuestionCallback) -> Dict[str, Any]:
        observations: Dict[str, Any] = {}
        for question in self.knowledge.get("tester_questions", []):
            q_id = question.get("id")
            q_text = question.get("text", "")
            q_type = question.get("type", "text")
            if not q_id or not q_text:
                continue
            raw_answer = ask(q_id, q_text).strip()
            if q_type == "yes_no":
                normalized = raw_answer.lower()
                if normalized in ("yes", "y", "true", "t", "1", "כן"):
                    value: Any = True
                elif normalized in ("no", "n", "false", "f", "0", "לא"):
                    value = False
                else:
                    value = raw_answer
            else:
                value = raw_answer
            observations[q_id] = value
        return observations

    def run(self, ask: QuestionCallback) -> Dict[str, Any]:
        scenario_id = self.knowledge.get("scenario_id", "TV_AUTO_SYNC")
        title = self.knowledge.get("title", "TV Auto Sync")

        self.step_logger.log_step("adb_precheck", "INFO", {"message": "Checking ADB connection to STB."})
        try:
            self.adb_client.ensure_connected()
            self.step_logger.log_step("adb_precheck", "PASS", {"message": "ADB connection OK."})
        except Exception as exc:  # noqa: BLE001
            self.step_logger.log_step("adb_precheck", "FAIL", {"error": str(exc)})
            return {
                "scenario_id": scenario_id,
                "title": title,
                "status": "FAIL",
                "root_cause_category": "ADB_CONNECTION_FAILED",
                "auto_evidence": {"error": str(exc)},
                "tester_observations": {},
                "analysis": "Failed to connect to STB over ADB; cannot run TV_AUTO_SYNC scenario.",
            }

        state_before = capture_quickset_state(self.adb_client, self.step_logger, label="before_autosync")

        self.raw_log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.raw_log_dir / f"{self.session_id}_tv_auto_sync.log"
        self.step_logger.log_step("logcat_capture_start", "INFO", {"log_path": str(log_path)})
        try:
            self.adb_client.start_logcat_capture(log_path)
        except Exception as exc:  # noqa: BLE001
            self.step_logger.log_step("logcat_capture_start", "FAIL", {"error": str(exc)})
            return {
                "scenario_id": scenario_id,
                "title": title,
                "status": "FAIL",
                "root_cause_category": "LOG_CAPTURE_FAILED",
                "auto_evidence": {"error": str(exc)},
                "tester_observations": {},
                "analysis": "Could not start logcat capture; cannot analyze QuickSet behavior.",
            }

        instructions = (
            "Please run the TV Auto Sync flow now:\n"
            "- Settings > Remotes & Accessories > PartnerRC > TV pairing.\n"
            "- Wait for the scan/summary screen.\n"
            "Press Enter here when finished."
        )
        self.step_logger.log_step("tester_trigger_quickset", "INFO", {"instructions": instructions})
        _ = ask("manual_trigger", instructions)

        try:
            self.adb_client.stop_logcat_capture()
            self.step_logger.log_step("logcat_capture_stop", "PASS", {"log_path": str(log_path)})
        except Exception as exc:  # noqa: BLE001
            self.step_logger.log_step("logcat_capture_stop", "FAIL", {"error": str(exc)})

        self.step_logger.log_step("tester_questions", "INFO", {"message": "Collecting tester observations."})
        tester_observations = self._ask_tester_questions(ask)
        self.step_logger.log_step("tester_questions", "PASS", {"observations": tester_observations})

        self.step_logger.log_step("log_analysis_start", "INFO", {"log_path": str(log_path)})
        log_result = analyze_quickset_logs(log_path, self._logs_cfg)
        matched_signatures = match_signatures(log_path)
        state_eval = evaluate_states(matched_signatures)
        self.step_logger.log_step(
            "log_analysis_complete",
            "PASS",
            {"log_result": log_result, "matched_signatures": matched_signatures, "state": state_eval},
        )

        tv_meta = extract_tv_metadata_from_log(log_path)
        self.step_logger.log_step("tv_metadata", "INFO", tv_meta)

        probe = VolumeBehaviorProbe(self.adb_client, log_path, self.knowledge_root)
        volume_probe = probe.run_probe(self.step_logger, ask)
        if volume_probe.get("volume_source") == "TV":
            tester_observations["tv_volume_changed"] = True
            tester_observations["tv_osd_seen"] = True
        elif volume_probe.get("volume_source") == "STB":
            tester_observations["tv_volume_changed"] = False
            tester_observations["tv_osd_seen"] = False

        state_after = capture_quickset_state(self.adb_client, self.step_logger, label="after_autosync")
        state_diff = diff_quickset_state(state_before, state_after)

        scenario_result = reason_autosync(
            matched_signatures=matched_signatures,
            tester_observations=tester_observations,
            terminal_state=state_eval.get("terminal_state", "UNKNOWN"),
            tv_meta=tv_meta,
            volume_probe=volume_probe,
            state_before=state_before.data,
            state_after=state_after.data,
            state_diff=state_diff,
        )
        scenario_result["volume_probe"] = volume_probe
        return scenario_result
