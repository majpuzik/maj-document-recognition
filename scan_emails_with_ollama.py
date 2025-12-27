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
Email Scanner with Ollama Final Classifier
Načte 1000 emailů z Thunderbird a klasifikuje je pomocí:
1. Keyword classifier (rychlý)
2. Ollama llama3.3:70b (finální rozhodčí)
"""
import sys
import logging
from pathlib import Path
from typing import List, Dict
import time
import mailbox
import email
from email.header import decode_header
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.integrations.thunderbird import ThunderbirdIntegration
from src.ai.classifier_improved import ImprovedAIClassifier
from src.ai.ollama_classifier import OllamaEmailClassifier
from src.database.db_manager import DatabaseManager
from src.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OllamaEmailScanner:
    """
    Scanner emailů s Ollama jako finálním rozhodčím

    Workflow:
    1. Načti email z Thunderbird
    2. Keyword klasifikace (rychlá)
    3. Ollama klasifikace (finální rozhodnutí)
    4. Ulož do databáze
    """

    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(self.config)
        self.thunderbird_scanner = ThunderbirdScanner()
        self.keyword_classifier = ImprovedAIClassifier(self.config, self.db_manager)
        self.ollama_classifier = OllamaEmailClassifier(model="llama3.3:70b")

        logger.info("✅ Initialized with Ollama llama3.3:70b")

    def scan_and_classify_emails(self, limit: int = 1000, skip_marketing: bool = True):
        """
        Naskenuj a klasifikuj N emailů z Thunderbird

        Args:
            limit: Kolik emailů zpracovat (default 1000)
            skip_marketing: Přeskočit marketingové emaily (default True)
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"📧 SCANNING {limit} EMAILS WITH OLLAMA CLASSIFIER")
        logger.info(f"{'='*70}\n")

        # Načti emaily z Thunderbird
        logger.info("📥 Loading emails from Thunderbird...")
        emails = self.thunderbird_scanner.scan_recent_emails(limit=limit)

        if not emails:
            logger.error("❌ No emails found!")
            return

        logger.info(f"✅ Found {len(emails)} emails\n")

        # Statistiky
        stats = {
            'total': len(emails),
            'processed': 0,
            'skipped_marketing': 0,
            'keyword_time': 0,
            'ollama_time': 0,
            'by_type': {},
            'ollama_overrides': 0  # Kolikrát Ollama změnila keyword klasifikaci
        }

        # Zpracuj každý email
        for idx, email in enumerate(emails, 1):
            try:
                logger.info(f"\n[{idx}/{len(emails)}] Processing: {email.get('subject', 'No Subject')[:60]}")

                subject = email.get('subject', '')
                body = email.get('body', '')
                sender = email.get('from', '')

                # Skip marketing pokud je požadováno
                if skip_marketing and self._is_marketing(subject, body, sender):
                    logger.info(f"   ⏭️  Skipping marketing email")
                    stats['skipped_marketing'] += 1
                    continue

                # 1. KEYWORD CLASSIFICATION (rychlá)
                start_time = time.time()
                keyword_result = self.keyword_classifier.classify_text(body)
                keyword_time = time.time() - start_time
                stats['keyword_time'] += keyword_time

                keyword_type = keyword_result.get('document_type', 'jine')
                keyword_conf = keyword_result.get('confidence', 0.0)

                logger.info(f"   🔍 Keyword: {keyword_type} ({keyword_conf:.2f}) in {keyword_time:.2f}s")

                # 2. OLLAMA CLASSIFICATION (finální rozhodčí)
                start_time = time.time()
                ollama_result = self.ollama_classifier.classify_email(subject, body, sender)
                ollama_time = time.time() - start_time
                stats['ollama_time'] += ollama_time

                final_type = ollama_result.get('document_type', 'jine')
                final_conf = ollama_result.get('confidence', 0.0)
                reasoning = ollama_result.get('reasoning', '')

                logger.info(f"   🤖 Ollama: {final_type} ({final_conf:.2f}) in {ollama_time:.2f}s")

                if reasoning:
                    logger.info(f"   💭 Reason: {reasoning}")

                # Zaznamenej, pokud Ollama změnila rozhodnutí
                if keyword_type != final_type:
                    logger.info(f"   🔄 OVERRIDE: {keyword_type} → {final_type}")
                    stats['ollama_overrides'] += 1

                # 3. ULOŽ DO DATABÁZE
                self._save_to_database(email, final_type, final_conf, keyword_result, ollama_result)

                # Statistiky
                stats['processed'] += 1
                stats['by_type'][final_type] = stats['by_type'].get(final_type, 0) + 1

                # Progress report každých 10 emailů
                if idx % 10 == 0:
                    self._print_progress(stats)

            except Exception as e:
                logger.error(f"   ❌ Error processing email: {e}")
                import traceback
                traceback.print_exc()
                continue

        # Finální report
        self._print_final_report(stats)

    def _is_marketing(self, subject: str, body: str, sender: str) -> bool:
        """Rychlá detekce marketingu (před Ollama)"""
        marketing_keywords = [
            'unsubscribe', 'newsletter', 'marketing', 'promo',
            'discount', 'sale', 'offer', 'sleva', 'akce',
            'newsletter', 'odhlásit', 'reklama'
        ]

        text = (subject + ' ' + body + ' ' + sender).lower()

        for keyword in marketing_keywords:
            if keyword in text:
                return True

        return False

    def _save_to_database(self, email: Dict, document_type: str, confidence: float,
                         keyword_result: Dict, ollama_result: Dict):
        """Ulož email s klasifikací do databáze"""

        metadata = {
            'subject': email.get('subject', ''),
            'from': email.get('from', ''),
            'date': email.get('date', ''),
            'keyword_classification': keyword_result,
            'ollama_classification': ollama_result,
            'message_id': email.get('message_id', '')
        }

        self.db_manager.insert_document(
            file_path=f"email://{email.get('message_id', 'unknown')}",
            file_name=email.get('subject', 'No Subject')[:100],
            file_size=len(email.get('body', '')),
            file_hash=email.get('message_id', ''),
            ocr_text=email.get('body', '')[:5000],
            ocr_confidence=100.0,
            document_type=document_type,
            ai_confidence=confidence,
            ai_method='ollama_final',
            sender=email.get('from', ''),
            subject=email.get('subject', ''),
            date_received=email.get('date', ''),
            metadata=str(metadata)
        )

    def _print_progress(self, stats: Dict):
        """Vypiš průběžnou statistiku"""
        processed = stats['processed']
        total = stats['total']
        skipped = stats['skipped_marketing']

        avg_keyword = stats['keyword_time'] / processed if processed > 0 else 0
        avg_ollama = stats['ollama_time'] / processed if processed > 0 else 0

        logger.info(f"\n📊 PROGRESS: {processed}/{total} emails processed, {skipped} marketing skipped")
        logger.info(f"   ⏱️  Avg time: Keyword {avg_keyword:.2f}s, Ollama {avg_ollama:.2f}s")
        logger.info(f"   🔄 Ollama overrides: {stats['ollama_overrides']}")

    def _print_final_report(self, stats: Dict):
        """Vypiš finální statistiku"""
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 FINAL REPORT")
        logger.info(f"{'='*70}")
        logger.info(f"\nTotal emails: {stats['total']}")
        logger.info(f"Processed: {stats['processed']}")
        logger.info(f"Skipped (marketing): {stats['skipped_marketing']}")
        logger.info(f"Ollama overrides: {stats['ollama_overrides']} ({stats['ollama_overrides']/stats['processed']*100:.1f}%)")

        logger.info(f"\n⏱️  Time Statistics:")
        logger.info(f"   Total keyword time: {stats['keyword_time']:.2f}s")
        logger.info(f"   Total Ollama time: {stats['ollama_time']:.2f}s")
        logger.info(f"   Avg per email: {(stats['keyword_time'] + stats['ollama_time'])/stats['processed']:.2f}s")

        logger.info(f"\n📋 Classification by Type:")
        for doc_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
            percentage = count / stats['processed'] * 100
            logger.info(f"   {doc_type:30s}: {count:4d} ({percentage:5.1f}%)")

        logger.info(f"\n{'='*70}")
        logger.info(f"✅ SCAN COMPLETE!")
        logger.info(f"{'='*70}\n")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Scan emails with Ollama classifier')
    parser.add_argument('--limit', type=int, default=1000, help='Number of emails to process (default: 1000)')
    parser.add_argument('--no-skip-marketing', action='store_true', help='Include marketing emails')

    args = parser.parse_args()

    scanner = OllamaEmailScanner()
    scanner.scan_and_classify_emails(
        limit=args.limit,
        skip_marketing=not args.no_skip_marketing
    )


if __name__ == '__main__':
    main()
