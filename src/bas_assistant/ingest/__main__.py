"""CLI entry point: `python -m bas_assistant.ingest` — crawl, parse, chunk, embed, index."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from bas_assistant.db.engine import get_engine
from bas_assistant.ingest.crawl import fetch_all
from bas_assistant.ingest.pipeline import IngestReport, run_ingest
from bas_assistant.logging import configure_logging
from bas_assistant.retrieval.embeddings import OpenAIEmbedder
from bas_assistant.settings import Settings

RAW_DIR = Path("data/raw")

logger = logging.getLogger(__name__)


def _log_report(report: IngestReport, elapsed_s: float) -> None:
    logger.info(
        "ingest complete: ingested=%d updated=%d skipped=%d failed=%d "
        "documents_by_type=%s chunks_by_type=%s parents=%d chunks=%d "
        "parse_quality=%s embed_tokens=%d embed_usd=%s elapsed_s=%.1f",
        report.ingested,
        report.updated,
        report.skipped,
        report.failed,
        report.documents_by_type,
        report.chunks_by_type,
        report.parents_written,
        report.chunks_written,
        report.parse_quality,
        report.embed_tokens,
        report.embed_usd,
        elapsed_s,
    )


def main() -> None:
    """Crawl the corpus, then parse, chunk, embed, and index every source."""
    configure_logging()
    start = time.monotonic()

    sources = fetch_all(RAW_DIR)
    embedder = OpenAIEmbedder(Settings())
    with Session(get_engine()) as session:
        report = run_ingest(session, sources, embedder)

    _log_report(report, time.monotonic() - start)


if __name__ == "__main__":  # pragma: no cover
    main()
