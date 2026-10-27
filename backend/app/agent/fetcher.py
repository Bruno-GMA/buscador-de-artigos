import logging
import re
import time
import html
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import requests
from ddgs import DDGS
from app.config import settings
from app.agent.publication import fetch_web_publication_date, parse_publication_date

logger = logging.getLogger(__name__)

TOPICS = {
    "SLM": '(all:"small language model" OR all:"small language models")',
    "RAG": '(all:"retrieval augmented generation" OR all:"retrieval-augmented generation")',
    "EdTech": '(all:"artificial intelligence in education" OR all:"educational technology")',
}
WEB_QUERIES = {
    "SLM": 'small language models research paper',
    "RAG": 'retrieval augmented generation research paper',
    "EdTech": 'AI in education research paper',
}
ATOM = {"a": "http://www.w3.org/2005/Atom"}
_last_arxiv_request = 0.0


@dataclass(frozen=True)
class Candidate:
    title: str
    authors: str
    abstract: str
    url: str
    source: str
    category_hint: str
    published_at: datetime | None = None


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def fetch_arxiv(topic: str, limit: int) -> list[Candidate]:
    global _last_arxiv_request
    wait = 3.1 - (time.monotonic() - _last_arxiv_request)
    if wait > 0:
        time.sleep(wait)
    _last_arxiv_request = time.monotonic()
    response = requests.get(
        "https://export.arxiv.org/api/query",
        params={"search_query": TOPICS[topic], "start": 0, "max_results": limit, "sortBy": "submittedDate", "sortOrder": "descending"},
        headers={"User-Agent": "AcademicPulseAI/1.0 (portfolio research digest)"},
        timeout=25,
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    found = []
    for entry in root.findall("a:entry", ATOM):
        title = " ".join((entry.findtext("a:title", default="", namespaces=ATOM)).split())
        abstract = " ".join((entry.findtext("a:summary", default="", namespaces=ATOM)).split())
        url = normalize_url(entry.findtext("a:id", default="", namespaces=ATOM))
        authors = ", ".join(a.findtext("a:name", default="", namespaces=ATOM) for a in entry.findall("a:author", ATOM))
        published_raw = entry.findtext("a:published", default="", namespaces=ATOM)
        published = datetime.fromisoformat(published_raw.replace("Z", "+00:00")) if published_raw else None
        if title and abstract and url:
            found.append(Candidate(title, authors, abstract, url, "arXiv", topic, published))
    return found


def fetch_web(topic: str, domain: str, limit: int) -> list[Candidate]:
    results = DDGS(timeout=15).text(f"site:{domain} {WEB_QUERIES[topic]}", max_results=limit, timelimit="m", backend="duckduckgo")
    found = []
    for item in results:
        url = normalize_url(item.get("href", ""))
        host = urlsplit(url).hostname or ""
        if host != domain and not host.endswith("." + domain):
            continue
        if urlsplit(url).netloc in {"ieeexplore.ieee.org", "dl.acm.org"}:
            continue
        title = re.sub(r"\s+", " ", item.get("title", "")).strip()
        snippet = re.sub(r"\s+", " ", item.get("body", "")).strip()
        if url and title and snippet:
            published = fetch_web_publication_date(url, domain)
            if published:
                found.append(Candidate(title, "Não informado", snippet, url, "Web", topic, published))
    return found


def fetch_acm(topic: str, limit: int) -> list[Candidate]:
    """Metadados de trabalhos ACM registrados sob o prefixo DOI 10.1145 no Crossref."""
    response = requests.get(
        "https://api.crossref.org/prefixes/10.1145/works",
        params={"query.bibliographic": WEB_QUERIES[topic], "rows": limit, "sort": "published", "order": "desc"},
        headers={"User-Agent": "AcademicPulseAI/1.0 (research digest; contact: local installation)"},
        timeout=25,
    )
    response.raise_for_status()
    found = []
    for item in response.json().get("message", {}).get("items", []):
        licenses = [entry.get("URL", "").lower() for entry in item.get("license", [])]
        if not any("creativecommons.org/licenses/" in url or "creativecommons.org/publicdomain/" in url for url in licenses):
            continue
        title = " ".join(item.get("title", []))
        abstract = html.unescape(re.sub(r"<[^>]+>", " ", item.get("abstract", "")))
        abstract = " ".join(abstract.split())
        doi = item.get("DOI", "")
        url = normalize_url(f"https://doi.org/{doi}") if doi else ""
        authors = ", ".join(" ".join(filter(None, [person.get("given"), person.get("family")])) for person in item.get("author", []))
        parts = item.get("published", {}).get("date-parts", [[]])[0]
        published = datetime(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1) if parts else None
        if title and abstract and url:
            found.append(Candidate(title, authors, abstract, url, "ACM", topic, published))
    return found


def fetch_ieee(topic: str, limit: int) -> list[Candidate]:
    """Ativa somente com chave e autorização explícita para síntese por IA."""
    if not settings.ieee_api_key or not settings.ieee_ai_permission_granted:
        return []
    response = requests.get(
        "https://ieeexploreapi.ieee.org/api/v1/search/articles",
        params={"apikey": settings.ieee_api_key, "querytext": WEB_QUERIES[topic], "max_records": limit},
        timeout=25,
    )
    response.raise_for_status()
    found = []
    for item in response.json().get("articles", []):
        title = " ".join(item.get("title", "").split())
        abstract = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", item.get("abstract", ""))).split())
        doi = item.get("doi")
        url = normalize_url(item.get("abstract_url", "") or (f"https://doi.org/{doi}" if doi else ""))
        author_list = item.get("authors", {}).get("authors", [])
        authors = ", ".join(author.get("full_name", "") for author in author_list)
        published = parse_publication_date(item.get("publication_date"))
        if not published and item.get("publication_year"):
            published = parse_publication_date(str(item["publication_year"]))
        if title and abstract and url and published:
            found.append(Candidate(title, authors, abstract, url, "IEEE", topic, published))
    return found


def _published_after(candidate: Candidate, first_run_date: date) -> bool:
    if candidate.published_at is None:
        return False
    published = candidate.published_at
    if published.tzinfo is not None:
        published = published.astimezone(ZoneInfo(settings.timezone))
    publication_date = published.date()
    return first_run_date < publication_date <= datetime.now(ZoneInfo(settings.timezone)).date()


def fetch_candidates(limit: int, first_run_date: date, sources: list[str], topics: list[str], web_domains: list[str]) -> list[Candidate]:
    per_source = max(2, limit // max(1, len(sources) * len(topics)))
    buckets: dict[str, list[Candidate]] = {name: [] for name in ("arXiv", "ACM", "IEEE", "Web")}
    fetches = {"arxiv": fetch_arxiv, "acm": fetch_acm, "ieee": fetch_ieee}
    for topic in topics:
        for source in sources:
            if source == "web":
                for domain in web_domains:
                    try:
                        buckets["Web"].extend(candidate for candidate in fetch_web(topic, domain, 5) if _published_after(candidate, first_run_date))
                    except Exception:
                        logger.exception("Falha ao buscar %s em %s", topic, domain)
                continue
            fetch = fetches[source]
            try:
                for candidate in fetch(topic, max(10, per_source * 4)):
                    if _published_after(candidate, first_run_date):
                        buckets[candidate.source].append(candidate)
            except Exception:
                logger.exception("Falha ao buscar %s em %s", topic, fetch.__name__)
    unique: dict[str, Candidate] = {}
    while any(buckets.values()) and len(unique) < limit:
        for bucket in buckets.values():
            if bucket:
                item = bucket.pop(0)
                unique.setdefault(item.url, item)
            if len(unique) >= limit:
                break
    return list(unique.values())[:limit]

