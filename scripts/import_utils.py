from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def validate_item_name(value: str) -> str:
    value = value.strip()
    if not value or Path(value).name != value or value in {".", ".."}:
        raise ValueError("must be a single non-empty item name")
    return value


def localize(value: Any, locale: str = "en") -> dict[str, str]:
    if isinstance(value, dict):
        return value
    return {locale: "" if value is None else str(value)}


def normalize_tags(value: Any, locale: str = "en") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for tag in value:
        if isinstance(tag, str):
            result.append({"title": {locale: tag}})
            continue
        normalized: dict[str, Any] = {}
        if "title" in tag:
            normalized["title"] = localize(tag["title"], locale)
        if "icon" in tag:
            normalized["icon"] = tag["icon"]
        if normalized:
            result.append(normalized)
    return result


def replace_directory(path: Path) -> Path:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
