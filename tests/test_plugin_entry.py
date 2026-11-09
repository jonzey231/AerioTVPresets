import pytest

from aeriotv_presets import plugin


def test_plugin_loads_without_dispatcharr():
    p = plugin.Plugin()
    ids = [f["id"] for f in p.fields]
    assert "target_username" in ids and "apply_mode" in ids
    # No Django here, so the User field stays a text box.
    user = next(f for f in p.fields if f["id"] == "target_username")
    assert user["type"] == "string"
    assert {a["id"] for a in p.actions} == {"load_lists", "preview", "apply"}


def test_unknown_action():
    with pytest.raises(plugin.ActionError):
        plugin.Plugin().run("nope", {}, {"settings": {}})


def test_apply_needs_a_user():
    with pytest.raises(plugin.ActionError, match="^Choose a user first.$"):
        plugin.Plugin().run("apply", {}, {"settings": {}})
