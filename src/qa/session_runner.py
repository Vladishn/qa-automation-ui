# File: src/qa/session_runner.py
"""Session orchestration without CLI side effects."""

from __future__ import annotations

import time
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Dict, Tuple, Optional

from src.adb.adb_client import ADBClient, ADBError
from src.qa.step_logger import StepLogger


class ScenarioLoadError(RuntimeError):
    """Raised when the requested scenario cannot be imported or instantiated."""


class SessionRunner:
    """Runs a single scenario and returns structured results."""

    SCENARIO_CLASS_MAP: Dict[str, Tuple[str, str]] = {
        "tv_auto_sync": ("src.quickset.scenarios.tv_auto_sync", "TvAutoSyncScenario"),
        "battery_status": ("src.quickset.scenarios.battery_status", "BatteryStatusScenario"),
        "remote_pair_unpair": (
            "src.quickset.scenarios.remote_pair_unpair",
            "RemotePairUnpairScenario",
        ),
        "live_button_mapping": (
            "src.quickset.scenarios.live_button_mapping",
            "LiveButtonMappingScenario",
        ),
    }

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.logs_root = self.project_root / "logs"
        self.raw_log_dir = self.logs_root / "raw_logcat"
        self.session_log_dir = self.logs_root / "sessions"
        self.reports_dir = self.logs_root / "reports"
        self.knowledge_dir = self.project_root / "knowledge"
        self.tv_auto_sync_knowledge = self.knowledge_dir / "quickset_tv_auto_sync.yaml"

        for path in (self.raw_log_dir, self.session_log_dir, self.reports_dir):
            path.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _normalize_scenario_name(name: str) -> str:
        """Normalize incoming scenario identifiers to lowercase snake_case."""
        sanitized = name.strip().lower()
        return sanitized.replace("-", "_").replace(" ", "_")

    def _build_question_callback(self) -> Callable[[str, str], str]:
        """Return a CLI-agnostic question callback used by interactive scenarios."""

        def ask(question_id: str, prompt: str) -> str:
            try:
                return input(f"[{question_id}] {prompt}\n> ")
            except KeyboardInterrupt:  # pragma: no cover
                return ""

        return ask

    def _build_scenario(
        self,
        scenario_name: str,
        adb: ADBClient,
        logger: StepLogger,
        session_id: str,
    ):
        """Instantiate the requested scenario class based on the registry."""
        try:
            module_name, class_name = self.SCENARIO_CLASS_MAP[scenario_name]
        except KeyError as exc:
            raise ScenarioLoadError(f"Scenario '{scenario_name}' is not registered.") from exc

        module = import_module(module_name)
        scenario_cls = getattr(module, class_name, None)
        if scenario_cls is None:
            raise ScenarioLoadError(
                f"Scenario class '{class_name}' missing in module '{module_name}'."
            )

        if scenario_name == "tv_auto_sync":
            return scenario_cls(
                adb,
                logger,
                knowledge_path=self.tv_auto_sync_knowledge,
                raw_log_dir=self.raw_log_dir,
                session_id=session_id,
            )
        if scenario_name == "live_button_mapping":
            return scenario_cls(
                adb,
                logger,
                raw_log_dir=self.raw_log_dir,
                session_id=session_id,
            )

        # Default: simple ctor (adb, logger)
        return scenario_cls(adb, logger)

    @staticmethod
    def _build_friendly_adb_message(
        target: str,
        session_id: str,
        scenario: str,
        error_msg: str,
    ) -> str:
        """
        Build a human-friendly explanation for ADB connection failures
        that can be shown directly in the CLI and stored in logs.
        """
        target = target or "unknown"

        error_msg = (error_msg or "").strip()
        if not error_msg:
            error_msg = "No additional error details reported by adb."

        friendly_msg = (
            f"Unable to establish ADB connection to the STB at {target}.\n\n"
            f"Details:\n"
            f"{error_msg}\n\n"
            "Possible causes:\n"
            "- The STB is reachable by ping, but ADB over network is disabled.\n"
            "- Developer Options → 'ADB over network' is OFF.\n"
            "- Another tester/computer is already connected and blocking the session.\n"
            "- A firewall or router is blocking TCP port 5555.\n"
            "- The STB showed an ADB RSA authorization popup that wasn't approved.\n\n"
            "Recommended actions:\n"
            "1. On the STB: enable Developer Options → ADB over network.\n"
            "2. Approve the RSA dialog (select 'Always allow').\n"
            "3. On your machine: run 'adb kill-server' then 'adb start-server'.\n"
            "4. If multiple machines/testers are connected: disconnect old sessions.\n\n"
            "After fixing the issue, rerun the command:\n"
            f"python -m src.cli run --session-id {session_id} --stb-ip {target} --scenario {scenario.upper()}"
        )
        return friendly_msg

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def run(self, session_id: str, stb_ip: str, scenario_name: str) -> Dict[str, Any]:
        """Execute a scenario and return structured results without printing."""
        normalized_scenario = self._normalize_scenario_name(scenario_name)
        logger = StepLogger(session_id, self.session_log_dir)
        adb = ADBClient(target=stb_ip)
        raw_log_path = self.raw_log_dir / f"{session_id}_{normalized_scenario}.log"

        start_ts = time.time()
        try:
            # -----------------------------------------------------------------
            # 1) Ensure ADB connectivity for ALL scenarios (not only TV_AUTO_SYNC)
            # -----------------------------------------------------------------
            try:
                logger.log_step(
                    "adb_precheck",
                    "INFO",
                    {"message": "Ensuring ADB connection to STB.", "target": adb.target},
                )
                adb.ensure_connected()
                logger.log_step(
                    "adb_precheck",
                    "PASS",
                    {"message": "ADB connection established.", "target": adb.target},
                )
            except ADBError as exc:
                friendly_msg = self._build_friendly_adb_message(
                    target=getattr(adb, "target", stb_ip),
                    session_id=session_id,
                    scenario=normalized_scenario,
                    error_msg=str(exc),
                )
                logger.log_step("adb_precheck", "FAIL", {"error": friendly_msg})

                return {
                    "session_id": session_id,
                    "scenario": normalized_scenario,
                    "status": "FAIL",
                    "result": {
                        "scenario_id": normalized_scenario.upper(),
                        "title": normalized_scenario.replace("_", " ").title(),
                        "status": "FAIL",
                        "root_cause_category": "ADB_CONNECTION_FAILED",
                        "analysis": friendly_msg,
                        "auto_evidence": {"error": friendly_msg},
                        "tester_observations": {},
                    },
                    "session_log_path": logger.log_path,
                    "raw_log_path": raw_log_path,
                    "duration_seconds": time.time() - start_ts,
                }
            except Exception as exc:  # noqa: BLE001
                # Catch any unexpected exception and surface it as a friendly ADB failure.
                friendly_msg = self._build_friendly_adb_message(
                    target=getattr(adb, "target", stb_ip),
                    session_id=session_id,
                    scenario=normalized_scenario,
                    error_msg=str(exc),
                )
                logger.log_step("adb_precheck", "FAIL", {"error": friendly_msg})

                return {
                    "session_id": session_id,
                    "scenario": normalized_scenario,
                    "status": "FAIL",
                    "result": {
                        "scenario_id": normalized_scenario.upper(),
                        "title": normalized_scenario.replace("_", " ").title(),
                        "status": "FAIL",
                        "root_cause_category": "ADB_CONNECTION_FAILED",
                        "analysis": friendly_msg,
                        "auto_evidence": {"error": friendly_msg},
                        "tester_observations": {},
                    },
                    "session_log_path": logger.log_path,
                    "raw_log_path": raw_log_path,
                    "duration_seconds": time.time() - start_ts,
                }

            # -----------------------------------------------------------------
            # 2) Build scenario instance
            # -----------------------------------------------------------------
            try:
                scenario = self._build_scenario(
                    normalized_scenario,
                    adb,
                    logger,
                    session_id,
                )
            except ScenarioLoadError as exc:
                logger.log_step("scenario_load", "FAIL", {"error": str(exc)})
                return {
                    "session_id": session_id,
                    "scenario": normalized_scenario,
                    "status": "FAIL",
                    "result": {
                        "scenario_id": normalized_scenario.upper(),
                        "title": normalized_scenario.replace("_", " ").title(),
                        "status": "FAIL",
                        "root_cause_category": "SCENARIO_LOAD_FAILED",
                        "analysis": str(exc),
                    },
                    "session_log_path": logger.log_path,
                    "raw_log_path": raw_log_path,
                    "duration_seconds": time.time() - start_ts,
                }

            # tv_auto_sync scenario manages logcat on its own
            scenario_manages_logcat = normalized_scenario == "tv_auto_sync"
            logcat_proc: Optional[Any] = None

            # -----------------------------------------------------------------
            # 3) Start logcat capture for scenarios that don't manage it internally
            # -----------------------------------------------------------------
            if not scenario_manages_logcat:
                try:
                    logcat_proc = adb.start_logcat_capture(raw_log_path)
                    logger.log_step(
                        "logcat_capture_start",
                        "INFO",
                        {"path": str(raw_log_path)},
                    )
                except ADBError as exc:
                    logger.log_step("logcat_capture_start", "FAIL", {"error": str(exc)})

            # -----------------------------------------------------------------
            # 4) Run scenario
            # -----------------------------------------------------------------
            logger.log_step(
                "session_start",
                "INFO",
                {"scenario": normalized_scenario, "stb_ip": stb_ip},
            )

            try:
                if normalized_scenario == "tv_auto_sync":
                    question_cb = self._build_question_callback()
                    scenario_result = scenario.run(question_cb)
                else:
                    scenario_result = scenario.run()
            except Exception as exc:  # noqa: BLE001
                scenario_result = {
                    "scenario_id": normalized_scenario.upper(),
                    "title": normalized_scenario.replace("_", " ").title(),
                    "status": "FAIL",
                    "root_cause_category": "EXCEPTION",
                    "analysis": str(exc),
                }
                logger.log_step("scenario_exception", "FAIL", {"error": str(exc)})

            status = scenario_result.get("status", "UNKNOWN")
            logger.log_step("session_end", status, {"scenario": normalized_scenario})

            # -----------------------------------------------------------------
            # 5) Stop logcat capture if we started it
            # -----------------------------------------------------------------
            if not scenario_manages_logcat and logcat_proc is not None and logcat_proc.poll() is None:
                logcat_proc.terminate()

            # -----------------------------------------------------------------
            # 6) Return structured session result
            # -----------------------------------------------------------------
            return {
                "session_id": session_id,
                "scenario": normalized_scenario,
                "status": status,
                "result": scenario_result,
                "session_log_path": logger.log_path,
                "raw_log_path": raw_log_path,
                "duration_seconds": time.time() - start_ts,
            }
        finally:
            logger.close()
