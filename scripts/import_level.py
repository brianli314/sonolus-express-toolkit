from PIL import Image
import zipfile
import os
from pathlib import Path
import argparse
import json
from utils import *
import pjsk_background_gen_PIL
from utils import localize
import shutil

PARENT = Path(__file__).parents[1]
EXTRACTED = PARENT / "extractions"
ENGINE = "next-rush-sbuga"
IMPORT_DIR = PARENT / "imports"
LEVELS_DIR = PARENT / "source" / "levels"
PLAYLIST_DIR = PARENT / "source" / "playlists"
BACKGROUNDS_DIR = PARENT / "source" / "backgrounds"

DIRECT = ["version", "rating", "useSkin", "useParticle", "useEffect"]
LOCALIZE = ["title", "artists", "author", "description", "tags"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the pinned SBUga engine.")
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

def write_playlist_json(data, args):
    out = {}
    out["version"] = data["version"]
    out["title"] = localize(data["title"], args.locale)
    out["time"] = data.get("time", 0)
    out["author"] = localize(data["author"], args.locale)
    out["tags"] = localize(data["tags"], args.locale)

    if data.get("subtitle"):
        out["subtitle"] = localize(data["subtitle"], args.locale)
    else:
        out["subtitle"] = localize("", args.locale)

    out["levels"] = [level.get("name") for level in data["levels"]]
    import_levels(data["levels"], args)
    return out

def generate_background(cover_path, name):
    bg_dir = BACKGROUNDS_DIR / f"{name}-v3-bg"
    os.makedirs(bg_dir, exist_ok=True)

    with Image.open(cover_path) as im:
        im = im.convert("RGBA")
        rendered = pjsk_background_gen_PIL.render_v3(im)
        rendered = rendered.crop((0, 440, 2048, 1608))
        rendered.save(bg_dir / "image.png", format="PNG")

    shutil.copy2(PARENT / "background_templates" / "data", bg_dir / "data")
    shutil.copy2(cover_path, bg_dir / "thumbnail")
    shutil.copy2(PARENT / "background_templates" / "configuration", bg_dir / "configuration")

    item = {
        "version": 2, 
        "title": {
            "en": name
        },
        "subtitle": {
            "en": f"Generated background for {name}"
        },
        "author": {
            "en": f"Untitled Charts Generator"
        },
        "tags": [],
    }
    with open(bg_dir / "item.json", 'w') as f:
        json.dump(item, f, indent=4)
    
    

def import_levels(items, args):
    for item in items:
        name = item["name"]
        if name in os.listdir(LEVELS_DIR):
            print(f"Skipping {name}: already exists")
            continue
        os.mkdir(LEVELS_DIR / name)

        shutil.copy2(EXTRACTED / item["cover"]["url"].lstrip("/"), LEVELS_DIR / name / "cover")
        shutil.copy2(EXTRACTED / item["bgm"]["url"].lstrip("/"), LEVELS_DIR / name / "bgm")
        shutil.copy2(EXTRACTED / item["data"]["url"].lstrip("/"), LEVELS_DIR / name / "data")
            
        if item.get("preview"):
            shutil.copy2(EXTRACTED / item["preview"]["url"].lstrip("/"), LEVELS_DIR / name / "preview")

        info = write_level_json(item, args)
        with open(LEVELS_DIR / name / "item.json", 'w') as f:
            json.dump(info, f, indent=4)

        generate_background(LEVELS_DIR / name / "cover", name)
        print(f"Created level {name}")


def import_playlists(items, args):
    for item in items:
        name = item["name"]
        if name in os.listdir(PLAYLIST_DIR):
            print(f"Skipping {name}: already exists")
            continue
        os.mkdir(PLAYLIST_DIR / name)

        shutil.copy2(EXTRACTED / item["thumbnail"]["url"].lstrip("/"), PLAYLIST_DIR / name / "thumbnail")

        info = write_playlist_json(item, args)
        with open(PLAYLIST_DIR  / name / "item.json", 'w') as f:
            json.dump(info, f, indent=4)

        print(f"Created playlist {name}")


def main():
    args = parse_args()
    LEVELS_DIR.mkdir(exist_ok=True)
    PLAYLIST_DIR.mkdir(exist_ok=True)
    BACKGROUNDS_DIR.mkdir(exist_ok=True)
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