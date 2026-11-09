import pytest

from aeriotv_presets import schema


def test_favorites_fixture(fixture):
    assert schema.validate_favorites(fixture("favorites.json")) == {"ids": [1042, 77, 903]}


@pytest.mark.parametrize("bad", [{"ids": [1, 1]}, {"ids": ["1"]}, {"ids": [True]}, {}, {"ids": [1], "x": 1},
                                 {"ids": list(range(1001))}])
def test_favorites_rejects(bad):
    with pytest.raises(schema.SchemaError):
        schema.validate_favorites(bad)


def test_hidden_groups_fixture(fixture):
    data = fixture("hiddenGroups.json")
    assert schema.validate_hidden_groups(data) == data
    assert not schema.is_empty(schema.HIDDEN_GROUPS, data)


def test_hidden_groups_rejects_unknown_kind():
    with pytest.raises(schema.SchemaError):
        schema.validate_hidden_groups({"radio": []})


def test_group_order_fixture(fixture):
    data = fixture("groupOrder.json")
    assert schema.validate_group_order(data) == data
    assert schema.is_empty(schema.GROUP_ORDER, {"mode": "default", "order": []})


def test_group_order_rejects_mode():
    with pytest.raises(schema.SchemaError):
        schema.validate_group_order({"mode": "random", "order": []})


def test_settings_fixture(fixture):
    data = fixture("settings.json")
    assert schema.validate_settings(data) == data
    # Every name in the doc example is one the plugin can seed.
    assert schema.validate_settings(data, strict_names=True) == data
    # A name the plugin does not seed (free text) is refused.
    with pytest.raises(schema.SchemaError):
        schema.validate_settings({"v": {"customAccentHex": "FF0000"}}, strict_names=True)


def test_settings_strict_values():
    assert schema.validate_settings({"v": {"selectedTheme": "Forest", "defaultGroup": "News"}}, strict_names=True)
    with pytest.raises(schema.SchemaError):
        schema.validate_settings({"v": {"selectedTheme": "Neon"}}, strict_names=True)
    with pytest.raises(schema.SchemaError):
        schema.validate_settings({"v": {"appearanceMode": "dim"}}, strict_names=True)


def test_record_fixture(fixture):
    record = fixture("record.json")
    assert schema.validate_envelope(record) is record


def test_record_rejects_newer_version(fixture):
    record = fixture("record.json")
    record["schemaVersion"] = 4
    with pytest.raises(schema.SchemaError):
        schema.validate_envelope(record)


@pytest.mark.parametrize("name,key", [
    ("Logan", "logan.aeriotv"),
    ("ADMIN", "admin.aeriotv"),
    ("john.doe-1_x", "john.doe-1_x.aeriotv"),
    ("a@b.com", "a-40b.com.aeriotv"),
    ("first+tag", "first-2btag.aeriotv"),
    ("_admin", "u_admin.aeriotv"),
    ("José", "jos-c3-a9.aeriotv"),
    ("a" * 60, "a" * 46 + ".aeriotv"),
    ("", None),
])
def test_user_key_vectors(name, key):
    # Test vectors from schema section 2.1.
    assert schema.user_key(name) == key
