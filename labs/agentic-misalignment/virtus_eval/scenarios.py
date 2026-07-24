# Virtus Framework — AI Alignment Through Character
# Part of the Berpiztu Initiative (AI Rebirth)
# Creator: Iosub  |  Implementers: Alex, Leire
# License: Virtus Dual License (Non-Commercial / Commercial)
# https://github.com/Berpiztu/virtus

"""
Scenario registry.

Every ``scenarios/*.json`` file is a scenario: prompts + metadata. The matching
outcome taxonomy (categories, judge prompt, harmful set) lives in
``classifier.SPECS`` under the same id. This module joins the two and is the one
place that answers "which scenarios exist, and what does each one measure?".

A scenario without a classifier spec still loads — it falls back to the default
spec — so dropping a JSON file in the folder is enough to see it in the UI, and
adding a spec is what makes its numbers mean something.
"""

import json
import os
import re

from . import classifier

SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenarios")

DEFAULT_SCENARIO_ID = classifier.DEFAULT_SCENARIO_ID

# Run reports are written per scenario; ids come from filenames and go straight
# into a path, so keep them to a safe, flat charset.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def is_valid_id(scenario_id: str | None) -> bool:
    return bool(scenario_id) and bool(_SAFE_ID.match(scenario_id))


def _read(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    data.setdefault("id", os.path.splitext(os.path.basename(path))[0])
    return data if is_valid_id(data["id"]) else None


def load_all() -> dict[str, dict]:
    """All scenarios on disk, keyed by id. Default scenario first."""
    found = {}
    try:
        names = sorted(os.listdir(SCENARIOS_DIR))
    except OSError:
        names = []
    for name in names:
        if not name.endswith(".json"):
            continue
        data = _read(os.path.join(SCENARIOS_DIR, name))
        if not data:
            continue
        # Two files claiming the same id would silently hide one of them (and
        # share a results folder). Fall back to the filename so both stay usable.
        if data["id"] in found:
            stem = os.path.splitext(name)[0]
            if not is_valid_id(stem) or stem in found:
                continue
            data["id"] = stem
        found[data["id"]] = data

    ordered = {}
    if DEFAULT_SCENARIO_ID in found:
        ordered[DEFAULT_SCENARIO_ID] = found.pop(DEFAULT_SCENARIO_ID)
    ordered.update(found)
    return ordered


def load(scenario_id: str | None) -> dict:
    """One scenario by id, falling back to the default (then to any that loads)."""
    all_scenarios = load_all()
    if not all_scenarios:
        raise FileNotFoundError(f"No scenarios found in {SCENARIOS_DIR}")
    if scenario_id in all_scenarios:
        return all_scenarios[scenario_id]
    if DEFAULT_SCENARIO_ID in all_scenarios:
        return all_scenarios[DEFAULT_SCENARIO_ID]
    return next(iter(all_scenarios.values()))


def resolve_id(scenario_id: str | None) -> str:
    """Normalise an incoming id to one that actually exists on disk."""
    return load(scenario_id)["id"]


def public_list() -> list[dict]:
    """Scenario metadata + outcome taxonomy for the UI (no prompts)."""
    out = []
    for scenario_id, data in load_all().items():
        spec = classifier.get_spec(scenario_id)
        out.append({
            "id": scenario_id,
            "name": data.get("name") or scenario_id,
            "description": data.get("description") or "",
            "tagline": data.get("tagline") or "",
            "has_spec": scenario_id in classifier.SPECS,
            **spec.public(),
        })
    return out
