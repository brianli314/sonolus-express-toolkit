"""Change the engine assigned to every level in the source tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from import_utils import validate_item_name, write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "source"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assign one engine to every existing level."
    )
    parser.add_argument(
        "engine",
        type=validate_item_name,
        help="Existing engine item to assign.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine_item = SOURCE_DIR / "engines" / args.engine / "item.json"
    if not engine_item.is_file():
        raise SystemExit(f"Engine item not found: {engine_item}")

    changed = 0
    for item_path in sorted((SOURCE_DIR / "levels").glob("*/item.json")):
        item = json.loads(item_path.read_text(encoding="utf-8"))
        if item.get("engine") == args.engine:
            continue

        print(f"{item_path.parent.name}: {item.get('engine')} -> {args.engine}")
        item["engine"] = args.engine
        write_json(item_path, item)
        changed += 1

    print(f"Updated {changed} level(s).")


if __name__ == "__main__":
    main()
