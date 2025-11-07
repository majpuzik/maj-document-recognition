#!/usr/bin/env python3
"""
Bank Statement Processor for Czech Banks v2.2
Supports analysis, tagging, PDF conversion, and Paperless-NGX integration

Version History:
- v1.0: Initial version with CAMT.053 support
- v2.0: Added FINSTA format support (ČSOB, MONETA Money Bank)
- v2.1: Added XML→PDF conversion for FINSTA statements
- v2.2: Restructured output to PAPERLESS_INTEGRATION_STANDARD format

Author: Claude Code + MCP Server
Date: 2025-11-02
"""
import re
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import xml.etree.ElementTree as ET

__version__ = "2.2"

class BankStatementProcessor:
    """
    Processor pro rozpoznání, analýzu a konverzi bankovních výpisů

    Podporované formáty:
    - FINSTA (Czech banks: ČSOB, MONETA Money Bank)
    - CAMT.053 (ISO 20022 standard)
    - Text-based statements (PDF with OCR)

    Features:
    - Analýza a klasifikace dokumentů
    - Automatické taggování pro Paperless-NGX
    - Konverze FINSTA XML → formátované PDF

    Usage:
        # Analýza
        processor = BankStatementProcessor()
        result = processor.analyze_statement("statement.xml")
        print(result)  # {'type': 'bank_statement', 'bank': 'ČSOB', ...}

        # Konverze XML → PDF
        pdf_path = processor.convert_to_pdf("statement.xml", "output.pdf")
    """

    # Známé české banky a jejich identifikátory
    CZECH_BANKS = {
        'Česká spořitelna': ['csas', 'ceska sporitelna', 'sporitelna', '0800'],
        'Komerční banka': ['kb', 'komercni banka', '0100'],
        'ČSOB': ['csob', 'československá obchodní banka', '0300'],
        'UniCredit Bank': ['unicredit', 'unicreditbank', '2700'],
        'Raiffeisenbank': ['raiffeisen', 'raiffeisenbank', 'rb', '5500'],
        'mBank': ['mbank', '6210'],
        'Air Bank': ['airbank', 'air bank', '3030'],
        'Fio banka': ['fio', 'fio banka', '2010'],
        'Equa bank': ['equa', 'equa bank', '6100'],
        'MONETA Money Bank': ['moneta', 'ge money bank', '0600'],
    }

    def __init__(self):
        pass

    def _build_paperless_output(self, old_format: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        """
        Konvertuje starý formát výstupu na standardizovaný PAPERLESS_INTEGRATION_STANDARD

        Args:
            old_format: Starý formát výstupu {'type', 'bank', 'account', 'confidence', 'tags', ...}
            file_path: Cesta k souboru (optional)

        Returns:
            Standardizovaný výstup podle PAPERLESS_INTEGRATION_STANDARD
        """
        # Extract data from tags for custom fields
        statement_number = None
        statement_period = None
        company_name = None

        for tag in old_format.get('tags', []):
            if tag.startswith('výpis-č-'):
                statement_number = tag.replace('výpis-č-', '')
            elif tag.startswith('období-'):
                statement_period = tag.replace('období-', '')
            elif tag.startswith('firma-'):
                company_name = tag.replace('firma-', '').replace('-', ' ').title()

        # Build custom fields
        custom_fields = {}
        if old_format.get('account'):
            custom_fields['bank_account'] = old_format['account']
        if statement_number:
            custom_fields['statement_number'] = statement_number
        if statement_period:
            custom_fields['statement_period'] = statement_period
        # Default currency for Czech banks
        custom_fields['currency'] = 'CZK'

        # Document type name
        doc_type_name = "Bankovní výpis"

        # Standardizovaný výstup
        result = {
            'document_type': old_format.get('type', 'unknown'),
            'confidence': old_format.get('confidence', 0),
            'country': 'CZ',
            'version': __version__,

            'paperless': {
                'tags': old_format.get('tags', []),
                'custom_fields': custom_fields,
                'document_type_name': doc_type_name
            },

            'metadata': {
                'bank': old_format.get('bank'),
                'account': old_format.get('account'),
                'format': None,  # Will be determined from tags
                'company': company_name
            }
        }

        # Determine format from tags
        if 'finsta' in old_format.get('tags', []):
            result['metadata']['format'] = 'finsta'
        elif 'camt-053' in old_format.get('tags', []):
            result['metadata']['format'] = 'camt-053'

        # Optional fields
        if old_format.get('bank'):
            result['paperless']['correspondent'] = old_format['bank']

        # Try to extract date from period
        if statement_period:
            # Parse period like "2024-01-01-2024-01-31" and use end date
            parts = statement_period.split('-')
            if len(parts) >= 6:
                try:
                    result['paperless']['date'] = f"{parts[3]}-{parts[4]}-{parts[5]}"
                except:
                    pass

        # Include file_path in metadata if provided
        if file_path:
            result['metadata']['file_path'] = file_path

        # Preserve error if present
        if old_format.get('error'):
            result['error'] = old_format['error']

        return result

    def analyze_statement(self, file_path: str) -> Dict[str, Any]:
        """
        Analyzuje bankovní výpis a vrací standardizovaný výstup pro Paperless-NGX

        Args:
            file_path: Cesta k souboru bankovního výpisu (XML nebo text)

        Returns:
            Dict podle PAPERLESS_INTEGRATION_STANDARD:
                - document_type: 'bank_statement' or 'unknown'
                - confidence: Skóre spolehlivosti 0-100
                - country: 'CZ'
                - version: Version string
                - paperless: {...} sekce s tagy a custom fields
                - metadata: {...} sekce s raw daty
        """
        old_result = {
            'type': 'unknown',
            'bank': None,
            'account': None,
            'confidence': 0,
            'tags': [],
            'version': __version__
        }

        try:
            # Check if file is XML
            if file_path.lower().endswith('.xml'):
                old_result = self._analyze_xml_statement(file_path)
            else:
                old_result = self._analyze_text_statement(file_path)

        except Exception as e:
            old_result['error'] = str(e)

        # Convert to standardized format
        return self._build_paperless_output(old_result, file_path)

    def convert_to_pdf(self, xml_path: str, pdf_path: Optional[str] = None) -> str:
        """
        Konvertuje FINSTA XML na formátované PDF

        Args:
            xml_path: Cesta k XML souboru
            pdf_path: Cesta k výstupnímu PDF (optional, default: same as XML)

        Returns:
            Path to created PDF file

        Raises:
            ImportError: If reportlab is not installed
            ValueError: If XML is not FINSTA format
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError:
            raise ImportError(
                "reportlab is required for PDF conversion. "
                "Install with: pip install reportlab"
            )

        # Parse XML
        statement = self._parse_finsta_xml(xml_path)

        # Default PDF path
        if pdf_path is None:
            pdf_path = xml_path.replace('.xml', '.pdf')

        # Create PDF
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()

        # Nadpis
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#003366'),
            spaceAfter=30,
        )

        story.append(Paragraph(f"Bankovní výpis č. {statement['cislo_vypisu']}", title_style))
        story.append(Spacer(1, 12))

        # Základní informace
        info_data = [
            ['Název:', statement['nazev_firmy']],
            ['Číslo účtu:', statement['cislo_uctu']],
            ['Období:', f"{statement['datum_od']} - {statement['datum_do']}"],
            ['Měna:', statement['mena']],
            ['', ''],
            ['Počáteční zůstatek:', f"{statement['pocatecni_zustatek']} {statement['mena']}"],
            ['Konečný zůstatek:', f"{statement['konecny_zustatek']} {statement['mena']}"],
            ['Suma příjmů:', f"{statement['suma_kredit']}"],
            ['Suma výdajů:', f"{statement['suma_debit']}"],
        ]

        info_table = Table(info_data, colWidths=[150, 350])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))

        story.append(info_table)
        story.append(Spacer(1, 20))

        # Transakce
        story.append(Paragraph("Transakce", styles['Heading2']))
        story.append(Spacer(1, 12))

        trans_data = [['Datum', 'Částka', 'Typ', 'VS', 'Popis']]

        for trans in statement['transactions']:
            trans_data.append([
                trans['datum'],
                trans['castka'],
                trans['typ'],
                trans['vs'] or '-',
                trans['popis'][:40] + '...' if len(trans['popis']) > 40 else trans['popis']
            ])

        trans_table = Table(trans_data, colWidths=[60, 70, 30, 70, 270])
        trans_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ]))

        story.append(trans_table)

        # Generování PDF
        doc.build(story)
        return pdf_path

    def _parse_finsta_xml(self, xml_file: str) -> Dict[str, Any]:
        """Parse FINSTA XML souboru"""
        tree = ET.parse(xml_file)
        root = tree.getroot()

        if root.tag != 'FINSTA' and root.find('.//FINSTA03') is None:
            raise ValueError("Not a FINSTA XML file")

        # Základní informace
        statement = {
            'cislo_vypisu': root.find('.//S28_CISLO_VYPISU').text if root.find('.//S28_CISLO_VYPISU') is not None else 'N/A',
            'cislo_uctu': root.find('.//S25_CISLO_UCTU').text if root.find('.//S25_CISLO_UCTU') is not None else 'N/A',
            'nazev_firmy': root.find('.//SHORTNAME').text if root.find('.//SHORTNAME') is not None else 'N/A',
            'datum_od': root.find('.//S60_DATUM').text if root.find('.//S60_DATUM') is not None else 'N/A',
            'datum_do': root.find('.//S62_DATUM').text if root.find('.//S62_DATUM') is not None else 'N/A',
            'mena': root.find('.//S60_MENA').text if root.find('.//S60_MENA') is not None else 'CZK',
            'pocatecni_zustatek': root.find('.//S60_CASTKA').text if root.find('.//S60_CASTKA') is not None else '0',
            'konecny_zustatek': root.find('.//S62_CASTKA').text if root.find('.//S62_CASTKA') is not None else '0',
            'suma_kredit': root.find('.//SUMA_KREDIT').text if root.find('.//SUMA_KREDIT') is not None else '0',
            'suma_debit': root.find('.//SUMA_DEBIT').text if root.find('.//SUMA_DEBIT') is not None else '0',
            'transactions': []
        }

        # Transakce
        for trans in root.findall('.//FINSTA05'):
            transaction = {
                'datum': trans.find('S61_DATUM').text if trans.find('S61_DATUM') is not None else '',
                'castka': trans.find('S61_CASTKA').text if trans.find('S61_CASTKA') is not None else '0',
                'typ': trans.find('S61_CD_INDIK').text if trans.find('S61_CD_INDIK') is not None else '',
                'popis': trans.find('S61_POST_NAR').text if trans.find('S61_POST_NAR') is not None else '',
                'vs': trans.find('S86_VARSYMOUR').text if trans.find('S86_VARSYMOUR') is not None else '',
                'ks': trans.find('S86_KONSTSYM').text if trans.find('S86_KONSTSYM') is not None else '',
                'ss': trans.find('S86_SPECSYMOUR').text if trans.find('S86_SPECSYMOUR') is not None else '',
            }
            statement['transactions'].append(transaction)

        return statement

    def _analyze_xml_statement(self, file_path: str) -> Dict[str, Any]:
        """
        Analyzuje XML bankovní výpis

        Podporuje:
        - FINSTA format (ČSOB, MONETA)
        - CAMT.053 (ISO 20022)
        - Další XML formáty (GPC, ABO)
        """
        result = {
            'type': 'unknown',
            'bank': None,
            'account': None,
            'confidence': 0,
            'tags': [],
            'version': __version__
        }

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # ========================================
            # FINSTA format (Czech banks - ČSOB, MONETA)
            # ========================================
            if root.tag == 'FINSTA' or root.find('.//FINSTA03') is not None:
                result['type'] = 'bank_statement'
                result['confidence'] = 95
                result['tags'].append('bankovní-výpis')
                result['tags'].append('xml')
                result['tags'].append('finsta')

                # Extract account number (S25_CISLO_UCTU)
                account_elem = root.find('.//S25_CISLO_UCTU')
                if account_elem is not None and account_elem.text:
                    result['account'] = account_elem.text
                    result['tags'].append('účet-nalezen')

                    # Identify bank by account code (last 4 digits after /)
                    for bank_name, identifiers in self.CZECH_BANKS.items():
                        for identifier in identifiers:
                            if f'/{identifier}' in account_elem.text:
                                result['bank'] = bank_name
                                result['tags'].append(f'banka-{bank_name.lower().replace(" ", "-")}')
                                break
                        if result['bank']:
                            break

                # Extract company name (SHORTNAME)
                shortname_elem = root.find('.//SHORTNAME')
                if shortname_elem is not None and shortname_elem.text:
                    company = shortname_elem.text.lower().replace(" ", "-").replace(".", "")
                    result['tags'].append(f'firma-{company}')

                # Extract statement number (S28_CISLO_VYPISU)
                statement_elem = root.find('.//S28_CISLO_VYPISU')
                if statement_elem is not None and statement_elem.text:
                    result['tags'].append(f'výpis-č-{statement_elem.text}')

                # Extract date period (S60_DATUM to S62_DATUM)
                date_from = root.find('.//S60_DATUM')
                date_to = root.find('.//S62_DATUM')
                if date_from is not None and date_to is not None:
                    result['tags'].append(f'období-{date_from.text}-{date_to.text}')

                return result

            # ========================================
            # CAMT.053 format (ISO 20022)
            # ========================================
            if any(ns in root.tag for ns in ['camt', 'Document', 'BkToCstmrStmt']):
                result['type'] = 'bank_statement'
                result['confidence'] = 90
                result['tags'].append('bankovní-výpis')
                result['tags'].append('xml')
                result['tags'].append('camt-053')

                # Try to extract bank name and account
                for elem in root.iter():
                    if 'FinInstnId' in elem.tag or 'Nm' in elem.tag:
                        if elem.text:
                            bank = self._identify_bank(elem.text)
                            if bank:
                                result['bank'] = bank
                                result['tags'].append(f'banka-{bank.lower().replace(" ", "-")}')

                    if 'IBAN' in elem.tag or 'Acct' in elem.tag:
                        if elem.text and len(elem.text) > 10:
                            result['account'] = elem.text
                            result['tags'].append('iban')

                return result

            # ========================================
            # Další XML formáty (GPC, ABO, etc.)
            # ========================================
            xml_content = ET.tostring(root, encoding='unicode').lower()
            if any(keyword in xml_content for keyword in ['statement', 'account', 'transaction', 'balance']):
                result['type'] = 'bank_statement'
                result['confidence'] = 70
                result['tags'].append('bankovní-výpis')
                result['tags'].append('xml')
                return result

        except ET.ParseError:
            pass  # Not valid XML or corrupted
        except Exception as e:
            result['error'] = str(e)

        return result

    def _analyze_text_statement(self, file_path: str) -> Dict[str, Any]:
        """
        Analyzuje textový bankovní výpis (PDF po OCR)

        Používá probabilistické skóre na základě klíčových slov
        """
        result = {
            'type': 'unknown',
            'bank': None,
            'account': None,
            'confidence': 0,
            'tags': [],
            'version': __version__
        }

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            content_lower = content.lower()
            score = 0

            # Keywords pro bankovní výpis
            if 'výpis' in content_lower or 'vypis' in content_lower:
                score += 20
            if 'bank statement' in content_lower or 'account statement' in content_lower:
                score += 20
            if 'zůstatek' in content_lower or 'balance' in content_lower:
                score += 15
            if 'transakce' in content_lower or 'transaction' in content_lower:
                score += 15
            if 'účet' in content_lower or 'account' in content_lower:
                score += 10
            if 'datum' in content_lower and ('částka' in content_lower or 'amount' in content_lower):
                score += 15

            # Hledej číslo účtu (formát: XXXXXX-XXXXXXXXXX/XXXX nebo IBAN)
            account_pattern = r'(\d{2,6}[-/]\d{2,10}[/]\d{4}|[A-Z]{2}\d{2}[A-Z0-9]{1,30})'
            account_match = re.search(account_pattern, content)
            if account_match:
                result['account'] = account_match.group(1)
                result['tags'].append('účet-nalezen')
                score += 15

            # Identifikuj banku
            bank = self._identify_bank(content)
            if bank:
                result['bank'] = bank
                result['tags'].append(f'banka-{bank.lower().replace(" ", "-")}')
                score += 20

            if score >= 50:
                result['type'] = 'bank_statement'
                result['confidence'] = min(score, 100)
                result['tags'].append('bankovní-výpis')
                result['tags'].append('text')

            return result

        except Exception as e:
            result['error'] = str(e)
            return result

    def _identify_bank(self, text: str) -> Optional[str]:
        """
        Identifikuje banku podle textu

        Hledá známé identifikátory bank v textu
        """
        text_lower = text.lower()

        for bank_name, identifiers in self.CZECH_BANKS.items():
            for identifier in identifiers:
                if identifier in text_lower:
                    return bank_name

        return None


def main():
    """CLI interface pro testování"""
    import argparse

    parser = argparse.ArgumentParser(
        description=f'Bank Statement Processor v{__version__}',
        epilog='Example: python bank_statement_processor.py statement.xml --json'
    )
    parser.add_argument('file', help='File to analyze')
    parser.add_argument('--json', action='store_true', help='Output as JSON (default)')
    parser.add_argument('--convert-to-pdf', action='store_true', help='Convert FINSTA XML to PDF')
    parser.add_argument('--output', '-o', help='Output PDF path (for --convert-to-pdf)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    args = parser.parse_args()

    processor = BankStatementProcessor()

    if args.convert_to_pdf:
        # PDF conversion mode
        try:
            output_path = processor.convert_to_pdf(args.file, args.output)
            print(f"✓ PDF vytvořeno: {output_path}")
        except Exception as e:
            print(f"❌ Chyba při konverzi: {str(e)}")
            import traceback
            traceback.print_exc()
            exit(1)
    else:
        # Analysis mode
        result = processor.analyze_statement(args.file)

        if args.json or True:  # Always JSON for MCP server
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Typ: {result['type']}")
            print(f"Banka: {result['bank'] or 'neznámá'}")
            print(f"Účet: {result['account'] or 'nenalezen'}")
            print(f"Confidence: {result['confidence']}%")
            print(f"Tagy: {', '.join(result['tags'])}")


if __name__ == '__main__':
    main()
