#!/usr/bin/env python3
"""
** The project "maj-document-recognition-v2/src" is a document matching system that automates the pr
"""

"""
Czech Electronic Document Generator (ISDOC)
============================================
Generates Czech electronic business documents in ISDOC format.
Supports: Faktury, Dodací listy, Dobropisy, Zálohové faktury

ISDOC is Czech national standard for electronic invoices.
Based on UN/CEFACT CII and compatible with EU standards.

Author: Claude Code
Date: 2025-12-04
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import hashlib
import json
from pathlib import Path


class DocumentType(Enum):
    """Czech business document types"""
    FAKTURA = 1           # Invoice
    DOBROPIS = 2          # Credit note
    VRUBOPIS = 3          # Debit note
    ZALOHOVA_FAKTURA = 4  # Proforma invoice
    DODACI_LIST = 5       # Delivery note
    OBJEDNAVKA = 6        # Purchase order


class VATRate(Enum):
    """Czech VAT rates (DPH)"""
    ZAKLADNI = 21      # Standard rate
    SNIZENA_1 = 15     # First reduced rate
    SNIZENA_2 = 10     # Second reduced rate
    NULOVA = 0         # Zero rate (export, etc.)


@dataclass
class Party:
    """Business party (dodavatel/odberatel)"""
    name: str                          # Název firmy
    ico: str                           # IČO (Company ID)
    dic: Optional[str] = None          # DIČ (VAT ID)
    street: Optional[str] = None       # Ulice
    city: Optional[str] = None         # Město
    postal_code: Optional[str] = None  # PSČ
    country: str = "CZ"                # Kód země
    contact_name: Optional[str] = None # Kontaktní osoba
    email: Optional[str] = None        # Email
    phone: Optional[str] = None        # Telefon
    bank_account: Optional[str] = None # Číslo účtu
    iban: Optional[str] = None         # IBAN
    swift: Optional[str] = None        # BIC/SWIFT


@dataclass
class LineItem:
    """Invoice line item (položka faktury)"""
    description: str               # Popis položky
    quantity: float               # Množství
    unit: str = "ks"              # Jednotka (ks, hod, m, kg, etc.)
    unit_price: float = 0.0       # Cena za jednotku bez DPH
    vat_rate: VATRate = VATRate.ZAKLADNI
    discount_percent: float = 0.0  # Sleva v %

    @property
    def net_amount(self) -> float:
        """Částka bez DPH"""
        base = self.quantity * self.unit_price
        return base * (1 - self.discount_percent / 100)

    @property
    def vat_amount(self) -> float:
        """Částka DPH"""
        return self.net_amount * self.vat_rate.value / 100

    @property
    def gross_amount(self) -> float:
        """Částka včetně DPH"""
        return self.net_amount + self.vat_amount


@dataclass
class CzechDocument:
    """Czech business document structure"""
    doc_type: DocumentType
    number: str                       # Číslo dokladu
    issue_date: date                  # Datum vystavení
    due_date: Optional[date] = None   # Datum splatnosti
    taxable_date: Optional[date] = None  # DUZP

    supplier: Optional[Party] = None      # Dodavatel
    customer: Optional[Party] = None      # Odběratel

    items: List[LineItem] = field(default_factory=list)

    currency: str = "CZK"             # Měna
    payment_method: str = "bank"      # Způsob úhrady
    variable_symbol: Optional[str] = None  # VS
    constant_symbol: Optional[str] = None  # KS
    specific_symbol: Optional[str] = None  # SS

    note: Optional[str] = None        # Poznámka
    order_reference: Optional[str] = None  # Číslo objednávky

    @property
    def total_net(self) -> float:
        """Celkem bez DPH"""
        return sum(item.net_amount for item in self.items)

    @property
    def total_vat(self) -> float:
        """Celkem DPH"""
        return sum(item.vat_amount for item in self.items)

    @property
    def total_gross(self) -> float:
        """Celkem s DPH"""
        return sum(item.gross_amount for item in self.items)

    def vat_breakdown(self) -> Dict[int, Dict[str, float]]:
        """Rozúčtování DPH podle sazeb"""
        breakdown = {}
        for item in self.items:
            rate = item.vat_rate.value
            if rate not in breakdown:
                breakdown[rate] = {'base': 0.0, 'vat': 0.0}
            breakdown[rate]['base'] += item.net_amount
            breakdown[rate]['vat'] += item.vat_amount
        return breakdown


class ISDOCGenerator:
    """
    Generator for ISDOC (Czech electronic invoice standard)

    ISDOC version: 6.0.2
    Namespace: http://isdoc.cz/namespace/2013
    """

    NAMESPACE = "http://isdoc.cz/namespace/2013"
    VERSION = "6.0.2"

    def __init__(self):
        self.ns = {'isdoc': self.NAMESPACE}

    def generate(self, doc: CzechDocument) -> str:
        """Generate ISDOC XML from document"""

        # Root element with namespace
        root = ET.Element('Invoice')
        root.set('xmlns', self.NAMESPACE)
        root.set('version', self.VERSION)

        # Document header
        self._add_header(root, doc)

        # Parties
        if doc.supplier:
            self._add_party(root, 'AccountingSupplierParty', doc.supplier)
        if doc.customer:
            self._add_party(root, 'AccountingCustomerParty', doc.customer)

        # Line items
        lines = ET.SubElement(root, 'InvoiceLines')
        for idx, item in enumerate(doc.items, 1):
            self._add_line_item(lines, item, idx)

        # Tax summary
        self._add_tax_summary(root, doc)

        # Payment info
        self._add_payment_info(root, doc)

        # Document summary
        self._add_summary(root, doc)

        # Generate pretty XML
        xml_str = ET.tostring(root, encoding='unicode')
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ", encoding="UTF-8").decode('utf-8')

    def _add_header(self, root: ET.Element, doc: CzechDocument):
        """Add document header"""
        ET.SubElement(root, 'DocumentType').text = str(doc.doc_type.value)
        ET.SubElement(root, 'ID').text = doc.number
        ET.SubElement(root, 'UUID').text = self._generate_uuid(doc)
        ET.SubElement(root, 'IssueDate').text = doc.issue_date.isoformat()

        if doc.taxable_date:
            ET.SubElement(root, 'TaxPointDate').text = doc.taxable_date.isoformat()

        # VAT applicability
        vat_scheme = ET.SubElement(root, 'VATApplicable')
        vat_scheme.text = 'true' if doc.total_vat > 0 else 'false'

        ET.SubElement(root, 'LocalCurrencyCode').text = doc.currency
        ET.SubElement(root, 'CurrRateRef').text = '1'

        if doc.note:
            ET.SubElement(root, 'Note').text = doc.note

        if doc.order_reference:
            order_ref = ET.SubElement(root, 'OrderReference')
            ET.SubElement(order_ref, 'SalesOrderID').text = doc.order_reference

    def _add_party(self, root: ET.Element, tag: str, party: Party):
        """Add party (supplier/customer)"""
        party_elem = ET.SubElement(root, tag)
        party_detail = ET.SubElement(party_elem, 'Party')

        # Identification
        party_ident = ET.SubElement(party_detail, 'PartyIdentification')

        if party.ico:
            ET.SubElement(party_ident, 'ID').text = party.ico

        # Name
        party_name = ET.SubElement(party_detail, 'PartyName')
        ET.SubElement(party_name, 'Name').text = party.name

        # Address
        if any([party.street, party.city, party.postal_code]):
            addr = ET.SubElement(party_detail, 'PostalAddress')
            if party.street:
                ET.SubElement(addr, 'StreetName').text = party.street
            if party.city:
                ET.SubElement(addr, 'CityName').text = party.city
            if party.postal_code:
                ET.SubElement(addr, 'PostalZone').text = party.postal_code

            country = ET.SubElement(addr, 'Country')
            ET.SubElement(country, 'IdentificationCode').text = party.country
            ET.SubElement(country, 'Name').text = self._country_name(party.country)

        # Tax registration (DIČ)
        if party.dic:
            tax_scheme = ET.SubElement(party_detail, 'PartyTaxScheme')
            ET.SubElement(tax_scheme, 'CompanyID').text = party.dic
            scheme = ET.SubElement(tax_scheme, 'TaxScheme')
            ET.SubElement(scheme, 'Name').text = 'VAT'

        # Contact
        if any([party.contact_name, party.email, party.phone]):
            contact = ET.SubElement(party_detail, 'Contact')
            if party.contact_name:
                ET.SubElement(contact, 'Name').text = party.contact_name
            if party.phone:
                ET.SubElement(contact, 'Telephone').text = party.phone
            if party.email:
                ET.SubElement(contact, 'ElectronicMail').text = party.email

    def _add_line_item(self, parent: ET.Element, item: LineItem, line_num: int):
        """Add invoice line item"""
        line = ET.SubElement(parent, 'InvoiceLine')

        ET.SubElement(line, 'ID').text = str(line_num)
        ET.SubElement(line, 'InvoicedQuantity').text = str(item.quantity)
        ET.SubElement(line, 'LineExtensionAmount').text = f"{item.net_amount:.2f}"
        ET.SubElement(line, 'LineExtensionAmountTaxInclusive').text = f"{item.gross_amount:.2f}"
        ET.SubElement(line, 'LineExtensionTaxAmount').text = f"{item.vat_amount:.2f}"
        ET.SubElement(line, 'UnitPrice').text = f"{item.unit_price:.2f}"
        ET.SubElement(line, 'UnitPriceTaxInclusive').text = f"{item.unit_price * (1 + item.vat_rate.value/100):.2f}"

        # Classified tax category
        tax_cat = ET.SubElement(line, 'ClassifiedTaxCategory')
        ET.SubElement(tax_cat, 'Percent').text = str(item.vat_rate.value)
        ET.SubElement(tax_cat, 'VATCalculationMethod').text = '0'  # 0 = standard

        # Item description
        item_elem = ET.SubElement(line, 'Item')
        ET.SubElement(item_elem, 'Description').text = item.description

    def _add_tax_summary(self, root: ET.Element, doc: CzechDocument):
        """Add VAT summary by rate"""
        tax_total = ET.SubElement(root, 'TaxTotal')

        breakdown = doc.vat_breakdown()
        for rate, amounts in sorted(breakdown.items()):
            subtotal = ET.SubElement(tax_total, 'TaxSubTotal')
            ET.SubElement(subtotal, 'TaxableAmount').text = f"{amounts['base']:.2f}"
            ET.SubElement(subtotal, 'TaxAmount').text = f"{amounts['vat']:.2f}"
            ET.SubElement(subtotal, 'AlreadyClaimedTaxableAmount').text = "0.00"
            ET.SubElement(subtotal, 'AlreadyClaimedTaxAmount').text = "0.00"
            ET.SubElement(subtotal, 'DifferenceTaxableAmount').text = f"{amounts['base']:.2f}"
            ET.SubElement(subtotal, 'DifferenceTaxAmount').text = f"{amounts['vat']:.2f}"

            tax_cat = ET.SubElement(subtotal, 'TaxCategory')
            ET.SubElement(tax_cat, 'Percent').text = str(rate)

        ET.SubElement(tax_total, 'TaxAmount').text = f"{doc.total_vat:.2f}"

    def _add_payment_info(self, root: ET.Element, doc: CzechDocument):
        """Add payment information"""
        payment = ET.SubElement(root, 'PaymentMeans')

        # Payment method code
        method_code = {
            'bank': '42',      # Bank transfer
            'cash': '10',      # Cash
            'card': '48',      # Card
            'check': '20',     # Check
        }.get(doc.payment_method, '42')

        ET.SubElement(payment, 'PaymentMeansCode').text = method_code

        if doc.due_date:
            ET.SubElement(payment, 'PaymentDueDate').text = doc.due_date.isoformat()

        # Bank account
        if doc.supplier and doc.supplier.bank_account:
            account = ET.SubElement(payment, 'PayeeFinancialAccount')
            ET.SubElement(account, 'ID').text = doc.supplier.bank_account

            if doc.supplier.iban:
                ET.SubElement(account, 'IBAN').text = doc.supplier.iban
            if doc.supplier.swift:
                branch = ET.SubElement(account, 'FinancialInstitutionBranch')
                inst = ET.SubElement(branch, 'FinancialInstitution')
                ET.SubElement(inst, 'BIC').text = doc.supplier.swift

        # Payment symbols (Czech specific)
        details = ET.SubElement(payment, 'PaymentNote')
        symbols = []
        if doc.variable_symbol:
            symbols.append(f"VS: {doc.variable_symbol}")
        if doc.constant_symbol:
            symbols.append(f"KS: {doc.constant_symbol}")
        if doc.specific_symbol:
            symbols.append(f"SS: {doc.specific_symbol}")
        details.text = ", ".join(symbols) if symbols else ""

    def _add_summary(self, root: ET.Element, doc: CzechDocument):
        """Add document totals"""
        summary = ET.SubElement(root, 'LegalMonetaryTotal')

        ET.SubElement(summary, 'TaxExclusiveAmount').text = f"{doc.total_net:.2f}"
        ET.SubElement(summary, 'TaxInclusiveAmount').text = f"{doc.total_gross:.2f}"
        ET.SubElement(summary, 'AlreadyClaimedTaxExclusiveAmount').text = "0.00"
        ET.SubElement(summary, 'AlreadyClaimedTaxInclusiveAmount').text = "0.00"
        ET.SubElement(summary, 'DifferenceTaxExclusiveAmount').text = f"{doc.total_net:.2f}"
        ET.SubElement(summary, 'DifferenceTaxInclusiveAmount').text = f"{doc.total_gross:.2f}"
        ET.SubElement(summary, 'PayableRoundingAmount').text = "0.00"
        ET.SubElement(summary, 'PaidDepositsAmount').text = "0.00"
        ET.SubElement(summary, 'PayableAmount').text = f"{doc.total_gross:.2f}"

    def _generate_uuid(self, doc: CzechDocument) -> str:
        """Generate unique document ID"""
        content = f"{doc.number}-{doc.issue_date}-{doc.total_gross}"
        hash_val = hashlib.md5(content.encode()).hexdigest()
        return f"{hash_val[:8]}-{hash_val[8:12]}-{hash_val[12:16]}-{hash_val[16:20]}-{hash_val[20:32]}"

    def _country_name(self, code: str) -> str:
        """Get country name from code"""
        names = {
            'CZ': 'Česká republika',
            'SK': 'Slovensko',
            'DE': 'Německo',
            'AT': 'Rakousko',
            'PL': 'Polsko',
        }
        return names.get(code, code)


class CzechDocumentGenerator:
    """
    High-level generator for Czech business documents.
    Supports multiple output formats.
    """

    def __init__(self):
        self.isdoc = ISDOCGenerator()

    def from_extracted_data(self, extracted: Dict[str, Any], doc_type: DocumentType = DocumentType.FAKTURA) -> CzechDocument:
        """
        Create CzechDocument from extracted invoice data.
        Compatible with data_extractors.py output format.
        """
        doc = CzechDocument(
            doc_type=doc_type,
            number=extracted.get('invoice_number', 'N/A'),
            issue_date=self._parse_date(extracted.get('issue_date')) or date.today(),
            due_date=self._parse_date(extracted.get('due_date')),
            taxable_date=self._parse_date(extracted.get('taxable_date')),
            currency=extracted.get('currency', 'CZK'),
            variable_symbol=extracted.get('variable_symbol'),
        )

        # Supplier
        supplier_data = extracted.get('supplier', {})
        if supplier_data:
            doc.supplier = Party(
                name=supplier_data.get('name', 'N/A'),
                ico=supplier_data.get('ico', ''),
                dic=supplier_data.get('dic'),
                street=supplier_data.get('street'),
                city=supplier_data.get('city'),
                postal_code=supplier_data.get('postal_code'),
                bank_account=supplier_data.get('bank_account'),
                iban=supplier_data.get('iban'),
            )

        # Customer
        customer_data = extracted.get('customer', {})
        if customer_data:
            doc.customer = Party(
                name=customer_data.get('name', 'N/A'),
                ico=customer_data.get('ico', ''),
                dic=customer_data.get('dic'),
            )

        # Line items
        for item_data in extracted.get('line_items', []):
            vat_rate = VATRate.ZAKLADNI
            vat_val = item_data.get('vat_rate', 21)
            if vat_val == 15:
                vat_rate = VATRate.SNIZENA_1
            elif vat_val == 10:
                vat_rate = VATRate.SNIZENA_2
            elif vat_val == 0:
                vat_rate = VATRate.NULOVA

            doc.items.append(LineItem(
                description=item_data.get('description', 'Položka'),
                quantity=float(item_data.get('quantity', 1)),
                unit=item_data.get('unit', 'ks'),
                unit_price=float(item_data.get('unit_price', 0)),
                vat_rate=vat_rate,
            ))

        return doc

    def generate_isdoc(self, doc: CzechDocument, output_path: Optional[str] = None) -> str:
        """Generate ISDOC XML"""
        xml_content = self.isdoc.generate(doc)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)

        return xml_content

    def generate_json(self, doc: CzechDocument, output_path: Optional[str] = None) -> str:
        """Generate JSON representation"""
        data = {
            'document_type': doc.doc_type.name,
            'number': doc.number,
            'issue_date': doc.issue_date.isoformat(),
            'due_date': doc.due_date.isoformat() if doc.due_date else None,
            'taxable_date': doc.taxable_date.isoformat() if doc.taxable_date else None,
            'currency': doc.currency,
            'payment_method': doc.payment_method,
            'variable_symbol': doc.variable_symbol,
            'constant_symbol': doc.constant_symbol,
            'note': doc.note,
            'supplier': self._party_to_dict(doc.supplier) if doc.supplier else None,
            'customer': self._party_to_dict(doc.customer) if doc.customer else None,
            'items': [
                {
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit': item.unit,
                    'unit_price': item.unit_price,
                    'vat_rate': item.vat_rate.value,
                    'net_amount': round(item.net_amount, 2),
                    'vat_amount': round(item.vat_amount, 2),
                    'gross_amount': round(item.gross_amount, 2),
                }
                for item in doc.items
            ],
            'vat_breakdown': {
                str(rate): {'base': round(vals['base'], 2), 'vat': round(vals['vat'], 2)}
                for rate, vals in doc.vat_breakdown().items()
            },
            'totals': {
                'net': round(doc.total_net, 2),
                'vat': round(doc.total_vat, 2),
                'gross': round(doc.total_gross, 2),
            }
        }

        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)

        return json_str

    def _party_to_dict(self, party: Party) -> Dict[str, Any]:
        """Convert Party to dict"""
        return {
            'name': party.name,
            'ico': party.ico,
            'dic': party.dic,
            'street': party.street,
            'city': party.city,
            'postal_code': party.postal_code,
            'country': party.country,
            'bank_account': party.bank_account,
            'iban': party.iban,
        }

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date from string"""
        if not date_str:
            return None

        formats = [
            '%Y-%m-%d',
            '%d.%m.%Y',
            '%d/%m/%Y',
            '%d. %m. %Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None


def demo():
    """Demo: Generate sample Czech invoice"""

    # Create supplier
    supplier = Party(
        name="ACME Czech s.r.o.",
        ico="12345678",
        dic="CZ12345678",
        street="Technická 1234/5",
        city="Praha",
        postal_code="16000",
        bank_account="1234567890/0800",
        iban="CZ6508000000001234567890",
        swift="GIBACZPX",
        email="info@acme.cz",
        phone="+420 123 456 789",
    )

    # Create customer
    customer = Party(
        name="Zákazník a.s.",
        ico="87654321",
        dic="CZ87654321",
        street="Hlavní 100",
        city="Brno",
        postal_code="60200",
    )

    # Create invoice
    doc = CzechDocument(
        doc_type=DocumentType.FAKTURA,
        number="FV-2024-001234",
        issue_date=date.today(),
        due_date=date(2025, 1, 4),
        taxable_date=date.today(),
        supplier=supplier,
        customer=customer,
        variable_symbol="2024001234",
        constant_symbol="0308",
        note="Děkujeme za Vaši objednávku!",
        order_reference="OBJ-2024-5678",
    )

    # Add items
    doc.items = [
        LineItem(
            description="Konzultace IT služby",
            quantity=8,
            unit="hod",
            unit_price=1500.00,
            vat_rate=VATRate.ZAKLADNI,
        ),
        LineItem(
            description="Software licence (roční)",
            quantity=1,
            unit="ks",
            unit_price=12000.00,
            vat_rate=VATRate.ZAKLADNI,
        ),
        LineItem(
            description="Kniha - programování",
            quantity=2,
            unit="ks",
            unit_price=450.00,
            vat_rate=VATRate.SNIZENA_2,  # Books = 10%
        ),
    ]

    # Generate
    gen = CzechDocumentGenerator()

    print("=" * 60)
    print("CZECH INVOICE GENERATOR - DEMO")
    print("=" * 60)

    # JSON output
    print("\n📋 JSON Output:")
    print("-" * 40)
    json_out = gen.generate_json(doc)
    print(json_out[:500] + "..." if len(json_out) > 500 else json_out)

    # ISDOC output
    print("\n📄 ISDOC XML Output (first 1000 chars):")
    print("-" * 40)
    isdoc_out = gen.generate_isdoc(doc)
    print(isdoc_out[:1000] + "...")

    # Summary
    print("\n💰 Summary:")
    print(f"   Základ DPH 21%: {sum(i.net_amount for i in doc.items if i.vat_rate == VATRate.ZAKLADNI):,.2f} Kč")
    print(f"   Základ DPH 10%: {sum(i.net_amount for i in doc.items if i.vat_rate == VATRate.SNIZENA_2):,.2f} Kč")
    print(f"   DPH celkem:     {doc.total_vat:,.2f} Kč")
    print(f"   Celkem s DPH:   {doc.total_gross:,.2f} Kč")

    print("\n✅ Demo complete!")


if __name__ == "__main__":
    demo()
