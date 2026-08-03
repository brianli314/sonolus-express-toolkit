# Repository and Server

[Documentation index](README.md) | [Import workflows](import-workflows.md)

## Overview

Python scripts populate `source/`, `@sonolus/pack` compiles it to `pack/`, and
`@sonolus/express` serves it through Caddy. The key paths are `src/index.ts`
(server), `scripts/` (importers), `imports/` (SCP staging), and
`upstream/sbuga/` (pinned engine source). `pack/` and `dist/` are ignored build
outputs.

The engine importer copies the complete engine bundle, not only play data.

## Rebuilding `source/`

SBUga supplies engine assets, SCP/ChartDownloader inputs supply levels, and
jackets produce backgrounds. `source/info.json` is maintained manually. Before
ignoring everything else, preserve the level inputs or download identifiers and
make `import_sbuga.py` copy `backgrounds/pjsk_template/`; the template exists
upstream but is not currently imported.

After that gap is fixed, the intended rule is:

```gitignore
/source/*
!/source/info.json
```

Rebuild in this order: initialize the submodule, install Python requirements,
import SBUga, import levels, then build. Exact commands are in the
[import guide](import-workflows.md).

## Build and serve

Run from the repository root:

```bash
npm install
git submodule update --init --recursive
npm run build
npm start
```

`npm run dev` rebuilds and runs TypeScript directly. The server loads `./pack` at
startup, exposes `GET /health`, and listens on port 3000; rebuild and restart
after imports.

For Caddy:

```caddyfile
sonolus.example.com {
    reverse_proxy 127.0.0.1:3000
}
```

Keep port 3000 private and verify `/health` through Caddy.

## TypeScript

`tsconfig.json` targets ES2022, uses NodeNext modules, checks strictly, reads from
`src/`, and emits to `dist/`.

`include` is not required: TypeScript's default discovery works with the current
`rootDir`. Adding `"include": ["src/**/*.ts"]` would only make that boundary
explicit.

Useful checks:

```bash
npx tsc --noEmit
npm run build
```
