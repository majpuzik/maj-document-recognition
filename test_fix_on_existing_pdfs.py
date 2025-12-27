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
Quick Fix Test - On Existing PDFs
==================================
Tests fixed version on already extracted PDFs from production scan
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add src paths
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ai'))

from ai_consensus_trainer import AIVoter
from data_extractors import create_extractor
from universal_business_classifier import UniversalBusinessClassifier
from text_extractor_cascade import CascadeTextExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def process_pdf_fixed(pdf_path: Path, classifier, voter, text_extractor):
    """Process PDF with FIXED enum comparison"""

    logger.info(f"\n{'='*80}")
    logger.info(f"Testing: {pdf_path.name}")
    logger.info(f"{'='*80}")

    # 1. Extract text
    extraction_result = text_extractor.extract_from_pdf(str(pdf_path))
    text = extraction_result.get('text', '')

    if not text or len(text) < 100:
        logger.info("❌ Insufficient text extracted")
        return None

    logger.info(f"✅ Text extracted: {len(text)} chars")

    # 2. Classify
    doc_type, confidence, details = classifier.classify(text)
    doc_type_str = str(doc_type).replace('DocumentType.', '')

    logger.info(f"✅ Classification: {doc_type_str} (confidence: {confidence}/200)")

    if doc_type == 'unknown':
        logger.info("❌ Unknown document type")
        return None

    # 3. Extract structured data - FIXED VERSION
    logger.info(f"\n📊 Testing FIXED extraction...")
    logger.info(f"   Checking: doc_type_str.lower() = '{doc_type_str.lower()}'")
    logger.info(f"   Match list: ['invoice', 'receipt', 'bank_statement']")

    if doc_type_str.lower() in ['invoice', 'receipt', 'bank_statement']:
        logger.info(f"   ✅ MATCH! Will extract data...")

        extractor = create_extractor(doc_type_str.lower())
        local_result = extractor.extract(text)

        # Get item count
        if doc_type_str.lower() == 'invoice':
            items = len(local_result.get('line_items', []))
            item_type = "line_items"
        elif doc_type_str.lower() == 'receipt':
            items = len(local_result.get('items', []))
            item_type = "items"
        else:
            items = len(local_result.get('transactions', []))
            item_type = "transactions"

        logger.info(f"\n   📦 Extracted {items} {item_type}")

        if items > 0:
            logger.info(f"   ✅ SUCCESS: Data extraction working!")

            # Show sample items
            if doc_type_str.lower() == 'invoice' and local_result.get('line_items'):
                logger.info(f"\n   Sample items:")
                for item in local_result['line_items'][:3]:
                    logger.info(f"      - {item.get('description', 'N/A')}: {item.get('amount', 'N/A')}")

            # 4. AI Consensus - FIXED VERSION
            logger.info(f"\n🗳️  Testing AI consensus validation...")
            try:
                consensus, details = voter.vote(text, doc_type_str.lower())

                logger.info(f"   ✅ AI Consensus working!")
                logger.info(f"      Item count: {details['majority_count']}")
                logger.info(f"      Agreeing models: {', '.join(details['agreeing_models'])}")
                logger.info(f"      Consensus strength: {details['consensus_strength']:.0%}")

                return {
                    'success': True,
                    'doc_type': doc_type_str,
                    'items_extracted': items,
                    'ai_consensus': details
                }

            except Exception as e:
                logger.error(f"   ❌ AI consensus failed: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
        else:
            logger.info(f"   ⚠️  No items extracted (data may not be parseable)")
            return {
                'success': False,
                'error': 'No items extracted'
            }
    else:
        logger.info(f"   ⚠️  NO MATCH - Not an extractable type")
        return {
            'success': False,
            'doc_type': doc_type_str,
            'error': 'Not extractable type'
        }


def main():
    """Main test"""

    logger.info("\n" + "="*80)
    logger.info("🔧 BUG FIX VALIDATION TEST")
    logger.info("="*80)
    logger.info("Testing FIXED enum comparison on existing PDFs")
    logger.info("="*80 + "\n")

    # Initialize components
    logger.info("Initializing components...")
    classifier = UniversalBusinessClassifier()
    voter = AIVoter(use_external_apis=False)
    config = {
        "ocr": {
            "cascade_threshold": 60.0,
            "min_text_length": 50
        }
    }
    text_extractor = CascadeTextExtractor(config)
    logger.info("✅ Components ready\n")

    # Get PDFs from production scan output
    pdf_dir = Path(__file__).parent / "production_scan_output"
    pdf_files = sorted(list(pdf_dir.glob("*.pdf")))[:5]  # First 5 PDFs

    if not pdf_files:
        logger.error("❌ No PDFs found in production_scan_output/")
        return

    logger.info(f"Found {len(pdf_files)} PDFs to test\n")

    # Test each PDF
    results = []
    for idx, pdf_path in enumerate(pdf_files, 1):
        result = process_pdf_fixed(pdf_path, classifier, voter, text_extractor)
        if result:
            results.append(result)

    # Summary
    logger.info("\n" + "="*80)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*80)

    successful = sum(1 for r in results if r.get('success'))
    logger.info(f"\nTotal tests: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {len(results) - successful}")

    if successful > 0:
        logger.info("\n✅ BUG FIX VALIDATED!")
        logger.info("   - Items are being extracted")
        logger.info("   - AI consensus validation is working")
    else:
        logger.info("\n❌ BUG FIX MAY HAVE ISSUES")

    logger.info("\n" + "="*80)


if __name__ == "__main__":
    main()
