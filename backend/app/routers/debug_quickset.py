"""Debug endpoints for inspecting QuickSet step logs."""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter

from ..config import settings

router = APIRouter(prefix="/debug/quickset", tags=["debug-quickset"])


def _collect_step_files(directory: Path) -> List[str]:
    if not directory.exists():
        return []
    return sorted(
        file.name
        for file in directory.glob("*.jsonl")
        if file.is_file()
    )


@router.get("/sessions")
def list_quickset_sessions() -> dict[str, object]:
    steps_dir = Path(settings.quickset_steps_dir).expanduser()
    files = _collect_step_files(steps_dir)
    return {
        "dir": str(steps_dir.resolve()),
        "files": files,
    }
