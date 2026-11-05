#!/usr/bin/env bash
# Pack a sonolus-pack source folder (levels/, playlists/, engines/, ...) into one .scp
# Usage: ./make_scp.sh [source_dir] [output.scp]
set -euo pipefail

SRC="${1:-source}"
OUT="$(realpath -m "${2:-collection.scp}")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 1. source -> pack (db.json + hashed repository), same step your server uses
npx -y @sonolus/pack -i "$SRC" -o "$WORK/pack"

# 2. pack -> static server layout (sonolus/info, sonolus/levels/..., sonolus/repository/...)
#    No -a/--address, so items aren't tied to a server URL
npx -y @sonolus/generate-static -i "$WORK/pack" -o "$WORK/static"

# 3. zip it with sonolus/ at the archive root; -0 because repository files are already compressed
rm -f "$OUT"
(cd "$WORK/static" && zip -r -0 -q "$OUT" sonolus)

echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"