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
Production Email Scanner - FAST Version (bez LLM volání)
=========================================================
Rychlá verze bez AI Voting - používá pouze keyword klasifikaci.
10-20x rychlejší než verze s Ollama LLM.

Author: Claude Code
Date: 2025-12-04
"""

import sys
import json
import mailbox
import email
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any

# Add src paths
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ai'))

from universal_business_classifier import UniversalBusinessClassifier
from data_extractors import create_extractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Instance %(instance_id)s] - %(levelname)s - %(message)s'
)


class FastEmailScanner:
    """Fast email scanner - NO LLM calls, keyword classification only"""

    def __init__(self, mbox_path: str, output_dir: str,
                 start_email: int = 0, end_email: int = None,
                 instance_id: int = 0):
        self.mbox_path = Path(mbox_path)
        self.output_dir = Path(output_dir)
        self.start_email = start_email
        self.end_email = end_email
        self.instance_id = instance_id

        # Create instance-specific output directory
        self.instance_dir = self.output_dir / f"instance_{instance_id}"
        self.instance_dir.mkdir(parents=True, exist_ok=True)

        # Setup logger with instance ID
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__),
            {'instance_id': instance_id}
        )

        # Initialize components - FAST MODE (no LLM)
        self.logger.info(f"🚀 Initializing FAST Email Scanner Instance {instance_id}")
        self.logger.info(f"   Email range: {start_email} - {end_email or 'END'}")
        self.logger.info(f"   Mode: FAST (keyword classification, no LLM)")

        self.classifier = UniversalBusinessClassifier()

        self.logger.info(f"✅ Classifier: {len(self.classifier.patterns)} document types")
        self.logger.info(f"✅ Mode: FAST (no AI voting = 10-20x faster)")

        # Statistics
        self.stats = {
            'instance_id': instance_id,
            'start_email': start_email,
            'end_email': end_email,
            'total_emails': 0,
            'emails_with_attachments': 0,
            'pdfs_extracted': 0,
            'documents_classified': 0,
            'documents_extracted': 0,
            'by_type': {},
            'processing_times': []
        }

        # Results storage
        self.results = []

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF using pdftotext (fast)"""
        try:
            result = subprocess.run(
                ['pdftotext', '-layout', str(pdf_path), '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
            return ""
        except Exception as e:
            self.logger.error(f"pdftotext failed: {e}")
            return ""

    def scan_mbox(self) -> List[Tuple[int, email.message.EmailMessage]]:
        """Scan mbox for emails with PDF attachments in specified range"""

        self.logger.info(f"📧 Scanning mbox: {self.mbox_path.name}")
        self.logger.info(f"   Range: emails {self.start_email} to {self.end_email or 'END'}")

        mbox = mailbox.mbox(str(self.mbox_path))
        emails_with_pdfs = []

        for idx, msg in enumerate(mbox):
            # Skip emails before start_email
            if idx < self.start_email:
                continue

            # Stop at end_email
            if self.end_email and idx >= self.end_email:
                self.logger.info(f"   Reached end email limit: {self.end_email}")
                break

            if (idx - self.start_email) % 5000 == 0 and idx > self.start_email:
                self.logger.info(f"   Scanned {idx - self.start_email} emails, found {len(emails_with_pdfs)} with PDFs...")

            # Check for PDF attachments
            has_pdf = False
            for part in msg.walk():
                if part.get_content_type() == 'application/pdf':
                    has_pdf = True
                    break

                filename = part.get_filename()
                if filename and filename.lower().endswith('.pdf'):
                    has_pdf = True
                    break

            if has_pdf:
                emails_with_pdfs.append((idx, msg))

        self.stats['total_emails'] = idx - self.start_email + 1 if idx >= self.start_email else 0
        self.stats['emails_with_attachments'] = len(emails_with_pdfs)

        self.logger.info(f"📊 Scan complete:")
        self.logger.info(f"   Total emails scanned: {self.stats['total_emails']}")
        self.logger.info(f"   Emails with PDFs: {self.stats['emails_with_attachments']}")

        return emails_with_pdfs

    def extract_pdf_attachments(self, msg: email.message.EmailMessage, email_id: int) -> List[Path]:
        """Extract PDF attachments from email"""

        pdf_files = []
        attachment_num = 0

        for part in msg.walk():
            if part.get_content_type() == 'application/pdf':
                attachment_num += 1
                filename = part.get_filename()

                if not filename:
                    filename = f"email_{email_id}_attachment_{attachment_num}.pdf"

                # Sanitize filename
                safe_filename = f"{email_id:06d}_{filename}"
                pdf_path = self.instance_dir / safe_filename

                # Save PDF
                try:
                    with open(pdf_path, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    pdf_files.append(pdf_path)
                    self.stats['pdfs_extracted'] += 1
                except Exception as e:
                    self.logger.error(f"   Failed to save PDF: {e}")

        return pdf_files

    def process_pdf(self, pdf_path: Path, email_id: int) -> Dict[str, Any]:
        """Process single PDF through FAST pipeline (no LLM)"""

        start_time = datetime.now()
        result = {
            'instance_id': self.instance_id,
            'email_id': email_id,
            'pdf_path': str(pdf_path),
            'filename': pdf_path.name,
            'success': False,
            'doc_type': None,
            'confidence': 0,
            'items_extracted': 0,
            'processing_time': 0
        }

        try:
            # 1. Extract text using pdftotext (fast)
            text = self.extract_text_from_pdf(pdf_path)

            if not text or len(text) < 50:
                result['error'] = 'Insufficient text extracted'
                result['text_length'] = len(text) if text else 0
                return result

            result['text_length'] = len(text)

            # 2. Classify document (keyword-based, fast)
            doc_type, confidence, details = self.classifier.classify(text)
            result['doc_type'] = str(doc_type).replace('DocumentType.', '')
            result['confidence'] = confidence
            result['matched_keywords'] = details.get('matched_keywords', [])[:5]

            if doc_type == 'unknown' or confidence < 50:
                result['error'] = 'Unknown or low confidence document type'
                return result

            self.stats['documents_classified'] += 1
            doc_type_str = str(doc_type).replace('DocumentType.', '')

            if doc_type_str not in self.stats['by_type']:
                self.stats['by_type'][doc_type_str] = {
                    'count': 0,
                    'extracted': 0
                }
            self.stats['by_type'][doc_type_str]['count'] += 1

            # 3. Extract structured data (no LLM)
            if doc_type_str.lower() in ['invoice', 'receipt', 'bank_statement']:
                extractor = create_extractor(doc_type_str.lower())
                local_result = extractor.extract(text)

                # Get item count
                if doc_type_str.lower() == 'invoice':
                    items = len(local_result.get('line_items', []))
                    result['total_gross'] = local_result.get('summary', {}).get('total_gross')
                elif doc_type_str.lower() == 'receipt':
                    items = len(local_result.get('items', []))
                    result['total'] = local_result.get('total')
                else:
                    items = len(local_result.get('transactions', []))

                result['items_extracted'] = items
                result['extraction_confidence'] = local_result.get('extraction_confidence', 0)

                if items > 0:
                    self.stats['documents_extracted'] += 1
                    self.stats['by_type'][doc_type_str]['extracted'] += 1

            result['success'] = True

        except Exception as e:
            self.logger.error(f"   Processing failed: {e}")
            result['error'] = str(e)

        # Processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        result['processing_time'] = processing_time
        self.stats['processing_times'].append(processing_time)

        return result

    def run(self):
        """Main processing loop"""

        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"🚀 FAST EMAIL SCANNER - INSTANCE {self.instance_id} STARTING")
        self.logger.info("=" * 80)
        self.logger.info(f"Mbox: {self.mbox_path}")
        self.logger.info(f"Email range: {self.start_email} - {self.end_email or 'END'}")
        self.logger.info(f"Output: {self.instance_dir}")
        self.logger.info(f"Mode: FAST (no LLM = 10-20x faster)")
        self.logger.info("=" * 80 + "\n")

        scan_start = datetime.now()

        # Phase 1: Scan mbox for PDFs
        self.logger.info("📧 PHASE 1: Scanning emails for PDF attachments...")
        emails_with_pdfs = self.scan_mbox()

        if not emails_with_pdfs:
            self.logger.warning("⚠️  No emails with PDF attachments found!")
            self.save_results()
            return

        # Phase 2: Extract PDFs
        self.logger.info(f"\n📄 PHASE 2: Extracting PDF attachments...")
        all_pdfs = []
        for email_id, msg in emails_with_pdfs:
            pdfs = self.extract_pdf_attachments(msg, email_id)
            all_pdfs.extend([(email_id, pdf) for pdf in pdfs])

        self.logger.info(f"   Extracted {len(all_pdfs)} PDF files")

        # Phase 3: Process PDFs (FAST - no LLM)
        self.logger.info(f"\n🔍 PHASE 3: Processing PDFs (FAST mode)...")

        for idx, (email_id, pdf_path) in enumerate(all_pdfs, 1):
            if idx % 50 == 0 or idx == 1:
                elapsed = (datetime.now() - scan_start).total_seconds()
                rate = idx / elapsed if elapsed > 0 else 0
                eta = (len(all_pdfs) - idx) / rate if rate > 0 else 0
                self.logger.info(f"[{idx}/{len(all_pdfs)}] {pdf_path.name[:40]} | Rate: {rate:.1f} docs/s | ETA: {eta/60:.1f} min")

            result = self.process_pdf(pdf_path, email_id)
            self.results.append(result)

        # Phase 4: Save results
        self.logger.info(f"\n💾 PHASE 4: Saving results...")
        self.save_results()

        # Phase 5: Final statistics
        total_time = (datetime.now() - scan_start).total_seconds()
        self.logger.info(f"\n" + "=" * 80)
        self.logger.info(f"📊 INSTANCE {self.instance_id} - FINAL STATISTICS")
        self.logger.info("=" * 80)
        self.print_statistics()
        self.logger.info(f"\n⏱️  Total time: {total_time/60:.1f} minutes")
        self.logger.info(f"📈 Rate: {len(all_pdfs)/total_time:.1f} documents/second")

    def save_results(self):
        """Save results to JSON"""

        output_file = self.instance_dir / f'instance_{self.instance_id}_results.json'

        report = {
            'scan_date': datetime.now().isoformat(),
            'instance_id': self.instance_id,
            'start_email': self.start_email,
            'end_email': self.end_email,
            'mode': 'FAST (no LLM)',
            'statistics': self.stats,
            'results': self.results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self.logger.info(f"   ✅ Results saved to: {output_file}")

    def print_statistics(self):
        """Print final statistics"""

        stats = self.stats

        self.logger.info(f"\n📧 Email Processing:")
        self.logger.info(f"   Email range: {stats['start_email']} - {stats['end_email']}")
        self.logger.info(f"   Total emails scanned: {stats['total_emails']}")
        self.logger.info(f"   Emails with PDFs: {stats['emails_with_attachments']}")
        self.logger.info(f"   PDFs extracted: {stats['pdfs_extracted']}")

        self.logger.info(f"\n🔍 Document Processing:")
        self.logger.info(f"   Documents classified: {stats['documents_classified']}")
        self.logger.info(f"   Documents extracted: {stats['documents_extracted']}")

        if stats['by_type']:
            self.logger.info(f"\n📋 By Document Type:")
            for doc_type, type_stats in stats['by_type'].items():
                self.logger.info(f"   {doc_type}: {type_stats['count']} classified, {type_stats['extracted']} extracted")

        if stats['processing_times']:
            import statistics
            times = stats['processing_times']
            self.logger.info(f"\n⏱️  Processing Time per Document:")
            self.logger.info(f"   Average: {statistics.mean(times)*1000:.0f}ms")
            self.logger.info(f"   Median: {statistics.median(times)*1000:.0f}ms")

        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"✅ INSTANCE {self.instance_id} COMPLETE")
        self.logger.info("=" * 80)


def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(description='Fast Email Scanner (no LLM)')
    parser.add_argument('--mbox-path', type=str, required=True,
                        help='Path to mbox file')
    parser.add_argument('--output-dir', type=str, required=True,
                        help='Output directory')
    parser.add_argument('--start-email', type=int, default=0,
                        help='Start email index (default: 0)')
    parser.add_argument('--end-email', type=int, default=None,
                        help='End email index (default: None = process all)')
    parser.add_argument('--instance-id', type=int, default=0,
                        help='Instance ID for parallel processing (default: 0)')

    args = parser.parse_args()

    # Create scanner
    scanner = FastEmailScanner(
        mbox_path=args.mbox_path,
        output_dir=args.output_dir,
        start_email=args.start_email,
        end_email=args.end_email,
        instance_id=args.instance_id
    )

    # Run scan
    scanner.run()


if __name__ == "__main__":
    main()
