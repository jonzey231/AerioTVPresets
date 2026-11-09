import copy
import json

import pytest

from aeriotv_setup import schema, seed

NOW = "2026-11-09T12:00:00Z"


def full_settings(**over):
    s = {
        "target_username": "viewer",
        "favorites": "1042, 77\n903",
        "group_order_mode": "manual",
        "group_order": "Sports\nNews\n\nMovies\nNews",
        "hidden_groups_live": "Adult\nSpanish",
        "hidden_groups_series": "Kids",
        "selected_theme": "Midnight",
        "appearance_mode": "dark",
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
    assert req.categories["settings"] == {"v": {"selectedTheme": "Midnight", "appearanceMode": "dark", "defaultGroup": "Sports"}}


def test_parse_blank_sections_are_left_out():
    req = seed.parse_settings({"target_username": "viewer", "favorites": "5"})
    assert list(req.categories) == ["favorites"]
    assert req.mode == "fill"


@pytest.mark.parametrize("over", [{"target_username": ""}, {"favorites": "12, abc"},
                                  {"apply_mode": "merge"}, {"group_order_mode": "manual", "group_order": ""}])
def test_parse_rejects(over):
    with pytest.raises(seed.SeedError):
        seed.parse_settings(full_settings(**over))


def test_new_record_round_trip():
    req = seed.parse_settings(full_settings())
    result = seed.merge(None, req.categories, mode="fill", app_version="0.1.0", now=NOW)
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
    result = seed.merge(existing, req.categories, mode="fill", app_version="0.1.0", now=NOW)
    cats = result.record["categories"]
    assert cats["favorites"] == before["categories"]["favorites"]
    assert cats["settings"] == before["categories"]["settings"]
    assert cats["recents"] == before["categories"]["recents"]
    assert sorted(result.kept) == ["favorites", "settings"]
    assert sorted(result.added) == ["groupOrder", "hiddenGroups"]
    assert existing == before  # input not mutated


def test_fill_with_nothing_new_writes_nothing(fixture):
    existing = fixture("record.json")
    result = seed.merge(existing, {"favorites": {"ids": [1]}}, mode="fill", app_version="0.1.0", now=NOW)
    assert not result.changed
    assert result.record["updatedAt"] == existing["updatedAt"]


def test_replace_overwrites_chosen_and_keeps_the_rest(fixture):
    existing = fixture("record.json")
    seed_cats = {"favorites": {"ids": [5, 6]}, "settings": {"v": {"selectedTheme": "Forest", "defaultGroup": "News"}}}
    result = seed.merge(existing, seed_cats, mode="replace", app_version="0.1.0", now=NOW)
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
        seed.merge(existing, {"favorites": {"ids": [1]}}, mode="replace", app_version="0.1.0", now=NOW)


def test_legacy_key_blocks_until_moved():
    assert seed.legacy_conflict(["app.molinete.aerio"], "viewer.aeriotv")[0]
    assert not seed.legacy_conflict(["app.molinete.aerio", "viewer.aeriotv"], "viewer.aeriotv")[0]
    assert not seed.legacy_conflict(["other.app.key"], "viewer.aeriotv")[0]


def test_summary_has_counts_only(fixture):
    summary = seed.summarize(fixture("record.json"))
    assert summary["categories"]["favorites"] == 2
    assert "1042" not in json.dumps(summary)
