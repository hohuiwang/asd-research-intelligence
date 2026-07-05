from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from .config import APP_EMAIL, PUBMED_BASE_URL
from .journals import high_impact_journal_query
from .models import Paper


AUTISM_QUERY = (
    '("Autism Spectrum Disorder"[MeSH Terms] OR '
    '"autism spectrum disorder"[Title/Abstract] OR '
    'autism[Title/Abstract] OR autistic[Title/Abstract] OR '
    'ASD[Title/Abstract] OR "pervasive developmental disorder"[Title/Abstract])'
)

UNDER_25_QUERY = (
    '(infant[Title/Abstract] OR infants[Title/Abstract] OR toddler[Title/Abstract] OR '
    'toddlers[Title/Abstract] OR preschool[Title/Abstract] OR child[Title/Abstract] OR '
    'children[Title/Abstract] OR adolescent[Title/Abstract] OR adolescents[Title/Abstract] OR '
    'youth[Title/Abstract] OR teen[Title/Abstract] OR teens[Title/Abstract] OR '
    '"young adult"[Title/Abstract] OR "young adults"[Title/Abstract] OR '
    'pediatric[Title/Abstract] OR paediatric[Title/Abstract] OR "under 25"[Title/Abstract] OR '
    '"0-25"[Title/Abstract] OR "Child"[MeSH Terms] OR "Adolescent"[MeSH Terms] OR '
    '"Young Adult"[MeSH Terms])'
)

ADULT_COMPANION_QUERY = (
    '(adult[Title/Abstract] OR adults[Title/Abstract] OR adulthood[Title/Abstract] OR '
    'aging[Title/Abstract] OR ageing[Title/Abstract] OR lifespan[Title/Abstract] OR '
    '"transition age"[Title/Abstract] OR "transition-age"[Title/Abstract] OR '
    'employment[Title/Abstract] OR "independent living"[Title/Abstract] OR '
    '"Adult"[MeSH Terms])'
)

EXCLUDED_PUBLICATION_TYPES = (
    "Editorial",
    "Letter",
    "Comment",
    "Case Reports",
    "News",
)


def build_search_query(
    days: int = 7,
    journal_scope: str = "high-impact",
    population_scope: str = "priority",
) -> str:
    if journal_scope not in {"high-impact", "broad"}:
        raise ValueError("journal_scope must be 'high-impact' or 'broad'")
    if population_scope not in {"priority", "all"}:
        raise ValueError("population_scope must be 'priority' or 'all'")

    today = date.today()
    start = today - timedelta(days=days)
    date_query = f'("{start.isoformat()}"[Date - Publication] : "{today.isoformat()}"[Date - Publication])'
    exclusion_query = "".join(f' NOT "{pt}"[Publication Type]' for pt in EXCLUDED_PUBLICATION_TYPES)

    parts = [AUTISM_QUERY, date_query]
    if population_scope == "priority":
        parts.append(f"({UNDER_25_QUERY} OR {ADULT_COMPANION_QUERY})")
    if journal_scope == "high-impact":
        parts.append(high_impact_journal_query())

    return " AND ".join(parts) + exclusion_query


def search_pubmed(
    days: int = 7,
    max_results: int = 100,
    journal_scope: str = "high-impact",
    population_scope: str = "priority",
) -> list[str]:
    query = build_search_query(
        days=days,
        journal_scope=journal_scope,
        population_scope=population_scope,
    )

    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(max_results),
        "sort": "pub+date",
        "tool": "autism_research_agent",
        "email": APP_EMAIL,
    }
    url = f"{PUBMED_BASE_URL}/esearch.fcgi"
    data = _get_json(url, params=params)
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_pubmed_details(pmids: list[str]) -> list[Paper]:
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "tool": "autism_research_agent",
        "email": APP_EMAIL,
    }
    url = f"{PUBMED_BASE_URL}/efetch.fcgi"
    xml_text = _get_text(url, params=params)
    root = ET.fromstring(xml_text)
    return [_parse_article(article) for article in root.findall(".//PubmedArticle")]


def fetch_recent_papers(
    days: int = 7,
    max_results: int = 100,
    journal_scope: str = "high-impact",
    population_scope: str = "priority",
) -> list[Paper]:
    pmids = search_pubmed(
        days=days,
        max_results=max_results,
        journal_scope=journal_scope,
        population_scope=population_scope,
    )
    time.sleep(0.35)
    return fetch_pubmed_details(pmids)


def _parse_article(article: ET.Element) -> Paper:
    pmid = _text(article, ".//PMID")
    title = " ".join(_text(article, ".//ArticleTitle").split())
    abstract_parts = [node.text or "" for node in article.findall(".//Abstract/AbstractText")]
    abstract = "\n".join(part.strip() for part in abstract_parts if part.strip())
    journal = _text(article, ".//Journal/Title") or _text(article, ".//MedlineTA")
    publication_date = _publication_date(article)
    doi = _doi(article)
    authors = tuple(_authors(article))
    publication_types = tuple(
        node.text or "" for node in article.findall(".//PublicationTypeList/PublicationType")
    )

    return Paper(
        pmid=pmid,
        title=title,
        abstract=abstract,
        journal=journal,
        publication_date=publication_date,
        doi=doi,
        authors=authors,
        publication_types=publication_types,
    )


def _publication_date(article: ET.Element) -> str:
    pub_date = article.find(".//JournalIssue/PubDate")
    if pub_date is None:
        return ""

    year = _child_text(pub_date, "Year") or "0000"
    month = _child_text(pub_date, "Month") or "01"
    day = _child_text(pub_date, "Day") or "01"
    return f"{year}-{_normalize_month(month)}-{day.zfill(2)}"


def _normalize_month(month: str) -> str:
    months = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }
    if month.isdigit():
        return month.zfill(2)
    return months.get(month[:3], "01")


def _doi(article: ET.Element) -> str | None:
    for article_id in article.findall(".//ArticleIdList/ArticleId"):
        if article_id.attrib.get("IdType") == "doi" and article_id.text:
            return article_id.text.strip()
    return None


def _authors(article: ET.Element) -> list[str]:
    names = []
    for author in article.findall(".//AuthorList/Author"):
        last = _child_text(author, "LastName")
        initials = _child_text(author, "Initials")
        collective = _child_text(author, "CollectiveName")
        if collective:
            names.append(collective)
        elif last:
            names.append(f"{last} {initials}".strip())
    return names


def _text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    return (node.text or "").strip() if node is not None else ""


def _child_text(root: ET.Element, child_name: str) -> str:
    node = root.find(child_name)
    return (node.text or "").strip() if node is not None else ""


def _get_json(url: str, params: dict[str, str] | None = None) -> dict:
    return json.loads(_get_text(url, params=params))


def _get_text(url: str, params: dict[str, str] | None = None) -> str:
    body = None
    headers = {"User-Agent": "autism-research-agent/0.1"}
    if params is not None:
        body = urllib.parse.urlencode(params).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise RuntimeError(
                "Python cannot verify HTTPS certificates. On macOS, run "
                "'/Applications/Python 3.14/Install Certificates.command' and retry. "
                "Do not disable SSL verification for this research tool."
            ) from exc
        raise
