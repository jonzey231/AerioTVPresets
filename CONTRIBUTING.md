# Contributing

## The schema is the contract

The record this plugin writes is defined by the AerioTV Dispatcharr Sync schema,
`docs/DispatcharrSyncSchema.md` in the AerioTV repos (Apple and Android, byte-identical). That
document is the contract, not this repository.

1. Change the schema there first. This plugin follows.
2. Refresh `docs/SCHEMA.md` here from the source and update its header (commit and date).
3. Update `aeriotv-presets/schema.py`, the fixtures in `tests/fixtures`, and the tests in the same
   commit.
4. Never write a `schemaVersion` higher than the one the AerioTV apps ship. Devices skip a record
   with a newer version, so a higher number would switch sync off for that user.

## Dispatcharr changes

Keep every Dispatcharr import in `aeriotv-presets/dispatcharr_bridge.py`. `schema.py` and `seed.py`
stay free of Django so the tests run without a server.

## Style

US spelling, the Oxford comma, no em dashes, and no emojis in code, docs, or commits. User-facing
text says AerioTV. Commit messages explain why.

## Tests

`pytest` must pass before every commit.
