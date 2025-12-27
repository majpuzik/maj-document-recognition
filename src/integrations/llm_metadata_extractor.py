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
LLM Metadata Extractor with Escalation Strategy + ISDOC Generator
Extracts document metadata using regex first, then escalates to LLM if needed.
Generates ISDOC XML format for accounting documents.

Supports:
- Local Ollama (Mac/Linux/DGX)
- Remote Ollama via network
- Automatic model selection based on availability
- ISDOC 6.0.2 XML generation for Czech invoices

Usage:
    python llm_metadata_extractor.py --mode test       # Test on sample
    python llm_metadata_extractor.py --mode paperless  # Process Paperless docs
    python llm_metadata_extractor.py --mode isdoc      # Generate ISDOC for docs
"""

import os
import sys
import re
import json
import uuid
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from xml.etree import ElementTree as ET
from xml.dom import minidom

# =============================================================================
# CONFIGURATION
# =============================================================================

class OllamaConfig:
    """Ollama server configuration with auto-discovery"""

    SERVERS = [
        {"name": "local", "url": "http://localhost:11434", "priority": 1},
        {"name": "dgx", "url": "http://192.168.10.200:11434", "priority": 2},
    ]

    # Preferred models in order of priority
    PREFERRED_MODELS = [
        "czech-finance-speed",  # Custom fine-tuned for Czech documents
        "qwen2.5:32b",          # Large model for complex extraction
        "qwen2.5:14b",          # Medium model
        "ministral-3:8b",       # Smaller fallback
    ]

    TIMEOUT = 120  # seconds per request


@dataclass
class ExtractionResult:
    """Result of metadata extraction"""
    field: str
    value: Any
    confidence: float  # 0.0 - 1.0
    source: str  # "regex" or "llm_escalated"
    model_used: Optional[str] = None


# =============================================================================
# REGEX EXTRACTORS (Fast, reliable for structured data)
# =============================================================================

class RegexExtractor:
    """Fast regex-based extraction - first line of defense"""

    # Date patterns
    DATE_PATTERNS = [
        # US format in emails: 5/12/25, 1:30 PM
        (r'Date:\s*(\d{1,2})/(\d{1,2})/(\d{2}),', 'us_email'),
        # ISO: 2024-10-26
        (r'(\d{4})-(\d{2})-(\d{2})', 'iso'),
        # European: 26.10.2024 or 26. 10. 2024
        (r'(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})', 'european'),
        # Czech: 26. října 2024
        (r'(\d{1,2})\.\s*(ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince)\s*(\d{4})', 'czech_text'),
    ]

    CZECH_MONTHS = {
        'ledna': 1, 'února': 2, 'března': 3, 'dubna': 4,
        'května': 5, 'června': 6, 'července': 7, 'srpna': 8,
        'září': 9, 'října': 10, 'listopadu': 11, 'prosince': 12
    }

    # Amount patterns
    AMOUNT_PATTERNS = [
        # Czech format: 1 234,56 Kč or 1234.56 CZK
        r'(\d{1,3}(?:\s?\d{3})*[,\.]\d{2})\s*(?:Kč|CZK|,-)',
        # With currency symbol: € 1,234.56
        r'[€$]\s*(\d{1,3}(?:[,\s]?\d{3})*[,\.]\d{2})',
        # Celkem/Total patterns
        r'(?:Celkem|Total|Suma|K úhradě)[:\s]*(\d{1,3}(?:[\s,]?\d{3})*[,\.]\d{2})',
    ]

    # Company ID patterns (Czech IČO/DIČ)
    ICO_PATTERN = r'I[ČC]O?[:\s]*(\d{8})'
    DIC_PATTERN = r'DI[ČC][:\s]*([A-Z]{2}\d{8,10})'

    @classmethod
    def extract_date(cls, text: str) -> Optional[ExtractionResult]:
        """Extract date using regex patterns"""
        for pattern, format_type in cls.DATE_PATTERNS:
            match = re.search(pattern, text[:2000], re.IGNORECASE)
            if match:
                try:
                    if format_type == 'us_email':
                        month, day, year = match.groups()
                        year = 2000 + int(year) if int(year) < 50 else 1900 + int(year)
                        date = datetime(year, int(month), int(day)).date()
                    elif format_type == 'iso':
                        year, month, day = match.groups()
                        date = datetime(int(year), int(month), int(day)).date()
                    elif format_type == 'european':
                        day, month, year = match.groups()
                        date = datetime(int(year), int(month), int(day)).date()
                    elif format_type == 'czech_text':
                        day, month_name, year = match.groups()
                        month = cls.CZECH_MONTHS.get(month_name.lower(), 1)
                        date = datetime(int(year), month, int(day)).date()
                    else:
                        continue

                    return ExtractionResult(
                        field="date",
                        value=date.isoformat(),
                        confidence=0.9,
                        source="regex"
                    )
                except (ValueError, KeyError):
                    continue
        return None

    @classmethod
    def extract_amount(cls, text: str) -> Optional[ExtractionResult]:
        """Extract monetary amount"""
        for pattern in cls.AMOUNT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1)
                amount_str = amount_str.replace(' ', '').replace(',', '.')
                try:
                    amount = float(amount_str)
                    return ExtractionResult(
                        field="amount",
                        value=amount,
                        confidence=0.85,
                        source="regex"
                    )
                except ValueError:
                    continue
        return None

    @classmethod
    def extract_ico(cls, text: str) -> Optional[ExtractionResult]:
        """Extract Czech company ID (IČO)"""
        match = re.search(cls.ICO_PATTERN, text, re.IGNORECASE)
        if match:
            return ExtractionResult(
                field="ico",
                value=match.group(1),
                confidence=0.95,
                source="regex"
            )
        return None

    @classmethod
    def extract_dic(cls, text: str) -> Optional[ExtractionResult]:
        """Extract Czech VAT ID (DIČ)"""
        match = re.search(cls.DIC_PATTERN, text, re.IGNORECASE)
        if match:
            return ExtractionResult(
                field="dic",
                value=match.group(1),
                confidence=0.95,
                source="regex"
            )
        return None


# =============================================================================
# LLM EXTRACTOR (Escalation for complex cases)
# =============================================================================

class LLMExtractor:
    """LLM-based extraction - escalation when regex fails"""

    def __init__(self, ollama_url: str = None, model: str = None):
        self.ollama_url = ollama_url
        self.model = model
        self._discover_server()

    def _discover_server(self):
        """Auto-discover available Ollama server and model"""
        if self.ollama_url and self.model:
            return

        for server in sorted(OllamaConfig.SERVERS, key=lambda x: x["priority"]):
            try:
                resp = requests.get(f"{server['url']}/api/tags", timeout=5)
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]

                    for preferred in OllamaConfig.PREFERRED_MODELS:
                        if any(preferred in m for m in models):
                            self.ollama_url = server["url"]
                            self.model = next(m for m in models if preferred in m)
                            print(f"Using Ollama: {server['name']} with model {self.model}")
                            return
            except:
                continue

        raise RuntimeError("No Ollama server available")

    def extract_date(self, text: str) -> Optional[ExtractionResult]:
        """Extract date using LLM"""
        prompt = f"""Analyze this document and extract the document date.
Return ONLY the date in ISO format (YYYY-MM-DD).
If no clear date found, return "null".

Document text (first 1500 chars):
{text[:1500]}

Date (ISO format only):"""

        response = self._query_ollama(prompt)
        if response:
            match = re.search(r'(\d{4}-\d{2}-\d{2})', response)
            if match:
                return ExtractionResult(
                    field="date",
                    value=match.group(1),
                    confidence=0.75,
                    source="llm_escalated",
                    model_used=self.model
                )
        return None

    def extract_correspondent(self, text: str) -> Optional[ExtractionResult]:
        """Extract sender/company name using LLM"""
        prompt = f"""Analyze this document and identify the sender or issuing company.
Return ONLY the company/person name, nothing else.
If it's an email, extract the sender. If it's an invoice, extract the vendor.

Document text (first 1500 chars):
{text[:1500]}

Sender/Company name:"""

        response = self._query_ollama(prompt)
        if response and len(response.strip()) > 2:
            name = response.strip().split('\n')[0][:100]
            if name and name.lower() != "null":
                return ExtractionResult(
                    field="correspondent",
                    value=name,
                    confidence=0.7,
                    source="llm_escalated",
                    model_used=self.model
                )
        return None

    def extract_document_type(self, text: str) -> Optional[ExtractionResult]:
        """Classify document type using LLM"""
        prompt = f"""Classify this document into ONE of these categories:
- invoice (faktura)
- receipt (účtenka/paragon)
- order (objednávka)
- contract (smlouva)
- bank_statement (bankovní výpis)
- notification (oznámení/upomínka)
- marketing (reklama/newsletter)
- personal (osobní korespondence)
- other

Return ONLY the category name in English.

Document text (first 1500 chars):
{text[:1500]}

Category:"""

        response = self._query_ollama(prompt)
        if response:
            category = response.strip().lower().split('\n')[0].split()[0]
            valid_categories = ['invoice', 'receipt', 'order', 'contract',
                              'bank_statement', 'notification', 'marketing',
                              'personal', 'other']
            if category in valid_categories:
                return ExtractionResult(
                    field="document_type",
                    value=category,
                    confidence=0.8,
                    source="llm_escalated",
                    model_used=self.model
                )
        return None

    def extract_all(self, text: str) -> Dict[str, ExtractionResult]:
        """Extract all metadata fields using a single LLM call"""
        prompt = f"""Analyze this document and extract the following information.
Return a JSON object with these fields:
- date: document date in YYYY-MM-DD format (or null)
- correspondent: sender/company name (or null)
- amount: total amount as number (or null)
- document_type: one of [invoice, receipt, order, contract, bank_statement, notification, marketing, personal, other]
- ico: Czech company ID - 8 digits (or null)
- dic: Czech VAT ID like CZ12345678 (or null)

Document text:
{text[:2000]}

JSON:"""

        response = self._query_ollama(prompt)
        results = {}

        if response:
            try:
                json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())

                    for field in ['date', 'correspondent', 'amount', 'document_type', 'ico', 'dic']:
                        if data.get(field) and data[field] != 'null':
                            results[field] = ExtractionResult(
                                field=field,
                                value=data[field],
                                confidence=0.7,
                                source="llm_escalated",
                                model_used=self.model
                            )
            except json.JSONDecodeError:
                pass

        return results

    def _query_ollama(self, prompt: str) -> Optional[str]:
        """Query Ollama API"""
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 200,
                    }
                },
                timeout=OllamaConfig.TIMEOUT
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
        except Exception as e:
            print(f"LLM query error: {e}")
        return None


# =============================================================================
# ISDOC XML GENERATOR (Czech Electronic Invoice Standard 6.0.2)
# =============================================================================

@dataclass
class ISDOCInvoiceData:
    """Data structure for ISDOC invoice"""
    # Document identification
    document_id: str = ""           # Unique document ID (UUID)
    invoice_number: str = ""        # Číslo faktury
    issue_date: str = ""            # Datum vystavení (YYYY-MM-DD)
    due_date: str = ""              # Datum splatnosti
    tax_point_date: str = ""        # Datum zdanitelného plnění

    # Supplier (Dodavatel)
    supplier_name: str = ""
    supplier_ico: str = ""          # IČO
    supplier_dic: str = ""          # DIČ
    supplier_street: str = ""
    supplier_city: str = ""
    supplier_postal_code: str = ""
    supplier_country: str = "CZ"
    supplier_bank_account: str = ""

    # Customer (Odběratel)
    customer_name: str = ""
    customer_ico: str = ""
    customer_dic: str = ""
    customer_street: str = ""
    customer_city: str = ""
    customer_postal_code: str = ""
    customer_country: str = "CZ"

    # Amounts
    total_without_vat: float = 0.0  # Celkem bez DPH
    vat_amount: float = 0.0         # DPH
    total_with_vat: float = 0.0     # Celkem s DPH
    currency: str = "CZK"

    # Payment
    variable_symbol: str = ""       # Variabilní symbol
    payment_method: str = "42"      # 42 = bank transfer

    # Line items
    line_items: List[Dict] = field(default_factory=list)

    # Source info
    original_filename: str = ""
    extraction_source: str = ""     # "regex" or "llm"


class ISDOCGenerator:
    """
    Generator for ISDOC 6.0.2 XML format
    https://isdoc.cz/6.0.2/xsd/isdoc-invoice-6.0.2.xsd
    """

    ISDOC_NS = "http://isdoc.cz/namespace/2013"
    XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
    SCHEMA_LOCATION = "http://isdoc.cz/namespace/2013 http://isdoc.cz/6.0.2/xsd/isdoc-invoice-6.0.2.xsd"

    # Document type codes
    DOC_TYPE_INVOICE = "1"        # Faktura
    DOC_TYPE_CREDIT_NOTE = "2"    # Dobropis
    DOC_TYPE_DEBIT_NOTE = "3"     # Vrubopis
    DOC_TYPE_PROFORMA = "4"       # Zálohová faktura

    def __init__(self, extractor: 'MetadataExtractor' = None):
        self.extractor = extractor

    def extract_invoice_data(self, text: str, filename: str = "") -> ISDOCInvoiceData:
        """
        Extract invoice data from document text using regex + LLM escalation
        """
        data = ISDOCInvoiceData()
        data.document_id = str(uuid.uuid4())
        data.original_filename = filename

        # Use regex extractors first
        date_result = RegexExtractor.extract_date(text)
        if date_result:
            data.issue_date = date_result.value
            data.tax_point_date = date_result.value
            data.extraction_source = "regex"

        amount_result = RegexExtractor.extract_amount(text)
        if amount_result:
            data.total_with_vat = amount_result.value
            # Estimate VAT (assume 21%)
            data.vat_amount = round(data.total_with_vat * 0.21 / 1.21, 2)
            data.total_without_vat = round(data.total_with_vat - data.vat_amount, 2)

        ico_result = RegexExtractor.extract_ico(text)
        if ico_result:
            data.supplier_ico = ico_result.value

        dic_result = RegexExtractor.extract_dic(text)
        if dic_result:
            data.supplier_dic = dic_result.value

        # Extract invoice number
        invoice_match = re.search(r'(?:Faktura|Invoice|Č\.|č\.|Nr\.|No\.)[:\s#]*(\d{4,}[-/]?\d*)', text, re.IGNORECASE)
        if invoice_match:
            data.invoice_number = invoice_match.group(1)

        # Extract variable symbol
        vs_match = re.search(r'(?:VS|V\.S\.|Var\.?\s*sym\.?)[:\s]*(\d{4,})', text, re.IGNORECASE)
        if vs_match:
            data.variable_symbol = vs_match.group(1)
        elif data.invoice_number:
            data.variable_symbol = re.sub(r'[^\d]', '', data.invoice_number)[:10]

        # Extract bank account
        bank_match = re.search(r'(\d{6,10})/(\d{4})', text)
        if bank_match:
            data.supplier_bank_account = f"{bank_match.group(1)}/{bank_match.group(2)}"

        # Use LLM for correspondent/supplier name if extractor available
        if self.extractor and self.extractor.use_llm and self.extractor.llm:
            correspondent = self.extractor.llm.extract_correspondent(text)
            if correspondent:
                data.supplier_name = correspondent.value
                data.extraction_source = "llm_escalated"

        # Fallback: try to extract company name from text
        if not data.supplier_name:
            company_patterns = [
                r'(?:Dodavatel|Supplier|Firma)[:\s]*([A-ZÁ-Ž][^\n,]{3,50})',
                r'([A-ZÁ-Ž][a-záčďéěíňóřšťúůýž\s]+(?:s\.r\.o\.|a\.s\.|spol\.))',
            ]
            for pattern in company_patterns:
                match = re.search(pattern, text)
                if match:
                    data.supplier_name = match.group(1).strip()[:100]
                    break

        return data

    def generate_xml(self, data: ISDOCInvoiceData) -> str:
        """
        Generate ISDOC 6.0.2 compliant XML
        """
        # Create root element with namespaces
        root = ET.Element("Invoice")
        root.set("xmlns", self.ISDOC_NS)
        root.set("xmlns:xsi", self.XSI_NS)
        root.set("xsi:schemaLocation", self.SCHEMA_LOCATION)
        root.set("version", "6.0.2")

        # Document type (1 = Invoice)
        ET.SubElement(root, "DocumentType").text = self.DOC_TYPE_INVOICE

        # Document ID
        ET.SubElement(root, "ID").text = data.invoice_number or data.document_id
        ET.SubElement(root, "UUID").text = data.document_id

        # Issue date
        if data.issue_date:
            ET.SubElement(root, "IssueDate").text = data.issue_date

        # Tax point date
        if data.tax_point_date:
            ET.SubElement(root, "TaxPointDate").text = data.tax_point_date

        # Due date
        if data.due_date:
            ET.SubElement(root, "VATApplicable").text = "true"

        # Currency
        ET.SubElement(root, "LocalCurrencyCode").text = data.currency
        ET.SubElement(root, "CurrRate").text = "1"
        ET.SubElement(root, "RefCurrRate").text = "1"

        # Accounting supplier (Dodavatel)
        supplier = ET.SubElement(root, "AccountingSupplierParty")
        party = ET.SubElement(supplier, "Party")

        if data.supplier_name:
            pname = ET.SubElement(party, "PartyName")
            ET.SubElement(pname, "Name").text = data.supplier_name

        if data.supplier_ico:
            pid = ET.SubElement(party, "PartyIdentification")
            ET.SubElement(pid, "ID").text = data.supplier_ico

        if data.supplier_dic:
            taxscheme = ET.SubElement(party, "PartyTaxScheme")
            ET.SubElement(taxscheme, "CompanyID").text = data.supplier_dic
            scheme = ET.SubElement(taxscheme, "TaxScheme")
            ET.SubElement(scheme, "ID").text = "VAT"

        if data.supplier_street or data.supplier_city:
            address = ET.SubElement(party, "PostalAddress")
            if data.supplier_street:
                ET.SubElement(address, "StreetName").text = data.supplier_street
            if data.supplier_city:
                ET.SubElement(address, "CityName").text = data.supplier_city
            if data.supplier_postal_code:
                ET.SubElement(address, "PostalZone").text = data.supplier_postal_code
            country = ET.SubElement(address, "Country")
            ET.SubElement(country, "IdentificationCode").text = data.supplier_country

        # Accounting customer (Odběratel) - if available
        if data.customer_name or data.customer_ico:
            customer = ET.SubElement(root, "AccountingCustomerParty")
            cparty = ET.SubElement(customer, "Party")

            if data.customer_name:
                cpname = ET.SubElement(cparty, "PartyName")
                ET.SubElement(cpname, "Name").text = data.customer_name

            if data.customer_ico:
                cpid = ET.SubElement(cparty, "PartyIdentification")
                ET.SubElement(cpid, "ID").text = data.customer_ico

        # Payment means
        payment = ET.SubElement(root, "PaymentMeans")
        ET.SubElement(payment, "PaymentMeansCode").text = data.payment_method

        if data.variable_symbol:
            pmid = ET.SubElement(payment, "PaymentID")
            ET.SubElement(pmid, "ID").text = data.variable_symbol

        if data.supplier_bank_account:
            account = ET.SubElement(payment, "PayeeFinancialAccount")
            ET.SubElement(account, "ID").text = data.supplier_bank_account

        # Tax total
        if data.vat_amount > 0:
            tax_total = ET.SubElement(root, "TaxTotal")
            ET.SubElement(tax_total, "TaxAmount").text = f"{data.vat_amount:.2f}"

            tax_subtotal = ET.SubElement(tax_total, "TaxSubTotal")
            ET.SubElement(tax_subtotal, "TaxableAmount").text = f"{data.total_without_vat:.2f}"
            ET.SubElement(tax_subtotal, "TaxAmount").text = f"{data.vat_amount:.2f}"

            tax_category = ET.SubElement(tax_subtotal, "TaxCategory")
            ET.SubElement(tax_category, "Percent").text = "21"

        # Legal monetary total
        monetary = ET.SubElement(root, "LegalMonetaryTotal")
        ET.SubElement(monetary, "TaxExclusiveAmount").text = f"{data.total_without_vat:.2f}"
        ET.SubElement(monetary, "TaxInclusiveAmount").text = f"{data.total_with_vat:.2f}"
        ET.SubElement(monetary, "AlreadyClaimedTaxExclusiveAmount").text = "0.00"
        ET.SubElement(monetary, "AlreadyClaimedTaxInclusiveAmount").text = "0.00"
        ET.SubElement(monetary, "DifferenceTaxExclusiveAmount").text = f"{data.total_without_vat:.2f}"
        ET.SubElement(monetary, "DifferenceTaxInclusiveAmount").text = f"{data.total_with_vat:.2f}"
        ET.SubElement(monetary, "PayableRoundingAmount").text = "0.00"
        ET.SubElement(monetary, "PaidDepositsAmount").text = "0.00"
        ET.SubElement(monetary, "PayableAmount").text = f"{data.total_with_vat:.2f}"

        # Invoice lines (minimal if no items extracted)
        if not data.line_items:
            # Create single summary line
            data.line_items = [{
                "description": f"Položka z {data.original_filename}" if data.original_filename else "Položka faktury",
                "quantity": 1,
                "unit_price": data.total_without_vat,
                "vat_rate": 21
            }]

        for i, item in enumerate(data.line_items, 1):
            line = ET.SubElement(root, "InvoiceLine")
            ET.SubElement(line, "ID").text = str(i)

            quantity = ET.SubElement(line, "InvoicedQuantity")
            quantity.text = str(item.get("quantity", 1))
            quantity.set("unitCode", "C62")  # Unit

            ET.SubElement(line, "LineExtensionAmount").text = f"{item.get('unit_price', 0):.2f}"
            ET.SubElement(line, "LineExtensionAmountTaxInclusive").text = f"{item.get('unit_price', 0) * 1.21:.2f}"

            line_item = ET.SubElement(line, "Item")
            ET.SubElement(line_item, "Description").text = item.get("description", "")[:256]

        # Convert to pretty XML
        xml_str = ET.tostring(root, encoding='unicode')
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ", encoding=None)

    def generate_from_text(self, text: str, filename: str = "") -> str:
        """
        Extract data from text and generate ISDOC XML
        """
        data = self.extract_invoice_data(text, filename)
        return self.generate_xml(data)

    def save_isdoc(self, xml_content: str, output_path: str) -> str:
        """
        Save ISDOC XML to file
        """
        # Remove XML declaration duplicate if present
        if xml_content.startswith('<?xml'):
            # Keep only one declaration
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + \
                         '\n'.join(xml_content.split('\n')[1:])
        else:
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        return output_path


# =============================================================================
# UNIFIED EXTRACTOR WITH ESCALATION
# =============================================================================

class MetadataExtractor:
    """
    Unified metadata extractor with escalation strategy:
    1. Try fast regex extraction
    2. If fails or low confidence, escalate to LLM
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.llm = None
        if use_llm:
            try:
                self.llm = LLMExtractor()
            except Exception as e:
                print(f"LLM not available: {e}")
                self.use_llm = False

    def extract(self, text: str, fields: List[str] = None) -> Dict[str, ExtractionResult]:
        """
        Extract metadata from document text.

        Args:
            text: Document content
            fields: List of fields to extract (default: all)

        Returns:
            Dictionary of field -> ExtractionResult
        """
        if fields is None:
            fields = ['date', 'correspondent', 'amount', 'document_type', 'ico', 'dic']

        results = {}
        llm_needed = []

        # Step 1: Try regex extraction first
        for field in fields:
            result = None

            if field == 'date':
                result = RegexExtractor.extract_date(text)
            elif field == 'amount':
                result = RegexExtractor.extract_amount(text)
            elif field == 'ico':
                result = RegexExtractor.extract_ico(text)
            elif field == 'dic':
                result = RegexExtractor.extract_dic(text)

            if result:
                results[field] = result
            else:
                llm_needed.append(field)

        # Step 2: Escalate to LLM for failed/missing fields
        if llm_needed and self.use_llm and self.llm:
            print(f"  Escalating to LLM for: {llm_needed}")

            if len(llm_needed) >= 3:
                llm_results = self.llm.extract_all(text)
                for field, result in llm_results.items():
                    if field in llm_needed:
                        results[field] = result
            else:
                for field in llm_needed:
                    if field == 'date':
                        result = self.llm.extract_date(text)
                    elif field == 'correspondent':
                        result = self.llm.extract_correspondent(text)
                    elif field == 'document_type':
                        result = self.llm.extract_document_type(text)
                    else:
                        continue

                    if result:
                        results[field] = result

        return results


# =============================================================================
# PAPERLESS-NGX INTEGRATION
# =============================================================================

def process_paperless_documents(limit: int = 100, dry_run: bool = True):
    """
    Process documents in Paperless-NGX and update metadata.
    Must run inside Paperless container.
    """
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
        django.setup()
        from documents.models import Document, Correspondent
    except ImportError:
        print("Error: Must run inside Paperless container")
        print("Usage: docker exec -it paperless-ngx python /path/llm_metadata_extractor.py --mode paperless")
        return

    extractor = MetadataExtractor(use_llm=True)

    # Find documents without correspondent
    docs = Document.objects.filter(correspondent__isnull=True)[:limit]
    print(f"Processing {docs.count()} documents without correspondent...")

    updated = 0
    for doc in docs:
        if not doc.content:
            continue

        print(f"\nDoc {doc.id}: {doc.original_filename[:50]}")

        results = extractor.extract(doc.content)

        for field, result in results.items():
            print(f"  {field}: {result.value} ({result.source})")

        if not dry_run and 'correspondent' in results:
            name = results['correspondent'].value
            correspondent, _ = Correspondent.objects.get_or_create(name=name[:128])
            doc.correspondent = correspondent
            doc.save(update_fields=['correspondent'])
            updated += 1

    print(f"\n{'Would update' if dry_run else 'Updated'} {updated} documents")


# =============================================================================
# ISDOC PAPERLESS INTEGRATION
# =============================================================================

def generate_isdoc_for_paperless_documents(limit: int = 100, output_dir: str = None, dry_run: bool = True):
    """
    Generate ISDOC XML files for accounting documents in Paperless-NGX.
    Must run inside Paperless container or provide API access.
    """
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
        django.setup()
        from documents.models import Document, DocumentType
    except ImportError:
        print("Error: Must run inside Paperless container")
        print("Usage: docker exec -it paperless-ngx python /path/llm_metadata_extractor.py --mode isdoc")
        return

    # Setup output directory
    if output_dir is None:
        output_dir = "/usr/src/paperless/media/isdoc"
    os.makedirs(output_dir, exist_ok=True)

    # Initialize extractor and ISDOC generator
    extractor = MetadataExtractor(use_llm=True)
    isdoc_gen = ISDOCGenerator(extractor)

    # Find accounting documents (invoices, receipts)
    # Try to filter by document type if available
    accounting_types = ['invoice', 'faktura', 'receipt', 'účtenka', 'dobropis', 'credit']

    docs = Document.objects.all()

    # Filter by document type if exists
    try:
        type_ids = DocumentType.objects.filter(
            name__iregex=r'|'.join(accounting_types)
        ).values_list('id', flat=True)
        if type_ids:
            docs = docs.filter(document_type_id__in=type_ids)
    except:
        pass

    # Also check content for invoice patterns
    docs = docs.filter(
        content__iregex=r'(faktura|invoice|účtenka|receipt|IČO|DIČ|celkem|total)'
    )[:limit]

    print(f"Processing {docs.count()} accounting documents...")
    generated = 0
    errors = 0

    for doc in docs:
        if not doc.content:
            continue

        print(f"\nDoc {doc.id}: {doc.original_filename[:50]}")

        try:
            # Generate ISDOC XML
            xml_content = isdoc_gen.generate_from_text(doc.content, doc.original_filename)

            # Create output filename
            base_name = os.path.splitext(doc.original_filename)[0]
            isdoc_filename = f"{base_name}_{doc.id}.isdoc"
            isdoc_path = os.path.join(output_dir, isdoc_filename)

            if dry_run:
                print(f"  Would generate: {isdoc_filename}")
                # Show extracted data
                data = isdoc_gen.extract_invoice_data(doc.content, doc.original_filename)
                print(f"    Invoice: {data.invoice_number or 'N/A'}")
                print(f"    Supplier: {data.supplier_name or 'N/A'}")
                print(f"    IČO: {data.supplier_ico or 'N/A'}")
                print(f"    Amount: {data.total_with_vat:.2f} {data.currency}")
            else:
                isdoc_gen.save_isdoc(xml_content, isdoc_path)
                print(f"  Generated: {isdoc_filename}")
                generated += 1

        except Exception as e:
            print(f"  Error: {e}")
            errors += 1

    print(f"\n{'Would generate' if dry_run else 'Generated'} {generated} ISDOC files")
    print(f"Errors: {errors}")
    print(f"Output directory: {output_dir}")


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM Metadata Extractor + ISDOC Generator")
    parser.add_argument("--mode", choices=["test", "paperless", "isdoc", "isdoc-test"],
                       default="test", help="Operation mode")
    parser.add_argument("--limit", type=int, default=10, help="Document limit")
    parser.add_argument("--apply", action="store_true", help="Apply changes (not dry-run)")
    parser.add_argument("--output", type=str, default=None, help="Output directory for ISDOC files")

    args = parser.parse_args()

    if args.mode == "test":
        sample_text = """
        Subject: Faktura 2024-001234
        From: "Firma ABC s.r.o." <info@abc.cz>
        Date: 5/12/25, 1:30 PM

        FAKTURA č. 2024-001234
        Datum vystavení: 12. května 2025

        Dodavatel:
        Firma ABC s.r.o.
        IČO: 12345678
        DIČ: CZ12345678

        Celkem k úhradě: 1 234,56 Kč
        """

        print("Testing extraction on sample text...")
        extractor = MetadataExtractor(use_llm=True)
        results = extractor.extract(sample_text)

        print("\nResults:")
        for field, result in results.items():
            print(f"  {field}: {result.value}")
            print(f"    Source: {result.source}, Confidence: {result.confidence}")
            if result.model_used:
                print(f"    Model: {result.model_used}")

    elif args.mode == "isdoc-test":
        # Test ISDOC generation without Paperless
        sample_text = """
        FAKTURA č. 2024-001234
        Datum vystavení: 12. 5. 2024
        Datum splatnosti: 26. 5. 2024

        Dodavatel:
        Firma ABC s.r.o.
        Ulice 123
        Praha 1, 110 00
        IČO: 12345678
        DIČ: CZ12345678
        Účet: 1234567890/0100

        Odběratel:
        Zákazník XYZ a.s.
        Jiná ulice 456
        Brno, 602 00
        IČO: 87654321

        Položky:
        1. Služba A          10 000,00 Kč
        2. Služba B           5 000,00 Kč

        Základ DPH:          15 000,00 Kč
        DPH 21%:              3 150,00 Kč
        Celkem k úhradě:     18 150,00 Kč

        VS: 2024001234
        """

        print("Testing ISDOC generation on sample invoice...")
        extractor = MetadataExtractor(use_llm=False)  # Regex only for test
        isdoc_gen = ISDOCGenerator(extractor)

        # Extract data
        data = isdoc_gen.extract_invoice_data(sample_text, "test_invoice.pdf")

        print("\nExtracted data:")
        print(f"  Invoice number: {data.invoice_number}")
        print(f"  Issue date: {data.issue_date}")
        print(f"  Supplier: {data.supplier_name}")
        print(f"  Supplier IČO: {data.supplier_ico}")
        print(f"  Supplier DIČ: {data.supplier_dic}")
        print(f"  Bank account: {data.supplier_bank_account}")
        print(f"  Variable symbol: {data.variable_symbol}")
        print(f"  Total with VAT: {data.total_with_vat:.2f} {data.currency}")
        print(f"  VAT amount: {data.vat_amount:.2f}")
        print(f"  Total without VAT: {data.total_without_vat:.2f}")

        # Generate XML
        xml = isdoc_gen.generate_xml(data)

        print("\n" + "=" * 60)
        print("ISDOC XML Output:")
        print("=" * 60)
        print(xml[:2000])  # First 2000 chars
        if len(xml) > 2000:
            print("...[truncated]...")

        # Save to file if output specified
        if args.output:
            output_path = os.path.join(args.output, "test_invoice.isdoc")
            os.makedirs(args.output, exist_ok=True)
            isdoc_gen.save_isdoc(xml, output_path)
            print(f"\nSaved to: {output_path}")

    elif args.mode == "paperless":
        process_paperless_documents(limit=args.limit, dry_run=not args.apply)

    elif args.mode == "isdoc":
        generate_isdoc_for_paperless_documents(
            limit=args.limit,
            output_dir=args.output,
            dry_run=not args.apply
        )
