import logging
import re
import time
import html
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

import requests
from ddgs import DDGS
from app.config import settings

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


def fetch_web(topic: str, limit: int) -> list[Candidate]:
    results = DDGS(timeout=15).text(WEB_QUERIES[topic], max_results=limit, timelimit="w", backend="duckduckgo")
    found = []
    for item in results:
        url = normalize_url(item.get("href", ""))
        if urlsplit(url).netloc in {"ieeexplore.ieee.org", "dl.acm.org"}:
            continue
        title = re.sub(r"\s+", " ", item.get("title", "")).strip()
        snippet = re.sub(r"\s+", " ", item.get("body", "")).strip()
        if url and title and snippet:
            found.append(Candidate(title, "Não informado", snippet, url, "Web", topic))
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
        if title and abstract and url:
            found.append(Candidate(title, authors, abstract, url, "IEEE", topic))
    return found


def _parse_ris(path: Path) -> list[dict[str, list[str]]]:
    records: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] = {}
    last_key = ""
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if len(line) < 6 or line[2:6] != "  - ":
            if last_key and line.strip() and current.get(last_key):
                current[last_key][-1] += " " + line.strip()
            continue
        key, value = line[:2], line[6:].strip()
        if key == "TY":
            current = {}
            last_key = ""
        elif key == "ER":
            if current:
                records.append(current)
            current = {}
            last_key = ""
        elif value:
            current.setdefault(key, []).append(value)
            last_key = key
    if current:
        records.append(current)
    return records


def fetch_capes_imports(limit: int) -> list[Candidate]:
    """Lê exportações RIS colocadas pelo usuário a partir do Portal CAPES."""
    folder = Path(settings.capes_import_dir)
    if not folder.is_dir():
        return []
    found = []
    for path in sorted(folder.glob("*.ris"), key=lambda p: p.stat().st_mtime, reverse=True):
        for record in _parse_ris(path):
            title = (record.get("TI") or record.get("T1") or [""])[0]
            abstract = " ".join(record.get("AB") or record.get("N2") or [])
            doi = (record.get("DO") or [""])[0]
            doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
            if doi.lower().startswith(("10.1109/", "10.1145/")):
                continue
            url = normalize_url(f"https://doi.org/{doi}" if doi else (record.get("UR") or [""])[0])
            authors = ", ".join(record.get("AU", []))
            year_raw = (record.get("PY") or record.get("Y1") or [""])[0][:4]
            published = datetime(int(year_raw), 1, 1) if year_raw.isdigit() else None
            if title and abstract and url:
                found.append(Candidate(title, authors, abstract, url, "CAPES", "EdTech", published))
            if len(found) >= limit:
                return found
    return found


def fetch_capes_feeds(limit: int) -> list[Candidate]:
    """Lê feeds RSS/Atom de alertas obtidos legalmente em bases acessadas via CAPES."""
    found = []
    for feed_url in filter(None, (part.strip() for part in settings.capes_rss_urls.split(","))):
        if not feed_url.startswith("https://"):
            logger.warning("Feed CAPES ignorado: URL deve usar HTTPS")
            continue
        try:
            response = requests.get(feed_url, timeout=20)
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
            items = root.findall(".//item") or root.findall("a:entry", ATOM)
            for item in items[:limit]:
                is_atom = item.tag.endswith("entry")
                title = item.findtext("a:title", default="", namespaces=ATOM) if is_atom else item.findtext("title", default="")
                abstract = item.findtext("a:summary", default="", namespaces=ATOM) if is_atom else item.findtext("description", default="")
                if is_atom:
                    link_node = item.find("a:link", ATOM)
                    link = link_node.get("href", "") if link_node is not None else ""
                else:
                    link = item.findtext("link", default="")
                abstract = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", abstract)).split())
                url = normalize_url(link)
                if urlsplit(url).netloc in {"ieeexplore.ieee.org", "dl.acm.org"} or urlsplit(url).path.lower().startswith(("/10.1109/", "/10.1145/")):
                    continue
                if title and abstract and url:
                    found.append(Candidate(" ".join(title.split()), "Não informado", abstract, url, "CAPES", "EdTech"))
        except Exception:
            logger.exception("Falha ao ler feed de alerta CAPES")
    return found[:limit]


def fetch_candidates(limit: int) -> list[Candidate]:
    per_source = max(1, limit // 6)
    buckets: dict[str, list[Candidate]] = {name: [] for name in ("CAPES", "arXiv", "ACM", "IEEE", "Web")}
    for topic in TOPICS:
        for fetch, count in ((fetch_arxiv, per_source), (fetch_acm, per_source), (fetch_ieee, per_source), (fetch_web, 1)):
            try:
                for candidate in fetch(topic, count):
                    buckets[candidate.source].append(candidate)
            except Exception:
                logger.exception("Falha ao buscar %s em %s", topic, fetch.__name__)
    for fetch in (fetch_capes_imports, fetch_capes_feeds):
        try:
            buckets["CAPES"].extend(fetch(max(1, limit // 3)))
        except Exception:
            logger.exception("Falha ao buscar em %s", fetch.__name__)
    unique: dict[str, Candidate] = {}
    while any(buckets.values()) and len(unique) < limit:
        for bucket in buckets.values():
            if bucket:
                item = bucket.pop(0)
                unique.setdefault(item.url, item)
            if len(unique) >= limit:
                break
    return list(unique.values())[:limit]

