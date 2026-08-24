# Import Guide

[Documentation](README.md) | [Build and server](repository-and-server.md)

Run commands from the repository root.

## Setup

```bash
python3 -m venv scripts/.venv
scripts/.venv/bin/pip install -r scripts/requirements.txt
git submodule update --init --recursive
```

## Import an engine from SCP

The SCP importer reads the engine used by the first level and copies its engine,
skin, background, effect, and particle into `source/`. Temporary extracted files
are removed when it finishes.

```bash
scripts/.venv/bin/python scripts/import_engine_scp.py --scp PATH_TO_FILE.scp
```

Optional arguments:

```bash
scripts/.venv/bin/python scripts/import_engine_scp.py \
  --scp PATH_TO_FILE.scp \
  --engine-name CUSTOM_NAME \
  --locale en
```

Without `--scp`, the script uses `imports/reference.scp`.

## Import an engine from SBUga

`import_engine_public.py` copies an engine and its default skin, background,
effect, and particle from `upstream/sbuga/files` into `source/`.

```bash
scripts/.venv/bin/python scripts/import_engine_public.py
```

Options:

```bash
scripts/.venv/bin/python scripts/import_engine_public.py \
  --reference-name next-rush \
  --engine-name next-rush-sbuga \
  --locale en
```

Configuration overrides from the engine's `engine.json` are applied to the
copied engine configuration.

## Import levels

Place playable `.scp` files in `imports/`, then run:

```bash
scripts/.venv/bin/python scripts/import_level.py
```

To use another directory or engine:

```bash
scripts/.venv/bin/python scripts/import_level.py \
  --import-dir PATH_TO_SCPS \
  --engine ENGINE_NAME \
  --locale en
```

The script imports levels and playlists into `source/` and generates a
background from each level cover. Import the referenced engine first.

## Build

After importing:

```bash
npm run build
npm start
```
