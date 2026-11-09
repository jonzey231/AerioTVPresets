"""Build the plugin's settings fields from live Dispatcharr data.

Pure Python, no Django. Dispatcharr 0.33.0 renders only these field types
(frontend/src/components/Field.jsx:16-82): info, boolean, number, select,
text, and string, in one flat list (components/cards/PluginCard.jsx:44-53).
There is no multi-select and no field grouping, so lists are numbered selects
and sections are info headers that open with an Expand switch. Select options
are {"value", "label"} with non-empty strings (apps/plugins/serializers.py:18-20
rejects a blank value and the loader then drops the whole field), so "leave
empty" uses the NONE sentinel.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional

from . import app_settings

NONE = "__none__"
FAVORITE_SLOTS = 10
GROUP_ORDER_SLOTS = 8
MAX_CHANNEL_OPTIONS = 3000

SHOW_LIVE = "show_live:"
SHOW_MOVIES = "show_movies:"
SHOW_SERIES = "show_series:"

SECTIONS = (
    ("expand_live", "Live TV"),
    ("expand_movies", "Movies"),
    ("expand_series", "TV Shows"),
    ("expand_app", "App Settings"),
)
EXPAND_DEFAULTS = {"expand_live": True, "expand_movies": False, "expand_series": False, "expand_app": False}

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


def _info(fid: str, label: str, text: str = "") -> Dict[str, Any]:
    field = {"id": fid, "label": label, "type": "info"}
    if text:
        field["description"] = text
    return field


def _show_switches(prefix: str, names: Iterable[str]) -> List[Dict[str, Any]]:
    return [{"id": prefix + n, "label": f"Show {n}", "type": "boolean", "default": True} for n in names if n]


def expanded(saved: Dict[str, Any]) -> Dict[str, bool]:
    out = {}
    for key, default in EXPAND_DEFAULTS.items():
        value = saved.get(key, default)
        out[key] = value is True or value == "true"
    return out


def app_settings_fields() -> List[Dict[str, Any]]:
    fields: List[Dict[str, Any]] = []
    for title, rows in app_settings.SPEC:
        fields.append(_info("app_hdr:" + title, title))
        for name, label, kind, opts in rows:
            if kind == app_settings.BOOL:
                choices = [{"value": "true", "label": "On"}, {"value": "false", "label": "Off"}]
            else:
                choices = [{"value": app_settings.option_value(v), "label": l} for v, l in opts]
            fields.append(_select(app_settings.field_id(name), label, [dict(LEAVE_AS_IS)] + choices))
    return fields


def build_fields(manifest_fields: List[Dict[str, Any]], *, usernames: Optional[List[str]],
                 saved: Optional[Dict[str, Any]] = None, channels: Optional[List[Dict[str, Any]]] = None,
                 live_groups: Optional[List[str]] = None, movie_groups: Optional[List[str]] = None,
                 series_groups: Optional[List[str]] = None, native_sections: bool = False) -> List[Dict[str, Any]]:
    """Return the full field list.

    usernames None means the database was not reachable: the manifest fields
    come back unchanged. channels None means no user is chosen yet.

    native_sections True (a Dispatcharr build whose field serializer accepts the
    `section` type, newer than 0.33.0) emits collapsible section markers
    ({"type": "section", "collapsed": bool}) and tags each member field with
    "section": <marker id>; every section is built and the Expand switches are
    left out. False keeps the 0.33.0 layout: Expand switches and info headers.
    """
    if native_sections:
        return _build_native(manifest_fields, usernames=usernames, saved=saved, channels=channels,
                             live_groups=live_groups, movie_groups=movie_groups, series_groups=series_groups)
    if usernames is None:
        return [copy.deepcopy(f) for f in manifest_fields]
    base = {f["id"]: copy.deepcopy(f) for f in manifest_fields}
    saved = saved or {}
    selected = str(saved.get("target_username") or "").strip()
    if selected == NONE:
        selected = ""
    open_ = expanded(saved)

    out: List[Dict[str, Any]] = [base["intro"]]
    users = [u for u in usernames if u]
    if selected and selected not in users:
        users.insert(0, selected)
    out.append(_select("target_username", "User",
                       [{"value": NONE, "label": "Choose a user"}] + [{"value": u, "label": u} for u in users],
                       "The Dispatcharr user whose AerioTV setup this writes."))
    for key, _title in SECTIONS:
        out.append(base[key])

    for key, title in SECTIONS:
        if not open_[key]:
            out.append(_info("hdr:" + key, f"{title} (collapsed)",
                             f"Turn on Expand {title}, Save, and run Load to edit. Saved choices still apply."))
            continue
        out.append(_info("hdr:" + key, title))
        out.extend(_section_fields(key, base, channels, live_groups, movie_groups, series_groups))

    out.append(base["apply_mode"])
    return out


def hidden_from_switches(settings: Dict[str, Any]) -> Dict[str, List[str]]:
    """Groups whose Show switch is off, as hiddenGroups lists (switch on or absent = shown)."""
    out = {"live": [], "movies": [], "series": []}
    for prefix, kind in ((SHOW_LIVE, "live"), (SHOW_MOVIES, "movies"), (SHOW_SERIES, "series")):
        for key in sorted(settings):
            if key.startswith(prefix):
                value = settings[key]
                if value is False or value == "false":
                    name = key[len(prefix):]
                    if name and name not in out[kind]:
                        out[kind].append(name)
    return out


def _section_fields(key, base, channels, live_groups, movie_groups, series_groups) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if key == "expand_live":
        if channels is None:
            out.append(_info("live_note", "Lists", "Choose a user, Save, and run Load to pick favorites and groups."))
            out.append(base["group_order_mode"])
            return out
        live_opts = name_options(live_groups or [], LEAVE_EMPTY)
        out.append(_info("favorites_note", "Favorite channels", "In display order. Leave empty to skip a slot."))
        chan_opts = channel_options(channels)
        for i, fid in enumerate(slot_ids("favorite", FAVORITE_SLOTS), 1):
            out.append(_select(fid, f"Favorite {i}", chan_opts))
        out.append(base["group_order_mode"])
        for i, fid in enumerate(slot_ids("group", GROUP_ORDER_SLOTS), 1):
            out.append(_select(fid, f"Group position {i}", live_opts))
        out.append(_select("default_group", "Default group", name_options(live_groups or [], LEAVE_AS_IS),
                           "The Live TV group AerioTV opens to."))
        out.append(_info("live_groups_note", "Live TV groups",
                         "Turn a group off to hide it. The user can show it again in AerioTV."))
        out.extend(_show_switches(SHOW_LIVE, live_groups or []))
    elif key == "expand_movies":
        out.append(_info("movie_groups_note", "Movie categories",
                         "Turn a category off to hide it. The user can show it again in AerioTV."))
        out.extend(_show_switches(SHOW_MOVIES, movie_groups or []))
    elif key == "expand_series":
        out.append(_info("series_groups_note", "TV show categories",
                         "Turn a category off to hide it. The user can show it again in AerioTV."))
        out.extend(_show_switches(SHOW_SERIES, series_groups or []))
    else:
        out.extend(app_settings_fields())
    return out


# Native section ids and their collapsed default (Live TV open, the rest closed).
NATIVE_SECTIONS = (
    ("sec_live", "expand_live", "Live TV", False),
    ("sec_movies", "expand_movies", "Movies", True),
    ("sec_series", "expand_series", "TV Shows", True),
    ("sec_app", "expand_app", "App Settings", True),
)


def _build_native(manifest_fields, *, usernames, saved, channels, live_groups, movie_groups, series_groups):
    base = {f["id"]: copy.deepcopy(f) for f in manifest_fields}
    saved = saved or {}
    selected = str(saved.get("target_username") or "").strip()
    if selected == NONE:
        selected = ""
    intro = base["intro"]
    intro["description"] = ("1. Choose a user, Save, run Load, then reload this page. 2. Make your choices in each "
                            "section and Save. 3. Run Preview, then Apply. Anything left on Leave empty or Leave as "
                            "is is not written.")
    out: List[Dict[str, Any]] = [intro]
    users = [u for u in usernames if u]
    if selected and selected not in users:
        users.insert(0, selected)
    out.append(_select("target_username", "User",
                       [{"value": NONE, "label": "Choose a user"}] + [{"value": u, "label": u} for u in users],
                       "The Dispatcharr user whose AerioTV setup this writes."))
    for sec_id, key, title, collapsed in NATIVE_SECTIONS:
        out.append({"id": sec_id, "label": title, "type": "section", "collapsed": collapsed})
        for field in _section_fields(key, base, channels, live_groups, movie_groups, series_groups):
            field["section"] = sec_id
            out.append(field)
    out.append(base["apply_mode"])
    return out
