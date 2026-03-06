"""
OCR service for extracting text from images and PDFs.
Uses Tesseract OCR with Vietnamese language support.
"""

import logging
import tempfile
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """OCR service using Tesseract for Vietnamese text extraction."""

    def __init__(self) -> None:
        self.lang = settings.tesseract_lang
        self._check_tesseract()

    def _check_tesseract(self) -> None:
        """Verify Tesseract is available."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
        except Exception:
            logger.warning(
                "Tesseract not found. OCR features will be unavailable. "
                "Install: apt-get install tesseract-ocr tesseract-ocr-vie"
            )

    async def extract_from_url(self, url: str) -> str:
        """Download image from URL and extract text."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()

            image = Image.open(BytesIO(response.content))
            return self._ocr_image(image)
        except Exception as e:
            logger.error("OCR from URL failed: %s", e)
            return ""

    async def extract_from_pdf_url(self, url: str) -> str:
        """Download PDF from URL and extract text via OCR."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                tmp.write(response.content)
                tmp.flush()
                return self._ocr_pdf(Path(tmp.name))
        except Exception as e:
            logger.error("PDF OCR failed: %s", e)
            return ""

    def _ocr_image(self, image: Image.Image) -> str:
        """Run OCR on a PIL Image."""
        import pytesseract

        # Preprocess for better OCR accuracy
        if image.mode != "RGB":
            image = image.convert("RGB")

        text = pytesseract.image_to_string(image, lang=self.lang)
        return text.strip()

    def _ocr_pdf(self, pdf_path: Path) -> str:
        """Convert PDF pages to images and run OCR."""
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(str(pdf_path), dpi=300)
            texts = [self._ocr_image(img) for img in images]
            return "\n\n--- Page ---\n\n".join(texts)
        except Exception as e:
            logger.error("PDF to image conversion failed: %s", e)
            return ""
