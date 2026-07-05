"""Detection de signaux a partir d'un snapshot courant vs le precedent."""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.collectors.base import Item


@dataclass
class Signal:
    source: str
    category: str
    kind: str  # "new" | "error"
    label: str
    url: str = ""


def detect_signals(source: str, current_items: list[Item], previous_items: dict[str, dict]) -> list[Signal]:
    signals: list[Signal] = []
    for item in current_items:
        if item.metadata.get("error") or item.metadata.get("blocked"):
            signals.append(Signal(source=source, category=item.category, kind="error", label=item.label, url=item.url))
            continue
        if item.id not in previous_items:
            signals.append(Signal(source=source, category=item.category, kind="new", label=item.label, url=item.url))
    return signals
