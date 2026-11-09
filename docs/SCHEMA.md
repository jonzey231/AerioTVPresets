# Vendored schema excerpt

Source: `docs/DispatcharrSyncSchema.md` in the AerioTV repos (Apple
https://github.com/jonzey231/AerioTV at commit a10e7c7, byte-identical in the Android repo), copied
2026-11-09. Only the sections this plugin depends on are copied, unedited. The AerioTV repos hold the
contract; when this copy and the source differ, the source wins and this file is refreshed.

Sections copied: 1.1, 2.1, 3, 4 (intro), 4.1, 4.7, 4.8, 4.9, 6.1, 6.2, 6.5, and 10a rule 2.

### 1.1 Server facts this design depends on
| Fact | Value |
|---|---|
| Endpoints | `GET/PUT/DELETE /api/accounts/users/me/app-data/<key>/`, `GET /api/accounts/users/me/app-data/` (list keys and sizes) |
| Admin cross-user | `/api/accounts/users/<id>/app-data/<key>/` (user_level >= 10). AerioTV does not use it for writes in v1 |
| Key pattern | `^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$` |
| Limits | 25 keys per user, 128 KiB per key (compact UTF-8 JSON), 1 MiB total per user, depth 8 (Dispatcharr dev c1920131, 2026-10-18; one database row per key). Servers before that commit cap at 32 KiB per key and 128 KiB per user and answer 413 the same way |
| Value | Must be a JSON object. PUT replaces the whole value. No PATCH, no ETag, no versioning |
| Concurrency | Last writer wins (server serializes with a row lock) |
| Visibility | Any admin can view and clear any user's data in the web UI |
| Errors | `{detail, code}`: 400 key_invalid, value_not_object, value_has_nul, value_too_deep; 413 value_too_large, total_too_large, body_too_large; 409 max_apps; 403 forbidden; 404 key_not_found |


### 2.1 Key name
`<user>` comes from the signed-in Dispatcharr username, read once per sync session with
`GET /api/accounts/users/me/` using the same credential as the App Data calls (the base user's or
the active profile's own key). The rule, identical on both platforms:

1. Take the username's UTF-8 bytes.
2. ASCII `A` to `Z` become lowercase. `a` to `z`, `0` to `9`, `_`, `.`, and `-` stay.
3. Every other byte becomes `-` plus two lowercase hex digits (percent-encoding with `-` in place of
   `%`, because the server key pattern `^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$` rejects `%`).
4. If the result does not start with a letter or digit, prefix `u`.
5. Cut to 46 characters, so `<user>.aeriotv.favorites` fits the 64 the server allows.
6. Append `.aeriotv`. An empty username has no key; sync waits for the next attempt.

Two usernames that map to one name cannot mix data: App Data is stored per user. The v2 three-key
layout under the new name would be `<user>.aeriotv`, `<user>.aeriotv.favorites`, and
`<user>.aeriotv.progress`; v3 writes only `<user>.aeriotv`.

Test vectors (Apple `Scripts/dsync-tests`, Android `DsyncV2Test.userKeyDerivation`):

| Username | Key |
|---|---|
| `Logan` | `logan.aeriotv` |
| `ADMIN` | `admin.aeriotv` |
| `john.doe-1_x` | `john.doe-1_x.aeriotv` |
| `a@b.com` | `a-40b.com.aeriotv` |
| `first+tag` | `first-2btag.aeriotv` |
| `_admin` | `u_admin.aeriotv` |
| `José` | `jos-c3-a9.aeriotv` |
| 60 x `a` | 46 x `a` then `.aeriotv` |
| empty | none |


## 3. Envelope (every key) and category sub-objects

```json
{
  "schemaVersion": 3,
  "deviceId": "6F1C2A9E-4B7D-4C1E-9E1A-0D2B8C3F5A11",
  "platform": "ios",
  "appVersion": "1.8.44",
  "updatedAt": "2026-10-17T18:04:05Z",
  "categories": {
    "favorites": {"updatedAt": "2026-10-17T18:04:05Z", "deviceId": "6F1C...5A11", "data": {"ids": [1042, 77]}},
    "recents": {"updatedAt": "2026-10-17T17:50:00Z", "deviceId": "A2B9...0C44", "data": {"rows": [[1042, 1760724245]]}},
    "settings": {"updatedAt": "2026-10-17T18:04:05Z", "deviceId": "6F1C...5A11", "data": {"v": {"selectedTheme": "Midnight"}, "tv": {"textScale": 1.3}, "mobile": {"textScale": 1.0}}}
  }
}
```

The envelope fields describe the last write of the whole key. Each category is a sub-object under
`categories` with its own `updatedAt` (ISO 8601, same rule as below), `deviceId` (the device that last
wrote THAT category), `data` (section 4), and optional `extra`. Merge, round-trip, and caps apply per
category exactly as in v1 (section 6): the envelope fields of v1 map to the sub-object's
`updatedAt`/`deviceId`/`data`/`extra`.

A write of a key re-emits every category it holds: it reads the key first (section 7.4a), replaces
only the categories it rebuilt, and round-trips every other category (including ones this device has
not read, has turned off, or does not know) untouched.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | int | 3 for the single-key layout (2 was the three-key layout, 1 one key per category). Bump only on a breaking change |
| `deviceId` | string | Random UUID generated once per install, stored locally, never tied to hardware ids |
| `platform` | string | `"ios"` (iPhone, iPad, Mac), `"tvos"`, `"android"` (phone, tablet, TV) |
| `appVersion` | string | Diagnostics only |
| `updatedAt` | string | ISO 8601 UTC, second precision, `Z` suffix |
| `categories` | object | Category name to sub-object (`updatedAt`, `deviceId`, `data`, optional `extra`) |
| `extra` (in a sub-object) | object, optional | Fields a newer writer added within the same `schemaVersion` (section 6.2) |

Reader rules:
1. Missing envelope fields or wrong types: ignore the key, log `[DSYNC] malformed <key>`, do not overwrite it. A sub-object missing `updatedAt` or `data` is ignored the same way, alone.
2. `schemaVersion` greater than the reader knows: ignore the key, log `[DSYNC] skip <key> v<n> > v<known>`, and do not write that key until the app updates (writing would downgrade it).
3. `schemaVersion` lower: upgrade in memory, write back at the current version on the next local change. Older builds read the v3 key as a higher `schemaVersion` and skip it (rule 2).

Encoding: compact JSON (no spaces), UTF-8, no NUL characters, max nesting depth 4 in practice.
Timestamps inside `data` are integer Unix seconds (UTC) to save bytes; only the envelope uses ISO 8601.

## 4. Payloads

IDs:
- Channel: Dispatcharr channel `id` (int). Not the UUID, not the channel number. favorites, recents,
  collections, and reminders all use it. Android keys channels locally as `"disp:<uuid>"` and
  translates them through its channel cache (the Dispatcharr channel id stored per cached channel)
  in both directions. A local key or a remote id it cannot translate (cache not built yet, channel
  gone) is never deleted: it is left out of the translation and kept as is on both sides. Apple
  follows the same rule.
- VOD: the Dispatcharr INTEGER primary keys (the `id` field `/api/vod/...` returns for movies,
  episodes, and series) as JSON ints in `vodId` and `seriesId` (Dispatcharr maintainer's request).
  Never the UUID. Apple must use the same integer ids. Each app maps them to whatever it keys local
  rows by (Android: movie and episode UUIDs locally, resolved through its VOD catalog and the series
  episode lists); a local row it cannot resolve yet stays on that device and is not written, and a
  pulled id it cannot resolve is skipped (never deleted on either side).
- Program: XMLTV programme id is not stable across EPG refreshes, so reminders key on `channelId` plus `start` (Unix seconds). That pair is the identity on both platforms.
- Group: group name (string), as the server sends it.
- Rows are compact arrays (positional). Position meanings are fixed per `schemaVersion`; new positions may only be appended (readers ignore extra trailing positions).

### 4.1 favorites (cap 1000)
```json
{"ids":[1042,77,903]}
```
`ids`: int[], in display order, no duplicates. Membership and order in one array.


### 4.7 hiddenGroups
```json
{"live":["Adult","Spanish"],"movies":[],"series":["Kids"]}
```
string[] each, cap 500 names each.

### 4.8 groupOrder
```json
{"mode":"manual","order":["Sports","News","Movies"]}
```
`mode`: `"default"`, `"alphabetical"`, or `"manual"`. `order`: string[], cap 500, used when manual.

### 4.9 settings
```json
{"v":{"selectedTheme":"Midnight","appearanceMode":"dark","trueBlack":true},"tv":{"textScale":1.3},"mobile":{"textScale":1.0}}
```
`v`, `tv`, `mobile`: maps of schema name to bool, int, double, or string. Only names in this
allowlist are written; `tv` and `mobile` are optional, and unknown lanes round-trip.

Lanes and scopes. Each Sync Categories row has a per-device scope (`syncScope.<item>`, device-local,
never synced itself):
1. A device offers only its own class. A TV shows All devices, TVs only, and Off; a phone or tablet
   shows All devices, Phones and tablets only, and Off. A stored scope for the other class (for example
   after a restore onto a different device class) is treated as All devices.
2. A device writes only to `v` or its own class lane (`tv` on a TV, `mobile` on a phone or tablet),
   and reads only `v` or its own class lane.
3. All devices writes and reads `v`. TVs only / Phones and tablets only writes and reads the class
   lane. Changing an item from All devices to the class lane seeds the class lane from the CURRENT
   LOCAL value on the next push, and from then on that device ignores `v` for the item; changing back
   to All devices pushes the local value to `v`.
4. Precedence is scope only: no merging across lanes, and no fallback from the class lane to `v` or
   back. A name missing from the lane this device reads is simply not applied.
5. Off writes nothing and reads nothing; the value already stored in any lane is left untouched.
6. A group row (for example Appearance) shows the same class-filtered choices, reads "Mixed" when
   its items differ, and picking a value sets every item in the group.
7. Names a device does not write (other items, other lanes, other platforms' names) round-trip (6.2).
The Drive preferences snapshot carries the same lanes (`keys` is `v`, plus `tv` and `mobile`) with the
same rules.

Allowlist. Item = the Sync Categories row (same ids and labels on both platforms). Dispatcharr names
are canonical; the Drive column lists Drive's wire name where it differs (kept for backward
compatibility):

| Schema name | Type | Item | Apple key | Android key | Drive name |
|---|---|---|---|---|---|
| selectedTheme | string | selectedTheme | selectedTheme | selected_theme | |
| customThemeHex | string | selectedTheme | customThemeHex | custom_theme_hex | |
| appearanceMode | string | appearanceMode | appearanceMode | appearance_mode | |
| trueBlack | bool | trueBlack | appearance.trueBlack | appearance_true_black | appearanceTrueBlack |
| useCustomAccent | bool | customAccent | useCustomAccent | use_custom_accent | |
| customAccentHex | string | customAccent | customAccentHex | custom_accent_hex | |
| liquidGlassStyle | string | glassEffect | liquidGlassStyle | (Apple only: round-trip) | |
| textScale, subtextScale, textContrast | double | textScale, subtextScale, textContrast | TextScale.key, SubtextScale.key, TextContrast.key | text_scale, subtext_scale, text_contrast | |
| timeFormat | string | timeFormat | ClockFormat.defaultsKey | ui_time_format | |
| defaultTab | string | defaultTab | defaultTab | default_tab | |
| skipLoadingScreen | bool | skipLoadingScreen | appBehaviorsSkipLoadingScreen | app_behaviors_skip_loading_screen | |
| autoResumeLastChannel | bool | resumeLastChannel | appBehaviorsAutoResumeLastChannel | app_behaviors_auto_resume_last_channel | |
| defaultLiveTvView | string | defaultLiveTVView | defaultLiveTVView | default_live_tv_view | |
| guideLayout | string | guideLayout | liveTVLayout | live_tv_layout | |
| guideGroupSelector, phoneGroupSelector, guideSidebarLayout | string | groupSelection | RemoteControlStore keys, phoneGroupSelector | guide_group_selector, phone_group_selector, guide_sidebar_layout | |
| liveTvEdgeSwipeOpensSidebar | bool | edgeSwipeSidebar | liveTVEdgeSwipeOpensSidebar | live_tv_edge_swipe_opens_sidebar | |
| channelListShowLogos, channelListShowNumbers, channelListShowNames, channelListShowProgramSubtitles | bool | showChannelLogos, showChannelNumbers, showChannelNames, showProgramSubtitles | ui.showChannelLogos, ui.showChannelNumbers, ui.showChannelNames, ui.showProgramSubtitles | ui_show_channel_logos, ui_show_channel_numbers, ui_show_channel_names, ui_show_program_subtitles | |
| channelLogoSize | int | logoSize | ui.channelLogoSize | ui_channel_logo_size_tenths | |
| showEpgBadgesTv, showEpgBadgesMobile | bool | programBadges | showEpgBadges.tv, showEpgBadges.mobile | ui_show_epg_badges_tv, ui_show_epg_badges_mobile | |
| hiddenEpgBadges | string | programBadges | ui.hiddenEpgBadges | ui_hidden_epg_badges | |
| guideProgramInfoButton | string | programInfoButton | guideProgramInfoButton | guideProgramInfoButton | |
| programInfoButtonGuide, programInfoButtonList | bool | programInfoButton | guideProgramInfoButtonGuideView, guideProgramInfoButtonListView | programInfoButtonGuide, programInfoButtonList | |
| logoCornersGuide | bool | roundedGuideLogos | LogoCorners.guideKey | ui_rounded_artwork_guide | |
| logoCornersGuideCells | bool | roundedProgramCells | LogoCorners.guideCellsKey | guide_rounded_program_cells | |
| logoCornersList | bool | roundedListLogos | LogoCorners.listKey | ui_rounded_artwork | |
| displayScaleLiveTv, displayScaleGuide | double | liveTVDisplayScale | listScale, guideScale | display_scale_live_tv, guide_scale | |
| enableCategoryColors | bool | categoryColors | enableCategoryColors | category master key | |
| categoryColor.<bucket> | string | categoryColors | categoryColor.<bucket> | categoryColor.<bucket> | |
| categoryBucketEnabled.<bucket> | bool | categoryColors | categoryBucketEnabled.<bucket> | categoryBucketEnabled.<bucket> | |
| customCategories | string (JSON, max 4 KiB) | categoryColors | CategoryColor.customCategoriesKey | category custom JSON key | customCategoryColors.v1 |
| tintChannelCards | bool | tintChannelCards | tintChannelCards | (Apple only: round-trip) | |
| playerInfoCard.showOnChannelChange | bool | infoCard | playerShowChannelInfoCard | playerShowChannelInfoCard | playerShowChannelInfoCard |
| playerInfoCard.channelLogo, .channelName, .programName, .programTime, .programSubtitle, .programDescription | bool | infoCard | playerInfoCardChannelLogo (and siblings) | player_card_show_channel_logo (and siblings) | |
| liveRewindEnabled, liveRewindKeepRecent | bool | liveRewind | liveRewindEnabled, liveRewindRetainChannels | live_rewind_enabled, live_rewind_keep_recent | |
| liveRewindDepthMinutes, liveRewindKeepCount | int | liveRewind | liveRewindDepthMinutes, liveRewindRetainCount | live_rewind_depth_minutes, live_rewind_keep_count | |
| liveRewindRetentionHours, liveRewindBudgetGb | int | liveRewind | (Android only) | live_rewind_retention_hours, live_rewind_budget_gb | |
| skipBack, skipForward | int | skipIntervals | skipBackSeconds, skipForwardSeconds | skip_back_seconds, skip_forward_seconds | skipBackSeconds, skipForwardSeconds |
| skipWithoutControls | bool | skipWithoutControls | player.skipWithoutControls | skip_without_controls | |
| autoRecoverFrozenStreams | bool | autoRecover | appBehaviorsAutoRecoverFrozenStreams | app_behaviors_auto_recover_frozen_streams | |
| appleTVChannelFlip | bool | channelFlip | appBehaviorsAppleTVChannelFlip | app_behaviors_apple_tv_channel_flip | |
| edgeBrightnessGesture, brightnessEdge | bool, string | edgeBrightness | appBehaviorsEdgeBrightnessGesture, appBehaviorsBrightnessEdge | in_player_gesture_brightness, in_player_gesture_brightness_edge | |
| edgeVolumeGesture | bool | edgeVolume | appBehaviorsEdgeVolumeGesture | in_player_gesture_volume | |
| multiview.audioFocusStyle | string | multiviewAudioFocus | multiviewAudioFocusStyle | multiview_audio_focus_style | |
| multiview.tilePadding | bool | multiviewPadding | multiviewTilePadding | multiview_tile_padding | |
| multiview.tileCornersRounded | bool | multiviewCorners | multiviewTileCornersRounded | multiview_tile_corners_rounded | |
| multiview.showLogos, multiview.logoPosition, multiview.logoSize | bool, string, int | multiviewLogos | multiview.showLogos, multiview.logoPosition, multiview.logoSize | multiview_show_logos, multiview_logo_position, multiview_logo_size | |
| multiview.pickerShowSubtitles, multiview.pickerShowDescriptions | bool | multiviewSubtitles, multiviewDescriptions | multiviewPickerShowSubtitles, multiviewPickerShowDescriptions | multiview_picker_show_subtitles, multiview_picker_show_descriptions | |
| vodLibraryRefreshHours | int | refreshLibrary | vodLibraryRefreshHours | vod_library_refresh_hours | |
| tmdbPostersEnabled | bool | tmdb | TMDBPosters.enabledDefaultsKey | app_behaviors_program_posters_tmdb_enabled | programPostersTmdbEnabled |
| displayScaleMovies | double | vodDisplayScale | uiScale | display_scale_movies | |
| moviesSortOrder, seriesSortOrder | string | vodSortOrder | moviesSortOrder, seriesSortOrder | movies_sort_order, series_sort_order | |
| dvrPreRollMins, dvrPostRollMins | int | preRoll, postRoll | dvrDefaultPreRollMins, dvrDefaultPostRollMins | dvr_default_pre_roll_mins, dvr_default_post_roll_mins | |
| dvrDefaultDestination | string | defaultDestination | (Android only) | dvr_default_destination | |
| dvrSortOrder | string | dvrSortOrder | dvrSortOrder | dvr_sort_order | |
| showRemoteHints | bool | remoteHints | showRemoteHintsKey | show_remote_hints | |
| exitDialogFocusExit | bool | exitFocus | (Android only) | exit_dialog_focus_exit | |
| guideTuneInMini | bool | playChannelsIn | RemoteControlStore.tuneInMiniKey | guide_tune_in_mini | |
| defaultGroup | string | groupOrder | defaultChannelGroup | default_group_token_<playlistId> | defaultGroup (JSON object, playlist id to token) |
| lastGroup | string | groupOrder | (Android only) | live_group_token_<playlistId> | lastGroup (JSON object) |
| recentGroupVisible | bool | groupOrder | (Android only) | recent_group_visible_<playlistId> | recentGroupVisible (JSON object) |

`defaultChannelGroup` (Apple's key) and `defaultGroup` are one setting; the schema name is
`defaultGroup`. The three per-playlist names carry the session's playlist only on Dispatcharr (its data
is already per profile and per playlist) and follow the Group Order data row, not a scope.

Values (Apple maps to exactly these strings and numbers). On read, an unknown value or a value of the
wrong type is ignored and the local setting is left unchanged:
| Schema name | Values |
|---|---|
| selectedTheme | `"Aerio"`, `"Midnight"`, `"Sunset"`, `"Forest"`, `"Lavender"`, `"Monochrome"`, `"Light"`, `"Custom"` (Android AppTheme enum names, case sensitive). Since 2026-11-05 the UI shows `"Light"` as Slate; the wire value stays `"Light"` |
| appearanceMode | `"dark"` (default), `"light"`, `"system"` |
| defaultTab | `"LiveTV"`, `"DVR"`, `"Movies"`, `"TVShows"`, `"Settings"` (Android AppTab enum names); absent or `""` = Live TV |
| timeFormat | `"system"` (default), `"12"`, `"24"` |
| textScale, subtextScale, displayScaleLiveTv, displayScaleMovies | number 0.85 to 1.50, default 1.0; text scales snap to 0.05 steps |
| displayScaleGuide | number 0.5 to 2.0, default 1.0 |
| textContrast | number 0.0 to 1.0 in 0.1 steps, default 0.0; readers clamp and snap |
| guideProgramInfoButton | `"off"`, `"current"`, `"all"` |
| guideGroupSelector | `"pills"`, `"sidebar"` |
| phoneGroupSelector | `"sidebar"` (default), `"pills"` |
| guideSidebarLayout | `"overlay"` (default), `"shift"` |
| guideLayout | `"basic"` (default), `"preview"` |
| defaultLiveTvView | the Android wire value as stored, up to 20 characters; `""` = the device's form-factor default |
| customAccentHex, categoryColor.<bucket> | `"RRGGBB"` hex, an optional leading `#` accepted; customAccentHex `""` = the theme's accent |
| customThemeHex | `"RRGGBB"` hex, an optional leading `#` accepted; the Custom theme's base color (the whole Custom palette and its matching accent derive from it) |
| appearanceMode, trueBlack | Unchanged on the wire. Since 2026-11-05 the UI shows one Mode choice (System, Light, Dark, True Black): True Black is written as appearanceMode `"dark"` plus trueBlack `true`, and every other choice writes trueBlack `false`. Readers honor trueBlack only with `"dark"`, so a received System or Light with trueBlack `true` renders as plain System or Light |
| hiddenEpgBadges | one string, badge ids separated by commas (no spaces), up to 1024 characters; `""` = none hidden |
| customCategories | JSON array string, up to 4 KiB |
| skipBack, skipForward | int seconds, one of 5, 10, 15, 30, 60 |
| channelLogoSize | int 25 to 250 (Android tenths, 100 = default size) |
| dvrPreRollMins, dvrPostRollMins | int minutes 0 to 240 |
| dvrDefaultDestination | `"server"` (default), `"local"` |
| vodLibraryRefreshHours | int hours 0 to 720 |
| liveRewindDepthMinutes | int minutes 1 to 1440 |
| liveRewindKeepCount | int 1 to 5 |
| liveRewindRetentionHours | int 1 to 720 |
| liveRewindBudgetGb | int 1 to 500 |
| brightnessEdge | `"left"` (default), `"right"` |
| multiview.logoSize | int 5 to 25 |
| moviesSortOrder, seriesSortOrder, dvrSortOrder, multiview.audioFocusStyle, multiview.logoPosition | the Android wire value, up to 40 characters; an unknown value falls back to the default |
| defaultGroup, lastGroup | the active playlist's group token exactly as stored, any string up to 200 characters; `""` = none. An unknown group is stored as is and the launch falls back |
| every bool row | JSON `true` or `false`, never a string |

Excluded from settings (own keys or device-local, section 2): `remoteControlMap`, `radioModeByDefault`,
`favoriteChannelIDs`, `favoriteOrder`, `channelGroupOrder*`, `hiddenChannelGroups` and siblings,
`streamBufferSize`, `networkTimeout`, `maxRetries`, `bgRefresh*`, display matching, passthrough, DVR
storage, learned remote buttons, debug and update options, `tmdbApiKey`, `preferAVPlayer`.
Parity rule: an "(Apple only)" or "(Android only)" row is a parity gap to close, not a design choice;
until closed, the other platform round-trips it (6.2).

Settings are per profile on both platforms: a pulled `settings` applies to the profile whose token
made the request, never to another profile on the device.


## 6. Merge, round-trip, and versioning

### 6.1 Merge rule
Last writer wins per key, by envelope `updatedAt`. On pull, if remote `updatedAt` is newer than the
local copy's last-applied `updatedAt`, apply remote as a full replace of that category. Ties: higher
`deviceId` string wins (deterministic). No field-level merge in v1.

Exception, progress and recents: before writing, merge local rows with the last pulled remote rows
by id, keep the newer row per id (row `updatedAt` or `watchedAt`), then apply caps. This keeps two
devices watching different titles from erasing each other.

### 6.2 Round-trip (PUT is a full replace)
Each platform stores the raw last-pulled JSON for every key and, on write:
1. Starts from that raw object.
2. Replaces only the fields it owns (the `data` members and rows this document defines and it supports).
3. Re-emits untouched: unknown top-level `data` members, unknown settings names in `settings.v`,
   trailing row positions it does not know, the whole `remoteMap` on phones, and the envelope `extra`.
Settings rows it does not support (for example Android today for `categoryColor.*`) are therefore
preserved byte for byte.


### 6.5 Key rename to `<user>.aeriotv` (2026-11-05)
After the list call, if `<user>.aeriotv` is not listed and any legacy key is (`app.molinete.aerio`
or any `app.molinete.aerio.*`), the app GETs every legacy key, merges them as in section 6.4 (a
legacy v3 value alone moves unchanged), PUTs the result to `<user>.aeriotv` (413 walks the section 8
trims), then DELETEs every legacy key (404 counts as gone). Log
`[DSYNC] migrated key (R read, D of N old keys removed)`, never a value, key, token, or URL. A
5xx or network failure stops the pull and the rename runs again next time; a PUT refused for
another reason keeps the old keys. Once `<user>.aeriotv` is listed the rename never runs again,
so whichever device syncs first moves the record once and every other device reads the new key.
Every write goes to `<user>.aeriotv`. The setup probe reads `<user>.aeriotv` and falls back to the
legacy key while it is absent; the QR restore offer counts either key as present. The API calls
are unchanged: the same `users/me/app-data/` endpoints, plus the `users/me/` read the app already
makes; only the key in the path differs.


Rule 2, first-pull seeding. An empty or missing server copy never overwrites what a user already has when they turn on Dispatcharr Sync:

1. Missing (bucket 404, absent from the list, or category absent inside the bucket): the key is marked read and not present, and the post-pull flush pushes local up. This was already the behavior.
2. Present with empty data (no ids, rows, names, or lanes; `groupOrder` with mode `default` and no order) on the first read of that key for this user on this device (no server stamp ever consumed here): the envelope is recorded as consumed without applying it, the key is marked dirty, and local is pushed up. Log line: `[DSYNC] pull <key> bytes=<n> empty on server, first pull: seeding from local`. Primitive values (for example `radioDefault.on=false`) are real choices and apply as usual. An empty copy seen after the first read is a real change from another device and applies as usual. `profiles` merges per row and is exempt.

