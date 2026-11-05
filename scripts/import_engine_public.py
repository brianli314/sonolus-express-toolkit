import argparse
import gzip
from pathlib import Path
import shutil
import json
import os
from typing import Any
from utils import *

SOURCE = Path(__file__).resolve().parents[1] / "source"
UPSTREAM = Path(__file__).resolve().parents[1] / "upstream"

ENGINE_NAME = 'next-rush-sbuga'
REF_NAME = 'next-rush'
SBUGA_PATH = UPSTREAM / "sbuga" / "files"


ENGINE_MAP = {
        "engine.json": "item.json",
        "thumbnail.png": "thumbnail.png",
        "EnginePlayData": "playData",
        "EngineTutorialData": "tutorialData",
        "EngineRom": "rom",
        "EngineConfiguration": "configuration",

        "EnginePreviewData": "previewData",
        "EngineWatchData": "watchData",
    }

FIELDS = ["version", "title", "subtitle", "author", "description", "tags"]


def update_configuration(
    configuration_path: Path,
    config_overrides: dict[str, dict[str, Any]],
) -> None:
    if not config_overrides:
        return

    with gzip.open(configuration_path, "rt", encoding="utf-8") as f:
        configuration = json.load(f)

    options = configuration.get("options")
    if not isinstance(options, list):
        raise ValueError(
            f"Engine configuration has no options list: {configuration_path}"
        )

    options_by_name = {
        option.get("name"): option
        for option in options
        if isinstance(option, dict) and isinstance(option.get("name"), str)
    }
    missing = sorted(set(config_overrides) - options_by_name.keys())
    if missing:
        raise ValueError(
            "Configuration overrides reference unknown options: "
            + ", ".join(missing)
        )

    for option_name, overrides in config_overrides.items():
        if not isinstance(overrides, dict):
            raise TypeError(
                f"Overrides for {option_name!r} must be an object, "
                f"got {type(overrides).__name__}"
            )
        options_by_name[option_name].update(overrides)

    encoded = json.dumps(
        configuration,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    configuration_path.write_bytes(gzip.compress(encoded, mtime=0))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the pinned SBUga engine.")
    parser.add_argument(
        "--engine-name",
        default=ENGINE_NAME,
        help="Name of the imported engine item.",
    )

    parser.add_argument(
        "--reference-name",
        default=REF_NAME,
        help="Name of reference engine"
    )

    parser.add_argument(
        "--path",
        default = SBUGA_PATH,
        help="Path of the reference repository"
    )

    parser.add_argument(
        "--locale",
        default="en",
        help="Locale to use when processing files"
    )

    return parser.parse_args()

def copy_folder(folder, data_type, name, locale):
    for item in os.listdir(folder):
        if item == folder.parent.name.removesuffix("s") + ".json":
            os.makedirs(SOURCE / data_type / name, exist_ok=True) 
            shutil.copy2(folder / item, SOURCE / data_type / name / "item.json")
            with open(SOURCE / data_type / name / "item.json", 'r') as f:
                data = json.load(f)

            for key in data:
                if key in FIELDS :
                    data[key] = localize(data[key], locale)

            if "tags" not in data:
                data["tags"] = []
            with open(SOURCE / data_type / name / "item.json", 'w') as f:
                json.dump(data, f, indent=4)
                
        else:
            os.makedirs(SOURCE / data_type / name, exist_ok=True)
            out_item = item
            if item.endswith(".json.gz"):
                out_item = item.removesuffix(".json.gz")
                print(f"Removed suffix of {item}")
            shutil.copy2(folder / item, SOURCE / data_type / name / out_item)

def copy_engine(engine, name, locale):
    for item in os.listdir(engine):
        if item in ENGINE_MAP:
            shutil.copy2(engine / item, SOURCE / "engines" / name / ENGINE_MAP[item])
        else:
            print(f"Extra item found: {item}")
            shutil.copy2(engine / item, SOURCE / "engines" / name / item)
            continue

    with open(SOURCE / "engines" / name/ "item.json") as f:
        data = json.load(f)

    for key in data:
        if key in FIELDS :
            data[key] = localize(data[key], locale)
            
    if "tags" not in data:
        data["tags"] = []

    update_configuration(
        SOURCE / "engines" / name / "configuration",
        data.get("config_overrides", {}),
    )

    skin =  data.get("skin_name_locale").get(locale)
    if skin:
        data["skin"] = skin
    else:
        data["skin"] = data["skin_name"]

    data.pop("skin_name")
    data.pop("skin_name_locale")

    data["background"] = data.pop("background_name")
    data["effect"] = data.pop("effect_name")
    data["particle"] = data.pop("particle_name")

    with open(SOURCE / "engines" / name/ "item.json", 'w') as f:
        json.dump(data, f, indent=4)



def main():
    args = parse_args()

    engine_source = SBUGA_PATH / "engines" / args.reference_name

    engine_metadata = json.loads(Path(engine_source / "engine.json").read_text())

    skin_name = engine_metadata["skin_name"]
    skin_locale = engine_metadata.get("skin_name_locale").get(args.locale)

    if skin_locale:
        skin_name = skin_locale

    background_name = engine_metadata["background_name"]
    effect_name = engine_metadata["effect_name"]
    particle_name = engine_metadata["particle_name"]

    skin_source = SBUGA_PATH / "skins" / skin_name
    background_source = SBUGA_PATH / "backgrounds" / background_name
    effect_source = SBUGA_PATH / "effects" / effect_name
    particle_source = SBUGA_PATH / "particles" / particle_name

    os.makedirs(SOURCE / "engines" / args.engine_name, exist_ok=True)


    copy_engine(engine_source, args.engine_name, args.locale)
    copy_folder(skin_source, "skins", skin_name, args.locale)
    copy_folder(background_source, "backgrounds", background_name, args.locale)
    copy_folder(effect_source, "effects", effect_name, args.locale)
    copy_folder(particle_source, "particles", particle_name, args.locale)

    print(f"Imported engine: {args.reference_name} -> {args.engine_name}")
    print(f"Default skin:    {skin_name}")
    print(f"Background:      {background_name}")
    print(f"Effect:          {effect_name}")
    print(f"Particle:        {particle_name}")
    
    

if __name__ == "__main__":
    main()
