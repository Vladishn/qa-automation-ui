"""Basic smoke tests for shared utilities."""

from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.qa.step_logger import StepLogger  # noqa: E402  (import after path tweak)


def test_step_logger_records_entries(tmp_path) -> None:
    """Ensure the step logger stores entries with metadata."""
    logger = StepLogger("test-session", tmp_path)
    logger.log_step("example", "PASS", {"note": "sample"})
    logger.close()

    log_file = tmp_path / "test-session.jsonl"
    content = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1
    entry = json.loads(content[0])
    assert entry["session_id"] == "test-session"
    assert entry["step_name"] == "example"
    assert entry["status"] == "PASS"
    assert entry["details"]["note"] == "sample"
