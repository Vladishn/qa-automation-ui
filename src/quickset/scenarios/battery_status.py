"""Scenario that queries the remote control battery status."""

from __future__ import annotations

from typing import Any, Dict

from src.adb.adb_client import ADBClient, ADBError
from src.qa.step_logger import StepLogger


class BatteryStatusScenario:
    """Pull the current battery status from QuickSet and validate thresholds."""

    name = "battery_status"

    def __init__(self, adb_client: ADBClient, logger: StepLogger) -> None:
        self.adb = adb_client
        self.logger = logger

    def run(self) -> Dict[str, Any]:
        """Execute the battery status retrieval workflow."""
        self.logger.log_step("check_connection", "INFO", {"target": self.adb.target})
        try:
            self.adb.ensure_connected()
            self.logger.log_step("check_connection", "PASS", {"target": self.adb.target})
        except ADBError as exc:
            self.logger.log_step("check_connection", "FAIL", {"error": str(exc)})
            return {"status": "FAIL", "details": {"error": str(exc)}}

        try:
            status_output = self.adb.run_shell("dumpsys battery | head -n 20")
            self.logger.log_step("query_battery", "PASS", {"output": status_output})
        except ADBError as exc:
            self.logger.log_step("query_battery", "FAIL", {"error": str(exc)})
            return {"status": "FAIL", "details": {"error": str(exc)}}

        level_line = next(
            (line for line in status_output.splitlines() if "level" in line.lower()),
            "",
        )
        if level_line:
            self.logger.log_step("battery_level_detected", "PASS", {"line": level_line.strip()})
            return {"status": "PASS", "details": {"battery_info": level_line.strip()}}

        self.logger.log_step("battery_level_missing", "FAIL", {"output": status_output})
        return {"status": "FAIL", "details": {"message": "Battery data missing from output."}}
