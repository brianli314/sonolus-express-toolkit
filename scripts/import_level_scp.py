"""Import playable levels and playlists from Sonolus SCP packages."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, cast

from import_utils import (
    localize,
    normalize_tags,
    replace_directory,
    validate_item_name,
    write_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPORT_DIR = PROJECT_ROOT / "imports"
SOURCE_DIR = PROJECT_ROOT / "source"
EXTRACTIONS_DIR = PROJECT_ROOT / "extractions"
ENGINE_NAME = "next-rush-sbuga"
LOCALE = "en"
BACKGROUND_MASK = json.loads(
    Path(__file__).with_name("import_settings.json").read_text(encoding="utf-8")
)["backgroundMask"]


@dataclass
class ImportStats:
    packages: int = 0
    levels_seen: int = 0
    levels_exported: int = 0
    levels_updated: int = 0
    levels_skipped: int = 0
    missing_cover: int = 0
    missing_bgm: int = 0
    missing_data: int = 0
    missing_preview: int = 0
    playlists_exported: int = 0
    backgrounds_generated: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import playable Sonolus SCP packages."
    )
    parser.add_argument(
        "--import-dir",
        type=Path,
        default=IMPORT_DIR,
        help="Directory containing playable SCP packages.",
    )
    parser.add_argument(
        "--engine",
        default=ENGINE_NAME,
        type=validate_item_name,
        help="Engine assigned to imported levels.",
    )
    parser.add_argument(
        "--locale",
        default=LOCALE,
        help="Locale used for plain-text metadata.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh existing levels with the same original name.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import_dir = args.import_dir.resolve()
    levels_dir = SOURCE_DIR / "levels"
    playlists_dir = SOURCE_DIR / "playlists"
    backgrounds_dir = SOURCE_DIR / "backgrounds"
    stats = ImportStats()

    engine_item = SOURCE_DIR / "engines" / args.engine / "item.json"
    if not engine_item.is_file():
        raise SystemExit(
            f"Engine item not found: {engine_item}\nImport the engine first."
        )

    all_scp_paths = sorted(import_dir.glob("*.scp"))
    reference_scp = import_dir / "reference.scp"
    scp_paths = [path for path in all_scp_paths if path.resolve() != reference_scp]

    if not scp_paths:
        print(f"No playable .scp files found in {import_dir}; nothing to import.")
        return

    for skipped_path in all_scp_paths:
        if skipped_path not in scp_paths:
            print(f"Skipping UI-only reference package: {skipped_path}")

    levels_dir.mkdir(parents=True, exist_ok=True)
    playlists_dir.mkdir(parents=True, exist_ok=True)

    for scp_path in scp_paths:
        stats.packages += 1
        extraction_path = EXTRACTIONS_DIR / scp_path.stem
        try:
            package_root = extract_scp(scp_path, EXTRACTIONS_DIR)
            package_stats = export_package(
                package_root=package_root,
                levels_dir=levels_dir,
                playlists_dir=playlists_dir,
                backgrounds_dir=backgrounds_dir,
                engine_name=args.engine,
                locale=args.locale,
                force=args.force,
            )
        finally:
            shutil.rmtree(extraction_path, ignore_errors=True)
        merge_stats(stats, package_stats)

    print()
    print("Import complete")
    print(f"  packages:           {stats.packages}")
    print(f"  levels seen:        {stats.levels_seen}")
    print(f"  levels exported:    {stats.levels_exported}")
    print(f"  levels updated:     {stats.levels_updated}")
    print(f"  levels skipped:     {stats.levels_skipped}")
    print(f"  missing cover:      {stats.missing_cover}")
    print(f"  missing bgm:        {stats.missing_bgm}")
    print(f"  missing data:       {stats.missing_data}")
    print(f"  missing preview:    {stats.missing_preview}")
    print(f"  playlists exported: {stats.playlists_exported}")
    print(f"  backgrounds made:   {stats.backgrounds_generated}")
    print(f"  Sonolus source:     {SOURCE_DIR}")


def extract_scp(scp_path: Path, extract_dir: Path) -> Path:
    target = extract_dir / scp_path.stem
    replace_directory(target)

    try:
        with zipfile.ZipFile(scp_path) as archive:
            safe_extract(archive, target)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid SCP/ZIP package: {scp_path}") from exc

    package_root = target / "sonolus"
    if not package_root.is_dir():
        raise FileNotFoundError(f"{scp_path} did not contain a sonolus/ directory")

    repository_dir = package_root / "repository"
    if not repository_dir.is_dir():
        raise FileNotFoundError(f"{scp_path} did not contain sonolus/repository/")

    print(f"Extracted {scp_path} -> {target}")
    return package_root


def safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    target = target.resolve()
    for member in archive.infolist():
        member_path = (target / member.filename).resolve()
        try:
            member_path.relative_to(target)
        except ValueError as exc:
            raise ValueError(f"Unsafe ZIP path: {member.filename}") from exc
        archive.extract(member, target)


def export_package(
    *,
    package_root: Path,
    levels_dir: Path,
    playlists_dir: Path,
    backgrounds_dir: Path,
    engine_name: str,
    locale: str,
    force: bool = False,
) -> ImportStats:
    stats = ImportStats()
    collection = collect_level_collection(package_root)
    items: dict[str, dict[str, Any]] = collection["items"]
    playlists: list[dict[str, Any]] = collection["playlists"]

    if not items:
        print(f"Skipping {package_root}: no levels found")
        return stats

    source_package = package_root.parent.name
    item_to_level_name: dict[str, str] = {}
    existing_levels = index_existing_levels(levels_dir)
    generated_backgrounds: dict[str, str] = {}

    for item_name, listed_item in items.items():
        stats.levels_seen += 1
        item = load_level_detail(package_root, item_name, listed_item)

        resources = {
            "cover": resolve_resource(package_root, item.get("cover")),
            "bgm": resolve_resource(package_root, item.get("bgm")),
            "preview": resolve_resource(package_root, item.get("preview")),
            "data": resolve_resource(package_root, item.get("data")),
        }

        missing = [
            resource_name
            for resource_name in ("cover", "bgm", "data")
            if resources[resource_name] is None
        ]
        if missing:
            if "cover" in missing:
                stats.missing_cover += 1
            if "bgm" in missing:
                stats.missing_bgm += 1
            if "data" in missing:
                stats.missing_data += 1
            stats.levels_skipped += 1
            print(f"Skip {item_name}: missing {', '.join(missing)}")
            continue

        if resources["preview"] is None:
            stats.missing_preview += 1

        data_path = cast(Path, resources["data"])
        bgm_path = cast(Path, resources["bgm"])
        cover_path = cast(Path, resources["cover"])
        chart_hash = hash_chart_file(data_path)
        bgm_hash = hash_file(bgm_path)
        background_name, was_generated = ensure_generated_background(
            backgrounds_dir=backgrounds_dir,
            template_dir=backgrounds_dir / "pjsk_template",
            cover_path=cover_path,
            item=item,
            locale=locale,
            cache=generated_backgrounds,
        )
        if was_generated:
            stats.backgrounds_generated += 1

        duplicate = find_duplicate_level(
            existing_levels,
            original_name=item_name,
            chart_hash=chart_hash,
            bgm_hash=bgm_hash,
        )

        is_update = False
        if duplicate is not None:
            duplicate_dir, duplicate_metadata = duplicate
            same_original_name = duplicate_metadata.get("originalName") == item_name
            same_content = (
                duplicate_metadata.get("chartHash") == chart_hash
                and duplicate_metadata.get("bgmHash") == bgm_hash
            )

            if same_original_name and (force or not same_content):
                output_dir = duplicate_dir
                is_update = True
                reason = (
                    "forced refresh" if force and same_content else "changed content"
                )
                print(f"Updating {item_name} in {output_dir} ({reason})")
            else:
                item_to_level_name[item_name] = duplicate_dir.name
                set_level_background(duplicate_dir / "item.json", background_name)
                stats.levels_skipped += 1
                print(f"Skip {item_name}: duplicate of {duplicate_dir.name}")
                continue
        else:
            level_name = unique_level_name(
                levels_dir,
                preferred=sanitize_identifier(item_name, fallback="level"),
                original_name=item_name,
            )
            output_dir = levels_dir / level_name

        replace_directory(output_dir)

        # SCP repository files are already processed Sonolus resources. Writing
        # them extensionless tells @sonolus/pack to copy them without processing.
        shutil.copy2(cover_path, output_dir / "cover")
        shutil.copy2(bgm_path, output_dir / "bgm")
        shutil.copy2(data_path, output_dir / "data")
        if resources["preview"] is not None:
            shutil.copy2(resources["preview"], output_dir / "preview")

        write_level_item(
            output_dir / "item.json",
            item=item,
            engine_name=engine_name,
            locale=locale,
            source_package=source_package,
            original_name=item_name,
            chart_hash=chart_hash,
            bgm_hash=bgm_hash,
            background_name=background_name,
        )

        item_to_level_name[item_name] = output_dir.name
        existing_levels = index_existing_levels(levels_dir)
        if is_update:
            stats.levels_updated += 1
        else:
            stats.levels_exported += 1
        print(f"Exported {item_name} -> {output_dir}")

    stats.playlists_exported += write_playlists(
        package_root=package_root,
        playlists_dir=playlists_dir,
        playlists=playlists,
        item_to_level_name=item_to_level_name,
        source_package=source_package,
        locale=locale,
    )
    return stats


def collect_level_collection(package_root: Path) -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    playlists: list[dict[str, Any]] = []

    levels_dir = package_root / "levels"
    if levels_dir.is_dir():
        list_path = levels_dir / "list"
        if list_path.is_file():
            add_level_items(items, load_json(list_path).get("items", []))

        for path in sorted(levels_dir.iterdir()):
            if not path.is_file() or path.name in {"info", "list"}:
                continue
            item = unwrap_item(load_json(path))
            items[item["name"]] = item

    playlists_dir = package_root / "playlists"
    if playlists_dir.is_dir():
        for path in sorted(playlists_dir.iterdir()):
            if not path.is_file() or path.name in {"info", "list"}:
                continue
            playlist = extract_playlist(load_json(path))
            playlists.append(playlist)
            add_level_items(items, playlist["levels"])

    return {"items": items, "playlists": playlists}


def load_level_detail(
    package_root: Path,
    item_name: str,
    listed_item: dict[str, Any],
) -> dict[str, Any]:
    detail_path = safe_direct_child(package_root / "levels", item_name)
    if detail_path is not None and detail_path.is_file():
        return unwrap_item(load_json(detail_path))
    return listed_item


def safe_direct_child(parent: Path, name: str) -> Optional[Path]:
    if not name or Path(name).name != name or name in {".", ".."}:
        return None
    return parent / name


def unwrap_item(value: dict[str, Any]) -> dict[str, Any]:
    return value.get("item", value)


def extract_playlist(value: dict[str, Any]) -> dict[str, Any]:
    return unwrap_item(value)


def add_level_items(
    items: dict[str, dict[str, Any]], candidates: Iterable[Any]
) -> None:
    for candidate in candidates:
        items[candidate["name"]] = candidate


def write_level_item(
    path: Path,
    *,
    item: dict[str, Any],
    engine_name: str,
    locale: str,
    source_package: str,
    original_name: str,
    chart_hash: str,
    bgm_hash: str,
    background_name: str,
) -> None:
    output: dict[str, Any] = {
        "version": item.get("version", 1),
        "rating": item.get("rating", 0),
        "engine": engine_name,
        "useSkin": {"useDefault": True},
        "useBackground": {"useDefault": False, "item": background_name},
        "useEffect": {"useDefault": True},
        "useParticle": {"useDefault": True},
        "title": localize(item.get("title") or original_name, locale),
        "artists": localize(item.get("artists") or "", locale),
        "author": localize(item.get("author") or "", locale),
        "tags": normalize_tags(item.get("tags", []), locale),
        "meta": {
            "importer": "scp",
            "sourcePackage": source_package,
            "originalName": original_name,
            "source": item.get("source"),
            "chartHash": chart_hash,
            "bgmHash": bgm_hash,
            "sourceMeta": item.get("meta"),
        },
    }

    if item.get("description") is not None:
        output["description"] = localize(item["description"], locale)

    write_json(path, output)


def ensure_generated_background(
    *,
    backgrounds_dir: Path,
    template_dir: Path,
    cover_path: Path,
    item: dict[str, Any],
    locale: str,
    cache: dict[str, str],
) -> tuple[str, bool]:
    cover_hash = hash_file(cover_path)
    if cover_hash in cache:
        return cache[cover_hash], False

    if not (template_dir / "data").is_file():
        raise FileNotFoundError("Background template is missing data")

    background_name = f"pjsk-generated-{cover_hash[:16]}-v3"
    output_dir = backgrounds_dir / background_name
    expected_meta = {
        "generator": "pjsk_background_gen_PIL",
        "version": "v3",
        "coverHash": cover_hash,
        "renderRevision": (
            f"center-crop-2048x1168-mask-{BACKGROUND_MASK.removeprefix('#')}"
        ),
    }

    if generated_background_matches(output_dir, expected_meta):
        cache[cover_hash] = background_name
        return background_name, False

    try:
        import pjsk_background_gen_PIL
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            "PJSK background generation requires Pillow and "
            "pjsk_background_gen_PIL. Install the generator from "
            "https://github.com/UntitledCharts/"
            "pjsekai-background-gen-pillow-upd before importing."
        ) from exc

    replace_directory(output_dir)

    with Image.open(cover_path) as jacket:
        source_image = jacket.convert("RGBA")
        rendered = pjsk_background_gen_PIL.render_v3(source_image)
        rendered = rendered.crop((0, 440, 2048, 1608))
        rendered.save(output_dir / "image.png", format="PNG")

    # The jacket is the background's browsing thumbnail. It is already a
    # processed Sonolus image, so keep it extensionless.
    shutil.copy2(cover_path, output_dir / "thumbnail")
    shutil.copy2(template_dir / "data", output_dir / "data")
    configuration = json.dumps(
        {"scope": "Sekai", "blur": 0, "mask": BACKGROUND_MASK},
        separators=(",", ":"),
    ).encode()
    (output_dir / "configuration").write_bytes(
        gzip.compress(configuration, mtime=0)
    )

    write_json(
        output_dir / "item.json",
        {
            "version": 2,
            "title": localize(item.get("title") or "Generated Background", locale),
            "subtitle": localize("PJSK V3 Background", locale),
            "author": localize(item.get("author") or "", locale),
            "tags": [],
            "meta": expected_meta,
        },
    )

    cache[cover_hash] = background_name
    print(f"Generated background {background_name}")
    return background_name, True


def generated_background_matches(path: Path, expected_meta: dict[str, str]) -> bool:
    try:
        item = load_json(path / "item.json")
    except (OSError, json.JSONDecodeError):
        return False

    return (
        isinstance(item, dict)
        and item.get("meta") == expected_meta
        and (path / "thumbnail").is_file()
        and (path / "image.png").is_file()
        and (path / "data").is_file()
        and (path / "configuration").is_file()
    )


def set_level_background(item_path: Path, background_name: str) -> None:
    try:
        item = load_json(item_path)
    except (OSError, json.JSONDecodeError):
        return

    use_background = {"useDefault": False, "item": background_name}
    if item.get("useBackground") == use_background:
        return

    item["useBackground"] = use_background
    write_json(item_path, item)
    print(f"Updated background reference in {item_path}")


def write_playlists(
    *,
    package_root: Path,
    playlists_dir: Path,
    playlists: list[dict[str, Any]],
    item_to_level_name: dict[str, str],
    source_package: str,
    locale: str,
) -> int:
    exported = 0

    for playlist in playlists:
        mapped_levels: list[str] = []
        levels = playlist.get("levels", [])

        for level in levels:
            original_name = level["name"]
            if original_name in item_to_level_name:
                mapped_levels.append(item_to_level_name[original_name])

        mapped_levels = deduplicate_preserving_order(mapped_levels)
        if not mapped_levels:
            continue

        original_name = str(
            playlist.get("name")
            or playlist.get("title")
            or f"playlist-{source_package}"
        )
        playlist_name = unique_playlist_name(
            playlists_dir,
            preferred=sanitize_identifier(original_name, fallback="playlist"),
            original_name=original_name,
            source_package=source_package,
        )
        output_dir = playlists_dir / playlist_name
        replace_directory(output_dir)

        item_json: dict[str, Any] = {
            "version": playlist.get("version", 1),
            "title": localize(playlist.get("title") or original_name, locale),
            "time": playlist.get("time", 0),
            "author": localize(playlist.get("author") or "", locale),
            "tags": normalize_tags(playlist.get("tags", []), locale),
            "levels": mapped_levels,
            "meta": {
                "importer": "scp",
                "sourcePackage": source_package,
                "originalName": original_name,
                "source": playlist.get("source"),
                "sourceMeta": playlist.get("meta"),
            },
        }
        if playlist.get("description") is not None:
            item_json["description"] = localize(playlist["description"], locale)

        write_json(output_dir / "item.json", item_json)

        thumbnail = resolve_resource(package_root, playlist.get("thumbnail"))
        if thumbnail is not None:
            shutil.copy2(thumbnail, output_dir / "thumbnail")

        exported += 1
        print(f"Exported playlist {original_name} -> {output_dir}")

    return exported


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_resource(package_root: Path, ref: Any) -> Optional[Path]:
    if not isinstance(ref, dict):
        return None

    hash_name = ref.get("hash")
    if not hash_name:
        url = ref.get("url")
        if isinstance(url, str) and "/sonolus/repository/" in url:
            hash_name = url.rsplit("/", 1)[-1]

    if not hash_name:
        return None
    if Path(hash_name).name != hash_name or hash_name in {".", ".."}:
        raise ValueError(f"Unsafe repository resource name: {hash_name}")

    path = package_root / "repository" / hash_name
    return path if path.is_file() else None


def sanitize_identifier(value: str, *, fallback: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return value[:120] or fallback


def unique_level_name(
    levels_dir: Path,
    *,
    preferred: str,
    original_name: str,
) -> str:
    primary = levels_dir / preferred
    if not primary.exists():
        return preferred

    metadata = read_import_metadata(primary / "item.json")
    if metadata.get("originalName") == original_name:
        return preferred

    digest = hashlib.sha256(original_name.encode("utf-8")).hexdigest()[:10]
    candidate = f"{preferred[:109]}-{digest}"
    suffix = 2
    while (levels_dir / candidate).exists():
        metadata = read_import_metadata(levels_dir / candidate / "item.json")
        if metadata.get("originalName") == original_name:
            return candidate
        candidate = f"{preferred[:104]}-{digest}-{suffix}"
        suffix += 1
    return candidate


def unique_playlist_name(
    playlists_dir: Path,
    *,
    preferred: str,
    original_name: str,
    source_package: str,
) -> str:
    primary = playlists_dir / preferred
    if not primary.exists() or playlist_matches(primary, original_name, source_package):
        return preferred

    digest_input = f"{source_package}\0{original_name}".encode("utf-8")
    digest = hashlib.sha256(digest_input).hexdigest()[:10]
    return f"{preferred[:109]}-{digest}"


def playlist_matches(path: Path, original_name: str, source_package: str) -> bool:
    meta = read_import_metadata(path / "item.json")
    return (
        meta.get("originalName") == original_name
        and meta.get("sourcePackage") == source_package
    )


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def hash_chart_file(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    return hashlib.sha256(raw).hexdigest()


def index_existing_levels(levels_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    indexed: list[tuple[Path, dict[str, Any]]] = []
    if not levels_dir.is_dir():
        return indexed

    for folder in levels_dir.iterdir():
        if not folder.is_dir():
            continue

        metadata = read_import_metadata(folder / "item.json")
        if not metadata:
            continue

        if not metadata.get("chartHash"):
            data_path = folder / "data"
            if data_path.is_file():
                try:
                    metadata["chartHash"] = hash_chart_file(data_path)
                except (OSError, gzip.BadGzipFile):
                    pass

        if not metadata.get("bgmHash"):
            bgm_path = folder / "bgm"
            if bgm_path.is_file():
                try:
                    metadata["bgmHash"] = hash_file(bgm_path)
                except OSError:
                    pass

        indexed.append((folder, metadata))
    return indexed


def read_import_metadata(item_json_path: Path) -> dict[str, Any]:
    try:
        item = load_json(item_json_path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    if not isinstance(item, dict) or not isinstance(item.get("meta"), dict):
        return {}
    meta = item["meta"]
    return meta if meta.get("importer") == "scp" else {}


def find_duplicate_level(
    existing_levels: list[tuple[Path, dict[str, Any]]],
    *,
    original_name: str,
    chart_hash: str,
    bgm_hash: str,
) -> Optional[tuple[Path, dict[str, Any]]]:
    same_name = next(
        (
            entry
            for entry in existing_levels
            if entry[1].get("originalName") == original_name
        ),
        None,
    )
    if same_name is not None:
        return same_name

    return next(
        (
            entry
            for entry in existing_levels
            if entry[1].get("chartHash") == chart_hash
            and entry[1].get("bgmHash") == bgm_hash
        ),
        None,
    )


def deduplicate_preserving_order(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def merge_stats(total: ImportStats, part: ImportStats) -> None:
    total.levels_seen += part.levels_seen
    total.levels_exported += part.levels_exported
    total.levels_updated += part.levels_updated
    total.levels_skipped += part.levels_skipped
    total.missing_cover += part.missing_cover
    total.missing_bgm += part.missing_bgm
    total.missing_data += part.missing_data
    total.missing_preview += part.missing_preview
    total.playlists_exported += part.playlists_exported
    total.backgrounds_generated += part.backgrounds_generated


if __name__ == "__main__":
    main()
