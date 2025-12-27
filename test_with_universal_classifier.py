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
Test real documents with Universal Classifier + Data Extractors + AI Voting

Workflow:
1. Load emails from database
2. Classify with UniversalBusinessClassifier (identifies document type)
3. Extract data with data_extractors (extracts line items)
4. Validate with AI consensus voting (3 AI models vote)
5. Save learning patterns

Author: Claude Code
Date: 2025-11-30
"""

import os
import sys
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path.home() / 'apps/maj-subscriptions-local'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))

# Import Universal Classifier
from universal_business_classifier import UniversalBusinessClassifier, DocumentType

# Import Data Extractors
from data_extractors import create_extractor

# Import AI Consensus Trainer
from ai_consensus_trainer import AIVoter, LearningDatabase

from dotenv import load_dotenv
load_dotenv(Path.home() / '.env.litellm')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Map DocumentType to extractor names
DOC_TYPE_MAP = {
    DocumentType.INVOICE: 'invoice',
    DocumentType.RECEIPT: 'receipt',
    DocumentType.GAS_RECEIPT: 'receipt',  # Use receipt extractor for gas receipts
    DocumentType.CAR_WASH: 'receipt',     # Use receipt extractor for car wash
    DocumentType.CAR_SERVICE: 'invoice',  # Use invoice extractor for car service
    DocumentType.BANK_STATEMENT: 'bank_statement',
}


class UniversalDocumentTester:
    """Test documents with Universal Classifier + Data Extractors + AI Voting"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        # Initialize components
        self.classifier = UniversalBusinessClassifier()
        self.voter = AIVoter()
        self.learning_db = LearningDatabase('universal_learning_patterns.jsonl')

        logger.info(f"✅ Initialized Universal Classifier with {len(self.classifier.patterns)} document types")
        logger.info(f"✅ Initialized AI Voter with {len(self.voter.models)} AI models")

    def load_emails(self, limit: int = 100) -> List[Dict]:
        """Load emails from database"""
        query = """
        SELECT
            id,
            email_subject,
            email_from,
            email_body_compact,
            email_body_full,
            email_date,
            has_pdf
        FROM email_evidence
        WHERE email_date >= '2024-01-01'
            AND LENGTH(COALESCE(email_body_compact, email_body_full)) > 300
        ORDER BY email_date DESC
        LIMIT ?
        """

        cursor = self.conn.execute(query, (limit,))
        emails = []

        for row in cursor.fetchall():
            text = row['email_body_compact'] or row['email_body_full'] or ''
            if len(text) > 300:
                emails.append({
                    'id': row['id'],
                    'subject': row['email_subject'],
                    'from': row['email_from'],
                    'text': text[:15000],  # Limit to 15k chars
                    'date': row['email_date'],
                    'has_pdf': row['has_pdf']
                })

        logger.info(f"📧 Loaded {len(emails)} emails")
        return emails

    def scan_email(self, email: Dict) -> Dict[str, Any]:
        """
        Scan email with workflow:
        1. Classify document type (Universal Classifier)
        2. Extract data (Data Extractors)
        3. Validate with AI (AI Voting)
        """
        print(f"\n{'='*80}")
        print(f"📧 Email {email['id']}: {email['subject'][:60]}...")
        print(f"   From: {email['from'][:40]}")
        print('='*80)

        # Step 1: Classify document type
        doc_type, confidence, details = self.classifier.classify(email['text'])

        if doc_type == DocumentType.UNKNOWN or confidence < 50:
            print(f"   ⚠️  Unknown document type (confidence: {confidence})")
            return {'email_id': email['id'], 'found': False, 'reason': 'unknown_type'}

        print(f"\n1️⃣  Classification: {doc_type.value}")
        print(f"   Confidence: {confidence}/200")
        print(f"   Keywords: {', '.join(details.get('matched_keywords', [])[:3])}")

        # Step 2: Extract data with appropriate extractor
        extractor_type = DOC_TYPE_MAP.get(doc_type)
        if not extractor_type:
            print(f"   ⚠️  No extractor available for {doc_type.value}")
            return {'email_id': email['id'], 'found': False, 'reason': 'no_extractor'}

        print(f"\n2️⃣  Extraction with {extractor_type} extractor...")
        extractor = create_extractor(extractor_type)
        extraction_result = extractor.extract(email['text'])

        # Count items based on extractor type
        if extractor_type == 'invoice':
            items_count = len(extraction_result.get('line_items', []))
        elif extractor_type == 'receipt':
            items_count = len(extraction_result.get('items', []))
        elif extractor_type == 'bank_statement':
            items_count = len(extraction_result.get('transactions', []))
        else:
            items_count = 0

        extraction_confidence = extraction_result.get('extraction_confidence', 0)

        print(f"   Extracted: {items_count} items")
        print(f"   Confidence: {extraction_confidence:.1f}%")

        if items_count == 0 or extraction_confidence < 50:
            print(f"   ⚠️  No valid items extracted")
            return {
                'email_id': email['id'],
                'found': True,
                'doc_type': doc_type.value,
                'classifier_confidence': confidence,
                'extraction_items': 0,
                'extraction_confidence': extraction_confidence,
                'reason': 'no_items'
            }

        # Step 3: Validate with AI consensus
        print(f"\n3️⃣  AI Validation...")
        return self.validate_with_ai(
            email,
            doc_type.value,
            extractor_type,
            items_count,
            extraction_confidence,
            confidence
        )

    def validate_with_ai(
        self,
        email: Dict,
        doc_type: str,
        extractor_type: str,
        local_items: int,
        extraction_confidence: float,
        classifier_confidence: int
    ) -> Dict[str, Any]:
        """Validate extraction with 3-AI consensus"""

        # AI voting
        consensus_result, voting_details = self.voter.vote(email['text'], extractor_type)

        # Check consensus
        has_consensus = voting_details['consensus_strength'] >= 0.67

        print(f"   Consensus: {voting_details['consensus_strength']:.0%}")
        print(f"   Models: {', '.join(voting_details['agreeing_models'])}")

        if has_consensus:
            # Save pattern
            self.learning_db.save_pattern(
                email['text'], extractor_type, consensus_result, voting_details
            )

            # Compare
            ai_items = voting_details['majority_count']
            match = local_items == ai_items

            print(f"\n4️⃣  Comparison:")
            print(f"   Classifier: {doc_type} ({classifier_confidence}/200)")
            print(f"   Local extractor: {local_items} items ({extraction_confidence:.0f}%)")
            print(f"   AI consensus: {ai_items} items")
            print(f"   {'✅ MATCH' if match else '❌ MISMATCH'}")

            return {
                'email_id': email['id'],
                'found': True,
                'doc_type': doc_type,
                'classifier_confidence': classifier_confidence,
                'has_consensus': True,
                'match': match,
                'local_items': local_items,
                'ai_items': ai_items,
                'consensus_strength': voting_details['consensus_strength'],
                'extraction_confidence': extraction_confidence
            }
        else:
            print("   ❌ No AI consensus")
            return {
                'email_id': email['id'],
                'found': True,
                'doc_type': doc_type,
                'classifier_confidence': classifier_confidence,
                'has_consensus': False
            }

    def test_batch(self, num_emails: int = 100) -> Dict[str, Any]:
        """Test batch of emails"""

        print(f"\n{'='*80}")
        print(f"🔍 UNIVERSAL CLASSIFIER TEST")
        print(f"{'='*80}")
        print(f"Document types: {len(self.classifier.patterns)}")
        print(f"AI models: {list(self.voter.models.keys())}")
        print(f"Testing: {num_emails} emails")
        print()

        # Load emails
        emails = self.load_emails(num_emails)

        if not emails:
            print("❌ No emails found")
            return {}

        # Scan each email
        results = []
        documents_found = 0
        matches = 0
        consensus_reached = 0

        for i, email in enumerate(emails, 1):
            print(f"\n[{i}/{len(emails)}]")
            try:
                result = self.scan_email(email)
                results.append(result)

                if result.get('found'):
                    documents_found += 1
                    if result.get('has_consensus'):
                        consensus_reached += 1
                        if result.get('match'):
                            matches += 1

            except Exception as e:
                logger.error(f"Failed to scan email: {e}")
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
                        'avg_extraction_conf': 0
                    }

                by_type[doc_type]['total'] += 1
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
                stats['accuracy'] = (stats['matches'] / stats['total'] * 100) if stats['total'] > 0 else 0

        summary = {
            'total_scanned': len(emails),
            'documents_found': documents_found,
            'consensus_reached': consensus_reached,
            'matches': matches,
            'overall_accuracy': (matches / consensus_reached * 100) if consensus_reached > 0 else 0,
            'by_type': by_type,
            'results': results
        }

        # Print summary
        print(f"\n{'='*80}")
        print(f"📊 SUMMARY")
        print(f"{'='*80}")
        print(f"Emails scanned: {summary['total_scanned']}")
        print(f"Documents found: {summary['documents_found']}")
        print(f"AI consensus reached: {summary['consensus_reached']}")
        print(f"Matches (local = AI): {summary['matches']}/{summary['consensus_reached']}")
        print(f"Overall accuracy: {summary['overall_accuracy']:.1f}%")
        print()

        for doc_type, stats in by_type.items():
            print(f"{doc_type.upper()}:")
            print(f"  Found: {stats['total']}")
            print(f"  Consensus: {stats['consensus']}/{stats['total']}")
            print(f"  Matches: {stats['matches']}/{stats['total']}")
            print(f"  Accuracy: {stats['accuracy']:.1f}%")
            print(f"  Avg classifier conf: {stats['avg_classifier_conf']:.0f}/200")
            print(f"  Avg extraction conf: {stats['avg_extraction_conf']:.0f}%")
            print()

        print('='*80)

        return summary


def main():
    """Main test function"""

    # Database path
    db_path = Path.home() / 'apps/maj-subscriptions-local/data/subscriptions.db'

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return

    print("\n🎯 UNIVERSAL CLASSIFIER + AI CONSENSUS TEST")
    print("="*80)
    print("Workflow:")
    print("  1. Universal Classifier identifies document type")
    print("  2. Data Extractors extract line items")
    print("  3. AI Voting validates results (GPT-4 + Gemini + Ollama)")
    print()

    tester = UniversalDocumentTester(str(db_path))

    # Test on 100 emails
    results = tester.test_batch(num_emails=100)

    # Save results
    results_file = 'universal_classifier_test_results.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        # Convert by_type keys to strings for JSON
        results_copy = results.copy()
        if 'by_type' in results_copy:
            results_copy['by_type'] = {
                str(k): v for k, v in results_copy['by_type'].items()
            }
        json.dump(results_copy, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved: {results_file}")
    print(f"💾 Learning patterns: universal_learning_patterns.jsonl")
    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
