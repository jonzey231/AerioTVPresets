"""AerioTV Presets: Dispatcharr plugin entry point.

Dispatcharr calls Plugin.run(action, params, context) when an admin clicks an
action. The UI sends no params; every input is a saved plugin setting, read
from context["settings"]. Field and action declarations live in plugin.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

from . import dispatcharr_bridge as bridge
from . import copying, options, profiles, schema, seed

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "plugin.json"), "r", encoding="utf-8") as _fh:
    _MANIFEST = json.load(_fh)

_log = logging.getLogger("plugins.aeriotv_presets")


# Keys earlier builds were installed under (named AerioTV Setup), so saved
# settings carry over when an old install is replaced.
_OLD_KEYS = ("aeriotv-setup", "aeriotv_setup")


def _plugin_keys() -> list:
    """Keys this folder may be installed under. Newer Dispatcharr builds keep the
    folder name as the key ("aeriotv-presets", as /api/plugins/plugins/ reports it);
    older ones sanitize it to "aeriotv_presets" (apps/plugins/api_views.py
    _sanitize_plugin_key). Try the folder name first, then the old names."""
    folder = os.path.basename(_HERE)
    base = folder.replace(" ", "_").replace("-", "_").lower()
    sanitized = re.sub(r"[^a-z0-9_]", "_", base).strip("._ ") or "plugin"
    return [k for k in dict.fromkeys([folder, folder.lower(), sanitized, *_OLD_KEYS]) if k]


def _saved_settings() -> dict:
    for key in _plugin_keys():
        saved = bridge.saved_settings(key)
        if saved:
            return saved
    return {}


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
    native = tables = False
    try:
        native = bridge.supports_sections()
        tables = bridge.supports_tables()
    except Exception:
        native = tables = False
    current = {}
    channels = live = None
    vod = {"movie": [], "series": []}
    try:
        saved = _saved_settings()
        selected = str(saved.get("target_username") or "").strip()
        if selected and selected != seed.NONE:
            user = bridge.find_user(selected)
            channels = bridge.visible_channels(user)
            live = bridge.visible_group_names(user)
            vod = bridge.vod_group_names(user)
            try:
                key = schema.user_key(user.username)
                record = bridge.read_record(user, key) if key else None
                cats = (record or {}).get(schema.CATEGORIES) if isinstance(record, dict) else None
                current = {name: (sub.get("data") or {}) for name, sub in (cats or {}).items()
                           if isinstance(sub, dict) and isinstance(sub.get("data"), dict)}
                current[options.RECORD_PRESENT] = isinstance(record, dict)
            except Exception:
                current = {}
    except Exception:
        _log.warning("[AERIOTV-PRESETS] could not load lists for the chosen user")
        channels = live = None
    return options.build_fields(
        manifest_fields, usernames=names, saved=saved,
        channels=channels, live_groups=live,
        movie_groups=vod.get("movie"), series_groups=vod.get("series"),
        native_sections=native, tables=tables, current=current,
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
            "preview": lambda s, lg: self._apply(s, lg, write=False),
            "apply": lambda s, lg: self._apply(s, lg, write=True),
        }.get(action)
        if handler is None:
            raise ActionError("Unknown action.")
        try:
            return handler(settings, logger)
        except (seed.SeedError, schema.SchemaError, profiles.ProfileError) as exc:
            logger.info("[AERIOTV-PRESETS] %s refused: %s", action, exc)
            raise ActionError(_sentence(str(exc))) from None
        except bridge.BridgeError as exc:
            logger.warning("[AERIOTV-PRESETS] %s failed: %s (%s)", action, exc.code, exc.status)
            raise ActionError(_sentence(f"{exc} ({exc.code})")) from None

    # ------------------------------------------------------------ actions

    def _target(self, settings):
        username = str(settings.get("target_username") or "").strip()
        if not username or username == seed.NONE:
            raise seed.SeedError("choose a user first")
        return bridge.find_user(username)

    def _load_lists(self, settings, logger):
        user = self._target(settings)
        channel_rows = bridge.visible_channels(user)
        live = bridge.visible_group_names(user)
        message = f"Loaded {len(channel_rows)} channels and {len(live)} groups for {user.username}."
        source_name = str(settings.get(options.COPY_FROM) or "").strip()
        if source_name and source_name != seed.NONE and source_name != user.username:
            source = bridge.find_user(source_name)
            key = schema.user_key(source.username)
            record = bridge.read_record(source, key) if key else None
            vod = bridge.vod_group_names(user)
            updates, report = copying.record_to_settings(
                record, channel_ids=[r["id"] for r in channel_rows], live_groups=live,
                movie_groups=vod["movie"], series_groups=vod["series"])
            updates[options.COPY_FROM] = seed.NONE
            bridge.update_saved_settings(_plugin_keys(), updates)
            logger.info("[AERIOTV-PRESETS] copied user %s into the form for user %s: %s; dropped channels=%d groups=%d settings=%d",
                        source.pk, user.pk, ",".join(report.copied) or "-", report.dropped_channels,
                        report.dropped_groups, report.dropped_settings)
            message = report.text(source.username)
        bridge.request_field_refresh()
        logger.info("[AERIOTV-PRESETS] lists requested for user %s: channels=%d groups=%d", user.pk, len(channel_rows), len(live))
        return {"status": "ok", "message": message + " Reload the page."}

    def _apply(self, settings, logger, *, write):
        request = seed.parse_settings(settings)
        primary = bridge.find_user(request.username)
        table = settings.get(profiles.TABLE)
        if isinstance(table, list) and table:
            key = schema.user_key(primary.username)
            record = bridge.read_record(primary, key) if key else None
            sub = ((record or {}).get(schema.CATEGORIES) or {}).get(schema.PROFILES) if isinstance(record, dict) else None
            existing = ((sub or {}).get("data") or {}).get("rows") or [] if isinstance(sub, dict) else []
            names = [str(r.get("user")) for r in table if isinstance(r, dict) and r.get("user")]
            rows = profiles.build_rows(table, target=primary.username,
                                       users=bridge.user_infos(names + [primary.username]),
                                       existing_rows=existing, now=int(time.time()))
            if rows:
                request.profiles = {"rows": rows}
        if not request.categories and not request.profiles:
            raise seed.SeedError("nothing to apply; set at least one section")
        also = settings.get(options.ALSO_USERS)
        names = [n for n in (also if isinstance(also, list) else []) if isinstance(n, str) and n and n != primary.username]
        targets = [primary] + [bridge.find_user(n) for n in dict.fromkeys(names)]
        if len(targets) == 1:
            outcome = self._apply_one(primary, request, logger, write=write, primary=True)
            if write and outcome["changed"] and request.profiles:
                bridge.update_saved_settings(_plugin_keys(), {profiles.TABLE: profiles.clear_pins(table)})
            return {"status": "ok", "message": outcome["toast"]}
        changed = unchanged = failed = 0
        for user in targets:
            try:
                outcome = self._apply_one(user, request, logger, write=write, primary=user is primary)
            except (seed.SeedError, schema.SchemaError, bridge.BridgeError) as exc:
                failed += 1
                logger.info("[AERIOTV-PRESETS] %s for user %s failed: %s",
                            "apply" if write else "preview", user.pk, getattr(exc, "code", None) or exc)
                continue
            if outcome["changed"]:
                changed += 1
            else:
                unchanged += 1
        if write and changed and request.profiles:
            bridge.update_saved_settings(_plugin_keys(), {profiles.TABLE: profiles.clear_pins(table)})
        return {"status": "ok", "message": seed.many_toast(request.mode, write=write, changed=changed,
                                                           unchanged=unchanged, failed=failed)}

    def _apply_one(self, user, request, logger, *, write, primary=False):
        key = schema.user_key(user.username)
        if key is None:
            raise seed.SeedError("this user has no AerioTV record name")
        vod = bridge.vod_group_names(user)
        cats, dropped_channels, dropped_groups = seed.scope_to_target(
            request.categories, channel_ids=[r["id"] for r in bridge.visible_channels(user)],
            live_groups=bridge.visible_group_names(user), movie_groups=vod["movie"], series_groups=vod["series"])
        if primary and request.profiles:
            # Profiles belong to the main User's devices only.
            cats[schema.PROFILES] = request.profiles
        if not cats:
            if not primary:
                logger.info("[AERIOTV-PRESETS] nothing to write for user %s", user.pk)
                return {"changed": False, "toast": ""}
            raise seed.SeedError(f"nothing {user.username} can use; run Refresh Lists")

        blocked, _legacy = seed.legacy_conflict(bridge.list_keys(user), key)
        if blocked:
            raise seed.SeedError("an older AerioTV record must move first; open AerioTV as this user with Dispatcharr Sync on")

        existing = bridge.read_record(user, key)
        result = seed.merge(existing, cats, mode=request.mode, app_version=self.version)
        logger.info(
            "[AERIOTV-PRESETS] %s for user %s: mode=%s record=%s add=%s replace=%s keep=%s dropped_channels=%d dropped_groups=%d",
            "apply" if write else "preview", user.pk, request.mode, seed.describe(seed.summarize(existing)),
            ",".join(result.added) or "-", ",".join(result.replaced) or "-", ",".join(result.kept) or "-",
            dropped_channels, dropped_groups,
        )
        size = None
        if write and result.changed:
            size = bridge.write_record(user, key, result.record)
            logger.info("[AERIOTV-PRESETS] wrote record for user %s: bytes=%d", user.pk, size)
        toast = seed.toast(request.mode, result, cats, write=write, size=size)
        if dropped_channels or dropped_groups:
            toast += f" Skipped {dropped_channels} channels and {dropped_groups} groups {user.username} cannot see."
        return {"changed": result.changed, "toast": toast}


class ActionError(Exception):
    """A short, user-facing failure. Dispatcharr shows str(exc) in a red toast
    (dev branch apps/plugins/api_views.py:886-890, frontend/src/pages/PluginDetail.jsx:378-381)."""


def _sentence(text: str) -> str:
    text = text.strip().rstrip(".")
    return (text[:1].upper() + text[1:] + ".") if text else "Something went wrong."
