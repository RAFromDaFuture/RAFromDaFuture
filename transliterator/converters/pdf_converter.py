"""
PDF-to-Markdown Converter

Faithfully converts PDF documents into structured Markdown.
Preserves headings, paragraphs, tables, lists, and formatting.
No interpretation — just transliteration.
"""

import os
import sys


class PDFConverter:
    """Converts PDF files to clean Markdown."""

    SUPPORTED_EXTENSIONS = {".pdf"}

    @staticmethod
    def can_handle(file_path: str) -> bool:
        _, ext = os.path.splitext(file_path.lower())
        return ext in PDFConverter.SUPPORTED_EXTENSIONS

    @staticmethod
    def convert(file_path: str) -> str:
        """
        Convert a PDF file to Markdown text.

        Uses pymupdf4llm for high-fidelity PDF-to-Markdown conversion
        that preserves document structure (headings, tables, lists, etc.).
        Falls back to raw text extraction if pymupdf4llm is unavailable.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        # Primary: pymupdf4llm gives the best markdown output
        try:
            import pymupdf4llm
            md_text = pymupdf4llm.to_markdown(file_path)
            return _postprocess(md_text, file_path)
        except ImportError:
            pass

        # Fallback: pymupdf (fitz) raw text extraction
        try:
            import fitz  # pymupdf
            doc = fitz.open(file_path)
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text("text")
                if text.strip():
                    pages.append(f"<!-- Page {i + 1} -->\n\n{text.strip()}")
            doc.close()
            raw = "\n\n---\n\n".join(pages)
            return _postprocess(raw, file_path)
        except ImportError:
            raise RuntimeError(
                "Neither pymupdf4llm nor pymupdf is installed. "
                "Run: pip install pymupdf4llm pymupdf"
            )


def _postprocess(md_text: str, file_path: str) -> str:
    """Add source metadata header and clean up the output."""
    filename = os.path.basename(file_path)
    header = (
        f"---\n"
        f"source_type: pdf\n"
        f"source_file: {filename}\n"
        f"---\n\n"
    )
    # Normalize excessive blank lines
    lines = md_text.split("\n")
    cleaned = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)

    return header + "\n".join(cleaned).strip() + "\n"
