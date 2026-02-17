"""
Fetcher module for PubMed, bioRxiv, and medRxiv papers.

Provides functions to retrieve recent papers from each source,
returning BiomedPaper objects compatible with the existing pipeline.
"""

import os
import re
import time
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from biomed_paper import BiomedPaper

logger = logging.getLogger(__name__)

# ============================================================
# bioRxiv / medRxiv Fetcher
# ============================================================

def fetch_biorxiv_papers(
    days: int = 1,
    server: str = "biorxiv",
    categories: list[str] | None = None,
    keywords: list[str] | None = None,
    max_results: int = 200,
) -> list[BiomedPaper]:
    """
    Fetch recent papers from bioRxiv or medRxiv API.

    Args:
        days: Number of past days to fetch.
        server: "biorxiv" or "medrxiv".
        categories: Optional list of bioRxiv categories to filter
                    (e.g., ["cell_biology", "immunology", "dermatology"]).
        keywords: Optional list of keywords to filter titles/abstracts.
        max_results: Maximum number of papers to return.

    Returns:
        List of BiomedPaper objects.
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    papers = []
    cursor = 0
    base_url = f"https://api.biorxiv.org/details/{server}/{start_date}/{end_date}"

    while len(papers) < max_results:
        url = f"{base_url}/{cursor}"
        try:
            logger.info(f"Fetching {server} papers: {url}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch from {server}: {e}")
            break

        collection = data.get("collection", [])
        if not collection:
            break

        for item in collection:
            # Category filter
            if categories:
                item_cat = item.get("category", "").lower().replace(" ", "_")
                if not any(c.lower().replace(" ", "_") in item_cat for c in categories):
                    continue

            # Keyword filter on title + abstract
            if keywords:
                text = (item.get("title", "") + " " + item.get("abstract", "")).lower()
                if not any(kw.lower() in text for kw in keywords):
                    continue

            paper_data = {
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "authors": item.get("authors", ""),
                "doi": item.get("doi", ""),
                "date": item.get("date", ""),
                "journal": server,
                "affiliations_raw": [
                    item.get("author_corresponding_institution", "")
                ] if item.get("author_corresponding_institution") else [],
                "pdf_url": "",  # Will be constructed by BiomedPaper
            }
            papers.append(BiomedPaper(paper_data, source=server))

            if len(papers) >= max_results:
                break

        # Pagination: bioRxiv returns 100 per page
        cursor += 100
        total = data.get("messages", [{}])[0].get("total", 0)
        if cursor >= total:
            break

        time.sleep(1)  # Be respectful to the API

    logger.info(f"Fetched {len(papers)} papers from {server}")
    return papers


# ============================================================
# PubMed Fetcher (E-utilities API)
# ============================================================

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def fetch_pubmed_papers(
    query: str,
    days: int = 1,
    max_results: int = 100,
    api_key: str | None = None,
) -> list[BiomedPaper]:
    """
    Fetch recent papers from PubMed using E-utilities.

    Args:
        query: PubMed search query string (supports MeSH terms).
                Example: '("skin diseases"[MeSH] OR "dermatology"[MeSH])'
        days: Number of past days to search.
        max_results: Maximum number of papers to return.
        api_key: Optional NCBI API key for higher rate limits.

    Returns:
        List of BiomedPaper objects.
    """
    # Step 1: Search for PMIDs
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "date",
        "datetype": "edat",  # Entrez date (when added to PubMed)
        "reldate": days,     # Papers from last N days
    }
    if api_key:
        search_params["api_key"] = api_key

    try:
        logger.info(f"Searching PubMed: {query} (last {days} days)")
        resp = requests.get(PUBMED_SEARCH_URL, params=search_params, timeout=30)
        resp.raise_for_status()
        search_data = resp.json()
    except Exception as e:
        logger.error(f"PubMed search failed: {e}")
        return []

    pmids = search_data.get("esearchresult", {}).get("idlist", [])
    if not pmids:
        logger.info("No PubMed papers found for the query")
        return []

    logger.info(f"Found {len(pmids)} PubMed IDs, fetching details...")

    # Step 2: Fetch paper details in batches
    papers = []
    batch_size = 50

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
            "rettype": "abstract",
        }
        if api_key:
            fetch_params["api_key"] = api_key

        try:
            resp = requests.get(PUBMED_FETCH_URL, params=fetch_params, timeout=30)
            resp.raise_for_status()
            papers.extend(_parse_pubmed_xml(resp.text))
        except Exception as e:
            logger.error(f"PubMed fetch failed for batch {i}: {e}")
            continue

        time.sleep(0.4)  # NCBI rate limit: 3 requests/sec without key

    logger.info(f"Fetched {len(papers)} papers from PubMed")
    return papers


def _parse_pubmed_xml(xml_text: str) -> list[BiomedPaper]:
    """Parse PubMed XML response into BiomedPaper objects."""
    papers = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"Failed to parse PubMed XML: {e}")
        return papers

    for article in root.findall(".//PubmedArticle"):
        try:
            # PMID
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            # Title
            title_el = article.find(".//ArticleTitle")
            title = _get_text(title_el)

            # Abstract
            abstract_parts = []
            for abs_text in article.findall(".//AbstractText"):
                label = abs_text.get("Label", "")
                text = _get_text(abs_text)
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)

            # Authors
            authors = []
            for author in article.findall(".//Author"):
                last = author.find("LastName")
                fore = author.find("ForeName")
                if last is not None and fore is not None:
                    authors.append(f"{fore.text} {last.text}")
                elif last is not None:
                    authors.append(last.text)

            # DOI
            doi = ""
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text or ""
                    break

            # Journal
            journal_el = article.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else ""

            # Date
            date_el = article.find(".//PubDate")
            date_str = ""
            if date_el is not None:
                year = date_el.find("Year")
                month = date_el.find("Month")
                day = date_el.find("Day")
                parts = []
                if year is not None:
                    parts.append(year.text)
                if month is not None:
                    parts.append(month.text)
                if day is not None:
                    parts.append(day.text)
                date_str = "-".join(parts)

            # Affiliations
            affiliations = []
            for aff in article.findall(".//AffiliationInfo/Affiliation"):
                if aff.text:
                    affiliations.append(aff.text.strip())

            # PDF URL - PubMed Central if available
            pmc_id = ""
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "pmc":
                    pmc_id = id_el.text or ""
                    break
            pdf_url = ""
            if pmc_id:
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"
            elif doi:
                pdf_url = f"https://doi.org/{doi}"

            if not title or not abstract:
                continue

            paper_data = {
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "doi": doi,
                "pmid": pmid,
                "date": date_str,
                "journal": journal,
                "affiliations_raw": affiliations,
                "pdf_url": pdf_url,
            }
            papers.append(BiomedPaper(paper_data, source="pubmed"))

        except Exception as e:
            logger.debug(f"Failed to parse a PubMed article: {e}")
            continue

    return papers


def _get_text(element) -> str:
    """Get all text content from an XML element, including mixed content."""
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


# ============================================================
# Combined Fetcher
# ============================================================

def fetch_all_biomed_papers(
    pubmed_query: str | None = None,
    biorxiv_categories: list[str] | None = None,
    biorxiv_keywords: list[str] | None = None,
    medrxiv_keywords: list[str] | None = None,
    days: int = 1,
    max_per_source: int = 100,
    ncbi_api_key: str | None = None,
) -> list[BiomedPaper]:
    """
    Fetch papers from all biomed sources.

    Returns combined, deduplicated list of BiomedPaper objects.
    """
    all_papers = []

    # PubMed
    if pubmed_query:
        papers = fetch_pubmed_papers(
            query=pubmed_query,
            days=days,
            max_results=max_per_source,
            api_key=ncbi_api_key,
        )
        all_papers.extend(papers)

    # bioRxiv
    if biorxiv_categories or biorxiv_keywords:
        papers = fetch_biorxiv_papers(
            days=days,
            server="biorxiv",
            categories=biorxiv_categories,
            keywords=biorxiv_keywords,
            max_results=max_per_source,
        )
        all_papers.extend(papers)

    # medRxiv
    if medrxiv_keywords:
        papers = fetch_biorxiv_papers(
            days=days,
            server="medrxiv",
            categories=None,
            keywords=medrxiv_keywords,
            max_results=max_per_source,
        )
        all_papers.extend(papers)

    # Deduplicate by DOI
    seen_dois = set()
    unique_papers = []
    for p in all_papers:
        key = p.doi if p.doi else p.title.lower().strip()
        if key not in seen_dois:
            seen_dois.add(key)
            unique_papers.append(p)

    logger.info(f"Total unique biomed papers: {len(unique_papers)}")
    return unique_papers
