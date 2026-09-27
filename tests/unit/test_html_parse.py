"""Behaviour: HTML product pages become markdown-ish text, in document order."""

import pytest

from bas_assistant.ingest.parse_html import parse_html

pytestmark = pytest.mark.unit

_PAGE = b"""
<html><body>
<nav><a href="/x">skip nav</a></nav>
<main>
<h1>O3 Sensor Hub</h1>
<p>Replaces multiple room sensors.</p>
<h2>Specifications</h2>
<table>
<tr><th>Spec</th><th>Value</th></tr>
<tr><td>Voltage</td><td>24 VDC</td></tr>
</table>
<ul><li>Modbus RTU</li><li>NFC</li></ul>
</main>
<footer>skip footer</footer>
</body></html>
"""


def test_headings_and_paragraphs_appear_in_document_order() -> None:
    text = parse_html(_PAGE)
    assert text.index("# O3 Sensor Hub") < text.index("Replaces multiple room sensors.")
    assert text.index("Replaces multiple room sensors.") < text.index("## Specifications")


def test_table_becomes_pipe_rows_with_a_header_divider() -> None:
    text = parse_html(_PAGE)
    assert "| Spec | Value |" in text
    assert "| --- | --- |" in text
    assert "| Voltage | 24 VDC |" in text


def test_list_items_are_kept() -> None:
    text = parse_html(_PAGE)
    assert "Modbus RTU" in text
    assert "NFC" in text


def test_nav_and_footer_are_dropped() -> None:
    text = parse_html(_PAGE)
    assert "skip nav" not in text
    assert "skip footer" not in text


def test_empty_page_returns_empty_string() -> None:
    assert parse_html(b"<html><body></body></html>") == ""
