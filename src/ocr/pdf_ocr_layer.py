#!/usr/bin/env python3
"""
** The project "maj-document-recognition-v2/src" is a document matching system that automates the pr
"""

"""
PDF OCR Layer Handler v2.0
Optimální fallback řetězec pro extrakci textu z dokumentů

Fallback strategie (na základě benchmarku):
  PDF: pdftotext (10ms) → Tesseract (1.2s) → Docling (26s)
  Obrázky: Tesseract (1.2s) → Docling (26s)
"""

import subprocess
import logging
from pathlib import Path
import tempfile
import shutil
from typing import Tuple, Optional, Dict
import time

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

logger = logging.getLogger(__name__)

# Minimum chars to consider extraction successful
MIN_CHARS_THRESHOLD = 50


class PDFOCRLayerHandler:
    """Handle PDF OCR layer detection and addition"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Check if ocrmypdf is available
        self.ocrmypdf_available = self._check_ocrmypdf()
        
    def _check_ocrmypdf(self) -> bool:
        """Check if ocrmypdf is installed"""
        try:
            result = subprocess.run(
                ['ocrmypdf', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.logger.warning("ocrmypdf not found - OCR layer addition disabled")
            return False
    
    def has_text_layer(self, pdf_path: str) -> Tuple[bool, int]:
        """
        Check if PDF has text layer
        
        Returns:
            Tuple[bool, int]: (has_text, total_chars)
        """
        try:
            doc = fitz.open(pdf_path)
            total_text = ""
            
            for page in doc:
                text = page.get_text()
                total_text += text
            
            doc.close()
            
            # Clean whitespace for accurate count
            char_count = len(total_text.strip())
            
            # Consider PDF has text layer if it has at least 50 characters
            has_text = char_count >= 50
            
            self.logger.info(
                f"PDF text layer check: {pdf_path.split('/')[-1]} - "
                f"{char_count} chars, has_text={has_text}"
            )
            
            return has_text, char_count
            
        except Exception as e:
            self.logger.error(f"Error checking PDF text layer: {e}")
            return False, 0
    
    def add_ocr_layer(self, input_pdf: str, output_pdf: Optional[str] = None,
                     languages: str = "ces+eng+deu") -> Tuple[bool, str]:
        """
        Add OCR layer to PDF using ocrmypdf
        
        Args:
            input_pdf: Input PDF file path
            output_pdf: Output PDF file path (if None, creates temp file)
            languages: OCR languages (ces=Czech, eng=English, deu=German)
            
        Returns:
            Tuple[bool, str]: (success, output_file_path)
        """
        if not self.ocrmypdf_available:
            self.logger.error("ocrmypdf not available - cannot add OCR layer")
            return False, input_pdf
        
        # Create output file if not specified
        if output_pdf is None:
            temp_dir = tempfile.gettempdir()
            input_path = Path(input_pdf)
            output_pdf = str(Path(temp_dir) / f"{input_path.stem}_ocr{input_path.suffix}")
        
        try:
            self.logger.info(f"Adding OCR layer to: {Path(input_pdf).name}")
            
            # Run ocrmypdf
            # Note: --skip-text, --force-ocr, --redo-ocr are mutually exclusive
            # For scanned PDFs without text, use --force-ocr
            cmd = [
                'ocrmypdf',
                '--language', languages,
                '--force-ocr',  # Force OCR (for scanned PDFs without text layer)
                '--optimize', '1',  # Basic optimization
                '--output-type', 'pdf',
                '--clean',  # Clean pages before OCR
                '--deskew',  # Deskew pages
                '--rotate-pages',  # Auto-rotate pages
                '--jobs', '1',  # Single job (stable)
                input_pdf,
                output_pdf
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per PDF
            )
            
            if result.returncode == 0:
                self.logger.info(f"✅ OCR layer added successfully: {Path(output_pdf).name}")
                return True, output_pdf
            else:
                self.logger.error(
                    f"❌ ocrmypdf failed (code {result.returncode}): "
                    f"{result.stderr[:200]}"
                )
                return False, input_pdf
                
        except subprocess.TimeoutExpired:
            self.logger.error("⏱️  OCR timeout (5 minutes)")
            return False, input_pdf
        except Exception as e:
            self.logger.error(f"❌ Error adding OCR layer: {e}")
            return False, input_pdf
    
    def process_pdf_with_ocr(self, pdf_path: str, 
                            force_ocr: bool = False) -> Tuple[bool, str]:
        """
        Process PDF and add OCR layer if needed
        
        Args:
            pdf_path: PDF file path
            force_ocr: Force OCR even if text layer exists
            
        Returns:
            Tuple[bool, str]: (ocr_added, output_file_path)
        """
        # Check if PDF has text layer
        has_text, char_count = self.has_text_layer(pdf_path)
        
        if has_text and not force_ocr:
            self.logger.info(f"📄 PDF already has text layer ({char_count} chars): {Path(pdf_path).name}")
            return False, pdf_path
        
        # Add OCR layer
        self.logger.info(f"🔍 Adding OCR layer to PDF ({char_count} chars): {Path(pdf_path).name}")
        success, output_path = self.add_ocr_layer(pdf_path)
        
        return success, output_path
    
    def batch_process_directory(self, input_dir: str, output_dir: str = None,
                               pattern: str = "*.pdf") -> Dict:
        """
        Batch process directory of PDFs
        
        Args:
            input_dir: Input directory
            output_dir: Output directory (if None, overwrites original)
            pattern: File pattern (default: *.pdf)
            
        Returns:
            Dict with processing statistics
        """
        from pathlib import Path
        
        input_path = Path(input_dir)
        pdf_files = list(input_path.glob(pattern))
        
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = None
        
        stats = {
            "total": len(pdf_files),
            "already_had_text": 0,
            "ocr_added": 0,
            "ocr_failed": 0,
            "processed_files": []
        }
        
        for i, pdf_file in enumerate(pdf_files, 1):
            self.logger.info(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
            
            # Check text layer
            has_text, char_count = self.has_text_layer(str(pdf_file))
            
            if has_text:
                stats["already_had_text"] += 1
                stats["processed_files"].append({
                    "file": pdf_file.name,
                    "status": "already_had_text",
                    "chars": char_count
                })
                continue
            
            # Add OCR
            if output_path:
                output_file = str(output_path / pdf_file.name)
            else:
                output_file = str(pdf_file)
            
            success, result_file = self.add_ocr_layer(str(pdf_file), output_file)
            
            if success:
                stats["ocr_added"] += 1
                stats["processed_files"].append({
                    "file": pdf_file.name,
                    "status": "ocr_added",
                    "output": result_file
                })
            else:
                stats["ocr_failed"] += 1
                stats["processed_files"].append({
                    "file": pdf_file.name,
                    "status": "ocr_failed"
                })
        
        return stats


# Convenience function
def ensure_pdf_has_ocr(pdf_path: str) -> str:
    """
    Ensure PDF has OCR layer, add if missing

    Args:
        pdf_path: PDF file path

    Returns:
        Path to PDF with OCR layer (may be original if already had text)
    """
    handler = PDFOCRLayerHandler()
    _, output_path = handler.process_pdf_with_ocr(pdf_path)
    return output_path


class OptimalTextExtractor:
    """
    Optimální fallback řetězec pro extrakci textu

    Benchmark výsledky (96 dokumentů):
      - pdftotext: 10ms průměr, 100% pro PDF s textem
      - Tesseract: 1,231ms průměr, 100% pro vše
      - Docling: 26,275ms průměr, 100% pro vše (nejvyšší kvalita)

    Strategie:
      PDF: pdftotext → Tesseract → Docling
      Obrázky: Tesseract → Docling
    """

    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}
    PDF_EXTENSION = '.pdf'

    def __init__(self, min_chars: int = MIN_CHARS_THRESHOLD):
        self.min_chars = min_chars
        self.logger = logging.getLogger(__name__)
        self._log_available_methods()

    def _log_available_methods(self):
        """Log which extraction methods are available"""
        methods = []
        if PYMUPDF_AVAILABLE:
            methods.append("pdftotext")
        if TESSERACT_AVAILABLE:
            methods.append("Tesseract")
        if DOCLING_AVAILABLE:
            methods.append("Docling")
        self.logger.info(f"Available extraction methods: {', '.join(methods) or 'NONE'}")

    def extract_with_pdftotext(self, file_path: str) -> Tuple[str, float]:
        """
        Extract text using PyMuPDF (pdftotext equivalent)

        Returns:
            Tuple[text, time_ms]
        """
        if not PYMUPDF_AVAILABLE:
            return "", 0

        start = time.time()
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            elapsed = (time.time() - start) * 1000
            return text.strip(), elapsed
        except Exception as e:
            self.logger.warning(f"pdftotext failed: {e}")
            return "", (time.time() - start) * 1000

    def extract_with_tesseract(self, file_path: str, lang: str = "ces+eng+deu") -> Tuple[str, float]:
        """
        Extract text using Tesseract OCR

        Returns:
            Tuple[text, time_ms]
        """
        if not TESSERACT_AVAILABLE:
            return "", 0

        start = time.time()
        try:
            ext = Path(file_path).suffix.lower()

            if ext == '.pdf':
                # Convert PDF to images first
                from pdf2image import convert_from_path
                images = convert_from_path(file_path, dpi=150)
                text_parts = []
                for img in images:
                    text_parts.append(pytesseract.image_to_string(img, lang=lang))
                text = "\n".join(text_parts)
            else:
                # Direct image OCR
                img = Image.open(file_path)
                text = pytesseract.image_to_string(img, lang=lang)

            elapsed = (time.time() - start) * 1000
            return text.strip(), elapsed
        except Exception as e:
            self.logger.warning(f"Tesseract failed: {e}")
            return "", (time.time() - start) * 1000

    def extract_with_docling(self, file_path: str) -> Tuple[str, float]:
        """
        Extract text using Docling (IBM AI)

        Returns:
            Tuple[text, time_ms]
        """
        if not DOCLING_AVAILABLE:
            return "", 0

        start = time.time()
        try:
            converter = DocumentConverter()
            result = converter.convert(file_path)
            text = result.document.export_to_markdown()
            elapsed = (time.time() - start) * 1000
            return text.strip(), elapsed
        except Exception as e:
            self.logger.warning(f"Docling failed: {e}")
            return "", (time.time() - start) * 1000

    def extract_text(self, file_path: str) -> Dict:
        """
        Extract text using optimal fallback chain

        Args:
            file_path: Path to document (PDF or image)

        Returns:
            Dict with:
                - text: Extracted text
                - method: Method that succeeded
                - time_ms: Total extraction time
                - attempts: List of attempted methods
                - success: Whether extraction succeeded
        """
        ext = Path(file_path).suffix.lower()
        attempts = []
        total_time = 0

        # Determine extraction order based on file type
        if ext == self.PDF_EXTENSION:
            # PDF: pdftotext → Tesseract → Docling
            methods = [
                ("pdftotext", self.extract_with_pdftotext),
                ("tesseract", self.extract_with_tesseract),
                ("docling", self.extract_with_docling),
            ]
        elif ext in self.IMAGE_EXTENSIONS:
            # Images: Tesseract → Docling
            methods = [
                ("tesseract", self.extract_with_tesseract),
                ("docling", self.extract_with_docling),
            ]
        else:
            # Unknown: Try all
            methods = [
                ("pdftotext", self.extract_with_pdftotext),
                ("tesseract", self.extract_with_tesseract),
                ("docling", self.extract_with_docling),
            ]

        self.logger.info(f"Extracting: {Path(file_path).name} (type: {ext})")

        for method_name, method_func in methods:
            text, time_ms = method_func(file_path)
            total_time += time_ms
            char_count = len(text)

            attempt = {
                "method": method_name,
                "chars": char_count,
                "time_ms": round(time_ms, 1),
                "success": char_count >= self.min_chars
            }
            attempts.append(attempt)

            if char_count >= self.min_chars:
                self.logger.info(
                    f"  SUCCESS: {method_name} extracted {char_count} chars in {time_ms:.0f}ms"
                )
                return {
                    "text": text,
                    "method": method_name,
                    "time_ms": round(total_time, 1),
                    "char_count": char_count,
                    "attempts": attempts,
                    "success": True
                }
            else:
                self.logger.info(
                    f"  {method_name}: only {char_count} chars (need {self.min_chars}), trying next..."
                )

        # All methods failed
        self.logger.warning(f"  FAILED: All extraction methods failed for {Path(file_path).name}")

        # Return best result we got
        best = max(attempts, key=lambda x: x["chars"]) if attempts else None
        best_text = ""
        if best and best["chars"] > 0:
            # Re-extract with best method to get text
            for method_name, method_func in methods:
                if method_name == best["method"]:
                    best_text, _ = method_func(file_path)
                    break

        return {
            "text": best_text,
            "method": best["method"] if best else "none",
            "time_ms": round(total_time, 1),
            "char_count": len(best_text),
            "attempts": attempts,
            "success": False
        }


# Global instance for convenience
_extractor = None

def extract_text_optimal(file_path: str) -> Dict:
    """
    Convenience function for optimal text extraction

    Args:
        file_path: Path to document

    Returns:
        Dict with extraction result
    """
    global _extractor
    if _extractor is None:
        _extractor = OptimalTextExtractor()
    return _extractor.extract_text(file_path)
