from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any

import yaml


def load_signatures() -> List[Dict[str, Any]]:
    base = Path(__file__).resolve().parents[2] / "knowledge" / "signatures"
    success_path = base / "autosync_success.yaml"
    failure_path = base / "autosync_failure.yaml"
    signatures: List[Dict[str, Any]] = []
    for path in (success_path, failure_path):
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            signatures.extend(data.get("signatures", []))
    return signatures


def match_signatures(log_path: Path) -> List[Dict[str, Any]]:
    """Return list of matched signature dicts (id, category, severity, pattern)."""
    signatures = load_signatures()
    log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    matches: List[Dict[str, Any]] = []
    for sig in signatures:
        pattern = sig.get("pattern", "")
        if pattern and pattern in log_text:
            matches.append(
                {
                    "id": sig.get("id"),
                    "category": sig.get("category"),
                    "severity": sig.get("severity"),
                    "pattern": pattern,
                    "tags": sig.get("tags", []),
                }
            )
    return matches
