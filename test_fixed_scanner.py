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
Quick Test - Fixed Production Scanner
======================================
Tests the fixed enum comparison bug on 100 emails
Should now show:
- Items extracted > 0
- AI consensus validation working
"""

import sys
import json
import mailbox
import email
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any

# Add src paths
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ai'))

from ai_consensus_trainer import AIVoter
from data_extractors import create_extractor
from universal_business_classifier import UniversalBusinessClassifier
from text_extractor_cascade import CascadeTextExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuickTestScanner:
    """Quick test of fixed scanner"""

    def __init__(self, mbox_path: str, output_dir: str, max_emails: int = 100):
        self.mbox_path = Path(mbox_path)
        self.output_dir = Path(output_dir)
        self.max_emails = max_emails
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("🔧 Quick Test - Fixed Scanner")
        logger.info(f"   Testing enum comparison fix")
        logger.info(f"   Max emails: {max_emails}")

        self.classifier = UniversalBusinessClassifier()
        self.voter = AIVoter(use_external_apis=False)

        config = {
            "ocr": {
                "cascade_threshold": 60.0,
                "min_text_length": 50
            }
        }
        self.text_extractor = CascadeTextExtractor(config)

        self.stats = {
            'total_emails': 0,
            'pdfs_extracted': 0,
            'documents_classified': 0,
            'documents_extracted': 0,
            'ai_validated': 0,
            'perfect_consensus': 0,
            'by_type': {}
        }

        self.results = []

    def scan_mbox(self) -> List[Tuple[int, email.message.EmailMessage]]:
        """Scan for first N emails with PDFs"""
        logger.info(f"📧 Scanning {self.mbox_path.name}...")

        mbox = mailbox.mbox(str(self.mbox_path))
        emails_with_pdfs = []

        for idx, msg in enumerate(mbox):
            if idx >= self.max_emails:
                break

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

        self.stats['total_emails'] = min(idx + 1, self.max_emails)
        logger.info(f"   Found {len(emails_with_pdfs)} emails with PDFs")
        return emails_with_pdfs

    def extract_pdf_attachments(self, msg: email.message.EmailMessage, email_id: int) -> List[Path]:
        """Extract PDFs"""
        pdf_files = []
        attachment_num = 0

        for part in msg.walk():
            if part.get_content_type() == 'application/pdf':
                attachment_num += 1
                filename = part.get_filename()

                if not filename:
                    filename = f"email_{email_id}_attachment_{attachment_num}.pdf"

                safe_filename = f"{email_id:06d}_{filename}"
                pdf_path = self.output_dir / safe_filename

                try:
                    with open(pdf_path, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    pdf_files.append(pdf_path)
                    self.stats['pdfs_extracted'] += 1
                except Exception as e:
                    logger.error(f"   Failed to save PDF: {e}")

        return pdf_files

    def process_pdf(self, pdf_path: Path, email_id: int) -> Dict[str, Any]:
        """Process PDF through fixed pipeline"""
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
                result['error'] = 'Insufficient text'
                return result

            # 2. Classify
            doc_type, confidence, details = self.classifier.classify(text)
            result['doc_type'] = str(doc_type).replace('DocumentType.', '')
            result['confidence'] = confidence

            if doc_type == 'unknown':
                result['error'] = 'Unknown type'
                return result

            self.stats['documents_classified'] += 1
            doc_type_str = str(doc_type).replace('DocumentType.', '')

            if doc_type_str not in self.stats['by_type']:
                self.stats['by_type'][doc_type_str] = {
                    'count': 0,
                    'extracted': 0,
                    'ai_validated': 0
                }
            self.stats['by_type'][doc_type_str]['count'] += 1

            # 3. Extract structured data - FIXED VERSION
            if doc_type_str.lower() in ['invoice', 'receipt', 'bank_statement']:
                extractor = create_extractor(doc_type_str.lower())
                local_result = extractor.extract(text)

                # Get item count
                if doc_type_str.lower() == 'invoice':
                    items = len(local_result.get('line_items', []))
                elif doc_type_str.lower() == 'receipt':
                    items = len(local_result.get('items', []))
                else:
                    items = len(local_result.get('transactions', []))

                result['items_extracted'] = items
                result['local_extraction'] = local_result

                if items > 0:
                    self.stats['documents_extracted'] += 1
                    self.stats['by_type'][doc_type_str]['extracted'] += 1

                    # 4. AI Consensus - FIXED VERSION
                    try:
                        consensus, details = self.voter.vote(text, doc_type_str.lower())

                        result['ai_consensus'] = {
                            'item_count': details['majority_count'],
                            'agreeing_models': details['agreeing_models'],
                            'consensus_strength': details['consensus_strength']
                        }

                        self.stats['ai_validated'] += 1
                        self.stats['by_type'][doc_type_str]['ai_validated'] += 1

                        if details['consensus_strength'] == 1.0:
                            self.stats['perfect_consensus'] += 1

                    except Exception as e:
                        logger.error(f"   AI consensus failed: {e}")
                        result['ai_error'] = str(e)

            result['success'] = True

        except Exception as e:
            logger.error(f"   Processing failed: {e}")
            result['error'] = str(e)

        processing_time = (datetime.now() - start_time).total_seconds()
        result['processing_time'] = processing_time

        return result

    def run(self):
        """Run quick test"""
        logger.info("\n" + "=" * 80)
        logger.info("🔧 QUICK TEST - FIXED ENUM COMPARISON BUG")
        logger.info("=" * 80)
        logger.info(f"Testing: {self.max_emails} emails")
        logger.info("Expected: Items extracted > 0, AI validation working")
        logger.info("=" * 80 + "\n")

        # Scan
        emails_with_pdfs = self.scan_mbox()
        if not emails_with_pdfs:
            logger.warning("⚠️  No PDFs found")
            return

        # Extract PDFs
        logger.info(f"\n📄 Extracting PDFs...")
        all_pdfs = []
        for email_id, msg in emails_with_pdfs:
            pdfs = self.extract_pdf_attachments(msg, email_id)
            all_pdfs.extend(pdfs)

        logger.info(f"   Extracted {len(all_pdfs)} PDFs\n")

        # Process
        logger.info(f"🔍 Processing PDFs...\n")
        for idx, pdf_path in enumerate(all_pdfs, 1):
            logger.info(f"[{idx}/{len(all_pdfs)}] {pdf_path.name}")

            result = self.process_pdf(pdf_path, idx)
            self.results.append(result)

            if result['success']:
                logger.info(f"   ✅ {result['doc_type']} (conf: {result['confidence']}/200)")
                logger.info(f"   📊 Items: {result['items_extracted']}")

                if result.get('ai_consensus'):
                    consensus = result['ai_consensus']
                    logger.info(f"   🗳️  AI: {consensus['item_count']} items, {consensus['consensus_strength']:.0%} consensus")
                    logger.info(f"      Models: {', '.join(consensus['agreeing_models'])}")

                logger.info(f"   ⏱️  {result['processing_time']:.1f}s\n")
            else:
                logger.info(f"   ❌ {result.get('error', 'Unknown error')}\n")

        # Results
        self.save_results()
        self.print_summary()

    def save_results(self):
        """Save results"""
        output_file = self.output_dir / 'quick_test_results.json'

        report = {
            'test_date': datetime.now().isoformat(),
            'max_emails': self.max_emails,
            'statistics': self.stats,
            'results': self.results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"\n💾 Results saved: {output_file}")

    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 80)

        logger.info(f"\n📧 Email Processing:")
        logger.info(f"   Emails scanned: {self.stats['total_emails']}")
        logger.info(f"   PDFs extracted: {self.stats['pdfs_extracted']}")

        logger.info(f"\n🔍 Document Processing:")
        logger.info(f"   Classified: {self.stats['documents_classified']}")
        logger.info(f"   Extracted: {self.stats['documents_extracted']}")
        logger.info(f"   AI validated: {self.stats['ai_validated']}")
        logger.info(f"   Perfect consensus: {self.stats['perfect_consensus']}")

        if self.stats['by_type']:
            logger.info(f"\n📋 By Document Type:")
            for doc_type, type_stats in self.stats['by_type'].items():
                logger.info(f"   {doc_type}:")
                logger.info(f"      Classified: {type_stats['count']}")
                logger.info(f"      Extracted: {type_stats['extracted']}")
                logger.info(f"      AI validated: {type_stats['ai_validated']}")

        # BUG FIX VALIDATION
        logger.info("\n" + "=" * 80)
        logger.info("🔧 BUG FIX VALIDATION")
        logger.info("=" * 80)

        if self.stats['documents_extracted'] > 0:
            logger.info("✅ FIXED: Items are now being extracted!")
        else:
            logger.info("❌ ISSUE: Still no items extracted")

        if self.stats['ai_validated'] > 0:
            logger.info("✅ FIXED: AI consensus validation is working!")
        else:
            logger.info("❌ ISSUE: AI validation still not triggering")

        logger.info("\n" + "=" * 80)


def main():
    """Main entry point"""

    # Thunderbird INBOX
    mbox_path = Path.home() / "Library/Thunderbird/Profiles" / \
                "1oli4gwg.default-esr/ImapMail/127.0.0.1/INBOX"

    # Output directory
    output_dir = Path(__file__).parent / "quick_test_output"

    # Run quick test on 100 emails
    scanner = QuickTestScanner(
        mbox_path=str(mbox_path),
        output_dir=str(output_dir),
        max_emails=100
    )

    scanner.run()


if __name__ == "__main__":
    main()
