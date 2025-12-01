# File: src/qa/report_generator.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import textwrap


def _read_jsonl_steps(path: Path) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    if not path.exists():
        return steps
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(eval(line))  # noqa: S307
            except Exception:
                continue
    return steps


def _format_steps_summary(steps: List[Dict[str, Any]]) -> str:
    total = len(steps)
    passes = sum(1 for step in steps if step.get("status") == "PASS")
    fails = sum(1 for step in steps if step.get("status") == "FAIL")
    return textwrap.dedent(
        f"""
        ## Steps Summary

        - Total steps recorded: {total}
        - PASS: {passes}
        - FAIL: {fails}
        """
    ).strip()


def _render_historical_context(summary: Dict[str, Any]) -> str:
    if not summary:
        return ""
    lines = ["## Historical Context (Pattern Memory)", ""]
    lines.append(f"Total runs for scenario: {summary.get('total_runs_for_scenario', 0)}")
    lines.append(f"Total failures for scenario: {summary.get('total_failures_for_scenario', 0)}")
    lines.append(f"Runs for this STB: {summary.get('runs_for_this_stb', 0)}")
    lines.append(f"Failures for this STB: {summary.get('failures_for_this_stb', 0)}")
    root_counts = summary.get("root_cause_counts") or {}
    if root_counts:
        lines.append("Root cause counts:")
        for root, count in root_counts.items():
            lines.append(f"  - {root}: {count}")
    sig_counts = summary.get("signature_counts") or {}
    if sig_counts:
        lines.append("Signature counts:")
        for sig, count in sig_counts.items():
            lines.append(f"  - {sig}: {count}")
    return "\n".join(lines)


def _extract_log_highlights(raw_log_path: Path, matched_signatures: List[Dict[str, Any]], limit: int = 10) -> str:
    lines = ["## Key Log Highlights", ""]
    if not raw_log_path or not raw_log_path.exists():
        lines.append("Raw log not available for this session.")
        return "\n".join(lines)

    log_text = raw_log_path.read_text(encoding="utf-8", errors="ignore")
    log_lines = log_text.splitlines()
    if not matched_signatures:
        lines.append("No known QuickSet signatures were matched in the logs.")
        return "\n".join(lines)

    for sig in matched_signatures[:limit]:
        sig_id = sig.get("id", "UNKNOWN")
        category = sig.get("category", "")
        severity = sig.get("severity", "")
        pattern = sig.get("pattern") or sig_id
        lines.append(f"### Signature: {sig_id} ({category}, {severity})")
        lines.append(f"Pattern: `{pattern}`")

        excerpt = "Pattern not found in raw log."
        for idx, line in enumerate(log_lines):
            if pattern and pattern in line:
                start = max(0, idx - 3)
                end = min(len(log_lines), idx + 4)
                snippet = "\n".join(log_lines[start:end])
                excerpt = f"```text\n{snippet}\n```"
                break

        lines.append("Excerpt:")
        lines.append(excerpt)
        lines.append("")

    return "\n".join(lines)


def generate_markdown_report(
    steps_jsonl_path: Path,
    scenario_result: Dict[str, Any],
    report_path: Path,
    raw_log_path: Path | None = None,
) -> None:
    steps = _read_jsonl_steps(steps_jsonl_path)
    summary_lines = [
        f"# Scenario Report: {scenario_result.get('title', scenario_result.get('scenario_id', 'Unknown'))}",
        "",
        f"**Status:** {scenario_result.get('status', 'UNKNOWN')}",
        f"**Root Cause:** {scenario_result.get('root_cause_category', 'UNKNOWN')}",
        f"**Analysis:** {scenario_result.get('analysis', 'N/A')}",
        "",
    ]

    historical = scenario_result.get("pattern_memory_summary") or {}
    if historical:
        summary_lines.append(_render_historical_context(historical))
        summary_lines.append("")

    summary_lines.append(_format_steps_summary(steps))
    summary_lines.append("")

    auto_evidence = scenario_result.get("auto_evidence", {}) or {}
    matched_signatures = auto_evidence.get("matched_signatures") or []
    summary_lines.append(_extract_log_highlights(raw_log_path or Path(), matched_signatures))
    summary_lines.append("")

    tv_brand_ui = scenario_result.get("tv_brand_ui")
    tv_brand_logs = scenario_result.get("tv_brand_logs")
    tv_model_logs = scenario_result.get("tv_model_logs")
    summary_lines.append("## TV Identity")
    summary_lines.append("")
    summary_lines.append(f"- Brand (UI): {tv_brand_ui or 'N/A'}")
    summary_lines.append(f"- Brand (logs): {tv_brand_logs or 'N/A'}")
    summary_lines.append(f"- Model (logs): {tv_model_logs or 'N/A'}")
    summary_lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(summary_lines).strip() + "\n", encoding="utf-8")
