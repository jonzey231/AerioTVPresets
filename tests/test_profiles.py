import pytest

from aeriotv_presets import options, profiles, schema, seed

USERS = {"dad": (1, True), "kid": (7, False), "mom": (3, False)}
def build(table, existing=None):
    return profiles.build_rows(table, target="dad", users=USERS, existing_rows=existing or [], now=1700000000)


def test_rows_shape_roles_and_default_profile():
    rows = build([{"user": "kid", "name": "Kids", "role": "child", "icon": "paw", "color": "orange",
                   "pin_type": "none", "pin": ""},
                  {"user": "dad", "name": "", "role": "child", "icon": "default", "color": "default",
                   "pin_type": "numbers", "pin": "2468"}],
                 existing=[[7, "kid", "Old", "none", "", "", "child", 5, {}, 0]])
    assert [r[1] for r in rows] == ["kid", "dad"]
    kid, dad = rows
    assert kid == [7, "kid", "Kids", "none", "", "", "child", 1700000000, {"icon": "paw", "color": "orange"}, 0]
    assert dad[6] == "admin" and dad[2] == "dad" and dad[8] == {} and dad[9] == 1
    assert dad[3:6] == ["none", "", ""]
    assert schema.validate_profiles({"rows": rows})


def test_target_is_added_as_the_default_profile():
    rows = build([{"user": "mom", "pin_type": "none"}])
    assert [r[1] for r in rows] == ["dad", "mom"] and rows[0][9] == 0


def test_no_pin_is_written_and_a_device_pin_stays():
    old = [[1, "dad", "Dad", "numbers", "a" * 64, "b" * 32, "admin", 5, {}, 0]]
    rows = build([{"user": "dad", "pin_type": "numbers", "pin": "1234"}, {"user": "kid"}], existing=old)
    assert rows[0][3:6] == ["numbers", "a" * 64, "b" * 32]
    assert rows[1][3:6] == ["none", "", ""] and rows[1][6] == "user"


def test_child_only_when_the_record_already_has_it():
    with pytest.raises(profiles.ProfileError, match="must be created in the AerioTV app"):
        build([{"user": "kid", "role": "child"}])
    old = [[7, "kid", "Kids", "numbers", "a" * 64, "b" * 32, "child", 5, {}, 1]]
    rows = build([{"user": "kid", "name": "Kiddo", "role": "child"}], existing=old)
    assert rows[1][6] == "child" and rows[1][2] == "Kiddo" and rows[1][4] == "a" * 64


def test_unknown_and_repeated_users():
    with pytest.raises(profiles.ProfileError):
        build([{"user": "ghost"}])
    with pytest.raises(profiles.ProfileError):
        build([{"user": "mom"}, {"user": "mom"}])


def test_replace_merges_rows_and_keeps_tombstones():
    existing = {"rows": [[1, "dad", "Dad", "none", "", "", "admin", 1, {}, 0],
                         [9, "gran", "Gran", "none", "", "", "user", 1, {}, 1]],
                "removed": [["mom", 100, 3], ["old", 100]]}
    new = [[3, "mom", "Mom", "none", "", "", "user", 2, {}, 0]]
    merged = profiles.merge_rows(existing, new)
    assert [r[1] for r in merged["rows"]] == ["mom", "dad", "gran"]
    assert merged["removed"] == [["old", 100]]


def test_fill_and_replace_through_seed_merge():
    rows = [[1, "dad", "Dad", "none", "", "", "admin", 2, {}, 0]]
    rec = seed.merge(None, {"profiles": {"rows": rows}}, mode="fill", app_version="0.0.7", now="2026-11-09T00:00:00Z")
    assert rec.added == ["profiles"]
    again = seed.merge(rec.record, {"profiles": {"rows": rows}}, mode="fill", app_version="0.0.7")
    assert again.kept == ["profiles"]
    assert seed.category_count("profiles", {"rows": rows}) == "profiles (1)"


def test_table_defaults():
    old = [[3, "mom", "Mom", "numbers", "a" * 64, "b" * 32, "user", 5, {"icon": "cat"}, 1],
           [1, "dad", "Dad", "none", "", "", "admin", 5, {}, 0]]
    rows = profiles.table_defaults("dad", old)
    assert [r["user"] for r in rows] == ["dad", "mom"]
    assert profiles.table_defaults("dad", []) == []
    assert rows[1]["icon"] == "cat" and "pin" not in rows[1] and "pin_type" not in rows[1]


def test_profiles_section_fields():
    import json, os
    manifest = json.load(open(os.path.join(os.path.dirname(__file__), "..", "aeriotv-presets", "plugin.json")))
    fields = options.build_fields(manifest["fields"], usernames=["dad", "kid"], saved={"target_username": "dad"},
                                  channels=[], live_groups=[], native_sections=True, tables=True, current={})
    by_id = {f["id"]: f for f in fields}
    table = by_id[profiles.TABLE]
    assert table["section"] == "sec_profiles"
    assert [c["id"] for c in table["columns"]] == ["user", "name", "role", "icon", "color"]
    assert table["label"] == "" and by_id["profiles_help"]["label"] == ""
    assert table["default"] == []
    marker = by_id["sec_profiles"]
    assert marker["collapsed"] is True


def test_unchanged_row_keeps_its_stamp():
    old = [[1, "dad", "Dad", "none", "", "", "admin", 5, {}, 0]]
    rows = build([{"user": "dad", "name": "Dad", "pin_type": "none", "icon": "default", "color": "default"}], existing=old)
    assert rows[0][7] == 5
    merged = profiles.merge_rows({"rows": old}, rows)
    assert merged == {"rows": old}
