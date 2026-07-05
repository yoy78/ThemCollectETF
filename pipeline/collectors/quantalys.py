"""Collecteur Quantalys (palmares / pages thematiques).

Desactive par defaut (voir config.yaml: quantalys.enabled). Aucune URL n'est
devinee : seules les pages explicitement listees dans config.yaml sont
interrogees, et uniquement si robots.txt les autorise pour notre User-Agent.

La structure exacte des pages Quantalys n'a pas pu etre inspectee (reseau
bloque depuis l'environnement de developpement). L'extraction ci-dessous est
volontairement generique (lignes de tableaux HTML) : un calibrage des
selecteurs sera necessaire une fois les premieres pages reellement recuperees
(cf. les logs du workflow GitHub Actions).
"""
from __future__ import annotations

import hashlib

from bs4 import BeautifulSoup

from pipeline.collectors.base import Item, PoliteFetcher, RobotsDisallowed


def _item_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


class QuantalysCollector:
    name = "quantalys"

    def __init__(self, urls: list[str], user_agent: str, min_delay_seconds: float = 4.0):
        self.urls = urls
        self.fetcher = PoliteFetcher(user_agent=user_agent, min_delay_seconds=min_delay_seconds)

    def collect(self) -> list[Item]:
        items: list[Item] = []
        for url in self.urls:
            try:
                html = self.fetcher.fetch(url)
            except RobotsDisallowed as exc:
                items.append(
                    Item(
                        id=_item_id("blocked", url),
                        source=self.name,
                        category=url,
                        label=f"Acces bloque par robots.txt: {exc}",
                        url=url,
                        metadata={"blocked": True},
                    )
                )
                continue
            except OSError as exc:
                items.append(
                    Item(
                        id=_item_id("error", url),
                        source=self.name,
                        category=url,
                        label=f"Erreur de collecte pour {url}: {exc}",
                        url=url,
                        metadata={"error": True},
                    )
                )
                continue

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.find_all("tr")
            for idx, row in enumerate(rows):
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                cells = [c for c in cells if c]
                if len(cells) < 2:
                    continue
                label = " | ".join(cells)
                items.append(
                    Item(
                        id=_item_id(url, str(idx), label),
                        source=self.name,
                        category=url,
                        label=label,
                        url=url,
                        metadata={"row_index": idx, "cells": cells},
                    )
                )
        return items
