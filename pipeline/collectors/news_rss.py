"""Collecteur de signaux faibles via les flux RSS Google News.

Sert de proxy pour detecter des sujets (rotations sectorielles, collectes
thematiques) avant qu'ils ne soient consolides dans des palmares officiels.
"""
from __future__ import annotations

import hashlib
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from pipeline.collectors.base import Item

FEED_URL = "https://news.google.com/rss/search"
USER_AGENT = "ThemCollectETF-Bot/1.0 (+veille personnelle, contact: ybrion@gmail.com)"


def _item_id(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]


def _fetch(url: str, timeout: float = 15.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


class NewsRSSCollector:
    name = "news_rss"

    def __init__(self, keywords: list[str], max_items_per_keyword: int = 8, delay_seconds: float = 1.5):
        self.keywords = keywords
        self.max_items_per_keyword = max_items_per_keyword
        self.delay_seconds = delay_seconds

    def _query_url(self, keyword: str) -> str:
        params = {"q": keyword, "hl": "fr", "gl": "FR", "ceid": "FR:fr"}
        return f"{FEED_URL}?{urllib.parse.urlencode(params)}"

    def collect(self) -> list[Item]:
        items: list[Item] = []
        for i, keyword in enumerate(self.keywords):
            if i > 0:
                time.sleep(self.delay_seconds)
            url = self._query_url(keyword)
            try:
                xml_text = _fetch(url)
            except OSError as exc:
                items.append(
                    Item(
                        id=f"error-{_item_id(keyword)}",
                        source=self.name,
                        category=keyword,
                        label=f"Erreur de collecte pour '{keyword}': {exc}",
                        metadata={"error": True},
                    )
                )
                continue

            root = ET.fromstring(xml_text)
            channel_items = root.findall("./channel/item")[: self.max_items_per_keyword]
            for entry in channel_items:
                title = (entry.findtext("title") or "").strip()
                link = (entry.findtext("link") or "").strip()
                pub_date = (entry.findtext("pubDate") or "").strip()
                source_el = entry.find("source")
                publisher = (source_el.text or "").strip() if source_el is not None else ""
                items.append(
                    Item(
                        id=_item_id(link or title),
                        source=self.name,
                        category=keyword,
                        label=title,
                        url=link,
                        metadata={"published": pub_date, "publisher": publisher},
                    )
                )
        return items
