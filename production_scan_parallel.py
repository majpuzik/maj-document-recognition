#!/usr/bin/env python3
"""
MAJ Document Recognition System is a comprehensive OCR system for document classification with AI in
"""

"""
Production Email Scanner - Parallel Processing Version
=======================================================
Scans emails from Thunderbird INBOX with support for parallel execution
Uses AI Consensus V2 (2 local Ollama models)

Author: Claude Code
Date: 2025-12-04
"""

import sys
import json
import mailbox
import email
import logging
import argparse
import psutil
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
    format='%(asctime)s - [Instance %(instance_id)s] - %(levelname)s - %(message)s'
)


class ParallelEmailScanner:
    """Production email scanner with parallel processing support"""

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

        # Initialize components - PRODUCTION MODE (Ollama only)
        self.logger.info(f"🚀 Initializing Parallel Email Scanner Instance {instance_id}")
        self.logger.info(f"   Email range: {start_email} - {end_email or 'END'}")
        self.logger.info(f"   Mode: PRODUCTION (2 local Ollama models)")

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

        self.logger.info(f"✅ Classifier: {len(self.classifier.patterns)} document types")
        self.logger.info(f"✅ AI Voter: {len(self.voter.models)} models (Ollama only)")

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
            'ai_validated': 0,
            'perfect_consensus': 0,
            'partial_consensus': 0,
            'no_consensus': 0,
            'by_type': {},
            'processing_times': [],
            'memory_usage_mb': []
        }

        # Results storage
        self.results = []

    def log_memory_usage(self):
        """Log current memory usage"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        self.stats['memory_usage_mb'].append(memory_mb)

        # Also log system memory
        system_memory = psutil.virtual_memory()
        available_gb = system_memory.available / 1024 / 1024 / 1024

        self.logger.info(f"💾 Memory: Process={memory_mb:.0f}MB, System Available={available_gb:.1f}GB")

        return memory_mb, available_gb

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

            if (idx - self.start_email) % 1000 == 0 and idx > self.start_email:
                self.logger.info(f"   Processed {idx - self.start_email} emails, found {len(emails_with_pdfs)} with PDFs...")
                self.log_memory_usage()

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
        """Process single PDF through pipeline"""

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
            'ai_consensus': None,
            'processing_time': 0
        }

        try:
            # 1. Extract text (returns Dict with 'text' key)
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

            # 2. Classify document (returns tuple: doc_type, confidence, details)
            doc_type, confidence, details = self.classifier.classify(text)
            result['doc_type'] = str(doc_type).replace('DocumentType.', '')  # Convert enum to string for JSON
            result['confidence'] = confidence
            result['classification_details'] = details

            if doc_type == 'unknown':
                result['error'] = 'Unknown document type'
                return result

            self.stats['documents_classified'] += 1
            # Convert DocumentType enum to string for JSON serialization
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

                    # 4. AI Consensus Validation (Production: 2 Ollama models)
                    try:
                        consensus, details = self.voter.vote(text, doc_type_str.lower())

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
                        self.logger.error(f"   AI consensus failed: {e}")
                        result['ai_error'] = str(e)

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
        self.logger.info(f"🚀 PARALLEL EMAIL SCANNER - INSTANCE {self.instance_id} STARTING")
        self.logger.info("=" * 80)
        self.logger.info(f"Mbox: {self.mbox_path}")
        self.logger.info(f"Email range: {self.start_email} - {self.end_email or 'END'}")
        self.logger.info(f"Output: {self.instance_dir}")
        self.logger.info(f"AI Mode: PRODUCTION (2 local Ollama models)")
        self.logger.info("=" * 80 + "\n")

        # Initial memory check
        self.log_memory_usage()

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
            all_pdfs.extend(pdfs)

        self.logger.info(f"   Extracted {len(all_pdfs)} PDF files")
        self.log_memory_usage()

        # Phase 3: Process PDFs
        self.logger.info(f"\n🔍 PHASE 3: Processing PDFs through AI pipeline...")

        for idx, pdf_path in enumerate(all_pdfs, 1):
            self.logger.info(f"\n[{idx}/{len(all_pdfs)}] Processing: {pdf_path.name}")

            result = self.process_pdf(pdf_path, idx)
            self.results.append(result)

            if result['success']:
                self.logger.info(f"   ✅ Type: {result['doc_type']} (confidence: {result['confidence']}/200)")
                self.logger.info(f"   📊 Items: {result['items_extracted']}")

                if result.get('ai_consensus'):
                    consensus = result['ai_consensus']
                    self.logger.info(f"   🗳️  AI Consensus: {consensus['item_count']} items")
                    self.logger.info(f"      Models: {', '.join(consensus['agreeing_models'])}")
                    self.logger.info(f"      Strength: {consensus['consensus_strength']:.0%}")

                self.logger.info(f"   ⏱️  Time: {result['processing_time']:.1f}s")
            else:
                self.logger.info(f"   ❌ Failed: {result.get('error', 'Unknown error')}")

            # Log memory every 10 documents
            if idx % 10 == 0:
                self.log_memory_usage()

        # Phase 4: Save results
        self.logger.info(f"\n💾 PHASE 4: Saving results...")
        self.save_results()

        # Phase 5: Final statistics
        self.logger.info(f"\n" + "=" * 80)
        self.logger.info(f"📊 INSTANCE {self.instance_id} - FINAL STATISTICS")
        self.logger.info("=" * 80)
        self.print_statistics()

    def save_results(self):
        """Save results to JSON"""

        output_file = self.instance_dir / f'instance_{self.instance_id}_results.json'

        report = {
            'scan_date': datetime.now().isoformat(),
            'instance_id': self.instance_id,
            'start_email': self.start_email,
            'end_email': self.end_email,
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
        self.logger.info(f"   AI validated: {stats['ai_validated']}")

        self.logger.info(f"\n🗳️  AI Consensus Quality:")
        self.logger.info(f"   Perfect (100%): {stats['perfect_consensus']}")
        self.logger.info(f"   Partial (50-99%): {stats['partial_consensus']}")
        self.logger.info(f"   No consensus: {stats['no_consensus']}")

        if stats['by_type']:
            self.logger.info(f"\n📋 By Document Type:")
            for doc_type, type_stats in stats['by_type'].items():
                self.logger.info(f"   {doc_type}:")
                self.logger.info(f"      Classified: {type_stats['count']}")
                self.logger.info(f"      Extracted: {type_stats['extracted']}")
                self.logger.info(f"      AI validated: {type_stats['ai_validated']}")
                self.logger.info(f"      Perfect consensus: {type_stats['perfect_consensus']}")

        if stats['processing_times']:
            import statistics
            times = stats['processing_times']
            self.logger.info(f"\n⏱️  Processing Time:")
            self.logger.info(f"   Average: {statistics.mean(times):.1f}s")
            self.logger.info(f"   Median: {statistics.median(times):.1f}s")
            self.logger.info(f"   Min: {min(times):.1f}s")
            self.logger.info(f"   Max: {max(times):.1f}s")

        if stats['memory_usage_mb']:
            import statistics
            memory = stats['memory_usage_mb']
            self.logger.info(f"\n💾 Memory Usage:")
            self.logger.info(f"   Average: {statistics.mean(memory):.0f} MB")
            self.logger.info(f"   Peak: {max(memory):.0f} MB")

        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"✅ INSTANCE {self.instance_id} COMPLETE")
        self.logger.info("=" * 80)


def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(description='Parallel Email Scanner')
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
    scanner = ParallelEmailScanner(
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
