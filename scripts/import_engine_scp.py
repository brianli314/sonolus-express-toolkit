import argparse
import json
import shutil
from pathlib import Path

from utils import extract_scp, localize


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
EXTRACTED = ROOT / "extractions"
DEFAULT_SCP = ROOT / "imports" / "reference.scp"

FIELDS = ["version", "title", "subtitle", "author", "description", "tags"]

FILES = {
    "engines": {
        "thumbnail": "thumbnail",
        "playData": "playData",
        "watchData": "watchData",
        "previewData": "previewData",
        "tutorialData": "tutorialData",
        "rom": "rom",
        "configuration": "configuration",
    },
    "skins": {"thumbnail": "thumbnail", "data": "data", "texture": "texture"},
    "backgrounds": {
        "thumbnail": "thumbnail",
        "data": "data",
        "image": "image",
        "configuration": "configuration",
    },
    "effects": {"thumbnail": "thumbnail", "data": "data", "audio": "audio"},
    "particles": {"thumbnail": "thumbnail", "data": "data", "texture": "texture"},
}


def parse_args():
    parser = argparse.ArgumentParser(description="Import an engine from an SCP.")
    parser.add_argument("--scp", type=Path, default=DEFAULT_SCP)
    parser.add_argument("--engine-name")
    parser.add_argument("--locale", default="en")
    return parser.parse_args()


def repository_file(reference):
    return EXTRACTED / "sonolus" / "repository" / reference["hash"]


def item_json(item, locale):
    data = {}
    for field in FIELDS:
        if field in item:
            data[field] = localize(item[field], locale)
    if "tags" not in data:
        data["tags"] = []
    return data


def copy_item(category, item, locale, name=None):
    name = name or item["name"]
    target = SOURCE / category / name
    target.mkdir(parents=True, exist_ok=True)

    for field, filename in FILES[category].items():
        if item.get(field):
            shutil.copy2(repository_file(item[field]), target / filename)

    with open(target / "item.json", "w") as f:
        json.dump(item_json(item, locale), f, indent=4)

    return name


def main():
    args = parse_args()

    if EXTRACTED.exists():
        shutil.rmtree(EXTRACTED)
    playlist = False

    try:
        extract_scp(args.scp, EXTRACTED)

        with open(EXTRACTED / "sonolus" / "levels" / "list") as f:
            levels = json.load(f)["items"]
        if levels:
            level = levels[0]
        else:
            with open(EXTRACTED / "sonolus" / "playlists" / "list") as f:
                plists = json.load(f)["items"]
            if plists:
                plist = plists[0]
                playlist = True
            else: 
                print("No samples found")
                return
            
        if playlist:
            level = plist["levels"][0]
        engine = level["engine"]
        skin = copy_item("skins", engine["skin"], args.locale)
        background = copy_item("backgrounds", engine["background"], args.locale)
        effect = copy_item("effects", engine["effect"], args.locale)
        particle = copy_item("particles", engine["particle"], args.locale)

        engine_name = args.engine_name or engine["name"]
        copy_item("engines", engine, args.locale, engine_name)

        item_path = SOURCE / "engines" / engine_name / "item.json"
        with open(item_path) as f:
            data = json.load(f)
        data.update(
            {
                "skin": skin,
                "background": background,
                "effect": effect,
                "particle": particle,
            }
        )
        with open(item_path, "w") as f:
            json.dump(data, f, indent=4)

        print(f"Imported engine: {engine_name}")
    finally:
        print()
        shutil.rmtree(EXTRACTED, ignore_errors=True)


if __name__ == "__main__":
    main()
