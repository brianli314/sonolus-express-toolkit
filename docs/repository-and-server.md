# Build and Server

[Documentation](README.md) | [Import guide](import-workflows.md)

## Layout

```text
scripts/               import tools
imports/               input SCP packages
upstream/sbuga/files/  public engine assets
background_templates/ generated-background templates
source/                editable Sonolus catalogue
pack/                  generated catalogue
src/index.ts            Express server
dist/                   compiled server
```

## Commands

Install Node dependencies:

```bash
npm install
```

Build the catalogue and server:

```bash
npm run build
```

Start the server on port 3000:

```bash
npm start
```

For development:

```bash
npm run dev
```

The health endpoint is `GET /health`. Rebuild after changing or importing files
under `source/`.
