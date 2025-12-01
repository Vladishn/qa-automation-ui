from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class StepLogger:
    """
    Writes QA steps to a JSONL file (one JSON object per line) for a given session.
    """

    def __init__(self, session_id: str, output_dir: Path | str) -> None:
        self.session_id = session_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self.output_dir / f"{self.session_id}.jsonl"
        self._fh = self._log_path.open("a", encoding="utf-8")

    @property
    def log_path(self) -> Path:
        """Return the path to the JSONL log file."""
        return self._log_path

    # Backward-compatible alias
    @property
    def file_path(self) -> Path:
        return self._log_path

    def log_step(
        self,
        step_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log a single step for the session.
        :param step_name: Human-readable step name.
        :param status: PASS / FAIL / INFO / ERROR / WARNING.
        :param details: Optional extra data (dict).
        """
        record = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "session_id": self.session_id,
            "step_name": step_name,
            "status": status,
            "details": details or {},
        }
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if hasattr(self, "_fh") and not self._fh.closed:
            self._fh.close()
