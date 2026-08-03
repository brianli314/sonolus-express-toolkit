#!/usr/bin/env python3
"""
Import an engine and its default UI assets from a Sonolus .scp package
into an @sonolus/pack source catalogue.

Default input:
    imports/reference.scp

Default output:
    source/
        engines/
        skins/
        backgrounds/
        effects/
        particles/
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterator, Optional

from import_utils import localize, normalize_tags, replace_directory, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REFERENCE_SCP = PROJECT_ROOT / "imports" / "reference.scp"
SOURCE_ROOT = PROJECT_ROOT / "source"
LOCALE = "en"


# SCP resources are already processed Sonolus repository resources.
# They are therefore written without extensions so @sonolus/pack
# passes them through rather than processing them again.
RESOURCE_FILES: dict[str, dict[str, str]] = {
    "engine": {
        "thumbnail": "thumbnail",
        "configuration": "configuration",
        "playData": "playData",
        "watchData": "watchData",
        "previewData": "previewData",
        "tutorialData": "tutorialData",
    },
    "skin": {"thumbnail": "thumbnail", "data": "data", "texture": "texture"},
    "background": {
        "thumbnail": "thumbnail",
        "data": "data",
        "image": "image",
        "configuration": "configuration",
    },
    "effect": {"thumbnail": "thumbnail", "data": "data", "audio": "audio"},
    "particle": {"thumbnail": "thumbnail", "data": "data", "texture": "texture"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import an engine from an SCP package."
    )
    parser.add_argument(
        "--scp",
        type=Path,
        default=REFERENCE_SCP,
        help="SCP package containing a level that references the engine.",
    )
    parser.add_argument(
        "--locale",
        default=LOCALE,
        help="Locale used for plain-text metadata.",
    )
    parser.add_argument(
        "--engine-name",
        help="Override the engine item name stored in the package.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="sonolus-scp-import-") as temp_dir:
        package_root = extract_scp(args.scp.resolve(), Path(temp_dir))
        import_engine_bundle(
            package_root=package_root,
            source_root=SOURCE_ROOT,
            level=next(iter_level_items(package_root)),
            locale=args.locale,
            engine_name_override=args.engine_name,
        )


def import_engine_bundle(
    package_root: Path,
    source_root: Path,
    level: dict[str, Any],
    locale: str,
    engine_name_override: Optional[str],
) -> None:
    engine = level["engine"]
    skin = engine["skin"]
    background = engine["background"]
    effect = engine["effect"]
    particle = engine["particle"]

    engine_name = safe_item_name(
        engine_name_override or get_item_name(engine, "engine"),
        "engine",
    )

    skin_name = get_item_name(skin, "skin")
    background_name = get_item_name(background, "background")
    effect_name = get_item_name(effect, "effect")
    particle_name = get_item_name(particle, "particle")

    imported = [
        import_item(
            package_root=package_root,
            source_root=source_root,
            category="skins",
            resource_type="skin",
            name=skin_name,
            item=skin,
            locale=locale,
        ),
        import_item(
            package_root=package_root,
            source_root=source_root,
            category="backgrounds",
            resource_type="background",
            name=background_name,
            item=background,
            locale=locale,
        ),
        import_item(
            package_root=package_root,
            source_root=source_root,
            category="effects",
            resource_type="effect",
            name=effect_name,
            item=effect,
            locale=locale,
        ),
        import_item(
            package_root=package_root,
            source_root=source_root,
            category="particles",
            resource_type="particle",
            name=particle_name,
            item=particle,
            locale=locale,
        ),
    ]

    engine_metadata = make_pack_item(engine, locale)
    engine_metadata.update(
        {
            "skin": skin_name,
            "background": background_name,
            "effect": effect_name,
            "particle": particle_name,
        }
    )

    engine_target = import_item(
        package_root=package_root,
        source_root=source_root,
        category="engines",
        resource_type="engine",
        name=engine_name,
        item=engine,
        locale=locale,
        item_json=engine_metadata,
    )

    print()
    print("Imported Sonolus engine bundle:")
    print(f"  Engine:     {engine_name}")
    print(f"  Skin:       {skin_name}")
    print(f"  Background: {background_name}")
    print(f"  Effect:     {effect_name}")
    print(f"  Particle:   {particle_name}")
    print()
    print(f"Engine output: {engine_target}")

    for path in imported:
        print(f"Asset output:  {path}")


def import_item(
    *,
    package_root: Path,
    source_root: Path,
    category: str,
    resource_type: str,
    name: str,
    item: dict[str, Any],
    locale: str,
    item_json: Optional[dict[str, Any]] = None,
) -> Path:
    target = replace_directory(source_root / category / name)

    for key, output_name in RESOURCE_FILES[resource_type].items():
        shutil.copy2(resource_path(package_root, item[key]), target / output_name)

    if resource_type == "engine" and item.get("rom"):
        shutil.copy2(resource_path(package_root, item["rom"]), target / "rom")

    metadata = item_json if item_json is not None else make_pack_item(item, locale)
    write_json(target / "item.json", metadata)

    return target


def make_pack_item(item: dict[str, Any], locale: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "version": item["version"],
        "title": localize(item.get("title", ""), locale),
        "subtitle": localize(item.get("subtitle", ""), locale),
        "author": localize(item.get("author", ""), locale),
        "tags": normalize_tags(item.get("tags", []), locale),
    }

    description = item.get("description")
    if description is not None:
        metadata["description"] = localize(description, locale)

    existing_meta = item.get("meta")
    if existing_meta is not None:
        metadata["meta"] = existing_meta

    return metadata


def extract_scp(scp_path: Path, extract_dir: Path) -> Path:
    target = extract_dir / scp_path.stem
    target.mkdir(parents=True)

    with zipfile.ZipFile(scp_path) as archive:
        safe_extract(archive, target)
    return target / "sonolus"


def safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    target = target.resolve()

    for member in archive.infolist():
        member_path = (target / member.filename).resolve()

        if not member_path.is_relative_to(target):
            raise ValueError(f"Unsafe ZIP path: {member.filename}")
        archive.extract(member, target)


def iter_level_items(package_root: Path) -> Iterator[dict[str, Any]]:
    levels_dir = package_root / "levels"

    if levels_dir.is_dir():
        for path in sorted(levels_dir.iterdir()):
            if not path.is_file() or path.name in {"info", "list"}:
                continue

            yield item_from_json(load_json(path))

        list_path = levels_dir / "list"
        if list_path.is_file():
            yield from load_json(list_path).get("items", [])

    playlists_dir = package_root / "playlists"

    if playlists_dir.is_dir():
        for path in sorted(playlists_dir.iterdir()):
            if not path.is_file() or path.name in {"info", "list"}:
                continue

            yield from item_from_json(load_json(path)).get("levels", [])


def item_from_json(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("item", data)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resource_path(package_root: Path, ref: dict[str, Any]) -> Path:
    hash_name = ref.get("hash") or ref["url"].rsplit("/", 1)[-1]
    if Path(hash_name).name != hash_name or hash_name in {".", ".."}:
        raise ValueError(f"Unsafe repository resource name: {hash_name}")
    return package_root / "repository" / hash_name


def get_item_name(item: dict[str, Any], label: str) -> str:
    return safe_item_name(item["name"], label)


def safe_item_name(name: str, label: str) -> str:
    name = name.strip()

    if not name:
        raise ValueError(f"The imported {label} name is empty")

    if "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError(f"Unsafe {label} name: {name!r}")

    return name


if __name__ == "__main__":
    main()
