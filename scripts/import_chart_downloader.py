"""Import a self-contained chart bundle into the Sonolus source tree."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from sonolus_converters import sus, usc
from sonolus_converters.LevelData import next_sekai

from import_level_scp import (
    ensure_generated_background,
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
DIFFICULTIES = ("easy", "normal", "hard", "expert", "master", "append")
MASTER_DATABASE_REPOSITORIES = {
    "jp": "sekai-master-db-diff",
    "en": "sekai-master-db-en-diff",
    "kr": "sekai-master-db-kr-diff",
    "cn": "sekai-master-db-cn-diff",
    "tw": "sekai-master-db-tc-diff",
}
SBUGA_MUSIC_API = "https://api.sbuga.com/api/pjsk_data/musics"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import one directory containing metadata, media, and charts."
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing level.json and chart/media files.",
    )
    parser.add_argument(
        "--engine",
        default=ENGINE_NAME,
        type=validate_item_name,
        help="Engine assigned to the imported levels.",
    )
    parser.add_argument(
        "--locale",
        default=LOCALE,
        help="Locale used for plain-text metadata.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace levels with the same output names.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory = args.directory.resolve()
    item = load_item(directory / "level.json")
    charts = find_charts(directory)

    engine_item = SOURCE_DIR / "engines" / args.engine / "item.json"
    if not engine_item.is_file():
        raise SystemExit(
            f"Engine item not found: {engine_item}\nImport the engine first."
        )

    base_name, pjsk = identify_bundle(directory, item)
    cover_path = find_asset(directory, "jacket")
    preview_path = find_asset(directory, "preview", required=False)
    output_names = make_output_names(base_name, charts)
    playlist_dir = (
        SOURCE_DIR / "playlists" / base_name if len(charts) > 1 else None
    )

    existing = [
        SOURCE_DIR / "levels" / name
        for name in output_names.values()
        if (SOURCE_DIR / "levels" / name).exists()
    ]
    if playlist_dir and playlist_dir.exists():
        existing.append(playlist_dir)
    if existing and not args.force:
        paths = "\n".join(f"  {path}" for path in existing)
        raise SystemExit(
            f"Level(s) already exist:\n{paths}\nPass --force to replace them."
        )

    bgm, bgm_source = load_bgm(directory, item, pjsk)
    ratings = get_ratings(item, charts, pjsk)
    background_name, _ = ensure_generated_background(
        backgrounds_dir=SOURCE_DIR / "backgrounds",
        template_dir=SOURCE_DIR / "backgrounds" / "pjsk_template",
        cover_path=cover_path,
        item={
            **item,
            "author": item.get("author")
            or ("Project Sekai: Colorful Stage!" if pjsk else ""),
        },
        locale=args.locale,
        cache={},
    )
    bgm_hash = hashlib.sha256(bgm).hexdigest()

    for chart in charts:
        data = load_chart(chart)
        label = chart_label(chart)
        output_dir = replace_directory(SOURCE_DIR / "levels" / output_names[chart])
        (output_dir / "data").write_bytes(data)
        shutil.copy2(cover_path, output_dir / "cover")
        (output_dir / "bgm").write_bytes(bgm)
        if preview_path:
            shutil.copy2(preview_path, output_dir / "preview")

        write_json(
            output_dir / "item.json",
            build_level_item(
                item,
                name=output_names[chart],
                label=label,
                chart_format=chart_format(chart),
                rating=ratings.get(label, int(item.get("rating", 0))),
                engine=args.engine,
                locale=args.locale,
                background_name=background_name,
                chart_hash=hash_chart(data),
                bgm_hash=bgm_hash,
                bgm_source=bgm_source,
                pjsk=pjsk,
            ),
        )
        print(f"Imported {chart.name} -> {output_dir}")

    if playlist_dir:
        write_playlist(
            playlist_dir,
            item=item,
            name=base_name,
            levels=list(output_names.values()),
            cover_path=cover_path,
            locale=args.locale,
            pjsk=pjsk,
        )
        print(f"Created playlist -> {playlist_dir}")

    print(f"Imported {len(charts)} level(s) from {directory}.")


def load_item(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value.get("item", value)


def find_charts(directory: Path) -> list[Path]:
    charts = sorted(directory.glob("*.sus")) + sorted(directory.glob("*.usc"))
    charts += sorted(directory.glob("*NSLevelData.json.gz"))
    if not charts:
        raise SystemExit(
            f"No .sus, .usc, or *NSLevelData.json.gz files found in {directory}"
        )
    return sorted(
        charts,
        key=lambda chart: (
            DIFFICULTIES.index(chart_label(chart))
            if chart_label(chart) in DIFFICULTIES
            else len(DIFFICULTIES),
            chart.name,
        ),
    )


def find_asset(directory: Path, stem: str, *, required: bool = True) -> Path | None:
    path = next(
        (
            candidate
            for candidate in sorted(directory.iterdir())
            if candidate.is_file()
            and (candidate.name == stem or candidate.name.startswith(f"{stem}."))
        ),
        None,
    )
    if required and path is None:
        raise SystemExit(f"Missing {stem} file in {directory}")
    return path


def load_bgm(
    directory: Path,
    item: dict[str, Any],
    pjsk: dict[str, Any] | None,
) -> tuple[bytes, str]:
    local_nosil = find_asset(directory, "music_nosil", required=False)
    if local_nosil:
        return local_nosil.read_bytes(), local_nosil.name

    music = find_asset(directory, "music")
    if not pjsk:
        return music.read_bytes(), music.name

    url = item.get("bgm_nosil_url") or find_pjsk_nosil_url(pjsk)
    print(f"Downloading synchronized PJSK BGM: {url}")
    request = Request(url, headers={"User-Agent": "sonolus-server-importer"})
    try:
        with urlopen(request, timeout=60) as response:
            return response.read(), url
    except OSError as exc:
        raise SystemExit(
            f"Could not download synchronized PJSK BGM from {url}"
        ) from exc


def find_pjsk_nosil_url(pjsk: dict[str, Any]) -> str:
    url = (
        f"{SBUGA_MUSIC_API}?region={pjsk['region']}"
        "&ignore_leak=true&image_type=png"
    )
    request = Request(url, headers={"User-Agent": "sonolus-server-importer"})
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
        musics = (
            payload.get("musics", payload) if isinstance(payload, dict) else payload
        )
        music = next(entry for entry in musics if entry["id"] == pjsk["musicId"])
        vocal = next(
            entry for entry in music["vocals"] if entry["id"] == pjsk["coverId"]
        )
        nosil_url = vocal["bgm_nosil_url"]
        if not isinstance(nosil_url, str) or not nosil_url:
            raise KeyError("bgm_nosil_url")
        return nosil_url
    except (OSError, KeyError, StopIteration, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit(
            "Could not find synchronized PJSK BGM metadata for "
            f"music {pjsk['musicId']}, vocal {pjsk['coverId']}"
        ) from exc


def identify_bundle(
    directory: Path, item: dict[str, Any]
) -> tuple[str, dict[str, Any] | None]:
    match = re.fullmatch(r"(\d+)[_-]cover[_-](\d+)", directory.name)
    region = directory.parent.name.lower()
    if (
        match
        and region in MASTER_DATABASE_REPOSITORIES
        and item.get("id") is not None
    ):
        pjsk = {
            "region": region,
            "musicId": int(item["id"]),
            "coverId": int(match.group(2)),
        }
        return (
            f"pjsk-{region}-{pjsk['musicId']}-{pjsk['coverId']}",
            pjsk,
        )

    original_name = str(item.get("name") or directory.name)
    return sanitize_identifier(original_name, fallback="level"), None


def chart_format(path: Path) -> str:
    if path.name.endswith("NSLevelData.json.gz"):
        return "leveldata"
    return path.suffix.removeprefix(".").lower()


def chart_label(path: Path) -> str:
    if path.name.endswith("NSLevelData.json.gz"):
        prefix = path.name.removesuffix("NSLevelData.json.gz").rstrip("._-")
        return sanitize_identifier(prefix.lower(), fallback="leveldata")
    return sanitize_identifier(path.stem.lower(), fallback="chart")


def make_output_names(base_name: str, charts: list[Path]) -> dict[Path, str]:
    labels = [chart_label(chart) for chart in charts]
    names = {}
    for chart in charts:
        label = chart_label(chart)
        if len(charts) == 1 and chart_format(chart) == "leveldata":
            name = base_name
        else:
            suffix = f"-{chart_format(chart)}" if labels.count(label) > 1 else ""
            name = f"{base_name}-{label}{suffix}"
        names[chart] = sanitize_identifier(name, fallback="level")
    return names


def load_chart(path: Path) -> bytes:
    if chart_format(path) == "leveldata":
        return path.read_bytes()

    loader = sus if chart_format(path) == "sus" else usc
    with path.open(encoding="utf-8-sig") as source:
        score = loader.load(source)
    output = io.BytesIO()
    next_sekai.export(output, score, as_compressed=True)
    return output.getvalue()


def hash_chart(data: bytes) -> str:
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    return hashlib.sha256(data).hexdigest()


def get_ratings(
    item: dict[str, Any], charts: list[Path], pjsk: dict[str, Any] | None
) -> dict[str, int]:
    embedded = item.get("ratings", {})
    ratings = {
        str(label).lower(): int(rating) for label, rating in embedded.items()
    }
    if not pjsk:
        return ratings

    difficulties = {
        chart_label(chart)
        for chart in charts
        if chart_label(chart) in DIFFICULTIES
    }
    missing = difficulties - ratings.keys()
    if missing:
        table = download_rating_table(pjsk["region"])
        ratings.update(
            {
                difficulty: table[pjsk["musicId"], difficulty]
                for difficulty in missing
            }
        )
    return ratings


def download_rating_table(region: str) -> dict[tuple[int, str], int]:
    repository = MASTER_DATABASE_REPOSITORIES[region]
    url = (
        "https://raw.githubusercontent.com/Sekai-World/"
        f"{repository}/refs/heads/main/musicDifficulties.json"
    )
    request = Request(url, headers={"User-Agent": "sonolus-server-importer"})
    try:
        with urlopen(request, timeout=30) as response:
            entries = json.load(response)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"Could not download PJSK difficulty ratings from {url}"
        ) from exc

    return {
        (int(entry["musicId"]), str(entry["musicDifficulty"]).lower()): int(
            entry["playLevel"]
        )
        for entry in entries
    }


def build_level_item(
    item: dict[str, Any],
    *,
    name: str,
    label: str,
    chart_format: str,
    rating: int,
    engine: str,
    locale: str,
    background_name: str,
    chart_hash: str,
    bgm_hash: str,
    bgm_source: str,
    pjsk: dict[str, Any] | None,
) -> dict[str, Any]:
    credits = [
        f"Lyrics: {item['lyricist']}" if item.get("lyricist") else "",
        f"Composition: {item['composer']}" if item.get("composer") else "",
        f"Arrangement: {item['arranger']}" if item.get("arranger") else "",
    ]
    tags = normalize_tags(item.get("tags", []), locale)
    if label in DIFFICULTIES:
        tags.insert(0, {"title": localize(f"#{label.upper()}", locale)})

    result: dict[str, Any] = {
        "version": item.get("version", 1),
        "rating": rating,
        "engine": engine,
        "useSkin": {"useDefault": True},
        "useBackground": {"useDefault": False, "item": background_name},
        "useEffect": {"useDefault": True},
        "useParticle": {"useDefault": True},
        "title": localize(item.get("title") or name, locale),
        "artists": localize(
            item.get("artists") or item.get("composer") or item.get("lyricist") or "",
            locale,
        ),
        "author": localize(
            item.get("author")
            or ("Project Sekai: Colorful Stage!" if pjsk else ""),
            locale,
        ),
        "tags": tags,
        "meta": {
            "importer": "chart-bundle",
            "originalName": name,
            "source": item.get("source") or ("https://sekai.best" if pjsk else None),
            "chartFile": label,
            "chartFormat": chart_format,
            "chartHash": chart_hash,
            "bgmHash": bgm_hash,
            "bgmSource": bgm_source,
            "sourceMeta": item,
            **(pjsk or {}),
        },
    }
    description = item.get("description") or "\n".join(filter(None, credits))
    if description:
        result["description"] = localize(description, locale)
    return result


def write_playlist(
    output_dir: Path,
    *,
    item: dict[str, Any],
    name: str,
    levels: list[str],
    cover_path: Path,
    locale: str,
    pjsk: dict[str, Any] | None,
) -> None:
    output_dir = replace_directory(output_dir)
    shutil.copy2(cover_path, output_dir / "thumbnail")
    write_json(
        output_dir / "item.json",
        {
            "version": item.get("version", 1),
            "title": localize(item.get("title") or name, locale),
            "time": 0,
            "author": localize(
                item.get("author")
                or ("Project Sekai: Colorful Stage!" if pjsk else ""),
                locale,
            ),
            "tags": normalize_tags(item.get("tags", []), locale),
            "levels": levels,
            "meta": {
                "importer": "chart-bundle",
                "originalName": name,
                "source": item.get("source")
                or ("https://sekai.best" if pjsk else None),
                **(pjsk or {}),
            },
        },
    )


if __name__ == "__main__":
    main()
