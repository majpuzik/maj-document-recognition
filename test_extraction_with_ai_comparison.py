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
Benchmark test: Structured Data Extraction vs External AI Models
Compares local extractors with GPT-4 and Gemini for 100% accuracy

Author: Claude Code
Date: 2025-11-30
"""

import os
import sys
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import time

# Import local extractors (direct import to avoid cv2 dependency)
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))

from data_extractors import create_extractor
from extraction_schemas import SchemaValidator, format_for_paperless

# External AI imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️  OpenAI not available (pip install openai)")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️  Gemini not available (pip install google-generativeai)")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIExtractor:
    """Wrapper for external AI model extraction"""

    def __init__(self, model_type: str, api_key: str):
        self.model_type = model_type
        self.api_key = api_key

        if model_type == 'openai':
            openai.api_key = api_key
            self.model_name = "gpt-4o"
        elif model_type == 'gemini':
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro')

    def extract_invoice(self, text: str) -> Dict[str, Any]:
        """Extract invoice data using AI"""
        prompt = """
Extract ALL line items from this invoice in JSON format.

Required format:
{
  "line_items": [
    {
      "line_number": 1,
      "description": "item description",
      "quantity": 1.0,
      "unit": "ks",
      "unit_price": 100.00,
      "vat_rate": 21,
      "vat_amount": 21.00,
      "total_net": 100.00,
      "total_gross": 121.00
    }
  ],
  "summary": {
    "total_net": 100.00,
    "total_vat": 21.00,
    "total_gross": 121.00,
    "currency": "CZK"
  }
}

Invoice text:
""" + text

        try:
            if self.model_type == 'openai':
                response = openai.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a structured data extraction expert. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                result_text = response.choices[0].message.content
            elif self.model_type == 'gemini':
                response = self.model.generate_content(prompt)
                result_text = response.text

            # Parse JSON
            # Remove markdown code blocks if present
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.startswith('```'):
                result_text = result_text[3:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]

            result = json.loads(result_text.strip())
            return result

        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return {"line_items": [], "summary": {}, "error": str(e)}

    def extract_receipt(self, text: str) -> Dict[str, Any]:
        """Extract receipt data using AI"""
        prompt = """
Extract ALL items from this receipt in JSON format.

Required format:
{
  "items": [
    {
      "line_number": 1,
      "description": "item name",
      "quantity": 1.0,
      "unit": "ks",
      "unit_price": 10.00,
      "vat_rate": 21,
      "total": 10.00
    }
  ],
  "summary": {
    "total": 10.00,
    "vat_breakdown": {"21": 1.74, "15": 0.0, "10": 0.0},
    "currency": "CZK"
  },
  "eet": {
    "fik": "FIK code if present",
    "bkp": "BKP code if present"
  }
}

Receipt text:
""" + text

        try:
            if self.model_type == 'openai':
                response = openai.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a structured data extraction expert. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                result_text = response.choices[0].message.content
            elif self.model_type == 'gemini':
                response = self.model.generate_content(prompt)
                result_text = response.text

            # Parse JSON
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.startswith('```'):
                result_text = result_text[3:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]

            result = json.loads(result_text.strip())
            return result

        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return {"items": [], "summary": {}, "eet": {}, "error": str(e)}


class ExtractionBenchmark:
    """Benchmark structured data extraction against AI models"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        # Load API keys
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.gemini_key = os.getenv('GEMINI_API_KEY')

        # Initialize AI extractors
        self.ai_extractors = {}
        if OPENAI_AVAILABLE and self.openai_key:
            self.ai_extractors['gpt4'] = AIExtractor('openai', self.openai_key)
        if GEMINI_AVAILABLE and self.gemini_key:
            self.ai_extractors['gemini'] = AIExtractor('gemini', self.gemini_key)

        logger.info(f"AI models available: {list(self.ai_extractors.keys())}")

    def load_test_documents(self, doc_type: str, limit: int = 20) -> List[Dict]:
        """Load real documents from database"""

        # Map doc types to database fields
        type_mapping = {
            'invoice': ['faktura', 'invoice'],
            'receipt': ['účtenka', 'receipt', 'stvrzenka'],
            'bank_statement': ['výpis', 'statement']
        }

        keywords = type_mapping.get(doc_type, [])
        where_clause = ' OR '.join([f"email_subject LIKE '%{kw}%' OR email_body_compact LIKE '%{kw}%'"
                                     for kw in keywords])

        query = f"""
        SELECT
            id,
            email_subject,
            email_from,
            email_body_compact,
            email_body_full,
            email_date,
            has_pdf
        FROM email_evidence
        WHERE ({where_clause})
            AND email_date >= '2024-01-01'
        ORDER BY email_date DESC
        LIMIT ?
        """

        cursor = self.conn.execute(query, (limit,))
        docs = []

        for row in cursor.fetchall():
            text = row['email_body_compact'] or row['email_body_full'] or ''
            if len(text) > 100:  # Skip too short documents
                docs.append({
                    'id': row['id'],
                    'subject': row['email_subject'],
                    'from': row['email_from'],
                    'text': text[:5000],  # Limit to 5000 chars for AI
                    'date': row['email_date'],
                    'has_pdf': row['has_pdf']
                })

        logger.info(f"Loaded {len(docs)} {doc_type} documents")
        return docs

    def compare_results(self, local_result: Dict, ai_results: Dict[str, Dict],
                       doc_type: str) -> Dict[str, Any]:
        """Compare local extraction with AI results"""

        comparison = {
            'local': local_result,
            'ai': ai_results,
            'analysis': {}
        }

        # Analyze based on doc type
        if doc_type == 'invoice':
            local_items = len(local_result.get('line_items', []))

            for ai_name, ai_result in ai_results.items():
                ai_items = len(ai_result.get('line_items', []))

                comparison['analysis'][ai_name] = {
                    'item_count_match': local_items == ai_items,
                    'local_items': local_items,
                    'ai_items': ai_items,
                    'item_count_diff': abs(local_items - ai_items)
                }

                # Compare totals
                local_total = local_result.get('summary', {}).get('total_gross', 0)
                ai_total = ai_result.get('summary', {}).get('total_gross', 0)

                comparison['analysis'][ai_name]['total_match'] = abs(local_total - ai_total) < 0.01
                comparison['analysis'][ai_name]['total_diff'] = abs(local_total - ai_total)

        elif doc_type == 'receipt':
            local_items = len(local_result.get('items', []))

            for ai_name, ai_result in ai_results.items():
                ai_items = len(ai_result.get('items', []))

                comparison['analysis'][ai_name] = {
                    'item_count_match': local_items == ai_items,
                    'local_items': local_items,
                    'ai_items': ai_items,
                    'eet_match': (
                        local_result.get('eet', {}).get('fik') == ai_result.get('eet', {}).get('fik')
                    )
                }

        return comparison

    def run_benchmark(self, doc_type: str, num_docs: int = 20) -> Dict[str, Any]:
        """Run full benchmark for document type"""

        print("=" * 80)
        print(f"🔬 BENCHMARK: {doc_type.upper()} EXTRACTION")
        print("=" * 80)
        print(f"Testing {num_docs} documents")
        print(f"AI models: {list(self.ai_extractors.keys())}")
        print()

        # Load test documents
        docs = self.load_test_documents(doc_type, num_docs)

        if not docs:
            print(f"❌ No {doc_type} documents found in database")
            return {}

        # Create local extractor
        local_extractor = create_extractor(doc_type)

        # Results storage
        results = {
            'doc_type': doc_type,
            'total_docs': len(docs),
            'successful_extractions': 0,
            'comparisons': [],
            'summary': {}
        }

        # Process each document
        for i, doc in enumerate(docs, 1):
            print(f"\n[{i}/{len(docs)}] Processing: {doc['subject'][:60]}...")

            # Local extraction
            print(f"  🔧 Local extractor...", end=' ')
            local_start = time.time()
            local_result = local_extractor.extract(doc['text'])
            local_time = time.time() - local_start
            print(f"✅ ({local_time:.2f}s)")

            # Validate
            is_valid, error = SchemaValidator.validate(local_result, doc_type)
            if not is_valid:
                print(f"  ⚠️  Local validation failed: {error}")
                continue

            # AI extractions
            ai_results = {}
            for ai_name, ai_extractor in self.ai_extractors.items():
                print(f"  🤖 {ai_name.upper()}...", end=' ')
                ai_start = time.time()

                try:
                    if doc_type == 'invoice':
                        ai_result = ai_extractor.extract_invoice(doc['text'])
                    elif doc_type == 'receipt':
                        ai_result = ai_extractor.extract_receipt(doc['text'])
                    else:
                        ai_result = {}

                    ai_time = time.time() - ai_start
                    ai_results[ai_name] = ai_result
                    print(f"✅ ({ai_time:.2f}s)")
                except Exception as e:
                    print(f"❌ {e}")
                    ai_results[ai_name] = {"error": str(e)}

            # Compare results
            comparison = self.compare_results(local_result, ai_results, doc_type)
            results['comparisons'].append(comparison)
            results['successful_extractions'] += 1

            # Show quick analysis
            for ai_name, analysis in comparison['analysis'].items():
                if doc_type == 'invoice':
                    match = "✅" if analysis['item_count_match'] else "❌"
                    print(f"    {match} {ai_name}: {analysis['local_items']} vs {analysis['ai_items']} items")
                elif doc_type == 'receipt':
                    match = "✅" if analysis['item_count_match'] else "❌"
                    print(f"    {match} {ai_name}: {analysis['local_items']} vs {analysis['ai_items']} items")

        # Calculate summary statistics
        if results['comparisons']:
            for ai_name in self.ai_extractors.keys():
                matches = sum(1 for c in results['comparisons']
                            if c['analysis'].get(ai_name, {}).get('item_count_match', False))

                results['summary'][ai_name] = {
                    'item_count_accuracy': (matches / len(results['comparisons'])) * 100,
                    'matches': matches,
                    'total': len(results['comparisons'])
                }

        return results

    def print_summary(self, results: Dict[str, Any]):
        """Print benchmark summary"""

        print("\n" + "=" * 80)
        print("📊 BENCHMARK RESULTS SUMMARY")
        print("=" * 80)
        print(f"Document type: {results['doc_type']}")
        print(f"Total documents tested: {results['total_docs']}")
        print(f"Successful extractions: {results['successful_extractions']}")
        print()

        print("🎯 ACCURACY COMPARISON:")
        print("-" * 80)

        for ai_name, stats in results.get('summary', {}).items():
            print(f"{ai_name.upper()}:")
            print(f"  Item count accuracy: {stats['item_count_accuracy']:.1f}% ({stats['matches']}/{stats['total']})")

        print("\n" + "=" * 80)

        # Identify areas for improvement
        print("\n🔍 AREAS FOR IMPROVEMENT:")
        print("-" * 80)

        mismatches = []
        for comp in results['comparisons']:
            for ai_name, analysis in comp['analysis'].items():
                if not analysis.get('item_count_match', False):
                    mismatches.append({
                        'ai': ai_name,
                        'local': analysis.get('local_items', 0),
                        'ai_items': analysis.get('ai_items', 0),
                        'diff': analysis.get('item_count_diff', 0)
                    })

        if mismatches:
            print(f"Found {len(mismatches)} mismatches:")
            for mm in mismatches[:5]:  # Show first 5
                print(f"  - {mm['ai']}: Local={mm['local']} vs AI={mm['ai_items']} (diff={mm['diff']})")
        else:
            print("✅ No mismatches found! 100% accuracy achieved!")

    def save_results(self, results: Dict[str, Any], output_file: str):
        """Save detailed results to JSON"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Detailed results saved: {output_file}")


def main():
    """Main benchmark function"""

    # Load env vars
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env.litellm')

    # Database path
    db_path = Path.home() / 'apps/maj-subscriptions-local/data/subscriptions.db'

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return

    # Create benchmark
    benchmark = ExtractionBenchmark(str(db_path))

    # Run benchmarks
    print("\n🚀 Starting extraction benchmark with AI comparison...\n")

    # Test invoices
    invoice_results = benchmark.run_benchmark('invoice', num_docs=10)
    if invoice_results:
        benchmark.print_summary(invoice_results)
        benchmark.save_results(invoice_results, 'benchmark_invoice_results.json')

    # Test receipts
    receipt_results = benchmark.run_benchmark('receipt', num_docs=10)
    if receipt_results:
        benchmark.print_summary(receipt_results)
        benchmark.save_results(receipt_results, 'benchmark_receipt_results.json')

    print("\n✅ Benchmark complete!")


if __name__ == "__main__":
    main()
