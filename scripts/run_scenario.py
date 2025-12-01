"""Legacy CLI wrapper for running QuickSet scenarios without Typer."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict


def _bootstrap_pythonpath() -> None:
    """Ensure that the project root is available on sys.path for imports."""
    import sys

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments required to execute a scenario."""
    parser = argparse.ArgumentParser(description="Run a QuickSet QA scenario.")
    parser.add_argument("--session-id", required=True, help="Session identifier.")
    parser.add_argument("--stb-ip", required=True, help="STB IP:PORT for adb.")
    parser.add_argument("--scenario", required=True, help="Scenario name, e.g. TV_AUTO_SYNC.")
    return parser.parse_args()


def main() -> None:
    """Entry point that coordinates argument parsing and scenario execution."""
    _bootstrap_pythonpath()
    from src.qa.session_runner import SessionRunner  # type: ignore

    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    runner = SessionRunner(project_root)
    result: Dict[str, Any] = runner.run(
        session_id=args.session_id,
        stb_ip=args.stb_ip,
        scenario_name=args.scenario,
    )

    scenario_result = result.get("result", {})
    status = scenario_result.get("status", "UNKNOWN")
    root_cause = scenario_result.get("root_cause_category", "Unspecified")
    analysis = scenario_result.get("analysis", "")

    print(f"Scenario: {args.scenario}")
    print(f"Session: {args.session_id}")
    print(f"Status: {status}")
    print(f"Root cause: {root_cause}")
    if analysis:
        print(f"Analysis: {analysis}")
    print(f"Steps JSONL: {result.get('session_log_path')}")
    print(f"Raw log: {result.get('raw_log_path')}")


if __name__ == "__main__":
    main()
