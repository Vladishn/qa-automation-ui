from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def analyze_quickset_logs(log_path: Path, logs_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze QuickSet-related logcat output for TV_AUTO_SYNC.

    :param log_path: Path to the captured logcat text file.
    :param logs_cfg: "logs" section from the scenario knowledge (required_tags, success_patterns, failure_patterns).
    :return: Dict with basic analysis: matched patterns, status, etc.
    """
    if not log_path.exists():
        return {
            "log_path": str(log_path),
            "status": "missing",
            "matched_success_patterns": [],
            "matched_failure_patterns": [],
            "has_required_tags": False,
            "lines_checked": 0,
        }

    required_tags: List[str] = list(logs_cfg.get("required_tags", []))
    success_patterns: List[str] = list(logs_cfg.get("success_patterns", []))
    failure_patterns: List[str] = list(logs_cfg.get("failure_patterns", []))

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    lines_lower = [line.lower() for line in lines]

    def any_in_lines(pattern: str) -> bool:
        p = pattern.lower()
        return any(p in line for line in lines_lower)

    matched_success = [p for p in success_patterns if any_in_lines(p)]
    matched_failure = [p for p in failure_patterns if any_in_lines(p)]

    has_required_tags = all(any_in_lines(tag) for tag in required_tags) if required_tags else True

    if matched_failure:
        status = "failure"
    elif matched_success:
        status = "success"
    else:
        status = "unknown"

    return {
        "log_path": str(log_path),
        "status": status,
        "matched_success_patterns": matched_success,
        "matched_failure_patterns": matched_failure,
        "has_required_tags": has_required_tags,
        "lines_checked": len(lines),
    }
