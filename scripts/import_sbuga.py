#!/usr/bin/env python3
"""Import the pinned Sbuga Next RUSH engine into the Sonolus Pack source tree."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from import_utils import (
    localize,
    normalize_tags,
    replace_directory,
    validate_item_name,
    write_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = PROJECT_ROOT / "upstream" / "sbuga"
SOURCE_ROOT = PROJECT_ROOT / "source"
LOCALE = "en"
SOURCE_ENGINE = "next-rush"
ENGINE_NAME = "next-rush-sbuga"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the pinned SBUga engine.")
    parser.add_argument(
        "--locale",
        default=LOCALE,
        help="Locale used to select the engine's default skin.",
    )
    parser.add_argument(
        "--engine-name",
        default=ENGINE_NAME,
        type=validate_item_name,
        help="Name of the imported engine item.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine_source = UPSTREAM / "files" / "engines" / SOURCE_ENGINE

    engine_metadata = load_json(engine_source / "engine.json")

    localized_skins = engine_metadata.get("skin_name_locale", {})
    skin_name = localized_skins.get(args.locale, engine_metadata["skin_name"])

    background_name = engine_metadata["background_name"]
    effect_name = engine_metadata["effect_name"]
    particle_name = engine_metadata["particle_name"]

    skin_source = UPSTREAM / "files" / "skins" / skin_name
    background_source = UPSTREAM / "files" / "backgrounds" / background_name
    effect_source = UPSTREAM / "files" / "effects" / effect_name
    particle_source = UPSTREAM / "files" / "particles" / particle_name

    require_directories(
        engine_source,
        skin_source,
        background_source,
        effect_source,
        particle_source,
    )

    engine_target = replace_directory(SOURCE_ROOT / "engines" / args.engine_name)
    skin_target = replace_directory(SOURCE_ROOT / "skins" / skin_name)
    background_target = replace_directory(SOURCE_ROOT / "backgrounds" / background_name)
    effect_target = replace_directory(SOURCE_ROOT / "effects" / effect_name)
    particle_target = replace_directory(SOURCE_ROOT / "particles" / particle_name)

    # Engine resources. Extensionless outputs are already compiled Sonolus
    # resources, so @sonolus/pack will copy them without reprocessing them.
    copy_required(
        engine_source,
        engine_target,
        {
            "thumbnail.png": "thumbnail.png",
            "EnginePlayData": "playData",
            "EngineWatchData": "watchData",
            "EnginePreviewData": "previewData",
            "EngineTutorialData": "tutorialData",
        },
    )

    copy_optional(
        engine_source / "EngineRom",
        engine_target / "rom",
    )

    install_engine_configuration(
        engine_source / "EngineConfiguration",
        engine_target / "configuration",
        engine_metadata.get("config_overrides", {}),
    )

    # Skin resources.
    copy_required(
        skin_source,
        skin_target,
        {
            "thumbnail.png": "thumbnail.png",
            "data": "data",
            "texture": "texture",
        },
    )

    # Background resources.
    copy_required(
        background_source,
        background_target,
        {
            "thumbnail.png": "thumbnail.png",
            "data": "data",
            "image.png": "image.png",
            "configuration.json.gz": "configuration",
        },
    )

    # Effect resources.
    copy_required(
        effect_source,
        effect_target,
        {
            "thumbnail.png": "thumbnail.png",
            "data": "data",
            "audio": "audio",
        },
    )

    # Particle resources.
    copy_required(
        particle_source,
        particle_target,
        {
            "thumbnail.png": "thumbnail.png",
            "data": "data",
            "texture": "texture",
        },
    )

    upstream_commit = get_git_commit(UPSTREAM)

    engine_item = make_item(engine_metadata)
    engine_item.update(
        {
            "skin": skin_name,
            "background": background_name,
            "effect": effect_name,
            "particle": particle_name,
            "meta": {
                "upstream": "Sbotga/sbuga-sonolus-server",
                "commit": upstream_commit,
                "sourceEngine": SOURCE_ENGINE,
                "locale": args.locale,
            },
        }
    )

    write_json(
        engine_target / "item.json",
        engine_item,
    )

    write_json(
        skin_target / "item.json",
        make_item(load_json(skin_source / "skin.json")),
    )

    write_json(
        background_target / "item.json",
        make_item(load_json(background_source / "background.json")),
    )

    write_json(
        effect_target / "item.json",
        make_item(load_json(effect_source / "effect.json")),
    )

    write_json(
        particle_target / "item.json",
        make_item(load_json(particle_source / "particle.json")),
    )

    print()
    print(f"Imported engine: {SOURCE_ENGINE} -> {args.engine_name}")
    print(f"Upstream commit: {upstream_commit}")
    print(f"Default skin:    {skin_name}")
    print(f"Background:      {background_name}")
    print(f"Effect:          {effect_name}")
    print(f"Particle:        {particle_name}")


def make_item(metadata: dict[str, Any]) -> dict[str, Any]:
    """Convert Sbuga metadata into a Sonolus Pack item.json."""

    item: dict[str, Any] = {
        "version": metadata["version"],
        "title": localize(metadata.get("title", "")),
        "subtitle": localize(metadata.get("subtitle", "")),
        "author": localize(metadata.get("author", "")),
        "tags": normalize_tags(metadata.get("tags", [])),
    }

    if "description" in metadata:
        item["description"] = localize(metadata["description"])

    return item


def install_engine_configuration(
    source: Path,
    target: Path,
    overrides: Any,
) -> None:
    """
    Copy EngineConfiguration and apply Sbuga's config_overrides.

    EngineConfiguration is normally gzip-compressed JSON.
    """

    require_file(source)

    if not overrides:
        shutil.copy2(source, target)
        return

    raw = source.read_bytes()

    try:
        decoded = gzip.decompress(raw)
    except (gzip.BadGzipFile, EOFError):
        decoded = raw

    configuration = json.loads(decoded.decode("utf-8"))
    options = configuration.get("options", [])

    found: set[str] = set()
    for option in options:
        name = option.get("name")
        changes = overrides.get(name)
        if changes:
            option.update(changes)
            found.add(name)

    unknown = sorted(set(overrides) - found)
    if unknown:
        raise ValueError(
            "Configuration override options were not found: "
            + ", ".join(unknown)
        )

    encoded = json.dumps(
        configuration,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    # mtime=0 makes repeated imports produce identical compressed bytes.
    target.write_bytes(gzip.compress(encoded, mtime=0))


def copy_required(
    source_directory: Path,
    target_directory: Path,
    mapping: dict[str, str],
) -> None:
    for source_name, target_name in mapping.items():
        source = source_directory / source_name
        target = target_directory / target_name

        require_file(source)
        shutil.copy2(source, target)


def copy_optional(source: Path, target: Path) -> None:
    if source.is_file():
        shutil.copy2(source, target)


def require_directories(*paths: Path) -> None:
    missing = [str(path) for path in paths if not path.is_dir()]

    if missing:
        raise FileNotFoundError(
            "Missing required directories:\n  "
            + "\n  ".join(missing)
        )


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required file: {path}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def get_git_commit(repository: Path) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "rev-parse",
            "HEAD",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return "unknown"

    return result.stdout.strip()


if __name__ == "__main__":
    main()
