"""
Extended main.py for zotero-arxiv-daily with PubMed/bioRxiv/medRxiv support.

This replaces the original main.py. It adds biomed paper sources while
keeping full backward compatibility with the original arXiv-only workflow.

New environment variables:
    PUBMED_QUERY       - PubMed search query (MeSH terms supported)
    BIORXIV_CATEGORIES - bioRxiv categories, "+" separated
    BIORXIV_KEYWORDS   - bioRxiv keyword filter, "+" separated
    MEDRXIV_KEYWORDS   - medRxiv keyword filter, "+" separated
    NCBI_API_KEY       - Optional NCBI API key for higher rate limits
    FETCH_DAYS         - Number of days to look back (default: 1)
"""

import os
import sys
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_zotero_corpus():
    """Retrieve papers from user's Zotero library."""
    from pyzotero import zotero
    import pathspec

    zotero_id = os.environ["ZOTERO_ID"]
    zotero_key = os.environ["ZOTERO_KEY"]
    zot = zotero.Zotero(zotero_id, "user", zotero_key)

    # Get all items
    items = zot.everything(zot.top())

    # Apply ignore patterns if set
    ignore_patterns = os.environ.get("ZOTERO_IGNORE", "")
    if ignore_patterns:
        spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns.strip().split("\n"))
    else:
        spec = None

    # Get collections for path-based filtering
    collections = {}
    for col in zot.everything(zot.collections()):
        collections[col["key"]] = col["data"].get("name", "")

    corpus = []
    for item in items:
        data = item.get("data", {})
        item_type = data.get("itemType", "")
        if item_type in ("attachment", "note"):
            continue

        title = data.get("title", "")
        abstract = data.get("abstractNote", "")
        if not title and not abstract:
            continue

        # Check ignore patterns
        if spec:
            item_collections = data.get("collections", [])
            col_names = [collections.get(c, "") for c in item_collections]
            if any(spec.match_file(name + "/") for name in col_names if name):
                continue

        # Use dateAdded for weighting (newer = more relevant)
        date_added = data.get("dateAdded", "2020-01-01")

        corpus.append({
            "title": title,
            "abstract": abstract,
            "date_added": date_added,
        })

    logger.info(f"Loaded {len(corpus)} papers from Zotero library")
    return corpus


def get_arxiv_papers(test_mode: bool = False):
    """Fetch arXiv papers (original functionality)."""
    import arxiv
    from paper import ArxivPaper

    query = os.environ.get("ARXIV_QUERY", "")
    if not query:
        logger.info("No ARXIV_QUERY set, skipping arXiv")
        return []

    categories = query.replace("+", " OR ").split()
    cat_query = " OR ".join(f"cat:{c}" for c in query.split("+"))

    if test_mode:
        search = arxiv.Search(
            query=cat_query,
            max_results=5,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
    else:
        # Fetch papers from yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        today = datetime.now().strftime("%Y%m%d")
        date_query = f"submittedDate:[{yesterday}0000 TO {today}0000]"
        full_query = f"({cat_query}) AND {date_query}"
        search = arxiv.Search(
            query=full_query,
            max_results=500,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

    papers = []
    try:
        for result in search.results():
            papers.append(ArxivPaper(result))
    except Exception as e:
        logger.error(f"arXiv fetch failed: {e}")
        # Fallback: use Atom feed approach
        try:
            client = arxiv.Client()
            for result in client.results(search):
                papers.append(ArxivPaper(result))
        except Exception as e2:
            logger.error(f"arXiv fallback also failed: {e2}")

    logger.info(f"Fetched {len(papers)} papers from arXiv")
    return papers


def get_biomed_papers(test_mode: bool = False):
    """Fetch papers from PubMed, bioRxiv, and medRxiv."""
    from biomed_fetcher import fetch_all_biomed_papers

    pubmed_query = os.environ.get("PUBMED_QUERY", "")
    biorxiv_cats = os.environ.get("BIORXIV_CATEGORIES", "")
    biorxiv_kw = os.environ.get("BIORXIV_KEYWORDS", "")
    medrxiv_kw = os.environ.get("MEDRXIV_KEYWORDS", "")
    ncbi_key = os.environ.get("NCBI_API_KEY", "")
    fetch_days = int(os.environ.get("FETCH_DAYS", "1"))

    # Check if any biomed source is configured
    if not any([pubmed_query, biorxiv_cats, biorxiv_kw, medrxiv_kw]):
        logger.info("No biomed sources configured, skipping")
        return []

    biorxiv_categories = biorxiv_cats.split("+") if biorxiv_cats else None
    biorxiv_keywords = biorxiv_kw.split("+") if biorxiv_kw else None
    medrxiv_keywords = medrxiv_kw.split("+") if medrxiv_kw else None

    if test_mode:
        fetch_days = 7  # Wider window for testing
        max_per = 10
    else:
        max_per = int(os.environ.get("MAX_PAPER_NUM", "50"))

    papers = fetch_all_biomed_papers(
        pubmed_query=pubmed_query,
        biorxiv_categories=biorxiv_categories,
        biorxiv_keywords=biorxiv_keywords,
        medrxiv_keywords=medrxiv_keywords,
        days=fetch_days,
        max_per_source=max_per,
        ncbi_api_key=ncbi_key or None,
    )

    return papers


def rerank_all_papers(arxiv_papers, biomed_papers, corpus):
    """
    Rerank all papers using the existing recommendation engine.
    Both ArxivPaper and BiomedPaper have .summary for embedding.
    """
    from recommender import rerank_paper

    all_candidates = arxiv_papers + biomed_papers

    if not all_candidates:
        logger.warning("No candidate papers to rank")
        return []

    if not corpus:
        logger.warning("Empty Zotero corpus, returning papers unranked")
        return all_candidates

    # rerank_paper expects objects with .summary attribute
    # Both ArxivPaper and BiomedPaper provide this
    ranked = rerank_paper(all_candidates, corpus)

    max_num = int(os.environ.get("MAX_PAPER_NUM", "50"))
    if max_num > 0:
        ranked = ranked[:max_num]

    return ranked


def construct_and_send_email(ranked_papers):
    """Build and send the email with paper recommendations."""
    from construct_email_extended import construct_email_html
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    if not ranked_papers:
        send_empty = os.environ.get("SEND_EMPTY", "False").lower() in ("true", "1")
        if not send_empty:
            logger.info("No papers to send and SEND_EMPTY is False")
            return
        html = "<h2>No new papers found today</h2>"
    else:
        html = construct_email_html(ranked_papers)

    # Email setup
    smtp_server = os.environ["SMTP_SERVER"]
    smtp_port = int(os.environ["SMTP_PORT"])
    sender = os.environ["SENDER"]
    password = os.environ["SENDER_PASSWORD"]
    receiver = os.environ["RECEIVER"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📚 Daily Paper Recommendations - {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        logger.info(f"Email sent to {receiver}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise


def main():
    test_mode = "--test" in sys.argv or os.environ.get("TEST_MODE", "") == "1"

    logger.info("=" * 60)
    logger.info("Zotero Paper Daily - Extended Edition")
    logger.info(f"Mode: {'TEST' if test_mode else 'PRODUCTION'}")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 1. Load Zotero corpus
    corpus = get_zotero_corpus()

    # 2. Fetch papers from all sources
    arxiv_papers = get_arxiv_papers(test_mode)
    biomed_papers = get_biomed_papers(test_mode)

    total = len(arxiv_papers) + len(biomed_papers)
    logger.info(f"Total candidate papers: {total} "
                f"(arXiv: {len(arxiv_papers)}, "
                f"biomed: {len(biomed_papers)})")

    if total == 0:
        logger.info("No new papers found")
        construct_and_send_email([])
        return

    # 3. Rerank
    ranked = rerank_all_papers(arxiv_papers, biomed_papers, corpus)
    logger.info(f"Top {len(ranked)} papers after ranking")

    # 4. Send email
    construct_and_send_email(ranked)

    logger.info("Done!")


if __name__ == "__main__":
    main()
