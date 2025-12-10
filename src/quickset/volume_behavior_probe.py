# File: src/quickset/volume_behavior_probe.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml


@dataclass
class VolumeProbeSignals:
    """
    Internal helper structure describing what we found in the logs.

    This is NOT exposed outside the probe; run_probe still returns the legacy
    dict shape (volume_source, confidence, matched_signatures, raw_code).
    """

    raw_code: Optional[int] = None
    volume_source: str = "UNKNOWN"  # "STB" / "TV" / "UNKNOWN"
    confidence: float = 0.2
    matched_signatures: List[Dict[str, str]] | None = None
    source_reason: str = ""
    lines_scanned: int = 0
    context_window_size: int = 0
    recent_volume_sources: List[str] = field(default_factory=list)


class VolumeBehaviorProbe:
    """
    Determine whether TV or STB volume reacted by reading QuickSet volume_source logs.

    New behavior (backwards compatible):
    - Scans only the tail of the log (recent lines) instead of the whole file.
    - Prioritizes volume_source codes that are in QuickSet / TV_AUTO_SYNC context.
    - Falls back to the legacy "last volume_source code in file" if nothing better exists.
    - Returns the same public result fields (volume_source, confidence, matched_signatures, raw_code),
      plus extra metadata keys that the analyzer may ignore safely.
    """

    # Patterns that extract numeric volume_source codes from log lines
    VOLUME_PATTERNS: List[str] = [
        r'"volume_source":\s*(\d+)',
        r'curVolSource:\s*(\d+)',
        r'current_volume_source.*value:(\d+)',
    ]

    # Markers that indicate QuickSet / TV auto-sync context in logs
    QUICKSET_MARKERS: List[str] = [
        "QuickSet",
        "quickset",
        "com.nes.pntv.quickset",
        "com.uei.quicksetsdk",
        "TV_AUTO_SYNC",
        "tv_auto_sync",
        "TvAutoSync",
    ]

    # Mapping from numeric code to semantic source
    SOURCE_MAP: Dict[int, str] = {
        0: "STB",
        1: "TV",
    }

    # How many lines from the end of the log to consider
    DEFAULT_TAIL_LINES: int = 4000

    # When searching around QuickSet markers, how many lines back we keep as context
    QUICKSET_CONTEXT_LINES: int = 150

    def __init__(self, adb_client: Any, log_path: Path, knowledge_root: Path) -> None:
        self.adb = adb_client
        self.log_path = log_path
        self.knowledge_root = knowledge_root
        self.signatures = self._load_signatures()

    # -------------------------------------------------------------------------
    # I/O helpers
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Parsing helpers
    # -------------------------------------------------------------------------

    def _tail_lines(self, text: str, max_lines: int) -> List[str]:
        """Return only the last max_lines lines from the log text."""
        if not text:
            return []
        lines = text.splitlines()
        if len(lines) <= max_lines:
            return lines
        return lines[-max_lines:]

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

    def _iter_volume_matches(
        self, lines: Iterable[str]
    ) -> Iterable[Tuple[int, str, int]]:
        """
        Yield (line_index, pattern, numeric_code) for every volume_source code
        found in the given lines.
        """
        for idx, line in enumerate(lines):
            for pattern in self.VOLUME_PATTERNS:
                for match in re.findall(pattern, line, flags=re.IGNORECASE):
                    try:
                        code = int(match)
                    except ValueError:
                        continue
                    yield idx, pattern, code

    def _closest_quickset_context_indices(self, lines: List[str]) -> List[int]:
        """
        Return indices of lines that contain QuickSet / TV_AUTO_SYNC markers.
        Used as anchors for contextual search.
        """
        anchor_indices: List[int] = []
        for idx, line in enumerate(lines):
            if any(marker in line for marker in self.QUICKSET_MARKERS):
                anchor_indices.append(idx)
        return anchor_indices

    def _select_best_code_from_tail(self, text: str) -> VolumeProbeSignals:
        """
        Core logic:
        - Work on the tail of the log to avoid stale history.
        - Try to find volume_source codes that are in QuickSet context.
        - Fallback to the last code in the tail if none are contextual.
        """
        signals = VolumeProbeSignals()
        if not text:
            signals.source_reason = "Empty log file; no volume_source information."
            return signals

        tail_lines = self._tail_lines(text, self.DEFAULT_TAIL_LINES)
        signals.lines_scanned = len(tail_lines)
        signals.context_window_size = self.QUICKSET_CONTEXT_LINES

        # Pre-compute QuickSet anchor positions
        anchor_indices = self._closest_quickset_context_indices(tail_lines)

        # Gather all volume matches in the tail
        all_matches: List[Tuple[int, str, int]] = list(self._iter_volume_matches(tail_lines))
        if all_matches:
            signals.recent_volume_sources = [
                self.SOURCE_MAP.get(code, "UNKNOWN") for _, _, code in all_matches[-10:]
            ]

        if not all_matches:
            signals.source_reason = (
                "No volume_source patterns found in the recent log tail."
            )
            return signals

        # 1) Prefer matches that are within QUICKSET_CONTEXT_LINES distance
        #    of a QuickSet anchor.
        contextual_matches: List[Tuple[int, str, int]] = []
        if anchor_indices:
            anchor_set = set(anchor_indices)
            for idx, pattern, code in all_matches:
                # Find any anchor within context window
                in_context = any(
                    abs(idx - anchor_idx) <= self.QUICKSET_CONTEXT_LINES
                    for anchor_idx in anchor_set
                )
                if in_context:
                    contextual_matches.append((idx, pattern, code))

        chosen_match: Tuple[int, str, int]
        if contextual_matches:
            # Take the LAST contextual match (closest to end of file)
            chosen_match = contextual_matches[-1]
            ctx_type = "quickset_context"
        else:
            # Fallback: legacy behavior on tail – last match in the tail
            chosen_match = all_matches[-1]
            ctx_type = "tail_fallback"

        line_index, pattern_used, raw_code = chosen_match

        # Map numeric code to source
        volume_source = self.SOURCE_MAP.get(raw_code, "UNKNOWN")
        confidence = 0.9 if raw_code in self.SOURCE_MAP else 0.2

        signals.raw_code = raw_code
        signals.volume_source = volume_source
        signals.confidence = confidence

        if ctx_type == "quickset_context":
            signals.source_reason = (
                f"Derived from volume_source={raw_code} within QuickSet/TV_AUTO_SYNC "
                f"context (line {line_index} in recent log tail)."
            )
        else:
            signals.source_reason = (
                f"Derived from last volume_source={raw_code} found in recent log tail "
                f"(no QuickSet anchors nearby)."
            )

        return signals

    # -------------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------------

    def run_probe(self, step_logger: Any, ask: Any | None = None) -> Dict[str, Any]:
        """
        Execute the volume behavior probe.

        Still logs:
          - volume_probe_prompt
          - volume_probe_result

        And still returns:
          {
            "volume_source": <"STB"/"TV"/"UNKNOWN">,
            "confidence": <float>,
            "matched_signatures": <list>,
            "raw_code": <int or None>,
            ...
          }

        Extra keys (like source_reason, lines_scanned, context_window_size) are
        safe for existing analyzers to ignore.
        """
        instruction = (
            "Volume Behavior Probe:\n"
            "Monitoring logs for recent volume control events."
        )
        step_logger.log_step(
            "volume_probe_prompt",
            "INFO",
            {"instruction": instruction, "tester_visible": False},
        )

        log_text = self._read_log_text()
        matched_signatures = self._match_signatures(log_text)

        signals = self._select_best_code_from_tail(log_text)
        signals.matched_signatures = matched_signatures

        result: Dict[str, Any] = {
            "volume_source": signals.volume_source,
            "confidence": signals.confidence,
            "matched_signatures": signals.matched_signatures or [],
            "raw_code": signals.raw_code,
            # extra, non-breaking debug/trace fields:
            "source_reason": signals.source_reason,
            "lines_scanned": signals.lines_scanned,
            "context_window_size": signals.context_window_size,
        }
        if signals.recent_volume_sources:
            result["volume_source_window"] = signals.recent_volume_sources

        step_logger.log_step("volume_probe_result", "INFO", result)
        return result
