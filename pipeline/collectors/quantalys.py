"""Collecteur Quantalys (palmares / pages thematiques / liste d'articles).

Desactive par defaut tant que non confirme (voir config.yaml: quantalys.enabled).
Les URLs suivies sont soit fournies par l'utilisateur, soit trouvees via une
recherche web reelle (jamais devinees) - voir config.yaml pour la liste actuelle.
Chaque requete respecte robots.txt et un delai minimum entre appels.

La structure exacte des pages n'a pas pu etre inspectee depuis l'environnement
de developpement (reseau bloque) : l'extraction combine deux strategies
generiques qui ne dependent pas des classes CSS exactes :
  - liens vers des articles (href contenant "/Article/Consultation/") : capte
    les nouvelles publications (palmares, observatoires) au fil de leur mise
    en ligne, utile comme signal faible.
  - lignes de tableaux HTML (tr/td) : capte d'eventuels classements chiffres.
Un calibrage plus fin sera possible une fois les premiers runs reels
inspectes (logs du workflow GitHub Actions).
"""
from __future__ import annotations

import hashlib
import re
import sys
import urllib.parse

from bs4 import BeautifulSoup

from pipeline.collectors.base import Item, PoliteFetcher, RobotsDisallowed

ARTICLE_HREF_RE = re.compile(r"/Article/Consultation/\d+")


def _debug(message: str) -> None:
    print(f"[quantalys] {message}", file=sys.stderr)


def _page_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


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

            _debug(f"{url}: {len(html)} octets recus, titre={_page_title(html)!r}")

            soup = BeautifulSoup(html, "html.parser")

            seen_article_urls: set[str] = set()
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if not ARTICLE_HREF_RE.search(href):
                    continue
                absolute_url = urllib.parse.urljoin(url, href)
                if absolute_url in seen_article_urls:
                    continue
                seen_article_urls.add(absolute_url)
                title = link.get_text(strip=True)
                if not title:
                    continue
                items.append(
                    Item(
                        id=_item_id("article", absolute_url),
                        source=self.name,
                        category=url,
                        label=title,
                        url=absolute_url,
                        metadata={"kind": "article"},
                    )
                )
            _debug(f"{url}: {len(soup.find_all('a', href=True))} liens <a>, {len(seen_article_urls)} articles retenus")

            rows = soup.find_all("tr")
            _debug(f"{url}: {len(rows)} lignes <tr> trouvees")
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
