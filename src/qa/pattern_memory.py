# File: src/qa/pattern_memory.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

MEMORY_RELATIVE_PATH = Path("logs/analytics/pattern_memory.json")


def _ensure_memory_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"entries": []}, indent=2), encoding="utf-8")


def load_pattern_memory(project_root: Path) -> Dict[str, Any]:
    memory_path = (project_root / MEMORY_RELATIVE_PATH).resolve()
    _ensure_memory_file(memory_path)
    try:
        with memory_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict) or "entries" not in data:
                raise ValueError("Invalid pattern memory structure")
            if not isinstance(data["entries"], list):
                raise ValueError("Pattern memory entries must be a list")
            return data
    except Exception:
        return {"entries": []}


def append_pattern_entry(project_root: Path, entry: Dict[str, Any]) -> Dict[str, Any]:
    memory_path = (project_root / MEMORY_RELATIVE_PATH).resolve()
    _ensure_memory_file(memory_path)

    data = load_pattern_memory(project_root)
    entries = data.get("entries", [])
    entries.append(entry)
    data["entries"] = entries
    with memory_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return data


def build_historical_summary(
    memory: Dict[str, Any],
    scenario_id: str,
    stb_target: Optional[str] = None,
    tv_brand_ui: Optional[str] = None,
) -> Dict[str, Any]:
    entries = memory.get("entries", [])
    scenario_entries = [e for e in entries if e.get("scenario_id") == scenario_id]

    total_runs = len(scenario_entries)
    total_failures = sum(1 for e in scenario_entries if e.get("status") == "FAIL")

    root_cause_counts: Dict[str, int] = {}
    sig_counts: Dict[str, int] = {}
    for entry in scenario_entries:
        root = entry.get("root_cause_category", "UNKNOWN")
        root_cause_counts[root] = root_cause_counts.get(root, 0) + 1
        for sig_id in entry.get("matched_signatures", []) or []:
            sig_counts[sig_id] = sig_counts.get(sig_id, 0) + 1

    stb_entries = scenario_entries
    if stb_target:
        stb_entries = [e for e in stb_entries if e.get("stb_target") == stb_target]
    runs_for_stb = len(stb_entries)
    fails_for_stb = sum(1 for e in stb_entries if e.get("status") == "FAIL")

    brand_entries = scenario_entries
    if tv_brand_ui:
        brand_entries = [e for e in brand_entries if e.get("tv_brand_ui") == tv_brand_ui]

    return {
        "scenario_id": scenario_id,
        "total_runs_for_scenario": total_runs,
        "total_failures_for_scenario": total_failures,
        "root_cause_counts": root_cause_counts,
        "signature_counts": sig_counts,
        "runs_for_this_stb": runs_for_stb,
        "failures_for_this_stb": fails_for_stb,
        "runs_for_this_brand_ui": len(brand_entries),
        "failures_for_this_brand_ui": sum(1 for e in brand_entries if e.get("status") == "FAIL"),
    }


def build_pattern_entry(
    session_id: str,
    scenario_id: str,
    stb_target: str,
    status: str,
    root_cause_category: str,
    matched_signatures: List[str],
    tv_brand_ui: Optional[str] = None,
    tv_brand_logs: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp": timestamp,
        "scenario_id": scenario_id,
        "session_id": session_id,
        "stb_target": stb_target,
        "status": status,
        "root_cause_category": root_cause_category,
        "matched_signatures": matched_signatures,
        "tv_brand_ui": tv_brand_ui,
        "tv_brand_logs": tv_brand_logs,
    }
