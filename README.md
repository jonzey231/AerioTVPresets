# AerioTV Setup for Dispatcharr

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
3. AerioTV with Dispatcharr Sync on the user's devices.

## Install

1. Download `aeriotv-setup-plugin-<version>.zip` from the
   [Releases](https://github.com/jonzey231/AerioTVDispatcharrPlugin/releases) page, or build it
   from a checkout with `scripts/build_zip.sh` (writes `dist/`).
2. In Dispatcharr, open Plugins, choose Install Plugin (or Import), and upload the zip.
3. Turn the plugin on and accept the trust prompt. Plugins run as server code; this one reads
   users, channels, groups, and VOD categories, and writes App Data for the user you pick.

## Using it

1. Open the plugin's settings and choose the user in the User list.
2. Save.
3. Run Load. Dispatcharr only reads a plugin's lists when it loads the plugin, so Load asks it to
   rebuild them for that user.
4. Reload the page. The sections now hold that user's channels and groups.
5. Make your choices in Live TV, Movies, TV Shows, and App Settings. Anything left on Leave empty
   or Leave as is is not written.
6. In Apply, pick Fill or Replace, then Save.
7. Run Preview. It reports what Apply would write, in one line.
8. Run Apply and confirm.

Run Load again (and reload) after choosing a different user, or after channels or groups change.

## What each section writes

| Section | Choices | Written to |
|---|---|---|
| Live TV | Favorite 1 to 10 (shown as `number name [group]`) | `favorites`, in slot order |
| Live TV | Group order (Server order, Alphabetical, or Manual) and Group position 1 to 8 | `groupOrder` |
| Live TV | Default group | `settings` (`defaultGroup`) |
| Live TV | A Show switch per group, or one Hidden Live TV groups list past 25 groups | `hiddenGroups.live` |
| Movies | Hidden movie categories list | `hiddenGroups.movies` |
| TV Shows | Hidden series categories list | `hiddenGroups.series` |
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

## How AerioTV picks it up

1. The user signs in to AerioTV with the Dispatcharr server.
2. AerioTV finds the record and offers Dispatcharr Sync.
3. After Turn On, the device applies the favorites, group order, hidden groups and categories, and
   settings. Every device that signs in as that user gets the same setup.

## Limits

1. Movie and series category lists are server-wide: every category enabled on an active M3U
   account, limited to the types the user may watch. Dispatcharr has no per-user category rule
   beyond that, and categories carry no adult flag.
2. Lists refresh only through Load and a page reload.
3. 10 favorite slots and 8 group positions.
4. Guide days is not part of the AerioTV settings that sync, so it is not offered.
5. App Settings offers settings with a fixed set of values. Number settings offer common values
   within the allowed ranges. Free text, colors, and sort orders are not offered.
6. If a user still has the AerioTV record key used before November 2026, the plugin waits until
   one of the user's devices has moved it.

## Privacy

The plugin logs user ids, counts, modes, and record sizes. It never logs channel names, group
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

- `aeriotv-setup/plugin.json`: manifest (catalog format, `manifest_version` 1, no capabilities).
- `aeriotv-setup/plugin.py`: the `Plugin` class and the Load, Preview, and Apply actions.
- `aeriotv-setup/options.py`: builds the settings fields and sections. No Django.
- `aeriotv-setup/app_settings.py`: the App Settings choices and their stored values. No Django.
- `aeriotv-setup/schema.py`: record shapes, validation, and the record key rule. No Django.
- `aeriotv-setup/seed.py`: settings parsing, Fill and Replace, and result text. No Django.
- `aeriotv-setup/dispatcharr_bridge.py`: the only module that imports Dispatcharr.
- `tests/`: pytest, with fixtures copied from the schema examples.

## Catalog status

Not submitted. A submission to [Dispatcharr/Plugins](https://github.com/Dispatcharr/Plugins) as an
external plugin needs a `plugins/aeriotv-setup/plugin.json` there with `name`, `version`, `description`,
`author`, `license`, `repo_url`, `source_type: "external"`, and `source_url` pointing at this
repository's release zip with `{version}`, plus a pull request titled `[aeriotv-setup] ...`.

## Changelog

- 0.0.1: first public release. Earlier internal builds were numbered 0.1.x.

## License

GNU Affero General Public License v3.0 or later, like the AerioTV apps. See [LICENSE](LICENSE).
