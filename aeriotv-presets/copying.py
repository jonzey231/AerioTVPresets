"""Copy from a user: turn a source user's AerioTV record into this plugin's
saved settings, so the admin can adjust the choices and Apply them to the target.

Pure Python, no Django. The source record is only read. Channel ids and group
names are kept only when the target user can see them; the rest are dropped and
counted in the report. A TMDB API key the source holds is copied into the key
field; the report names it but never shows it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from . import app_settings, options, schema


@dataclass
class CopyReport:
    copied: List[str] = field(default_factory=list)
    dropped_channels: int = 0
    dropped_groups: int = 0
    dropped_settings: int = 0

    def text(self, source: str) -> str:
        if not self.copied:
            return f"{source} has no AerioTV choices to copy."
        out = f"Copied {', '.join(self.copied)} from {source}."
        dropped = []
        if self.dropped_channels:
            dropped.append(options.plural(self.dropped_channels, "channel"))
        if self.dropped_groups:
            dropped.append(options.plural(self.dropped_groups, "group"))
        if self.dropped_settings:
            dropped.append(options.plural(self.dropped_settings, "setting"))
        if dropped:
            out += " Skipped " + ", ".join(dropped) + " the target cannot use."
        return out


def _data(record: Optional[Dict[str, Any]], name: str) -> Dict[str, Any]:
    sub = ((record or {}).get(schema.CATEGORIES) or {}).get(name)
    data = sub.get("data") if isinstance(sub, dict) else None
    return data if isinstance(data, dict) else {}


def record_to_settings(record: Optional[Dict[str, Any]], *, channel_ids: Iterable[int],
                       live_groups: Iterable[str], movie_groups: Iterable[str],
                       series_groups: Iterable[str]) -> "tuple[Dict[str, Any], CopyReport]":
    """Settings entries that prefill every section from a record.

    Both control styles are written (tables and slots, multiselects and Show
    switches) so the prefill works whichever controls this Dispatcharr shows;
    Dispatcharr drops keys with no matching field on the next Save.
    """
    report = CopyReport()
    out: Dict[str, Any] = {}
    visible_ids = set(channel_ids)
    live = list(live_groups)
    live_set = set(live)

    fav = _data(record, schema.FAVORITES)
    if fav.get("ids"):
        ids = [i for i in fav["ids"] if isinstance(i, int) and not isinstance(i, bool)]
        kept = [i for i in ids if i in visible_ids]
        report.dropped_channels += len(ids) - len(kept)
        out[options.FAVORITES_TABLE] = [{"channel": str(i)} for i in kept]
        for n in range(1, options.FAVORITE_SLOTS + 1):
            out[f"favorite_{n}"] = str(kept[n - 1]) if n <= len(kept) else options.NONE
        report.copied.append(f"favorites ({len(kept)})")

    order = _data(record, schema.GROUP_ORDER)
    if order.get("mode") in schema.GROUP_ORDER_MODES:
        names = [g for g in order.get("order") or [] if isinstance(g, str)]
        kept = [g for g in names if g in live_set]
        report.dropped_groups += len(names) - len(kept)
        out["group_order_mode"] = order["mode"]
        out[options.GROUP_ORDER_TABLE] = [{"group": g} for g in kept]
        for n in range(1, options.GROUP_ORDER_SLOTS + 1):
            out[f"group_{n}"] = kept[n - 1] if n <= len(kept) else options.NONE
        report.copied.append("group order")

    hidden = _data(record, schema.HIDDEN_GROUPS)
    if hidden:
        total = 0
        for kind, prefix, multi, offered in (
            ("live", options.SHOW_LIVE, options.HIDDEN_LIVE, live),
            ("movies", options.SHOW_MOVIES, options.HIDDEN_MOVIES, list(movie_groups)),
            ("series", options.SHOW_SERIES, options.HIDDEN_SERIES, list(series_groups)),
        ):
            names = [g for g in hidden.get(kind) or [] if isinstance(g, str)]
            offered_set = set(offered)
            kept = [g for g in names if g in offered_set]
            report.dropped_groups += len(names) - len(kept)
            total += len(kept)
            out[multi] = kept
            for g in offered:
                out[prefix + g] = g not in kept
        report.copied.append(f"hidden groups ({total})")

    lane = _data(record, schema.SETTINGS).get("v")
    if isinstance(lane, dict) and lane:
        count = 0
        for name, value in lane.items():
            if name == "trueBlack":
                continue
            if name == "defaultGroup":
                if isinstance(value, str) and value in live_set:
                    out["default_group"] = value
                    count += 1
                else:
                    report.dropped_settings += 1
                continue
            if name not in app_settings.BY_NAME:
                continue
            if name == "appearanceMode" and value == "dark" and lane.get("trueBlack") is True:
                out[app_settings.field_id(name)] = app_settings.TRUE_BLACK
                count += 1
                continue
            if not app_settings.is_valid(name, value):
                report.dropped_settings += 1
                continue
            kind, _ = app_settings.BY_NAME[name]
            out[app_settings.field_id(name)] = ("true" if value else "false") if kind == app_settings.BOOL \
                else app_settings.option_value(value)
            count += 1
        if count:
            report.copied.append(f"settings ({count})")

    key = schema.tmdb_api_key(_data(record, schema.TMDB_KEY))
    if key:
        try:
            schema.validate_tmdb_key({"apiKey": key})
        except schema.SchemaError:
            report.dropped_settings += 1
        else:
            out[options.TMDB_KEY_FIELD] = key
            out[options.TMDB_CLEAR_FIELD] = False
            report.copied.append("TMDB API key")
    return out, report
