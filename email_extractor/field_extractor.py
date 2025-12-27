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
Field Extractor - 31 Custom Fields
===================================
Extracts structured data from document text using regex patterns.

31 Custom Fields:
1.  doc_typ           - Typ dokumentu (faktura, smlouva, ...)
2.  protistrana_nazev - Název protistrany
3.  protistrana_ico   - IČO protistrany
4.  protistrana_typ   - Typ (firma, OSVČ, FO)
5.  castka_celkem     - Celková částka
6.  datum_dokumentu   - Datum dokumentu
7.  cislo_dokumentu   - Číslo dokumentu
8.  mena              - Měna (CZK, EUR, USD)
9.  stav_platby       - Stav (zaplaceno, nezaplaceno)
10. datum_splatnosti  - Datum splatnosti
11. kategorie         - Kategorie dokumentu
12. email_from        - Email odesílatele
13. email_to          - Email příjemce
14. email_subject     - Předmět emailu
15. od_osoba          - Jméno odesílatele
16. od_osoba_role     - Role odesílatele
17. od_firma          - Firma odesílatele
18. pro_osoba         - Jméno příjemce
19. pro_osoba_role    - Role příjemce
20. pro_firma         - Firma příjemce
21. predmet           - Předmět/účel
22. ai_summary        - AI souhrn
23. ai_keywords       - AI klíčová slova
24. ai_popis          - AI popis obsahu
25. typ_sluzby        - Typ služby
26. nazev_sluzby      - Název služby
27. predmet_typ       - Typ předmětu
28. predmet_nazev     - Název předmětu
29. polozky_text      - Položky (text)
30. polozky_json      - Položky (JSON)
31. perioda           - Období

Author: Claude Code
Date: 2025-12-15
"""

import re
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


# ============================================================================
# FIELD DEFINITIONS
# ============================================================================

FIELD_NAMES = [
    "doc_typ", "protistrana_nazev", "protistrana_ico", "protistrana_typ",
    "castka_celkem", "datum_dokumentu", "cislo_dokumentu", "mena",
    "stav_platby", "datum_splatnosti", "kategorie", "email_from",
    "email_to", "email_subject", "od_osoba", "od_osoba_role",
    "od_firma", "pro_osoba", "pro_osoba_role", "pro_firma",
    "predmet", "ai_summary", "ai_keywords", "ai_popis",
    "typ_sluzby", "nazev_sluzby", "predmet_typ", "predmet_nazev",
    "polozky_text", "polozky_json", "perioda"
]

# Document categories
DOC_CATEGORIES = {
    "invoice": "účetní",
    "contract": "právní",
    "bank_statement": "účetní",
    "order": "obchodní",
    "delivery_note": "logistika",
    "receipt": "účetní",
    "tax_document": "daňové",
    "correspondence": "korespondence",
    "marketing": "marketing",
    "other": "ostatní"
}

# Service types
SERVICE_TYPES = {
    "hosting": ["hosting", "server", "cloud", "aws", "azure"],
    "telekomunikace": ["telefon", "mobile", "tarif", "data", "internet", "wifi"],
    "software": ["licence", "software", "subscription", "saas"],
    "energie": ["elektřina", "plyn", "energie", "eon", "čez", "innogy"],
    "pojištění": ["pojištění", "insurance", "pojistka"],
    "účetnictví": ["účetní", "daňov", "audit"],
    "právní": ["advokát", "právní", "notář"],
    "doprava": ["doprava", "přeprava", "kurýr", "pošta"],
    "marketing": ["reklama", "marketing", "google ads", "facebook"],
}


# ============================================================================
# REGEX PATTERNS
# ============================================================================

class Patterns:
    """Regex patterns for field extraction"""

    # IČO (8 digits)
    ICO = re.compile(r'IČO?[:\s]*(\d{8})', re.IGNORECASE)

    # DIČ (CZ + 8-10 digits)
    DIC = re.compile(r'DIČ[:\s]*(CZ\d{8,10})', re.IGNORECASE)

    # Amount patterns
    AMOUNTS = [
        re.compile(r'celkem\s*(?:k\s*úhradě)?[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)?', re.IGNORECASE),
        re.compile(r'total\s*(?:amount)?[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)?', re.IGNORECASE),
        re.compile(r'k\s*úhradě[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)?', re.IGNORECASE),
        re.compile(r'částka[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)?', re.IGNORECASE),
        re.compile(r'suma[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)?', re.IGNORECASE),
        re.compile(r'cena[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)?', re.IGNORECASE),
    ]

    # Date patterns (DD.MM.YYYY or YYYY-MM-DD)
    DATE_DMY = re.compile(r'(\d{1,2})[./](\d{1,2})[./](\d{4})')
    DATE_YMD = re.compile(r'(\d{4})-(\d{2})-(\d{2})')

    # Due date specific
    DUE_DATE = re.compile(r'(?:splatnost|due\s*date|fällig)[:\s]*(\d{1,2})[./](\d{1,2})[./](\d{4})', re.IGNORECASE)

    # Document number
    DOC_NUMBERS = [
        re.compile(r'(?:faktura|invoice|doklad)\s*(?:č|číslo|nr?|number)?[.:\s#]*([A-Z0-9/-]+)', re.IGNORECASE),
        re.compile(r'(?:číslo\s*(?:faktury|dokladu))[:\s]*([A-Z0-9/-]+)', re.IGNORECASE),
        re.compile(r'(?:invoice|rechnung)\s*(?:no|nr)?[.:\s#]*([A-Z0-9/-]+)', re.IGNORECASE),
    ]

    # Variable symbol
    VS = re.compile(r'(?:VS|var(?:iabilní)?\s*symbol)[:\s]*(\d{4,10})', re.IGNORECASE)

    # IBAN
    IBAN = re.compile(r'([A-Z]{2}\d{2}[\sA-Z0-9]{10,30})', re.IGNORECASE)

    # Bank account CZ format
    BANK_ACCOUNT_CZ = re.compile(r'(\d{2,6}[-/]?\d{2,10})/(\d{4})')

    # Company patterns
    COMPANY_SUPPLIER = [
        re.compile(r'(?:dodavatel|supplier|verkäufer)[:\s]*([^\n]{3,60})', re.IGNORECASE),
        re.compile(r'(?:vystavil|issued\s*by)[:\s]*([^\n]{3,60})', re.IGNORECASE),
    ]

    COMPANY_CUSTOMER = [
        re.compile(r'(?:odběratel|customer|käufer)[:\s]*([^\n]{3,60})', re.IGNORECASE),
        re.compile(r'(?:příjemce|recipient)[:\s]*([^\n]{3,60})', re.IGNORECASE),
    ]

    # Person name (basic)
    PERSON = re.compile(r'(?:jméno|name|kontakt)[:\s]*([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+)', re.IGNORECASE)

    # Period patterns
    PERIOD = [
        re.compile(r'(?:období|period|za\s*měsíc)[:\s]*(\d{1,2})[./](\d{4})', re.IGNORECASE),
        re.compile(r'(?:období|period)[:\s]*(\d{4})', re.IGNORECASE),
        re.compile(r'(\d{1,2})/(\d{4})', re.IGNORECASE),
    ]

    # Items/lines (basic)
    ITEMS = re.compile(r'^\s*\d+[.)]\s*(.+?)\s+(\d+)\s*[xX×]?\s*([0-9,.]+)', re.MULTILINE)


# ============================================================================
# FIELD EXTRACTOR
# ============================================================================

class FieldExtractor:
    """Extract 31 custom fields from document text"""

    @classmethod
    def extract_all(cls, text: str, email_meta: Dict = None, doc_type: str = None) -> Dict[str, Any]:
        """
        Extract all 31 custom fields from text.

        Args:
            text: Document text content
            email_meta: Email metadata (from, to, subject, date)
            doc_type: Document type (if already classified)

        Returns:
            Dictionary with all 31 fields
        """
        if email_meta is None:
            email_meta = {}

        # Initialize all fields with None
        fields = {name: None for name in FIELD_NAMES}

        if not text:
            return fields

        text_lower = text.lower()

        # 1. doc_typ
        fields["doc_typ"] = doc_type

        # 2-4. Protistrana
        fields.update(cls._extract_counterparty(text))

        # 5. castka_celkem
        fields["castka_celkem"] = cls._extract_amount(text)

        # 6. datum_dokumentu
        fields["datum_dokumentu"] = cls._extract_date(text)

        # 7. cislo_dokumentu
        fields["cislo_dokumentu"] = cls._extract_doc_number(text)

        # 8. mena
        fields["mena"] = cls._extract_currency(text)

        # 9. stav_platby
        fields["stav_platby"] = cls._extract_payment_status(text_lower)

        # 10. datum_splatnosti
        fields["datum_splatnosti"] = cls._extract_due_date(text)

        # 11. kategorie
        fields["kategorie"] = DOC_CATEGORIES.get(doc_type, "ostatní")

        # 12-14. Email fields
        fields["email_from"] = email_meta.get("from", "")
        fields["email_to"] = email_meta.get("to", "")
        fields["email_subject"] = email_meta.get("subject", "")

        # 15-20. Osoba/Firma
        fields.update(cls._extract_persons(text, email_meta))

        # 21. predmet
        fields["predmet"] = email_meta.get("subject", "")[:200] if email_meta.get("subject") else None

        # 22-24. AI fields (basic extraction, will be enhanced by LLM in Phase 2)
        fields["ai_keywords"] = cls._extract_keywords(text_lower)
        fields["ai_summary"] = cls._extract_summary(text)

        # 25-26. Služba
        fields.update(cls._extract_service(text_lower))

        # 27-28. Předmět typ/název
        fields.update(cls._extract_subject_type(text, doc_type))

        # 29-30. Položky
        fields.update(cls._extract_items(text))

        # 31. perioda
        fields["perioda"] = cls._extract_period(text)

        return fields

    @classmethod
    def _extract_counterparty(cls, text: str) -> Dict[str, Any]:
        """Extract counterparty info (2-4)"""
        result = {
            "protistrana_nazev": None,
            "protistrana_ico": None,
            "protistrana_typ": None
        }

        # ICO
        ico_match = Patterns.ICO.search(text)
        if ico_match:
            result["protistrana_ico"] = ico_match.group(1)

        # Company name from supplier patterns
        for pattern in Patterns.COMPANY_SUPPLIER:
            match = pattern.search(text)
            if match:
                name = match.group(1).strip()
                # Clean up common suffixes
                name = re.sub(r'\s*(IČO?|DIČ|s\.r\.o\.|a\.s\.|spol\..*|, .*$)', '', name, flags=re.IGNORECASE)
                result["protistrana_nazev"] = name[:100]
                break

        # Determine type
        if result["protistrana_ico"]:
            text_lower = text.lower()
            if "s.r.o" in text_lower or "a.s." in text_lower or "spol." in text_lower:
                result["protistrana_typ"] = "firma"
            elif "osvč" in text_lower or "živnost" in text_lower:
                result["protistrana_typ"] = "OSVČ"
            else:
                result["protistrana_typ"] = "firma"

        return result

    @classmethod
    def _extract_amount(cls, text: str) -> Optional[float]:
        """Extract total amount (5)"""
        for pattern in Patterns.AMOUNTS:
            match = pattern.search(text)
            if match:
                amount_str = match.group(1)
                # Clean and convert
                amount_str = amount_str.replace(" ", "").replace(",", ".")
                # Remove thousands separator if present
                if amount_str.count(".") > 1:
                    parts = amount_str.rsplit(".", 1)
                    amount_str = parts[0].replace(".", "") + "." + parts[1]
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None

    @classmethod
    def _extract_date(cls, text: str) -> Optional[str]:
        """Extract document date (6) - returns YYYY-MM-DD"""
        # Try YMD first (ISO format)
        match = Patterns.DATE_YMD.search(text)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

        # Try DMY format
        match = Patterns.DATE_DMY.search(text)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        return None

    @classmethod
    def _extract_doc_number(cls, text: str) -> Optional[str]:
        """Extract document number (7)"""
        for pattern in Patterns.DOC_NUMBERS:
            match = pattern.search(text)
            if match:
                num = match.group(1).strip()
                if len(num) >= 3 and len(num) <= 30:
                    return num
        return None

    @classmethod
    def _extract_currency(cls, text: str) -> Optional[str]:
        """Extract currency (8)"""
        text_lower = text.lower()

        # Order matters - check more specific first
        if "czk" in text_lower or "kč" in text_lower:
            return "CZK"
        elif "eur" in text_lower or "€" in text:
            return "EUR"
        elif "usd" in text_lower or "$" in text:
            return "USD"
        elif "gbp" in text_lower or "£" in text:
            return "GBP"
        return None

    @classmethod
    def _extract_payment_status(cls, text_lower: str) -> Optional[str]:
        """Extract payment status (9)"""
        paid_patterns = ["zaplaceno", "paid", "bezahlt", "uhrazeno"]
        unpaid_patterns = ["nezaplaceno", "unpaid", "k úhradě", "splatno"]

        for pattern in paid_patterns:
            if pattern in text_lower:
                return "zaplaceno"

        for pattern in unpaid_patterns:
            if pattern in text_lower:
                return "nezaplaceno"

        return None

    @classmethod
    def _extract_due_date(cls, text: str) -> Optional[str]:
        """Extract due date (10) - returns YYYY-MM-DD"""
        match = Patterns.DUE_DATE.search(text)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        return None

    @classmethod
    def _extract_persons(cls, text: str, email_meta: Dict) -> Dict[str, Any]:
        """Extract person/company fields (15-20)"""
        result = {
            "od_osoba": None,
            "od_osoba_role": None,
            "od_firma": None,
            "pro_osoba": None,
            "pro_osoba_role": None,
            "pro_firma": None
        }

        # From header parsing
        from_header = email_meta.get("from", "")
        if "<" in from_header:
            name_part = from_header.split("<")[0].strip().strip('"').strip("'")
            if name_part:
                result["od_osoba"] = name_part

        # To header parsing
        to_header = email_meta.get("to", "")
        if "<" in to_header:
            name_part = to_header.split("<")[0].strip().strip('"').strip("'")
            if name_part:
                result["pro_osoba"] = name_part

        # Try to find company from text
        for pattern in Patterns.COMPANY_SUPPLIER:
            match = pattern.search(text)
            if match:
                result["od_firma"] = match.group(1).strip()[:100]
                break

        for pattern in Patterns.COMPANY_CUSTOMER:
            match = pattern.search(text)
            if match:
                result["pro_firma"] = match.group(1).strip()[:100]
                break

        return result

    @classmethod
    def _extract_keywords(cls, text_lower: str) -> Optional[str]:
        """Extract keywords (23)"""
        keywords = []

        keyword_patterns = [
            ("faktura", "faktur"),
            ("smlouva", "smlouv"),
            ("objednávka", "objednáv"),
            ("platba", "platb"),
            ("účet", "účet"),
            ("pojištění", "pojišt"),
            ("daň", "daň"),
            ("licence", "licenc"),
            ("služba", "služb"),
            ("zboží", "zboží"),
        ]

        for keyword, pattern in keyword_patterns:
            if pattern in text_lower:
                keywords.append(keyword)

        return ", ".join(keywords[:10]) if keywords else None

    @classmethod
    def _extract_summary(cls, text: str) -> Optional[str]:
        """Extract basic summary (22) - first meaningful sentence"""
        # Skip empty lines and headers
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 20]

        for line in lines[:5]:
            # Skip lines that look like headers or metadata
            if any(x in line.lower() for x in ['from:', 'to:', 'date:', 'subject:', '---']):
                continue
            # Return first meaningful line
            if len(line) > 30:
                return line[:200]

        return None

    @classmethod
    def _extract_service(cls, text_lower: str) -> Dict[str, Any]:
        """Extract service type and name (25-26)"""
        result = {
            "typ_sluzby": None,
            "nazev_sluzby": None
        }

        for service_type, patterns in SERVICE_TYPES.items():
            for pattern in patterns:
                if pattern in text_lower:
                    result["typ_sluzby"] = service_type
                    # Try to find service name
                    match = re.search(rf'{pattern}[:\s]*([^\n,]{{3,50}})', text_lower)
                    if match:
                        result["nazev_sluzby"] = match.group(1).strip()
                    return result

        return result

    @classmethod
    def _extract_subject_type(cls, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract subject type and name (27-28)"""
        result = {
            "predmet_typ": None,
            "predmet_nazev": None
        }

        if doc_type == "invoice":
            result["predmet_typ"] = "fakturace"
        elif doc_type == "contract":
            result["predmet_typ"] = "smlouva"
        elif doc_type == "order":
            result["predmet_typ"] = "objednávka"

        # Try to find subject description
        patterns = [
            re.compile(r'(?:předmět|věc|re)[:\s]*([^\n]{10,100})', re.IGNORECASE),
            re.compile(r'(?:subject|betreff)[:\s]*([^\n]{10,100})', re.IGNORECASE),
        ]

        for pattern in patterns:
            match = pattern.search(text)
            if match:
                result["predmet_nazev"] = match.group(1).strip()[:100]
                break

        return result

    @classmethod
    def _extract_items(cls, text: str) -> Dict[str, Any]:
        """Extract line items (29-30)"""
        result = {
            "polozky_text": None,
            "polozky_json": None
        }

        items = []
        for match in Patterns.ITEMS.finditer(text):
            description, qty, price = match.groups()
            items.append({
                "popis": description.strip()[:100],
                "mnozstvi": int(qty) if qty.isdigit() else qty,
                "cena": price.replace(",", ".")
            })

        if items:
            result["polozky_text"] = "; ".join([f"{i['popis']} ({i['mnozstvi']}x {i['cena']})" for i in items[:10]])
            result["polozky_json"] = json.dumps(items[:20], ensure_ascii=False)

        return result

    @classmethod
    def _extract_period(cls, text: str) -> Optional[str]:
        """Extract period (31)"""
        for pattern in Patterns.PERIOD:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return f"{groups[0]}/{groups[1]}"
                elif len(groups) == 1:
                    return groups[0]
        return None


# ============================================================================
# CLI
# ============================================================================

def main():
    """Test field extraction"""
    import argparse

    parser = argparse.ArgumentParser(description='Field Extractor Test')
    parser.add_argument('--file', type=str, help='Text file to extract from')
    parser.add_argument('--text', type=str, help='Direct text input')

    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        # Test with sample text
        text = """
        FAKTURA č. 2024001234
        Datum vystavení: 15.12.2024
        Datum splatnosti: 29.12.2024

        Dodavatel:
        ABC Software s.r.o.
        IČO: 12345678
        DIČ: CZ12345678

        Odběratel:
        XYZ Company a.s.

        Položky:
        1. Licence software      12x   1,500.00 CZK
        2. Technická podpora      1x  5,000.00 CZK

        Celkem k úhradě: 23,000.00 CZK
        VS: 2024001234
        """

    email_meta = {
        "from": "Jan Novák <jan@abc.cz>",
        "to": "info@xyz.com",
        "subject": "Faktura za software licence"
    }

    fields = FieldExtractor.extract_all(text, email_meta, "invoice")

    print("\n" + "=" * 60)
    print("EXTRACTED FIELDS")
    print("=" * 60)

    for name, value in fields.items():
        if value is not None:
            print(f"{name:25s}: {value}")

    print("=" * 60)


if __name__ == "__main__":
    main()
