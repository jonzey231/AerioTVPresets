<img src="logo.png" width="128" alt="AerioTV">

# AerioTV Presets for Dispatcharr

A Dispatcharr plugin that lets a Dispatcharr admin set up a user's AerioTV app before the user signs
in: favorite channels, Live TV group order, hidden groups and categories, and app settings such as
theme and mode. The plugin writes that user's AerioTV Dispatcharr Sync record on the server. When
the user signs in to AerioTV, their devices offer Dispatcharr Sync and start from that setup.

## What it does

1. Shows the chosen user's channels and groups as lists to pick from.
2. Writes the picks to the user's AerioTV record, the App Data key `<username>.aeriotv`.
3. Fill mode only adds what the record does not have yet; Replace mode overwrites what you set.
4. Never touches anything else in the record (recents, progress, reminders, and the rest).

The record shape is the AerioTV Dispatcharr Sync schema, version 3. See [docs/SCHEMA.md](docs/SCHEMA.md)
and [CONTRIBUTING.md](CONTRIBUTING.md).

## Requirements

1. Dispatcharr 0.33.0 or newer, with the App Data API.
2. For collapsible sections (Live TV, Movies, TV Shows, App Settings, Apply), a Dispatcharr build
   whose plugin settings support `section` fields: the Dispatcharr `dev` branch from November 2026
   (it still reports version 0.33.0). On a build without them, the plugin falls back to Expand
   switches for each section and a flat list.
3. AerioTV 1.8.45 or newer on iPhone, iPad, and Apple TV, or AerioTV for Android 0.5.14 or newer on
   phones, tablets, and Android TV, with Dispatcharr Sync on.

## Install

1. Download `aeriotv-presets-plugin-<version>.zip` from the
   [Releases](https://github.com/jonzey231/AerioTVPresets/releases) page, or build it
   from a checkout with `scripts/build_zip.sh` (writes `dist/`).
2. In Dispatcharr, open Plugins, choose Install Plugin (or Import), and upload the zip.
3. Turn the plugin on and accept the trust prompt. Plugins run as server code; this one reads
   users, channels, groups, and VOD categories, and writes App Data for the user you pick.

## Using it

The plugin page shows the same steps:

1. Choose a user and Save.
2. Run Refresh Lists, then reload this page. Do this again after switching users.
3. Open each section and make your choices. Anything left on Leave empty or Leave as is is skipped.
4. Save.
5. Run Preview to see what would change. Preview writes nothing.
6. In Apply, pick Fill to add only what the record does not have yet, or Replace to overwrite what you set here. Run Apply and confirm.

Dispatcharr reads a plugin's lists only when it loads the plugin, and saving settings does not
reload it. Refresh Lists asks Dispatcharr to reload the plugin, which builds the lists for the saved
user. Run it again when channels or groups change.

## More tools

1. Copy from: pick a user and run Refresh Lists to fill every section from that user's AerioTV
   record. That record is only read. Channels and groups the target cannot see are skipped and
   counted in the notification.
2. Also apply to: Preview and Apply also write these users, each with its own Fill or Replace.
   Each user keeps only the favorites and groups it can see. Profiles go to the main User only.
   One notification sums up the run; the Dispatcharr log has a line per user.
3. Current record: each section opens with a short line saying what the User's record holds now.
4. Clear Record: deletes the User's AerioTV sync record after a confirmation. It removes only that
   record. Devices keep what they have and write a new record on their next sync.

## What each section writes

| Section | Choices | Written to |
|---|---|---|
| Live TV | Favorite channels table, one row per channel (shown as `number name [group]`) | `favorites`, in row order |
| Live TV | Group order (Server order, Alphabetical, or Manual) and a Manual group order table | `groupOrder` |
| Live TV | Default group | `settings` (`defaultGroup`) |
| Live TV | A Show switch per group, or one Hidden Live TV groups list past 25 groups | `hiddenGroups.live` |
| Movies | Hidden movie categories list | `hiddenGroups.movies` |
| TV Shows | Hidden series categories list | `hiddenGroups.series` |
| Profiles | Profiles table: user, display name, role (Standard or Child), icon, color, PIN type, and PIN, one row per profile in order | `profiles` (main User only) |
| App Settings | Appearance, startup, Live TV and guide, player, Multiview, Movies, TV Shows, and DVR, and TV remote settings | `settings` (all devices) |
| Apply | Fill or Replace | how the record is merged |

Hidden groups and categories are hidden in AerioTV; the user can show them again in AerioTV's group
manager.

Fill and Replace:

1. Fill (default) adds a section only when the record does not hold it yet. Anything a device
   already saved stays.
2. Replace overwrites the sections you set here. For settings, only the settings you set are
   overwritten; the user's other settings stay.
3. Sections you left empty, and every other part of the record, are kept as they are.
4. The plugin never writes a newer schema version than AerioTV knows, and it refuses a record it
   cannot read.

Profiles:

1. The User is always the default profile. Dispatcharr admins are always Admin; other users are
   Standard or Child.
2. A PIN is 4 to 6 digits (Numbers) or 4 to 6 of U, D, L, and R (Directions). It is stored only as a
   salted SHA-256, the same way the apps store it. Leave a PIN empty to keep the one in the record.
   PINs are cleared from the plugin page after a successful Apply.
3. While any profile is a Child, every other profile needs a PIN.
4. Devices offer these profiles; a profile is added on a device only when someone picks it there.
5. The Profiles table needs a Dispatcharr build with table fields.

## How AerioTV picks it up

1. The user signs in to AerioTV with the Dispatcharr server.
2. AerioTV finds the record and offers Dispatcharr Sync.
3. After Turn On, the device applies the favorites, group order, hidden groups and categories, and
   settings. Every device that signs in as that user gets the same setup.

## Limits

1. Movie and series category lists are server-wide: every category enabled on an active M3U
   account, limited to the types the user may watch. Dispatcharr has no per-user category rule
   beyond that, and categories carry no adult flag.
2. Lists refresh when the plugin loads, or through Refresh Lists and a page reload.
3. Builds without table fields show 10 favorite slots and 8 group positions instead of tables.
4. Guide days is not part of the AerioTV settings that sync (checked against the schema on both
   apps' main branches), so it is not offered.
5. App Settings offers settings with a fixed set of values. Number settings offer common values
   within the allowed ranges. Free text, colors, and sort orders are not offered.
6. If a user still has the AerioTV record key used before November 2026, the plugin waits until
   one of the user's devices has moved it.

## Privacy

The plugin logs user ids, counts, modes, and record sizes. PINs are never logged or kept after Apply. It never logs channel names, group
names, setting values, or record keys. It makes no network calls.

## Open items

1. The AerioTV schema lists the writer platforms `ios`, `tvos`, and `android`; records from the
   plugin say `dispatcharr-plugin`. Both apps accept it; the schema should name it.
2. When an action fails, Dispatcharr writes a stack trace to its log beside the red notification.
3. Not yet submitted to the Dispatcharr plugin catalog.

## Development and tests

```
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/pytest
scripts/build_zip.sh
```

Layout:

- `aeriotv-presets/plugin.json`: manifest (catalog format, `manifest_version` 1, capability `user_data`).
- `aeriotv-presets/plugin.py`: the `Plugin` class and the Refresh Lists, Preview, Apply, and Clear Record actions.
- `aeriotv-presets/options.py`: builds the settings fields and sections. No Django.
- `aeriotv-presets/app_settings.py`: the App Settings choices and their stored values. No Django.
- `aeriotv-presets/schema.py`: record shapes, validation, and the record key rule. No Django.
- `aeriotv-presets/copying.py`: Copy from, a record turned back into form choices. No Django.
- `aeriotv-presets/profiles.py`: profile rows, PIN hashing, and the Child PIN rule. No Django.
- `aeriotv-presets/seed.py`: settings parsing, Fill and Replace, per-user scoping, and result text. No Django.
- `aeriotv-presets/dispatcharr_bridge.py`: the only module that imports Dispatcharr.
- `tests/`: pytest, with fixtures copied from the schema examples.

## Catalog status

Not submitted. A submission to [Dispatcharr/Plugins](https://github.com/Dispatcharr/Plugins) as an
external plugin needs a `plugins/aeriotv-presets/plugin.json` there with `name`, `version`, `description`,
`author`, `license`, `repo_url`, `source_type: "external"`, and `source_url` pointing at this
repository's release zip with `{version}`, plus a pull request titled `[aeriotv-presets] ...`.

## Changelog

- 0.0.7: Copy from another user, Also apply to several users, a Current record line per section,
  a Profiles section, Clear Record, and clearer steps.
- 0.0.6: the steps and notes show one line each, and the steps are rewritten to match the flow.
- 0.0.5: Live TV shows only the Lists note until the lists load; clearer note text.
- 0.0.4: favorites and manual group order are tables that start from the record; settings show the value in the record now; lists build when the plugin loads, so Load becomes Refresh Lists; declares the `user_data` capability.
- 0.0.3: the description names the minimum AerioTV versions.
- 0.0.2: the catalog manifest also declares the Load, Preview, and Apply actions for `manifest_version` 1; the plugin itself is unchanged.
- 0.0.1: first public release. Earlier internal builds were numbered 0.1.x and named AerioTV Setup; their saved settings carry over.

## License

GNU Affero General Public License v3.0 or later, like the AerioTV apps. See [LICENSE](LICENSE).
