# AerioTV Setup for Dispatcharr

A Dispatcharr plugin that lets a Dispatcharr admin preconfigure a user's AerioTV setup on the
server: favorite channels, Live TV group order, hidden groups, and a few settings (theme, mode, and
default group). The plugin writes that user's AerioTV Dispatcharr Sync record, the App Data key
`<username>.aeriotv`. When that user signs in to AerioTV with Dispatcharr Sync on, their devices find
the record and start from it, so nobody has to set up each phone, tablet, or TV by hand.

The record shape is the AerioTV Dispatcharr Sync schema (v3). See [docs/SCHEMA.md](docs/SCHEMA.md)
for the vendored excerpt and [CONTRIBUTING.md](CONTRIBUTING.md) for where the contract lives.

## What it does

1. You pick a Dispatcharr user from the User list, save, and run **Load User Lists**, then reload
   the page. Every other choice is a list built for that user: Favorite 1 to 10 (that user's
   channels, shown as `number name [group]`), Group position 1 to 8, Hidden Live TV group 1 to 8,
   Hidden movie group 1 to 5, Hidden series group 1 to 5, Default group, Theme, Mode, and Apply
   mode. Anything left on Leave empty or Leave as is is not written.
2. **Show Channels** and **Show Groups** list the same channels and groups as text, for reference.
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
profiles). Group names are written exactly as the server names them.

## Install

1. Build the zip from a checkout: `scripts/build_zip.sh` writes
   `dist/aeriotv-setup-plugin-<version>.zip` (one top-level `aeriotv-setup/` folder; the build is
   byte-for-byte reproducible). Dispatcharr installs it under the plugin key `aeriotv_setup`.
2. In Dispatcharr, open **Plugins**, choose **Import**, and upload the zip.
3. Enable the plugin and accept the trust prompt. Plugins run as server code with full database
   access; this one reads users, channels, and groups, and writes App Data for the user you pick.
4. The lists are read when Dispatcharr loads the plugin. Load User Lists asks Dispatcharr to reload
   it, so after adding a Dispatcharr user or channels, run Load User Lists and reload the page.

The plugin is not in the Dispatcharr plugin catalog yet.

## Testing

You need a Dispatcharr server, a Standard test user on it (for example one named `plugin`), and an
AerioTV device that has never signed in as that user.

1. On a computer, run `scripts/build_zip.sh` in this repository to build the zip.
2. In the Dispatcharr web UI, open Plugins, choose Import, and upload the zip.
3. Turn the AerioTV Setup plugin on and accept the trust prompt.
4. Open the plugin settings, choose the test user in the User list, and save.
5. Run Load User Lists, then reload the page. Expected: the settings now show Favorite 1 to 10,
   Group position 1 to 8, the hidden group lists, and Default group.
6. Set Favorite 1 and Favorite 2 to two channels from the lists.
7. Set Group order to Manual and Group position 1 to 3 to three groups, in the order you want.
   Leave Apply mode on Fill. Save.
8. Run Preview. Expected: "Preview (fill): adds favorites, groupOrder" and "no AerioTV record yet".
9. Run Apply and confirm. Expected: "Applied (fill): adds favorites, groupOrder".
10. Run Preview again. Expected: it now says it keeps the device copy of favorites and groupOrder.
11. On the AerioTV device, add the Dispatcharr server and sign in as the test user.
12. Expected: AerioTV offers Dispatcharr Sync during first launch. Choose Turn On.
13. Expected: Live TV shows the two favorites in the order you entered, and the groups you listed
    lead the group list in that order.

## Phase plan

1. Phase 1 (this release): favorites, group order, hidden groups, and selected settings.
2. Phase 2: more of the settings allowlist (appearance, guide, and player options).
3. Phase 3: AerioTV profiles.

## Status

Version 0.1.1. Unit tests pass (`pytest`); it has not yet run inside a Dispatcharr
server.

Built against Dispatcharr v0.33.0 (commit `1241b3f`, 2026-10-30) and the Dispatcharr plugin
catalog at commit `ae0d954` (2026-11-09). Every Dispatcharr call is in
`aeriotv-setup/dispatcharr_bridge.py`, so changes in Dispatcharr's internals are fixed in one file.

Open questions:

1. **Manifest version.** The catalog carries a manifest version 2 sample (`manifest_version`,
   declared `capabilities`, `context["data_dir"]`, async actions), but the v0.33.0 loader does not
   read `manifest_version`. This plugin uses the version 1 form, which needs no capabilities (it
   only uses the database). Revisit when a Dispatcharr release enforces version 2.
2. **Lists refresh on reload only.** Dispatcharr reads `Plugin.fields` only when it loads a plugin
   (`apps/plugins/loader.py` `_load_plugin`), and its settings form cannot react to a changed field.
   Load User Lists touches Dispatcharr's shared plugin reload token so every worker rebuilds the
   fields on the next page load; that token helper is private (`_touch_reload_token`). With no
   database at load, the User field falls back to a text box.
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
9. **Movie and series groups.** The hidden movie and series lists show every VOD category on the
   server; v0.33.0 has no per-user VOD category rule to reuse.
10. **No multi-select.** Dispatcharr 0.33.0 renders info, boolean, number, select, text, and string
   fields only (`frontend/src/components/Field.jsx`), so lists use numbered selects.
11. **Select option values must be non-empty.** `apps/plugins/serializers.py` drops a whole field
   when any option value is blank, which is why 0.1.0 showed no User, Group order, Theme, or Mode
   control. Leave empty now uses the value `__none__`.
12. **Settings saved by 0.1.0** (the old text boxes) stay in Dispatcharr's saved settings but are
   ignored.

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
- `aeriotv-setup/options.py`: builds the select lists from users, channels, and groups. No Django.
- `aeriotv-setup/seed.py`: settings parsing and the Fill and Replace merge. No Django.
- `aeriotv-setup/dispatcharr_bridge.py`: the only module that imports Dispatcharr.
- `tests/`: pytest, with fixtures copied from the schema examples.

## License

GNU Affero General Public License v3.0 or later, like the AerioTV apps. See [LICENSE](LICENSE).
