#!/usr/bin/env python3
"""
PDF OCR Layer Handler
Detects if PDF has text layer and adds OCR if needed
"""

import subprocess
import logging
from pathlib import Path
import tempfile
import shutil
from typing import Tuple, Optional
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


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
            cmd = [
                'ocrmypdf',
                '--language', languages,
                '--skip-text',  # Skip pages that already have text
                '--optimize', '1',  # Basic optimization
                '--output-type', 'pdf',
                '--force-ocr',  # Force OCR even if text exists
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
