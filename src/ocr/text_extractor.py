"""
Text extraction from various document formats
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from docx import Document


class TextExtractor:
    """Extract text from various document formats using OCR"""

    def __init__(self, config: dict):
        """
        Initialize TextExtractor

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.ocr_config = config.get("ocr", {})
        self.languages = "+".join(self.ocr_config.get("languages", ["eng"]))

    def extract_from_image(self, image_path: str) -> Dict[str, any]:
        """
        Extract text from image file

        Args:
            image_path: Path to image file

        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            self.logger.info(f"Extracting text from image: {image_path}")

            # Load image
            image = Image.open(image_path)

            # Perform OCR
            custom_config = f"--oem 3 --psm 6 -l {self.languages}"
            text = pytesseract.image_to_string(image, config=custom_config)

            # Get OCR confidence
            try:
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config=custom_config)
                confidences = [int(conf) for conf in data["conf"] if conf != "-1"]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            except Exception as e:
                self.logger.warning(f"Could not calculate OCR confidence: {e}")
                avg_confidence = 0

            return {
                "success": True,
                "text": text.strip(),
                "confidence": avg_confidence,
                "page_count": 1,
                "format": "image",
            }

        except Exception as e:
            self.logger.error(f"Error extracting text from image: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0,
            }

    def extract_from_pdf(self, pdf_path: str) -> Dict[str, any]:
        """
        Extract text from PDF file

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            self.logger.info(f"Extracting text from PDF: {pdf_path}")

            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=300)
            self.logger.info(f"PDF has {len(images)} pages")

            all_text = []
            all_confidences = []

            # Process each page
            for i, image in enumerate(images, 1):
                self.logger.debug(f"Processing page {i}/{len(images)}")

                # Perform OCR
                custom_config = f"--oem 3 --psm 6 -l {self.languages}"
                text = pytesseract.image_to_string(image, config=custom_config)
                all_text.append(text)

                # Get confidence
                try:
                    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config=custom_config)
                    confidences = [int(conf) for conf in data["conf"] if conf != "-1"]
                    if confidences:
                        all_confidences.extend(confidences)
                except Exception as e:
                    self.logger.warning(f"Could not calculate OCR confidence for page {i}: {e}")

            # Calculate average confidence
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0

            return {
                "success": True,
                "text": "\n\n".join(all_text).strip(),
                "confidence": avg_confidence,
                "page_count": len(images),
                "format": "pdf",
            }

        except Exception as e:
            self.logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0,
            }

    def extract_from_docx(self, docx_path: str) -> Dict[str, any]:
        """
        Extract text from DOCX file (no OCR needed)

        Args:
            docx_path: Path to DOCX file

        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            self.logger.info(f"Extracting text from DOCX: {docx_path}")

            doc = Document(docx_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])

            return {
                "success": True,
                "text": text.strip(),
                "confidence": 100,  # No OCR needed
                "page_count": len(doc.sections),
                "format": "docx",
            }

        except Exception as e:
            self.logger.error(f"Error extracting text from DOCX: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0,
            }

    def extract(self, file_path: str) -> Dict[str, any]:
        """
        Extract text from file (auto-detect format)

        Args:
            file_path: Path to file

        Returns:
            Dictionary with extracted text and metadata
        """
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "text": "",
                "confidence": 0,
            }

        # Get file extension
        ext = Path(file_path).suffix.lower()

        # Route to appropriate extractor
        if ext in [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"]:
            return self.extract_from_image(file_path)
        elif ext == ".pdf":
            return self.extract_from_pdf(file_path)
        elif ext == ".docx":
            return self.extract_from_docx(file_path)
        else:
            return {
                "success": False,
                "error": f"Unsupported file format: {ext}",
                "text": "",
                "confidence": 0,
            }
