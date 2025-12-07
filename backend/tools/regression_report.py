import json
from pathlib import Path
import sys

# ROOT_DIR = backend (הקובץ נמצא ב-backend/tools)
ROOT_DIR = Path(__file__).resolve().parents[1]
REGRESSION_DIR = ROOT_DIR / "artifacts" / "regression"


def norm_status(s):
    """Normalize status string to lower-case."""
    return (s or "").lower()


def main():
    if len(sys.argv) < 2:
        print("Usage: regression_report.py SESSION_ID")
        raise SystemExit(1)

    sid = sys.argv[1]
    path = REGRESSION_DIR / f"session_{sid}.json"

    if not path.exists():
        print(f"[ERROR] Snapshot not found: {path}")
        raise SystemExit(1)

    data = json.loads(path.read_text(encoding="utf-8"))

    session = data.get("session", {})
    timeline = data.get("timeline", [])
    has_failure = data.get("has_failure")

    # --- basic fields ---
    session_id = (
        session.get("session_id")
        or session.get("id")
        or sid
    )
    scenario = session.get("scenario_name") or session.get("scenario")
    tester = session.get("tester_id") or session.get("tester")
    stb_ip = session.get("stb_ip")
    overall_status = session.get("overall_status")

    brand_mismatch = session.get("brand_mismatch")
    tv_brand_user = session.get("tv_brand_user")
    tv_brand_log = session.get("tv_brand_log")
    has_volume_issue = session.get("has_volume_issue")
    has_osd_issue = session.get("has_osd_issue")
    analysis_text = session.get("analysis_text")

    # --- failed steps ---
    failed_events = [e for e in timeline if norm_status(e.get("status")) == "fail"]

    analysis_event = next(
        (e for e in timeline if e.get("name") == "analysis_summary"),
        None,
    )
    summary_details = (analysis_event or {}).get("details") or {}
    failed_from_summary = summary_details.get("failed_steps") or []

    print("=" * 60)
    print("REGRESSION REPORT")
    print("=" * 60)
    print(f"Session ID   : {session_id}")
    if scenario:
        print(f"Scenario     : {scenario}")
    if tester:
        print(f"Tester       : {tester}")
    if stb_ip:
        print(f"STB IP       : {stb_ip}")
    if overall_status:
        print(f"Overall      : {overall_status}")
    if has_failure is not None:
        print(f"Has failure  : {has_failure}")
    print()

    print("TV / Brand:")
    if tv_brand_user or tv_brand_log:
        print(f"  User brand : {tv_brand_user}")
        print(f"  Log brand  : {tv_brand_log}")
    if brand_mismatch is not None:
        print(f"  Mismatch   : {brand_mismatch}")
    print()

    print("Volume / OSD:")
    if has_volume_issue is not None:
        print(f"  Volume issue: {has_volume_issue}")
    if has_osd_issue is not None:
        print(f"  OSD issue   : {has_osd_issue}")
    print()

    if analysis_text:
        print("Analysis:")
        print(f"  {analysis_text}")
        print()

    # --- failed steps section ---
    if failed_events:
        print("Failed steps (from timeline):")
        for idx, e in enumerate(failed_events, start=1):
            name = e.get("name") or e.get("label") or f"step_{idx}"
            label = e.get("label") or ""
            details = e.get("details") or {}
            reason = (
                details.get("probe_mismatch_reason")
                or details.get("mismatch_reason")
                or details.get("analysis")
                or details.get("error")
                or ""
            )
            disp = name
            if label and label != name:
                disp += f" ({label})"
            print(f"  {idx}. {disp}")
            if reason:
                print(f"       - {reason}")
        print()

    if failed_from_summary:
        print("Failed steps (from summary.failed_steps):")
        for idx, name in enumerate(failed_from_summary, start=1):
            print(f"  {idx}. {name}")
        print()

    if not failed_events and not failed_from_summary:
        print("No failed steps recorded.")
        print()

    print("Source file:")
    print(f"  {path}")


if __name__ == "__main__":
    main()
