"""Orchestrateur du pipeline: lit config.yaml, lance les collecteurs actifs,
calcule les signaux et ecrit le digest du jour."""
from __future__ import annotations

import datetime
from pathlib import Path

import yaml

from pipeline.collectors.news_rss import NewsRSSCollector
from pipeline.collectors.quantalys import QuantalysCollector
from pipeline.report import build_report
from pipeline.signals import Signal, detect_signals
from pipeline.storage import load_latest, save_snapshot

REPORTS_DIR = Path("data/reports")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_collectors(config: dict) -> list:
    collectors = []

    news_cfg = config.get("news_rss", {})
    if news_cfg.get("enabled"):
        collectors.append(
            NewsRSSCollector(
                keywords=news_cfg.get("keywords", []),
                max_items_per_keyword=news_cfg.get("max_items_per_keyword", 8),
            )
        )

    quantalys_cfg = config.get("quantalys", {})
    if quantalys_cfg.get("enabled") and quantalys_cfg.get("urls"):
        collectors.append(
            QuantalysCollector(
                urls=quantalys_cfg["urls"],
                user_agent=quantalys_cfg.get("user_agent", "ThemCollectETF-Bot/1.0"),
                min_delay_seconds=quantalys_cfg.get("min_delay_seconds", 4.0),
            )
        )

    return collectors


def run(config_path: str = "config.yaml") -> str:
    config = load_config(config_path)
    run_date = datetime.date.today().isoformat()

    signals_by_source: dict[str, list[Signal]] = {}
    for collector in build_collectors(config):
        previous = load_latest(collector.name)
        current_items = collector.collect()
        save_snapshot(collector.name, current_items, run_date)
        signals_by_source[collector.name] = detect_signals(collector.name, current_items, previous)

    report_md = build_report(run_date, signals_by_source)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"{run_date}.md").write_text(report_md, encoding="utf-8")
    (REPORTS_DIR / "latest.md").write_text(report_md, encoding="utf-8")

    return report_md


if __name__ == "__main__":
    print(run())
