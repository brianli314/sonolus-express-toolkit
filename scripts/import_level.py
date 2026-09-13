from PIL import Image
import zipfile
import os
from pathlib import Path
import argparse
import json
from utils import *
from utils import localize, generate_background
import shutil
import time


PARENT = Path(__file__).parents[1]
EXTRACTED = PARENT / "extractions"
ENGINE = "next-rush-sbuga"
IMPORT_DIR = PARENT / "imports"
LEVELS_DIR = PARENT / "source" / "levels"
PLAYLIST_DIR = PARENT / "source" / "playlists"

DIRECT = ["version", "rating", "useSkin", "useParticle", "useEffect"]
LOCALIZE = ["title", "artists", "author", "description", "tags"]

SORT = ["easy", "normal", "hard", "expert", "master", "append"]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a level from a scp")
    parser.add_argument(
        "--engine",
        default=ENGINE,
        help="Name of engine to use",
    )

    parser.add_argument(
        "--import-dir",
        default=IMPORT_DIR,
        type=Path,
        help="Path to import import directory"
    )

    parser.add_argument(
        "--locale",
        default="en",
        help="Locale to use when processing files"
    )

    return parser.parse_args()


def write_level_json(data, args):
    out = {}
    for item in DIRECT:
        if data.get(item):
            out[item] = data[item]
    for item in LOCALIZE:
        if data.get(item):
            out[item] = localize(data[item], args.locale)

    out["engine"] = args.engine
    out["useBackground"] = {
        "useDefault": False,
        "item": f"{data["name"]}-v3-bg"
    }
    return out

def write_playlist_json(data, level_names, locale):
    out = {}
    out["version"] = data["version"]
    out["title"] = localize(data["title"], locale)
    out["time"] = data.get("time", 0)
    out["author"] = localize(data["author"], locale)
    out["tags"] = localize(data["tags"], locale)

    if data.get("subtitle"):
        out["subtitle"] = localize(data["subtitle"], locale)
    else:
        out["subtitle"] = localize("", locale)

    out["levels"] = level_names
    return out
    

def import_levels(items, args):
    level_names = []
    for item in items:
        name = item["name"]
        exist = False
        for lvl in os.listdir(LEVELS_DIR):
            if lvl.endswith(name):
                exist = True
                break
        if exist:
            print(f"Skipping {name}: already exists")
            continue

        tstamp = f"{10_000_000_000 - time.time()}-{name}"
        directory = LEVELS_DIR / tstamp
        os.mkdir(directory)

        shutil.copy2(EXTRACTED / item["cover"]["url"].lstrip("/"), directory / "cover")
        shutil.copy2(EXTRACTED / item["bgm"]["url"].lstrip("/"), directory / "bgm")
        shutil.copy2(EXTRACTED / item["data"]["url"].lstrip("/"), directory / "data")
            
        if item.get("preview"):
            shutil.copy2(EXTRACTED / item["preview"]["url"].lstrip("/"), directory / "preview")

        info = write_level_json(item, args)
        with open(directory / "item.json", 'w') as f:
            json.dump(info, f, indent=4)

        generate_background(directory / "cover", name)
        level_names.append(tstamp)
        print(f"Created level {name}")
    return level_names


def import_playlists(items, args):
    for item in items:
        name = item["name"]
        exist = False
        for lvl in os.listdir(PLAYLIST_DIR):
            if lvl.endswith(name):
                exist = True
                break
        if exist:
            print(f"Skipping {name}: already exists")
            continue

        directory = PLAYLIST_DIR / f"{10_000_000_000 - time.time()}-{name}"
        os.mkdir(directory)

        shutil.copy2(EXTRACTED / item["thumbnail"]["url"].lstrip("/"), directory / "thumbnail")

        level_names = import_levels(list(reversed(item["levels"])), args)

        info = write_playlist_json(item, list(reversed(level_names)), args.locale)
        with open(directory / "item.json", 'w') as f:
            json.dump(info, f, indent=4)

        print(f"Created playlist {name}")


def main():
    args = parse_args()
    LEVELS_DIR.mkdir(exist_ok=True)
    PLAYLIST_DIR.mkdir(exist_ok=True)
    imports = os.listdir(args.import_dir)

    if not imports:
        print("No SCPs found")
        return
    
    for imp in imports:
        if not imp.endswith(".scp"):
            print(f"File {imp} not an SCP")
            continue

        extract_scp(args.import_dir / imp, PARENT / "extractions")

        levels = EXTRACTED / "sonolus" / "levels"
        with open(levels / "list") as f:
            data = json.load(f)
            items = data.get("items")
        
        import_levels(items, args)

        playlists = EXTRACTED / "sonolus" / "playlists"
        with open(playlists / "list") as f:
            data = json.load(f)
            items = data.get("items")

        import_playlists(items, args)

        shutil.rmtree(PARENT / "extractions")
        
if __name__ == "__main__":
    main()