"""Seed logic: turn the admin's plugin settings into record categories and
merge them into a user's AerioTV record.

Pure Python, no Django. Everything that touches Dispatcharr lives in
dispatcharr_bridge.py.

Merge modes:
- fill (default): add a phase 1 category only when the record does not hold it
  yet. A category a device already wrote is never touched.
- replace: overwrite the categories the admin filled in. For settings, only the
  names the admin set are overwritten in the `v` lane; every other name and lane
  stays. Categories the admin left blank, and every non phase 1 category, are
  round-tripped untouched.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import app_settings, options, schema

MODE_FILL = "fill"
MODE_REPLACE = "replace"
MODES = (MODE_FILL, MODE_REPLACE)

# Stable writer identity for records this plugin writes. Devices compare
# deviceId only to break updatedAt ties (schema 6.1).
PLUGIN_DEVICE_ID = "00000000-0000-4000-8000-a3e10d15ea7d"
PLUGIN_PLATFORM = "dispatcharr-plugin"


class SeedError(ValueError):
    """The admin's input cannot be turned into a valid seed."""


@dataclass
class SeedRequest:
    username: str
    mode: str
    categories: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def parse_channel_ids(text: Any) -> List[int]:
    """Comma, space, or newline separated channel ids, order kept, repeats dropped."""
    if not text:
        return []
    if not isinstance(text, str):
        raise SeedError("favorites must be text")
    ids: List[int] = []
    for token in re.split(r"[\s,]+", text.strip()):
        if not token:
            continue
        if not token.isdigit():
            raise SeedError("favorites must be channel ids (whole numbers)")
        value = int(token)
        if value not in ids:
            ids.append(value)
    return ids


NONE = "__none__"


def _value(settings: Dict[str, Any], key: str) -> str:
    """A saved setting as a string; blank and the Leave empty sentinel read as ""."""
    raw = settings.get(key)
    if raw is None:
        return ""
    value = str(raw).strip()
    return "" if value == NONE else value


def _slots(settings: Dict[str, Any], prefix: str) -> List[str]:
    """Values of prefix_1, prefix_2, ... in slot order, empties skipped, repeats dropped."""
    numbered = []
    for key in settings:
        if key.startswith(prefix + "_") and key[len(prefix) + 1:].isdigit():
            numbered.append((int(key[len(prefix) + 1:]), key))
    out: List[str] = []
    for _, key in sorted(numbered):
        value = _value(settings, key)
        if value and value not in out:
            out.append(value)
    return out


def parse_settings(settings: Dict[str, Any]) -> SeedRequest:
    """Build a SeedRequest from the plugin's saved settings.

    Reads the select slots (favorite_N, group_N), the Show switches
    (show_live:, show_movies:, show_series:), and the App Settings selects
    (set:<name>). The 0.1.0 text fields (favorites, group_order,
    hidden_groups_*) are ignored on purpose: Dispatcharr keeps old keys in the
    saved settings after the fields are gone, and the admin can no longer see them.
    """
    settings = dict(settings or {})
    username = _value(settings, "target_username")
    if not username:
        raise SeedError("choose a user first")
    mode = _value(settings, "apply_mode") or MODE_FILL
    if mode not in MODES:
        raise SeedError("apply mode must be fill or replace")

    cats: Dict[str, Dict[str, Any]] = {}

    ids = parse_channel_ids(" ".join(_slots(settings, "favorite")))
    if ids:
        cats[schema.FAVORITES] = {"ids": ids}

    order = _slots(settings, "group")
    order_mode = _value(settings, "group_order_mode")
    if order_mode:
        if order_mode == "manual" and not order:
            raise SeedError("manual group order needs at least one group")
        cats[schema.GROUP_ORDER] = {"mode": order_mode, "order": order if order_mode == "manual" else []}
    elif order:
        cats[schema.GROUP_ORDER] = {"mode": "manual", "order": order}

    hidden = options.hidden_from_switches(settings)
    if any(hidden.values()):
        cats[schema.HIDDEN_GROUPS] = hidden

    try:
        lane: Dict[str, Any] = app_settings.lane_from_settings(settings, NONE)
    except ValueError as exc:
        raise SeedError(f"setting {exc} has a value outside the schema") from exc
    default_group = _value(settings, "default_group")
    if default_group:
        lane["defaultGroup"] = default_group
    if lane:
        cats[schema.SETTINGS] = {"v": lane}

    for name, data in cats.items():
        try:
            if name == schema.SETTINGS:
                schema.validate_settings(data, strict_names=True)
            else:
                schema.validate_category_data(name, data)
        except schema.SchemaError as exc:
            raise SeedError(str(exc)) from exc

    return SeedRequest(username=username, mode=mode, categories=cats)


@dataclass
class MergeResult:
    record: Dict[str, Any]
    added: List[str] = field(default_factory=list)
    replaced: List[str] = field(default_factory=list)
    kept: List[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.replaced)


def new_record(app_version: str, now: str) -> Dict[str, Any]:
    return {
        "schemaVersion": schema.SCHEMA_VERSION,
        "deviceId": PLUGIN_DEVICE_ID,
        "platform": PLUGIN_PLATFORM,
        "appVersion": app_version,
        "updatedAt": now,
        schema.CATEGORIES: {},
    }


def merge(existing: Optional[Dict[str, Any]], seed: Dict[str, Dict[str, Any]], *,
          mode: str, app_version: str, now: Optional[str] = None) -> MergeResult:
    """Merge seed categories into an existing record (or a new one).

    Raises schema.SchemaError when the existing record is one the plugin must
    not write over (malformed, or a schemaVersion it does not know).
    """
    if mode not in MODES:
        raise SeedError("apply mode must be fill or replace")
    now = now or schema.iso_seconds()
    if existing is None:
        record = new_record(app_version, now)
    else:
        record = copy.deepcopy(schema.validate_envelope(existing))
    cats = record[schema.CATEGORIES]
    result = MergeResult(record=record)

    for name, data in seed.items():
        prior = cats.get(name)
        if prior is None:
            cats[name] = schema.category(data, device_id=PLUGIN_DEVICE_ID, updated_at=now)
            result.added.append(name)
            continue
        if mode == MODE_FILL:
            result.kept.append(name)
            continue
        new_data = data
        if name == schema.SETTINGS:
            new_data = copy.deepcopy(prior.get("data") or {})
            lane = dict(new_data.get("v") or {})
            lane.update(data.get("v", {}))
            new_data["v"] = lane
        if new_data == prior.get("data"):
            result.kept.append(name)
            continue
        cats[name] = schema.category(new_data, device_id=PLUGIN_DEVICE_ID, updated_at=now, previous=prior)
        result.replaced.append(name)

    if result.changed:
        # Envelope fields describe the last write of the whole key (schema 3).
        record["schemaVersion"] = schema.SCHEMA_VERSION
        record["deviceId"] = PLUGIN_DEVICE_ID
        record["platform"] = PLUGIN_PLATFORM
        record["appVersion"] = app_version
        record["updatedAt"] = now
    return result


def summarize(record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts only, never values, for logs and UI messages."""
    if not record:
        return {"present": False}
    cats = record.get(schema.CATEGORIES) or {}
    out: Dict[str, Any] = {"present": True, "schemaVersion": record.get("schemaVersion"), "categories": {}}
    for name, sub in sorted(cats.items()):
        data = (sub or {}).get("data") or {}
        if name == schema.FAVORITES:
            count = len(data.get("ids") or [])
        elif name == schema.GROUP_ORDER:
            count = len(data.get("order") or [])
        elif name == schema.HIDDEN_GROUPS:
            count = sum(len(data.get(k) or []) for k in schema.HIDDEN_GROUP_KINDS)
        elif name == schema.SETTINGS:
            count = sum(len(v) for v in data.values() if isinstance(v, dict))
        else:
            count = None
        out["categories"][name] = count
    return out


def describe(summary: Dict[str, Any]) -> str:
    if not summary.get("present"):
        return "no AerioTV record yet"
    parts = []
    for name, count in summary["categories"].items():
        parts.append(name if count is None else f"{name} ({count})")
    return "record holds: " + (", ".join(parts) if parts else "no categories")


def legacy_conflict(keys: List[str], record_key: str) -> Tuple[bool, List[str]]:
    """Schema 6.5: devices move legacy keys only while <user>.aeriotv is absent.

    Writing the new key while a legacy key exists would strand the legacy data,
    so the plugin refuses until a device has done the move.
    """
    legacy = [k for k in keys if k == "app.molinete.aerio" or k.startswith("app.molinete.aerio.")]
    return (bool(legacy) and record_key not in keys), legacy
