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

# Multiselect fields (dev-branch Dispatcharr): selected values are hidden names.
HIDDEN_LIVE = "hidden_live"
HIDDEN_MOVIES = "hidden_movies"
HIDDEN_SERIES = "hidden_series"
# Above this many Live TV groups, one multiselect replaces the per-group switches.
LIVE_SWITCH_LIMIT = 25
VOD_SCOPE_NOTE = ("Lists categories from the server's active M3U accounts that are enabled for VOD, and only "
                  "the types this user may watch. Dispatcharr has no per-user category rule beyond that.")

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


def app_settings_fields(current: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    fields: List[Dict[str, Any]] = []
    for title, rows in app_settings.SPEC:
        fields.append(_info("app_hdr:" + title, title))
        for name, label, kind, opts in rows:
            if kind == app_settings.BOOL:
                choices = [{"value": "true", "label": "On"}, {"value": "false", "label": "Off"}]
            else:
                choices = [{"value": app_settings.option_value(v), "label": l} for v, l in opts]
            field = _select(app_settings.field_id(name), label, [dict(LEAVE_AS_IS)] + choices)
            now = _setting_now(current or {}, name)
            if name == "appearanceMode" and now == "dark" and _setting_now(current or {}, "trueBlack") is True:
                now = "True Black"
            elif opts and now is not None:
                now = next((l for v, l in opts if v == now and type(v) is type(now)), now)
            fields.append(_with_now(field, now))
    return fields


def build_fields(manifest_fields: List[Dict[str, Any]], *, usernames: Optional[List[str]],
                 saved: Optional[Dict[str, Any]] = None, channels: Optional[List[Dict[str, Any]]] = None,
                 live_groups: Optional[List[str]] = None, movie_groups: Optional[List[str]] = None,
                 series_groups: Optional[List[str]] = None, native_sections: bool = False,
                 tables: bool = False, current: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
                             live_groups=live_groups, movie_groups=movie_groups, series_groups=series_groups,
                             tables=tables, current=current)
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
                             f"Turn on Expand {title}, Save, and run Refresh Lists to edit. Saved choices still apply."))
            continue
        out.append(_info("hdr:" + key, title))
        out.extend(_section_fields(key, base, channels, live_groups, movie_groups, series_groups))

    out.append(base["apply_mode"])
    return out


def hidden_from_switches(settings: Dict[str, Any]) -> Dict[str, List[str]]:
    """Hidden groups as hiddenGroups lists: the multiselect picks first, then every
    Show switch that is off (switch on or absent = shown)."""
    out = {"live": [], "movies": [], "series": []}
    for fid, kind in ((HIDDEN_LIVE, "live"), (HIDDEN_MOVIES, "movies"), (HIDDEN_SERIES, "series")):
        picked = settings.get(fid)
        if isinstance(picked, list):
            for name in picked:
                if isinstance(name, str) and name and name != NONE and name not in out[kind]:
                    out[kind].append(name)
    for prefix, kind in ((SHOW_LIVE, "live"), (SHOW_MOVIES, "movies"), (SHOW_SERIES, "series")):
        for key in sorted(settings):
            if key.startswith(prefix):
                value = settings[key]
                if value is False or value == "false":
                    name = key[len(prefix):]
                    if name and name not in out[kind]:
                        out[kind].append(name)
    return out


def _multiselect(fid: str, label: str, names: Iterable[str], help_text: str) -> Dict[str, Any]:
    return {"id": fid, "label": label, "type": "multiselect", "default": [], "help_text": help_text,
            "options": [{"value": n, "label": n} for n in names if n and n != NONE]}


def _section_fields(key, base, channels, live_groups, movie_groups, series_groups,
                    multiselect: bool = False, tables: bool = False,
                    current: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """current: the user's record as {category: data}, used for "Now:" hints and
    table defaults. tables: the build supports `table` fields (dev branch)."""
    current = current or {}
    out: List[Dict[str, Any]] = []
    if key == "expand_live":
        if channels is None:
            out.append(_info("live_note", "Lists", "Choose a user, Save, then run Refresh Lists and reload the page to fill these lists."))
            out.append(base["group_order_mode"])
            return out
        live_opts = name_options(live_groups or [], LEAVE_EMPTY)
        chan_opts = channel_options(channels)
        if tables:
            out.append(_favorites_table(chan_opts, current.get("favorites") or {}))
            out.append(_with_now(base["group_order_mode"], (current.get("groupOrder") or {}).get("mode")))
            out.append(_group_table(live_opts, current.get("groupOrder") or {}))
        else:
            out.append(_info("favorites_note", "Favorite channels", "In display order. Leave empty to skip a slot."))
            for i, fid in enumerate(slot_ids("favorite", FAVORITE_SLOTS), 1):
                out.append(_select(fid, f"Favorite {i}", chan_opts))
            out.append(base["group_order_mode"])
            for i, fid in enumerate(slot_ids("group", GROUP_ORDER_SLOTS), 1):
                out.append(_select(fid, f"Group position {i}", live_opts))
        out.append(_with_now(_select("default_group", "Default group", name_options(live_groups or [], LEAVE_AS_IS),
                                     "The Live TV group AerioTV opens to."),
                             _setting_now(current, "defaultGroup")))
        if multiselect and len(live_groups or []) > LIVE_SWITCH_LIMIT:
            out.append(_multiselect(HIDDEN_LIVE, "Hidden Live TV groups", live_groups or [],
                                    "Pick the groups to hide. The user can show them again in AerioTV."))
        else:
            out.append(_info("live_groups_note", "Live TV groups",
                             "Turn a group off to hide it. The user can show it again in AerioTV."))
            out.extend(_show_switches(SHOW_LIVE, live_groups or []))
    elif key in ("expand_movies", "expand_series"):
        movies = key == "expand_movies"
        names = (movie_groups if movies else series_groups) or []
        if channels is None:
            out.append(_info("movies_note" if movies else "series_note", "Lists",
                             "Choose a user, Save, then run Refresh Lists and reload the page to fill these lists."))
        elif multiselect:
            out.append(_multiselect(HIDDEN_MOVIES if movies else HIDDEN_SERIES,
                                    "Hidden movie categories" if movies else "Hidden series categories", names,
                                    "Pick the categories to hide. The user can show them again in AerioTV. "
                                    + VOD_SCOPE_NOTE))
        else:
            out.append(_info("movie_groups_note" if movies else "series_groups_note",
                             "Movie categories" if movies else "TV show categories",
                             "Turn a category off to hide it. The user can show it again in AerioTV. "
                             + VOD_SCOPE_NOTE))
            out.extend(_show_switches(SHOW_MOVIES if movies else SHOW_SERIES, names))
    else:
        out.extend(app_settings_fields(current))
    return out


FAVORITES_TABLE = "favorites_rows"
GROUP_ORDER_TABLE = "group_order_rows"


def _favorites_table(chan_opts: List[Dict[str, str]], now: Dict[str, Any]) -> Dict[str, Any]:
    known = {o["value"] for o in chan_opts}
    rows = [{"channel": str(i)} for i in (now.get("ids") or []) if str(i) in known]
    return {"id": FAVORITES_TABLE, "label": "Favorite channels", "type": "table",
            "help_text": "One row per favorite, in display order. Starts from what the record holds now.",
            "default": rows,
            "columns": [{"id": "channel", "label": "Channel", "type": "select", "options": chan_opts[1:]}]}


def _group_table(live_opts: List[Dict[str, str]], now: Dict[str, Any]) -> Dict[str, Any]:
    known = {o["value"] for o in live_opts}
    rows = [{"group": g} for g in (now.get("order") or []) if g in known] if now.get("mode") == "manual" else []
    return {"id": GROUP_ORDER_TABLE, "label": "Manual group order", "type": "table",
            "help_text": "One row per group, first to last. Used when Group order is Manual.",
            "default": rows,
            "columns": [{"id": "group", "label": "Group", "type": "select", "options": live_opts[1:]}]}


def _setting_now(current: Dict[str, Any], name: str) -> Any:
    lane = ((current.get("settings") or {}).get("v")) or {}
    return lane.get(name)


def _with_now(field: Dict[str, Any], value: Any) -> Dict[str, Any]:
    """Add "In the record now: <value>" to a field's help text."""
    if value is None or value == "":
        return field
    shown = ("On" if value else "Off") if isinstance(value, bool) else str(value)
    note = f"In the record now: {shown}."
    field["help_text"] = (field.get("help_text", "") + " " + note).strip()
    return field


# Native section ids and their collapsed default (Live TV open, the rest closed).
NATIVE_SECTIONS = (
    ("sec_live", "expand_live", "Live TV", False),
    ("sec_movies", "expand_movies", "Movies", True),
    ("sec_series", "expand_series", "TV Shows", True),
    ("sec_app", "expand_app", "App Settings", True),
)


def _build_native(manifest_fields, *, usernames, saved, channels, live_groups, movie_groups, series_groups,
                  tables=False, current=None):
    base = {f["id"]: copy.deepcopy(f) for f in manifest_fields}
    saved = saved or {}
    selected = str(saved.get("target_username") or "").strip()
    if selected == NONE:
        selected = ""
    intro = base["intro"]
    intro["description"] = ("1. Choose a user, Save, run Refresh Lists, then reload this page. 2. Make your choices in each "
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
        for field in _section_fields(key, base, channels, live_groups, movie_groups, series_groups,
                                     multiselect=True, tables=tables, current=current):
            field["section"] = sec_id
            out.append(field)
    # Dispatcharr renders fields outside a section above every section
    # (frontend/src/components/PluginFieldList.jsx), so Apply mode gets its own
    # open section to sit last.
    out.append({"id": "sec_apply", "label": "Apply", "type": "section", "collapsed": False})
    apply_mode = base["apply_mode"]
    apply_mode["section"] = "sec_apply"
    out.append(apply_mode)
    return out
