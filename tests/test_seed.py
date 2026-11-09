import copy
import json

import pytest

from aeriotv_presets import schema, seed

NOW = "2026-11-09T12:00:00Z"


def full_settings(**over):
    s = {
        "target_username": "viewer",
        "favorite_1": "1042", "favorite_2": "77", "favorite_3": "__none__", "favorite_10": "903",
        "group_order_mode": "manual",
        "group_1": "Sports", "group_2": "News", "group_3": "__none__", "group_4": "Movies", "group_5": "News",
        "show_live:Adult": False, "show_live:Spanish": False, "show_live:News": True,
        "show_series:Kids": False, "show_movies:Drama": True,
        "set:selectedTheme": "Midnight",
        "set:appearanceMode": "dark",
        "default_group": "Sports",
        "apply_mode": "fill",
    }
    s.update(over)
    return s


def test_parse_matches_fixtures(fixture):
    req = seed.parse_settings(full_settings())
    assert req.categories["favorites"] == fixture("favorites.json")
    assert req.categories["groupOrder"] == fixture("groupOrder.json")
    assert req.categories["hiddenGroups"] == fixture("hiddenGroups.json")
    assert req.categories["settings"] == {"v": {"selectedTheme": "Midnight", "appearanceMode": "dark", "trueBlack": False, "defaultGroup": "Sports"}}


def test_parse_blank_sections_are_left_out():
    req = seed.parse_settings({"target_username": "viewer", "favorite_1": "5", "set:selectedTheme": "__none__",
                               "group_order_mode": "__none__", "apply_mode": "fill"})
    assert list(req.categories) == ["favorites"]
    assert req.mode == "fill"


@pytest.mark.parametrize("over", [{"target_username": ""}, {"target_username": "__none__"}, {"favorite_2": "abc"},
                                  {"apply_mode": "merge"},
                                  {"group_order_mode": "manual", "group_1": "__none__", "group_2": "__none__",
                                   "group_4": "__none__", "group_5": "__none__"}])
def test_parse_rejects(over):
    with pytest.raises(seed.SeedError):
        seed.parse_settings(full_settings(**over))


def test_new_record_round_trip():
    req = seed.parse_settings(full_settings())
    result = seed.merge(None, req.categories, mode="fill", app_version="0.0.1", now=NOW)
    assert sorted(result.added) == sorted(schema.PHASE1_CATEGORIES)
    record = json.loads(json.dumps(result.record, separators=(",", ":")))
    assert schema.validate_envelope(record) == result.record
    assert record["schemaVersion"] == schema.SCHEMA_VERSION
    assert record["categories"]["favorites"] == {
        "updatedAt": NOW, "deviceId": seed.PLUGIN_DEVICE_ID, "data": {"ids": [1042, 77, 903]}}


def test_fill_never_touches_device_categories(fixture):
    existing = fixture("record.json")
    before = copy.deepcopy(existing)
    req = seed.parse_settings(full_settings())
    result = seed.merge(existing, req.categories, mode="fill", app_version="0.0.1", now=NOW)
    cats = result.record["categories"]
    assert cats["favorites"] == before["categories"]["favorites"]
    assert cats["settings"] == before["categories"]["settings"]
    assert cats["recents"] == before["categories"]["recents"]
    assert sorted(result.kept) == ["favorites", "settings"]
    assert sorted(result.added) == ["groupOrder", "hiddenGroups"]
    assert existing == before  # input not mutated


def test_fill_with_nothing_new_writes_nothing(fixture):
    existing = fixture("record.json")
    result = seed.merge(existing, {"favorites": {"ids": [1]}}, mode="fill", app_version="0.0.1", now=NOW)
    assert not result.changed
    assert result.record["updatedAt"] == existing["updatedAt"]


def test_replace_overwrites_chosen_and_keeps_the_rest(fixture):
    existing = fixture("record.json")
    seed_cats = {"favorites": {"ids": [5, 6]}, "settings": {"v": {"selectedTheme": "Forest", "defaultGroup": "News"}}}
    result = seed.merge(existing, seed_cats, mode="replace", app_version="0.0.1", now=NOW)
    cats = result.record["categories"]
    assert cats["favorites"]["data"] == {"ids": [5, 6]}
    assert cats["settings"]["data"] == {
        "v": {"selectedTheme": "Forest", "defaultGroup": "News"}, "tv": {"textScale": 1.3}, "mobile": {"textScale": 1.0}}
    assert cats["recents"] == existing["categories"]["recents"]
    assert result.record["updatedAt"] == NOW
    assert schema.validate_envelope(result.record)


def test_refuses_newer_schema(fixture):
    existing = fixture("record.json")
    existing["schemaVersion"] = 9
    with pytest.raises(schema.SchemaError):
        seed.merge(existing, {"favorites": {"ids": [1]}}, mode="replace", app_version="0.0.1", now=NOW)


def test_legacy_key_blocks_until_moved():
    assert seed.legacy_conflict(["app.molinete.aerio"], "viewer.aeriotv")[0]
    assert not seed.legacy_conflict(["app.molinete.aerio", "viewer.aeriotv"], "viewer.aeriotv")[0]
    assert not seed.legacy_conflict(["other.app.key"], "viewer.aeriotv")[0]


def test_summary_has_counts_only(fixture):
    summary = seed.summarize(fixture("record.json"))
    assert summary["categories"]["favorites"] == 2
    assert "1042" not in json.dumps(summary)


def test_slot_order_is_numeric_not_text():
    req = seed.parse_settings({"target_username": "v", "favorite_10": "3", "favorite_2": "2", "favorite_1": "1"})
    assert req.categories["favorites"] == {"ids": [1, 2, 3]}


def test_old_text_fields_are_ignored():
    req = seed.parse_settings({"target_username": "v", "favorites": "1, 2", "group_order": "News"})
    assert req.categories == {}


def test_app_settings_values_are_typed():
    req = seed.parse_settings({"target_username": "v", "set:liveRewindEnabled": "false",
                               "set:liveRewindDepthMinutes": "60", "set:textScale": "1.1",
                               "set:appearanceMode": "trueblack", "set:skipBack": "__none__"})
    assert req.categories["settings"] == {"v": {"liveRewindEnabled": False, "liveRewindDepthMinutes": 60,
                                                "textScale": 1.1, "appearanceMode": "dark", "trueBlack": True}}


def test_app_setting_outside_schema_is_refused():
    with pytest.raises(seed.SeedError):
        seed.parse_settings({"target_username": "v", "set:skipBack": "7"})


def test_toasts_are_short():
    cats = {"favorites": {"ids": [1, 2]}, "groupOrder": {"mode": "manual", "order": ["A", "B", "C"]}}
    new = seed.merge(None, cats, mode="fill", app_version="0.0.1", now=NOW)
    assert seed.toast("fill", new, cats, write=False) == "Preview (Fill): would add favorites (2), groupOrder (3 groups)."
    assert seed.toast("fill", new, cats, write=True, size=1946) == "Applied (Fill): favorites (2), groupOrder (3 groups). Record 1.9 KB."
    again = seed.merge(new.record, cats, mode="fill", app_version="0.0.1", now=NOW)
    assert seed.toast("fill", again, cats, write=False) == "Preview (Fill): no change; the record already has favorites, groupOrder."


def test_tables_take_precedence_over_slots():
    req = seed.parse_settings({"target_username": "v", "favorite_1": "5",
                               "favorites_rows": [{"channel": "9"}, {"channel": "3"}, {"channel": ""}, {"channel": "9"}],
                               "group_order_rows": [{"group": "B"}, {"group": "A"}]})
    assert req.categories["favorites"] == {"ids": [9, 3]}
    assert req.categories["groupOrder"] == {"mode": "manual", "order": ["B", "A"]}


def test_empty_table_writes_nothing():
    req = seed.parse_settings({"target_username": "v", "favorites_rows": [], "favorite_1": "5"})
    assert "favorites" not in req.categories
