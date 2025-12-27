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
Multilingual Support Test
=========================
Test current production models on English and German documents.

Tests:
- Czech invoices (baseline)
- English invoices
- German invoices

Models tested:
- qwen2.5:32b (general model)
- czech-finance-speed (Czech specialist)

Author: Claude Code
Date: 2025-12-04
"""

import sys
import time
import json
import logging
import requests
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class MultilingualTester:
    """Test OCR models on multiple languages"""

    def __init__(self):
        self.ollama_endpoint = "http://localhost:11434"
        self.results = []

    def test_connection(self) -> bool:
        """Test Ollama connection"""
        try:
            response = requests.get(f"{self.ollama_endpoint}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ Ollama connected: {self.ollama_endpoint}")
                return True
            else:
                logger.error(f"❌ Ollama not responding")
                return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to Ollama: {e}")
            return False

    def call_ollama_model(self, text: str, model: str, language: str) -> Tuple[str, float, bool]:
        """Call Ollama model and measure time"""

        # Language-specific prompts
        if language == "en":
            prompt = f"""Extract structured data from this English business document.
Find: company name, company number, VAT number, amounts, dates, items.

Document text:
{text[:3000]}

Return JSON only with extracted fields."""

        elif language == "de":
            prompt = f"""Extrahieren Sie strukturierte Daten aus diesem deutschen Geschäftsdokument.
Finden Sie: Firmenname, Steuernummer, USt-IdNr, Beträge, Datum, Artikel.

Document text:
{text[:3000]}

Geben Sie nur JSON mit extrahierten Feldern zurück."""

        else:  # Czech
            prompt = f"""Extrahuj strukturovaná data z tohoto českého obchodního dokumentu.
Najdi: název firmy, IČO, DIČ, částky, data, položky.

Document text:
{text[:3000]}

Vrať pouze JSON s extrahovanými poli."""

        start_time = time.time()

        try:
            response = requests.post(
                f"{self.ollama_endpoint}/api/generate",
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False
                },
                timeout=60
            )

            elapsed = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                success = len(response_text.strip()) > 10
                return response_text, elapsed, success
            else:
                return f"Error: {response.status_code}", elapsed, False

        except Exception as e:
            elapsed = time.time() - start_time
            return f"Exception: {e}", elapsed, False

    def test_sample_documents(self):
        """Test with sample documents in different languages"""

        logger.info("\n" + "=" * 80)
        logger.info("🌍 MULTILINGUAL SUPPORT TEST")
        logger.info("=" * 80)

        # Test documents
        test_docs = [
            {
                "language": "cs",
                "name": "Czech Invoice",
                "text": """
FAKTURA č. 2025001

Dodavatel:
Firma ABC s.r.o.
IČO: 12345678
DIČ: CZ12345678
Sídlo: Václavské náměstí 1, Praha 1

Odběratel:
XYZ a.s.
IČO: 87654321
DIČ: CZ87654321

Položky:
1. Notebook Dell Latitude 5420 - 25 990 Kč
2. Myš Logitech MX Master 3 - 2 490 Kč
3. Klávesnice Logitech MX Keys - 3 290 Kč

Cena celkem bez DPH: 31 770 Kč
DPH 21%: 6 671,70 Kč
Cena celkem s DPH: 38 441,70 Kč

Datum vystavení: 2025-03-15
Datum splatnosti: 2025-04-15
Variabilní symbol: 2025001
"""
            },
            {
                "language": "en",
                "name": "English Invoice",
                "text": """
INVOICE No. 2025001

Supplier:
ABC Company Ltd
Company No: 12345678
VAT No: GB123456789
Address: 10 Downing Street, London, UK

Customer:
XYZ Corporation Inc
Company No: 87654321
VAT No: GB987654321

Items:
1. Dell Latitude 5420 Notebook - £1,099.00
2. Logitech MX Master 3 Mouse - £99.00
3. Logitech MX Keys Keyboard - £129.00

Subtotal (excl. VAT): £1,327.00
VAT 20%: £265.40
Total (incl. VAT): £1,592.40

Invoice Date: March 15, 2025
Due Date: April 15, 2025
Reference: INV-2025001
"""
            },
            {
                "language": "de",
                "name": "German Invoice",
                "text": """
RECHNUNG Nr. 2025001

Lieferant:
ABC GmbH
Steuernummer: 12345678
USt-IdNr: DE123456789
Adresse: Friedrichstraße 1, Berlin, Deutschland

Kunde:
XYZ AG
Steuernummer: 87654321
USt-IdNr: DE987654321

Positionen:
1. Dell Latitude 5420 Notebook - 1.299,00 €
2. Logitech MX Master 3 Maus - 99,00 €
3. Logitech MX Keys Tastatur - 129,00 €

Zwischensumme (ohne MwSt): 1.527,00 €
MwSt 19%: 290,13 €
Gesamtsumme (inkl. MwSt): 1.817,13 €

Rechnungsdatum: 15. März 2025
Fälligkeitsdatum: 15. April 2025
Referenz: RE-2025001
"""
            }
        ]

        models = [
            "qwen2.5:32b",
            "czech-finance-speed"
        ]

        # Test each document with each model
        for doc in test_docs:
            logger.info(f"\n{'=' * 80}")
            logger.info(f"📄 Testing: {doc['name']} ({doc['language'].upper()})")
            logger.info(f"{'=' * 80}")

            for model in models:
                logger.info(f"\n🔬 Testing model: {model}")

                response, elapsed, success = self.call_ollama_model(
                    doc['text'],
                    model,
                    doc['language']
                )

                # Store result
                self.results.append({
                    'language': doc['language'],
                    'document': doc['name'],
                    'model': model,
                    'time': elapsed,
                    'success': success,
                    'response_length': len(response),
                    'response_preview': response[:200]
                })

                if success:
                    logger.info(f"   ✅ Success in {elapsed:.2f}s")
                    logger.info(f"   📊 Response length: {len(response)} chars")
                    logger.info(f"   📝 Preview: {response[:150]}...")
                else:
                    logger.info(f"   ❌ Failed in {elapsed:.2f}s")
                    logger.info(f"   ⚠️  Response: {response[:100]}")

    def generate_report(self):
        """Generate comparison report"""

        logger.info("\n" + "=" * 80)
        logger.info("📊 MULTILINGUAL SUPPORT RESULTS")
        logger.info("=" * 80)

        # Group by language
        by_language = {}
        for result in self.results:
            lang = result['language']
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(result)

        # Print results by language
        for lang in ['cs', 'en', 'de']:
            if lang not in by_language:
                continue

            lang_name = {'cs': 'Czech', 'en': 'English', 'de': 'German'}[lang]
            logger.info(f"\n## {lang_name.upper()} ({lang})")
            logger.info("-" * 80)

            for result in by_language[lang]:
                status = "✅" if result['success'] else "❌"
                logger.info(f"{status} {result['model']:25} | {result['time']:6.2f}s | {result['response_length']:5d} chars")

        # Summary table
        logger.info("\n## SUMMARY TABLE")
        logger.info("-" * 80)
        logger.info(f"{'Model':25} | {'Czech':8} | {'English':8} | {'German':8}")
        logger.info("-" * 80)

        for model in ["qwen2.5:32b", "czech-finance-speed"]:
            model_results = [r for r in self.results if r['model'] == model]

            cs_result = next((r for r in model_results if r['language'] == 'cs'), None)
            en_result = next((r for r in model_results if r['language'] == 'en'), None)
            de_result = next((r for r in model_results if r['language'] == 'de'), None)

            cs_status = "✅ OK" if cs_result and cs_result['success'] else "❌ FAIL"
            en_status = "✅ OK" if en_result and en_result['success'] else "❌ FAIL"
            de_status = "✅ OK" if de_result and de_result['success'] else "❌ FAIL"

            logger.info(f"{model:25} | {cs_status:8} | {en_status:8} | {de_status:8}")

        # Save results to JSON
        output_file = Path(__file__).parent / "multilingual_test_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'results': self.results,
                'summary': {
                    'total_tests': len(self.results),
                    'successful': sum(1 for r in self.results if r['success']),
                    'failed': sum(1 for r in self.results if not r['success'])
                }
            }, f, indent=2, ensure_ascii=False)

        logger.info(f"\n✅ Results saved: {output_file}")

        # Conclusion
        logger.info("\n" + "=" * 80)
        logger.info("🎯 CONCLUSION")
        logger.info("=" * 80)

        success_rate = sum(1 for r in self.results if r['success']) / len(self.results) * 100
        logger.info(f"\nOverall success rate: {success_rate:.1f}%")

        # Per-language success rates
        for lang in ['cs', 'en', 'de']:
            lang_results = [r for r in self.results if r['language'] == lang]
            if lang_results:
                lang_success = sum(1 for r in lang_results if r['success']) / len(lang_results) * 100
                lang_name = {'cs': 'Czech', 'en': 'English', 'de': 'German'}[lang]
                logger.info(f"{lang_name:8}: {lang_success:5.1f}% success rate")


def main():
    """Main test function"""

    tester = MultilingualTester()

    # Test connection
    if not tester.test_connection():
        logger.error("❌ Cannot connect to Ollama. Exiting.")
        return 1

    # Run tests
    tester.test_sample_documents()

    # Generate report
    tester.generate_report()

    return 0


if __name__ == "__main__":
    sys.exit(main())
