"""Scenario discovery helpers."""

from __future__ import annotations

from importlib import import_module
from pkgutil import iter_modules
from pathlib import Path
from typing import List

PACKAGE_PATH = Path(__file__).parent


def available_scenarios() -> List[str]:
    """Return the list of available scenario module names."""
    return [
        module.name
        for module in iter_modules([str(PACKAGE_PATH)])
        if not module.ispkg and not module.name.startswith("_")
    ]


def load_scenario_module(name: str):
    """Import and return a scenario module by name."""
    return import_module(f"{__name__}.{name}")
