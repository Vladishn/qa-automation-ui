from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


BASE_DIR = Path(__file__).resolve().parent.parent  # backend/app -> backend
REGRESSION_DIR = BASE_DIR / "artifacts" / "regression"


def save_session_snapshot(session_id: str, session_data: Dict[str, Any]) -> str:
    """
    Save a JSON snapshot for the given session_id into a regression artifacts directory.
    Returns the absolute file path of the written JSON file.
    """
    REGRESSION_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{session_id}_{timestamp}.json"
    path = REGRESSION_DIR / filename

    with path.open("w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)

    return str(path)
