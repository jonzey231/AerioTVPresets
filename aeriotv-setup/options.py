"""Build the plugin's settings fields from live Dispatcharr data.

Pure Python, no Django. Dispatcharr 0.33.0 renders only these field types
(frontend/src/components/Field.jsx): info, boolean, number, select, text, and
string. There is no multi-select, so lists are repeated selects (Favorite 1,
Favorite 2, ...). Select options are {"value", "label"} with non-empty strings:
apps/plugins/serializers.py validates each option with CharField() (blank not
allowed) and drops the whole field when one option fails, so "leave empty" uses
the NONE sentinel instead of "".
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional

NONE = "__none__"
FAVORITE_SLOTS = 10
GROUP_ORDER_SLOTS = 8
HIDDEN_LIVE_SLOTS = 8
HIDDEN_VOD_SLOTS = 5
MAX_CHANNEL_OPTIONS = 3000

LEAVE_EMPTY = {"value": NONE, "label": "Leave empty"}
LEAVE_AS_IS = {"value": NONE, "label": "Leave as is"}


def slot_ids(prefix: str, count: int) -> List[str]:
    return [f"{prefix}_{i}" for i in range(1, count + 1)]


def channel_label(row: Dict[str, Any]) -> str:
    number = row.get("channel_number")
    if isinstance(number, float) and number.is_integer():
        number = int(number)
    head = f"{number} " if number is not None else ""
    group = row.get("group_name") or "no group"
    return f"{head}{row.get('name') or 'Unnamed'} [{group}]"


def channel_options(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    out = [dict(LEAVE_EMPTY)]
    for row in list(rows)[:MAX_CHANNEL_OPTIONS]:
        out.append({"value": str(row["id"]), "label": channel_label(row)})
    return out


def name_options(names: Iterable[str], first: Dict[str, str]) -> List[Dict[str, str]]:
    out = [dict(first)]
    for name in names:
        if name and name != NONE:
            out.append({"value": name, "label": name})
    return out


def _select(fid: str, label: str, options: List[Dict[str, str]], help_text: str = "") -> Dict[str, Any]:
    field = {"id": fid, "label": label, "type": "select", "default": options[0]["value"], "options": options}
    if help_text:
        field["help_text"] = help_text
    return field


def _info(fid: str, label: str, text: str) -> Dict[str, Any]:
    return {"id": fid, "label": label, "type": "info", "description": text}


def build_fields(manifest_fields: List[Dict[str, Any]], *, usernames: Optional[List[str]],
                 selected_user: str = "", channels: Optional[List[Dict[str, Any]]] = None,
                 live_groups: Optional[List[str]] = None, movie_groups: Optional[List[str]] = None,
                 series_groups: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Return the full field list.

    usernames None means the database was not reachable: the manifest fields
    come back unchanged (User stays a text box). channels None means no user
    lists are loaded yet: the list sections are replaced by a note.
    """
    base = {f["id"]: copy.deepcopy(f) for f in manifest_fields}
    if usernames is None:
        return [copy.deepcopy(f) for f in manifest_fields]

    out: List[Dict[str, Any]] = [base["intro"]]
    users = [u for u in usernames if u]
    if selected_user and selected_user not in users:
        users.insert(0, selected_user)
    out.append(_select("target_username", "User",
                       [{"value": NONE, "label": "Choose a user"}] + [{"value": u, "label": u} for u in users],
                       "The Dispatcharr user whose AerioTV setup this writes."))

    if channels is None:
        out.append(_info("lists_note", "Lists", "Choose a user, save, run Load User Lists, then reload this page to pick favorites and groups."))
        out.append(base["group_order_mode"])
    else:
        chan_opts = channel_options(channels)
        live_opts = name_options(live_groups or [], LEAVE_EMPTY)
        out.append(_info("favorites_note", "Favorite channels", "In display order. Leave empty to skip a slot."))
        for i, fid in enumerate(slot_ids("favorite", FAVORITE_SLOTS), 1):
            out.append(_select(fid, f"Favorite {i}", chan_opts))
        out.append(base["group_order_mode"])
        for i, fid in enumerate(slot_ids("group", GROUP_ORDER_SLOTS), 1):
            out.append(_select(fid, f"Group position {i}", live_opts))
        out.append(_info("hidden_note", "Hidden groups", "Groups AerioTV hides for this user."))
        for i, fid in enumerate(slot_ids("hidden_live", HIDDEN_LIVE_SLOTS), 1):
            out.append(_select(fid, f"Hidden Live TV group {i}", live_opts))
        movie_opts = name_options(movie_groups or [], LEAVE_EMPTY)
        for i, fid in enumerate(slot_ids("hidden_movies", HIDDEN_VOD_SLOTS), 1):
            out.append(_select(fid, f"Hidden movie group {i}", movie_opts))
        series_opts = name_options(series_groups or [], LEAVE_EMPTY)
        for i, fid in enumerate(slot_ids("hidden_series", HIDDEN_VOD_SLOTS), 1):
            out.append(_select(fid, f"Hidden series group {i}", series_opts))
        out.append(_select("default_group", "Default group", name_options(live_groups or [], LEAVE_AS_IS),
                           "The Live TV group AerioTV opens to."))

    out.append(base["selected_theme"])
    out.append(base["appearance_mode"])
    out.append(base["apply_mode"])
    return out
