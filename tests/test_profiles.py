import hashlib

import pytest

from aeriotv_presets import options, profiles, schema, seed

USERS = {"dad": (1, True), "kid": (7, False), "mom": (3, False)}
SALTS = iter([bytes(range(16)), bytes(range(16, 32)), bytes(range(32, 48))])


def build(table, existing=None):
    return profiles.build_rows(table, target="dad", users=USERS, existing_rows=existing or [], now=1700000000,
                               salt=lambda: next(SALTS))


def test_pin_hash_matches_the_schema_rule():
    salt = bytes(range(16))
    assert profiles.hash_pin("UULR", salt) == hashlib.sha256(salt + b"UULR").hexdigest()
    assert profiles.normalize_pin("directions", "u u l r") == "UULR"
    assert profiles.normalize_pin("numbers", "1234") == "1234"
    for bad in (("numbers", "12"), ("numbers", "1234567"), ("numbers", "12a4"), ("directions", "UUX R")):
        with pytest.raises(profiles.ProfileError):
            profiles.normalize_pin(*bad)


def test_rows_shape_roles_and_default_profile():
    global SALTS
    SALTS = iter([bytes(range(16)), bytes(range(16, 32))])
    rows = build([{"user": "kid", "name": "Kids", "role": "child", "icon": "paw", "color": "orange",
                   "pin_type": "none", "pin": ""},
                  {"user": "dad", "name": "", "role": "child", "icon": "default", "color": "default",
                   "pin_type": "numbers", "pin": "2468"}])
    assert [r[1] for r in rows] == ["kid", "dad"]
    kid, dad = rows
    assert kid == [7, "kid", "Kids", "none", "", "", "child", 1700000000, {"icon": "paw", "color": "orange"}, 0]
    assert dad[6] == "admin" and dad[2] == "dad" and dad[8] == {} and dad[9] == 1
    assert dad[5] == bytes(range(16)).hex() and dad[4] == hashlib.sha256(bytes(range(16)) + b"2468").hexdigest()
    assert schema.validate_profiles({"rows": rows})


def test_target_is_added_as_the_default_profile():
    rows = build([{"user": "mom", "pin_type": "none"}])
    assert [r[1] for r in rows] == ["dad", "mom"] and rows[0][9] == 0


def test_child_needs_pins_on_the_others():
    with pytest.raises(profiles.ProfileError, match="every other profile needs a PIN: dad"):
        build([{"user": "kid", "role": "child", "pin_type": "none"}])


def test_empty_pin_keeps_the_record_pin():
    old = [[1, "dad", "Dad", "numbers", "a" * 64, "b" * 32, "admin", 5, {}, 0]]
    rows = build([{"user": "dad", "pin_type": "numbers", "pin": ""}], existing=old)
    assert rows[0][4:6] == ["a" * 64, "b" * 32]
    with pytest.raises(profiles.ProfileError, match="enter a PIN for dad"):
        build([{"user": "dad", "pin_type": "directions", "pin": ""}], existing=old)


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


def test_table_defaults_and_cleared_pins():
    old = [[3, "mom", "Mom", "numbers", "a" * 64, "b" * 32, "user", 5, {"icon": "cat"}, 1],
           [1, "dad", "Dad", "none", "", "", "admin", 5, {}, 0]]
    rows = profiles.table_defaults("dad", old)
    assert [r["user"] for r in rows] == ["dad", "mom"]
    assert profiles.table_defaults("dad", []) == []
    assert rows[1]["icon"] == "cat" and rows[1]["pin"] == "" and rows[1]["pin_type"] == "numbers"
    assert profiles.clear_pins([{"user": "a", "pin": "1234"}]) == [{"user": "a", "pin": ""}]


def test_profiles_section_fields():
    import json, os
    manifest = json.load(open(os.path.join(os.path.dirname(__file__), "..", "aeriotv-presets", "plugin.json")))
    fields = options.build_fields(manifest["fields"], usernames=["dad", "kid"], saved={"target_username": "dad"},
                                  channels=[], live_groups=[], native_sections=True, tables=True, current={})
    by_id = {f["id"]: f for f in fields}
    table = by_id[profiles.TABLE]
    assert table["section"] == "sec_profiles"
    assert [c["id"] for c in table["columns"]] == ["user", "name", "role", "icon", "color", "pin_type", "pin"]
    assert table["default"] == []
    marker = by_id["sec_profiles"]
    assert marker["collapsed"] is True


def test_unchanged_row_keeps_its_stamp():
    old = [[1, "dad", "Dad", "none", "", "", "admin", 5, {}, 0]]
    rows = build([{"user": "dad", "name": "Dad", "pin_type": "none", "icon": "default", "color": "default"}], existing=old)
    assert rows[0][7] == 5
    merged = profiles.merge_rows({"rows": old}, rows)
    assert merged == {"rows": old}
