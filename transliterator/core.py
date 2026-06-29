"""
Transliterator Core Engine

The main orchestrator that detects input types and routes them to
the appropriate converter. Supports files (PDF, DOCX, XLSX, images)
and URLs (web pages, SharePoint links).

Zero AI interpretation — faithful structural transliteration only.
"""

import os
import glob as globmod
from datetime import datetime, timezone

from .converters.pdf_converter import PDFConverter
from .converters.web_converter import WebConverter
from .converters.image_converter import ImageConverter
from .converters.office_converter import OfficeConverter


class Transliterator:
    """
    Main transliterator engine.

    Accepts any supported source (file path, URL, or directory)
    and produces clean Markdown output.
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(os.getcwd(), "transliterator_output")
        os.makedirs(self.output_dir, exist_ok=True)

    def convert(self, source: str, save: bool = True) -> str:
        """
        Convert a source to Markdown.

        Args:
            source: File path, URL, or directory path
            save: If True, save the output to a .md file

        Returns:
            The Markdown text
        """
        source = source.strip()

        # Detect source type and route to correct converter
        if WebConverter.can_handle(source):
            print(f"[URL] Converting: {source}")
            md_text = WebConverter.convert(source)
            out_name = _url_to_filename(source)

        elif os.path.isdir(source):
            print(f"[DIR] Converting all supported files in: {source}")
            return self.convert_directory(source, save=save)

        elif os.path.isfile(source):
            md_text = self._convert_file(source)
            out_name = _file_to_md_name(source)

        else:
            raise ValueError(
                f"Cannot handle source: {source}\n"
                f"Provide a valid file path, directory, or URL."
            )

        if save:
            out_path = os.path.join(self.output_dir, out_name)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md_text)
            print(f"[SAVED] {out_path}")

        return md_text

    def convert_directory(self, dir_path: str, save: bool = True) -> str:
        """Convert all supported files in a directory."""
        results = []
        supported_exts = (
            PDFConverter.SUPPORTED_EXTENSIONS
            | ImageConverter.SUPPORTED_EXTENSIONS
            | OfficeConverter.SUPPORTED_EXTENSIONS
        )

        files = sorted(os.listdir(dir_path))
        converted_count = 0

        for filename in files:
            file_path = os.path.join(dir_path, filename)
            if not os.path.isfile(file_path):
                continue

            _, ext = os.path.splitext(filename.lower())
            if ext not in supported_exts:
                continue

            try:
                md_text = self._convert_file(file_path)
                if save:
                    out_name = _file_to_md_name(file_path)
                    out_path = os.path.join(self.output_dir, out_name)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(md_text)
                    print(f"[SAVED] {out_path}")
                results.append(md_text)
                converted_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to convert {filename}: {e}")

        summary = (
            f"---\n"
            f"batch_conversion: true\n"
            f"source_directory: {dir_path}\n"
            f"files_converted: {converted_count}\n"
            f"timestamp: {datetime.now(timezone.utc).isoformat()}\n"
            f"---\n\n"
        )

        return summary + "\n\n---\n\n".join(results)

    def _convert_file(self, file_path: str) -> str:
        """Route a file to the appropriate converter."""
        if PDFConverter.can_handle(file_path):
            print(f"[PDF] Converting: {file_path}")
            return PDFConverter.convert(file_path)

        elif ImageConverter.can_handle(file_path):
            print(f"[IMG] Converting: {file_path}")
            return ImageConverter.convert(file_path)

        elif OfficeConverter.can_handle(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            print(f"[{ext.upper().lstrip('.')}] Converting: {file_path}")
            return OfficeConverter.convert(file_path)

        else:
            # Try to read as plain text
            print(f"[TXT] Reading as plain text: {file_path}")
            return _read_as_text(file_path)

    @staticmethod
    def supported_formats() -> dict:
        """Return a dictionary of all supported formats."""
        return {
            "PDF": list(PDFConverter.SUPPORTED_EXTENSIONS),
            "Images (OCR)": list(ImageConverter.SUPPORTED_EXTENSIONS),
            "Office Documents": list(OfficeConverter.SUPPORTED_EXTENSIONS),
            "Web Pages": ["http://", "https://"],
            "SharePoint": ["*.sharepoint.com/*"],
            "Plain Text": [".txt", ".csv", ".md", ".json", ".xml", ".html"],
        }


def _file_to_md_name(file_path: str) -> str:
    """Generate a .md filename from the source file."""
    basename = os.path.basename(file_path)
    name, _ = os.path.splitext(basename)
    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
    return f"{safe_name}.md"


def _url_to_filename(url: str) -> str:
    """Generate a .md filename from a URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_") or "index"
    domain = parsed.netloc.replace(".", "_")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{domain}_{path}")
    return f"{safe}.md"


def _read_as_text(file_path: str) -> str:
    """Read a file as plain text and wrap it in markdown."""
    filename = os.path.basename(file_path)
    _, ext = os.path.splitext(filename)

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    header = (
        f"---\n"
        f"source_type: text\n"
        f"source_file: {filename}\n"
        f"---\n\n"
    )

    # If it's already markdown, just add the header
    if ext.lower() in (".md", ".markdown"):
        return header + content

    # For code/config files, wrap in a code block
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".json": "json", ".xml": "xml", ".html": "html", ".css": "css",
        ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".sh": "bash",
        ".sql": "sql", ".csv": "csv",
    }
    lang = lang_map.get(ext.lower(), "")

    if lang:
        return header + f"```{lang}\n{content}\n```\n"

    return header + content
