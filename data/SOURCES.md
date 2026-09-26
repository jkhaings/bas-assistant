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

Session A also crawls product pages for additional PDF links.

## Delta Controls product pages

`https://deltacontrols.com/products/` — follow "Load More". robots.txt respected.
One request per second. Raw HTML cached in `data/raw/` (gitignored).

## O3 help center

Deferred until after the technical round (Zendesk API requires further investigation).

## FORBIDDEN

`support.deltacontrols.com` — **SSO-gated**. Never crawl, never fetch, never pass
its URLs to any model. Claude is denied by `.claude/settings.json`.

## Ingestion rules

- robots.txt respected for all sources.
- 1 request per second, no parallelism within a domain.
- Raw bytes cached in `data/raw/` keyed by URL hash (gitignored).
- Content-hash idempotency: unchanged sources are skipped on re-ingest.
- Mark two documents `acl_groups = ["engineer"]` for RBAC tests; the rest `["all"]`.
