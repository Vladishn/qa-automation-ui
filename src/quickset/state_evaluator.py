from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any

import yaml


def load_state_machine() -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "knowledge" / "states" / "tv_auto_sync_states.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def evaluate_states(matched_signatures: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Infer a terminal state based on matched signatures.
    Priority: FAILURE > SUCCESS > INCONCLUSIVE.
    """
    success_ids = {m["id"] for m in matched_signatures if m.get("category") == "SUCCESS"}
    failure_ids = {
        m["id"]
        for m in matched_signatures
        if m.get("category") not in ("SUCCESS", "INFO")
    }

    if failure_ids:
        terminal = "FAILURE"
    elif success_ids:
        terminal = "SUCCESS"
    else:
        terminal = "INCONCLUSIVE"

    return {
        "terminal_state": terminal,
        "matched_success": list(success_ids),
        "matched_failure": list(failure_ids),
    }
