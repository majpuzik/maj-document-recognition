#!/usr/bin/env python3
"""
MAJ Document Recognition - MBW Document Processor
Zpracování dokumentů z Dropbox MBW složky s možností selekce
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier_improved import ImprovedAIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.bank_statement_processor import BankStatementProcessor
from src.ocr.pdf_ocr_layer import PDFOCRLayerHandler


class MBWDocumentProcessor:
    """Processor pro MBW dokumenty s možností selekce"""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize processor"""
        # Load config
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.db_manager = DatabaseManager(self.config)
        self.document_processor = DocumentProcessor(self.config)
        self.classifier = ImprovedAIClassifier(self.config, self.db_manager)

        # Bank statement processor
        self.bank_processor = BankStatementProcessor()

        # PDF OCR layer handler
        self.ocr_handler = PDFOCRLayerHandler()

        # Results
        self.processed_documents = []

    def find_mbw_documents(self, source_dir: str) -> List[Path]:
        """
        Najít všechny dokumenty v MBW složce

        Args:
            source_dir: Cesta ke složce MBW

        Returns:
            Seznam cest k dokumentům
        """
        source_path = Path(source_dir).expanduser()

        if not source_path.exists():
            self.logger.error(f"Složka neexistuje: {source_path}")
            return []

        # Podporované formáty
        extensions = [
            '.pdf', '.PDF',
            '.jpg', '.JPG', '.jpeg', '.JPEG', '.png', '.PNG',
            '.xml', '.XML',  # Bank statements (CAMT.053)
            '.sta', '.STA',  # Bank statements (MT940)
            '.mt940', '.MT940',  # Bank statements
            '.gpc', '.GPC',  # Bank statements (ABO/GPC)
            '.abo', '.ABO',  # Bank statements
            '.csv', '.CSV'  # Bank statements / various formats
        ]

        documents = []
        for ext in extensions:
            documents.extend(source_path.rglob(f'*{ext}'))

        self.logger.info(f"Nalezeno {len(documents)} dokumentů v {source_path}")
        return sorted(documents)

    def _is_bank_statement(self, file_path: Path) -> bool:
        """
        Zkontrolovat, jestli je soubor bankovní výpis

        Args:
            file_path: Cesta k souboru

        Returns:
            True pokud je to pravděpodobně bankovní výpis
        """
        # Check file extension
        if file_path.suffix.lower() in ['.sta', '.mt940', '.gpc', '.abo']:
            return True

        # Check filename patterns
        filename_lower = file_path.name.lower()
        if any(pattern in filename_lower for pattern in
              ['vypis', 'statement', 'kontoauszug', 'platby', 'transakce']):
            return True

        # For XML, check content
        if file_path.suffix.lower() == '.xml':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(1000)  # First 1000 chars
                    if 'camt.053' in content or 'BkToCstmrStmt' in content:
                        return True
            except:
                pass

        return False

    def _process_bank_statement(self, file_path: Path) -> Dict:
        """
        Zpracovat bankovní výpis

        Args:
            file_path: Cesta k bankovnímu výpisu

        Returns:
            Zpracovaná data bankovního výpisu
        """
        self.logger.info(f"📊 Zpracovávám jako bankovní výpis: {file_path.name}")

        try:
            # Parse bank statement
            statement = self.bank_processor.parse_file(str(file_path))

            # Generate Paperless metadata
            paperless_meta = self.bank_processor.generate_paperless_metadata(statement)

            # File metadata
            stat = file_path.stat()

            result = {
                "success": True,
                "file_path": str(file_path),
                "file_name": file_path.name,
                "file_size": stat.st_size,
                "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
                "file_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),

                # Bank statement specific
                "document_type": "bankovni_vypis",
                "confidence": 0.95,  # High confidence for structured data
                "classification_method": "bank_statement_parser",

                # Bank statement data
                "bank_statement": {
                    "id": statement.statement_id,
                    "bank": statement.bank_name,
                    "account": statement.account_number,
                    "iban": statement.iban,
                    "period_from": statement.from_date.isoformat() if statement.from_date else None,
                    "period_to": statement.to_date.isoformat() if statement.to_date else None,
                    "opening_balance": float(statement.opening_balance),
                    "closing_balance": float(statement.closing_balance),
                    "currency": statement.currency,
                    "transaction_count": len(statement.transactions),
                    "format": statement.original_format
                },

                # Paperless metadata
                "paperless_title": paperless_meta['title'],
                "paperless_tags": paperless_meta['tags'],
                "paperless_correspondent": paperless_meta['correspondent'],

                # Auto-select high confidence documents
                "selected": True,
            }

            # Save to DB
            doc_id = self.db_manager.insert_document(
                file_path=str(file_path),
                ocr_text=f"Bank statement: {statement.account_number}, {len(statement.transactions)} transactions",
                ocr_confidence=0.95,
                document_type="bankovni_vypis",
                ai_confidence=0.95,
                ai_method="bank_statement_parser",
                metadata=result
            )
            result["db_id"] = doc_id

            return result

        except Exception as e:
            self.logger.error(f"Chyba při zpracování bankovního výpisu: {e}")
            # Fall back to regular processing
            return None

    def process_document(self, file_path: Path) -> Dict:
        """
        Zpracovat jeden dokument

        Args:
            file_path: Cesta k dokumentu

        Returns:
            Zpracovaná data dokumentu
        """
        self.logger.info(f"Zpracovávám: {file_path.name}")

        try:
            # Check if it's a bank statement first
            if self._is_bank_statement(file_path):
                result = self._process_bank_statement(file_path)
                if result:  # Successfully processed as bank statement
                    return result
                # If failed, fall through to regular processing

            # If PDF, ensure OCR layer exists
            file_to_process = file_path
            if file_path.suffix.lower() == '.pdf':
                ocr_added, ocr_file = self.ocr_handler.process_pdf_with_ocr(str(file_path))
                if ocr_added:
                    self.logger.info(f"🔍 OCR layer added to {file_path.name}")
                    file_to_process = Path(ocr_file)

            # OCR
            ocr_result = self.document_processor.process_document(str(file_to_process))

            if not ocr_result.get("success"):
                return {
                    "success": False,
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "error": ocr_result.get("error", "OCR failed")
                }

            text = ocr_result.get("text", "")

            # AI Classification
            classification = self.classifier.classify(text, {
                "sender": "",
                "file_name": file_path.name
            })

            # File metadata
            stat = file_path.stat()
            file_size = stat.st_size
            file_mtime = datetime.fromtimestamp(stat.st_mtime)

            # Prepare result
            result = {
                "success": True,
                "file_path": str(file_path),
                "file_name": file_path.name,
                "file_size": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "file_date": file_mtime.isoformat(),
                "file_date_formatted": file_mtime.strftime("%Y-%m-%d %H:%M:%S"),

                # OCR
                "text": text,
                "text_length": len(text),
                "ocr_confidence": ocr_result.get("confidence", 0),
                "language": ocr_result.get("language", "unknown"),

                # Classification
                "document_type": classification.get("type", "jine"),
                "confidence": classification.get("confidence", 0),
                "classification_method": classification.get("method", "unknown"),
                "classification_details": classification.get("details", {}),

                # Paperless metadata
                "paperless_title": self._generate_title(file_path.name, classification),
                "paperless_tags": self._generate_tags(classification),
                "paperless_correspondent": self._extract_correspondent(text, classification),

                # Selection (default: selected if confidence > 0.7)
                "selected": classification.get("confidence", 0) >= 0.7,
            }

            # Save to DB
            doc_id = self.db_manager.insert_document(
                file_path=str(file_path),
                ocr_text=text,
                ocr_confidence=ocr_result.get("confidence", 0),
                document_type=classification.get("type", "jine"),
                ai_confidence=classification.get("confidence", 0),
                ai_method=classification.get("method", "unknown"),
                metadata=result
            )
            result["db_id"] = doc_id

            return result

        except Exception as e:
            self.logger.error(f"Chyba při zpracování {file_path}: {e}", exc_info=True)
            return {
                "success": False,
                "file_path": str(file_path),
                "file_name": file_path.name,
                "error": str(e)
            }

    def _generate_title(self, file_name: str, classification: Dict) -> str:
        """Generovat název pro Paperless"""
        doc_type = classification.get("type", "dokument")
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Remove extension
        base_name = Path(file_name).stem

        return f"{doc_type}_{date_str}_{base_name}"

    def _generate_tags(self, classification: Dict) -> List[str]:
        """Generovat tagy pro Paperless"""
        tags = ["MBW"]  # Základní tag

        doc_type = classification.get("type", "")
        if doc_type:
            tags.append(doc_type)

        confidence = classification.get("confidence", 0)
        if confidence >= 0.9:
            tags.append("high_confidence")
        elif confidence < 0.7:
            tags.append("low_confidence")

        return tags

    def _extract_correspondent(self, text: str, classification: Dict) -> Optional[str]:
        """Extrahovat odesílatele z textu"""
        # TODO: Implementovat pokročilou extrakci
        # Zatím jen základní heuristika

        doc_type = classification.get("type", "")

        # Pro faktury hledej IČO/firmu
        if doc_type == "faktura":
            # Hledej řádky s "s.r.o.", "a.s." apod.
            for line in text.split('\n')[:20]:  # Prvních 20 řádků
                if any(x in line.lower() for x in ['s.r.o.', 'a.s.', 'spol.', 'gmbh']):
                    return line.strip()[:50]  # Max 50 znaků

        return None

    def process_all(self, source_dir: str) -> List[Dict]:
        """
        Zpracovat všechny dokumenty

        Args:
            source_dir: Cesta ke složce MBW

        Returns:
            Seznam zpracovaných dokumentů
        """
        documents = self.find_mbw_documents(source_dir)

        if not documents:
            self.logger.warning("Žádné dokumenty k zpracování")
            return []

        self.logger.info(f"Zahajuji zpracování {len(documents)} dokumentů...")

        results = []
        for i, doc_path in enumerate(documents, 1):
            self.logger.info(f"[{i}/{len(documents)}] Zpracovávám: {doc_path.name}")

            result = self.process_document(doc_path)
            results.append(result)

            # Progress
            if i % 10 == 0:
                success_count = sum(1 for r in results if r.get("success"))
                self.logger.info(f"Progress: {i}/{len(documents)} ({success_count} úspěšných)")

        self.processed_documents = results
        return results

    def save_results(self, output_path: str):
        """
        Uložit výsledky do JSON

        Args:
            output_path: Cesta k výstupnímu souboru
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'processed_date': datetime.now().isoformat(),
                'total_documents': len(self.processed_documents),
                'successful': sum(1 for d in self.processed_documents if d.get('success')),
                'failed': sum(1 for d in self.processed_documents if not d.get('success')),
                'documents': self.processed_documents
            }, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Výsledky uloženy do: {output_file}")

    def print_summary(self):
        """Vypsat souhrn zpracování"""
        if not self.processed_documents:
            print("Žádné dokumenty ke zobrazení")
            return

        total = len(self.processed_documents)
        successful = sum(1 for d in self.processed_documents if d.get('success'))
        failed = total - successful

        print("\n" + "═" * 80)
        print("📊 SOUHRN ZPRACOVÁNÍ MBW DOKUMENTŮ")
        print("═" * 80)
        print(f"  Celkem:            {total}")
        print(f"  Úspěšně:           {successful} ({successful/total*100:.1f}%)")
        print(f"  Chyby:             {failed}")
        print()

        # Statistiky dle typu
        type_counts = {}
        for doc in self.processed_documents:
            if doc.get('success'):
                doc_type = doc.get('document_type', 'unknown')
                type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

        print("📋 ROZPOZNANÉ TYPY DOKUMENTŮ:")
        for doc_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {doc_type:25s} {count:3d} ({count/successful*100:.1f}%)")

        print("═" * 80)


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='MAJ Document Recognition - MBW Processor')
    parser.add_argument('--source', '-s',
                       default='~/Dropbox/MBW',
                       help='Cesta ke složce MBW (default: ~/Dropbox/MBW)')
    parser.add_argument('--output', '-o',
                       default='data/mbw_processed.json',
                       help='Výstupní JSON soubor (default: data/mbw_processed.json)')
    parser.add_argument('--config', '-c',
                       default='config/config.yaml',
                       help='Cesta ke konfiguraci (default: config/config.yaml)')

    args = parser.parse_args()

    # Create processor
    processor = MBWDocumentProcessor(args.config)

    # Process all documents
    print("🚀 Zahajuji zpracování MBW dokumentů...")
    print(f"   Zdroj: {args.source}")
    print(f"   Výstup: {args.output}")
    print()

    results = processor.process_all(args.source)

    # Save results
    processor.save_results(args.output)

    # Print summary
    processor.print_summary()

    print("\n✅ Zpracování dokončeno!")
    print(f"\n📄 Výsledky: {args.output}")
    print("📝 Další krok: Použij interactive_selector.py pro výběr dokumentů")


if __name__ == "__main__":
    main()
