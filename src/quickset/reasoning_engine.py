from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml


def load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_errors() -> Dict[str, Dict[str, Any]]:
    path = Path(__file__).resolve().parents[2] / "knowledge" / "core" / "quickset_errors.yaml"
    data = load_yaml(path)
    return {item["id"]: item for item in data.get("errors", [])}


def load_rules() -> List[Dict[str, Any]]:
    path = Path(__file__).resolve().parents[2] / "knowledge" / "rules" / "autosync_rules.yaml"
    data = load_yaml(path)
    return data.get("rules", [])


def load_scenario_meta() -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "knowledge" / "scenarios" / "tv_auto_sync.yaml"
    return load_yaml(path)


def evaluate_rules(
    rules: List[Dict[str, Any]],
    matched_signatures: List[Dict[str, Any]],
    tester_observations: Dict[str, Any],
    volume_probe: Dict[str, Any] | None,
) -> Dict[str, Any]:
    matched_ids = {m.get("id") for m in matched_signatures}
    for rule in rules:
        conditions = rule.get("conditions", {})
        required = set(conditions.get("required_signals", []) or [])
        tester_require = conditions.get("tester", {}) or {}
        tester_any = conditions.get("tester_any", {}) or {}
        probe_require = conditions.get("probe", {}) or {}

        if required and not required.issubset(matched_ids):
            continue

        tester_ok = True
        for key, expected in tester_require.items():
            if tester_observations.get(key) != expected:
                tester_ok = False
                break
        if not tester_ok:
            continue

        any_ok = True
        for key, expected_values in tester_any.items():
            if tester_observations.get(key) not in expected_values:
                any_ok = False
                break
        if not any_ok:
            continue

        probe_ok = True
        if probe_require:
            if not volume_probe:
                probe_ok = False
            else:
                for key, expected in probe_require.items():
                    if volume_probe.get(key) != expected:
                        probe_ok = False
                        break
        if not probe_ok:
            continue

        return rule.get("outcome", {})

    return {
        "status": "INCONCLUSIVE",
        "root_cause_category": "INCONCLUSIVE",
        "analysis": "No matching rule; insufficient evidence.",
    }


def reason_autosync(
    matched_signatures: List[Dict[str, Any]],
    tester_observations: Dict[str, Any],
    terminal_state: str,
    tv_meta: Dict[str, Any] | None = None,
    volume_probe: Dict[str, Any] | None = None,
    state_before: Dict[str, Any] | None = None,
    state_after: Dict[str, Any] | None = None,
    state_diff: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    rules = load_rules()
    errors = load_errors()
    scenario_meta = load_scenario_meta()

    tv_meta = tv_meta or {}
    volume_probe = volume_probe or {}
    state_before = state_before or {}
    state_after = state_after or {}
    state_diff = state_diff or {}

    outcome = evaluate_rules(rules, matched_signatures, tester_observations, volume_probe)
    status = outcome.get("status", "INCONCLUSIVE")
    root_cause_category = outcome.get("root_cause_category", "INCONCLUSIVE")
    analysis = outcome.get("analysis", "")

    root_details = errors.get(root_cause_category, {})
    root_title = root_details.get("title", root_cause_category)
    root_description = root_details.get("description", "")

    rule_actions = outcome.get("suggested_actions") or []
    error_actions = root_details.get("suggested_actions") or []
    suggested_actions: List[str] = []
    seen: set[str] = set()
    for action in list(rule_actions) + list(error_actions):
        if not action or action in seen:
            continue
        seen.add(action)
        suggested_actions.append(action)

    return {
        "scenario_id": scenario_meta.get("scenario_id", "TV_AUTO_SYNC"),
        "title": scenario_meta.get("title", "TV Auto Sync"),
        "status": status,
        "root_cause_category": root_cause_category,
        "root_cause_title": root_title,
        "root_cause_description": root_description,
        "analysis": analysis,
        "suggested_actions": suggested_actions,
        "auto_evidence": {
            "terminal_state": terminal_state,
            "matched_signatures": matched_signatures,
        },
        "tester_observations": tester_observations,
        "tv_brand_ui": tester_observations.get("tv_brand_ui"),
        "tv_brand_logs": tv_meta.get("tv_brand_logs"),
        "tv_model_logs": tv_meta.get("tv_model_logs"),
        "volume_probe": volume_probe,
        "state_before": state_before,
        "state_after": state_after,
        "state_diff": state_diff,
    }
