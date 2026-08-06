# Import Workflows

[Documentation index](README.md) | [Repository and server](repository-and-server.md)

Run all commands from the repository root. Set up Python once:

```bash
python3 -m venv scripts/.venv
scripts/.venv/bin/pip install -r scripts/requirements.txt
```

Every executable importer supports `--help`. `import_utils.py` is a shared module
and is not run directly.

## Import the SBUga engine (inside git module)

This imports Next RUSH plus its default skin, background, effect, particle,
configuration, all engine modes, and optional ROM, using the engine data from the [Sbuga engine](https://github.com/Sbotga/sbuga-sonolus-server). It also records the pinned
SBUga commit. If the engine name changes, pass the same name to level importers
with `--engine`.

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


## Import an engine from an SCP

The importer finds a level in the package and follows its engine, skin,
background, effect, and particle references. ZIP traversal and unsafe item names
are rejected. Use either this importer or the pinned SBUga importer to provide the
engine required by levels. SCP contents are kept in
`extractions/<package-name>/` while importing and removed afterward, including
when the import fails.

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



## Import playable SCP packages

The assigned engine must already exist. Cover, BGM, and LevelData are required;
preview audio is optional. The importer keeps SCP inputs, detects duplicate charts
using names and content hashes, updates changed levels, resolves playlists, and
generates one V3 background per unique jacket. `--force` also refreshes metadata,
cover, and preview for levels with the same original name; it does not overwrite a
different level that merely has duplicate content. Extracted packages remain in
`extractions/` only while being processed and are removed afterward. The staging
directory is ignored by Git. There is no bulk-clean option.

Place packages in `imports/`; `reference.scp` is skipped.

```bash
scripts/.venv/bin/python scripts/import_level_scp.py
```

Optional form:

```bash
scripts/.venv/bin/python scripts/import_level_scp.py \
  --import-dir PATH_TO_SCP_DIRECTORY \
  --engine next-rush-sbuga \
  --locale en \
  --force
```


## Import a chart bundle directory

Each chart file becomes a separate playable level. Its filename is appended to
the bundle name, so `master.sus` becomes `...-master`. Same-named SUS and USC
files also get a format suffix to avoid collisions. A lone
`NSLevelData.json.gz` keeps the name from `level.json` or the directory name;
names such as `master.NSLevelData.json.gz` use `master` as their suffix.
When a bundle contains multiple charts, the importer also creates a playlist
with the bundle's title and jacket containing all of those levels.

`level.json` supplies normal Sonolus metadata. It may also contain a `ratings`
object keyed by chart filename, such as `{"master": 31}`. For official PJSK
folders, the importer recognizes the region, music ID, and cover ID and fetches
missing difficulty ratings from the same regional master database used by
ChartDownloader. It also uses SBUga's silence-removed BGM because the normal
PJSK `music.mp3` can contain several seconds of leading filler. A local
`music_nosil.*` file takes priority and avoids that download. `--force` replaces
only matching output names.

The directory must contain metadata and media:

```text
level.json
music.<extension>
music_nosil.<extension>    optional synchronized override
jacket.<extension>
preview.<extension>        optional
```

It must also contain one or more supported chart files:

```text
*NSLevelData.json.gz       copied directly
*.sus                     converted to Next Sekai LevelData
*.usc                     converted to Next Sekai LevelData
```

Official PJSK ChartDownloader folders fit this layout because they contain
`easy.sus`, `normal.sus`, and the other available difficulties. Import one
self-contained directory:

```bash
scripts/.venv/bin/python scripts/import_chart_downloader.py \
  scripts/chart-downloader/out/pjsk/jp/755_cover_1312
```

Useful variants:

```bash
scripts/.venv/bin/python scripts/import_chart_downloader.py PATH --force

scripts/.venv/bin/python scripts/import_chart_downloader.py PATH \
  --engine next-rush-sbuga \
  --locale en
```



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
`renderRevision`; changing render behavior also changes the revision so stale
outputs are regenerated.

If a background looks stretched, verify that `image.png` is 2048 x 1168. If a
downloaded image cannot be opened, use `file PATH` to check that it is not an HTML
page saved from a GitHub `blob` URL.

## Build after importing

Importers write `source/`; the server reads `pack/`:

```bash
npm run build
npm start
```

Restart the process behind Caddy after rebuilding. For development, use
`npm run dev`.

## Change the engine for every level

The target engine must already exist in `source/engines/`:

```bash
scripts/.venv/bin/python scripts/set_level_engine.py ENGINE_NAME
npm run pack
```

This changes every existing level, including SCP and chart-bundle imports. It
does not convert LevelData, so only switch to an engine compatible with the
charts. Pass `--engine ENGINE_NAME` to future imports as well.

## Change generated-background brightness

Set the black-overlay alpha, then repack (`0` is brightest and `f` is darkest):

```bash
scripts/.venv/bin/python scripts/set_background_brightness.py 4
npm run pack
```

The script updates existing backgrounds and the setting used by future imports.
