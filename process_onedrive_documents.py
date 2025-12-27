#!/usr/bin/env python3
"""
NAS5 Docker Apps Collection
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
Process OneDrive Documents with Duplicate Detection + OCR
=========================================================
Processes PDF/JPG documents from ACASIS OneDrive backup folder.
Uses MD5 hash and text similarity to detect duplicates.
Adds OCR layer to scanned PDFs using ocrmypdf.

Author: Claude Code
Date: 2025-12-04
"""

import sys
import json
import hashlib
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Set, Optional
from difflib import SequenceMatcher

# Add src paths
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ai'))

from universal_business_classifier import UniversalBusinessClassifier
from data_extractors import create_extractor
from pdf_ocr_layer import PDFOCRLayerHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detect duplicate documents using multiple methods"""

    def __init__(self):
        self.file_hashes: Dict[str, str] = {}  # hash -> filename
        self.text_hashes: Dict[int, str] = {}  # text_hash -> filename
        self.seen_texts: List[Tuple[str, str]] = []  # (text_snippet, filename)

    def get_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_text_hash(self, text: str) -> int:
        """Get hash of normalized text"""
        # Normalize: lowercase, remove whitespace
        normalized = ''.join(text.lower().split())
        return hash(normalized[:2000])  # First 2000 chars

    def text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity ratio"""
        # Use first 1000 chars for speed
        return SequenceMatcher(None, text1[:1000], text2[:1000]).ratio()

    def is_duplicate(self, file_path: Path, text: str) -> Tuple[bool, str, str]:
        """
        Check if document is duplicate.
        Returns: (is_duplicate, method, original_file)
        """
        # Method 1: File hash (exact duplicate)
        file_hash = self.get_file_hash(file_path)
        if file_hash in self.file_hashes:
            return True, "file_hash", self.file_hashes[file_hash]

        # Method 2: Text hash (same content, different file)
        if text and len(text) > 100:
            text_hash = self.get_text_hash(text)
            if text_hash in self.text_hashes:
                return True, "text_hash", self.text_hashes[text_hash]

            # Method 3: Text similarity (similar content)
            text_snippet = text[:1000]
            for seen_text, seen_file in self.seen_texts:
                similarity = self.text_similarity(text_snippet, seen_text)
                if similarity > 0.95:  # 95% similar
                    return True, f"similarity_{similarity:.0%}", seen_file

            # Not a duplicate - register this document
            self.text_hashes[text_hash] = str(file_path.name)
            self.seen_texts.append((text_snippet, str(file_path.name)))

        self.file_hashes[file_hash] = str(file_path.name)
        return False, "", ""


class OneDriveDocumentProcessor:
    """Process OneDrive documents with classification, extraction and OCR"""

    def __init__(self, source_dir: str, output_file: str, enable_ocr: bool = True):
        self.source_dir = Path(source_dir)
        self.output_file = Path(output_file)
        self.enable_ocr = enable_ocr

        # Initialize components
        self.classifier = UniversalBusinessClassifier()
        self.duplicate_detector = DuplicateDetector()

        # Initialize OCR handler
        self.ocr_handler = None
        if enable_ocr:
            try:
                self.ocr_handler = PDFOCRLayerHandler()
                if self.ocr_handler.ocrmypdf_available:
                    logger.info("✅ OCR: ocrmypdf available")
                else:
                    logger.warning("⚠️  OCR: ocrmypdf not available, falling back to tesseract")
            except Exception as e:
                logger.warning(f"⚠️  OCR init failed: {e}")

        logger.info(f"✅ Source: {self.source_dir}")
        logger.info(f"✅ Output: {self.output_file}")
        logger.info(f"✅ Classifier: {len(self.classifier.patterns)} document types")

        # Statistics
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'duplicates': 0,
            'classified': 0,
            'extracted': 0,
            'ocr_added': 0,
            'errors': 0,
            'by_type': {},
            'duplicate_details': []
        }

        self.results = []

    def find_documents(self) -> List[Path]:
        """Find all PDF and image files"""
        files = []

        # PDF files
        files.extend(self.source_dir.glob("**/*.pdf"))
        files.extend(self.source_dir.glob("**/*.PDF"))

        # Image files (scanned documents)
        for ext in ['jpg', 'jpeg', 'png', 'JPG', 'JPEG', 'PNG']:
            files.extend(self.source_dir.glob(f"**/*.{ext}"))

        # Remove duplicates and sort
        files = list(set(files))
        files.sort(key=lambda x: x.name)

        logger.info(f"📄 Found {len(files)} documents")
        return files

    def extract_text(self, file_path: Path) -> Tuple[str, bool]:
        """Extract text from PDF or image. Returns (text, ocr_was_used)"""
        suffix = file_path.suffix.lower()

        if suffix == '.pdf':
            return self._extract_text_from_pdf(file_path)
        elif suffix in ['.jpg', '.jpeg', '.png']:
            text = self._extract_text_from_image(file_path)
            return text, True  # Images always use OCR
        return "", False

    def _extract_text_from_pdf(self, pdf_path: Path) -> Tuple[str, bool]:
        """
        Extract text from PDF using pdftotext, with OCR fallback.
        Returns: (text, ocr_was_used)
        """
        ocr_used = False

        # First try pdftotext
        try:
            result = subprocess.run(
                ['pdftotext', '-layout', str(pdf_path), '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                # Check if we got meaningful text
                if len(text) >= 50:
                    return text, False
        except Exception as e:
            logger.debug(f"pdftotext failed for {pdf_path.name}: {e}")

        # If no text, try OCR
        if self.enable_ocr and self.ocr_handler:
            logger.info(f"   🔍 No text layer, running OCR on {pdf_path.name}...")
            try:
                # Check if PDF has text layer
                has_text, char_count = self.ocr_handler.has_text_layer(str(pdf_path))

                if not has_text or char_count < 50:
                    # Add OCR layer
                    success, ocr_pdf_path = self.ocr_handler.add_ocr_layer(str(pdf_path))

                    if success:
                        ocr_used = True
                        self.stats['ocr_added'] += 1
                        # Extract text from OCR'd PDF
                        result = subprocess.run(
                            ['pdftotext', '-layout', ocr_pdf_path, '-'],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            text = result.stdout.strip()
                            logger.info(f"   ✅ OCR extracted {len(text)} chars")
                            return text, True
            except Exception as e:
                logger.error(f"   ❌ OCR failed for {pdf_path.name}: {e}")

        # Fallback: try tesseract directly on PDF converted to image
        return self._ocr_pdf_with_tesseract(pdf_path)

    def _ocr_pdf_with_tesseract(self, pdf_path: Path) -> Tuple[str, bool]:
        """Fallback OCR using pdftoppm + tesseract"""
        import tempfile
        import os

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Convert PDF to images
                result = subprocess.run(
                    ['pdftoppm', '-png', '-r', '300', str(pdf_path), f'{temp_dir}/page'],
                    capture_output=True,
                    timeout=120
                )

                if result.returncode != 0:
                    return "", False

                # OCR each page
                all_text = []
                for img_file in sorted(Path(temp_dir).glob('page-*.png')):
                    result = subprocess.run(
                        ['tesseract', str(img_file), 'stdout', '-l', 'ces+eng+deu'],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode == 0:
                        all_text.append(result.stdout)

                if all_text:
                    text = '\n\n'.join(all_text)
                    logger.info(f"   ✅ Tesseract OCR extracted {len(text)} chars")
                    return text, True

        except FileNotFoundError:
            logger.debug("pdftoppm or tesseract not found")
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")

        return "", False

    def _extract_text_from_image(self, image_path: Path) -> str:
        """Extract text from image using tesseract OCR"""
        try:
            result = subprocess.run(
                ['tesseract', str(image_path), 'stdout', '-l', 'ces+eng'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return result.stdout
            return ""
        except FileNotFoundError:
            logger.warning("tesseract not found, skipping OCR")
            return ""
        except Exception as e:
            logger.error(f"OCR failed for {image_path.name}: {e}")
            return ""

    def process_document(self, file_path: Path) -> Dict[str, Any]:
        """Process single document"""
        result = {
            'file': str(file_path.name),
            'path': str(file_path),
            'size': file_path.stat().st_size,
            'success': False,
            'is_duplicate': False,
            'doc_type': None,
            'confidence': 0,
            'extracted_data': None,
            'ocr_used': False
        }

        try:
            # Step 1: Extract text (with OCR if needed)
            text, ocr_used = self.extract_text(file_path)
            result['text_length'] = len(text) if text else 0
            result['ocr_used'] = ocr_used

            if not text or len(text) < 50:
                result['error'] = 'No text extracted'
                return result

            # Step 2: Check for duplicates
            is_dup, dup_method, dup_original = self.duplicate_detector.is_duplicate(file_path, text)

            if is_dup:
                result['is_duplicate'] = True
                result['duplicate_method'] = dup_method
                result['duplicate_of'] = dup_original
                self.stats['duplicates'] += 1
                self.stats['duplicate_details'].append({
                    'file': file_path.name,
                    'method': dup_method,
                    'original': dup_original
                })
                logger.info(f"   ⏭️  DUPLICATE ({dup_method}): {file_path.name} = {dup_original}")
                result['success'] = True
                return result

            # Step 3: Classify document
            doc_type, confidence, details = self.classifier.classify(text)
            result['doc_type'] = str(doc_type).replace('DocumentType.', '')
            result['confidence'] = confidence
            result['matched_keywords'] = details.get('matched_keywords', [])[:5]

            if doc_type == 'unknown' or confidence < 50:
                result['error'] = 'Unknown document type'
                return result

            self.stats['classified'] += 1
            doc_type_str = result['doc_type']

            if doc_type_str not in self.stats['by_type']:
                self.stats['by_type'][doc_type_str] = {'count': 0, 'extracted': 0}
            self.stats['by_type'][doc_type_str]['count'] += 1

            # Step 4: Extract structured data
            if doc_type_str.lower() in ['invoice', 'receipt', 'bank_statement']:
                extractor = create_extractor(doc_type_str.lower())
                extraction = extractor.extract(text)

                # Count items
                if doc_type_str.lower() == 'invoice':
                    items = len(extraction.get('line_items', []))
                    result['total'] = extraction.get('summary', {}).get('total_gross')
                elif doc_type_str.lower() == 'receipt':
                    items = len(extraction.get('items', []))
                    result['total'] = extraction.get('total')
                else:
                    items = len(extraction.get('transactions', []))

                result['items_extracted'] = items
                result['extracted_data'] = extraction

                if items > 0:
                    self.stats['extracted'] += 1
                    self.stats['by_type'][doc_type_str]['extracted'] += 1

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)
            self.stats['errors'] += 1
            logger.error(f"   ❌ Error processing {file_path.name}: {e}")

        return result

    def run(self):
        """Main processing loop"""
        logger.info("\n" + "=" * 80)
        logger.info("🔍 ONEDRIVE DOCUMENT PROCESSOR")
        logger.info("=" * 80)
        logger.info(f"Source: {self.source_dir}")
        logger.info(f"Features: Duplicate detection, Classification, Extraction")
        logger.info("=" * 80 + "\n")

        start_time = datetime.now()

        # Find documents
        documents = self.find_documents()
        self.stats['total_files'] = len(documents)

        if not documents:
            logger.warning("⚠️  No documents found!")
            return

        # Process each document
        for idx, doc_path in enumerate(documents, 1):
            logger.info(f"[{idx}/{len(documents)}] {doc_path.name}")

            result = self.process_document(doc_path)
            self.results.append(result)
            self.stats['processed'] += 1

            if result['success'] and not result['is_duplicate']:
                logger.info(f"   ✅ {result['doc_type']} (conf: {result['confidence']})")

        # Save results
        self.save_results()

        # Print summary
        total_time = (datetime.now() - start_time).total_seconds()
        self.print_summary(total_time)

    def save_results(self):
        """Save results to JSON"""
        report = {
            'scan_date': datetime.now().isoformat(),
            'source_dir': str(self.source_dir),
            'statistics': self.stats,
            'results': self.results
        }

        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"💾 Results saved: {self.output_file}")

    def print_summary(self, total_time: float):
        """Print processing summary"""
        s = self.stats

        logger.info("\n" + "=" * 80)
        logger.info("📊 PROCESSING SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total files: {s['total_files']}")
        logger.info(f"Processed: {s['processed']}")
        logger.info(f"Duplicates: {s['duplicates']}")
        logger.info(f"Classified: {s['classified']}")
        logger.info(f"OCR added: {s['ocr_added']}")
        logger.info(f"Extracted: {s['extracted']}")
        logger.info(f"Errors: {s['errors']}")

        if s['by_type']:
            logger.info("\n📋 By Document Type:")
            for doc_type, stats in sorted(s['by_type'].items()):
                logger.info(f"   {doc_type}: {stats['count']} ({stats['extracted']} extracted)")

        if s['duplicate_details']:
            logger.info(f"\n🔄 Duplicates Found ({len(s['duplicate_details'])}):")
            for dup in s['duplicate_details'][:10]:
                logger.info(f"   {dup['file']} = {dup['original']} ({dup['method']})")
            if len(s['duplicate_details']) > 10:
                logger.info(f"   ... and {len(s['duplicate_details']) - 10} more")

        logger.info(f"\n⏱️  Total time: {total_time:.1f}s")
        logger.info(f"📈 Rate: {s['processed']/total_time:.1f} docs/s")
        logger.info("=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Process OneDrive documents')
    parser.add_argument('--source', type=str,
                        default='/Volumes/ACASIS/OneDrive_backup/1Naskenované_soubory',
                        help='Source directory')
    parser.add_argument('--output', type=str,
                        default='data/onedrive_extraction_results.json',
                        help='Output JSON file')

    args = parser.parse_args()

    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Process documents
    processor = OneDriveDocumentProcessor(args.source, args.output)
    processor.run()


if __name__ == "__main__":
    main()
