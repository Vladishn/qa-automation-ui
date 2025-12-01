# File: src/cli.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.qa.pattern_memory import (
    append_pattern_entry,
    build_historical_summary,
    build_pattern_entry,
    load_pattern_memory,
)
from src.qa.report_generator import generate_markdown_report
from src.qa.session_runner import SessionRunner

app = typer.Typer(help="QuickSet QA automation CLI")
console = Console()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_steps(jsonl_path: Path) -> List[Dict[str, Any]]:
    if not jsonl_path.exists():
        return []
    steps: List[Dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return steps


def _summarize_steps(steps: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(steps)
    passed = sum(1 for step in steps if step.get("status") == "PASS")
    failed = sum(1 for step in steps if step.get("status") == "FAIL")
    return {"total": total, "pass": passed, "fail": failed}


def format_summary(result: Dict[str, Any]) -> str:
    status = result.get("status", "UNKNOWN")
    root = result.get("root_cause_category", "UNKNOWN")
    analysis = result.get("analysis", "")
    title = result.get("title") or result.get("scenario_id", "")
    return f"Scenario: {title} | Status: {status} | Root cause: {root} | Analysis: {analysis}"


@app.command("run")
def run_scenario(
    session_id: str = typer.Option(..., "--session-id", help="Session identifier."),
    stb_ip: str = typer.Option(..., "--stb-ip", help="STB IP:PORT for adb."),
    scenario: str = typer.Option(..., "--scenario", help="Scenario name."),
) -> None:
    root = _project_root()
    runner = SessionRunner(root)
    session_output = runner.run(session_id=session_id, stb_ip=stb_ip, scenario_name=scenario)

    steps_path = root / "logs" / "sessions" / f"{session_id}.jsonl"
    steps = _load_steps(steps_path)
    step_counts = _summarize_steps(steps)

    scenario_result: Dict[str, Any] = session_output.get("result", {}) or {}
    report_path = root / "logs" / "reports" / f"{session_id}_{scenario.lower()}.md"

    raw_log_path = session_output.get("raw_log_path")
    raw_log_path = Path(raw_log_path) if raw_log_path else None

    scenario_id = scenario_result.get("scenario_id", scenario.upper())
    tv_brand_ui = scenario_result.get("tv_brand_ui")
    tv_brand_logs = scenario_result.get("tv_brand_logs")
    matched_sigs = scenario_result.get("auto_evidence", {}).get("matched_signatures") or []
    matched_sig_ids = [sig.get("id") for sig in matched_sigs if sig.get("id")]
    status = scenario_result.get("status", "UNKNOWN")
    root_cause = scenario_result.get("root_cause_category", "UNKNOWN")

    pattern_entry = build_pattern_entry(
        session_id=session_id,
        scenario_id=scenario_id,
        stb_target=stb_ip,
        status=status,
        root_cause_category=root_cause,
        matched_signatures=matched_sig_ids,
        tv_brand_ui=tv_brand_ui,
        tv_brand_logs=tv_brand_logs,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    memory = append_pattern_entry(root, pattern_entry)
    historical_summary = build_historical_summary(memory, scenario_id, stb_target=stb_ip, tv_brand_ui=tv_brand_ui)
    scenario_result["pattern_memory_summary"] = historical_summary

    generate_markdown_report(steps_path, scenario_result, report_path, raw_log_path=raw_log_path)

    console.print(
        Panel(
            format_summary(scenario_result),
            title="QuickSet Scenario Summary",
            subtitle=f"Session: {session_id}",
            expand=False,
        )
    )

    tv_table = Table(title="TV Identity", box=box.SIMPLE_HEAVY)
    tv_table.add_column("Source")
    tv_table.add_column("Value")
    tv_table.add_row("Brand (UI)", str(tv_brand_ui or "N/A"))
    tv_table.add_row("Brand (logs)", str(tv_brand_logs or "N/A"))
    tv_table.add_row("Model (logs)", str(scenario_result.get("tv_model_logs") or "N/A"))
    console.print(tv_table)

    volume_probe = scenario_result.get("volume_probe") or {}
    probe_table = Table(title="Volume Probe", box=box.MINIMAL_HEAVY_HEAD)
    probe_table.add_column("Metric")
    probe_table.add_column("Value")
    probe_table.add_row("Volume Source", str(volume_probe.get("volume_source", "UNKNOWN")))
    confidence = volume_probe.get("confidence")
    probe_table.add_row("Confidence", f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "N/A")
    console.print(probe_table)

    overview = Table(title="Steps Overview", box=box.SIMPLE_HEAVY)
    overview.add_column("Total")
    overview.add_column("PASS", style="green")
    overview.add_column("FAIL", style="red")
    overview.add_row(str(step_counts["total"]), str(step_counts["pass"]), str(step_counts["fail"]))
    console.print(overview)

    evidence = scenario_result.get("auto_evidence", {})
    sig_table = Table(title="Matched Signatures", box=box.MINIMAL_HEAVY_HEAD)
    sig_table.add_column("ID")
    sig_table.add_column("Category")
    sig_table.add_column("Severity")
    for sig in evidence.get("matched_signatures") or []:
        sig_table.add_row(
            str(sig.get("id", "")),
            str(sig.get("category", "")),
            str(sig.get("severity", "")),
        )
    console.print(sig_table)

    state_diff = scenario_result.get("state_diff") or {}
    changed = state_diff.get("changed") or {}
    if changed:
        diff_table = Table(title="QuickSet State Diff", box=box.MINIMAL_HEAVY_HEAD)
        diff_table.add_column("Key")
        diff_table.add_column("Before")
        diff_table.add_column("After")
        for key, diff in changed.items():
            diff_table.add_row(key, str(diff.get("before")), str(diff.get("after")))
        console.print(diff_table)
    if state_diff.get("unchanged"):
        unchanged_list = ", ".join(state_diff["unchanged"])
        console.print(f"Unchanged keys: {unchanged_list}")

    console.print(f"Terminal state: {evidence.get('terminal_state', 'unknown')}")
    console.print(f"Steps JSONL: {steps_path}")
    console.print(f"Report saved to: {report_path}")

    historical = scenario_result.get("pattern_memory_summary") or {}
    if historical:
        hist_table = Table(title="Historical Context (Pattern Memory)", box=box.MINIMAL_HEAVY_HEAD)
        hist_table.add_column("Metric")
        hist_table.add_column("Value")
        hist_table.add_row("Total runs (scenario)", str(historical.get("total_runs_for_scenario", 0)))
        hist_table.add_row("Failures (scenario)", str(historical.get("total_failures_for_scenario", 0)))
        hist_table.add_row("Runs for this STB", str(historical.get("runs_for_this_stb", 0)))
        hist_table.add_row("Failures for this STB", str(historical.get("failures_for_this_stb", 0)))
        console.print(hist_table)

    suggested_actions = scenario_result.get("suggested_actions") or []
    if suggested_actions:
        actions_text = "\n".join(f"- {action}" for action in suggested_actions)
        console.print(
            Panel(
                actions_text,
                title="Suggested Next Steps",
                subtitle="Failure Compass",
                expand=False,
            )
        )


@app.command("summarize")
def summarize_session(
    session_id: str = typer.Option(..., "--session-id", help="Session identifier."),
    scenario: str = typer.Option("TV_AUTO_SYNC", "--scenario", help="Scenario name."),
) -> None:
    root = _project_root()
    report_path = root / "logs" / "reports" / f"{session_id}_{scenario.lower()}.md"
    if report_path.exists():
        console.print(Panel(report_path.read_text(), title="Stored Report"))
    else:
        console.print(f"No report found for: {session_id}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
