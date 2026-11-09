import json
import os

from aeriotv_presets import app_settings, options, schema

MANIFEST = json.load(open(os.path.join(os.path.dirname(__file__), "..", "aeriotv-presets", "plugin.json")))
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
        "hdr:expand_live", "live_note",
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


def native(saved):
    return options.build_fields(MANIFEST["fields"], usernames=["plugin"], saved=saved, channels=CHANNELS,
                                live_groups=["News", "Sports"], movie_groups=["Drama"], series_groups=["Kids"],
                                native_sections=True)


def test_native_sections():
    fields = native({"target_username": "plugin", "expand_live": False})
    ids = [f["id"] for f in fields]
    assert not any(i.startswith("expand_") or i.startswith("hdr:") for i in ids)
    markers = [f for f in fields if f["type"] == "section"]
    assert [(m["id"], m["label"], m["collapsed"]) for m in markers] == [
        ("sec_live", "Live TV", False), ("sec_movies", "Movies", True),
        ("sec_series", "TV Shows", True), ("sec_app", "App Settings", True), ("sec_apply", "Apply", False)]
    by_id = {f["id"]: f for f in fields}
    assert by_id["favorite_1"]["section"] == "sec_live"
    assert by_id["show_live:News"]["section"] == "sec_live"
    movies = by_id["hidden_movies"]
    assert (movies["type"], movies["section"], movies["default"]) == ("multiselect", "sec_movies", [])
    assert movies["options"] == [{"value": "Drama", "label": "Drama"}]
    assert by_id["hidden_series"]["section"] == "sec_series"
    assert not any(i.startswith("show_movies:") or i.startswith("show_series:") for i in ids)
    assert by_id["apply_mode"]["section"] == "sec_apply"
    assert by_id["set:selectedTheme"]["section"] == "sec_app"
    assert by_id["app_hdr:Appearance"]["section"] == "sec_app"
    for top in ("intro", "target_username"):
        assert "section" not in by_id[top]
    assert ids[0:2] == ["intro", "target_username"] and ids[-1] == "apply_mode"
    for f in fields:
        if f["type"] != "section":
            assert f.get("section") in (None, "sec_live", "sec_movies", "sec_series", "sec_app", "sec_apply")


def test_native_sections_before_a_user():
    fields = options.build_fields(MANIFEST["fields"], usernames=["plugin"], native_sections=True)
    by_id = {f["id"]: f for f in fields}
    assert by_id["live_note"]["section"] == "sec_live"
    assert "group_order_mode" not in by_id


def test_many_live_groups_use_a_multiselect():
    groups = [f"G{i:02d}" for i in range(options.LIVE_SWITCH_LIMIT + 1)]
    fields = options.build_fields(MANIFEST["fields"], usernames=["plugin"], saved={"target_username": "plugin"},
                                  channels=CHANNELS, live_groups=groups, native_sections=True)
    ids = [f["id"] for f in fields]
    assert "hidden_live" in ids and not any(i.startswith("show_live:") for i in ids)
    few = native({"target_username": "plugin"})
    assert "hidden_live" not in [f["id"] for f in few]


def test_multiselect_picks_map_to_hidden_groups():
    saved = {"hidden_live": ["Adult", "__none__"], "show_live:Adult": False, "show_live:Kids": False,
             "hidden_movies": ["Drama"], "hidden_series": "not a list"}
    assert options.hidden_from_switches(saved) == {"live": ["Adult", "Kids"], "movies": ["Drama"], "series": []}


def test_notes_before_load():
    fields = options.build_fields(MANIFEST["fields"], usernames=["plugin"], native_sections=True)
    by_id = {f["id"]: f for f in fields}
    text = ("Choose a user and Save, then run Refresh Lists and reload the page. "
            "Run Refresh Lists again after switching users.")
    assert by_id["live_note"]["description"] == text
    assert by_id["movies_note"]["description"] == text and by_id["movies_note"]["section"] == "sec_movies"


def test_apply_mode_wording():
    labels = [o["label"] for o in next(f for f in MANIFEST["fields"] if f["id"] == "apply_mode")["options"]]
    assert labels == ["Fill: only add what the record does not have yet",
                      "Replace: overwrite the sections you set here"]


CURRENT = {"favorites": {"ids": [77, 999]}, "groupOrder": {"mode": "manual", "order": ["Sports", "Gone"]},
           "settings": {"v": {"selectedTheme": "Light", "appearanceMode": "dark", "trueBlack": True,
                              "liveRewindEnabled": False, "defaultGroup": "News"}}}


def tables_build():
    return options.build_fields(MANIFEST["fields"], usernames=["plugin"], saved={"target_username": "plugin"},
                                channels=CHANNELS, live_groups=["News", "Sports"], movie_groups=[],
                                series_groups=[], native_sections=True, tables=True, current=CURRENT)


def test_tables_replace_slots_and_start_from_the_record():
    by_id = {f["id"]: f for f in tables_build()}
    assert not any(i.startswith("favorite_") or (i.startswith("group_") and i[6:].isdigit()) for i in by_id)
    fav = by_id[options.FAVORITES_TABLE]
    assert fav["type"] == "table" and fav["section"] == "sec_live"
    assert fav["default"] == [{"channel": "77"}]  # 999 is not visible to the user
    col = fav["columns"][0]
    assert (col["id"], col["type"]) == ("channel", "select")
    assert all(o["value"] != options.NONE for o in col["options"])
    grp = by_id[options.GROUP_ORDER_TABLE]
    assert grp["default"] == [{"group": "Sports"}]
    assert grp["columns"][0]["options"] == [{"value": "News", "label": "News"}, {"value": "Sports", "label": "Sports"}]


def test_now_hints_show_record_values():
    by_id = {f["id"]: f for f in tables_build()}
    assert by_id["set:selectedTheme"]["help_text"] == "In the record now: Slate."
    assert by_id["set:appearanceMode"]["help_text"] == "In the record now: True Black."
    assert by_id["set:liveRewindEnabled"]["help_text"] == "In the record now: Off."
    assert by_id["default_group"]["help_text"].endswith("In the record now: News.")
    assert by_id["group_order_mode"]["help_text"] == "In the record now: manual."
    assert "help_text" not in by_id["set:skipBack"]
