#!/bin/sh
# Builds the zip the Dispatcharr Plugins page imports: one top-level folder,
# aeriotv-presets/, holding plugin.json and plugin.py. Dispatcharr installs it
# under the key aeriotv-presets (older builds: aeriotv_presets, apps/plugins/api_views.py, _sanitize_plugin_key).
# Reproducible: sorted entries, fixed timestamps and permissions.
# Usage: scripts/build_zip.sh [output.zip]
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$ROOT/aeriotv-presets/plugin.json")
OUT=${1:-"$ROOT/dist/aeriotv-presets-plugin-$VERSION.zip"}
mkdir -p "$(dirname "$OUT")"
python3 - "$ROOT" "$OUT" <<'PY'
import os, sys, zipfile
root, out = sys.argv[1], sys.argv[2]
src = os.path.join(root, "aeriotv-presets")
files = sorted(
    n for n in os.listdir(src)
    if os.path.isfile(os.path.join(src, n)) and not n.endswith(".pyc") and not n.startswith(".")
)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for name in files:
        info = zipfile.ZipInfo("aeriotv-presets/" + name, date_time=(2026, 1, 1, 0, 0, 0))
        info.external_attr = 0o644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        with open(os.path.join(src, name), "rb") as fh:
            zf.writestr(info, fh.read())
    # Dispatcharr shows logo.png from the plugin folder on the plugin card.
    logo = os.path.join(root, "logo.png")
    if os.path.isfile(logo) and "logo.png" not in files:
        info = zipfile.ZipInfo("aeriotv-presets/logo.png", date_time=(2026, 1, 1, 0, 0, 0))
        info.external_attr = 0o644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        with open(logo, "rb") as fh:
            zf.writestr(info, fh.read())
print(out)
PY
