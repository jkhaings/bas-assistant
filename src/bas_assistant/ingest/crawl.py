"""Crawl deltacontrols.com: robots.txt-respecting, rate-limited, cached to disk."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel
from selectolax.parser import HTMLParser

from bas_assistant.ingest.sources import (
    BASE_URL,
    CRAWL_DELAY_SECONDS,
    MAX_PDFS,
    PDF_NAME_ALLOWLIST,
    SITEMAP_URL,
    STARTER_PDFS,
    USER_AGENT,
    acl_groups_for,
    doc_type_for,
    product_for,
)

logger = logging.getLogger(__name__)

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class RawSource(BaseModel):
    """One fetched byte-blob ready for parsing, plus its provenance."""

    url: str
    filename: str
    product: str
    doc_type: str
    acl_groups: list[str]
    source_type: Literal["pdf", "page"]
    content: bytes


def _cache_path(url: str, raw_dir: Path) -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()
    suffix = ".pdf" if url.lower().endswith(".pdf") else ".html"
    return raw_dir / f"{digest}{suffix}"


def fetch(url: str, raw_dir: Path, client: httpx.Client, robots: RobotFileParser) -> bytes | None:
    """Fetch a URL through the on-disk cache. None means disallowed, missing, or an HTTP error."""
    cached = _cache_path(url, raw_dir)
    if cached.exists():
        return cached.read_bytes()
    if not robots.can_fetch(USER_AGENT, url):
        logger.info("robots.txt disallows %s", url)
        return None
    time.sleep(CRAWL_DELAY_SECONDS)
    try:
        response = client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("skipping %s: %s", url, exc)
        return None
    raw_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(response.content)
    return response.content


def discover_product_pages(
    raw_dir: Path, client: httpx.Client, robots: RobotFileParser
) -> list[str]:
    """Return every product page URL listed in the product sitemap."""
    body = fetch(SITEMAP_URL, raw_dir, client, robots)
    if body is None:
        return []
    root = ElementTree.fromstring(body)
    return [loc.text for loc in root.findall(".//sm:loc", _SITEMAP_NS) if loc.text]


def extract_pdf_links(html: bytes) -> list[str]:
    """Return catalog/datasheet/protocol PDF URLs from a product page's downloads list."""
    tree = HTMLParser(html)
    links = []
    for node in tree.css(".downloads-list a.download-link"):
        href = node.attributes.get("href")
        if href and href.lower().endswith(".pdf") and PDF_NAME_ALLOWLIST.search(href):
            links.append(urljoin(BASE_URL, href))
    return links


def discover_pdf_urls(raw_dir: Path, client: httpx.Client, robots: RobotFileParser) -> list[str]:
    """Return PDF URLs to ingest: the starter list, then whatever crawling adds, capped."""
    ordered = dict.fromkeys(f"{BASE_URL}/wp-content/uploads/{name}" for name in STARTER_PDFS)
    for page_url in discover_product_pages(raw_dir, client, robots):
        html = fetch(page_url, raw_dir, client, robots)
        if html is None:
            continue
        for pdf_url in extract_pdf_links(html):
            ordered.setdefault(pdf_url, None)
    return list(ordered)[:MAX_PDFS]


def _product_from_url(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    return slug.replace("-", " ").title()


def _pdf_source(url: str, content: bytes) -> RawSource:
    filename = url.rsplit("/", 1)[-1]
    return RawSource(
        url=url,
        filename=filename,
        product=product_for(filename),
        doc_type=doc_type_for(filename),
        acl_groups=acl_groups_for(filename),
        source_type="pdf",
        content=content,
    )


def _page_source(url: str, content: bytes) -> RawSource:
    return RawSource(
        url=url,
        filename=url.rstrip("/").rsplit("/", 1)[-1],
        product=_product_from_url(url),
        doc_type="page",
        acl_groups=["all"],
        source_type="page",
        content=content,
    )


def _load_robots(client: httpx.Client) -> RobotFileParser:
    """Fetch and parse robots.txt ourselves.

    RobotFileParser.read() fetches with urllib's default User-Agent, which
    deltacontrols.com's Cloudflare front end answers with a 403 — and
    RobotFileParser treats a 401/403 on the robots.txt fetch itself as
    "disallow everything", silently blocking every URL. Fetching with our own
    identified User-Agent (as every other request here does) avoids that.
    """
    response = client.get(f"{BASE_URL}/robots.txt", headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    robots = RobotFileParser()
    robots.parse(response.text.splitlines())
    return robots


def fetch_all(raw_dir: Path) -> list[RawSource]:
    """Crawl the corpus: starter + discovered PDFs, plus every product page's HTML."""
    sources: list[RawSource] = []
    with httpx.Client(timeout=60.0) as client:
        robots = _load_robots(client)
        for url in discover_pdf_urls(raw_dir, client, robots):
            content = fetch(url, raw_dir, client, robots)
            if content is not None:
                sources.append(_pdf_source(url, content))
        for page_url in discover_product_pages(raw_dir, client, robots):
            content = fetch(page_url, raw_dir, client, robots)
            if content is not None:
                sources.append(_page_source(page_url, content))
    return sources
