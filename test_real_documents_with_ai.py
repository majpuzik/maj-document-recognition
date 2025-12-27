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
Test real documents from database with 3-AI consensus voting
1. Load real documents from subscriptions.db
2. Run local extractors
3. Validate with 3 AI models (GPT-4, Gemini, Ollama 32B)
4. Save learning patterns

Author: Claude Code
Date: 2025-11-30
"""

import os
import sys
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
from data_extractors import create_extractor
from extraction_schemas import SchemaValidator

# Import AI consensus trainer
from ai_consensus_trainer import AIVoter, LearningDatabase

from dotenv import load_dotenv
load_dotenv(Path.home() / '.env.litellm')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealDocumentTester:
    """Test real documents with 3-AI consensus"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        self.voter = AIVoter()
        self.learning_db = LearningDatabase('real_documents_learning.jsonl')

        logger.info(f"✅ Initialized with {len(self.voter.models)} AI models")

    def load_all_emails(self, limit: int = 100) -> List[Dict]:
        """Load all emails from database to scan for documents"""

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
        docs = []

        for row in cursor.fetchall():
            text = row['email_body_compact'] or row['email_body_full'] or ''
            if len(text) > 300:
                docs.append({
                    'id': row['id'],
                    'subject': row['email_subject'],
                    'from': row['email_from'],
                    'text': text[:15000],  # Limit to 15k chars
                    'date': row['email_date'],
                    'has_pdf': row['has_pdf']
                })

        logger.info(f"📧 Loaded {len(docs)} emails to scan")
        return docs

    def scan_email(self, email: Dict) -> Dict[str, Any]:
        """Scan email and try to extract any document type"""

        print(f"\n{'='*80}")
        print(f"📧 Scanning: {email['subject'][:60]}...")
        print(f"   From: {email['from'][:40]}")
        print(f"   Date: {email['date']}")
        print('='*80)

        # Try all document types
        results = {}
        found_doc_type = None
        max_items = 0

        for doc_type in ['invoice', 'receipt', 'bank_statement']:
            extractor = create_extractor(doc_type)
            result = extractor.extract(email['text'])

            if doc_type == 'invoice':
                items = len(result.get('line_items', []))
            elif doc_type == 'receipt':
                items = len(result.get('items', []))
            elif doc_type == 'bank_statement':
                items = len(result.get('transactions', []))
            else:
                items = 0

            confidence = result.get('extraction_confidence', 0)

            if items > 0 and confidence > 50:
                results[doc_type] = {'items': items, 'confidence': confidence, 'result': result}
                if items > max_items:
                    max_items = items
                    found_doc_type = doc_type

        if not found_doc_type:
            print("   ⚠️  No documents found (0 items extracted)")
            return {'email_id': email['id'], 'found': False}

        # Found a document - validate with AI
        print(f"\n✅ Found {found_doc_type}: {max_items} items ({results[found_doc_type]['confidence']:.1f}% confidence)")

        return self.validate_with_ai(email, found_doc_type, results[found_doc_type])

    def validate_with_ai(self, email: Dict, doc_type: str, extraction: Dict) -> Dict[str, Any]:
        """Validate extraction with 3-AI consensus"""

        print(f"\n🗳️  Validating with 3 AI models...")

        # AI voting
        consensus_result, voting_details = self.voter.vote(email['text'], doc_type)

        # Check consensus
        has_consensus = voting_details['consensus_strength'] >= 0.67

        print(f"   Consensus: {voting_details['consensus_strength']:.0%}")
        print(f"   Models: {', '.join(voting_details['agreeing_models'])}")

        if has_consensus:
            # Save pattern
            self.learning_db.save_pattern(
                email['text'], doc_type, consensus_result, voting_details
            )

            # Compare
            local_items = extraction['items']
            ai_items = voting_details['majority_count']
            match = local_items == ai_items

            print(f"\n   Local: {local_items} items")
            print(f"   AI: {ai_items} items")
            print(f"   {'✅ MATCH' if match else '❌ MISMATCH'}")

            return {
                'email_id': email['id'],
                'found': True,
                'doc_type': doc_type,
                'has_consensus': True,
                'match': match,
                'local_items': local_items,
                'ai_items': ai_items,
                'consensus_strength': voting_details['consensus_strength']
            }
        else:
            print("   ❌ No consensus")
            return {
                'email_id': email['id'],
                'found': True,
                'doc_type': doc_type,
                'has_consensus': False
            }

    def test_document(self, doc: Dict, doc_type: str) -> Dict[str, Any]:
        """Test single document with AI consensus"""

        print(f"\n{'='*80}")
        print(f"📄 Testing: {doc['subject'][:60]}...")
        print(f"   From: {doc['from'][:40]}")
        print(f"   Date: {doc['date']}")
        print('='*80)

        # 1. Local extraction
        print("\n1️⃣  Local extractor:")
        extractor = create_extractor(doc_type)
        local_result = extractor.extract(doc['text'])

        if doc_type == 'invoice':
            local_items = len(local_result.get('line_items', []))
        elif doc_type == 'receipt':
            local_items = len(local_result.get('items', []))
        elif doc_type == 'bank_statement':
            local_items = len(local_result.get('transactions', []))
        else:
            local_items = 0

        print(f"   Extracted: {local_items} items")
        print(f"   Confidence: {local_result.get('extraction_confidence', 0):.1f}%")

        # 2. AI voting
        print("\n2️⃣  AI voting (GPT-4 + Gemini + Ollama):")
        consensus_result, voting_details = self.voter.vote(doc['text'], doc_type)

        # 3. Check consensus
        has_consensus = voting_details['consensus_strength'] >= 0.67  # 2 out of 3

        print(f"\n3️⃣  Consensus check:")
        print(f"   Strength: {voting_details['consensus_strength']:.0%}")
        print(f"   Agreeing models: {', '.join(voting_details['agreeing_models'])}")

        if has_consensus:
            print("   ✅ CONSENSUS REACHED")

            # Save pattern
            self.learning_db.save_pattern(
                doc['text'], doc_type, consensus_result, voting_details
            )

            # Compare
            print(f"\n4️⃣  Comparison:")
            ai_items = voting_details['majority_count']
            match = local_items == ai_items

            print(f"   Local: {local_items} items")
            print(f"   AI consensus: {ai_items} items")

            if match:
                print("   ✅ LOCAL EXTRACTOR IS CORRECT!")
            else:
                diff = abs(local_items - ai_items)
                print(f"   ❌ MISMATCH (diff: {diff} items)")

            return {
                'doc_id': doc['id'],
                'doc_type': doc_type,
                'has_consensus': True,
                'match': match,
                'local_items': local_items,
                'ai_items': ai_items,
                'consensus_strength': voting_details['consensus_strength'],
                'agreeing_models': voting_details['agreeing_models']
            }
        else:
            print("   ❌ NO CONSENSUS - AI models disagree")
            return {
                'doc_id': doc['id'],
                'doc_type': doc_type,
                'has_consensus': False
            }

    def scan_emails_batch(self, num_emails: int = 100) -> Dict[str, Any]:
        """Scan batch of emails for any documents"""

        print(f"\n{'='*80}")
        print(f"🔍 SCANNING {num_emails} EMAILS FOR DOCUMENTS")
        print(f"{'='*80}")
        print(f"AI models: {list(self.voter.models.keys())}")
        print()

        # Load emails
        emails = self.load_all_emails(num_emails)

        if not emails:
            print("❌ No emails found")
            return {}

        # Scan each email
        results = []
        documents_found = 0

        for i, email in enumerate(emails, 1):
            print(f"\n[{i}/{len(emails)}]")
            try:
                result = self.scan_email(email)
                results.append(result)
                if result.get('found'):
                    documents_found += 1
            except Exception as e:
                logger.error(f"Failed to scan email: {e}")
                continue

        # Calculate summary by document type
        by_type = {}
        for r in results:
            if r.get('found') and r.get('doc_type'):
                doc_type = r['doc_type']
                if doc_type not in by_type:
                    by_type[doc_type] = {'total': 0, 'consensus': 0, 'matches': 0}

                by_type[doc_type]['total'] += 1
                if r.get('has_consensus'):
                    by_type[doc_type]['consensus'] += 1
                if r.get('match'):
                    by_type[doc_type]['matches'] += 1

        summary = {
            'total_scanned': len(emails),
            'documents_found': documents_found,
            'by_type': by_type,
            'results': results
        }

        # Print summary
        print(f"\n{'='*80}")
        print(f"📊 SCAN SUMMARY")
        print(f"{'='*80}")
        print(f"Emails scanned: {summary['total_scanned']}")
        print(f"Documents found: {summary['documents_found']}")
        print()

        for doc_type, stats in by_type.items():
            accuracy = (stats['matches'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"{doc_type.upper()}:")
            print(f"  Found: {stats['total']}")
            print(f"  Consensus: {stats['consensus']}/{stats['total']}")
            print(f"  Matches: {stats['matches']}/{stats['total']}")
            print(f"  Accuracy: {accuracy:.1f}%")
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

    print("\n🎯 REAL DOCUMENTS TEST WITH 3-AI CONSENSUS")
    print("="*80)
    print("Testing real documents from database")
    print("AI models: GPT-4 + Gemini + Ollama (qwen2.5:32b)")
    print()

    tester = RealDocumentTester(str(db_path))

    # Scan emails for any documents
    print("\n\n" + "📧"*40)
    scan_results = tester.scan_emails_batch(num_emails=100)  # Start with 100 emails
    all_results = scan_results

    # Save overall results
    results_file = 'real_documents_test_results.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n\n💾 Results saved: {results_file}")
    print(f"💾 Learning patterns saved: real_documents_learning.jsonl")

    # Show overall statistics
    print(f"\n{'='*80}")
    print("📊 OVERALL STATISTICS")
    print('='*80)

    for doc_type, results in all_results.items():
        print(f"\n{doc_type.upper()}:")
        print(f"  Accuracy: {results['accuracy']:.1f}%")
        print(f"  Perfect matches: {results['perfect_matches']}/{results['total_tested']}")

    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
