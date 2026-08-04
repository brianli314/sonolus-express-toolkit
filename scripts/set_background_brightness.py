"""Set the dark overlay used by generated PJSK backgrounds."""

from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

from import_utils import write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "source"
SETTINGS_PATH = Path(__file__).with_name("import_settings.json")


def parse_mask(value: str) -> str:
    value = value.strip().lower().removeprefix("#")
    if len(value) == 1:
        value = f"000{value}"
    if not re.fullmatch(r"000[0-9a-f]", value):
        raise argparse.ArgumentTypeError("use 0-f, 0000-000f, or #0000-#000f")
    return f"#{value}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set generated-background darkness (0 is brightest, f is darkest)."
    )
    parser.add_argument("mask", type=parse_mask, help="Black overlay alpha, such as 4")
    return parser.parse_args()


def main() -> None:
    mask = parse_args().mask
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    settings["backgroundMask"] = mask
    write_json(SETTINGS_PATH, settings)

    configuration = json.dumps(
        {"scope": "Sekai", "blur": 0, "mask": mask}, separators=(",", ":")
    ).encode()
    compressed = gzip.compress(configuration, mtime=0)

    backgrounds_dir = SOURCE_DIR / "backgrounds"
    paths = sorted(backgrounds_dir.glob("pjsk-generated-*-v3/configuration"))
    template_path = backgrounds_dir / "pjsk_template" / "configuration"
    if template_path.parent.is_dir():
        paths.append(template_path)

    for path in paths:
        path.write_bytes(compressed)

    revision = f"center-crop-2048x1168-mask-{mask.removeprefix('#')}"
    for item_path in sorted(backgrounds_dir.glob("pjsk-generated-*-v3/item.json")):
        item = json.loads(item_path.read_text(encoding="utf-8"))
        item["meta"]["renderRevision"] = revision
        write_json(item_path, item)

    print(f"Set background mask to {mask} in {len(paths)} configuration(s).")
    print("Run npm run pack to apply the change to the server.")


if __name__ == "__main__":
    main()
