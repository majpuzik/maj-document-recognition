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
Test MBW Documents with Universal Classifier + Data Extractors + AI Voting

Tests 51 real business documents from MBW (Müllers Büro Werkstatt):
- Invoices (faktury)
- Receipts (účtenky)
- Bank statements (výpisy)
- Contracts (smlouvy)
- Insurance documents (pojištění)

Author: Claude Code
Date: 2025-11-30
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
import subprocess

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


class MBWDocumentTester:
    """Test MBW documents with full pipeline"""

    def __init__(self, mbw_dir: str):
        self.mbw_dir = Path(mbw_dir)

        # Initialize components
        self.classifier = UniversalBusinessClassifier()
        self.voter = AIVoter(hierarchical=True)
        self.learning_db = LearningDatabase('mbw_learning_hierarchical.jsonl')

        logger.info(f"✅ Initialized for MBW directory: {self.mbw_dir}")
        logger.info(f"✅ Universal Classifier: {len(self.classifier.patterns)} document types")
        logger.info(f"✅ AI Voter: {len(self.voter.models)} models")

    def find_mbw_documents(self) -> List[Path]:
        """Find all PDF documents in MBW directory"""
        # Get all PDFs in the directory (not just those with MBW in name)
        pdf_files = list(self.mbw_dir.glob("*.pdf"))

        # Also check subdirectories
        pdf_files.extend(self.mbw_dir.glob("**/*.pdf"))

        # Remove duplicates
        pdf_files = list(set(pdf_files))

        logger.info(f"📄 Found {len(pdf_files)} PDF documents in MBW folder")
        return sorted(pdf_files)

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

    def test_document(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Test single PDF document through full pipeline:
        1. Extract text from PDF
        2. Classify with Universal Classifier
        3. Extract data with appropriate extractor
        4. Validate with AI consensus
        """
        print(f"\n{'='*80}")
        print(f"📄 {pdf_path.name}")
        print('='*80)

        # Step 1: Extract text
        print("1️⃣  Extracting text from PDF...")
        text = self.extract_text_from_pdf(pdf_path)

        if not text or len(text) < 100:
            print(f"   ⚠️  Failed to extract text ({len(text)} chars)")
            return {
                'file': pdf_path.name,
                'found': False,
                'reason': 'no_text'
            }

        print(f"   Extracted {len(text)} characters")

        # Step 2: Classify
        print("\n2️⃣  Classifying document type...")
        doc_type, confidence, details = self.classifier.classify(text)

        if doc_type == DocumentType.UNKNOWN or confidence < 50:
            print(f"   ⚠️  Unknown document type (confidence: {confidence})")
            return {
                'file': pdf_path.name,
                'found': False,
                'reason': 'unknown_type',
                'text_length': len(text)
            }

        print(f"   Type: {doc_type.value}")
        print(f"   Confidence: {confidence}/200")
        if details.get('matched_keywords'):
            print(f"   Keywords: {', '.join(details['matched_keywords'][:3])}")

        # Step 3: Extract data
        extractor_type = DOC_TYPE_MAP.get(doc_type)
        if not extractor_type:
            print(f"   ⚠️  No extractor for {doc_type.value}")
            return {
                'file': pdf_path.name,
                'found': True,
                'doc_type': doc_type.value,
                'classifier_confidence': confidence,
                'reason': 'no_extractor'
            }

        print(f"\n3️⃣  Extracting data ({extractor_type})...")
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

        print(f"   Items extracted: {items_count}")
        print(f"   Confidence: {extraction_confidence:.1f}%")

        if items_count == 0:
            print(f"   ⚠️  No items extracted")
            return {
                'file': pdf_path.name,
                'found': True,
                'doc_type': doc_type.value,
                'classifier_confidence': confidence,
                'extraction_items': 0,
                'extraction_confidence': extraction_confidence,
                'reason': 'no_items'
            }

        # Step 4: AI Validation
        print(f"\n4️⃣  AI Validation...")
        consensus_result, voting_details = self.voter.vote(text, extractor_type)

        has_consensus = voting_details['consensus_strength'] >= 0.67

        print(f"   Consensus: {voting_details['consensus_strength']:.0%}")
        print(f"   Models: {', '.join(voting_details['agreeing_models'])}")

        if has_consensus:
            # Save pattern
            self.learning_db.save_pattern(
                text, extractor_type, consensus_result, voting_details
            )

            # Compare
            ai_items = voting_details['majority_count']
            match = items_count == ai_items

            print(f"\n5️⃣  Results:")
            print(f"   Classifier: {doc_type.value} ({confidence}/200)")
            print(f"   Local: {items_count} items ({extraction_confidence:.0f}%)")
            print(f"   AI: {ai_items} items")
            print(f"   {'✅ MATCH' if match else '❌ MISMATCH'}")

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
            print("   ❌ No AI consensus")
            return {
                'file': pdf_path.name,
                'found': True,
                'doc_type': doc_type.value,
                'classifier_confidence': confidence,
                'has_consensus': False,
                'local_items': items_count,
                'extraction_confidence': extraction_confidence
            }

    def test_all_documents(self, limit: int = None) -> Dict[str, Any]:
        """Test all MBW documents"""

        print(f"\n{'='*80}")
        print(f"🔍 MBW DOCUMENTS TEST")
        print(f"{'='*80}")
        print(f"Pipeline: PDF → Text → Classifier → Extractor → AI Voting")
        print(f"AI Models: {list(self.voter.models.keys())}")
        print()

        # Find documents
        pdf_files = self.find_mbw_documents()

        if not pdf_files:
            print("❌ No MBW documents found")
            return {}

        if limit:
            pdf_files = pdf_files[:limit]
            print(f"Testing first {limit} documents")

        # Test each document
        results = []
        documents_found = 0
        consensus_reached = 0
        matches = 0

        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}]")
            try:
                result = self.test_document(pdf_path)
                results.append(result)

                if result.get('found'):
                    documents_found += 1
                    if result.get('has_consensus'):
                        consensus_reached += 1
                        if result.get('match'):
                            matches += 1

            except Exception as e:
                logger.error(f"Failed to test {pdf_path.name}: {e}")
                results.append({
                    'file': pdf_path.name,
                    'found': False,
                    'reason': 'error',
                    'error': str(e)
                })
                continue

        # Calculate summary by document type
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
            'total_tested': len(pdf_files),
            'documents_found': documents_found,
            'consensus_reached': consensus_reached,
            'matches': matches,
            'overall_accuracy': (matches / consensus_reached * 100) if consensus_reached > 0 else 0,
            'by_type': by_type,
            'results': results
        }

        # Print summary
        print(f"\n{'='*80}")
        print(f"📊 MBW TEST SUMMARY")
        print(f"{'='*80}")
        print(f"PDFs tested: {summary['total_tested']}")
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
    """Main test function"""

    # MBW documents directory
    mbw_dir = Path.home() / "Dropbox/MBW"

    if not mbw_dir.exists():
        print(f"❌ MBW directory not found: {mbw_dir}")
        return

    print("\n🎯 MBW DOCUMENTS TEST")
    print("="*80)
    print("Testing real business documents:")
    print("  - Invoices (faktury)")
    print("  - Receipts (účtenky)")
    print("  - Bank statements (výpisy)")
    print("  - Contracts (smlouvy)")
    print("  - Insurance documents (pojištění)")
    print()
    print("Pipeline:")
    print("  1. PDF → Text extraction (pdftotext)")
    print("  2. Universal Classifier (pattern matching)")
    print("  3. Data Extractors (line items)")
    print("  4. AI Voting (GPT-4 + Gemini + Ollama)")
    print()

    tester = MBWDocumentTester(str(mbw_dir))

    # Test all MBW documents
    results = tester.test_all_documents()

    # Save results
    results_file = 'mbw_test_hierarchical.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved: {results_file}")
    print(f"💾 Learning patterns: mbw_learning_hierarchical.jsonl")
    print("\n✅ MBW test complete!")


if __name__ == "__main__":
    main()
