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
Enhanced Field Extractor for Czech Accounting Documents
Extracts: amounts, VAT, IČO, document numbers, dates, direction, category

Author: Claude Code
Date: 2025-12-17
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    """Document direction - income or expense"""
    PRIJEM = "příjem"
    VYDAJ = "výdaj"
    UNKNOWN = "neznámý"


class DocumentSubtype(Enum):
    """Detailed document subtype"""
    # Faktury
    FAKTURA_PRIJATA = "faktura_přijatá"
    FAKTURA_VYDANA = "faktura_vydaná"
    ZALOHA_PRIJATA = "záloha_přijatá"
    ZALOHA_VYDANA = "záloha_vydaná"
    DOBROPIS_PRIJATY = "dobropis_přijatý"
    DOBROPIS_VYDANY = "dobropis_vydaný"

    # Účtenky
    UCTENKA = "účtenka"
    UCTENKA_PHM = "účtenka_PHM"
    PARKOVNE = "parkovné"

    # Objednávky
    OBJEDNAVKA_PRIJATA = "objednávka_přijatá"
    OBJEDNAVKA_VYDANA = "objednávka_vydaná"

    # Bankovní
    BANKOVNI_VYPIS = "bankovní_výpis"
    PRIKAZ_K_UHRADE = "příkaz_k_úhradě"
    AVIZO = "avízo"

    # Ostatní
    SMLOUVA = "smlouva"
    UNKNOWN = "neznámý"


class Category(Enum):
    """Expense/income category for accounting"""
    PHM = "PHM"
    ENERGIE = "energie"
    TELEKOMUNIKACE = "telekomunikace"
    SLUZBY = "služby"
    MATERIAL = "materiál"
    KANCELAR = "kancelář"
    CESTOVNE = "cestovné"
    POJISTENI = "pojištění"
    DANE = "daně"
    MZDY = "mzdy"
    NAKUP_ZBOZI = "nákup_zboží"
    PRODEJ_ZBOZI = "prodej_zboží"
    SLUZBY_PRODEJ = "služby_prodej"
    OSTATNI = "ostatní"


@dataclass
class ExtractedAmount:
    """Structured amount with VAT breakdown"""
    celkem: Optional[float] = None
    zaklad: Optional[float] = None
    dph: Optional[float] = None
    sazba_dph: Optional[int] = None
    mena: str = "CZK"
    confidence: float = 0.0


@dataclass
class ExtractedDocument:
    """Complete extracted document data"""
    # Type classification
    doc_type: str = "unknown"
    doc_subtype: str = "unknown"
    direction: str = "unknown"

    # Amounts
    castka_celkem: Optional[float] = None
    castka_zaklad: Optional[float] = None
    castka_dph: Optional[float] = None
    sazba_dph: Optional[int] = None
    mena: str = "CZK"

    # Identifiers
    cislo_dokumentu: Optional[str] = None
    variabilni_symbol: Optional[str] = None
    konstantni_symbol: Optional[str] = None

    # Counterparty
    protistrana_nazev: Optional[str] = None
    protistrana_ico: Optional[str] = None
    protistrana_dic: Optional[str] = None

    # Dates
    datum_dokumentu: Optional[str] = None
    datum_splatnosti: Optional[str] = None
    datum_uhrady: Optional[str] = None

    # Status
    stav_platby: Optional[str] = None
    kategorie: Optional[str] = None

    # Metadata
    confidence: float = 0.0
    extraction_method: str = "regex"


class EnhancedFieldExtractor:
    """Enhanced extractor for Czech accounting documents"""

    # Regex patterns for Czech amounts
    AMOUNT_PATTERNS = [
        # "Celkem: 1 234,56 Kč" or "1234.56 CZK"
        r'(?:celkem|total|součet|k úhradě|částka)[:\s]*(\d[\d\s]*[,\.]\d{2})\s*(?:Kč|CZK|€|EUR)?',
        # "1 234,56 Kč" standalone
        r'(\d{1,3}(?:[\s\xa0]\d{3})*[,\.]\d{2})\s*(?:Kč|CZK)',
        # Simple: "1234.56"
        r'(\d+[,\.]\d{2})',
    ]

    # VAT patterns
    VAT_PATTERNS = [
        r'(?:DPH|daň)[:\s]*(\d[\d\s]*[,\.]\d{2})',
        r'(?:základ|base)[:\s]*(\d[\d\s]*[,\.]\d{2})',
        r'(\d{1,2})\s*%\s*(?:DPH|sazba)',
    ]

    # IČO pattern (8 digits)
    ICO_PATTERN = r'(?:IČO?|IČ)[:\s]*(\d{8})'

    # DIČ pattern (CZ + 8-10 digits)
    DIC_PATTERN = r'(?:DIČ)[:\s]*(CZ\d{8,10})'

    # Document number patterns
    DOC_NUMBER_PATTERNS = [
        r'(?:faktur[ay]|invoice)[:\s#]*(\d{6,15})',
        r'(?:číslo dokladu|č\.\s*d\.)[:\s]*(\d+)',
        r'(?:VS|var\.?\s*symbol)[:\s]*(\d{1,10})',
    ]

    # Date patterns (Czech format)
    DATE_PATTERNS = [
        r'(\d{1,2})\s*[\.\/]\s*(\d{1,2})\s*[\.\/]\s*(\d{4})',
        r'(\d{4})-(\d{2})-(\d{2})',
    ]

    # Direction indicators
    INCOME_INDICATORS = [
        'faktura vydaná', 'vydali jsme', 'náš doklad', 'odběratel',
        'prodej', 'příjem', 'tržba', 'výnos'
    ]

    EXPENSE_INDICATORS = [
        'faktura přijatá', 'obdrželi jsme', 'dodavatel', 'věřitel',
        'nákup', 'výdaj', 'náklad', 'platba za'
    ]

    # Category mapping based on keywords
    CATEGORY_KEYWORDS = {
        Category.PHM: ['benzín', 'nafta', 'phm', 'tankování', 'čerpací', 'shell', 'omv', 'mol', 'eni'],
        Category.ENERGIE: ['elektřina', 'plyn', 'čez', 'eon', 'innogy', 'energie', 'teplo'],
        Category.TELEKOMUNIKACE: ['telefon', 'mobil', 'internet', 'o2', 'vodafone', 't-mobile', 'upc'],
        Category.SLUZBY: ['služby', 'servis', 'údržba', 'oprava', 'konzultace', 'poradenství'],
        Category.MATERIAL: ['materiál', 'spotřební', 'kancelářské potřeby'],
        Category.KANCELAR: ['nájem', 'pronájem', 'kancelář', 'úklid'],
        Category.CESTOVNE: ['jízdenka', 'letenka', 'hotel', 'ubytování', 'cestovné', 'diety'],
        Category.POJISTENI: ['pojištění', 'pojistka', 'havarijní', 'odpovědnost'],
        Category.DANE: ['daň', 'finanční úřad', 'silniční daň', 'dph'],
        Category.MZDY: ['mzda', 'plat', 'odměna', 'sociální', 'zdravotní'],
    }

    def __init__(self):
        self.compiled_patterns = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance"""
        self.compiled_patterns['amounts'] = [re.compile(p, re.IGNORECASE) for p in self.AMOUNT_PATTERNS]
        self.compiled_patterns['vat'] = [re.compile(p, re.IGNORECASE) for p in self.VAT_PATTERNS]
        self.compiled_patterns['ico'] = re.compile(self.ICO_PATTERN, re.IGNORECASE)
        self.compiled_patterns['dic'] = re.compile(self.DIC_PATTERN, re.IGNORECASE)
        self.compiled_patterns['doc_number'] = [re.compile(p, re.IGNORECASE) for p in self.DOC_NUMBER_PATTERNS]
        self.compiled_patterns['date'] = [re.compile(p) for p in self.DATE_PATTERNS]

    def extract_all(self, text: str, doc_type: str = "unknown",
                    email_from: str = "", email_to: str = "") -> ExtractedDocument:
        """
        Extract all fields from document text

        Args:
            text: Document text (OCR or email body)
            doc_type: Pre-classified document type
            email_from: Sender email for direction detection
            email_to: Recipient email for direction detection

        Returns:
            ExtractedDocument with all extracted fields
        """
        result = ExtractedDocument(doc_type=doc_type)

        # Normalize text
        text_lower = text.lower()

        # Extract direction
        result.direction = self._extract_direction(text_lower, email_from, email_to)

        # Extract subtype based on doc_type and direction
        result.doc_subtype = self._extract_subtype(doc_type, result.direction, text_lower)

        # Extract amounts
        amounts = self._extract_amounts(text)
        result.castka_celkem = amounts.celkem
        result.castka_zaklad = amounts.zaklad
        result.castka_dph = amounts.dph
        result.sazba_dph = amounts.sazba_dph
        result.mena = amounts.mena

        # Extract identifiers
        result.cislo_dokumentu = self._extract_document_number(text)
        result.variabilni_symbol = self._extract_variable_symbol(text)

        # Extract counterparty
        result.protistrana_ico = self._extract_ico(text)
        result.protistrana_dic = self._extract_dic(text)

        # Extract dates
        dates = self._extract_dates(text)
        if dates:
            result.datum_dokumentu = dates[0]
            if len(dates) > 1:
                result.datum_splatnosti = dates[1]

        # Extract category
        result.kategorie = self._extract_category(text_lower)

        # Calculate confidence
        result.confidence = self._calculate_confidence(result)

        return result

    def _extract_direction(self, text: str, email_from: str = "", email_to: str = "") -> str:
        """Determine if document is income or expense"""

        # Check text for indicators
        income_score = sum(1 for ind in self.INCOME_INDICATORS if ind in text)
        expense_score = sum(1 for ind in self.EXPENSE_INDICATORS if ind in text)

        # Check email addresses for our domains
        our_domains = ['softel.cz', 'maj.cz', 'puzik.cz']

        if email_from:
            if any(domain in email_from.lower() for domain in our_domains):
                income_score += 2  # We sent it = likely invoice we issued
            else:
                expense_score += 1  # Someone sent to us = likely expense

        if income_score > expense_score:
            return Direction.PRIJEM.value
        elif expense_score > income_score:
            return Direction.VYDAJ.value
        else:
            return Direction.UNKNOWN.value

    def _extract_subtype(self, doc_type: str, direction: str, text: str) -> str:
        """Determine document subtype"""

        if doc_type in ['invoice', 'faktura']:
            if 'záloha' in text or 'zálohov' in text:
                return DocumentSubtype.ZALOHA_PRIJATA.value if direction == Direction.VYDAJ.value else DocumentSubtype.ZALOHA_VYDANA.value
            elif 'dobropis' in text:
                return DocumentSubtype.DOBROPIS_PRIJATY.value if direction == Direction.VYDAJ.value else DocumentSubtype.DOBROPIS_VYDANY.value
            else:
                return DocumentSubtype.FAKTURA_PRIJATA.value if direction == Direction.VYDAJ.value else DocumentSubtype.FAKTURA_VYDANA.value

        elif doc_type in ['receipt', 'účtenka']:
            if any(kw in text for kw in ['benzín', 'nafta', 'phm', 'tank']):
                return DocumentSubtype.UCTENKA_PHM.value
            elif 'parkov' in text:
                return DocumentSubtype.PARKOVNE.value
            return DocumentSubtype.UCTENKA.value

        elif doc_type in ['order', 'objednávka']:
            return DocumentSubtype.OBJEDNAVKA_PRIJATA.value if direction == Direction.VYDAJ.value else DocumentSubtype.OBJEDNAVKA_VYDANA.value

        elif doc_type in ['bank_statement', 'bankovní_výpis']:
            return DocumentSubtype.BANKOVNI_VYPIS.value

        elif doc_type in ['contract', 'smlouva']:
            return DocumentSubtype.SMLOUVA.value

        return DocumentSubtype.UNKNOWN.value

    def _extract_amounts(self, text: str) -> ExtractedAmount:
        """Extract amounts with VAT breakdown"""
        result = ExtractedAmount()

        # Find total amount
        for pattern in self.compiled_patterns['amounts']:
            match = pattern.search(text)
            if match:
                amount_str = match.group(1)
                result.celkem = self._parse_amount(amount_str)
                if result.celkem:
                    result.confidence = 0.8
                    break

        # Find VAT amount and rate
        vat_found = False
        base_found = False

        for pattern in self.compiled_patterns['vat']:
            for match in pattern.finditer(text):
                value = match.group(1)
                context = text[max(0, match.start()-20):match.end()+20].lower()

                if '%' in context or 'sazba' in context:
                    # This is VAT rate
                    try:
                        rate = int(value.strip())
                        if rate in [0, 10, 15, 21]:
                            result.sazba_dph = rate
                    except:
                        pass
                elif 'dph' in context or 'daň' in context:
                    # This is VAT amount
                    result.dph = self._parse_amount(value)
                    vat_found = True
                elif 'základ' in context or 'base' in context:
                    # This is base amount
                    result.zaklad = self._parse_amount(value)
                    base_found = True

        # Calculate missing values
        if result.celkem and result.dph and not result.zaklad:
            result.zaklad = round(result.celkem - result.dph, 2)
        elif result.celkem and result.zaklad and not result.dph:
            result.dph = round(result.celkem - result.zaklad, 2)
        elif result.zaklad and result.sazba_dph and not result.dph:
            result.dph = round(result.zaklad * result.sazba_dph / 100, 2)
            result.celkem = round(result.zaklad + result.dph, 2)

        # Detect currency
        if '€' in text or 'EUR' in text:
            result.mena = 'EUR'
        elif 'USD' in text or '$' in text:
            result.mena = 'USD'

        return result

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse Czech format amount to float"""
        try:
            # Remove spaces and convert comma to dot
            cleaned = amount_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
            return round(float(cleaned), 2)
        except:
            return None

    def _extract_ico(self, text: str) -> Optional[str]:
        """Extract IČO (8 digit company ID)"""
        match = self.compiled_patterns['ico'].search(text)
        if match:
            ico = match.group(1)
            # Validate - must be 8 digits
            if len(ico) == 8 and ico.isdigit():
                return ico
        return None

    def _extract_dic(self, text: str) -> Optional[str]:
        """Extract DIČ (VAT ID)"""
        match = self.compiled_patterns['dic'].search(text)
        if match:
            return match.group(1)
        return None

    def _extract_document_number(self, text: str) -> Optional[str]:
        """Extract document number"""
        for pattern in self.compiled_patterns['doc_number']:
            match = pattern.search(text)
            if match:
                doc_num = match.group(1)
                # Filter out too short or likely wrong matches
                if len(doc_num) >= 4:
                    return doc_num
        return None

    def _extract_variable_symbol(self, text: str) -> Optional[str]:
        """Extract variable symbol"""
        pattern = re.compile(r'(?:VS|var\.?\s*symbol)[:\s]*(\d{1,10})', re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group(1)
        return None

    def _extract_dates(self, text: str) -> List[str]:
        """Extract dates from text"""
        dates = []
        for pattern in self.compiled_patterns['date']:
            for match in pattern.finditer(text):
                groups = match.groups()
                if len(groups) == 3:
                    if len(groups[0]) == 4:
                        # YYYY-MM-DD format
                        date_str = f"{groups[0]}-{groups[1]}-{groups[2]}"
                    else:
                        # DD.MM.YYYY format
                        date_str = f"{groups[2]}-{groups[1].zfill(2)}-{groups[0].zfill(2)}"
                    dates.append(date_str)
        return dates[:2]  # Return max 2 dates

    def _extract_category(self, text: str) -> Optional[str]:
        """Extract expense/income category"""
        best_category = None
        best_score = 0

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_category = category.value

        return best_category if best_score > 0 else Category.OSTATNI.value

    def _calculate_confidence(self, result: ExtractedDocument) -> float:
        """Calculate extraction confidence score"""
        score = 0.0
        max_score = 10.0

        # Critical fields
        if result.castka_celkem:
            score += 3.0
        if result.cislo_dokumentu:
            score += 2.0
        if result.protistrana_ico:
            score += 2.0

        # Important fields
        if result.datum_dokumentu:
            score += 1.0
        if result.direction != Direction.UNKNOWN.value:
            score += 1.0
        if result.kategorie:
            score += 1.0

        return round(score / max_score, 2)

    def to_dict(self, result: ExtractedDocument) -> Dict[str, Any]:
        """Convert ExtractedDocument to dictionary"""
        return {
            'doc_type': result.doc_type,
            'doc_subtype': result.doc_subtype,
            'direction': result.direction,
            'castka_celkem': result.castka_celkem,
            'castka_zaklad': result.castka_zaklad,
            'castka_dph': result.castka_dph,
            'sazba_dph': result.sazba_dph,
            'mena': result.mena,
            'cislo_dokumentu': result.cislo_dokumentu,
            'variabilni_symbol': result.variabilni_symbol,
            'protistrana_ico': result.protistrana_ico,
            'protistrana_dic': result.protistrana_dic,
            'datum_dokumentu': result.datum_dokumentu,
            'datum_splatnosti': result.datum_splatnosti,
            'stav_platby': result.stav_platby,
            'kategorie': result.kategorie,
            'confidence': result.confidence,
        }


# Test
if __name__ == "__main__":
    extractor = EnhancedFieldExtractor()

    test_text = """
    FAKTURA č. 2595135367

    Dodavatel: Webglobe s.r.o.
    IČO: 25136071
    DIČ: CZ25136071

    Datum vystavení: 15.10.2025
    Datum splatnosti: 1.11.2025

    Základ DPH: 2 000,00 Kč
    DPH 21%: 420,00 Kč
    Celkem k úhradě: 2 420,00 Kč

    VS: 2595135367

    Služba: Webhosting premium
    """

    result = extractor.extract_all(
        text=test_text,
        doc_type="invoice",
        email_from="fakturace@webglobe.cz"
    )

    print("=" * 60)
    print("ENHANCED FIELD EXTRACTOR TEST")
    print("=" * 60)

    data = extractor.to_dict(result)
    for key, value in data.items():
        if value:
            print(f"  {key}: {value}")

    print(f"\nConfidence: {result.confidence * 100:.0f}%")
