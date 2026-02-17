"""
BiomedPaper class - provides the same interface as ArxivPaper
for papers from PubMed, bioRxiv, and medRxiv.

This allows seamless integration with the existing recommendation
and email construction pipeline from zotero-arxiv-daily.
"""

import re
import logging
from functools import cached_property

logger = logging.getLogger(__name__)


class BiomedPaper:
    """
    A paper from PubMed, bioRxiv, or medRxiv.
    Provides the same property interface as ArxivPaper so it can be used
    interchangeably in the recommendation and email pipelines.
    """

    def __init__(self, data: dict, source: str = "pubmed"):
        """
        Args:
            data: dict with keys: title, abstract, authors, doi, pdf_url,
                  journal, date, affiliations_raw, pmid (optional)
            source: "pubmed", "biorxiv", or "medrxiv"
        """
        self._data = data
        self._source = source
        self.score = 0  # Will be set by recommender

    @property
    def title(self) -> str:
        return self._data.get("title", "")

    @property
    def summary(self) -> str:
        return self._data.get("abstract", "")

    @property
    def authors(self) -> list:
        authors = self._data.get("authors", [])
        if isinstance(authors, str):
            return [a.strip() for a in authors.split(";")]
        return authors

    @property
    def doi(self) -> str:
        return self._data.get("doi", "")

    @property
    def paper_id(self) -> str:
        """Unique identifier - DOI for biomed, PMID for pubmed."""
        if self._source == "pubmed":
            return self._data.get("pmid", self.doi)
        return self.doi

    @property
    def arxiv_id(self) -> str:
        """Compatibility with ArxivPaper - returns DOI or PMID."""
        return self.paper_id

    @property
    def pdf_url(self) -> str:
        url = self._data.get("pdf_url", "")
        if url:
            return url
        # Construct from DOI
        if self._source == "biorxiv":
            return f"https://www.biorxiv.org/content/{self.doi}v1.full.pdf"
        elif self._source == "medrxiv":
            return f"https://www.medrxiv.org/content/{self.doi}v1.full.pdf"
        elif self._source == "pubmed" and self.doi:
            return f"https://doi.org/{self.doi}"
        return ""

    @property
    def abs_url(self) -> str:
        """URL to the abstract/landing page."""
        if self._source == "biorxiv":
            return f"https://www.biorxiv.org/content/{self.doi}"
        elif self._source == "medrxiv":
            return f"https://www.medrxiv.org/content/{self.doi}"
        elif self._source == "pubmed":
            pmid = self._data.get("pmid", "")
            if pmid:
                return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            elif self.doi:
                return f"https://doi.org/{self.doi}"
        return ""

    @property
    def source(self) -> str:
        return self._source

    @property
    def source_label(self) -> str:
        labels = {
            "pubmed": "PubMed",
            "biorxiv": "bioRxiv",
            "medrxiv": "medRxiv",
        }
        return labels.get(self._source, self._source)

    @property
    def journal(self) -> str:
        return self._data.get("journal", self.source_label)

    @property
    def date(self) -> str:
        return self._data.get("date", "")

    @cached_property
    def code_url(self) -> str | None:
        """bioRxiv/medRxiv papers rarely have code repos, return None."""
        return None

    @cached_property
    def tex(self) -> dict | None:
        """No LaTeX source for biomed papers."""
        return None

    @cached_property
    def tldr(self) -> str:
        """Generate TL;DR using LLM - same approach as ArxivPaper."""
        try:
            from llm import get_llm
            llm = get_llm()

            prompt = (
                f"Given the title and abstract of a biomedical paper, "
                f"generate a one-sentence TLDR summary in {llm.lang}:\n\n"
                f"Title: {self.title}\n\n"
                f"Abstract: {self.summary}\n"
            )

            # Truncate if too long
            try:
                import tiktoken
                enc = tiktoken.encoding_for_model("gpt-4o")
                tokens = enc.encode(prompt)
                if len(tokens) > 4000:
                    prompt = enc.decode(tokens[:4000])
            except Exception:
                prompt = prompt[:16000]

            tldr = llm.chat(prompt)
            logger.info(f"Generated TLDR for: {self.title[:50]}...")
            return tldr
        except Exception as e:
            logger.warning(f"Failed to generate TLDR for {self.title}: {e}")
            return self.summary[:300] + "..." if len(self.summary) > 300 else self.summary

    @cached_property
    def affiliations(self) -> list | None:
        """Extract affiliations from raw data."""
        raw = self._data.get("affiliations_raw", [])
        if isinstance(raw, list) and raw:
            # Deduplicate while preserving order
            seen = set()
            result = []
            for a in raw:
                a_clean = a.strip()
                if a_clean and a_clean not in seen:
                    seen.add(a_clean)
                    result.append(a_clean)
            return result if result else None
        elif isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        return None

    def __repr__(self):
        return f"BiomedPaper(source={self._source}, title={self.title[:50]}...)"
