"""
Image-to-Markdown Converter (OCR)

Faithfully extracts text from images using OCR and outputs
structured Markdown. No interpretation — just transliteration
of visible text content.
"""

import os


class ImageConverter:
    """Converts images to Markdown via OCR text extraction."""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"}

    @staticmethod
    def can_handle(file_path: str) -> bool:
        _, ext = os.path.splitext(file_path.lower())
        return ext in ImageConverter.SUPPORTED_EXTENSIONS

    @staticmethod
    def convert(file_path: str) -> str:
        """
        Extract text from an image file using OCR and return as Markdown.

        Uses Tesseract OCR via pytesseract. Falls back to Pillow-only
        basic info if Tesseract is not installed.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Image file not found: {file_path}")

        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("Pillow is not installed. Run: pip install Pillow")

        img = Image.open(file_path)
        width, height = img.size
        img_format = img.format or os.path.splitext(file_path)[1].lstrip(".")

        # Try OCR with pytesseract
        ocr_text = ""
        try:
            import pytesseract
            ocr_text = pytesseract.image_to_string(img)
        except ImportError:
            ocr_text = "[OCR unavailable — install pytesseract and Tesseract engine]"
        except Exception as e:
            ocr_text = f"[OCR failed: {e}]"

        return _postprocess(ocr_text, file_path, width, height, img_format)


def _postprocess(ocr_text: str, file_path: str, width: int, height: int, img_format: str) -> str:
    """Add source metadata and structure the output."""
    filename = os.path.basename(file_path)

    header = (
        f"---\n"
        f"source_type: image\n"
        f"source_file: {filename}\n"
        f"image_format: {img_format}\n"
        f"image_dimensions: {width}x{height}\n"
        f"---\n\n"
    )

    if ocr_text.strip():
        body = f"## Extracted Text\n\n{ocr_text.strip()}\n"
    else:
        body = "## Extracted Text\n\n[No text detected in image]\n"

    return header + body
