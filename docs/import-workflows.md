# Import Workflows

[Documentation index](README.md) | [Repository and server](repository-and-server.md)

Run all commands from the repository root. Set up Python once:

```bash
python3 -m venv scripts/.venv
scripts/.venv/bin/pip install -r scripts/requirements.txt
```

Every executable importer supports `--help`. `import_utils.py` is a shared module
and is not run directly.

## Import the pinned SBUga engine

```bash
git submodule update --init --recursive
scripts/.venv/bin/python scripts/import_sbuga.py
```

Optional form:

```bash
scripts/.venv/bin/python scripts/import_sbuga.py \
  --locale en \
  --engine-name next-rush-sbuga
```

This imports Next RUSH plus its default skin, background, effect, particle,
configuration, all engine modes, and optional ROM. It also records the pinned
SBUga commit. If the engine name changes, pass the same name to level importers
with `--engine`.

## Import an engine from an SCP

Default input: `imports/reference.scp`.

```bash
scripts/.venv/bin/python scripts/import_engine_scp.py
```

Optional form:

```bash
scripts/.venv/bin/python scripts/import_engine_scp.py \
  --scp PATH_TO_REFERENCE.scp \
  --locale en \
  --engine-name CUSTOM_ENGINE_NAME
```

The importer finds a level in the package and follows its engine, skin,
background, effect, and particle references. ZIP traversal and unsafe item names
are rejected. Use either this importer or the pinned SBUga importer to provide the
engine required by levels.

## Import playable SCP packages

Place packages in `imports/`; `reference.scp` is skipped.

```bash
scripts/.venv/bin/python scripts/import_level_scp.py
```

Optional form:

```bash
scripts/.venv/bin/python scripts/import_level_scp.py \
  --import-dir PATH_TO_SCP_DIRECTORY \
  --engine next-rush-sbuga \
  --locale en
```

The assigned engine must already exist. Cover, BGM, and LevelData are required;
preview audio is optional. The importer keeps SCP inputs, detects duplicate charts
using names and content hashes, updates changed levels, resolves playlists, and
generates one V3 background per unique jacket. There is no bulk-clean option.

## Import ChartDownloader output

[`UntitledCharts/chart-downloader`](https://github.com/UntitledCharts/chart-downloader)
downloads a level and normally produces:

```text
level.json
NSLevelData.json.gz
music.<extension>
jacket.<extension>
preview.<extension>        optional
```

Import one output directory:

```bash
scripts/.venv/bin/python scripts/import_chart_downloader.py PATH_TO_LEVEL
```

Useful variants:

```bash
scripts/.venv/bin/python scripts/import_chart_downloader.py PATH_TO_LEVEL --force

scripts/.venv/bin/python scripts/import_chart_downloader.py PATH_TO_LEVEL \
  --engine next-rush-sbuga \
  --locale en
```

`--force` replaces only the same-named level. The importer uses `level.json` for
version, rating, title, artists, author, tags, description, original metadata,
and source URL when available. It cannot invent missing music, jacket, rating, or
author metadata.

For Next Sekai, obtain the exact identifier from its Sonolus item; names commonly
look like `coconut-next-sekai-<numeric-id>`.

## Generated backgrounds

A **jacket** is the square song artwork. The importers use it as the level cover
and background thumbnail, then create a local Project Sekai-style background:

```text
source/backgrounds/pjsk-generated-<cover-hash>-v3/
├── item.json
├── thumbnail
├── image.png
├── data
└── configuration
```

The Pillow renderer first produces 2048 x 2048. The importer applies the crop
matched against a known SBUga V3 result:

```python
rendered = rendered.crop((0, 440, 2048, 1608))
```

This removes 440 pixels from both top and bottom without resizing and saves a
2048 x 1168 image. The shared template uses approximately 16:9 display metadata:

```json
{"aspectRatio": 1.778, "fit": "cover", "color": "#000"}
```

Each level references the generated background by item name. Generation happens
during import, not per request. Metadata includes the jacket hash and
`renderRevision: "center-crop-2048x1168"`; changing render behavior must also
change the revision so stale images are regenerated.

SBUga's public server instead receives `background_v3_url` from its API and pairs
that prepared image with its template. The local server deliberately generates
and stores its own image, avoiding a runtime dependency on SBUga.

If a background looks stretched, verify that `image.png` is 2048 x 1168. If a
downloaded image cannot be opened, use `file PATH` to check that it is not an HTML
page saved from a GitHub `blob` URL.

## Level converters

[`sonolus-level-converters`](https://github.com/UntitledCharts/sonolus-level-converters)
is installed by `requirements.txt`. Run:

```bash
scripts/.venv/bin/sonolus-converters
```

It prompts for input, detected format, output path, and output format. Conversion
handles chart data; metadata and media still need a source such as
ChartDownloader.

## Build after importing

Importers write `source/`; the server reads `pack/`:

```bash
npm run build
npm start
```

Restart the process behind Caddy after rebuilding. For development, use
`npm run dev`.
