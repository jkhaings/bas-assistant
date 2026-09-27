# Corpus sources

All sources are **publicly accessible** (no login required). Session A ingests them.

## Delta Controls catalog-sheet PDFs

Base URL: `https://deltacontrols.com/wp-content/uploads/`

Starter list (12 documents):
- enteliWEB-Catalog-Sheet.pdf
- enteliVAULT_Catalog_Sheet.pdf
- enteliVIEW-Catalog-Sheet.pdf
- eBM-800-Catalog-Sheet.pdf
- eBMGR-Catalog-Sheet.pdf
- Red5-PLUS-1146_Catalog-Sheet.pdf
- Red5-PLUS-1180_Catalog-Sheet.pdf
- eZNT-T331_Catalog_Sheet.pdf
- eZNTW_Catalog_Sheet.pdf
- DAC-633PoE-Catalog-Sheet.pdf
- UNOnext-Datasheet.pdf
- UNOnext-MODBUS-RTU-Protocol.pdf

Session A also discovers additional PDF links from every product page (see below), capped at 40
PDFs total, filtered to filenames that look like catalog/datasheet/protocol/spec sheets (forced-labour
reports and old conference decks linked from the same pages are excluded by that filter).

## Delta Controls product pages

Discovered from `https://deltacontrols.com/product-sitemap.xml` (42 URLs as of Sep 26) — the
robots.txt-endorsed path, used instead of reverse-engineering the "Load More" AJAX call. Each page's
`.downloads-section .downloads-list a.download-link` is scanned for `.pdf` links.

## O3 help center

Deferred until after the technical round (Zendesk API requires further investigation).

## FORBIDDEN

`support.deltacontrols.com` — **SSO-gated**. Never crawl, never fetch, never pass
its URLs to any model. Claude is denied by `.claude/settings.json`.

## Ingestion rules

- robots.txt respected for all sources. `deltacontrols.com/robots.txt` sets `Crawl-delay: 10`
  (stricter than the original 1-req/s plan) and blocks the bare `curl`/`wget` user agents — the
  crawler identifies itself as `bas-assistant/0.1 (+https://github.com/jkhaings/bas-assistant)`.
- No parallelism within a domain; the 10s delay only applies to cache misses, so a re-run with a
  warm `data/raw/` cache does no network I/O at all.
- Raw bytes cached in `data/raw/` keyed by a hash of the URL (gitignored).
- Content-hash idempotency: unchanged sources are skipped on re-ingest (raw bytes for a PDF,
  extracted text for HTML — HTML carries per-request nonces that would defeat a raw-byte hash).
- Two documents are `acl_groups = ["engineer"]` for RBAC tests — `UNOnext-MODBUS-RTU-Protocol.pdf`
  and `DAC-633PoE-Catalog-Sheet.pdf` (see `src/bas_assistant/ingest/sources.py`); the rest `["all"]`.
