# AerioTV Setup for Dispatcharr

A Dispatcharr plugin that lets a Dispatcharr admin preconfigure a user's AerioTV setup on the
server: favorite channels, Live TV group order, hidden groups, and a few settings (theme, mode, and
default group). The plugin writes that user's AerioTV Dispatcharr Sync record, the App Data key
`<username>.aeriotv`. When that user signs in to AerioTV with Dispatcharr Sync on, their devices find
the record and start from it, so nobody has to set up each phone, tablet, or TV by hand.

The record shape is the AerioTV Dispatcharr Sync schema (v3). See [docs/SCHEMA.md](docs/SCHEMA.md)
for the vendored excerpt and [CONTRIBUTING.md](CONTRIBUTING.md) for where the contract lives.

## What it does

1. You pick a Dispatcharr user and fill in any of the sections in the plugin settings, then save.
2. **Show Channels** lists the channels that user can see, with the channel ids favorites use.
   **Show Groups** lists the Live TV group names that user can see.
3. **Preview** reports what Apply would add, replace, or keep. It writes nothing.
4. **Apply** writes the record, after a confirmation.
   - **Fill** (default) only adds sections the record does not have yet. Anything a device already
     saved is left alone.
   - **Replace** overwrites the sections you filled in. For settings, only the settings you set are
     overwritten; every other saved setting stays. Sections you left blank, and everything else
     in the record (recents, progress, reminders, and the rest), are kept as they are.

Blank sections are never written. The plugin never writes a `schemaVersion` higher than 3, and it
refuses to touch a record with a newer `schemaVersion` or a malformed one. Logs carry user ids,
counts, and byte sizes, never values or record keys.

Favorites are checked against the channels the chosen user can see (the same visibility rule
Dispatcharr applies everywhere: user level, adult content preference, and assigned channel
profiles). Group names are written as typed, exactly as the server names them.

## Install

1. Download this repository and zip the `aeriotv-setup` folder:
   `zip -r aeriotv-setup.zip aeriotv-setup -x '*__pycache__*'`
2. In Dispatcharr, open **Plugins**, choose **Import**, and upload the zip.
3. Enable the plugin and accept the trust prompt. Plugins run as server code with full database
   access; this one reads users, channels, and groups, and writes App Data for the user you pick.
4. The User list is read when the plugin loads. After adding a Dispatcharr user, reload plugins to
   see the new name.

The plugin is not in the Dispatcharr plugin catalog yet.

## Trying it with a test user

1. In Dispatcharr, create a Standard user for testing (for example one named `plugin`) and assign
   it a channel profile if you want a smaller channel list.
2. In the plugin settings, pick that user, run **Show Channels**, and copy a few ids into Favorite
   channels. Set a theme. Save.
3. Run **Preview**, then **Apply** with Fill.
4. Sign in to AerioTV on a device as that user with Dispatcharr Sync on. The device offers
   Dispatcharr Sync on first launch and starts with those favorites and that theme.
5. Run **Preview** again: Fill now reports that it keeps the device copy of each section.

## Phase plan

1. Phase 1 (this release): favorites, group order, hidden groups, and selected settings.
2. Phase 2: more of the settings allowlist (appearance, guide, and player options).
3. Phase 3: AerioTV profiles.

## Status

Version 0.1.0, a scaffold. Unit tests pass (`pytest`); it has not yet run inside a Dispatcharr
server.

Built against Dispatcharr v0.33.0 (commit `1241b3f`, 2026-10-30) and the Dispatcharr plugin
catalog at commit `ae0d954` (2026-11-09). Every Dispatcharr call is in
`aeriotv-setup/dispatcharr_bridge.py`, so changes in Dispatcharr's internals are fixed in one file.

Open questions:

1. **Manifest version.** The catalog carries a manifest version 2 sample (`manifest_version`,
   declared `capabilities`, `context["data_dir"]`, async actions), but the v0.33.0 loader does not
   read `manifest_version`. This plugin uses the version 1 form, which needs no capabilities (it
   only uses the database). Revisit when a Dispatcharr release enforces version 2.
2. **User dropdown.** Dispatcharr reads `Plugin.fields` when the plugin loads, so the User list is a
   snapshot until the next reload. With no database at load, it falls back to a text box.
3. **Writer identity.** The record envelope's `platform` is `dispatcharr-plugin` and `deviceId` is a
   fixed id. Both apps accept any string there today, but the schema lists only `ios`, `tvos`, and
   `android`; the schema should name the plugin's values.
4. **Guide days.** Requested as a seeded setting, but it is not in the schema's settings allowlist
   (section 4.9), so it is not offered. Mode (`appearanceMode`) is offered beside the theme.
5. **Legacy records.** If the user still has the pre 2026-11-05 key (`app.molinete.aerio`), devices
   only move it while `<username>.aeriotv` is absent, so the plugin refuses to write until a device
   has moved it.
6. **Fill and empty sections.** Fill counts a section as present even when a device saved it empty.
   Devices treat an empty server copy as nothing to apply on their first read (schema 10a rule 2).
7. **App wording.** The apps still describe an existing record as another device's setup; seeded
   record wording is an app-side follow-up on both platforms.
8. **Minimum version.** `min_dispatcharr_version` is 0.33.0, the version read. The first release
   with the App Data API and `channels_queryset_for_user` was not confirmed.
9. **Movie and series groups.** Show Groups lists Live TV groups only; movie and series group names
   are typed by hand.

### Catalog submission requirements (not submitting yet)

From the catalog's README, CONTRIBUTING.md, and CODE_OF_CONDUCT.md:

1. Plugin folder `plugins/<slug>/` with a lowercase, hyphenated slug (`aeriotv-setup`).
2. `plugin.json` with `name`, `version` (MAJOR.MINOR.PATCH), `description`, `author` (the GitHub
   account opening the pull request) or `maintainers`, and `license` (an OSI approved SPDX id;
   `AGPL-3.0-or-later` qualifies). Optional: `min_dispatcharr_version`, `repo_url`,
   `discord_thread`.
3. External plugin (recommended): only `plugin.json` (plus optional README and logo) goes in the
   catalog, with `source_type: "external"`, `source_url` an HTTPS release zip URL containing
   `{version}`, and `repo_url`. That needs a GitHub release zip in this repository.
4. Pull request title `[aeriotv-setup] description` with a meaningful description. New plugins
   always get maintainer review; CodeQL and ClamAV scans run on the source.
5. Code of Conduct: no paid features, no undisclosed phone home (this plugin makes no network
   calls), a committed maintainer, and nothing that helps access content without authorization.
6. Any change to name, author, license, or source needs a version bump.

## Development

```
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/pytest
```

Layout:

- `aeriotv-setup/plugin.json`: manifest, settings fields, and actions (catalog format).
- `aeriotv-setup/plugin.py`: the `Plugin` class Dispatcharr loads.
- `aeriotv-setup/schema.py`: record shapes, validation, and the record key rule. No Django.
- `aeriotv-setup/seed.py`: settings parsing and the Fill and Replace merge. No Django.
- `aeriotv-setup/dispatcharr_bridge.py`: the only module that imports Dispatcharr.
- `tests/`: pytest, with fixtures copied from the schema examples.

## License

GNU Affero General Public License v3.0 or later, like the AerioTV apps. See [LICENSE](LICENSE).
