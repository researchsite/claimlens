import json
import os
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "cache"


def cache_path(preset_id: str) -> Path:
    return CACHE_DIR / f"{preset_id}.json"


def has_cache(preset_id: str) -> bool:
    return cache_path(preset_id).exists()


def load_cache(preset_id: str) -> dict | None:
    p = cache_path(preset_id)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(preset_id: str, data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    with open(cache_path(preset_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
