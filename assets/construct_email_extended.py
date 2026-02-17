"""
Extended email construction that supports both ArxivPaper and BiomedPaper.

Backward compatible with the original construct_email.py while adding
source badges and biomed-specific fields (journal, PMID, DOI).
"""

import logging

logger = logging.getLogger(__name__)

# ============================================================
# Source badge colors
# ============================================================
SOURCE_COLORS = {
    "arxiv": "#b31b1b",     # arXiv red
    "pubmed": "#326599",    # PubMed blue
    "biorxiv": "#6b3a2a",   # bioRxiv brown
    "medrxiv": "#003366",   # medRxiv dark blue
}

SOURCE_LABELS = {
    "arxiv": "arXiv",
    "pubmed": "PubMed",
    "biorxiv": "bioRxiv",
    "medrxiv": "medRxiv",
}


def _get_source(paper) -> str:
    """Determine the source of a paper."""
    if hasattr(paper, "source"):
        return paper.source
    return "arxiv"


def _get_star_html(score: float) -> str:
    """Generate star rating HTML from score (0-1)."""
    full_star = '⭐'
    half_star = '✨'
    stars = score * 5
    full_star_num = int(stars)
    half_star_num = 1 if stars - full_star_num >= 0.5 else 0
    return full_star * full_star_num + half_star * half_star_num


def _get_source_badge(source: str) -> str:
    """Generate colored source badge HTML."""
    color = SOURCE_COLORS.get(source, "#666")
    label = SOURCE_LABELS.get(source, source)
    return (
        f'<span style="display:inline-block; background-color:{color}; '
        f'color:white; padding:2px 8px; border-radius:3px; '
        f'font-size:12px; font-weight:bold; margin-right:6px;">'
        f'{label}</span>'
    )


def get_paper_block_html(paper, rank: int) -> str:
    """
    Generate HTML block for a single paper.
    Works with both ArxivPaper and BiomedPaper.
    """
    source = _get_source(paper)
    title = paper.title
    authors = ", ".join(paper.authors[:5]) if isinstance(paper.authors, list) else str(paper.authors)
    if isinstance(paper.authors, list) and len(paper.authors) > 5:
        authors += f" et al. ({len(paper.authors)} authors)"

    score = getattr(paper, "score", 0)
    rate = _get_star_html(score) if score else ""

    # TL;DR
    try:
        tldr = paper.tldr
    except Exception:
        tldr = paper.summary[:300] + "..." if len(paper.summary) > 300 else paper.summary

    # Source badge
    badge = _get_source_badge(source)

    # Links section
    links_html = ""

    if source == "arxiv":
        arxiv_id = paper.arxiv_id
        links_html += f'<strong>arXiv:</strong> <a href="https://arxiv.org/abs/{arxiv_id}">{arxiv_id}</a> | '
        links_html += f'<a href="{paper.pdf_url}" style="display:inline-block;text-decoration:none;font-size:13px;font-weight:bold;color:#fff;background-color:#d9534f;padding:6px 12px;border-radius:4px;">PDF</a> '
    else:
        # BiomedPaper
        if hasattr(paper, "doi") and paper.doi:
            links_html += f'<strong>DOI:</strong> <a href="https://doi.org/{paper.doi}">{paper.doi}</a> | '
        if hasattr(paper, "_data") and paper._data.get("pmid"):
            pmid = paper._data["pmid"]
            links_html += f'<strong>PMID:</strong> <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/">{pmid}</a> | '
        if paper.pdf_url:
            links_html += f'<a href="{paper.pdf_url}" style="display:inline-block;text-decoration:none;font-size:13px;font-weight:bold;color:#fff;background-color:#d9534f;padding:6px 12px;border-radius:4px;">PDF</a> '

    # Code link (mostly for arXiv papers)
    code_url = getattr(paper, "code_url", None)
    if code_url:
        links_html += f'<a href="{code_url}" style="display:inline-block;text-decoration:none;font-size:13px;font-weight:bold;color:#fff;background-color:#5bc0de;padding:6px 12px;border-radius:4px;margin-left:6px;">Code</a> '

    # Affiliations
    affiliations_html = ""
    affiliations = getattr(paper, "affiliations", None)
    if affiliations:
        if isinstance(affiliations, (list, set)):
            aff_str = " · ".join(str(a) for a in affiliations)
        else:
            aff_str = str(affiliations)
        affiliations_html = f'<div style="color:#888;font-size:12px;margin-top:6px;">🏛 {aff_str}</div>'

    # Journal info (for biomed papers)
    journal_html = ""
    if source != "arxiv":
        journal = getattr(paper, "journal", "")
        date = getattr(paper, "date", "")
        if journal or date:
            parts = [p for p in [journal, date] if p]
            journal_html = f'<div style="color:#666;font-size:12px;margin-top:4px;">📖 {" · ".join(parts)}</div>'

    return f"""
    <table border="0" cellpadding="0" cellspacing="0" width="100%"
           style="font-family:Arial,sans-serif; border:1px solid #ddd;
                  border-radius:8px; padding:16px; background-color:#f9f9f9;
                  margin-bottom:16px;">
        <tr>
            <td>
                <div style="margin-bottom:8px;">
                    {badge}
                    <span style="font-size:12px;color:#999;">#{rank}</span>
                    <span style="float:right;">{rate}</span>
                </div>
                <div style="font-size:17px;font-weight:bold;color:#333;margin-bottom:8px;">
                    {title}
                </div>
                <div style="font-size:13px;color:#666;margin-bottom:8px;">
                    {authors}
                </div>
                {journal_html}
                {affiliations_html}
                <div style="font-size:14px;color:#444;margin:12px 0;
                            padding:10px;background:#fff;border-radius:6px;
                            border-left:3px solid {SOURCE_COLORS.get(source, '#666')};">
                    <strong>TL;DR:</strong> {tldr}
                </div>
                <div style="margin-top:8px;">
                    {links_html}
                </div>
            </td>
        </tr>
    </table>
    """


def construct_email_html(papers: list) -> str:
    """
    Construct the full email HTML from a list of ranked papers.
    """
    from datetime import datetime

    # Count by source
    source_counts = {}
    for p in papers:
        src = _get_source(p)
        source_counts[src] = source_counts.get(src, 0) + 1

    source_summary = " · ".join(
        f"{SOURCE_LABELS.get(s, s)}: {c}"
        for s, c in sorted(source_counts.items())
    )

    # Header
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;">

    <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                color:white;padding:24px;border-radius:12px;margin-bottom:20px;">
        <h1 style="margin:0;font-size:24px;">📚 Daily Paper Recommendations</h1>
        <p style="margin:8px 0 0;opacity:0.9;">
            {datetime.now().strftime('%Y-%m-%d')} · {len(papers)} papers · {source_summary}
        </p>
    </div>
    """

    # Paper blocks
    for i, paper in enumerate(papers, 1):
        html += get_paper_block_html(paper, rank=i)

    # Footer
    html += """
    <div style="text-align:center;color:#999;font-size:12px;margin-top:24px;
                padding-top:16px;border-top:1px solid #eee;">
        Powered by
        <a href="https://github.com/TideDra/zotero-arxiv-daily">Zotero-arXiv-Daily</a>
        (Extended with PubMed/bioRxiv/medRxiv support)
    </div>
    </body>
    </html>
    """

    return html
