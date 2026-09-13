import zipfile
import os
from pathlib import Path
import pjsk_background_gen_PIL
from PIL import Image
import shutil
import json

def localize(value, locale="en"):
    if isinstance(value, list):
        return [localize(item, locale) for item in value]

    elif isinstance(value, dict):
        if "title" in value:
            return {
                **value,
                "title": localize(value["title"], locale)
            }
    elif not isinstance (value, str):
        return value
    return {locale: "" if value is None else str(value)}

def extract_scp(scp, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(scp, 'r') as zip_ref:
        zip_ref.extractall(out_dir)
        print(f"Extracted all files to: {out_dir}")


def generate_background(cover_path, name):
    PARENT = Path(__file__).parents[1]
    BACKGROUNDS_DIR = PARENT / "source" / "backgrounds"

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
    