"""Rendu Markdown du digest quotidien a partir des signaux detectes."""
from __future__ import annotations

from pipeline.signals import Signal

SOURCE_TITLES = {
    "news_rss": "Signaux faibles (actualite)",
    "quantalys": "Quantalys",
}


def build_report(run_date: str, signals_by_source: dict[str, list[Signal]]) -> str:
    lines = [f"# Digest thematique - {run_date}", ""]

    errors = [s for signals in signals_by_source.values() for s in signals if s.kind == "error"]
    if errors:
        lines.append("## Avertissements")
        for e in errors:
            lines.append(f"- **{e.source}** ({e.category}): {e.label}")
        lines.append("")

    any_new = False
    for source, signals in signals_by_source.items():
        new_signals = [s for s in signals if s.kind == "new"]
        if not new_signals:
            continue
        any_new = True
        lines.append(f"## {SOURCE_TITLES.get(source, source)}")
        by_category: dict[str, list[Signal]] = {}
        for s in new_signals:
            by_category.setdefault(s.category, []).append(s)
        for category, items in by_category.items():
            lines.append(f"### {category}")
            for s in items:
                if s.url:
                    lines.append(f"- [{s.label}]({s.url})")
                else:
                    lines.append(f"- {s.label}")
            lines.append("")

    if not any_new and not errors:
        lines.append("Rien de nouveau depuis le dernier passage.")
        lines.append("")

    return "\n".join(lines)
