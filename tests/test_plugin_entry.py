from aeriotv_setup import plugin


def test_plugin_loads_without_dispatcharr():
    p = plugin.Plugin()
    ids = [f["id"] for f in p.fields]
    assert "target_username" in ids and "apply_mode" in ids
    # No Django here, so the User field stays a text box.
    user = next(f for f in p.fields if f["id"] == "target_username")
    assert user["type"] == "string"
    assert {a["id"] for a in p.actions} == {"load_lists", "show_channels", "show_groups", "preview", "apply"}


def test_unknown_action():
    assert plugin.Plugin().run("nope", {}, {"settings": {}})["status"] == "error"


def test_apply_needs_a_user():
    out = plugin.Plugin().run("apply", {}, {"settings": {}})
    assert out == {"status": "error", "message": "choose a user first"}
