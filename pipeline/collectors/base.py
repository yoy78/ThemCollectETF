"""Interfaces communes aux collecteurs de donnees."""
from __future__ import annotations

import time
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol
from urllib.robotparser import RobotFileParser


@dataclass
class Item:
    """Un element de donnee collecte (article, ligne de palmares, flux...)."""

    id: str
    source: str
    category: str
    label: str
    url: str = ""
    metadata: dict = field(default_factory=dict)


class Collector(Protocol):
    name: str

    def collect(self) -> list[Item]:
        ...


class RobotsDisallowed(RuntimeError):
    """Leve quand robots.txt interdit l'acces a une url cible."""


class PoliteFetcher:
    """Fetcher HTTP qui respecte robots.txt et impose un delai entre requetes."""

    def __init__(self, user_agent: str, min_delay_seconds: float = 3.0):
        self.user_agent = user_agent
        self.min_delay_seconds = min_delay_seconds
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._last_request_at: dict[str, float] = {}

    def _robots_for(self, url: str) -> RobotFileParser:
        from urllib.parse import urlsplit

        origin = urlsplit(url)
        base = f"{origin.scheme}://{origin.netloc}"
        if base not in self._robots_cache:
            parser = RobotFileParser()
            parser.set_url(f"{base}/robots.txt")
            try:
                parser.read()
            except OSError:
                # robots.txt injoignable : par prudence on refuse l'acces.
                parser.disallow_all = True
            self._robots_cache[base] = parser
        return self._robots_cache[base]

    def _throttle(self, url: str) -> None:
        from urllib.parse import urlsplit

        host = urlsplit(url).netloc
        last = self._last_request_at.get(host)
        if last is not None:
            elapsed = time.monotonic() - last
            wait = self.min_delay_seconds - elapsed
            if wait > 0:
                time.sleep(wait)
        self._last_request_at[host] = time.monotonic()

    def fetch(self, url: str, timeout: float = 15.0) -> str:
        robots = self._robots_for(url)
        if not robots.can_fetch(self.user_agent, url):
            raise RobotsDisallowed(f"robots.txt interdit l'acces a {url} pour {self.user_agent}")

        self._throttle(url)
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
