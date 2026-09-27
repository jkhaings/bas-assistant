"""Parse a Delta Controls product page into markdown-ish text.

Headings, paragraphs, list items, and tables become text; nav, footer, and
script/style noise are dropped. Selectolax's compound CSS selectors do not
preserve document order (verified against the real markup), so content is
walked depth-first through direct-child iteration instead.
"""

from __future__ import annotations

from selectolax.parser import HTMLParser, Node

_DROP_SELECTORS = ("nav", "footer", "header", "script", "style", "form")
_HEADING_PREFIX = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}


def _table_to_markdown(table: Node) -> str:
    rows = [[cell.text(strip=True) for cell in tr.css("th, td")] for tr in table.css("tr")]
    rows = [row for row in rows if any(row)]
    if not rows:
        return ""
    header = "| " + " | ".join(rows[0]) + " |"
    divider = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body = ("| " + " | ".join(row) + " |" for row in rows[1:])
    return "\n".join([header, divider, *body])


def _walk_blocks(node: Node) -> list[str]:
    """Depth-first walk that treats headings, paragraphs, items, and tables as leaves."""
    blocks: list[str] = []
    for child in node.iter():
        tag = child.tag
        if tag in _HEADING_PREFIX:
            text = child.text(strip=True)
            if text:
                blocks.append(f"{_HEADING_PREFIX[tag]} {text}")
        elif tag in ("p", "li"):
            text = child.text(strip=True)
            if text:
                blocks.append(text)
        elif tag == "table":
            table_md = _table_to_markdown(child)
            if table_md:
                blocks.append(table_md)
        else:
            blocks.extend(_walk_blocks(child))
    return blocks


def parse_html(content: bytes) -> str:
    """Return a product page's main content as markdown-ish text."""
    tree = HTMLParser(content)
    for selector in _DROP_SELECTORS:
        for node in tree.css(selector):
            node.decompose()

    root = tree.css_first("main") or tree.body
    if root is None:
        return ""
    return "\n\n".join(_walk_blocks(root))
