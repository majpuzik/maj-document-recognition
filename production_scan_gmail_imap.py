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
Production Email Scanner - Gmail IMAP
=====================================
Scans emails directly from Gmail IMAP server
Uses AI Consensus V2 (2 local Ollama models)

Author: Claude Code
Date: 2025-12-01
"""

import sys
import json
import email
import imaplib
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any
from email.header import decode_header

# Add src paths
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ai'))

from ai_consensus_trainer import AIVoter
from data_extractors import create_extractor
from universal_business_classifier import UniversalBusinessClassifier
from text_extractor_cascade import CascadeTextExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)


class GmailIMAPScanner:
    """Production email scanner using Gmail IMAP"""

    def __init__(self, output_dir: str, max_emails: int = 10000):
        self.output_dir = Path(output_dir)
        self.max_emails = max_emails
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components - PRODUCTION MODE (Ollama only)
        logger.info("🚀 Initializing Production Gmail IMAP Scanner V2")
        logger.info(f"   Mode: PRODUCTION (2 local Ollama models)")

        self.classifier = UniversalBusinessClassifier()
        self.voter = AIVoter(use_external_apis=False)  # Production: Ollama only

        # Config for text extractor
        config = {
            "ocr": {
                "cascade_threshold": 60.0,
                "min_text_length": 50
            }
        }
        self.text_extractor = CascadeTextExtractor(config)

        logger.info(f"✅ Classifier: {len(self.classifier.patterns)} document types")
        logger.info(f"✅ AI Voter: {len(self.voter.models)} models (Ollama only)")
        logger.info(f"✅ Max emails to process: {max_emails}")

        # Statistics
        self.stats = {
            'total_emails': 0,
            'emails_with_attachments': 0,
            'pdfs_extracted': 0,
            'documents_classified': 0,
            'documents_extracted': 0,
            'ai_validated': 0,
            'perfect_consensus': 0,
            'partial_consensus': 0,
            'no_consensus': 0,
            'by_type': {},
            'processing_times': []
        }

        # Results storage
        self.results = []

    def connect_gmail(self) -> imaplib.IMAP4_SSL:
        """Connect to Gmail IMAP server"""

        logger.info("📧 Connecting to Gmail IMAP...")

        # Gmail IMAP settings
        imap_host = 'imap.gmail.com'
        imap_port = 993

        # Get credentials from user
        email_address = input("Enter Gmail address: ").strip()

        # For security, use App Password (not main password)
        print("⚠️  Use App Password, not your main password!")
        print("   Generate at: https://myaccount.google.com/apppasswords")
        password = input("Enter App Password: ").strip()

        # Connect
        imap = imaplib.IMAP4_SSL(imap_host, imap_port)
        imap.login(email_address, password)

        logger.info("✅ Connected to Gmail IMAP")
        return imap

    def scan_imap(self, imap: imaplib.IMAP4_SSL) -> List[Tuple[int, bytes]]:
        """Scan IMAP for emails with PDF attachments"""

        # Select mailbox (ALL MAIL contains everything)
        logger.info("📧 Selecting [Gmail]/All Mail folder...")
        imap.select('"[Gmail]/All Mail"', readonly=True)

        # Search for ALL emails (or specific criteria)
        logger.info(f"🔍 Searching for emails (max {self.max_emails})...")
        status, messages = imap.search(None, 'ALL')

        if status != 'OK':
            logger.error("❌ Failed to search emails")
            return []

        email_ids = messages[0].split()
        logger.info(f"📊 Found {len(email_ids)} emails total")

        # Limit to max_emails (take most recent)
        if len(email_ids) > self.max_emails:
            email_ids = email_ids[-self.max_emails:]
            logger.info(f"   Limited to {self.max_emails} most recent emails")

        self.stats['total_emails'] = len(email_ids)

        # Fetch emails with PDF attachments
        emails_with_pdfs = []

        for i, email_id in enumerate(email_ids):
            if i % 100 == 0 and i > 0:
                logger.info(f"   Scanned {i}/{len(email_ids)} emails, found {len(emails_with_pdfs)} with PDFs...")

            # Fetch email
            status, msg_data = imap.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue

            # Parse email
            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)

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
                emails_with_pdfs.append((int(email_id), email_body))

        self.stats['emails_with_attachments'] = len(emails_with_pdfs)

        logger.info(f"📊 Scan complete:")
        logger.info(f"   Total emails scanned: {self.stats['total_emails']}")
        logger.info(f"   Emails with PDFs: {self.stats['emails_with_attachments']}")

        return emails_with_pdfs

    def extract_pdf_attachments(self, email_body: bytes, email_id: int) -> List[Path]:
        """Extract PDF attachments from email"""

        pdf_files = []
        attachment_num = 0

        msg = email.message_from_bytes(email_body)

        for part in msg.walk():
            if part.get_content_type() == 'application/pdf':
                attachment_num += 1
                filename = part.get_filename()

                if not filename:
                    filename = f"email_{email_id}_attachment_{attachment_num}.pdf"

                # Sanitize filename
                safe_filename = f"{email_id:06d}_{filename}"
                pdf_path = self.output_dir / safe_filename

                # Save PDF
                try:
                    with open(pdf_path, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    pdf_files.append(pdf_path)
                    self.stats['pdfs_extracted'] += 1
                except Exception as e:
                    logger.error(f"   Failed to save PDF: {e}")

        return pdf_files

    def process_pdf(self, pdf_path: Path, email_id: int) -> Dict[str, Any]:
        """Process single PDF through pipeline"""

        start_time = datetime.now()
        result = {
            'email_id': email_id,
            'pdf_path': str(pdf_path),
            'filename': pdf_path.name,
            'success': False,
            'doc_type': None,
            'confidence': 0,
            'items_extracted': 0,
            'ai_consensus': None,
            'processing_time': 0
        }

        try:
            # 1. Extract text
            extraction_result = self.text_extractor.extract_from_pdf(str(pdf_path))
            text = extraction_result.get('text', '')

            if not text or len(text) < 100:
                result['error'] = 'Insufficient text extracted'
                result['ocr_info'] = {
                    'confidence': extraction_result.get('confidence', 0),
                    'language': extraction_result.get('language_used', 'unknown'),
                    'pages': extraction_result.get('pages', 0)
                }
                return result

            # Store OCR metadata
            result['ocr_info'] = {
                'confidence': extraction_result.get('confidence', 0),
                'language': extraction_result.get('language_used', 'unknown'),
                'pages': extraction_result.get('pages', 0),
                'text_length': len(text)
            }

            # 2. Classify document
            doc_type, confidence, details = self.classifier.classify(text)
            result['doc_type'] = str(doc_type).replace('DocumentType.', '')
            result['confidence'] = confidence
            result['classification_details'] = details

            if doc_type == 'unknown':
                result['error'] = 'Unknown document type'
                return result

            self.stats['documents_classified'] += 1
            doc_type_str = str(doc_type).replace('DocumentType.', '')

            if doc_type_str not in self.stats['by_type']:
                self.stats['by_type'][doc_type_str] = {
                    'count': 0,
                    'extracted': 0,
                    'ai_validated': 0,
                    'perfect_consensus': 0
                }
            self.stats['by_type'][doc_type_str]['count'] += 1

            # 3. Extract structured data
            if doc_type in ['invoice', 'receipt', 'bank_statement']:
                extractor = create_extractor(doc_type)
                local_result = extractor.extract(text)

                # Get item count
                if doc_type == 'invoice':
                    items = len(local_result.get('line_items', []))
                elif doc_type == 'receipt':
                    items = len(local_result.get('items', []))
                else:
                    items = len(local_result.get('transactions', []))

                result['items_extracted'] = items
                result['local_extraction'] = local_result

                if items > 0:
                    self.stats['documents_extracted'] += 1
                    self.stats['by_type'][doc_type_str]['extracted'] += 1

                    # 4. AI Consensus Validation
                    try:
                        consensus, details = self.voter.vote(text, doc_type)

                        result['ai_consensus'] = {
                            'item_count': details['majority_count'],
                            'agreeing_models': details['agreeing_models'],
                            'consensus_strength': details['consensus_strength'],
                            'all_counts': details['item_counts']
                        }

                        self.stats['ai_validated'] += 1
                        self.stats['by_type'][doc_type_str]['ai_validated'] += 1

                        # Track consensus quality
                        if details['consensus_strength'] == 1.0:
                            self.stats['perfect_consensus'] += 1
                            self.stats['by_type'][doc_type_str]['perfect_consensus'] += 1
                        elif details['consensus_strength'] >= 0.5:
                            self.stats['partial_consensus'] += 1
                        else:
                            self.stats['no_consensus'] += 1

                    except Exception as e:
                        logger.error(f"   AI consensus failed: {e}")
                        result['ai_error'] = str(e)

            result['success'] = True

        except Exception as e:
            logger.error(f"   Processing failed: {e}")
            result['error'] = str(e)

        # Processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        result['processing_time'] = processing_time
        self.stats['processing_times'].append(processing_time)

        return result

    def run(self):
        """Main processing loop"""

        logger.info("\n" + "=" * 80)
        logger.info("🚀 PRODUCTION GMAIL IMAP SCANNER V2 - STARTING")
        logger.info("=" * 80)
        logger.info(f"Max emails: {self.max_emails}")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"AI Mode: PRODUCTION (2 local Ollama models)")
        logger.info("=" * 80 + "\n")

        # Phase 1: Connect to Gmail
        imap = self.connect_gmail()

        try:
            # Phase 2: Scan for PDFs
            logger.info("\n📧 PHASE 2: Scanning emails for PDF attachments...")
            emails_with_pdfs = self.scan_imap(imap)

            if not emails_with_pdfs:
                logger.warning("⚠️  No emails with PDF attachments found!")
                return

            # Phase 3: Extract PDFs
            logger.info(f"\n📄 PHASE 3: Extracting PDF attachments...")
            all_pdfs = []
            for email_id, email_body in emails_with_pdfs:
                pdfs = self.extract_pdf_attachments(email_body, email_id)
                all_pdfs.extend(pdfs)

            logger.info(f"   Extracted {len(all_pdfs)} PDF files")

            # Phase 4: Process PDFs
            logger.info(f"\n🔍 PHASE 4: Processing PDFs through AI pipeline...")

            for idx, pdf_path in enumerate(all_pdfs, 1):
                logger.info(f"\n[{idx}/{len(all_pdfs)}] Processing: {pdf_path.name}")

                result = self.process_pdf(pdf_path, idx)
                self.results.append(result)

                if result['success']:
                    logger.info(f"   ✅ Type: {result['doc_type']} (confidence: {result['confidence']}/200)")
                    logger.info(f"   📊 Items: {result['items_extracted']}")

                    if result.get('ai_consensus'):
                        consensus = result['ai_consensus']
                        logger.info(f"   🗳️  AI Consensus: {consensus['item_count']} items")
                        logger.info(f"      Models: {', '.join(consensus['agreeing_models'])}")
                        logger.info(f"      Strength: {consensus['consensus_strength']:.0%}")

                    logger.info(f"   ⏱️  Time: {result['processing_time']:.1f}s")
                else:
                    logger.info(f"   ❌ Failed: {result.get('error', 'Unknown error')}")

            # Phase 5: Save results
            logger.info(f"\n💾 PHASE 5: Saving results...")
            self.save_results()

            # Phase 6: Final statistics
            logger.info(f"\n" + "=" * 80)
            logger.info("📊 FINAL STATISTICS")
            logger.info("=" * 80)
            self.print_statistics()

        finally:
            # Close IMAP connection
            try:
                imap.close()
                imap.logout()
                logger.info("\n✅ Disconnected from Gmail IMAP")
            except:
                pass

    def save_results(self):
        """Save results to JSON"""

        output_file = self.output_dir / 'production_scan_results_gmail.json'

        report = {
            'scan_date': datetime.now().isoformat(),
            'max_emails': self.max_emails,
            'statistics': self.stats,
            'results': self.results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"   ✅ Results saved to: {output_file}")

    def print_statistics(self):
        """Print final statistics"""

        stats = self.stats

        logger.info(f"\n📧 Email Processing:")
        logger.info(f"   Total emails scanned: {stats['total_emails']}")
        logger.info(f"   Emails with PDFs: {stats['emails_with_attachments']}")
        logger.info(f"   PDFs extracted: {stats['pdfs_extracted']}")

        logger.info(f"\n🔍 Document Processing:")
        logger.info(f"   Documents classified: {stats['documents_classified']}")
        logger.info(f"   Documents extracted: {stats['documents_extracted']}")
        logger.info(f"   AI validated: {stats['ai_validated']}")

        logger.info(f"\n🗳️  AI Consensus Quality:")
        logger.info(f"   Perfect (100%): {stats['perfect_consensus']}")
        logger.info(f"   Partial (50-99%): {stats['partial_consensus']}")
        logger.info(f"   No consensus: {stats['no_consensus']}")

        if stats['by_type']:
            logger.info(f"\n📋 By Document Type:")
            for doc_type, type_stats in stats['by_type'].items():
                logger.info(f"   {doc_type}:")
                logger.info(f"      Classified: {type_stats['count']}")
                logger.info(f"      Extracted: {type_stats['extracted']}")
                logger.info(f"      AI validated: {type_stats['ai_validated']}")
                logger.info(f"      Perfect consensus: {type_stats['perfect_consensus']}")

        if stats['processing_times']:
            import statistics
            times = stats['processing_times']
            logger.info(f"\n⏱️  Processing Time:")
            logger.info(f"   Average: {statistics.mean(times):.1f}s")
            logger.info(f"   Median: {statistics.median(times):.1f}s")
            logger.info(f"   Min: {min(times):.1f}s")
            logger.info(f"   Max: {max(times):.1f}s")

        logger.info("\n" + "=" * 80)
        logger.info("✅ PRODUCTION SCAN COMPLETE")
        logger.info("=" * 80)


def main():
    """Main entry point"""

    # Output directory
    output_dir = Path(__file__).parent / "production_scan_output_gmail"

    # Create scanner
    scanner = GmailIMAPScanner(
        output_dir=str(output_dir),
        max_emails=10000
    )

    # Run scan
    scanner.run()


if __name__ == "__main__":
    main()
