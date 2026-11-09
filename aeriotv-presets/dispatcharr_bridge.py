"""The only module that imports Dispatcharr code.

Every Dispatcharr API this plugin relies on is called here, so drift in
Dispatcharr's internals is fixed in one file. Read against Dispatcharr
v0.33.0, commit 1241b3f7ffb2e64c8d1157ecd5e3b199af1ae430 (2026-10-30):

- apps/accounts/models.py: User (username, user_level, channel_profiles),
  UserAppData (user, key, value JSON, byte_size, updated_at), unique per
  (user, key).
- apps/accounts/app_data.py: validate_app_data_key, validate_app_data_value
  (object only, depth 8, 128 KiB, raises AppDataError 400/413),
  put_app_data_value (row lock, 25 keys per user -> 409 max_apps, 1 MiB per
  user -> 413 total_too_large), get_app_data_value, summarize_user_app_data.
- apps/channels/access.py: channels_queryset_for_user (the visibility rule
  every user-facing channel surface uses).
- apps/channels/models.py: Channel (id, channel_number, name, channel_group,
  override), ChannelGroup (name).

Imports are inside the functions so the pure modules and the tests never
need Django.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class BridgeError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "error"):
        super().__init__(message)
        self.status = status
        self.code = code


def find_user(username: str):
    from apps.accounts.models import User

    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        raise BridgeError("user not found", status=404, code="user_not_found")


def visible_channels(user) -> List[Dict[str, Any]]:
    """Channels the user can see, with the group name the apps receive."""
    from django.db.models.functions import Coalesce

    from apps.channels.access import channels_queryset_for_user
    from apps.channels.models import Channel

    qs = channels_queryset_for_user(Channel.objects.all(), user)
    rows = (
        qs.annotate(group_name=Coalesce("override__channel_group__name", "channel_group__name"))
        .order_by("channel_number", "name")
        .values("id", "channel_number", "name", "group_name")
    )
    return list(rows)


def visible_group_names(user) -> List[str]:
    names = {row["group_name"] for row in visible_channels(user) if row.get("group_name")}
    return sorted(names, key=str.casefold)


def list_keys(user) -> List[str]:
    from apps.accounts.app_data import summarize_user_app_data

    return [row["key"] for row in summarize_user_app_data(user.pk)["apps"]]


def read_record(user, key: str) -> Optional[Dict[str, Any]]:
    from apps.accounts.app_data import AppDataError, get_app_data_value, validate_app_data_key

    try:
        validate_app_data_key(key)
    except AppDataError as exc:
        raise BridgeError(exc.detail, exc.status_code, exc.code)
    return get_app_data_value(user.pk, key)


def write_record(user, key: str, value: Dict[str, Any]) -> int:
    """Store the record with Dispatcharr's own checks. Returns the stored byte size."""
    from apps.accounts.app_data import (
        AppDataError,
        put_app_data_value,
        validate_app_data_key,
        validate_app_data_value,
    )

    try:
        validate_app_data_key(key)
        size = validate_app_data_value(value)
        put_app_data_value(user.pk, key, value, size)
    except AppDataError as exc:
        raise BridgeError(exc.detail, exc.status_code, exc.code)
    return size


def usernames() -> List[str]:
    """Every Dispatcharr username, for the User dropdown."""
    from apps.accounts.models import User

    return list(User.objects.order_by("username").values_list("username", flat=True))


def vod_group_names(user=None) -> Dict[str, List[str]]:
    """Movie and series category names a user could browse.

    Scope (apps/vod/models.py VODCategory and M3UVODCategoryRelation): categories
    linked to an active M3U account with the relation enabled. With a user,
    movie or series categories are dropped when apps/vod/utils.py
    is_vod_movies_enabled / is_vod_series_enabled say that user may not watch
    them (dev branch; skipped where the helpers do not exist). Dispatcharr has
    no per-user category rule beyond that.
    """
    from apps.vod.models import VODCategory

    allowed = {"movie": True, "series": True}
    if user is not None:
        try:
            from apps.vod.utils import is_vod_movies_enabled, is_vod_series_enabled

            allowed = {"movie": bool(is_vod_movies_enabled(user=user)),
                       "series": bool(is_vod_series_enabled(user=user))}
        except ImportError:
            pass
    rows = (
        VODCategory.objects.filter(m3u_relations__enabled=True, m3u_relations__m3u_account__is_active=True)
        .distinct()
        .order_by("name")
        .values_list("name", "category_type")
    )
    out: Dict[str, List[str]] = {"movie": [], "series": []}
    for name, kind in rows:
        if kind in out and allowed[kind] and name not in out[kind]:
            out[kind].append(name)
    return out


def saved_settings(plugin_key: str) -> Dict[str, Any]:
    """This plugin's saved settings (apps/plugins/models.py PluginConfig.settings)."""
    from apps.plugins.models import PluginConfig

    cfg = PluginConfig.objects.filter(key=plugin_key).only("settings").first()
    return dict(cfg.settings or {}) if cfg else {}


def request_field_refresh() -> None:
    """Make every worker rebuild this plugin's fields on the next Plugins page load.

    Dispatcharr reads Plugin.fields only when it loads a plugin
    (apps/plugins/loader.py _load_plugin). The Plugins list view calls
    discover_plugins(use_cache=True), which reloads every plugin when the
    shared .reload_token file is newer than the worker's last reload. Touching
    that token is what PluginManager._touch_reload_token does.
    """
    import os

    from apps.plugins.loader import PluginManager

    pm = PluginManager.get()
    touch = getattr(pm, "_touch_reload_token", None)
    if callable(touch):
        touch()
        return
    path = os.path.join(pm.plugins_dir, ".reload_token")
    with open(path, "a", encoding="utf-8"):
        pass
    os.utime(path, None)


def supports_sections() -> bool:
    """True when this Dispatcharr accepts `section` fields (newer than v0.33.0).

    v0.33.0 field types: apps/plugins/serializers.py:26. The dev branch at
    174a26e adds section, multiselect, table, and file (serializers.py:40) and
    renders sections as an accordion (frontend/src/components/PluginFieldList.jsx).
    """
    from apps.plugins.serializers import PluginFieldSerializer

    return "section" in PluginFieldSerializer().fields["type"].choices
