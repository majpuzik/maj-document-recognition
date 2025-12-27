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
Extract and Test MBW Email Attachments

Scans Thunderbird mailbox for MBW emails with PDF attachments,
extracts them, and tests with Universal Classifier + Data Extractors + AI Voting.

Author: Claude Code
Date: 2025-12-01
"""

import os
import sys
import email
import base64
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple
from email import policy
from email.parser import BytesParser

# Add paths
sys.path.insert(0, str(Path.home() / 'apps/maj-subscriptions-local'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))

# Import Universal Classifier
from universal_business_classifier import UniversalBusinessClassifier, DocumentType

# Import Data Extractors
from data_extractors import create_extractor

# Import AI Consensus
from ai_consensus_trainer import AIVoter, LearningDatabase

from dotenv import load_dotenv
load_dotenv(Path.home() / '.env.litellm')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Map DocumentType to extractor names
DOC_TYPE_MAP = {
    DocumentType.INVOICE: 'invoice',
    DocumentType.RECEIPT: 'receipt',
    DocumentType.GAS_RECEIPT: 'receipt',
    DocumentType.CAR_WASH: 'receipt',
    DocumentType.CAR_SERVICE: 'invoice',
    DocumentType.BANK_STATEMENT: 'bank_statement',
}


class MBWAttachmentExtractor:
    """Extract MBW attachments from Thunderbird and test them"""

    def __init__(self, mbox_path: str, output_dir: str):
        self.mbox_path = Path(mbox_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize components
        self.classifier = UniversalBusinessClassifier()
        self.voter = AIVoter()
        self.learning_db = LearningDatabase('mbw_attachments_learning.jsonl')

        logger.info(f"✅ Initialized for mbox: {self.mbox_path.name}")
        logger.info(f"✅ Output directory: {self.output_dir}")
        logger.info(f"✅ Universal Classifier: {len(self.classifier.patterns)} document types")
        logger.info(f"✅ AI Voter: {len(self.voter.models)} models")

    def scan_mbox_for_mbw_emails(self) -> List[Tuple[int, email.message.EmailMessage]]:
        """Scan mbox for emails containing 'MBW' with PDF attachments"""

        logger.info(f"📧 Scanning mbox: {self.mbox_path.name} ({self.mbox_path.stat().st_size / 1024**3:.1f} GB)")

        mbw_emails = []
        parser = BytesParser(policy=policy.default)

        with open(self.mbox_path, 'rb') as f:
            # Read mbox in chunks
            email_count = 0
            current_email = bytearray()
            in_email = False

            for line in f:
                # Detect start of new email
                if line.startswith(b'From '):
                    # Process previous email
                    if current_email:
                        email_count += 1
                        if email_count % 10000 == 0:
                            logger.info(f"  Processed {email_count} emails, found {len(mbw_emails)} MBW emails...")

                        try:
                            msg = parser.parsebytes(bytes(current_email))

                            # Check if MBW in subject or body
                            subject = str(msg.get('Subject', ''))
                            if 'MBW' in subject.upper() or 'MYBRAINWORKS' in subject.upper():
                                # Check if has PDF attachments
                                has_pdf = False
                                for part in msg.walk():
                                    if part.get_content_type() == 'application/pdf':
                                        has_pdf = True
                                        break

                                if has_pdf:
                                    mbw_emails.append((email_count, msg))
                                    logger.info(f"  ✅ Found MBW email #{email_count}: {subject[:60]}")

                        except Exception as e:
                            logger.debug(f"  Error parsing email #{email_count}: {e}")

                    # Start new email
                    current_email = bytearray()
                    in_email = True

                elif in_email:
                    current_email.extend(line)

            # Process last email
            if current_email:
                email_count += 1
                try:
                    msg = parser.parsebytes(bytes(current_email))
                    subject = str(msg.get('Subject', ''))
                    if 'MBW' in subject.upper() or 'MYBRAINWORKS' in subject.upper():
                        has_pdf = False
                        for part in msg.walk():
                            if part.get_content_type() == 'application/pdf':
                                has_pdf = True
                                break
                        if has_pdf:
                            mbw_emails.append((email_count, msg))
                            logger.info(f"  ✅ Found MBW email #{email_count}: {subject[:60]}")
                except Exception as e:
                    logger.debug(f"  Error parsing last email: {e}")

        logger.info(f"📊 Total emails scanned: {email_count}")
        logger.info(f"📊 MBW emails with PDF attachments: {len(mbw_emails)}")

        return mbw_emails

    def extract_pdf_attachments(self, msg: email.message.EmailMessage, email_id: int) -> List[Path]:
        """Extract PDF attachments from email"""

        extracted_files = []
        attachment_count = 0

        for part in msg.walk():
            if part.get_content_type() == 'application/pdf':
                # Get filename
                filename = part.get_filename()
                if not filename:
                    filename = f"email_{email_id}_attachment_{attachment_count}.pdf"

                # Sanitize filename
                filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()

                # Save to output directory
                output_path = self.output_dir / f"{email_id:06d}_{filename}"

                try:
                    # Get payload
                    payload = part.get_payload(decode=True)

                    if payload:
                        with open(output_path, 'wb') as f:
                            f.write(payload)

                        extracted_files.append(output_path)
                        logger.info(f"    💾 Extracted: {filename} ({len(payload)/1024:.1f} KB)")
                        attachment_count += 1

                except Exception as e:
                    logger.error(f"    ❌ Failed to extract {filename}: {e}")

        return extracted_files

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF using pdftotext"""
        try:
            result = subprocess.run(
                ['pdftotext', '-layout', str(pdf_path), '-'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"pdftotext failed for {pdf_path.name}")
                return ""

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout extracting text from {pdf_path.name}")
            return ""
        except FileNotFoundError:
            logger.error("pdftotext not found. Install: brew install poppler")
            return ""
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path.name}: {e}")
            return ""

    def test_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """Test single PDF through pipeline"""

        # Extract text
        text = self.extract_text_from_pdf(pdf_path)

        if not text or len(text) < 100:
            return {
                'file': pdf_path.name,
                'found': False,
                'reason': 'no_text',
                'text_length': len(text)
            }

        # Classify
        doc_type, confidence, details = self.classifier.classify(text)

        if doc_type == DocumentType.UNKNOWN or confidence < 50:
            return {
                'file': pdf_path.name,
                'found': False,
                'reason': 'unknown_type',
                'confidence': confidence,
                'text_length': len(text)
            }

        # Extract data
        extractor_type = DOC_TYPE_MAP.get(doc_type)
        if not extractor_type:
            return {
                'file': pdf_path.name,
                'found': True,
                'doc_type': doc_type.value,
                'classifier_confidence': confidence,
                'reason': 'no_extractor',
                'text_length': len(text)
            }

        extractor = create_extractor(extractor_type)
        extraction_result = extractor.extract(text)

        # Count items
        if extractor_type == 'invoice':
            items_count = len(extraction_result.get('line_items', []))
        elif extractor_type == 'receipt':
            items_count = len(extraction_result.get('items', []))
        elif extractor_type == 'bank_statement':
            items_count = len(extraction_result.get('transactions', []))
        else:
            items_count = 0

        extraction_confidence = extraction_result.get('extraction_confidence', 0)

        if items_count == 0:
            return {
                'file': pdf_path.name,
                'found': True,
                'doc_type': doc_type.value,
                'classifier_confidence': confidence,
                'extraction_items': 0,
                'extraction_confidence': extraction_confidence,
                'reason': 'no_items',
                'text_length': len(text)
            }

        # AI Validation
        consensus_result, voting_details = self.voter.vote(text, extractor_type)
        has_consensus = voting_details['consensus_strength'] >= 0.67

        if has_consensus:
            # Save pattern
            self.learning_db.save_pattern(
                text, extractor_type, consensus_result, voting_details
            )

            # Compare
            ai_items = voting_details['majority_count']
            match = items_count == ai_items

            return {
                'file': pdf_path.name,
                'found': True,
                'doc_type': doc_type.value,
                'classifier_confidence': confidence,
                'has_consensus': True,
                'match': match,
                'local_items': items_count,
                'ai_items': ai_items,
                'consensus_strength': voting_details['consensus_strength'],
                'extraction_confidence': extraction_confidence,
                'text_length': len(text)
            }
        else:
            return {
                'file': pdf_path.name,
                'found': True,
                'doc_type': doc_type.value,
                'classifier_confidence': confidence,
                'has_consensus': False,
                'local_items': items_count,
                'extraction_confidence': extraction_confidence,
                'text_length': len(text)
            }

    def run(self, limit: int = 50) -> Dict[str, Any]:
        """Run full extraction and testing pipeline"""

        print(f"\n{'='*80}")
        print(f"🔍 MBW ATTACHMENT EXTRACTION & TEST")
        print(f"{'='*80}")
        print(f"Mbox: {self.mbox_path.name}")
        print(f"Output: {self.output_dir}")
        print(f"Limit: {limit} emails")
        print()

        # Step 1: Scan for MBW emails
        print("1️⃣  Scanning mbox for MBW emails with PDF attachments...")
        mbw_emails = self.scan_mbox_for_mbw_emails()

        if not mbw_emails:
            print("❌ No MBW emails found with PDF attachments")
            return {}

        if limit:
            mbw_emails = mbw_emails[:limit]
            print(f"   Limiting to first {limit} emails")

        # Step 2: Extract attachments
        print(f"\n2️⃣  Extracting PDF attachments from {len(mbw_emails)} emails...")
        all_pdfs = []
        for email_id, msg in mbw_emails:
            subject = str(msg.get('Subject', ''))
            print(f"\n  Email #{email_id}: {subject[:60]}")

            pdfs = self.extract_pdf_attachments(msg, email_id)
            all_pdfs.extend(pdfs)

        print(f"\n📊 Total PDFs extracted: {len(all_pdfs)}")

        if not all_pdfs:
            print("❌ No PDFs extracted")
            return {}

        # Step 3: Test PDFs
        print(f"\n3️⃣  Testing {len(all_pdfs)} PDFs through pipeline...")
        print("   Pipeline: PDF → Text → Classifier → Extractor → AI Voting")
        print()

        results = []
        documents_found = 0
        consensus_reached = 0
        matches = 0

        for i, pdf_path in enumerate(all_pdfs, 1):
            print(f"[{i}/{len(all_pdfs)}] {pdf_path.name}")

            try:
                result = self.test_pdf(pdf_path)
                results.append(result)

                if result.get('found'):
                    documents_found += 1
                    print(f"  ✅ {result['doc_type']} (conf: {result['classifier_confidence']}/200)")

                    if result.get('has_consensus'):
                        consensus_reached += 1
                        if result.get('match'):
                            matches += 1
                            print(f"  ✅ MATCH: Local {result['local_items']} = AI {result['ai_items']}")
                        else:
                            print(f"  ❌ MISMATCH: Local {result['local_items']} ≠ AI {result['ai_items']}")
                    elif result.get('local_items', 0) > 0:
                        print(f"  ⚠️  No AI consensus ({result['local_items']} items)")
                    else:
                        print(f"  ⚠️  No items extracted")
                else:
                    print(f"  ❌ {result.get('reason', 'unknown')}")

            except Exception as e:
                logger.error(f"Failed to test {pdf_path.name}: {e}")
                results.append({
                    'file': pdf_path.name,
                    'found': False,
                    'reason': 'error',
                    'error': str(e)
                })

        # Calculate summary
        by_type = {}
        for r in results:
            if r.get('found') and r.get('doc_type'):
                doc_type = r['doc_type']
                if doc_type not in by_type:
                    by_type[doc_type] = {
                        'total': 0,
                        'consensus': 0,
                        'matches': 0,
                        'avg_classifier_conf': 0,
                        'avg_extraction_conf': 0,
                        'files': []
                    }

                by_type[doc_type]['total'] += 1
                by_type[doc_type]['files'].append(r['file'])

                if r.get('has_consensus'):
                    by_type[doc_type]['consensus'] += 1
                if r.get('match'):
                    by_type[doc_type]['matches'] += 1
                if r.get('classifier_confidence'):
                    by_type[doc_type]['avg_classifier_conf'] += r['classifier_confidence']
                if r.get('extraction_confidence'):
                    by_type[doc_type]['avg_extraction_conf'] += r['extraction_confidence']

        # Calculate averages
        for doc_type, stats in by_type.items():
            if stats['total'] > 0:
                stats['avg_classifier_conf'] = stats['avg_classifier_conf'] / stats['total']
                stats['avg_extraction_conf'] = stats['avg_extraction_conf'] / stats['total']
                stats['accuracy'] = (stats['matches'] / stats['consensus'] * 100) if stats['consensus'] > 0 else 0

        summary = {
            'total_pdfs': len(all_pdfs),
            'documents_found': documents_found,
            'consensus_reached': consensus_reached,
            'matches': matches,
            'overall_accuracy': (matches / consensus_reached * 100) if consensus_reached > 0 else 0,
            'by_type': by_type,
            'results': results
        }

        # Print summary
        print(f"\n{'='*80}")
        print(f"📊 MBW ATTACHMENTS TEST SUMMARY")
        print(f"{'='*80}")
        print(f"PDFs extracted: {summary['total_pdfs']}")
        print(f"Documents identified: {summary['documents_found']}")
        print(f"AI consensus: {summary['consensus_reached']}")
        print(f"Matches: {summary['matches']}/{summary['consensus_reached']}")
        print(f"Overall accuracy: {summary['overall_accuracy']:.1f}%")
        print()

        for doc_type, stats in by_type.items():
            print(f"{doc_type.upper()}:")
            print(f"  Found: {stats['total']}")
            print(f"  Consensus: {stats['consensus']}/{stats['total']}")
            print(f"  Matches: {stats['matches']}/{stats['consensus']}")
            print(f"  Accuracy: {stats['accuracy']:.1f}%")
            print(f"  Avg classifier conf: {stats['avg_classifier_conf']:.0f}/200")
            print(f"  Avg extraction conf: {stats['avg_extraction_conf']:.0f}%")
            print(f"  Files: {', '.join(stats['files'][:3])}{'...' if len(stats['files']) > 3 else ''}")
            print()

        print('='*80)

        return summary


def main():
    """Main function"""

    # Thunderbird INBOX
    mbox_path = Path.home() / "Library/Thunderbird/Profiles/1oli4gwg.default-esr/ImapMail/127.0.0.1/INBOX"

    # Output directory for extracted PDFs
    output_dir = Path(__file__).parent / "temp_attachments"

    if not mbox_path.exists():
        print(f"❌ Mbox not found: {mbox_path}")
        return

    print("\n🎯 MBW ATTACHMENT EXTRACTION & TEST")
    print("="*80)
    print("Extracting PDF attachments from MBW emails and testing them")
    print("Pipeline: Email → Extract PDF → Text → Classifier → Extractor → AI Voting")
    print()

    extractor = MBWAttachmentExtractor(str(mbox_path), str(output_dir))

    # Run extraction and testing (limit to 50 emails to start)
    results = extractor.run(limit=50)

    # Save results
    import json
    results_file = 'mbw_attachments_results.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved: {results_file}")
    print(f"💾 Learning patterns: mbw_attachments_learning.jsonl")
    print(f"💾 Extracted PDFs: {output_dir}")
    print("\n✅ MBW attachments test complete!")


if __name__ == "__main__":
    main()
