import json
import os

from aeriotv_setup import options

MANIFEST = json.load(open(os.path.join(os.path.dirname(__file__), "..", "aeriotv-setup", "plugin.json")))
CHANNELS = [
    {"id": 1042, "channel_number": 5.0, "name": "Five", "group_name": "News"},
    {"id": 77, "channel_number": 7.5, "name": "Seven", "group_name": None},
    {"id": 3, "channel_number": None, "name": "", "group_name": "Sports"},
]


def all_options_valid(fields):
    """Mirror apps/plugins/serializers.py: every option value and label is a non-empty string."""
    for f in fields:
        assert f["type"] in {"info", "boolean", "number", "select", "text", "string"}
        if f["type"] == "select":
            assert f["options"], f["id"]
            values = [o["value"] for o in f["options"]]
            for o in f["options"]:
                assert isinstance(o["value"], str) and o["value"]
                assert isinstance(o["label"], str) and o["label"]
            assert f["default"] in values, f["id"]


def test_manifest_selects_are_valid():
    all_options_valid(MANIFEST["fields"])


def test_no_database_keeps_manifest():
    fields = options.build_fields(MANIFEST["fields"], usernames=None)
    assert fields == MANIFEST["fields"]


def test_user_select_before_lists():
    fields = options.build_fields(MANIFEST["fields"], usernames=["alice", "plugin"])
    ids = [f["id"] for f in fields]
    assert ids == ["intro", "target_username", "lists_note", "group_order_mode",
                   "selected_theme", "appearance_mode", "apply_mode"]
    user = fields[1]
    assert user["type"] == "select"
    assert [o["value"] for o in user["options"]] == [options.NONE, "alice", "plugin"]
    all_options_valid(fields)


def test_full_lists():
    fields = options.build_fields(MANIFEST["fields"], usernames=["plugin"], selected_user="plugin",
                                  channels=CHANNELS, live_groups=["News", "Sports"],
                                  movie_groups=["Drama"], series_groups=[])
    all_options_valid(fields)
    by_id = {f["id"]: f for f in fields}
    assert len([i for i in by_id if i.startswith("favorite_")]) == options.FAVORITE_SLOTS
    assert len([i for i in by_id if i.startswith("group_") and i[6:].isdigit()]) == options.GROUP_ORDER_SLOTS
    fav = by_id["favorite_1"]["options"]
    assert fav[0] == {"value": options.NONE, "label": "Leave empty"}
    assert fav[1] == {"value": "1042", "label": "5 Five [News]"}
    assert fav[2] == {"value": "77", "label": "7.5 Seven [no group]"}
    assert fav[3] == {"value": "3", "label": "Unnamed [Sports]"}
    assert [o["value"] for o in by_id["hidden_movies_1"]["options"]] == [options.NONE, "Drama"]
    assert [o["value"] for o in by_id["hidden_series_1"]["options"]] == [options.NONE]
    assert by_id["default_group"]["options"][0]["label"] == "Leave as is"
    assert fields[-1]["id"] == "apply_mode"


def test_selected_user_missing_from_list_is_kept():
    fields = options.build_fields(MANIFEST["fields"], usernames=["a"], selected_user="gone")
    assert [o["value"] for o in fields[1]["options"]] == [options.NONE, "gone", "a"]


def test_channel_cap():
    rows = [{"id": i, "channel_number": i, "name": f"c{i}", "group_name": "g"} for i in range(5000)]
    assert len(options.channel_options(rows)) == options.MAX_CHANNEL_OPTIONS + 1
