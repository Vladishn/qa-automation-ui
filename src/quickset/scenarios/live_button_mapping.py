from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

from src.qa.step_logger import StepLogger

QuestionCallback = Callable[[str, str], str]

YES_VALUES = {"yes", "y", "true", "1", "כן"}
NO_VALUES = {"no", "n", "false", "0", "לא"}


class LiveButtonMappingScenario:
    """Collects tester observations while capturing logs for the Live button mapping test."""

    def __init__(
        self,
        adb_client: Any,
        step_logger: StepLogger,
        raw_log_dir: Path,
        session_id: str,
    ) -> None:
        self.adb_client = adb_client
        self.step_logger = step_logger
        self.session_id = session_id
        self.raw_log_dir = Path(raw_log_dir)
        self.raw_log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.raw_log_dir / f"{self.session_id}_live_button_mapping.log"

    def _safe_int(self, value: str, default: int = 3) -> int:
        try:
            parsed = int(value.strip())
            return parsed if parsed > 0 else default
        except (ValueError, AttributeError):
            return default

    def _normalize_bool(self, value: str) -> bool | None:
        if not value:
            return None
        normalized = value.strip().lower()
        if normalized in YES_VALUES:
            return True
        if normalized in NO_VALUES:
            return False
        return None

    def run(self, ask: QuestionCallback) -> Dict[str, Any]:
        observations: Dict[str, Any] = {}
        analysis_text = "Live button mapping session completed."

        self.step_logger.log_step(
            "logcat_capture_start",
            "INFO",
            {"log_path": str(self.log_path), "tester_visible": False},
        )
        try:
            self.adb_client.start_logcat_capture(self.log_path)
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Failed to start logcat capture: {exc}"
            self.step_logger.log_step("logcat_capture_start", "FAIL", {"error": error_msg})
            return {
                "scenario_id": "LIVE_BUTTON_MAPPING",
                "title": "Live Button Mapping",
                "status": "FAIL",
                "analysis": error_msg,
                "tester_observations": observations,
            }

        expected_prompt = "Which channel should the Live button jump to? (Default: 3)"
        expected_answer = ask("expected_channel", expected_prompt)
        expected_channel = self._safe_int(expected_answer or "", default=3)
        observations["expected_channel"] = expected_channel
        self.step_logger.log_step(
            "live_expected_channel",
            "INFO",
            {"expected_channel": expected_channel, "tester_visible": False},
        )

        manual_prompt = (
            "Press the Live button on the remote once now. Wait for PartnerTV+ to open, "
            "then press Enter here."
        )
        ask("manual_trigger_live", manual_prompt)
        self.step_logger.log_step(
            "live_manual_trigger_ack",
            "INFO",
            {"tester_visible": False},
        )

        behavior_prompt = "Did the Live button open PartnerTV+ on the expected channel? (yes/no)"
        behavior_answer = ask("live_behavior_observed", behavior_prompt)
        normalized_behavior = self._normalize_bool(behavior_answer or "")
        observations["tester_live_ok"] = normalized_behavior

        try:
            self.adb_client.stop_logcat_capture()
            self.step_logger.log_step(
                "logcat_capture_stop",
                "PASS",
                {"log_path": str(self.log_path), "tester_visible": False},
            )
        except Exception as exc:  # noqa: BLE001
            self.step_logger.log_step("logcat_capture_stop", "FAIL", {"error": str(exc)})

        self.step_logger.log_step(
            "analysis_summary",
            "INFO",
            {"analysis": analysis_text, "tester_visible": False},
        )

        return {
            "scenario_id": "LIVE_BUTTON_MAPPING",
            "title": "Live Button Mapping",
            "status": "PASS",
            "analysis": analysis_text,
            "tester_observations": observations,
        }
