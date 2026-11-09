"""AerioTV Setup: Dispatcharr plugin entry point.

Dispatcharr calls Plugin.run(action, params, context) when an admin clicks an
action. The UI sends no params; every input is a saved plugin setting, read
from context["settings"]. Field and action declarations live in plugin.json.
"""

from __future__ import annotations

import copy
import json
import logging
import os

from . import dispatcharr_bridge as bridge
from . import schema, seed

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "plugin.json"), "r", encoding="utf-8") as _fh:
    _MANIFEST = json.load(_fh)

LIST_LIMIT = 300
_log = logging.getLogger("plugins.aeriotv_setup")


def _user_field(field):
    """Turn the User text box into a dropdown of Dispatcharr users when possible.

    Dispatcharr reads Plugin.fields when the plugin loads, so the list refreshes
    on a plugin reload. On any failure the text box stays.
    """
    try:
        names = bridge.usernames()
    except Exception:
        return field
    if not names:
        return field
    out = dict(field)
    out["type"] = "select"
    out["options"] = [{"value": "", "label": "Choose a user"}] + [{"value": n, "label": n} for n in names]
    out.pop("placeholder", None)
    return out


class Plugin:
    name = _MANIFEST["name"]
    version = _MANIFEST["version"]
    description = _MANIFEST["description"]
    author = _MANIFEST["author"]
    help_url = _MANIFEST.get("help_url", "")
    actions = _MANIFEST["actions"]

    @property
    def fields(self):
        fields = copy.deepcopy(_MANIFEST["fields"])
        return [(_user_field(f) if f.get("id") == "target_username" else f) for f in fields]

    def run(self, action, params, context):
        logger = (context or {}).get("logger") or _log
        settings = (context or {}).get("settings") or {}
        handler = {
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
        username = (settings.get("target_username") or "").strip()
        if not username:
            raise seed.SeedError("choose a user first")
        return bridge.find_user(username)

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
