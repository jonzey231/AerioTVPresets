import json
import os

from aeriotv_setup import app_settings, options, schema

MANIFEST = json.load(open(os.path.join(os.path.dirname(__file__), "..", "aeriotv-setup", "plugin.json")))
CHANNELS = [
    {"id": 1042, "channel_number": 5.0, "name": "Five", "group_name": "News"},
    {"id": 77, "channel_number": 7.5, "name": "Seven", "group_name": None},
    {"id": 3, "channel_number": None, "name": "", "group_name": "Sports"},
]
ALL_OPEN = {"target_username": "plugin", "expand_live": True, "expand_movies": True,
            "expand_series": True, "expand_app": True}


def all_valid(fields):
    """Mirror apps/plugins/serializers.py and Field.jsx."""
    ids = [f["id"] for f in fields]
    assert len(ids) == len(set(ids))
    for f in fields:
        assert f["type"] in {"info", "boolean", "number", "select", "text", "string"}
        if f["type"] == "select":
            assert f["options"], f["id"]
            for o in f["options"]:
                assert isinstance(o["value"], str) and o["value"]
                assert isinstance(o["label"], str) and o["label"]
            assert f["default"] in [o["value"] for o in f["options"]], f["id"]


def full(saved):
    return options.build_fields(MANIFEST["fields"], usernames=["plugin"], saved=saved, channels=CHANNELS,
                                live_groups=["News", "Sports"], movie_groups=["Drama"], series_groups=["Kids"])


def test_manifest_is_valid():
    all_valid(MANIFEST["fields"])


def test_no_database_keeps_manifest():
    assert options.build_fields(MANIFEST["fields"], usernames=None) == MANIFEST["fields"]


def test_default_layout_before_a_user():
    fields = options.build_fields(MANIFEST["fields"], usernames=["alice", "plugin"])
    all_valid(fields)
    assert [f["id"] for f in fields] == [
        "intro", "target_username", "expand_live", "expand_movies", "expand_series", "expand_app",
        "hdr:expand_live", "live_note", "group_order_mode",
        "hdr:expand_movies", "hdr:expand_series", "hdr:expand_app", "apply_mode"]
    assert fields[1]["type"] == "select"
    assert "collapsed" in fields[9]["label"]


def test_live_section():
    fields = full({"target_username": "plugin"})
    all_valid(fields)
    ids = [f["id"] for f in fields]
    assert [i for i in ids if i.startswith("favorite_")] == [f"favorite_{n}" for n in range(1, 11)]
    assert [i for i in ids if i.startswith("group_") and i[6:].isdigit()] == [f"group_{n}" for n in range(1, 9)]
    assert "default_group" in ids
    switches = [f for f in fields if f["id"].startswith(options.SHOW_LIVE)]
    assert [(f["label"], f["type"], f["default"]) for f in switches] == [
        ("Show News", "boolean", True), ("Show Sports", "boolean", True)]
    fav = next(f for f in fields if f["id"] == "favorite_1")["options"]
    assert fav[1] == {"value": "1042", "label": "5 Five [News]"}
    assert fav[2] == {"value": "77", "label": "7.5 Seven [no group]"}
    assert fav[3] == {"value": "3", "label": "Unnamed [Sports]"}
    assert not any(i.startswith(options.SHOW_MOVIES) or i.startswith("set:") for i in ids)
    assert ids[-1] == "apply_mode"


def test_every_section_open_at_once():
    fields = full(ALL_OPEN)
    all_valid(fields)
    ids = [f["id"] for f in fields]
    assert "show_movies:Drama" in ids and "show_series:Kids" in ids
    assert len([i for i in ids if i.startswith("set:")]) == len(app_settings.BY_NAME)
    assert ids.index("hdr:expand_live") < ids.index("hdr:expand_movies") < ids.index("hdr:expand_series") < ids.index("hdr:expand_app")


def test_live_collapsed():
    fields = full({"target_username": "plugin", "expand_live": False, "expand_app": True})
    ids = [f["id"] for f in fields]
    assert "favorite_1" not in ids and "set:selectedTheme" in ids


def test_app_setting_selects_round_trip():
    for f in full(ALL_OPEN):
        if not f["id"].startswith("set:"):
            continue
        name = f["id"][4:]
        assert name in schema.SEEDABLE_SETTINGS
        for o in f["options"][1:]:
            if name == "appearanceMode" and o["value"] == "trueblack":
                continue
            assert app_settings.is_valid(name, app_settings.to_stored(name, o["value"])), (name, o)


def test_switches_map_to_hidden_groups():
    saved = {"show_live:News": True, "show_live:Adult": False, "show_movies:Drama": "false",
             "show_series:Kids": False, "show_series:Cartoons": True, "other": False}
    assert options.hidden_from_switches(saved) == {"live": ["Adult"], "movies": ["Drama"], "series": ["Kids"]}
    assert options.hidden_from_switches({}) == {"live": [], "movies": [], "series": []}


def test_channel_cap():
    rows = [{"id": i, "channel_number": i, "name": f"c{i}", "group_name": "g"} for i in range(5000)]
    assert len(options.channel_options(rows)) == options.MAX_CHANNEL_OPTIONS + 1
