"""Extrai datas de publicação declaradas pela fonte; ausência de data exclui o item."""

import logging
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit

import requests
from dateutil.parser import parse as parse_date

logger = logging.getLogger(__name__)
DATE_META = {
    "article:published_time", "datepublished", "pubdate", "citation_publication_date",
    "citation_date", "dc.date.issued",
}


def parse_publication_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        # Datas parciais recebem o primeiro dia possível, mantendo o filtro conservador.
        return parse_date(value, fuzzy=False, default=datetime(1900, 1, 1))
    except (TypeError, ValueError, OverflowError):
        return None


class PublicationMetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values: list[str] = []
        self.in_json_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "meta":
            name = (attributes.get("property") or attributes.get("name") or "").lower()
            if name in DATE_META and attributes.get("content"):
                self.values.append(attributes["content"] or "")
        elif tag == "script" and (attributes.get("type") or "").lower() == "application/ld+json":
            self.in_json_ld = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_json_ld = False

    def handle_data(self, data: str) -> None:
        if not self.in_json_ld:
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return
        def collect(value):
            if isinstance(value, dict):
                if isinstance(value.get("datePublished"), str):
                    self.values.append(value["datePublished"])
                for nested in value.values():
                    collect(nested)
            elif isinstance(value, list):
                for nested in value:
                    collect(nested)
        collect(payload)


def fetch_web_publication_date(url: str, allowed_domain: str) -> datetime | None:
    host = (urlsplit(url).hostname or "").lower()
    if not (host == allowed_domain or host.endswith("." + allowed_domain)):
        return None
    if urlsplit(url).scheme != "https":
        return None
    try:
        with requests.get(url, headers={"User-Agent": "AcademicPulseAI/1.0"}, timeout=12, allow_redirects=False, stream=True) as response:
            if response.status_code != 200 or "html" not in response.headers.get("Content-Type", "").lower():
                return None
            parser = PublicationMetaParser()
            parser.feed(response.raw.read(250_000, decode_content=True).decode("utf-8", errors="replace"))
            for raw in parser.values:
                parsed = parse_publication_date(raw)
                if parsed:
                    return parsed
    except (requests.RequestException, UnicodeError, ValueError) as exc:
        logger.debug("Data web indisponível para %s: %s", url, exc)
    return None
