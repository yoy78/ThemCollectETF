"""Collecteur Quantalys (palmares / pages thematiques / liste d'articles).

Desactive (voir config.yaml: quantalys.enabled=false). Teste en conditions
reelles via GitHub Actions sur 3 URLs trouvees par recherche web (jamais
devinees) : chaque reponse HTTP simple (urllib, sans JS) ne renvoie que
~230-240 octets, un <title> vide et 0 lien - un veritable HTML de page ne
tiendrait pas dans si peu d'octets. Le contenu brut recu est :

    <html lang="en"><head></head><body><script>
    window.location.href='/redirect_<jeton_opaque>/<chemin_original>';
    </script><noscript>This website requires JS enabled and cookies</noscript>
    </body></html>

C'est un mecanisme anti-bot deliberatif (redirection vers une url a jeton
genere cote client, valide uniquement si JS + cookies sont executes), pas
une simple page dynamique. Le contourner demanderait un navigateur headless
dont le seul but serait de dejouer cette protection - non fait sans accord
explicite, et resterait fragile (le jeton change vraisemblablement a chaque
session). Voir config.yaml pour l'alternative legitime (produit officiel
"Flux de donnees" Quantalys).

Le code ci-dessous reste fonctionnel (respect robots.txt, rate-limit,
extraction generique liens/tableaux) au cas ou d'autres pages Quantalys
sans ce challenge JS seraient identifiees.
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
            _debug(f"{url}: contenu brut = {html!r}")

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
