from aeriotv_presets import copying, seed

SOURCE = {
    "schemaVersion": 3, "deviceId": "d", "platform": "ios", "appVersion": "1", "updatedAt": "2026-11-01T00:00:00Z",
    "categories": {
        "favorites": {"updatedAt": "2026-11-01T00:00:00Z", "data": {"ids": [5, 9, 77]}},
        "groupOrder": {"updatedAt": "2026-11-01T00:00:00Z", "data": {"mode": "manual", "order": ["News", "Adult", "Sports"]}},
        "hiddenGroups": {"updatedAt": "2026-11-01T00:00:00Z", "data": {"live": ["Adult", "Kids"], "movies": ["Drama"], "series": []}},
        "settings": {"updatedAt": "2026-11-01T00:00:00Z", "data": {"v": {
            "selectedTheme": "Forest", "appearanceMode": "dark", "trueBlack": True, "skipBack": 7,
            "liveRewindEnabled": True, "defaultGroup": "Sports", "customAccentHex": "FF0000"}}},
    },
}


def copy():
    return copying.record_to_settings(SOURCE, channel_ids=[5, 77], live_groups=["News", "Sports", "Kids"],
                                      movie_groups=["Drama", "Comedy"], series_groups=["Kids"])


def test_copy_keeps_what_the_target_can_see():
    out, report = copy()
    assert out["favorites_rows"] == [{"channel": "5"}, {"channel": "77"}]
    assert out["favorite_1"] == "5" and out["favorite_3"] == "__none__"
    assert out["group_order_rows"] == [{"group": "News"}, {"group": "Sports"}]
    assert out["group_order_mode"] == "manual"
    assert out["hidden_live"] == ["Kids"] and out["show_live:Kids"] is False and out["show_live:News"] is True
    assert out["hidden_movies"] == ["Drama"] and out["show_movies:Comedy"] is True
    assert out["set:selectedTheme"] == "Forest" and out["set:appearanceMode"] == "trueblack"
    assert out["set:liveRewindEnabled"] == "true" and out["default_group"] == "Sports"
    assert "set:skipBack" not in out
    assert (report.dropped_channels, report.dropped_groups, report.dropped_settings) == (1, 2, 1)
    assert report.text("alice") == ("Copied favorites (2), group order, hidden groups (2), settings (4) from alice. "
                                    "Skipped 1 channels, 2 groups, 1 settings the target cannot use.")


def test_copied_settings_parse_back_to_the_same_record_values():
    out, _ = copy()
    out["target_username"] = "bob"
    req = seed.parse_settings(out)
    assert req.categories["favorites"] == {"ids": [5, 77]}
    assert req.categories["groupOrder"] == {"mode": "manual", "order": ["News", "Sports"]}
    assert req.categories["hiddenGroups"] == {"live": ["Kids"], "movies": ["Drama"], "series": []}
    assert req.categories["settings"]["v"]["trueBlack"] is True


def test_empty_source():
    out, report = copying.record_to_settings(None, channel_ids=[], live_groups=[], movie_groups=[], series_groups=[])
    assert out == {} and report.text("alice") == "alice has no AerioTV choices to copy."
