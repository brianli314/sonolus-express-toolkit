"""Import one ChartDownloader level directory into the Sonolus pack source tree."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import urlsplit

from import_level_scp import (
    ensure_generated_background,
    hash_chart_file,
    hash_file,
    sanitize_identifier,
)
from import_utils import (
    localize,
    normalize_tags,
    replace_directory,
    validate_item_name,
    write_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "source"
ENGINE_NAME = "next-rush-sbuga"
LOCALE = "en"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import one ChartDownloader level.")
    parser.add_argument(
        "level_dir",
        type=Path,
        help="ChartDownloader directory containing level.json.",
    )
    parser.add_argument(
        "--engine",
        default=ENGINE_NAME,
        type=validate_item_name,
        help="Engine assigned to the imported level.",
    )
    parser.add_argument(
        "--locale",
        default=LOCALE,
        help="Locale used for plain-text metadata.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace a level with the same output name.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    level_dir = args.level_dir.resolve()

    item = load_item(level_dir / "level.json")
    original_name = str(item.get("name") or level_dir.name)
    level_name = sanitize_identifier(original_name, fallback="level")
    output_dir = SOURCE_DIR / "levels" / level_name

    if output_dir.exists() and not args.force:
        raise SystemExit(
            f"Level already exists: {output_dir}\nPass --force to replace it."
        )

    engine_item = SOURCE_DIR / "engines" / args.engine / "item.json"
    if not engine_item.is_file():
        raise SystemExit(
            f"Engine item not found: {engine_item}\nImport the engine first."
        )

    resources = {
        "data": require_file(level_dir / "NSLevelData.json.gz", "level data"),
        "cover": find_asset(level_dir, "jacket", required=True),
        "bgm": find_asset(level_dir, "music", required=True),
        "preview": find_asset(level_dir, "preview", required=False),
    }

    data_path = cast(Path, resources["data"])
    cover_path = cast(Path, resources["cover"])
    bgm_path = cast(Path, resources["bgm"])

    chart_hash = hash_chart_file(data_path)
    bgm_hash = hash_file(bgm_path)
    background_name, _ = ensure_generated_background(
        backgrounds_dir=SOURCE_DIR / "backgrounds",
        template_dir=SOURCE_DIR / "backgrounds" / "pjsk_template",
        cover_path=cover_path,
        item=item,
        locale=args.locale,
        cache={},
    )

    replace_directory(output_dir)
    shutil.copy2(data_path, output_dir / "data")
    shutil.copy2(cover_path, output_dir / "cover")
    shutil.copy2(bgm_path, output_dir / "bgm")
    if resources["preview"] is not None:
        shutil.copy2(resources["preview"], output_dir / "preview")

    output_item: dict[str, Any] = {
        "version": item.get("version", 1),
        "rating": item.get("rating", 0),
        "engine": args.engine,
        "useSkin": {"useDefault": True},
        "useBackground": {"useDefault": False, "item": background_name},
        "useEffect": {"useDefault": True},
        "useParticle": {"useDefault": True},
        "title": localize(item.get("title") or original_name, args.locale),
        "artists": localize(item.get("artists") or "", args.locale),
        "author": localize(item.get("author") or "", args.locale),
        "tags": normalize_tags(item.get("tags", []), args.locale),
        "meta": {
            "importer": "chart-downloader",
            "originalName": original_name,
            "source": infer_source(item, original_name),
            "chartHash": chart_hash,
            "bgmHash": bgm_hash,
            "sourceMeta": item.get("meta"),
        },
    }
    if item.get("description") is not None:
        output_item["description"] = localize(item["description"], args.locale)

    write_json(output_dir / "item.json", output_item)
    print(f"Imported {original_name} -> {output_dir}")
    if resources["preview"] is None:
        print("Preview was not available; imported without one.")


def load_item(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    item = value.get("item", value) if isinstance(value, dict) else None
    if not isinstance(item, dict):
        raise SystemExit(f"Expected a level object in {path}")
    return item


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise SystemExit(f"Missing {label}: {path}")
    return path


def find_asset(directory: Path, stem: str, *, required: bool) -> Optional[Path]:
    match = next(
        (
            path
            for path in sorted(directory.iterdir())
            if path.is_file()
            and (path.name == stem or path.name.startswith(f"{stem}."))
        ),
        None,
    )
    if match is not None:
        return match
    if required:
        raise SystemExit(f"Missing {stem} file in {directory}")
    return None


def infer_source(item: dict[str, Any], original_name: str) -> Optional[str]:
    if original_name.startswith("coconut-next-sekai-"):
        return "https://coconut.sonolus.com/next-sekai"

    for key in ("data", "bgm", "preview", "cover"):
        resource = item.get(key)
        url = resource.get("url") if isinstance(resource, dict) else None
        if not isinstance(url, str):
            continue
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        prefix = parsed.path.partition("/sonolus/")[0]
        return f"{parsed.scheme}://{parsed.netloc}{prefix}"
    return None


if __name__ == "__main__":
    main()
