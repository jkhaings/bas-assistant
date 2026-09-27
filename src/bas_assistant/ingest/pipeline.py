"""Ingest orchestration: crawl → parse → chunk → embed → upsert, idempotently."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from bas_assistant.db.activity import Usage
from bas_assistant.db.corpus import Chunk, Document, Parent
from bas_assistant.ingest.chunking import ChildDraft, build_children, build_parents
from bas_assistant.ingest.crawl import RawSource
from bas_assistant.ingest.parse_html import parse_html
from bas_assistant.ingest.parse_pdf import parse_pdf
from bas_assistant.retrieval.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 100


@dataclass
class IngestOutcome:
    """What one successfully ingested document produced."""

    parent_count: int
    child_count: int
    parse_quality: str
    tokens: int
    usd: Decimal


@dataclass
class IngestReport:
    """Running counts from one ingest run, for the CLI summary."""

    ingested: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    documents_by_type: dict[str, int] = field(default_factory=dict)
    chunks_by_type: dict[str, int] = field(default_factory=dict)
    parents_written: int = 0
    chunks_written: int = 0
    parse_quality: dict[str, int] = field(default_factory=dict)
    embed_tokens: int = 0
    embed_usd: Decimal = Decimal("0")

    def record_success(self, source_type: str, is_new: bool, outcome: IngestOutcome) -> None:
        """Fold one successfully ingested document's counts into the running totals."""
        self.ingested += 1 if is_new else 0
        self.updated += 1 if not is_new else 0
        self.documents_by_type[source_type] = self.documents_by_type.get(source_type, 0) + 1
        self.chunks_by_type[source_type] = (
            self.chunks_by_type.get(source_type, 0) + outcome.child_count
        )
        self.parents_written += outcome.parent_count
        self.chunks_written += outcome.child_count
        self.parse_quality[outcome.parse_quality] = (
            self.parse_quality.get(outcome.parse_quality, 0) + 1
        )
        self.embed_tokens += outcome.tokens
        self.embed_usd += outcome.usd


def _parse(source: RawSource) -> tuple[list[tuple[int, str]], str]:
    """Return (pages, parse_quality) for one source."""
    if source.source_type == "pdf":
        parsed = parse_pdf(source.filename, source.content)
        return parsed.pages, parsed.parse_quality
    return [(1, parse_html(source.content))], "html"


def _content_hash(source: RawSource, pages: list[tuple[int, str]]) -> str:
    """Hash raw bytes for a PDF; hash the extracted text for HTML (whose bytes carry nonces)."""
    basis = (
        source.content if source.source_type == "pdf" else "\n".join(t for _, t in pages).encode()
    )
    return hashlib.sha256(basis).hexdigest()


def _embed_children(
    session: Session,
    document: Document,
    parents: list[Parent],
    drafts: list[ChildDraft],
    embedder: EmbeddingProvider,
) -> tuple[int, Decimal]:
    """Embed children in batches, write one usage row per batch, and add the Chunk rows."""
    total_tokens = 0
    total_usd = Decimal("0")
    for batch_start in range(0, len(drafts), EMBED_BATCH_SIZE):
        batch = drafts[batch_start : batch_start + EMBED_BATCH_SIZE]
        result = embedder.embed([draft.text for draft in batch])
        total_tokens += result.input_tokens
        total_usd += result.usd
        provider, model = result.provider_and_model(embedder.model)
        session.add(
            Usage(
                request_id=None,
                stage="embed",
                alias="embed",
                model=model,
                provider=provider,
                input_tokens=result.input_tokens,
                usd=result.usd,
                latency_ms=result.latency_ms,
            )
        )
        for offset, (draft, vector) in enumerate(zip(batch, result.vectors, strict=True)):
            session.add(
                Chunk(
                    document_id=document.id,
                    parent_id=parents[draft.parent_index].id,
                    page=draft.page,
                    position=batch_start + offset,
                    text=draft.text,
                    embedding=vector,
                )
            )
    return total_tokens, total_usd


def _unchanged_pdf_bytes(source: RawSource, existing: Document | None) -> bool:
    """Fast path: skip parsing entirely when a PDF's raw bytes already match."""
    return (
        existing is not None
        and source.source_type == "pdf"
        and hashlib.sha256(source.content).hexdigest() == existing.content_hash
    )


def _replace_document(
    session: Session,
    source: RawSource,
    content_hash: str,
    parse_quality: str,
    existing: Document | None,
) -> Document:
    """Delete the old document row (if any) and insert the new one, flushed so its id exists."""
    if existing is not None:
        session.delete(existing)  # cascades to its parents and chunks
        session.flush()
    document = Document(
        title=source.product,
        source_url=source.url,
        source_type=source.source_type,
        product=source.product,
        doc_type=source.doc_type,
        acl_groups=source.acl_groups,
        content_hash=content_hash,
        parse_quality=parse_quality,
    )
    session.add(document)
    session.flush()
    return document


def ingest_source(
    session: Session, source: RawSource, embedder: EmbeddingProvider, report: IngestReport
) -> None:
    """Ingest one source: skip if unchanged, otherwise replace it and update `report`."""
    existing = session.scalars(
        select(Document).where(Document.source_url == source.url)
    ).one_or_none()
    if _unchanged_pdf_bytes(source, existing):
        report.skipped += 1
        return

    pages, parse_quality = _parse(source)
    content_hash = _content_hash(source, pages)
    if existing is not None and existing.content_hash == content_hash:
        report.skipped += 1
        return

    parent_drafts = build_parents(pages)
    child_drafts = build_children(parent_drafts)
    document = _replace_document(session, source, content_hash, parse_quality, existing)

    parents = [
        Parent(document_id=document.id, page_start=p.page_start, page_end=p.page_end, text=p.text)
        for p in parent_drafts
    ]
    session.add_all(parents)
    session.flush()

    tokens, usd = _embed_children(session, document, parents, child_drafts, embedder)
    session.commit()

    outcome = IngestOutcome(
        parent_count=len(parents),
        child_count=len(child_drafts),
        parse_quality=parse_quality,
        tokens=tokens,
        usd=usd,
    )
    report.record_success(source.source_type, existing is None, outcome)


def run_ingest(
    session: Session, sources: list[RawSource], embedder: EmbeddingProvider
) -> IngestReport:
    """Ingest every source, one at a time, into one running report."""
    report = IngestReport()
    for source in sources:
        try:
            ingest_source(session, source, embedder, report)
        except Exception:
            logger.exception("failed to ingest %s", source.url)
            session.rollback()
            report.failed += 1
    return report
