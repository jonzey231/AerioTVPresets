"""AerioTV Setup: Dispatcharr plugin entry point.

Dispatcharr calls Plugin.run(action, params, context) when an admin clicks an
action. The UI sends no params; every input is a saved plugin setting, read
from context["settings"]. Field and action declarations live in plugin.json.
"""

from __future__ import annotations

import json
import logging
import os
import re

from . import dispatcharr_bridge as bridge
from . import options, schema, seed

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "plugin.json"), "r", encoding="utf-8") as _fh:
    _MANIFEST = json.load(_fh)

LIST_LIMIT = 300
_log = logging.getLogger("plugins.aeriotv_setup")


def _plugin_key() -> str:
    """The key Dispatcharr installs this folder under (apps/plugins/api_views.py _sanitize_plugin_key)."""
    base = os.path.basename(_HERE).replace(" ", "_").replace("-", "_").lower()
    return re.sub(r"[^a-z0-9_]", "_", base).strip("._ ") or "plugin"


def _live_fields():
    """Fields with users, channels, and groups read from the database now.

    Dispatcharr reads this when it loads the plugin. Any failure (for example no
    database yet) falls back to the manifest fields.
    """
    manifest_fields = _MANIFEST["fields"]
    try:
        names = bridge.usernames()
    except Exception:
        return options.build_fields(manifest_fields, usernames=None)
    saved = {}
    native = False
    try:
        native = bridge.supports_sections()
    except Exception:
        native = False
    channels = live = None
    vod = {"movie": [], "series": []}
    try:
        saved = bridge.saved_settings(_plugin_key())
        selected = str(saved.get("target_username") or "").strip()
        if selected and selected != seed.NONE:
            user = bridge.find_user(selected)
            channels = bridge.visible_channels(user)
            live = bridge.visible_group_names(user)
            vod = bridge.vod_group_names(user)
    except Exception:
        _log.warning("[AERIOTV-SETUP] could not load lists for the chosen user")
        channels = live = None
    return options.build_fields(
        manifest_fields, usernames=names, saved=saved,
        channels=channels, live_groups=live,
        movie_groups=vod.get("movie"), series_groups=vod.get("series"),
        native_sections=native,
    )


class Plugin:
    name = _MANIFEST["name"]
    version = _MANIFEST["version"]
    description = _MANIFEST["description"]
    author = _MANIFEST["author"]
    help_url = _MANIFEST.get("help_url", "")
    actions = _MANIFEST["actions"]

    @property
    def fields(self):
        return _live_fields()

    def run(self, action, params, context):
        logger = (context or {}).get("logger") or _log
        settings = (context or {}).get("settings") or {}
        handler = {
            "load_lists": self._load_lists,
            "show_channels": self._show_channels,
            "show_groups": self._show_groups,
            "preview": lambda s, lg: self._apply(s, lg, write=False),
            "apply": lambda s, lg: self._apply(s, lg, write=True),
        }.get(action)
        if handler is None:
            return {"status": "error", "message": "Unknown action"}
        try:
            return handler(settings, logger)
        except (seed.SeedError, schema.SchemaError) as exc:
            return {"status": "error", "message": str(exc)}
        except bridge.BridgeError as exc:
            logger.warning("[AERIOTV-SETUP] %s failed: %s (%s)", action, exc.code, exc.status)
            return {"status": "error", "message": f"{exc} ({exc.code})"}

    # ------------------------------------------------------------ actions

    def _target(self, settings):
        username = str(settings.get("target_username") or "").strip()
        if not username or username == seed.NONE:
            raise seed.SeedError("choose a user first")
        return bridge.find_user(username)

    def _load_lists(self, settings, logger):
        user = self._target(settings)
        count = len(bridge.visible_channels(user))
        bridge.request_field_refresh()
        logger.info("[AERIOTV-SETUP] lists requested for user %s: %d channels", user.pk, count)
        return {"status": "ok", "message": f"Loaded {count} channels for this user. Reload the page to see the expanded sections."}

    def _show_channels(self, settings, logger):
        user = self._target(settings)
        rows = bridge.visible_channels(user)
        lines = []
        for row in rows[:LIST_LIMIT]:
            number = row.get("channel_number")
            number = "" if number is None else (f"{number:g} " if isinstance(number, float) else f"{number} ")
            group = row.get("group_name") or "no group"
            lines.append(f"{row['id']}: {number}{row['name']} [{group}]")
        more = len(rows) - len(lines)
        if more > 0:
            lines.append(f"and {more} more")
        logger.info("[AERIOTV-SETUP] listed channels for user %s: %d", user.pk, len(rows))
        return {"status": "ok", "message": "\n".join(lines) or "This user cannot see any channels."}

    def _show_groups(self, settings, logger):
        user = self._target(settings)
        names = bridge.visible_group_names(user)
        logger.info("[AERIOTV-SETUP] listed groups for user %s: %d", user.pk, len(names))
        return {"status": "ok", "message": "\n".join(names) or "This user cannot see any groups."}

    def _apply(self, settings, logger, *, write):
        request = seed.parse_settings(settings)
        if not request.categories:
            raise seed.SeedError("nothing to apply: fill in at least one section")
        user = bridge.find_user(request.username)
        key = schema.user_key(user.username)
        if key is None:
            raise seed.SeedError("this user has no AerioTV record name")

        fav = request.categories.get(schema.FAVORITES)
        if fav:
            visible = {row["id"] for row in bridge.visible_channels(user)}
            unknown = [i for i in fav["ids"] if i not in visible]
            if unknown:
                raise seed.SeedError(
                    f"{len(unknown)} favorite id(s) are not channels this user can see: "
                    + ", ".join(str(i) for i in unknown[:20])
                )

        hidden = request.categories.get(schema.HIDDEN_GROUPS)
        if hidden:
            # Choices saved for a previously chosen user can name groups this user never sees.
            if hidden.get("live"):
                visible_groups = set(bridge.visible_group_names(user))
                hidden["live"] = [g for g in hidden["live"] if g in visible_groups]
            if hidden.get("movies") or hidden.get("series"):
                vod = bridge.vod_group_names(user)
                hidden["movies"] = [g for g in hidden.get("movies", []) if g in set(vod["movie"])]
                hidden["series"] = [g for g in hidden.get("series", []) if g in set(vod["series"])]
            if not any(hidden.values()):
                del request.categories[schema.HIDDEN_GROUPS]
        if not request.categories:
            raise seed.SeedError("nothing to apply: fill in at least one section")

        keys = bridge.list_keys(user)
        blocked, _legacy = seed.legacy_conflict(keys, key)
        if blocked:
            raise seed.SeedError(
                "this user has an older AerioTV record that a device has not moved yet; "
                "open AerioTV on one of their devices with Dispatcharr Sync on, then try again"
            )

        existing = bridge.read_record(user, key)
        result = seed.merge(existing, request.categories, mode=request.mode, app_version=self.version)
        parts = []
        if result.added:
            parts.append("adds " + ", ".join(result.added))
        if result.replaced:
            parts.append("replaces " + ", ".join(result.replaced))
        if result.kept:
            parts.append("keeps the device copy of " + ", ".join(result.kept))
        plan = "; ".join(parts) or "no change"

        if not write:
            before = seed.describe(seed.summarize(existing))
            return {"status": "ok", "message": f"Preview ({request.mode}): {plan}. Today the {before}."}
        if not result.changed:
            return {"status": "ok", "message": f"Nothing written: {plan}."}
        size = bridge.write_record(user, key, result.record)
        logger.info(
            "[AERIOTV-SETUP] wrote record for user %s: mode=%s added=%d replaced=%d bytes=%d",
            user.pk, request.mode, len(result.added), len(result.replaced), size,
        )
        return {"status": "ok", "message": f"Applied ({request.mode}): {plan}. Their AerioTV devices pick it up on the next sync."}
