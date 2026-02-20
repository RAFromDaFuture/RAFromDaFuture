"""
Web/SharePoint URL-to-Markdown Converter

Faithfully converts web pages (including SharePoint pages) into
structured Markdown. Preserves headings, paragraphs, tables, links,
lists, and images. No interpretation — just transliteration.
"""

import os
import re
from urllib.parse import urlparse


class WebConverter:
    """Converts web pages and SharePoint links to clean Markdown."""

    @staticmethod
    def can_handle(source: str) -> bool:
        """Check if the source looks like a URL."""
        try:
            parsed = urlparse(source)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def is_sharepoint(url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        return "sharepoint.com" in host or "sharepoint.us" in host

    @staticmethod
    def convert(url: str) -> str:
        """
        Fetch a URL and convert its HTML content to Markdown.

        Handles regular web pages and SharePoint pages.
        SharePoint pages get special handling to extract the actual
        document content from SharePoint's wrapper HTML.
        """
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests is not installed. Run: pip install requests")

        try:
            from markdownify import markdownify as md
        except ImportError:
            raise RuntimeError("markdownify is not installed. Run: pip install markdownify")

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise RuntimeError("beautifulsoup4 is not installed. Run: pip install beautifulsoup4")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")

        # If the URL points directly to a PDF, hand off to PDF converter
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            return _handle_pdf_url(url, response.content)

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Remove script/style/nav elements that aren't content
        for tag in soup.find_all(["script", "style", "nav", "footer", "iframe", "noscript"]):
            tag.decompose()

        # SharePoint-specific: extract main content area
        if WebConverter.is_sharepoint(url):
            content_area = (
                soup.find("div", {"class": re.compile(r"CanvasZone|rte-editor|wiki", re.I)})
                or soup.find("div", {"role": "main"})
                or soup.find("main")
                or soup.find("article")
            )
            if content_area:
                soup = content_area

        # Extract page title
        title = ""
        title_tag = soup.find("title") if hasattr(soup, "find") else None
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # Convert to markdown
        md_text = md(
            str(soup),
            heading_style="ATX",
            bullets="-",
            strip=["img"],
            convert=["table", "thead", "tbody", "tr", "th", "td",
                     "p", "h1", "h2", "h3", "h4", "h5", "h6",
                     "ul", "ol", "li", "a", "strong", "em",
                     "blockquote", "pre", "code", "br", "hr"],
        )

        return _postprocess(md_text, url, title)

    @staticmethod
    def convert_sharepoint_doc(url: str, auth_token: str = None) -> str:
        """
        Convert a SharePoint-hosted document (Word, Excel, PDF).

        If auth_token is provided, uses it for authenticated access
        to SharePoint REST API. Otherwise attempts anonymous access.
        """
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests is not installed. Run: pip install requests")

        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
            headers["Accept"] = "application/json;odata=verbose"

        # Try to get the file via SharePoint REST API
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Attempt direct download
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")

        if "application/pdf" in content_type:
            return _handle_pdf_url(url, response.content)
        elif "application/vnd.openxmlformats-officedocument" in content_type:
            return _handle_office_url(url, response.content, content_type)
        else:
            # Treat as HTML page
            return WebConverter.convert(url)


def _handle_pdf_url(url: str, content: bytes) -> str:
    """Save PDF content to temp file and convert."""
    import tempfile
    from .pdf_converter import PDFConverter

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        return PDFConverter.convert(tmp_path)
    finally:
        os.unlink(tmp_path)


def _handle_office_url(url: str, content: bytes, content_type: str) -> str:
    """Save Office doc content to temp file and convert."""
    import tempfile
    from .office_converter import OfficeConverter

    if "wordprocessingml" in content_type:
        suffix = ".docx"
    elif "spreadsheetml" in content_type:
        suffix = ".xlsx"
    else:
        suffix = ".docx"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        return OfficeConverter.convert(tmp_path)
    finally:
        os.unlink(tmp_path)


def _postprocess(md_text: str, url: str, title: str = "") -> str:
    """Add source metadata header and clean up."""
    parsed = urlparse(url)
    source_type = "sharepoint" if WebConverter.is_sharepoint(url) else "web"

    header = (
        f"---\n"
        f"source_type: {source_type}\n"
        f"source_url: {url}\n"
        f"source_domain: {parsed.netloc}\n"
    )
    if title:
        header += f"title: {title}\n"
    header += f"---\n\n"

    if title and not md_text.strip().startswith(f"# {title}"):
        md_text = f"# {title}\n\n{md_text}"

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
