# File: src/adb/adb_client.py
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional


class ADBError(RuntimeError):
    """Raised when an ADB operation fails."""


class ADBClient:
    """
    Thin wrapper around the adb binary that:
    - Ensures the server is running.
    - Normalizes the target (adds :5555 if missing).
    - Tries adb connect + verifies via adb devices.
    - Provides logcat capture helpers.

    This is designed so that QA testers only need to run:
        python -m src.cli run --session-id ... --stb-ip 192.168.1.200 --scenario TV_AUTO_SYNC

    and the ADB connectivity will be handled automatically per run,
    even when working with multiple STBs or on different machines.
    """

    def __init__(
        self,
        target: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        adb_path: str = "adb",
    ) -> None:
        """
        :param target: IP or IP:PORT of the STB, e.g. '192.168.1.200' or '192.168.1.200:5555'
        :param max_retries: how many times to retry adb connect
        :param retry_delay: delay (seconds) between retries
        :param adb_path: path to adb binary
        """
        self.raw_target = target.strip()
        self.target = self._normalize_target(self.raw_target)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.adb_path = adb_path
        self._logcat_proc: Optional[subprocess.Popen] = None

    # ----------------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------------
    @staticmethod
    def _normalize_target(target: str) -> str:
        """
        Normalize target:
        - If it already has ':', assume it's IP:PORT and return as-is.
        - Otherwise, append ':5555' as the default TCP port.
        """
        if ":" in target:
            return target
        return f"{target}:5555"

    def _run_adb(self, *args: str, check: bool = False) -> subprocess.CompletedProcess:
        """
        Run an adb command and return the CompletedProcess.
        Raises ADBError if check=True and returncode != 0.
        """
        cmd = [self.adb_path, *args]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ADBError(
                f"adb binary not found when running: {' '.join(cmd)}; "
                "ensure Android platform-tools are installed and adb is in PATH."
            ) from exc

        if check and proc.returncode != 0:
            raise ADBError(
                f"ADB command failed: {' '.join(cmd)}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}\n"
            )
        return proc

    def _ensure_server_running(self) -> None:
        """
        Ensure ADB server is running. This is idempotent and safe to call often.
        """
        # 'adb start-server' will start the daemon if needed; otherwise it is a no-op.
        self._run_adb("start-server", check=True)

    def _parse_devices_output(self, output: str) -> dict[str, str]:
        """
        Parse 'adb devices' output into a {serial: status} dict.
        """
        devices: dict[str, str] = {}
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices attached"):
                continue
            # Expected format: "<serial>\t<state>"
            parts = line.split()
            if len(parts) >= 2:
                serial, state = parts[0], parts[1]
                devices[serial] = state
        return devices

    def _connect_once(self) -> tuple[bool, str]:
        """
        Attempt a single adb connect to the normalized target.
        Returns (success, debug_message).
        """
        proc = self._run_adb("connect", self.target, check=False)
        out = (proc.stdout or "") + (proc.stderr or "")
        out = out.strip()
        if "connected to" in out or "already connected" in out:
            return True, out
        # Not a hard decision here yet; we will re-check via adb devices anyway.
        return proc.returncode == 0, out

    def _check_device_state(self) -> str:
        """
        Run 'adb devices' and return the state for self.target if present,
        or empty string if not present.
        """
        proc = self._run_adb("devices", check=False)
        devices = self._parse_devices_output(proc.stdout or "")
        # adb devices will show the serial as "<ip>:<port>"
        return devices.get(self.target, "")

    # ----------------------------------------------------------------------
    # Public API used by the rest of the project
    # ----------------------------------------------------------------------
    def ensure_connected(self) -> None:
        """
        Ensure that:
        - ADB server is running.
        - adb connect <target> was attempted.
        - 'adb devices' shows <target> in 'device' state.

        This method will:
        - Retry a few times.
        - Raise ADBError with a clear message if it cannot reach 'device' state.
        """
        self._ensure_server_running()

        last_msg = ""
        for attempt in range(1, self.max_retries + 1):
            ok, msg = self._connect_once()
            last_msg = msg
            # Give adb a moment to update internal state
            time.sleep(0.5)
            state = self._check_device_state()

            if state == "device":
                # We're good.
                return

            if state == "unauthorized":
                raise ADBError(
                    f"ADB target {self.target} is 'unauthorized'. "
                    "Please confirm the RSA/ADB dialog on the STB screen and select "
                    "'Always allow', then rerun the test."
                )

            # If state is 'offline' or empty, we can retry
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
                continue

        # If we got here, we never reached 'device' state.
        raise ADBError(
            f"Failed to connect to STB over ADB at {self.target} after "
            f"{self.max_retries} attempts.\n"
            f"Last adb connect output:\n{last_msg or '[no output]'}\n"
            "Make sure:\n"
            "  - The STB is powered on and on the same network.\n"
            "  - ADB over network is enabled in Developer options.\n"
            "  - No firewall blocks TCP port 5555.\n"
        )

    def start_logcat_capture(self, log_path: Path) -> subprocess.Popen:
        """
        Start a logcat capture for this target into the given file.
        Returns the Popen process handle.

        The caller is responsible for terminating this process (or calling stop_logcat_capture()).
        """
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Use -v time for stable timestamps; adjust as needed.
        cmd = [self.adb_path, "-s", self.target, "logcat", "-v", "time"]
        # Open the file and stream logcat output into it
        log_file = open(log_path, "w", encoding="utf-8", errors="ignore")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._logcat_proc = proc
        return proc

    def stop_logcat_capture(self) -> None:
        """
        Stop an ongoing logcat capture if started via start_logcat_capture.
        """
        if self._logcat_proc is None:
            return
        if self._logcat_proc.poll() is None:
            # Still running; try to terminate
            self._logcat_proc.terminate()
            try:
                self._logcat_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._logcat_proc.kill()
        self._logcat_proc = None

    # Optional helper for generic shell commands, in case scenarios need it:
    def shell(self, command: str, check: bool = True) -> str:
        """
        Run 'adb -s <target> shell <command>' and return stdout.
        """
        proc = self._run_adb("-s", self.target, "shell", command, check=check)
        return proc.stdout or ""
