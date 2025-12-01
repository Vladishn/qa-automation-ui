"""Scenario that pairs and unpairs a remote via QuickSet."""

from __future__ import annotations

from typing import Any, Dict

from src.adb.adb_client import ADBClient, ADBError
from src.qa.step_logger import StepLogger


class RemotePairUnpairScenario:
    """Validate the remote pairing flow followed by an unpair step."""

    name = "remote_pair_unpair"

    def __init__(self, adb_client: ADBClient, logger: StepLogger) -> None:
        self.adb = adb_client
        self.logger = logger

    def run(self) -> Dict[str, Any]:
        """Execute the pair/unpair sequence."""
        self.logger.log_step("check_connection", "INFO", {"target": self.adb.target})
        try:
            self.adb.ensure_connected()
            self.logger.log_step("check_connection", "PASS", {"target": self.adb.target})
        except ADBError as exc:
            self.logger.log_step("check_connection", "FAIL", {"error": str(exc)})
            return {"status": "FAIL", "details": {"error": str(exc)}}

        try:
            pair_output = self.adb.run_shell("am broadcast -a quickset.intent.PAIR_REMOTE")
            self.logger.log_step("pair_remote", "PASS", {"output": pair_output})
            unpair_output = self.adb.run_shell("am broadcast -a quickset.intent.UNPAIR_REMOTE")
            self.logger.log_step("unpair_remote", "PASS", {"output": unpair_output})
            return {"status": "PASS", "details": {"message": "Remote paired and unpaired."}}
        except ADBError as exc:
            self.logger.log_step("remote_pair_unpair", "FAIL", {"error": str(exc)})
            return {"status": "FAIL", "details": {"error": str(exc)}}
