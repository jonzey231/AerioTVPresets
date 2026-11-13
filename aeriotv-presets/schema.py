"""AerioTV Dispatcharr Sync record shapes (phase 1 categories).

Pure Python, no Django. Mirrors docs/SCHEMA.md, which is a vendored copy of
the contract in the AerioTV repos (docs/DispatcharrSyncSchema.md). When the
two disagree, the AerioTV repos win and this file is fixed to match.

Phase 1 writes four categories: favorites, groupOrder, hiddenGroups, and
settings. The plugin also writes profiles (section 4.12) and tmdbKey (section
4.13). Every other category in a record is round-tripped untouched.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import app_settings

# Schema section 3. The plugin never writes a higher number than this.
SCHEMA_VERSION = 3
CATEGORIES = "categories"
KEY_SUFFIX = ".aeriotv"
USER_PART_MAX = 46

FAVORITES = "favorites"
GROUP_ORDER = "groupOrder"
HIDDEN_GROUPS = "hiddenGroups"
SETTINGS = "settings"
PROFILES = "profiles"
TMDB_KEY = "tmdbKey"
PHASE1_CATEGORIES = (FAVORITES, GROUP_ORDER, HIDDEN_GROUPS, SETTINGS)

# Caps from schema sections 4.1, 4.7, and 4.8.
FAVORITES_CAP = 1000
GROUP_NAMES_CAP = 500
GROUP_ORDER_MODES = ("default", "alphabetical", "manual")
HIDDEN_GROUP_KINDS = ("live", "movies", "series")
SETTINGS_LANES = ("v", "tv", "mobile")

# Section 4.9 values for the settings this plugin offers. Only names in the
# allowlist are ever written.
THEMES = ("Aerio", "Midnight", "Sunset", "Forest", "Lavender", "Monochrome", "Light", "Custom")
APPEARANCE_MODES = ("dark", "light", "system")
GROUP_TOKEN_MAX = 200

# Section 4.13 sizes a TMDB key at 32 characters, or about 250 for a read
# access token. The plugin refuses anything longer than this, which keeps the
# category far inside Dispatcharr's 128 KiB value limit.
TMDB_KEY_MAX = 1024
# The apps' saved server copies hold the key's SHA-256 digest under this name
# (Apple e4a19d3). Section 4.13: a write sends only the key or "", never a
# digest or an encrypted form, so the plugin drops this member if it ever sees it.
TMDB_DIGEST = "apiKeySha256"


class SchemaError(ValueError):
    """A value does not match the AerioTV Dispatcharr Sync schema."""


# ---------------------------------------------------------------- key name

_KEEP = set(b"abcdefghijklmnopqrstuvwxyz0123456789_.-")


def user_key(username: str) -> Optional[str]:
    """Record key for a Dispatcharr username (schema section 2.1).

    Returns None for an empty username (no key).
    """
    if not username:
        return None
    out: List[str] = []
    for byte in username.encode("utf-8"):
        if 0x41 <= byte <= 0x5A:
            out.append(chr(byte + 0x20))
        elif byte in _KEEP:
            out.append(chr(byte))
        else:
            out.append("-%02x" % byte)
    name = "".join(out)
    if not (name[0].isascii() and name[0].isalnum()):
        name = "u" + name
    return name[:USER_PART_MAX] + KEY_SUFFIX


# ---------------------------------------------------------------- time

def iso_seconds(moment: Optional[datetime] = None) -> str:
    """ISO 8601 UTC, second precision, Z suffix (schema section 3)."""
    moment = moment or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def is_iso(value: Any) -> bool:
    return isinstance(value, str) and bool(_ISO_RE.match(value))


# ---------------------------------------------------------------- payloads

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _names(value: Any, label: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(n, str) for n in value):
        raise SchemaError(f"{label} must be a list of strings")
    if len(value) > GROUP_NAMES_CAP:
        raise SchemaError(f"{label} holds more than {GROUP_NAMES_CAP} names")
    return value


def validate_favorites(data: Any) -> Dict[str, Any]:
    """Section 4.1: {"ids": [int, ...]} in display order, no duplicates."""
    if not isinstance(data, dict) or set(data) - {"ids"} or "ids" not in data:
        raise SchemaError("favorites must be {\"ids\": [...]}")
    ids = data["ids"]
    if not isinstance(ids, list) or not all(_is_int(i) for i in ids):
        raise SchemaError("favorites ids must be integers")
    if len(ids) != len(set(ids)):
        raise SchemaError("favorites ids must not repeat")
    if len(ids) > FAVORITES_CAP:
        raise SchemaError(f"favorites holds more than {FAVORITES_CAP} ids")
    return data


def validate_group_order(data: Any) -> Dict[str, Any]:
    """Section 4.8: {"mode": "default"|"alphabetical"|"manual", "order": [str]}."""
    if not isinstance(data, dict) or set(data) - {"mode", "order"}:
        raise SchemaError("groupOrder must be {\"mode\", \"order\"}")
    if data.get("mode") not in GROUP_ORDER_MODES:
        raise SchemaError("groupOrder mode is not one of default, alphabetical, or manual")
    _names(data.get("order", []), "groupOrder order")
    return data


def validate_hidden_groups(data: Any) -> Dict[str, Any]:
    """Section 4.7: {"live": [str], "movies": [str], "series": [str]}."""
    if not isinstance(data, dict) or set(data) - set(HIDDEN_GROUP_KINDS):
        raise SchemaError("hiddenGroups keys must be live, movies, or series")
    for kind in HIDDEN_GROUP_KINDS:
        _names(data.get(kind, []), f"hiddenGroups {kind}")
    return data


# Settings this plugin writes, with their value checks (section 4.9).
def _check_theme(v: Any) -> bool:
    return v in THEMES


def _check_appearance(v: Any) -> bool:
    return v in APPEARANCE_MODES


def _check_group_token(v: Any) -> bool:
    return isinstance(v, str) and len(v) <= GROUP_TOKEN_MAX


SEEDABLE_SETTINGS = {
    "selectedTheme": _check_theme,
    "appearanceMode": _check_appearance,
    "defaultGroup": _check_group_token,
}
for _name in app_settings.BY_NAME:
    SEEDABLE_SETTINGS.setdefault(_name, (lambda n: lambda v: app_settings.is_valid(n, v))(_name))
SEEDABLE_SETTINGS["trueBlack"] = lambda v: isinstance(v, bool)


def validate_settings(data: Any, *, strict_names: bool = False) -> Dict[str, Any]:
    """Section 4.9: lanes v, tv, mobile of name to bool, int, double, or string.

    With strict_names, every name must be one this plugin seeds and its value
    must pass that name's check. Without it (records written by devices), only
    the lane and value types are checked, so unknown names round-trip.
    """
    if not isinstance(data, dict):
        raise SchemaError("settings must be an object")
    for lane, values in data.items():
        if lane not in SETTINGS_LANES:
            if strict_names:
                raise SchemaError("settings lane must be v, tv, or mobile")
            continue
        if not isinstance(values, dict):
            raise SchemaError("settings lane must be an object")
        for name, value in values.items():
            if not isinstance(value, (bool, int, float, str)):
                raise SchemaError("settings values must be bool, number, or string")
            if strict_names:
                check = SEEDABLE_SETTINGS.get(name)
                if check is None:
                    raise SchemaError("setting is not seedable by this plugin")
                if not check(value):
                    raise SchemaError("setting value is outside the schema range")
    return data


def validate_profiles(data: Any) -> Dict[str, Any]:
    """Section 4.12 rows (see profiles.py)."""
    from . import profiles

    try:
        return profiles.validate(data)
    except profiles.ProfileError as exc:
        raise SchemaError(str(exc)) from exc


def tmdb_api_key(data: Any) -> Optional[str]:
    """Section 4.13 reader rule: the trimmed key, "" for no key (a missing
    apiKey reads as ""), or None when the category is malformed."""
    if not isinstance(data, dict):
        return None
    value = data.get("apiKey", "")
    return value.strip() if isinstance(value, str) else None


def validate_tmdb_key(data: Any) -> Dict[str, Any]:
    """Section 4.13: {"apiKey": "<key>"}, "" = no key. For what this plugin
    writes: one trimmed line, no spaces or control characters, at most
    TMDB_KEY_MAX characters. Error text never repeats the key."""
    if not isinstance(data, dict) or set(data) != {"apiKey"} or not isinstance(data["apiKey"], str):
        raise SchemaError("tmdbKey must be {\"apiKey\": \"...\"}")
    key = data["apiKey"]
    if len(key) > TMDB_KEY_MAX:
        raise SchemaError(f"the TMDB API key is longer than {TMDB_KEY_MAX} characters")
    if any(ch.isspace() or not ch.isprintable() for ch in key):
        raise SchemaError("the TMDB API key must be one line with no spaces")
    return data


VALIDATORS = {
    TMDB_KEY: validate_tmdb_key,
    PROFILES: validate_profiles,
    FAVORITES: validate_favorites,
    GROUP_ORDER: validate_group_order,
    HIDDEN_GROUPS: validate_hidden_groups,
    SETTINGS: validate_settings,
}


def validate_category_data(name: str, data: Any) -> Dict[str, Any]:
    validator = VALIDATORS.get(name)
    if validator is None:
        raise SchemaError("category is not one this plugin writes")
    return validator(data)


def is_empty(name: str, data: Dict[str, Any]) -> bool:
    """Schema 10a rule 2: what a device treats as an empty server copy."""
    if name == FAVORITES:
        return not data.get("ids")
    if name == GROUP_ORDER:
        return data.get("mode", "default") == "default" and not data.get("order")
    if name == HIDDEN_GROUPS:
        return not any(data.get(k) for k in HIDDEN_GROUP_KINDS)
    if name == SETTINGS:
        return not any(data.get(lane) for lane in SETTINGS_LANES)
    return not data


# ---------------------------------------------------------------- envelope

def category(data: Dict[str, Any], *, device_id: str, updated_at: str,
             previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A category sub-object. Unknown members of previous (for example extra) round-trip."""
    out = {"updatedAt": updated_at, "deviceId": device_id, "data": data}
    for key, value in (previous or {}).items():
        out.setdefault(key, value)
    return out


def validate_envelope(record: Any) -> Dict[str, Any]:
    """Reader rules 1 and 2 (schema section 3) for a whole record."""
    if not isinstance(record, dict):
        raise SchemaError("record must be an object")
    version = record.get("schemaVersion")
    if not _is_int(version):
        raise SchemaError("schemaVersion must be an integer")
    if version > SCHEMA_VERSION:
        raise SchemaError("record schemaVersion is newer than this plugin knows")
    if version < SCHEMA_VERSION:
        raise SchemaError("record schemaVersion predates the single-key layout")
    for name in ("deviceId", "platform", "appVersion"):
        if not isinstance(record.get(name), str):
            raise SchemaError(f"{name} must be a string")
    if not is_iso(record.get("updatedAt")):
        raise SchemaError("updatedAt must be ISO 8601 UTC")
    cats = record.get(CATEGORIES)
    if not isinstance(cats, dict):
        raise SchemaError("categories must be an object")
    for name, sub in cats.items():
        if name not in PHASE1_CATEGORIES:
            continue
        if not isinstance(sub, dict) or not is_iso(sub.get("updatedAt")) or not isinstance(sub.get("data"), dict):
            raise SchemaError("phase 1 category sub-object is malformed")
        validate_category_data(name, sub["data"])
    return record
