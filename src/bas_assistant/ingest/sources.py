"""Corpus source configuration: what to crawl, and how to classify it.

See data/SOURCES.md for the sourcing rules this implements.
"""

from __future__ import annotations

import re
from pathlib import Path

BASE_URL = "https://deltacontrols.com"
SITEMAP_URL = f"{BASE_URL}/product-sitemap.xml"
USER_AGENT = "bas-assistant/0.1 (+https://github.com/jkhaings/bas-assistant)"
CRAWL_DELAY_SECONDS = 10.0  # robots.txt says 10; stricter than the design's 1 req/s

# The real crawl discovers 78 unique catalog PDF URLs across the 42 product
# pages (confirmed by running discovery uncapped; 70 fetched successfully as
# of the Sep 27 2026 ingest, a handful blocked by Cloudflare on individual
# URLs) — comfortably covered at 90. A lower cap (40) silently dropped
# O3-Sensor-Hub-Catalog-Sheet.pdf, which the golden questions depend on,
# purely because of where it falls in sitemap order.
MAX_PDFS = 90
MAX_PDF_PAGES = 20

# Product pages link to many PDFs (spec sheets, forced-labour reports, old
# conference decks). Only these look like actual product documentation.
PDF_NAME_ALLOWLIST = re.compile(r"(catalog|datasheet|data-sheet|spec|protocol)", re.IGNORECASE)

# Two documents kept engineer-tier so the ACL and abstain-for-support tests
# have something real to check against; the rest are acl_groups=["all"].
# Confirmed against the parsed corpus in data/top20_questions.md.
ENGINEER_ONLY_FILENAMES = frozenset(
    {
        "UNOnext-MODBUS-RTU-Protocol.pdf",
        "DAC-633PoE-Catalog-Sheet.pdf",
    }
)

# Tried first regardless of what the sitemap crawl finds, so ingestion stays
# useful even if deltacontrols.com reshuffles its product pages.
STARTER_PDFS: dict[str, str] = {
    "enteliWEB-Catalog-Sheet.pdf": "enteliWEB",
    "enteliVAULT_Catalog_Sheet.pdf": "enteliVAULT",
    "enteliVIEW-Catalog-Sheet.pdf": "enteliVIEW",
    "eBM-800-Catalog-Sheet.pdf": "eBM-800",
    "eBMGR-Catalog-Sheet.pdf": "eBMGR",
    "Red5-PLUS-1146_Catalog-Sheet.pdf": "Red5-PLUS-1146",
    "Red5-PLUS-1180_Catalog-Sheet.pdf": "Red5-PLUS-1180",
    "eZNT-T331_Catalog_Sheet.pdf": "eZNT-T331",
    "eZNTW_Catalog_Sheet.pdf": "eZNTW",
    "DAC-633PoE-Catalog-Sheet.pdf": "DAC-633PoE",
    "UNOnext-Datasheet.pdf": "UNOnext",
    "UNOnext-MODBUS-RTU-Protocol.pdf": "UNOnext",
}

_PRODUCT_SUFFIX = re.compile(
    r"[-_](Catalog[-_]Sheet|Data-?sheet|Protocol|Presentaion|Presentation).*$", re.IGNORECASE
)


def acl_groups_for(filename: str) -> list[str]:
    """Return the ACL groups for a PDF, by filename."""
    if filename in ENGINEER_ONLY_FILENAMES:
        return ["engineer"]
    return ["all"]


def doc_type_for(filename: str) -> str:
    """Classify a PDF filename into a doc_type for filtering and citations."""
    lower = filename.lower()
    if "protocol" in lower:
        return "protocol"
    if "datasheet" in lower or "data-sheet" in lower:
        return "datasheet"
    return "catalog"


def product_from_filename(filename: str) -> str:
    """Derive a human-readable product name from a PDF filename.

    A heuristic fallback for PDFs discovered by crawling rather than listed in
    STARTER_PDFS: strip the doc-type suffix, then de-slug what remains.
    """
    stem = _PRODUCT_SUFFIX.sub("", Path(filename).stem)
    return stem.replace("_", " ").replace("-", " ").strip() or stem


def product_for(filename: str) -> str:
    """Look up the known product name, or derive one from the filename."""
    return STARTER_PDFS.get(filename, product_from_filename(filename))
