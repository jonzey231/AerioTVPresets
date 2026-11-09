"""App Settings the plugin can seed: a subset of the schema's settings allowlist
(docs/SCHEMA.md section 4.9) with the exact stored values.

Pure Python, no Django. Only names with a fixed set of values (booleans,
enums, and numbers picked from schema ranges) are offered. Free text, wire
values the schema does not enumerate, colors, and device-local names are left
out. Every entry is written to the `v` lane (All devices).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

BOOL = "bool"
STR = "str"
INT = "int"
FLOAT = "float"

# Section groupings shown as info headers in App Settings.
# Each entry: (schema name, label, kind, [(stored value, label), ...] or None for bool)
_ON_OFF = None

SPEC: List[Tuple[str, List[Tuple[str, str, str, Optional[List[Tuple[Any, str]]]]]]] = [
    ("Appearance", [
        ("selectedTheme", "Theme", STR, [("Aerio", "Aerio"), ("Midnight", "Midnight"), ("Sunset", "Sunset"),
                                          ("Forest", "Forest"), ("Lavender", "Lavender"),
                                          ("Monochrome", "Monochrome"), ("Light", "Slate")]),
        ("appearanceMode", "Mode", STR, [("system", "System"), ("light", "Light"), ("dark", "Dark"),
                                         ("trueblack", "True Black")]),
        ("textScale", "Text size", FLOAT, [(v, f"{v:g}x") for v in (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.5)]),
        ("subtextScale", "Secondary text size", FLOAT, [(v, f"{v:g}x") for v in (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.5)]),
        ("textContrast", "Text contrast", FLOAT, [(round(i / 10, 1), f"{i * 10}%") for i in range(0, 11)]),
        ("timeFormat", "Time format", STR, [("system", "System"), ("12", "12 hour"), ("24", "24 hour")]),
        ("enableCategoryColors", "Category colors", BOOL, _ON_OFF),
        ("tintChannelCards", "Tint channel cards", BOOL, _ON_OFF),
    ]),
    ("Startup", [
        ("defaultTab", "Start on tab", STR, [("LiveTV", "Live TV"), ("DVR", "DVR"), ("Movies", "Movies"),
                                             ("TVShows", "TV Shows"), ("Settings", "Settings")]),
        ("skipLoadingScreen", "Skip loading screen", BOOL, _ON_OFF),
        ("autoResumeLastChannel", "Resume last channel", BOOL, _ON_OFF),
    ]),
    ("Live TV and guide", [
        ("guideLayout", "Guide layout", STR, [("basic", "Basic"), ("preview", "Preview")]),
        ("guideGroupSelector", "TV group selector", STR, [("pills", "Pills"), ("sidebar", "Sidebar")]),
        ("phoneGroupSelector", "Phone group selector", STR, [("sidebar", "Sidebar"), ("pills", "Pills")]),
        ("guideSidebarLayout", "Sidebar layout", STR, [("overlay", "Overlay"), ("shift", "Shift")]),
        ("liveTvEdgeSwipeOpensSidebar", "Edge swipe opens sidebar", BOOL, _ON_OFF),
        ("channelListShowLogos", "Show channel logos", BOOL, _ON_OFF),
        ("channelListShowNumbers", "Show channel numbers", BOOL, _ON_OFF),
        ("channelListShowNames", "Show channel names", BOOL, _ON_OFF),
        ("channelListShowProgramSubtitles", "Show program subtitles", BOOL, _ON_OFF),
        ("channelLogoSize", "Channel logo size", INT, [(v, f"{v}%") for v in (50, 75, 100, 125, 150, 200, 250)]),
        ("showEpgBadgesTv", "Program badges on TV", BOOL, _ON_OFF),
        ("showEpgBadgesMobile", "Program badges on phones and tablets", BOOL, _ON_OFF),
        ("guideProgramInfoButton", "Program info button", STR, [("off", "Off"), ("current", "Current program"), ("all", "All programs")]),
        ("programInfoButtonGuide", "Program info button in the guide", BOOL, _ON_OFF),
        ("programInfoButtonList", "Program info button in the list", BOOL, _ON_OFF),
        ("logoCornersGuide", "Rounded guide logos", BOOL, _ON_OFF),
        ("logoCornersGuideCells", "Rounded program cells", BOOL, _ON_OFF),
        ("logoCornersList", "Rounded list logos", BOOL, _ON_OFF),
        ("displayScaleLiveTv", "Live TV display scale", FLOAT, [(v, f"{v:g}x") for v in (0.85, 0.9, 1.0, 1.1, 1.25, 1.5)]),
        ("displayScaleGuide", "Guide display scale", FLOAT, [(v, f"{v:g}x") for v in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)]),
        ("guideTuneInMini", "Play channels in the mini player", BOOL, _ON_OFF),
    ]),
    ("Player", [
        ("playerInfoCard.showOnChannelChange", "Info card on channel change", BOOL, _ON_OFF),
        ("playerInfoCard.channelLogo", "Info card: channel logo", BOOL, _ON_OFF),
        ("playerInfoCard.channelName", "Info card: channel name", BOOL, _ON_OFF),
        ("playerInfoCard.programName", "Info card: program name", BOOL, _ON_OFF),
        ("playerInfoCard.programTime", "Info card: program time", BOOL, _ON_OFF),
        ("playerInfoCard.programSubtitle", "Info card: program subtitle", BOOL, _ON_OFF),
        ("playerInfoCard.programDescription", "Info card: program description", BOOL, _ON_OFF),
        ("liveRewindEnabled", "Live rewind", BOOL, _ON_OFF),
        ("liveRewindDepthMinutes", "Live rewind depth", INT, [(v, f"{v} minutes") for v in (15, 30, 60, 90, 120, 180, 240)]),
        ("liveRewindKeepRecent", "Keep rewind for recent channels", BOOL, _ON_OFF),
        ("liveRewindKeepCount", "Recent channels kept", INT, [(v, str(v)) for v in (1, 2, 3, 4, 5)]),
        ("skipBack", "Skip back", INT, [(v, f"{v} seconds") for v in (5, 10, 15, 30, 60)]),
        ("skipForward", "Skip forward", INT, [(v, f"{v} seconds") for v in (5, 10, 15, 30, 60)]),
        ("skipWithoutControls", "Skip without showing controls", BOOL, _ON_OFF),
        ("autoRecoverFrozenStreams", "Recover frozen streams", BOOL, _ON_OFF),
        ("appleTVChannelFlip", "Channel flip on the remote", BOOL, _ON_OFF),
        ("edgeBrightnessGesture", "Edge brightness gesture", BOOL, _ON_OFF),
        ("brightnessEdge", "Brightness edge", STR, [("left", "Left"), ("right", "Right")]),
        ("edgeVolumeGesture", "Edge volume gesture", BOOL, _ON_OFF),
    ]),
    ("Multiview", [
        ("multiview.tilePadding", "Tile padding", BOOL, _ON_OFF),
        ("multiview.tileCornersRounded", "Rounded tile corners", BOOL, _ON_OFF),
        ("multiview.showLogos", "Show logos", BOOL, _ON_OFF),
        ("multiview.pickerShowSubtitles", "Picker shows subtitles", BOOL, _ON_OFF),
        ("multiview.pickerShowDescriptions", "Picker shows descriptions", BOOL, _ON_OFF),
    ]),
    ("Movies, TV Shows, and DVR", [
        ("vodLibraryRefreshHours", "Refresh library every", INT, [(0, "Never"), (6, "6 hours"), (12, "12 hours"), (24, "24 hours"), (48, "48 hours"), (168, "7 days")]),
        ("tmdbPostersEnabled", "TMDB posters", BOOL, _ON_OFF),
        ("dvrPreRollMins", "DVR start early", INT, [(v, f"{v} minutes") for v in (0, 1, 2, 5, 10, 15, 30)]),
        ("dvrPostRollMins", "DVR end late", INT, [(v, f"{v} minutes") for v in (0, 1, 2, 5, 10, 15, 30, 60)]),
        ("dvrDefaultDestination", "DVR destination", STR, [("server", "Server"), ("local", "This device")]),
    ]),
    ("TV remote", [
        ("showRemoteHints", "Remote hints", BOOL, _ON_OFF),
        ("exitDialogFocusExit", "Exit dialog focuses Exit", BOOL, _ON_OFF),
    ]),
]

TRUE_BLACK = "trueblack"
FIELD_PREFIX = "set:"

# name -> (kind, allowed stored values or None for bool)
BY_NAME: Dict[str, Tuple[str, Optional[List[Any]]]] = {}
for _section, _rows in SPEC:
    for _name, _label, _kind, _opts in _rows:
        BY_NAME[_name] = (_kind, None if _opts is None else [v for v, _ in _opts])


def field_id(name: str) -> str:
    return FIELD_PREFIX + name


def option_value(value: Any) -> str:
    """The string a select stores for a schema value."""
    return f"{value:g}" if isinstance(value, float) else str(value)


def to_stored(name: str, raw: str) -> Any:
    """Convert a saved select string to the schema value, or raise ValueError."""
    kind, allowed = BY_NAME[name]
    if kind == BOOL:
        if raw in ("true", True):
            return True
        if raw in ("false", False):
            return False
        raise ValueError(name)
    for value in allowed or []:
        if option_value(value) == str(raw):
            return value
    raise ValueError(name)


def is_valid(name: str, value: Any) -> bool:
    """Check a value the plugin is about to write."""
    if name == "trueBlack":
        return isinstance(value, bool)
    if name not in BY_NAME:
        return False
    kind, allowed = BY_NAME[name]
    if kind == BOOL:
        return isinstance(value, bool)
    if name == "appearanceMode":
        return value in ("system", "light", "dark")
    if kind == INT and (isinstance(value, bool) or not isinstance(value, int)):
        return False
    if kind == FLOAT and (isinstance(value, bool) or not isinstance(value, (int, float))):
        return False
    if kind == STR and not isinstance(value, str):
        return False
    return value in (allowed or [])


def lane_from_settings(settings: Dict[str, Any], none: str) -> Dict[str, Any]:
    """The `v` lane values the admin chose (unset selects are skipped)."""
    lane: Dict[str, Any] = {}
    for name in BY_NAME:
        raw = settings.get(field_id(name))
        if raw is None or raw == "" or raw == none:
            continue
        if name == "appearanceMode":
            if raw == TRUE_BLACK:
                lane["appearanceMode"] = "dark"
                lane["trueBlack"] = True
            else:
                lane["appearanceMode"] = to_stored(name, raw)
                lane["trueBlack"] = False
            continue
        lane[name] = to_stored(name, raw)
    return lane
