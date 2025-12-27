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
Smart Bank Statement Handler
Automatická identifikace a zpracování bankovních výpisů (XML, PDF, Excel)
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.ocr.bank_statement_processor import BankStatementProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SmartBankStatementHandler:
    """
    Inteligentní handler pro bankovní výpisy

    Funkce:
    1. IDENTIFIKACE - Rozpozná bankovní výpisy (XML, PDF, Excel)
    2. ANALÝZA - Zjistí banku, typ, confidence
    3. KONVERZE - XML/Excel → PDF pro Paperless
    4. ULOŽENÍ - Do databáze s metadaty
    """

    def __init__(self):
        self.bank_processor = BankStatementProcessor()

        # Známé XML formáty bankovních výpisů
        self.xml_bank_formats = {
            'FINSTA': ['FINSTA', 'FINSTA03', 'FINSTA05'],  # ČSOB, MONETA
            'CAMT.053': ['Document', 'BkToCstmrStmt', 'camt.053'],  # ISO 20022
            'MT940': ['MT940', 'SwiftMessage'],  # SWIFT MT940
            'ABO': ['FINSTA', 'GPC'],  # Multi-Cash format
        }

        # Dropbox placeholder detection
        self.placeholder_attrs = ['com.dropbox.placeholder', 'com.dropbox.attrs']

    def is_dropbox_placeholder(self, file_path: Path) -> bool:
        """
        Zkontroluje, jestli je soubor Dropbox placeholder (nestažený)

        Returns:
            True pokud je placeholder (není fyzicky stažený)
        """
        try:
            # Check file size
            if file_path.stat().st_size == 0:
                # Check extended attributes
                import subprocess
                result = subprocess.run(
                    ['xattr', '-l', str(file_path)],
                    capture_output=True,
                    text=True
                )

                for attr in self.placeholder_attrs:
                    if attr in result.stdout:
                        return True
            return False
        except Exception as e:
            logger.warning(f"Nelze zkontrolovat placeholder: {e}")
            return False

    def identify_xml_bank_statement(self, xml_path: Path) -> Tuple[bool, Dict]:
        """
        IDENTIFIKACE: Zjistí, jestli je XML soubor bankovní výpis

        Args:
            xml_path: Cesta k XML souboru

        Returns:
            (is_bank_statement, details)
            details: {'format': 'FINSTA', 'confidence': 95, 'bank': 'ČSOB', ...}
        """
        result = {
            'is_bank_statement': False,
            'format': None,
            'confidence': 0,
            'bank': None,
            'account': None,
            'reason': None
        }

        # Check if placeholder
        if self.is_dropbox_placeholder(xml_path):
            result['reason'] = 'dropbox_placeholder'
            logger.warning(f"⚠️  {xml_path.name} je Dropbox placeholder - není stažený!")
            return False, result

        try:
            # Try to parse XML
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Get XML structure as string for pattern matching
            xml_str = ET.tostring(root, encoding='unicode')[:5000].lower()

            # Check for known bank statement formats
            for format_name, patterns in self.xml_bank_formats.items():
                for pattern in patterns:
                    if pattern.lower() in xml_str:
                        result['is_bank_statement'] = True
                        result['format'] = format_name
                        result['confidence'] = 95

                        logger.info(f"✅ XML bankovní výpis rozpoznán: {format_name}")

                        # Try to get more details
                        if format_name == 'FINSTA':
                            # Extract ČSOB/MONETA specific fields
                            account_elem = root.find('.//S25_CISLO_UCTU')
                            if account_elem is not None:
                                result['account'] = account_elem.text

                                # Identify bank by account code
                                if '/0300' in account_elem.text:
                                    result['bank'] = 'ČSOB'
                                elif '/0600' in account_elem.text:
                                    result['bank'] = 'MONETA Money Bank'

                        return True, result

            # Not recognized
            result['reason'] = 'unknown_xml_format'
            logger.info(f"ℹ️  {xml_path.name} je XML, ale nerozpoznaný formát")
            return False, result

        except ET.ParseError:
            result['reason'] = 'invalid_xml'
            logger.warning(f"⚠️  {xml_path.name} není validní XML")
            return False, result
        except Exception as e:
            result['reason'] = f'error: {str(e)}'
            logger.error(f"❌ Chyba při analýze {xml_path.name}: {e}")
            return False, result

    def process_bank_statement_xml(self, xml_path: Path, output_dir: Optional[Path] = None) -> Optional[Dict]:
        """
        Zpracuje bankovní výpis XML

        1. Identifikuje formát
        2. Analyzuje obsah (bank_statement_processor)
        3. Konvertuje na PDF
        4. Vrátí metadata pro databázi

        Args:
            xml_path: Cesta k XML souboru
            output_dir: Složka pro výstupní PDF (optional)

        Returns:
            Dict s metadaty pro databázi nebo None
        """
        logger.info(f"\n📊 Zpracovávám XML: {xml_path.name}")

        # 1. IDENTIFIKACE
        is_bank, details = self.identify_xml_bank_statement(xml_path)

        if not is_bank:
            logger.info(f"   ⏭️  Přeskakuji - není bankovní výpis ({details.get('reason')})")
            return None

        logger.info(f"   ✅ Identifikováno: {details['format']} (confidence: {details['confidence']}%)")

        # 2. ANALÝZA pomocí bank_statement_processor
        try:
            analysis = self.bank_processor.analyze_statement(str(xml_path))

            logger.info(f"   📋 Banka: {analysis['metadata']['bank']}")
            logger.info(f"   💳 Účet: {analysis['metadata']['account']}")

            # 3. KONVERZE XML → PDF
            if output_dir is None:
                output_dir = xml_path.parent

            pdf_filename = xml_path.stem + '_converted.pdf'
            pdf_path = output_dir / pdf_filename

            try:
                converted_pdf = self.bank_processor.convert_to_pdf(
                    str(xml_path),
                    str(pdf_path)
                )
                logger.info(f"   ✅ PDF vytvořeno: {pdf_path.name}")

                # Add PDF path to metadata
                analysis['converted_pdf'] = str(pdf_path)

            except ImportError as e:
                logger.warning(f"   ⚠️  Nelze vytvořit PDF (chybí reportlab): {e}")
                analysis['converted_pdf'] = None
            except Exception as e:
                logger.warning(f"   ⚠️  Chyba při konverzi PDF: {e}")
                analysis['converted_pdf'] = None

            # 4. PŘIPRAVIT METADATA PRO DATABÁZI
            db_metadata = {
                'source_file': str(xml_path),
                'document_type': analysis['document_type'],
                'confidence': analysis['confidence'],
                'bank': analysis['metadata']['bank'],
                'account': analysis['metadata']['account'],
                'format': analysis['metadata']['format'],
                'tags': analysis['paperless']['tags'],
                'custom_fields': analysis['paperless']['custom_fields'],
                'converted_pdf': analysis.get('converted_pdf'),
                'version': analysis['version']
            }

            return db_metadata

        except Exception as e:
            logger.error(f"   ❌ Chyba při zpracování: {e}")
            import traceback
            traceback.print_exc()
            return None

    def scan_and_process_directory(self, directory: Path) -> List[Dict]:
        """
        Naskenuje složku a zpracuje všechny XML bankovní výpisy

        Args:
            directory: Složka k prohledání

        Returns:
            Seznam zpracovaných výpisů s metadaty
        """
        logger.info(f"\n🔍 Skenuji složku: {directory}")

        # Find all XML files
        xml_files = list(directory.rglob('*.xml')) + list(directory.rglob('*.XML'))
        logger.info(f"   Nalezeno {len(xml_files)} XML souborů")

        processed = []
        placeholders = []
        skipped = []

        for xml_file in xml_files:
            # Check if placeholder
            if self.is_dropbox_placeholder(xml_file):
                placeholders.append(xml_file)
                continue

            # Process
            result = self.process_bank_statement_xml(xml_file)

            if result:
                processed.append(result)
            else:
                skipped.append(xml_file)

        # Summary
        logger.info(f"\n📊 SOUHRN:")
        logger.info(f"   ✅ Zpracováno: {len(processed)}")
        logger.info(f"   ⏭️  Přeskočeno: {len(skipped)}")
        logger.info(f"   ☁️  Dropbox placeholders: {len(placeholders)}")

        if placeholders:
            logger.warning(f"\n⚠️  VAROVÁNÍ: {len(placeholders)} souborů je Dropbox placeholder!")
            logger.warning("   Tyto soubory nejsou fyzicky stažené z cloudu.")
            logger.warning("   Řešení: Klikni pravým tlačítkem → 'Make available offline'")
            for p in placeholders[:5]:
                logger.warning(f"   - {p}")

        return processed


def main():
    """Test handler"""
    import argparse

    parser = argparse.ArgumentParser(description='Smart Bank Statement Handler')
    parser.add_argument('--scan', help='Složka k prohledání')
    parser.add_argument('--identify', help='XML soubor k identifikaci')
    parser.add_argument('--process', help='XML soubor ke zpracování')

    args = parser.parse_args()

    handler = SmartBankStatementHandler()

    if args.identify:
        is_bank, details = handler.identify_xml_bank_statement(Path(args.identify))
        print(f"\n✅ Je bankovní výpis: {is_bank}")
        print(f"📋 Detaily:")
        for key, value in details.items():
            print(f"   {key}: {value}")

    elif args.process:
        result = handler.process_bank_statement_xml(Path(args.process))
        if result:
            print(f"\n✅ Zpracováno úspěšně:")
            import json
            print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.scan:
        results = handler.scan_and_process_directory(Path(args.scan))
        print(f"\n✅ Zpracováno {len(results)} výpisů")


if __name__ == '__main__':
    main()
