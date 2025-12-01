# File: src/quickset/volume_behavior_probe.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class VolumeBehaviorProbe:
    """Determine whether TV or STB volume reacted by reading QuickSet volume_source logs."""

    VOLUME_PATTERNS = [
        r'"volume_source":\s*(\d+)',
        r'curVolSource:\s*(\d+)',
        r'current_volume_source.*value:(\d+)',
    ]

    SOURCE_MAP = {
        0: "STB",
        1: "TV",
    }

    def __init__(self, adb_client: Any, log_path: Path, knowledge_root: Path) -> None:
        self.adb = adb_client
        self.log_path = log_path
        self.knowledge_root = knowledge_root
        self.signatures = self._load_signatures()

    def _load_signatures(self) -> List[Dict[str, str]]:
        path = self.knowledge_root / "signatures" / "volume_behavior.yaml"
        if not path.exists():
            return []
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data.get("signatures", [])

    def _read_log_text(self) -> str:
        if not self.log_path.exists():
            return ""
        return self.log_path.read_text(encoding="utf-8", errors="ignore")

    def _find_last_volume_code(self, text: str) -> Optional[int]:
        last_match: Optional[int] = None
        for pattern in self.VOLUME_PATTERNS:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            if matches:
                try:
                    last_match = int(matches[-1])
                except ValueError:
                    continue
        return last_match

    def _match_signatures(self, text: str) -> List[Dict[str, str]]:
        matches: List[Dict[str, str]] = []
        for sig in self.signatures:
            pattern = sig.get("pattern")
            if pattern and pattern in text:
                matches.append(
                    {
                        "id": sig.get("id"),
                        "category": sig.get("category"),
                        "severity": sig.get("severity"),
                    }
                )
        return matches

    def run_probe(self, step_logger: Any, ask: Any) -> Dict[str, Any]:
        instruction = (
            "Volume Behavior Probe:\n"
            "Please press Volume UP on the remote three times, then press Enter here."
        )
        step_logger.log_step("volume_probe_prompt", "INFO", {"instruction": instruction})
        ask("volume_probe", instruction)

        log_text = self._read_log_text()
        raw_code = self._find_last_volume_code(log_text)
        matched_signatures = self._match_signatures(log_text)

        volume_source = self.SOURCE_MAP.get(raw_code, "UNKNOWN")
        confidence = 0.9 if raw_code in self.SOURCE_MAP else 0.2

        result = {
            "volume_source": volume_source,
            "confidence": confidence,
            "matched_signatures": matched_signatures,
            "raw_code": raw_code,
        }
        step_logger.log_step("volume_probe_result", "INFO", result)
        return result
