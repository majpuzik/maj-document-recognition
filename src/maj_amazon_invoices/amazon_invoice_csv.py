#!/usr/bin/env python3
"""
Amazon Business Invoice CSV Parser
===================================
Parses Amazon Business order export CSV files in multiple languages.
Extracts structured data for ISDOC electronic invoice generation.

Supported languages: German (DE), English (EN), Czech (CZ)

File detection patterns:
- bestellungen_von_*, bestellungen-von-*
- invoices_from_*, invoices-from-*
- objednavky_od_*, objednavky-od-*

Author: Claude Code
Date: 2025-12-27
"""

import csv
import re
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from enum import Enum


class Language(Enum):
    """Supported CSV languages"""
    GERMAN = "de"
    ENGLISH = "en"
    CZECH = "cz"
    UNKNOWN = "unknown"


# Multi-language column mappings
# Key = internal field name, Value = dict of language -> column header
COLUMN_MAPPING = {
    # Order level fields
    "order_date": {
        "de": "Bestelldatum",
        "en": "Order Date",
        "cz": "Datum objednávky"
    },
    "order_number": {
        "de": "Bestellnummer",
        "en": "Order Number",
        "cz": "Číslo objednávky"
    },
    "account_group": {
        "de": ["Name des Empfängers", "Kontogruppe", "Firmenname", "Empfänger"],
        "en": ["Account Group", "Recipient Name", "Company Name"],
        "cz": ["Skupina účtu", "Název příjemce", "Firma"]
    },
    "po_number": {
        "de": "PO Nummer",
        "en": "PO Number",
        "cz": "Číslo PO"
    },
    "order_quantity": {
        "de": "Bestellmenge",
        "en": "Order Quantity",
        "cz": "Množství objednávky"
    },
    "currency": {
        "de": "Währung",
        "en": "Currency",
        "cz": "Měna"
    },
    "subtotal": {
        "de": "Zwischensumme",
        "en": "Subtotal",
        "cz": "Mezisoučet"
    },
    "shipping_costs": {
        "de": ["Versandkosten (inkl. USt.)", "Versandkosten"],
        "en": ["Shipping Costs", "Shipping", "Delivery Costs"],
        "cz": ["Náklady na dopravu", "Doprava"]
    },
    "promotion": {
        "de": ["Aktionen (inkl. USt.)", "Werbeaktion", "Rabatt"],
        "en": ["Promotion", "Discount", "Promo"],
        "cz": ["Sleva", "Akce"]
    },
    "vat": {
        "de": "USt",
        "en": "VAT",
        "cz": "DPH"
    },
    "total_incl_vat": {
        "de": ["Bestellung - Gesamt (inkl. USt.)", "Summe inkl. USt", "Gesamt inkl. USt"],
        "en": ["Order Total (incl. VAT)", "Total incl. VAT", "Total (incl. VAT)"],
        "cz": ["Celkem vč. DPH", "Celková objednávka vč. DPH"]
    },
    "order_status": {
        "de": "Bestellstatus",
        "en": "Order Status",
        "cz": "Stav objednávky"
    },

    # User/account fields
    "approver": {
        "de": "Genehmiger",
        "en": "Approver",
        "cz": "Schvalovatel"
    },
    "account_user": {
        "de": ["Käufer", "Kontobenutzer", "Besteller"],
        "en": ["Account User", "Buyer", "Purchaser"],
        "cz": ["Uživatel účtu", "Kupující"]
    },
    "user_email": {
        "de": ["Käufer E-Mail", "E-Mail-Adresse des Kontobenutzers", "Käufer-E-Mail"],
        "en": ["Account User Email Address", "Buyer Email", "Email"],
        "cz": ["E-mail uživatele účtu", "E-mail kupujícího"]
    },
    "user_vat_country": {
        "de": "Land/Region für Umsatzsteuer-Identifikationsnummer des Kontobenutzers",
        "en": "Country/Region for Account User VAT ID",
        "cz": "Země DIČ uživatele účtu"
    },
    "user_vat_id": {
        "de": ["Steuernummer des Käufers", "Umsatzsteuer-Identifikationsnummer des Kontobenutzers", "USt-IdNr. Käufer"],
        "en": ["Account User VAT ID", "Buyer VAT ID", "Tax Number"],
        "cz": ["DIČ uživatele účtu", "DIČ kupujícího"]
    },

    # Invoice fields
    "invoice_status": {
        "de": "Rechnungsstatus",
        "en": "Invoice Status",
        "cz": "Stav faktury"
    },
    "invoice_total": {
        "de": "Gesamtbetrag der Rechnung",
        "en": "Invoice Total Amount",
        "cz": "Celková částka faktury"
    },
    "invoice_open_amount": {
        "de": "Offener Betrag der Rechnung",
        "en": "Invoice Open Amount",
        "cz": "Nezaplacená částka faktury"
    },
    "invoice_issue_date": {
        "de": "Ausstellungsdatum der Rechnung",
        "en": "Invoice Issue Date",
        "cz": "Datum vystavení faktury"
    },
    "invoice_due_date": {
        "de": "Fälligkeitsdatum der Rechnung",
        "en": "Invoice Due Date",
        "cz": "Datum splatnosti faktury"
    },

    # Payment fields
    "payment_reference": {
        "de": "Zahlungsreferenznummer",
        "en": "Payment Reference Number",
        "cz": "Číslo platební reference"
    },
    "payment_date": {
        "de": "Zahlungsdatum",
        "en": "Payment Date",
        "cz": "Datum platby"
    },
    "payment_amount": {
        "de": "Zahlungsbetrag",
        "en": "Payment Amount",
        "cz": "Částka platby"
    },
    "payment_method": {
        "de": ["Zahlungsmethode", "Zahlungsart", "Bezahlmethode"],
        "en": ["Payment Method", "Payment Type"],
        "cz": ["Způsob platby", "Platební metoda"]
    },
    "payment_id": {
        "de": "Zahlungskennzeichnung",
        "en": "Payment ID",
        "cz": "Identifikátor platby"
    },

    # Product fields
    "amazon_category": {
        "de": "Amazon-interne Produktkategorie",
        "en": "Amazon Internal Product Category",
        "cz": "Interní kategorie produktu Amazon"
    },
    "asin": {
        "de": "ASIN",
        "en": "ASIN",
        "cz": "ASIN"
    },
    "title": {
        "de": "Titel",
        "en": "Title",
        "cz": "Název"
    },
    "unspsc": {
        "de": "UNSPSC",
        "en": "UNSPSC",
        "cz": "UNSPSC"
    },
    "segment": {
        "de": "Segment",
        "en": "Segment",
        "cz": "Segment"
    },
    "family": {
        "de": "FAMILIE",
        "en": "FAMILY",
        "cz": "RODINA"
    },
    "class": {
        "de": "KLASSE",
        "en": "CLASS",
        "cz": "TŘÍDA"
    },
    "commodity": {
        "de": "WARE",
        "en": "COMMODITY",
        "cz": "KOMODITA"
    },
    "brand_code": {
        "de": "Markencode",
        "en": "Brand Code",
        "cz": "Kód značky"
    },
    "brand": {
        "de": "Marke",
        "en": "Brand",
        "cz": "Značka"
    },
    "manufacturer": {
        "de": "Hersteller",
        "en": "Manufacturer",
        "cz": "Výrobce"
    },
    "model_number": {
        "de": "Modellnummer des Artikels",
        "en": "Item Model Number",
        "cz": "Modelové číslo položky"
    },
    "part_number": {
        "de": "Teilenummer",
        "en": "Part Number",
        "cz": "Číslo dílu"
    },
    "condition": {
        "de": "Produktzustand",
        "en": "Product Condition",
        "cz": "Stav produktu"
    },

    # Item pricing fields
    "listed_ppu": {
        "de": "Gelisteter PPU",
        "en": "Listed PPU",
        "cz": "Uvedená cena za kus"
    },
    "purchase_ppu": {
        "de": ["Kaufpreis pro Einheit (inkl. USt.)", "Kauf-PPU", "Einzelpreis"],
        "en": ["Purchase PPU", "Unit Price", "Price Per Unit"],
        "cz": ["Nákupní cena za kus", "Jednotková cena"]
    },
    "item_quantity": {
        "de": "Artikelmenge",
        "en": "Item Quantity",
        "cz": "Množství položky"
    },
    "item_subtotal": {
        "de": ["Summe (inkl. USt.)", "Artikelzwischensumme", "Zwischensumme"],
        "en": ["Item Subtotal", "Total (incl. VAT)", "Subtotal"],
        "cz": ["Mezisoučet položky", "Celkem položka"]
    },
    "item_shipping": {
        "de": "Versandkosten für Artikel",
        "en": "Item Shipping Costs",
        "cz": "Náklady na dopravu položky"
    },
    "item_promotion": {
        "de": "Werbeaktion für Artikel",
        "en": "Item Promotion",
        "cz": "Sleva na položku"
    },
    "item_vat": {
        "de": "Artikel-USt",
        "en": "Item VAT",
        "cz": "DPH položky"
    },
    "item_net_total": {
        "de": ["Summe (exkl. USt.)", "Nettosumme des Artikels", "Nettosumme"],
        "en": ["Item Net Total", "Total (excl. VAT)", "Net Total"],
        "cz": ["Čistá suma položky", "Celkem bez DPH"]
    },
    "item_vat_rate": {
        "de": "Umsatzsteuersatz für die Artikelzwischensumme",
        "en": "Item Subtotal VAT Rate",
        "cz": "Sazba DPH pro mezisoučet položky"
    },

    # Seller fields
    "seller_name": {
        "de": ["Seller name", "Name des Verkäufers", "Verkäufer"],
        "en": ["Seller Name", "Seller", "Vendor Name"],
        "cz": ["Název prodejce", "Prodejce"]
    },
    "seller_credentials": {
        "de": "Anmeldedaten des Verkäufers",
        "en": "Seller Credentials",
        "cz": "Přihlašovací údaje prodejce"
    },
    "seller_vat_country": {
        "de": "Land für Umsatzsteuer-Identifikationsnummer des Verkäufers",
        "en": "Country for Seller VAT ID",
        "cz": "Země DIČ prodejce"
    },
    "seller_vat_id": {
        "de": ["Seller VAT number", "Umsatzsteuer-Identifikationsnummer des Verkäufers", "USt-IdNr. Verkäufer"],
        "en": ["Seller VAT ID", "Seller VAT Number", "Seller Tax ID"],
        "cz": ["DIČ prodejce", "IČ DPH prodejce"]
    },

    # Cost center fields
    "gl_account": {
        "de": "Hauptbuchkontonummer",
        "en": "GL Account Number",
        "cz": "Číslo hlavního účtu"
    },
    "department": {
        "de": "Abteilung",
        "en": "Department",
        "cz": "Oddělení"
    },
    "cost_center": {
        "de": "Kostenstelle",
        "en": "Cost Center",
        "cz": "Nákladové středisko"
    },
    "project_number": {
        "de": "Projektnummer",
        "en": "Project Number",
        "cz": "Číslo projektu"
    },
    "location": {
        "de": "Ort",
        "en": "Location",
        "cz": "Místo"
    },

    # Address fields
    "address_line_1": {
        "de": "Adresszeile 1",
        "en": "Address Line 1",
        "cz": "Adresní řádek 1"
    },
    "address_line_2": {
        "de": "Adresszeile 2",
        "en": "Address Line 2",
        "cz": "Adresní řádek 2"
    },
    "state": {
        "de": "Bundesland",
        "en": "State",
        "cz": "Kraj"
    },
    "postal_code": {
        "de": "Postleitzahl",
        "en": "Postal Code",
        "cz": "PSČ"
    },

    # Shipping/Tracking fields
    "tracking_number": {
        "de": "Sendungsnummer",
        "en": "Tracking Number",
        "cz": "Číslo zásilky"
    },
    "delivery_method": {
        "de": "Liefermethode",
        "en": "Delivery Method",
        "cz": "Způsob doručení"
    },

    # Invoice number
    "invoice_number": {
        "de": "Rechnungsnummer",
        "en": "Invoice Number",
        "cz": "Číslo faktury"
    },

    # Order comments
    "order_comments": {
        "de": "Bestellkommentare",
        "en": "Order Comments",
        "cz": "Poznámky k objednávce"
    },

    # VAT rate and amount
    "vat_rate": {
        "de": "Umsatzsteuersatz",
        "en": "VAT Rate",
        "cz": "Sazba DPH"
    },
    "vat_amount": {
        "de": "USt.-Summe",
        "en": "VAT Amount",
        "cz": "Částka DPH"
    },

    # Additional price breakdowns
    "unit_price_excl_vat": {
        "de": "Kaufpreis pro Einheit (exkl. USt.)",
        "en": "Unit Price (excl. VAT)",
        "cz": "Jednotková cena bez DPH"
    },
    "shipping_excl_vat": {
        "de": "Versandkosten (exkl. USt.)",
        "en": "Shipping (excl. VAT)",
        "cz": "Doprava bez DPH"
    },
    "shipping_vat": {
        "de": "Versandkosten USt.",
        "en": "Shipping VAT",
        "cz": "DPH dopravy"
    },
    "promotion_excl_vat": {
        "de": "Aktionen (exkl. USt.)",
        "en": "Promotion (excl. VAT)",
        "cz": "Sleva bez DPH"
    },
    "promotion_vat": {
        "de": "Aktionen USt.",
        "en": "Promotion VAT",
        "cz": "DPH slevy"
    },

    # Delivery fields
    "recipient_name": {
        "de": "Empfängername",
        "en": "Recipient Name",
        "cz": "Jméno příjemce"
    },
    "recipient_email": {
        "de": "E-Mail des Empfängers",
        "en": "Recipient Email",
        "cz": "E-mail příjemce"
    },
}


@dataclass
class AmazonOrderItem:
    """Single item in an Amazon order"""
    asin: str
    title: str
    quantity: float
    unit_price: float  # Purchase PPU
    subtotal: float
    shipping: float
    promotion: float
    vat_amount: float
    vat_rate: float  # as percentage, e.g., 19.0
    net_total: float

    # Product details
    unspsc: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    condition: Optional[str] = None

    # Seller info
    seller_name: Optional[str] = None
    seller_vat_id: Optional[str] = None
    seller_country: Optional[str] = None

    @property
    def gross_total(self) -> float:
        """Total including VAT"""
        return self.net_total + self.vat_amount


@dataclass
class AmazonOrder:
    """Complete Amazon order with all items"""
    order_number: str
    order_date: datetime
    currency: str

    # Order totals
    subtotal: float
    shipping: float
    promotion: float
    vat: float
    total_incl_vat: float

    # Status
    status: str
    invoice_status: Optional[str] = None

    # Customer info
    account_user: Optional[str] = None
    user_email: Optional[str] = None
    user_vat_id: Optional[str] = None
    user_vat_country: Optional[str] = None
    account_group: Optional[str] = None

    # Invoice details
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None

    # Payment info
    payment_method: Optional[str] = None
    payment_date: Optional[datetime] = None
    payment_reference: Optional[str] = None

    # Cost allocation
    cost_center: Optional[str] = None
    department: Optional[str] = None
    project_number: Optional[str] = None
    gl_account: Optional[str] = None

    # Delivery
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    delivery_method: Optional[str] = None
    tracking_number: Optional[str] = None

    # Address
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    location: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None

    # Invoice number (separate from order number)
    invoice_number: Optional[str] = None

    # Comments
    order_comments: Optional[str] = None

    # VAT breakdown
    vat_rate: Optional[float] = None
    shipping_excl_vat: Optional[float] = None
    shipping_vat: Optional[float] = None
    promotion_excl_vat: Optional[float] = None
    promotion_vat: Optional[float] = None
    unit_price_excl_vat: Optional[float] = None

    # Items
    items: List[AmazonOrderItem] = field(default_factory=list)

    # Language detected
    language: Language = Language.UNKNOWN

    def to_isdoc_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for ISDOC generation"""
        # Calculate totals from items if order-level totals are missing
        items_net = sum(item.net_total for item in self.items)
        items_vat = sum(item.vat_amount for item in self.items)
        items_gross = sum(item.gross_total for item in self.items)

        # Use order totals or calculate from items
        total_net = self.subtotal if self.subtotal > 0 else items_net
        total_vat = self.vat if self.vat > 0 else items_vat
        total_gross = self.total_incl_vat if self.total_incl_vat > 0 else (items_gross + self.shipping + self.promotion)

        return {
            "doc_type": "FAKTURA",
            "number": self.order_number,
            "issue_date": self.invoice_date or self.order_date,
            "due_date": self.due_date,
            "taxable_date": self.invoice_date or self.order_date,
            "currency": self.currency,

            "customer": {
                "name": self.account_group or self.account_user or "Unknown",
                "dic": self.user_vat_id,
                "country": self.user_vat_country or "CZ",
                "email": self.user_email,
                "contact_name": self.account_user,
            },

            "items": [
                {
                    "description": item.title,
                    "quantity": item.quantity,
                    "unit": "ks",
                    "unit_price": item.unit_price,
                    "vat_rate": int(item.vat_rate) if item.vat_rate else 0,
                    "net_amount": item.net_total,
                    "vat_amount": item.vat_amount,
                    "gross_amount": item.gross_total,
                    "asin": item.asin,
                    "seller_name": item.seller_name,
                    "seller_vat_id": item.seller_vat_id,
                }
                for item in self.items
            ],

            "summary": {
                "total_net": total_net + self.shipping + self.promotion,
                "total_vat": total_vat,
                "total_gross": total_gross,
                "shipping": self.shipping,
                "promotion": self.promotion,
            },

            "payment": {
                "method": self.payment_method,
                "date": self.payment_date,
                "reference": self.payment_reference,
            },

            "cost_allocation": {
                "cost_center": self.cost_center,
                "department": self.department,
                "project": self.project_number,
                "gl_account": self.gl_account,
            }
        }


def detect_amazon_csv(filepath: str) -> bool:
    """
    Detect if a file is an Amazon Business invoice CSV

    Patterns checked:
    - Filename: bestellungen_von_*, invoices_from_*, objednavky_od_*
    - CSV headers contain Amazon-specific columns
    """
    path = Path(filepath)
    filename = path.name.lower()

    # Check filename patterns
    filename_patterns = [
        r'bestellungen[_-]von[_-]',
        r'bestellungen[_-]from[_-]',
        r'invoices[_-]from[_-]',
        r'invoices[_-]von[_-]',
        r'objednavky[_-]od[_-]',
        r'objednavky[_-]from[_-]',
        r'orders[_-]from[_-]',
        r'amazon.*invoice',
        r'amazon.*order',
    ]

    for pattern in filename_patterns:
        if re.search(pattern, filename):
            return True

    # If filename doesn't match, check CSV headers
    if path.suffix.lower() == '.csv':
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = next(reader, [])

                # Check for Amazon-specific columns
                amazon_indicators = [
                    'ASIN', 'Bestellnummer', 'Order Number', 'Číslo objednávky',
                    'Amazon-interne Produktkategorie', 'Amazon Internal Product Category'
                ]

                for header in headers:
                    if any(ind in header for ind in amazon_indicators):
                        return True
        except Exception:
            pass

    return False


class AmazonInvoiceCSVParser:
    """
    Parser for Amazon Business invoice CSV files

    Supports multi-language CSV exports (DE, EN, CZ)
    Groups rows by order number into AmazonOrder objects
    """

    def __init__(self):
        self.column_map: Dict[str, int] = {}
        self.language: Language = Language.UNKNOWN
        self.headers: List[str] = []

    def detect_language(self, headers: List[str]) -> Language:
        """Detect CSV language from headers"""
        # Count matches for each language
        scores = {lang: 0 for lang in [Language.GERMAN, Language.ENGLISH, Language.CZECH]}

        for header in headers:
            header_clean = header.strip()
            for field_name, translations in COLUMN_MAPPING.items():
                for lang_code, translated in translations.items():
                    if header_clean == translated:
                        lang = Language.GERMAN if lang_code == "de" else \
                               Language.ENGLISH if lang_code == "en" else \
                               Language.CZECH
                        scores[lang] += 1

        # Return language with highest score
        best_lang = max(scores, key=scores.get)
        if scores[best_lang] > 0:
            return best_lang
        return Language.UNKNOWN

    def build_column_map(self, headers: List[str]) -> Dict[str, int]:
        """Build mapping from internal field names to column indices"""
        column_map = {}
        lang_code = self.language.value

        for idx, header in enumerate(headers):
            header_clean = header.strip()
            for field_name, translations in COLUMN_MAPPING.items():
                if lang_code in translations:
                    # Support both single string and list of alternatives
                    possible_names = translations[lang_code]
                    if isinstance(possible_names, str):
                        possible_names = [possible_names]

                    if header_clean in possible_names:
                        column_map[field_name] = idx
                        break

        return column_map

    def get_value(self, row: List[str], field: str, default: Any = None) -> Any:
        """Get value from row by field name"""
        if field not in self.column_map:
            return default
        idx = self.column_map[field]
        if idx >= len(row):
            return default
        value = row[idx].strip()
        return value if value and value not in ['N/A', 'n/a', '-', ''] else default

    def parse_float(self, value: str, default: float = 0.0) -> float:
        """Parse float from string, handling European format"""
        if not value or value in ['N/A', 'n/a', '-', '']:
            return default
        try:
            # Handle European format (comma as decimal separator)
            value = value.replace('.', '').replace(',', '.')
            return float(value)
        except ValueError:
            return default

    def parse_date(self, value: str) -> Optional[datetime]:
        """Parse date from various formats"""
        if not value or value in ['N/A', 'n/a', '-', '']:
            return None

        formats = [
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%d.%m.%Y',
            '%m/%d/%Y',
            '%Y/%m/%d',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def parse_vat_rate(self, value: str) -> float:
        """Parse VAT rate from string like '19 %' or '0.19'"""
        if not value or value in ['N/A', 'n/a', '-', '']:
            return 0.0
        try:
            # Remove % and whitespace
            value = value.replace('%', '').strip()
            rate = float(value.replace(',', '.'))
            # If rate is less than 1, it's probably a decimal (0.19 = 19%)
            if 0 < rate < 1:
                rate *= 100
            return rate
        except ValueError:
            return 0.0

    def detect_delimiter(self, filepath: str) -> str:
        """Detect CSV delimiter (comma, semicolon, or tab)"""
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()

        # Count potential delimiters
        tab_count = first_line.count('\t')
        semicolon_count = first_line.count(';')
        comma_count = first_line.count(',')

        # Return the one with highest count
        if tab_count > semicolon_count and tab_count > comma_count:
            return '\t'
        elif semicolon_count > comma_count:
            return ';'
        return ','

    def parse_file(self, filepath: str) -> List[AmazonOrder]:
        """
        Parse Amazon CSV file and return list of orders

        Each order contains all its line items grouped together
        """
        orders: Dict[str, AmazonOrder] = {}

        # Detect delimiter
        delimiter = self.detect_delimiter(filepath)

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=delimiter)
            self.headers = next(reader)

            # Detect language and build column map
            self.language = self.detect_language(self.headers)
            self.column_map = self.build_column_map(self.headers)

            if not self.column_map.get('order_number'):
                raise ValueError("Cannot find order number column - unsupported CSV format")

            for row in reader:
                if not row or len(row) < 5:
                    continue

                order_number = self.get_value(row, 'order_number')
                if not order_number:
                    continue

                # Create or get existing order
                if order_number not in orders:
                    orders[order_number] = self._create_order(row)

                # Add item to order
                item = self._create_item(row)
                if item:
                    orders[order_number].items.append(item)

        return list(orders.values())

    def _create_order(self, row: List[str]) -> AmazonOrder:
        """Create AmazonOrder from CSV row"""
        return AmazonOrder(
            order_number=self.get_value(row, 'order_number', ''),
            order_date=self.parse_date(self.get_value(row, 'order_date')) or datetime.now(),
            currency=self.get_value(row, 'currency', 'EUR'),

            subtotal=self.parse_float(self.get_value(row, 'subtotal')),
            shipping=self.parse_float(self.get_value(row, 'shipping_costs')),
            promotion=self.parse_float(self.get_value(row, 'promotion')),
            vat=self.parse_float(self.get_value(row, 'vat')),
            total_incl_vat=self.parse_float(self.get_value(row, 'total_incl_vat')),

            status=self.get_value(row, 'order_status', 'Unknown'),
            invoice_status=self.get_value(row, 'invoice_status'),

            account_user=self.get_value(row, 'account_user'),
            user_email=self.get_value(row, 'user_email'),
            user_vat_id=self.get_value(row, 'user_vat_id'),
            user_vat_country=self.get_value(row, 'user_vat_country'),
            account_group=self.get_value(row, 'account_group'),

            invoice_date=self.parse_date(self.get_value(row, 'invoice_issue_date')),
            due_date=self.parse_date(self.get_value(row, 'invoice_due_date')),

            payment_method=self.get_value(row, 'payment_method'),
            payment_date=self.parse_date(self.get_value(row, 'payment_date')),
            payment_reference=self.get_value(row, 'payment_reference'),

            cost_center=self.get_value(row, 'cost_center'),
            department=self.get_value(row, 'department'),
            project_number=self.get_value(row, 'project_number'),
            gl_account=self.get_value(row, 'gl_account'),

            recipient_name=self.get_value(row, 'recipient_name'),
            recipient_email=self.get_value(row, 'recipient_email'),
            delivery_method=self.get_value(row, 'delivery_method'),
            tracking_number=self.get_value(row, 'tracking_number'),

            # Address
            address_line_1=self.get_value(row, 'address_line_1'),
            address_line_2=self.get_value(row, 'address_line_2'),
            location=self.get_value(row, 'location'),
            state=self.get_value(row, 'state'),
            postal_code=self.get_value(row, 'postal_code'),

            # Invoice number
            invoice_number=self.get_value(row, 'invoice_number'),

            # Comments
            order_comments=self.get_value(row, 'order_comments'),

            # VAT breakdown
            vat_rate=self.parse_vat_rate(self.get_value(row, 'vat_rate')),
            shipping_excl_vat=self.parse_float(self.get_value(row, 'shipping_excl_vat')),
            shipping_vat=self.parse_float(self.get_value(row, 'shipping_vat')),
            promotion_excl_vat=self.parse_float(self.get_value(row, 'promotion_excl_vat')),
            promotion_vat=self.parse_float(self.get_value(row, 'promotion_vat')),
            unit_price_excl_vat=self.parse_float(self.get_value(row, 'unit_price_excl_vat')),

            language=self.language,
        )

    def _create_item(self, row: List[str]) -> Optional[AmazonOrderItem]:
        """Create AmazonOrderItem from CSV row"""
        asin = self.get_value(row, 'asin')
        title = self.get_value(row, 'title')

        if not asin and not title:
            return None

        return AmazonOrderItem(
            asin=asin or '',
            title=title or 'Unknown Product',
            quantity=self.parse_float(self.get_value(row, 'item_quantity'), 1.0),
            unit_price=self.parse_float(self.get_value(row, 'purchase_ppu')),
            subtotal=self.parse_float(self.get_value(row, 'item_subtotal')),
            shipping=self.parse_float(self.get_value(row, 'item_shipping')),
            promotion=self.parse_float(self.get_value(row, 'item_promotion')),
            vat_amount=self.parse_float(self.get_value(row, 'item_vat')),
            vat_rate=self.parse_vat_rate(self.get_value(row, 'item_vat_rate')),
            net_total=self.parse_float(self.get_value(row, 'item_net_total')),

            unspsc=self.get_value(row, 'unspsc'),
            brand=self.get_value(row, 'brand'),
            manufacturer=self.get_value(row, 'manufacturer'),
            model_number=self.get_value(row, 'model_number'),
            condition=self.get_value(row, 'condition'),

            seller_name=self.get_value(row, 'seller_name'),
            seller_vat_id=self.get_value(row, 'seller_vat_id'),
            seller_country=self.get_value(row, 'seller_vat_country'),
        )

    def parse_to_isdoc_list(self, filepath: str) -> List[Dict[str, Any]]:
        """Parse CSV and return list of ISDOC-compatible dictionaries"""
        orders = self.parse_file(filepath)
        return [order.to_isdoc_dict() for order in orders]


# Convenience functions
def parse_amazon_csv(filepath: str) -> List[AmazonOrder]:
    """Parse Amazon CSV file and return list of orders"""
    parser = AmazonInvoiceCSVParser()
    return parser.parse_file(filepath)


def parse_amazon_csv_to_isdoc(filepath: str) -> List[Dict[str, Any]]:
    """Parse Amazon CSV and return ISDOC-compatible dictionaries"""
    parser = AmazonInvoiceCSVParser()
    return parser.parse_to_isdoc_list(filepath)


if __name__ == "__main__":
    import sys
    import json

    print("=" * 70)
    print("Amazon Business Invoice CSV Parser")
    print("=" * 70)

    if len(sys.argv) > 1:
        filepath = sys.argv[1]

        if not os.path.exists(filepath):
            print(f"Error: File not found: {filepath}")
            sys.exit(1)

        print(f"\nParsing: {filepath}")
        print(f"Is Amazon CSV: {detect_amazon_csv(filepath)}")

        try:
            orders = parse_amazon_csv(filepath)
            print(f"\nFound {len(orders)} orders:\n")

            for order in orders:
                print(f"Order: {order.order_number}")
                print(f"  Date: {order.order_date}")
                print(f"  Status: {order.status}")
                print(f"  Currency: {order.currency}")
                print(f"  Total: {order.total_incl_vat} {order.currency}")
                print(f"  Items: {len(order.items)}")
                for item in order.items[:3]:  # Show first 3 items
                    print(f"    - {item.title[:50]}... ({item.quantity}x {item.unit_price})")
                if len(order.items) > 3:
                    print(f"    ... and {len(order.items) - 3} more items")
                print()

            # Export ISDOC data
            isdoc_data = [o.to_isdoc_dict() for o in orders]
            print("\nISDOC-compatible data:")
            print(json.dumps(isdoc_data[0] if isdoc_data else {}, indent=2, default=str)[:500])

        except Exception as e:
            print(f"Error parsing file: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\nUsage: python amazon_invoice_csv.py <csv_file>")
        print("\nSupported file patterns:")
        print("  - bestellungen_von_*.csv")
        print("  - invoices_from_*.csv")
        print("  - objednavky_od_*.csv")
        print("\nSupported languages: German, English, Czech")
