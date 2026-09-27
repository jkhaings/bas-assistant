"""Parse PDF bytes into per-page text, preserving table structure as markdown.

Docling does the real parsing; pypdfium2 (already a Docling dependency, and
reused directly rather than adding PyMuPDF) is the fallback when Docling
fails or returns nothing, per this session's documented time-box.
"""

from __future__ import annotations

import io
import logging

import pypdfium2 as pdfium
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
from docling_core.types.io import DocumentStream
from pydantic import BaseModel

from bas_assistant.ingest.sources import MAX_PDF_PAGES

logger = logging.getLogger(__name__)


class ParsedPdf(BaseModel):
    """A parsed PDF: one (page_number, text) pair per page, and how well it went."""

    pages: list[tuple[int, str]]
    parse_quality: str  # docling | fallback


def _docling_converter() -> DocumentConverter:
    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    # Declared as the wider value type: dict is invariant, and DocumentConverter
    # takes dict[InputFormat, FormatOption], not the narrower PdfFormatOption.
    format_options: dict[InputFormat, FormatOption] = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=options)
    }
    return DocumentConverter(format_options=format_options)


def _parse_with_docling(filename: str, content: bytes) -> list[tuple[int, str]]:
    stream = DocumentStream(name=filename, stream=io.BytesIO(content))
    result = _docling_converter().convert(stream, max_num_pages=MAX_PDF_PAGES)
    doc = result.document
    return [(page_no, doc.export_to_markdown(page_no=page_no)) for page_no in sorted(doc.pages)]


def _parse_with_pypdfium2(content: bytes) -> list[tuple[int, str]]:
    pdf = pdfium.PdfDocument(content)
    page_count = min(len(pdf), MAX_PDF_PAGES)
    return [(i + 1, pdf[i].get_textpage().get_text_range()) for i in range(page_count)]


def parse_pdf(filename: str, content: bytes) -> ParsedPdf:
    """Parse a PDF's bytes into per-page text. Falls back to pypdfium2 on any Docling failure."""
    try:
        pages = _parse_with_docling(filename, content)
        if any(text.strip() for _, text in pages):
            return ParsedPdf(pages=pages, parse_quality="docling")
        logger.warning("docling produced no text for %s; falling back", filename)
    except Exception:
        logger.exception("docling failed for %s; falling back", filename)
    return ParsedPdf(pages=_parse_with_pypdfium2(content), parse_quality="fallback")
