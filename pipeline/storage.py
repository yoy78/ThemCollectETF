"""Lecture/ecriture des snapshots JSON versionnes dans data/snapshots/."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from pipeline.collectors.base import Item

SNAPSHOTS_DIR = Path("data/snapshots")


def _source_dir(source: str) -> Path:
    path = SNAPSHOTS_DIR / source
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_latest(source: str) -> dict[str, dict]:
    """Retourne {item_id: item_dict} du dernier snapshot connu, ou {} si aucun."""
    latest_path = _source_dir(source) / "latest.json"
    if not latest_path.exists():
        return {}
    with latest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["id"]: item for item in data.get("items", [])}


def save_snapshot(source: str, items: list[Item], run_date: str) -> None:
    payload = {"source": source, "date": run_date, "items": [asdict(i) for i in items]}
    source_dir = _source_dir(source)
    with (source_dir / f"{run_date}.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
    with (source_dir / "latest.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
