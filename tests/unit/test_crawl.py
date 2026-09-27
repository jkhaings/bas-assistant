"""Behaviour: PDF-link extraction, source classification, caching, and robots.txt/rate limiting."""

import time
from pathlib import Path
from urllib.robotparser import RobotFileParser

import httpx
import pytest

from bas_assistant.ingest.crawl import _page_source, _pdf_source, extract_pdf_links, fetch
from bas_assistant.ingest.sources import CRAWL_DELAY_SECONDS

pytestmark = pytest.mark.unit

_PRODUCT_PAGE = b"""
<html><body><main>
<ul class="downloads-list">
<li><a class="download-link" href="/wp-content/uploads/eBM-800-Catalog-Sheet.pdf">Catalog</a></li>
<li><a class="download-link" href="/wp-content/uploads/Forced-Labour-Report.pdf">Report</a></li>
</ul>
</main></body></html>
"""


def _allow_all_robots() -> RobotFileParser:
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    return robots


def _deny_all_robots() -> RobotFileParser:
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Disallow: /"])
    return robots


def test_extract_pdf_links_keeps_allowlisted_names_only() -> None:
    links = extract_pdf_links(_PRODUCT_PAGE)

    assert links == ["https://deltacontrols.com/wp-content/uploads/eBM-800-Catalog-Sheet.pdf"]


def test_pdf_source_classifies_by_filename() -> None:
    source = _pdf_source(
        "https://deltacontrols.com/wp-content/uploads/DAC-633PoE-Catalog-Sheet.pdf", b"%PDF-x"
    )

    assert source.source_type == "pdf"
    assert source.product == "DAC-633PoE"
    assert source.doc_type == "catalog"
    assert source.acl_groups == ["engineer"]


def test_page_source_derives_a_product_name_from_the_url_slug() -> None:
    source = _page_source("https://deltacontrols.com/products/o3-sensor-hub/", b"<html></html>")

    assert source.source_type == "page"
    assert source.product == "O3 Sensor Hub"
    assert source.acl_groups == ["all"]


def test_fetch_caches_to_disk_and_skips_the_delay_on_a_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "sleep", sleep_calls.append)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"hello")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = fetch("https://deltacontrols.com/x.pdf", tmp_path, client, _allow_all_robots())
        second = fetch("https://deltacontrols.com/x.pdf", tmp_path, client, _allow_all_robots())

    assert first == b"hello"
    assert second == b"hello"
    assert sleep_calls == [CRAWL_DELAY_SECONDS]  # only the first (uncached) fetch waits


def test_fetch_returns_none_when_robots_txt_disallows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("should never fetch a disallowed URL")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch(
            "https://deltacontrols.com/private.pdf", tmp_path, client, _deny_all_robots()
        )

    assert result is None


def test_fetch_returns_none_on_an_http_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(403))) as client:
        result = fetch("https://deltacontrols.com/gone.pdf", tmp_path, client, _allow_all_robots())

    assert result is None
