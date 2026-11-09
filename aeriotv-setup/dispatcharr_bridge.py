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
