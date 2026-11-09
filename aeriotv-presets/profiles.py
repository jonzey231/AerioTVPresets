"""AerioTV profiles (schema section 4.12) built from the Profiles table.

Pure Python, no Django. A row is
[userId, username, displayName, pinType, pinHash, pinSalt, role, updatedAt, avatar, order].
The plugin never sets a PIN: a new profile is written without one and the user
sets it on a device. A PIN a device already saved for that user stays as it is.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

TABLE = "profiles_rows"
ROW_CAP = 25
NAME_MAX_BYTES = 40
PIN_TYPES = ("none", "numbers", "directions")
ROLES = ("admin", "user", "child")
ICONS = ("person", "face", "child", "paw", "cat", "fish", "star", "rocket", "music", "soccer", "gamepad", "movie")
COLORS = ("teal", "blue", "orange", "ember", "green", "purple", "slate", "sea")
DEFAULT_ICON = "default"
DEFAULT_COLOR = "default"


class ProfileError(ValueError):
    pass


def _clip_name(name: str) -> str:
    data = name.encode("utf-8")[:NAME_MAX_BYTES]
    return data.decode("utf-8", errors="ignore")


def table_defaults(target: str, existing_rows: List[Any]) -> List[Dict[str, Any]]:
    """Table rows that start from the record's profiles."""
    rows = []
    for r in sorted((r for r in existing_rows if isinstance(r, list) and len(r) >= 7),
                    key=lambda r: r[9] if len(r) > 9 and isinstance(r[9], int) else 0):
        avatar = r[8] if len(r) > 8 and isinstance(r[8], dict) else {}
        rows.append({"user": r[1], "name": r[2] or r[1], "role": r[6] if r[6] in ("user", "child") else "user",
                     "icon": avatar.get("icon") if avatar.get("icon") in ICONS else DEFAULT_ICON,
                     "color": avatar.get("color") if avatar.get("color") in COLORS else DEFAULT_COLOR})
    # With no profiles in the record the table starts empty, so an untouched
    # table writes nothing (Dispatcharr hands unsaved defaults to actions).
    return rows


def build_rows(table: Any, *, target: str, users: Dict[str, Tuple[int, bool]], existing_rows: List[Any],
               now: int) -> List[list]:
    """Profile rows for the record. users maps username to (user id, is Dispatcharr admin).

    A profile keeps the PIN a device saved for it; a new profile has none.
    The target user is always present (the default profile).
    """
    if not isinstance(table, list):
        return []
    by_user = {r[1]: r for r in existing_rows if isinstance(r, list) and len(r) >= 7}
    picked: List[Dict[str, Any]] = []
    seen = set()
    for row in table:
        if not isinstance(row, dict):
            continue
        name = str(row.get("user") or "").strip()
        if not name or name == "__none__":
            continue
        if name in seen:
            raise ProfileError(f"{name} is listed twice")
        if name not in users:
            raise ProfileError(f"{name} is not a Dispatcharr user")
        seen.add(name)
        picked.append(row)
    if not picked:
        return []
    if target not in seen:
        picked.insert(0, {"user": target})
    if len(picked) > ROW_CAP:
        raise ProfileError(f"at most {ROW_CAP} profiles")

    out: List[list] = []
    for order, row in enumerate(picked):
        username = str(row["user"]).strip()
        user_id, is_admin = users[username]
        role = "admin" if is_admin else (row.get("role") if row.get("role") in ("user", "child") else "user")
        old = by_user.get(username)
        if old is not None and old[3] in PIN_TYPES and old[3] != "none" and old[4] and old[5]:
            pin_type, pin_hash, pin_salt = old[3], old[4], old[5]
        else:
            pin_type, pin_hash, pin_salt = "none", "", ""
        avatar = {}
        if row.get("icon") in ICONS:
            avatar["icon"] = row["icon"]
        if row.get("color") in COLORS:
            avatar["color"] = row["color"]
        display = _clip_name(str(row.get("name") or "").strip() or username)
        stamp = now
        if old is not None and len(old) >= 10 and [old[2], old[3], old[4], old[5], old[6], old[8], old[9]] == \
                [display, pin_type, pin_hash, pin_salt, role, avatar, order]:
            stamp = old[7]  # unchanged row keeps its stamp, so devices see no edit
        out.append([user_id, username, display, pin_type, pin_hash, pin_salt, role, stamp, avatar, order])

    return out


def merge_rows(existing: Dict[str, Any], rows: List[list]) -> Dict[str, Any]:
    """Replace: the seeded rows replace rows for the same usernames; other rows
    and the removal tombstones stay, and a re-added user leaves `removed`."""
    data = dict(existing or {})
    seeded = {r[1] for r in rows}
    kept = [r for r in data.get("rows") or [] if isinstance(r, list) and len(r) > 1 and r[1] not in seeded]
    data["rows"] = rows + kept
    if isinstance(data.get("removed"), list):
        data["removed"] = [t for t in data["removed"]
                           if not (isinstance(t, list) and t and str(t[0]).lower() in {u.lower() for u in seeded})]
    return data


def validate(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise ProfileError("profiles must hold rows")
    for r in data["rows"]:
        if not (isinstance(r, list) and len(r) >= 10 and isinstance(r[0], int) and isinstance(r[1], str)
                and r[3] in PIN_TYPES and r[6] in ROLES and isinstance(r[8], dict) and isinstance(r[9], int)):
            raise ProfileError("profile row does not match the schema")
        if len(r[2].encode("utf-8")) > NAME_MAX_BYTES:
            raise ProfileError("profile name is too long")
        if r[3] == "none" and (r[4] or r[5]):
            raise ProfileError("a profile without a PIN has no hash")
        if r[3] != "none" and not (re.fullmatch(r"[0-9a-f]{64}", r[4]) and re.fullmatch(r"[0-9a-f]{32}", r[5])):
            raise ProfileError("PIN hash or salt is malformed")
    if len(data["rows"]) > ROW_CAP:
        raise ProfileError("too many profiles")
    return data
