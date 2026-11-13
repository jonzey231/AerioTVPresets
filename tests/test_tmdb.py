"""TMDB API key preset (schema section 4.13): {"apiKey": "<key>"}, "" = no key."""

import copy
import json
import os
import re

import pytest

from aeriotv_presets import copying, options, schema, seed

NOW = "2026-11-13T12:00:00Z"
EARLIER = "2026-11-01T08:00:00Z"
# Placeholders only, never a real key.
KEY = "0123456789abcdef0123456789abcdef"
OTHER = "fedcba9876543210fedcba9876543210"
MANIFEST = json.load(open(os.path.join(os.path.dirname(__file__), "..", "aeriotv-presets", "plugin.json")))


def form(**over):
    s = {"target_username": "viewer", "apply_mode": "fill"}
    s.update(over)
    return s


def record(tmdb=None):
    """A device-written record, optionally holding a tmdbKey sub-object."""
    rec = {
        "schemaVersion": 3, "deviceId": "6F1C2A9E-4B7D-4C1E-9E1A-0D2B8C3F5A11", "platform": "ios",
        "appVersion": "1.8.45", "updatedAt": EARLIER,
        "categories": {
            "favorites": {"updatedAt": EARLIER, "deviceId": "6F1C...5A11", "data": {"ids": [1042, 77]}},
        },
    }
    if tmdb is not None:
        rec["categories"]["tmdbKey"] = tmdb
    return rec


def device_tmdb(data):
    return {"updatedAt": EARLIER, "deviceId": "A2B9...0C44", "data": data}


def depth(value):
    if isinstance(value, dict):
        return 1 + max((depth(v) for v in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((depth(v) for v in value), default=0)
    return 0


# ---------------------------------------------------------------- shape

def test_key_field_writes_the_schema_shape():
    req = seed.parse_settings(form(tmdb_api_key=f"  {KEY}  "))
    assert req.categories == {"tmdbKey": {"apiKey": KEY}}  # trimmed, as the apps store it
    assert schema.validate_tmdb_key(req.categories["tmdbKey"]) == {"apiKey": KEY}


def test_empty_field_leaves_the_category_alone():
    for value in ("", "   ", None):
        req = seed.parse_settings(form(tmdb_api_key=value, favorite_1="5"))
        assert "tmdbKey" not in req.categories
    req = seed.parse_settings(form(favorite_1="5", tmdb_clear=False))
    assert list(req.categories) == ["favorites"]


@pytest.mark.parametrize("bad", [
    {}, {"apiKey": 42}, {"apiKey": None}, {"apiKey": KEY, "extra": 1}, ["apiKey"],
    {"apiKey": KEY + " " + KEY}, {"apiKey": KEY + "\n"}, {"apiKey": KEY + "\x00"},
    {"apiKey": "a" * (schema.TMDB_KEY_MAX + 1)},
])
def test_shape_is_checked(bad):
    with pytest.raises(schema.SchemaError) as err:
        schema.validate_tmdb_key(bad)
    assert KEY not in str(err.value)


def test_refused_key_is_never_echoed():
    with pytest.raises(seed.SeedError) as err:
        seed.parse_settings(form(tmdb_api_key=f"{KEY} {OTHER}"))
    assert str(err.value) == "the TMDB API key must be one line with no spaces"
    assert KEY not in str(err.value) and OTHER not in str(err.value)
    long_ok = "a" * schema.TMDB_KEY_MAX
    assert seed.parse_settings(form(tmdb_api_key=long_ok)).categories["tmdbKey"] == {"apiKey": long_ok}


def test_reader_rule_matches_the_apps():
    assert schema.tmdb_api_key({"apiKey": f" {KEY} "}) == KEY
    assert schema.tmdb_api_key({"apiKey": ""}) == ""
    assert schema.tmdb_api_key({}) == ""  # missing apiKey reads as no key
    assert schema.tmdb_api_key({"apiKey": 42}) is None  # malformed
    assert schema.tmdb_api_key(None) is None


# ---------------------------------------------------------------- Fill

def test_fill_adds_an_absent_category_with_the_plugin_stamp():
    req = seed.parse_settings(form(tmdb_api_key=KEY))
    for existing in (None, record()):
        result = seed.merge(existing, req.categories, mode="fill", app_version="0.0.7", now=NOW)
        assert result.added == ["tmdbKey"]
        sub = result.record["categories"]["tmdbKey"]
        assert sub == {"updatedAt": NOW, "deviceId": seed.PLUGIN_DEVICE_ID, "data": {"apiKey": KEY}}
        assert result.record["platform"] == "dispatcharr-plugin"
        assert result.record["deviceId"] == seed.PLUGIN_DEVICE_ID
        assert result.record["updatedAt"] == NOW
        assert schema.validate_envelope(json.loads(json.dumps(result.record))) == result.record


def test_default_stamp_is_iso_seconds_utc():
    result = seed.merge(None, {"tmdbKey": {"apiKey": KEY}}, mode="fill", app_version="0.0.7")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result.record["categories"]["tmdbKey"]["updatedAt"])


@pytest.mark.parametrize("held", [{"apiKey": OTHER}, {"apiKey": ""}, {"apiKey": 42}])
def test_fill_keeps_any_tmdb_category_the_record_holds(held):
    existing = record(device_tmdb(held))
    before = copy.deepcopy(existing)
    result = seed.merge(existing, {"tmdbKey": {"apiKey": KEY}}, mode="fill", app_version="0.0.7", now=NOW)
    assert result.kept == ["tmdbKey"] and not result.changed
    assert result.record == before  # nothing restamped
    assert existing == before  # input not mutated


# ---------------------------------------------------------------- Replace

def test_replace_overwrites_an_existing_key_and_keeps_unknown_members():
    held = device_tmdb({"apiKey": OTHER, "future": 1})
    held["extra"] = {"note": "x"}
    result = seed.merge(record(held), {"tmdbKey": {"apiKey": KEY}}, mode="replace", app_version="0.0.7", now=NOW)
    assert result.replaced == ["tmdbKey"]
    sub = result.record["categories"]["tmdbKey"]
    assert sub == {"updatedAt": NOW, "deviceId": seed.PLUGIN_DEVICE_ID,
                   "data": {"apiKey": KEY, "future": 1}, "extra": {"note": "x"}}
    assert result.record["categories"]["favorites"] == record()["categories"]["favorites"]


def test_replace_with_the_same_key_keeps_the_device_stamp():
    existing = record(device_tmdb({"apiKey": KEY}))
    result = seed.merge(existing, {"tmdbKey": {"apiKey": KEY}}, mode="replace", app_version="0.0.7", now=NOW)
    assert result.kept == ["tmdbKey"] and not result.changed
    assert result.record["categories"]["tmdbKey"]["updatedAt"] == EARLIER


def test_replace_adds_an_absent_category_and_overwrites_a_malformed_one():
    added = seed.merge(record(), {"tmdbKey": {"apiKey": KEY}}, mode="replace", app_version="0.0.7", now=NOW)
    assert added.added == ["tmdbKey"]
    bad = record(device_tmdb({"apiKey": 42}))
    fixed = seed.merge(bad, {"tmdbKey": {"apiKey": KEY}}, mode="replace", app_version="0.0.7", now=NOW)
    assert fixed.replaced == ["tmdbKey"]
    assert fixed.record["categories"]["tmdbKey"]["data"] == {"apiKey": KEY}
    junk = record("not an object")
    fresh = seed.merge(junk, {"tmdbKey": {"apiKey": KEY}}, mode="replace", app_version="0.0.7", now=NOW)
    assert fresh.record["categories"]["tmdbKey"] == {
        "updatedAt": NOW, "deviceId": seed.PLUGIN_DEVICE_ID, "data": {"apiKey": KEY}}


# ---------------------------------------------------------------- explicit clear

def test_clear_writes_no_key_over_a_held_key():
    req = seed.parse_settings(form(apply_mode="replace", tmdb_clear=True))
    assert req.categories == {"tmdbKey": {"apiKey": ""}}
    result = seed.merge(record(device_tmdb({"apiKey": OTHER})), req.categories, mode="replace",
                        app_version="0.0.7", now=NOW)
    assert result.replaced == ["tmdbKey"]
    assert result.record["categories"]["tmdbKey"] == {
        "updatedAt": NOW, "deviceId": seed.PLUGIN_DEVICE_ID, "data": {"apiKey": ""}}
    assert seed.toast("replace", result, req.categories, write=True) == "Applied (Replace): TMDB API key (cleared)."


@pytest.mark.parametrize("existing", [None, record(), record(device_tmdb({"apiKey": ""})),
                                      record(device_tmdb({})), record(device_tmdb({"apiKey": 42}))])
def test_clear_never_starts_the_category(existing):
    # A fresh "" would read on devices as a clear newer than every key (schema 4.13).
    before = copy.deepcopy(existing)
    cats = {"tmdbKey": {"apiKey": ""}}
    result = seed.merge(existing, cats, mode="replace", app_version="0.0.7", now=NOW)
    assert result.kept == ["tmdbKey"] and not result.changed
    if before is None:
        assert "tmdbKey" not in result.record["categories"]
    else:
        assert result.record == before
    assert seed.toast("replace", result, cats, write=False) == \
        "Preview (Replace): no change. The record has no TMDB API key to clear."


def test_clear_beside_other_sections():
    cats = {"favorites": {"ids": [5]}, "tmdbKey": {"apiKey": ""}}
    result = seed.merge(record(), cats, mode="replace", app_version="0.0.7", now=NOW)
    assert seed.toast("replace", result, cats, write=False) == \
        "Preview (Replace): would write favorites (1). The record has no TMDB API key to clear."


def test_clear_needs_replace_and_excludes_a_key():
    with pytest.raises(seed.SeedError, match="^clearing the TMDB API key needs Replace$"):
        seed.parse_settings(form(apply_mode="fill", tmdb_clear="true"))
    with pytest.raises(seed.SeedError, match="^set a TMDB API key or clear it, not both$"):
        seed.parse_settings(form(apply_mode="replace", tmdb_clear=True, tmdb_api_key=KEY))
    with pytest.raises(seed.SeedError):
        seed.merge(record(device_tmdb({"apiKey": OTHER})), {"tmdbKey": {"apiKey": ""}}, mode="fill",
                   app_version="0.0.7", now=NOW)


# ---------------------------------------------------------------- text, logs, and the form never carry the key

def test_toasts_and_summaries_never_show_the_key():
    cats = {"tmdbKey": {"apiKey": KEY}}
    new = seed.merge(None, cats, mode="fill", app_version="0.0.7", now=NOW)
    texts = [seed.toast("fill", new, cats, write=False), seed.toast("fill", new, cats, write=True, size=300)]
    assert texts == ["Preview (Fill): would add TMDB API key.", "Applied (Fill): TMDB API key. Record 0.3 KB."]
    again = seed.merge(new.record, cats, mode="fill", app_version="0.0.7", now=NOW)
    texts.append(seed.toast("fill", again, cats, write=False))
    assert texts[-1] == "Preview (Fill): no change; the record already has TMDB API key."
    summary = seed.summarize(new.record)
    texts.append(seed.describe(summary))
    assert texts[-1] == "record holds: tmdbKey"
    assert not any(KEY in t for t in texts) and KEY not in json.dumps(summary)


def test_form_never_shows_the_record_key():
    current = {"tmdbKey": {"apiKey": KEY}, options.RECORD_PRESENT: True}
    fields = options.build_fields(MANIFEST["fields"], usernames=["viewer"], saved={"target_username": "viewer"},
                                  channels=[], live_groups=[], native_sections=True, tables=True, current=current)
    assert KEY not in json.dumps(fields)
    by_id = {f["id"]: f for f in fields}
    key_field, clear = by_id[options.TMDB_KEY_FIELD], by_id[options.TMDB_CLEAR_FIELD]
    assert (key_field["type"], key_field["default"], key_field["label"]) == ("string", "", "TMDB API key")
    assert key_field["input_type"] == "password"  # masked in the form
    assert key_field["help_text"].endswith("Leave empty to keep the key in the record. In the record now: a key.")
    assert (clear["type"], clear["default"], clear["label"]) == ("boolean", False, "Clear the TMDB API key")
    assert clear["help_text"].startswith("Replace only.")
    assert key_field["section"] == clear["section"] == by_id["app_hdr:TMDB"]["section"] == "sec_app"
    ids = [f["id"] for f in fields]
    assert ids.index("set:exitDialogFocusExit") < ids.index("app_hdr:TMDB") < ids.index(options.TMDB_KEY_FIELD) \
        < ids.index(options.TMDB_CLEAR_FIELD) < ids.index("sec_apply")
    cleared = options.tmdb_fields({"tmdbKey": {"apiKey": ""}})[1]
    assert cleared["help_text"].endswith("In the record now: no key.")
    assert "In the record now" not in options.tmdb_fields({})[1]["help_text"]


def test_flat_layout_offers_the_fields_under_app_settings():
    fields = options.build_fields(MANIFEST["fields"], usernames=["viewer"],
                                  saved={"target_username": "viewer", "expand_app": True})
    ids = [f["id"] for f in fields]
    assert ids.index("hdr:expand_app") < ids.index(options.TMDB_KEY_FIELD) < ids.index("apply_mode")
    closed = options.build_fields(MANIFEST["fields"], usernames=["viewer"], saved={"target_username": "viewer"})
    assert options.TMDB_KEY_FIELD not in [f["id"] for f in closed]


# ---------------------------------------------------------------- Copy from and Also apply to

def test_copy_from_fills_the_key_field():
    source = record(device_tmdb({"apiKey": KEY}))
    out, report = copying.record_to_settings(source, channel_ids=[1042, 77], live_groups=[], movie_groups=[],
                                             series_groups=[])
    assert out[options.TMDB_KEY_FIELD] == KEY and out[options.TMDB_CLEAR_FIELD] is False
    assert report.copied == ["favorites (2)", "TMDB API key"]
    assert KEY not in report.text("alice")
    out["target_username"] = "bob"
    out["apply_mode"] = "replace"
    assert seed.parse_settings(out).categories["tmdbKey"] == {"apiKey": KEY}


@pytest.mark.parametrize("held", [{"apiKey": ""}, {}, {"apiKey": 42}])
def test_copy_from_skips_a_source_without_a_key(held):
    out, report = copying.record_to_settings(record(device_tmdb(held)), channel_ids=[], live_groups=[],
                                             movie_groups=[], series_groups=[])
    assert options.TMDB_KEY_FIELD not in out and options.TMDB_CLEAR_FIELD not in out
    assert "TMDB API key" not in report.copied


def test_copy_from_skips_a_key_the_plugin_cannot_write():
    out, report = copying.record_to_settings(record(device_tmdb({"apiKey": f"{KEY} {OTHER}"})), channel_ids=[],
                                             live_groups=[], movie_groups=[], series_groups=[])
    assert options.TMDB_KEY_FIELD not in out and report.dropped_settings == 1


def test_also_apply_to_sends_the_same_key_to_every_user():
    cats = {"favorites": {"ids": [1, 2]}, "tmdbKey": {"apiKey": KEY}}
    scoped, _, _ = seed.scope_to_target(cats, channel_ids=[], live_groups=[], movie_groups=[], series_groups=[])
    assert scoped == {"tmdbKey": {"apiKey": KEY}}
    clear, _, _ = seed.scope_to_target({"tmdbKey": {"apiKey": ""}}, channel_ids=[], live_groups=[],
                                       movie_groups=[], series_groups=[])
    assert clear == {"tmdbKey": {"apiKey": ""}}


# ---------------------------------------------------------------- Dispatcharr limits

def test_record_stays_inside_the_app_data_limits():
    big = "a" * schema.TMDB_KEY_MAX
    result = seed.merge(record(), {"tmdbKey": {"apiKey": big}}, mode="fill", app_version="0.0.7", now=NOW)
    body = json.dumps(result.record, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert len(body) < 128 * 1024
    assert depth(result.record["categories"]["tmdbKey"]) == 2
    assert depth(result.record) <= 8


# ---------------------------------------------------------------- end to end through Plugin.run, bridge stubbed

def test_apply_writes_every_user_and_never_logs_the_key(monkeypatch, caplog):
    import logging
    from types import SimpleNamespace

    from aeriotv_presets import plugin

    users = {"viewer": SimpleNamespace(pk=1, username="viewer"), "guest": SimpleNamespace(pk=2, username="guest")}
    store = {"viewer.aeriotv": record(device_tmdb({"apiKey": OTHER}))}
    bridge = plugin.bridge
    monkeypatch.setattr(bridge, "find_user", lambda name: users[name])
    monkeypatch.setattr(bridge, "visible_channels", lambda user: [])
    monkeypatch.setattr(bridge, "visible_group_names", lambda user: [])
    monkeypatch.setattr(bridge, "vod_group_names", lambda user=None: {"movie": [], "series": []})
    monkeypatch.setattr(bridge, "list_keys", lambda user: [k for k in store if k.startswith(user.username + ".")])
    monkeypatch.setattr(bridge, "read_record", lambda user, key: copy.deepcopy(store.get(key)))

    def write(user, key, value):
        store[key] = copy.deepcopy(value)
        return len(json.dumps(value, separators=(",", ":")))
    monkeypatch.setattr(bridge, "write_record", write)

    logger = logging.getLogger("test.aeriotv_presets.tmdb")
    settings = form(tmdb_api_key=KEY, also_users=["guest"])
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        fill = plugin.Plugin().run("apply", {}, {"settings": settings, "logger": logger})
        assert fill["message"] == "Applied (Fill) for 2 users: 1 changed, 1 unchanged."
        assert store["viewer.aeriotv"]["categories"]["tmdbKey"]["data"] == {"apiKey": OTHER}  # Fill kept it
        assert store["guest.aeriotv"]["categories"]["tmdbKey"]["data"] == {"apiKey": KEY}

        replace = plugin.Plugin().run("apply", {}, {"settings": dict(settings, apply_mode="replace"), "logger": logger})
        assert replace["message"] == "Applied (Replace) for 2 users: 1 changed, 1 unchanged."
        assert store["viewer.aeriotv"]["categories"]["tmdbKey"]["data"] == {"apiKey": KEY}

        clear = form(apply_mode="replace", tmdb_clear=True)
        cleared = plugin.Plugin().run("apply", {}, {"settings": clear, "logger": logger})
        assert cleared["message"].startswith("Applied (Replace): TMDB API key (cleared). Record ")
        assert store["viewer.aeriotv"]["categories"]["tmdbKey"]["data"] == {"apiKey": ""}

        with pytest.raises(plugin.ActionError, match="^The TMDB API key must be one line with no spaces.$"):
            plugin.Plugin().run("apply", {}, {"settings": form(tmdb_api_key=f"{KEY} x"), "logger": logger})

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "tmdbKey" in logged and KEY not in logged and OTHER not in logged
    for message in (fill, replace, cleared):
        assert KEY not in message["message"]
