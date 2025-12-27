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
Structured Data Extractors v1.0
Extracts line-by-line structured data from business documents

Supported Documents:
- Invoices: ALL line items with description, quantity, price, VAT per row
- Bank Statements: ALL transactions with counterparty, amount, symbols
- Receipts: ALL items with prices, VAT rates, EET codes

Author: Claude Code
Date: 2025-11-30
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class DataExtractorBase:
    """Base class for all data extractors with common utilities"""

    # Common regex patterns
    RE_AMOUNT = re.compile(r'(\d[\d\s]*[,\.]\d{2})')
    RE_DATE = re.compile(r'\b(\d{1,2})[\./-](\d{1,2})[\./-](\d{2,4})\b')
    RE_PERCENTAGE = re.compile(r'(\d{1,2})\s*%')
    RE_QUANTITY = re.compile(r'(\d+(?:[,\.]\d+)?)\s*(?:ks|pcs|x)?', re.I)

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def parse_amount(self, text: str) -> Optional[Decimal]:
        """Parse amount from text (handles CZ and EN formats)"""
        if not text:
            return None

        try:
            # Remove whitespace
            text = text.strip().replace(' ', '')

            # Handle Czech format (1 234,56)
            if ',' in text and '.' not in text:
                text = text.replace(',', '.')
            # Handle thousands separator (1.234,56 or 1,234.56)
            elif ',' in text and '.' in text:
                # Determine which is decimal separator
                comma_pos = text.rfind(',')
                dot_pos = text.rfind('.')
                if comma_pos > dot_pos:  # Czech: 1.234,56
                    text = text.replace('.', '').replace(',', '.')
                else:  # English: 1,234.56
                    text = text.replace(',', '')

            return Decimal(text)
        except (InvalidOperation, ValueError) as e:
            self.logger.warning(f"Failed to parse amount '{text}': {e}")
            return None

    def parse_date(self, text: str) -> Optional[str]:
        """Parse date from text, returns YYYY-MM-DD"""
        match = self.RE_DATE.search(text)
        if not match:
            return None

        day, month, year = match.groups()

        # Handle 2-digit years
        if len(year) == 2:
            year = f"20{year}" if int(year) < 50 else f"19{year}"

        try:
            date_obj = datetime(int(year), int(month), int(day))
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            return None

    def extract_bounding_boxes(self, ocr_data: Dict) -> List[Dict]:
        """Extract bounding boxes from OCR data"""
        if not ocr_data or 'text' not in ocr_data:
            return []

        boxes = []
        n_boxes = len(ocr_data['text'])

        for i in range(n_boxes):
            if int(ocr_data['conf'][i]) > 0:  # Skip low confidence
                boxes.append({
                    'text': ocr_data['text'][i],
                    'conf': int(ocr_data['conf'][i]),
                    'left': ocr_data['left'][i],
                    'top': ocr_data['top'][i],
                    'width': ocr_data['width'][i],
                    'height': ocr_data['height'][i]
                })

        return boxes


class InvoiceExtractor(DataExtractorBase):
    """
    Extracts ALL line items from invoices

    Output format:
    {
        "line_items": [
            {
                "line_number": 1,
                "description": "ChatGPT Plus API - November 2024",
                "quantity": 1.0,
                "unit": "ks",
                "unit_price": 150.00,
                "vat_rate": 21,
                "vat_amount": 31.50,
                "total_net": 150.00,
                "total_gross": 181.50
            }
        ],
        "summary": {
            "total_net": 150.00,
            "total_vat": 31.50,
            "total_gross": 181.50,
            "currency": "CZK"
        }
    }
    """

    # Invoice-specific patterns
    RE_LINE_NUMBER = re.compile(r'^\s*(\d+)[\s\.]')
    RE_ITEM_CODE = re.compile(r'\b([A-Z0-9]{3,})\b')
    RE_VAT_RATE = re.compile(r'(?:DPH|VAT)\s*(\d{1,2})\s*%', re.I)

    # NEW v1.1: Subject extraction patterns
    RE_SUBJECT = re.compile(r'(?:předmět|subject|popis|description)[\s:]+(.+)', re.I)
    RE_ISDOC = re.compile(r'<\?xml.*?ISDOC|isdoc.*?version|xmlns.*?isdoc', re.I | re.DOTALL)
    RE_ISDOC_VERSION = re.compile(r'version=["\']?(\d+\.\d+\.?\d*)["\']?', re.I)
    RE_ISDOC_UUID = re.compile(r'<ID>([a-f0-9\-]{36})</ID>', re.I)

    # NEW v1.1: Service vs Goods detection keywords
    SERVICE_KEYWORDS = [
        'služba', 'služby', 'service', 'services', 'práce', 'work',
        'poradenství', 'consulting', 'podpora', 'support', 'údržba',
        'maintenance', 'licence', 'license', 'předplatné', 'subscription',
        'pronájem', 'rental', 'hosting', 'api', 'software', 'saas',
        'měsíční', 'monthly', 'roční', 'yearly', 'annual'
    ]
    GOODS_KEYWORDS = [
        'zboží', 'goods', 'materiál', 'material', 'produkt', 'product',
        'výrobek', 'item', 'kus', 'ks', 'pcs', 'balení', 'package',
        'hardware', 'přístroj', 'device', 'součástka', 'component',
        'náhradní díl', 'spare part', 'spotřební', 'consumable'
    ]

    # Table section markers
    TABLE_START_MARKERS = [
        'položky', 'items', 'popis', 'description',
        'množství', 'quantity', 'cena', 'price'
    ]
    TABLE_END_MARKERS = [
        'celkem', 'total', 'suma', 'mezisoučet', 'subtotal',
        'k úhradě', 'to pay', 'způsob platby', 'payment method'
    ]

    def extract(self, text: str, ocr_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Extract all invoice line items with subject, item_type, and ISDOC detection"""
        try:
            # Find table region
            table_region = self._find_table_region(text, ocr_data)

            if not table_region:
                self.logger.warning("No table region found in invoice")
                return self._empty_result()

            # Extract rows
            rows = self._extract_table_rows(table_region, ocr_data)

            # Parse line items
            line_items = []
            for idx, row_text in enumerate(rows, 1):
                item = self._parse_line_item(idx, row_text)
                if item:
                    # NEW v1.1: Detect item type per line
                    item['item_type'] = self._detect_item_type(item.get('description', ''))
                    line_items.append(item)

            # Calculate summary
            summary = self._calculate_summary(line_items)

            # NEW v1.1: Extract invoice subject
            subject = self._extract_subject(text, line_items)

            # NEW v1.1: Determine overall item type
            item_type = self._determine_overall_item_type(line_items)

            # NEW v1.1: Detect ISDOC
            isdoc_info = self._detect_isdoc(text)

            result = {
                'line_items': line_items,
                'summary': summary,
                'extraction_confidence': self._calculate_confidence(line_items, text)
            }

            # Add new fields if detected
            if subject:
                result['subject'] = subject
            if item_type:
                result['item_type'] = item_type
            if isdoc_info.get('is_isdoc'):
                result['isdoc'] = isdoc_info

            return result

        except Exception as e:
            self.logger.error(f"Invoice extraction failed: {e}")
            return self._empty_result()

    def _extract_subject(self, text: str, line_items: List[Dict]) -> Optional[str]:
        """NEW v1.1: Extract invoice subject (předmět faktury)"""
        # Try to find explicit subject line
        match = self.RE_SUBJECT.search(text)
        if match:
            subject = match.group(1).strip()
            if len(subject) > 5:  # Reasonable subject
                return subject[:200]  # Limit length

        # Fallback: Generate from line items
        if line_items:
            descriptions = [item.get('description', '') for item in line_items[:3]]
            descriptions = [d for d in descriptions if d]
            if descriptions:
                if len(descriptions) == 1:
                    return descriptions[0][:200]
                else:
                    return f"{descriptions[0][:100]} a další ({len(line_items)} položek)"

        return None

    def _detect_item_type(self, description: str) -> str:
        """NEW v1.1: Detect if item is service or goods"""
        desc_lower = description.lower()

        service_score = sum(1 for kw in self.SERVICE_KEYWORDS if kw in desc_lower)
        goods_score = sum(1 for kw in self.GOODS_KEYWORDS if kw in desc_lower)

        if service_score > goods_score:
            return 'service'
        elif goods_score > service_score:
            return 'goods'
        else:
            return 'goods'  # Default to goods if unclear

    def _determine_overall_item_type(self, line_items: List[Dict]) -> str:
        """NEW v1.1: Determine overall invoice item type"""
        if not line_items:
            return 'mixed'

        types = [item.get('item_type', 'goods') for item in line_items]
        services = types.count('service')
        goods = types.count('goods')

        if services > 0 and goods > 0:
            return 'mixed'
        elif services > 0:
            return 'service'
        else:
            return 'goods'

    def _detect_isdoc(self, text: str) -> Dict[str, Any]:
        """NEW v1.1: Detect ISDOC XML in document"""
        result = {'is_isdoc': False}

        if self.RE_ISDOC.search(text):
            result['is_isdoc'] = True

            # Extract version
            version_match = self.RE_ISDOC_VERSION.search(text)
            if version_match:
                result['version'] = version_match.group(1)

            # Extract UUID
            uuid_match = self.RE_ISDOC_UUID.search(text)
            if uuid_match:
                result['uuid'] = uuid_match.group(1)

        return result

    def _find_table_region(self, text: str, ocr_data: Optional[Dict]) -> Optional[str]:
        """Find the table region in invoice text - IMPROVED VERSION"""
        lines = text.split('\n')

        start_idx = None
        end_idx = None

        # IMPROVED: Look for separator lines (===, ---, ======)
        separator_pattern = re.compile(r'^[\s\-=]{10,}$')

        # Strategy 1: Find "Položky:" or "Items:" keyword
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(marker in line_lower for marker in self.TABLE_START_MARKERS):
                start_idx = i
                self.logger.debug(f"Found table start marker at line {i}: {line[:40]}")
                break

        # Strategy 2: Find by table headers if not found
        if start_idx is None:
            for i, line in enumerate(lines):
                line_lower = line.lower()
                # Count how many table-related keywords are in this line
                header_keywords = ['položky', 'items', 'popis', 'description', 'množství', 'quantity', 'cena', 'price', 'č.', 'dph', 'vat']
                keyword_count = sum(1 for kw in header_keywords if kw in line_lower)

                if keyword_count >= 3:  # If 3+ keywords, likely a header
                    start_idx = i
                    self.logger.debug(f"Found table header at line {i}: {line[:40]}")
                    break

        if start_idx is None:
            self.logger.warning("Could not find table start")
            return None

        # Find table end - look for closing separator or end markers
        # Start searching from a few lines after start to skip header separators
        separator_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i].strip()
            line_lower = line.lower()

            # Count separators
            if separator_pattern.match(line):
                separator_count += 1
                # If we've seen at least 2 separators and find another one,
                # this is likely the closing separator
                if separator_count >= 2 and i > start_idx + 3:
                    end_idx = i + 1
                    self.logger.debug(f"Found closing separator at line {i}")
                    break

            # End markers (Celkem, Total, etc.)
            if i > start_idx + 3:  # Must be at least 3 lines after start
                if any(marker in line_lower for marker in self.TABLE_END_MARKERS):
                    end_idx = i
                    self.logger.debug(f"Found end marker at line {i}: {line[:40]}")
                    break

        if end_idx is None:
            end_idx = len(lines)

        # Extract table region
        table_text = '\n'.join(lines[start_idx:end_idx])
        self.logger.debug(f"Table region: lines {start_idx}-{end_idx} ({end_idx - start_idx} lines)")
        return table_text

    def _extract_table_rows(self, table_region: str, ocr_data: Optional[Dict]) -> List[str]:
        """Extract individual rows from table region - IMPROVED"""
        lines = table_region.split('\n')

        rows = []
        separator_pattern = re.compile(r'^[\s\-=]{10,}$')

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip separator lines
            if separator_pattern.match(line):
                continue

            # Skip header rows
            if self._is_header_row(line):
                continue

            # IMPROVED: Check multiple conditions for data rows
            is_data_row = False

            # 1. Has amounts (strongest indicator)
            if self.RE_AMOUNT.search(line):
                is_data_row = True

            # 2. Starts with line number (e.g. "1.", "2.", "3.")
            elif re.match(r'^\s*\d+\.', line):
                is_data_row = True

            # 3. Starts with number followed by space/tab (e.g. "1   Item", "2\tItem")
            elif re.match(r'^\s*\d+[\s\t]', line):
                is_data_row = True

            if is_data_row:
                rows.append(line)
                self.logger.debug(f"Found data row: {line[:60]}...")

        self.logger.info(f"Extracted {len(rows)} table rows")
        return rows

    def _is_header_row(self, line: str) -> bool:
        """Check if line is a table header"""
        line_lower = line.lower()
        header_keywords = [
            'položka', 'item', 'popis', 'description',
            'množství', 'quantity', 'cena', 'price',
            'dph', 'vat', 'celkem', 'total'
        ]

        # If line contains multiple header keywords, it's likely a header
        keyword_count = sum(1 for kw in header_keywords if kw in line_lower)
        return keyword_count >= 2

    def _parse_line_item(self, line_number: int, row_text: str) -> Optional[Dict]:
        """Parse single line item from row text"""
        try:
            # Extract all amounts from the row
            amounts = [self.parse_amount(m.group(1))
                      for m in self.RE_AMOUNT.finditer(row_text)]
            amounts = [a for a in amounts if a is not None]

            if not amounts:
                return None

            # Extract VAT rate
            vat_match = self.RE_VAT_RATE.search(row_text)
            vat_rate = int(vat_match.group(1)) if vat_match else 21  # Default 21%

            # Extract quantity
            qty_match = self.RE_QUANTITY.search(row_text)
            quantity = float(qty_match.group(1).replace(',', '.')) if qty_match else 1.0

            # Determine which amounts are which
            # Typical layouts:
            # - [quantity] [description] [unit_price] [total]
            # - [quantity] [description] [unit_price] [vat_rate] [total_net] [vat_amount] [total_gross]

            if len(amounts) >= 2:
                unit_price = amounts[0]
                total_gross = amounts[-1]

                # Calculate based on quantity
                total_net = unit_price * Decimal(str(quantity))
                vat_amount = total_net * Decimal(str(vat_rate)) / Decimal('100')

                # If we have 3+ amounts, middle ones might be net/vat breakdown
                if len(amounts) >= 3:
                    total_net = amounts[-2]
                    vat_amount = amounts[-1] - total_net
            else:
                # Only one amount - assume it's total gross
                total_gross = amounts[0]
                total_net = total_gross / (1 + Decimal(str(vat_rate)) / Decimal('100'))
                vat_amount = total_gross - total_net
                unit_price = total_net / Decimal(str(quantity))

            # Extract description (text before first amount)
            first_amount_pos = row_text.find(str(amounts[0]))
            description = row_text[:first_amount_pos].strip()

            # Clean up description (remove line numbers, item codes at start)
            description = re.sub(r'^\d+[\s\.]+', '', description)
            description = re.sub(r'^[A-Z0-9]{3,}\s+', '', description)

            return {
                'line_number': line_number,
                'description': description or f"Item {line_number}",
                'quantity': quantity,
                'unit': 'ks',
                'unit_price': float(unit_price),
                'vat_rate': vat_rate,
                'vat_amount': float(vat_amount),
                'total_net': float(total_net),
                'total_gross': float(total_gross)
            }

        except Exception as e:
            self.logger.error(f"Failed to parse line item: {e}")
            return None

    def _calculate_summary(self, line_items: List[Dict]) -> Dict[str, Any]:
        """Calculate invoice summary from line items"""
        if not line_items:
            return {
                'total_net': 0.0,
                'total_vat': 0.0,
                'total_gross': 0.0,
                'currency': 'CZK'
            }

        total_net = sum(item['total_net'] for item in line_items)
        total_vat = sum(item['vat_amount'] for item in line_items)
        total_gross = sum(item['total_gross'] for item in line_items)

        return {
            'total_net': round(total_net, 2),
            'total_vat': round(total_vat, 2),
            'total_gross': round(total_gross, 2),
            'currency': 'CZK'
        }

    def _calculate_confidence(self, line_items: List[Dict], text: str) -> float:
        """Calculate extraction confidence score"""
        if not line_items:
            return 0.0

        score = 50.0  # Base score

        # Boost for multiple items extracted
        score += min(len(line_items) * 5, 30)

        # Boost if we found VAT rates
        if any(item['vat_rate'] > 0 for item in line_items):
            score += 10

        # Boost if descriptions are not generic
        non_generic = sum(1 for item in line_items
                         if not item['description'].startswith('Item '))
        score += min(non_generic * 5, 10)

        return min(score, 100.0)

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'line_items': [],
            'summary': {
                'total_net': 0.0,
                'total_vat': 0.0,
                'total_gross': 0.0,
                'currency': 'CZK'
            },
            'extraction_confidence': 0.0
        }


class BankStatementExtractor(DataExtractorBase):
    """
    Extracts ALL transactions from bank statements

    Output format:
    {
        "transactions": [
            {
                "date": "2024-11-15",
                "type": "incoming",
                "amount": 5000.00,
                "currency": "CZK",
                "counterparty": "ACME Corp s.r.o.",
                "counterparty_account": "123456789/0100",
                "variable_symbol": "2024001",
                "constant_symbol": "0308",
                "specific_symbol": "",
                "description": "Faktura 2024001"
            }
        ],
        "summary": {
            "opening_balance": 10000.00,
            "closing_balance": 15000.00,
            "total_incoming": 5000.00,
            "total_outgoing": 0.00,
            "currency": "CZK"
        }
    }
    """

    # Transaction patterns
    RE_ACCOUNT = re.compile(r'(\d{2,16})[\s/]?(\d{4})')
    RE_VAR_SYMBOL = re.compile(r'VS\s*:?\s*(\d+)', re.I)
    RE_CONST_SYMBOL = re.compile(r'KS\s*:?\s*(\d{4})', re.I)
    RE_SPEC_SYMBOL = re.compile(r'SS\s*:?\s*(\d+)', re.I)

    # Balance patterns
    RE_OPENING_BALANCE = re.compile(r'(?:počáteční|starting|opening)\s+(?:zůstatek|balance)\s*:?\s*(\d[\d\s,\.]+)', re.I)
    RE_CLOSING_BALANCE = re.compile(r'(?:konečný|ending|closing)\s+(?:zůstatek|balance)\s*:?\s*(\d[\d\s,\.]+)', re.I)

    def extract(self, text: str, ocr_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Extract all transactions from bank statement"""
        try:
            # Find transaction region
            trans_region = self._find_transaction_region(text)

            if not trans_region:
                self.logger.warning("No transaction region found")
                return self._empty_result()

            # Extract transaction rows
            rows = self._extract_transaction_rows(trans_region)

            # Parse transactions
            transactions = []
            for row_text in rows:
                trans = self._parse_transaction(row_text)
                if trans:
                    transactions.append(trans)

            # Extract balances
            opening = self._extract_balance(text, self.RE_OPENING_BALANCE)
            closing = self._extract_balance(text, self.RE_CLOSING_BALANCE)

            # Calculate summary
            summary = self._calculate_summary(transactions, opening, closing)

            return {
                'transactions': transactions,
                'summary': summary,
                'extraction_confidence': self._calculate_confidence(transactions, text)
            }

        except Exception as e:
            self.logger.error(f"Bank statement extraction failed: {e}")
            return self._empty_result()

    def _find_transaction_region(self, text: str) -> Optional[str]:
        """Find transaction listing in statement"""
        lines = text.split('\n')

        # Look for transaction table headers
        header_keywords = ['datum', 'date', 'popis', 'description', 'částka', 'amount']

        start_idx = None
        for i, line in enumerate(lines):
            line_lower = line.lower()
            keyword_count = sum(1 for kw in header_keywords if kw in line_lower)
            if keyword_count >= 2:
                start_idx = i + 1  # Skip header line
                break

        if start_idx is None:
            return text  # No clear header, use whole text

        # Find end (usually before summary section)
        end_keywords = ['celkem', 'total', 'konečný zůstatek', 'closing balance']
        end_idx = len(lines)

        for i in range(start_idx, len(lines)):
            line_lower = lines[i].lower()
            if any(kw in line_lower for kw in end_keywords):
                end_idx = i
                break

        return '\n'.join(lines[start_idx:end_idx])

    def _extract_transaction_rows(self, trans_region: str) -> List[str]:
        """Extract individual transaction rows"""
        lines = trans_region.split('\n')

        rows = []
        current_row = []

        for line in lines:
            line = line.strip()
            if not line:
                if current_row:
                    rows.append(' '.join(current_row))
                    current_row = []
                continue

            # Check if line starts with date (beginning of new transaction)
            if self.RE_DATE.match(line):
                if current_row:
                    rows.append(' '.join(current_row))
                current_row = [line]
            else:
                # Continuation of previous transaction
                current_row.append(line)

        # Add last row
        if current_row:
            rows.append(' '.join(current_row))

        return rows

    def _parse_transaction(self, row_text: str) -> Optional[Dict]:
        """Parse single transaction from row text"""
        try:
            # Extract date
            date = self.parse_date(row_text)
            if not date:
                return None

            # Extract amounts (look for +/- indicators)
            amounts = []
            trans_type = 'unknown'

            # Look for amount with sign
            amount_pattern = re.compile(r'([+-]?)\s*(\d[\d\s]*[,\.]\d{2})')
            for match in amount_pattern.finditer(row_text):
                sign = match.group(1)
                amount_text = match.group(2)
                amount = self.parse_amount(amount_text)

                if amount:
                    if sign == '-':
                        trans_type = 'outgoing'
                        amount = -abs(amount)
                    elif sign == '+' or amount > 0:
                        trans_type = 'incoming'
                        amount = abs(amount)

                    amounts.append(amount)

            if not amounts:
                return None

            # Use the largest amount (usually the transaction amount)
            amount = max(amounts, key=abs)

            # Extract symbols
            var_symbol = self._extract_symbol(row_text, self.RE_VAR_SYMBOL)
            const_symbol = self._extract_symbol(row_text, self.RE_CONST_SYMBOL)
            spec_symbol = self._extract_symbol(row_text, self.RE_SPEC_SYMBOL)

            # Extract account number
            account_match = self.RE_ACCOUNT.search(row_text)
            counterparty_account = f"{account_match.group(1)}/{account_match.group(2)}" if account_match else ""

            # Extract counterparty and description
            # Usually the text between date and first amount
            date_str = date
            first_amount_pos = row_text.find(str(amounts[0]))
            middle_text = row_text[len(date_str):first_amount_pos].strip()

            # Split into counterparty and description
            parts = middle_text.split(maxsplit=3)
            counterparty = parts[0] if parts else ""
            description = ' '.join(parts[1:]) if len(parts) > 1 else middle_text

            return {
                'date': date,
                'type': trans_type,
                'amount': float(amount),
                'currency': 'CZK',
                'counterparty': counterparty,
                'counterparty_account': counterparty_account,
                'variable_symbol': var_symbol,
                'constant_symbol': const_symbol,
                'specific_symbol': spec_symbol,
                'description': description
            }

        except Exception as e:
            self.logger.error(f"Failed to parse transaction: {e}")
            return None

    def _extract_symbol(self, text: str, pattern: re.Pattern) -> str:
        """Extract payment symbol"""
        match = pattern.search(text)
        return match.group(1) if match else ""

    def _extract_balance(self, text: str, pattern: re.Pattern) -> Optional[float]:
        """Extract balance amount"""
        match = pattern.search(text)
        if match:
            amount = self.parse_amount(match.group(1))
            return float(amount) if amount else None
        return None

    def _calculate_summary(self, transactions: List[Dict],
                          opening: Optional[float],
                          closing: Optional[float]) -> Dict[str, Any]:
        """Calculate statement summary"""
        total_incoming = sum(t['amount'] for t in transactions if t['amount'] > 0)
        total_outgoing = sum(abs(t['amount']) for t in transactions if t['amount'] < 0)

        # If balances not found, calculate from transactions
        if opening is None and transactions:
            opening = 0.0
        if closing is None and opening is not None:
            closing = opening + total_incoming - total_outgoing

        return {
            'opening_balance': opening or 0.0,
            'closing_balance': closing or 0.0,
            'total_incoming': total_incoming,
            'total_outgoing': total_outgoing,
            'transaction_count': len(transactions),
            'currency': 'CZK'
        }

    def _calculate_confidence(self, transactions: List[Dict], text: str) -> float:
        """Calculate extraction confidence"""
        if not transactions:
            return 0.0

        score = 40.0

        # Boost for number of transactions
        score += min(len(transactions) * 3, 30)

        # Boost for having symbols
        trans_with_vs = sum(1 for t in transactions if t['variable_symbol'])
        score += min(trans_with_vs * 2, 20)

        # Boost for having counterparty info
        trans_with_cp = sum(1 for t in transactions if t['counterparty'])
        score += min(trans_with_cp * 1, 10)

        return min(score, 100.0)

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'transactions': [],
            'summary': {
                'opening_balance': 0.0,
                'closing_balance': 0.0,
                'total_incoming': 0.0,
                'total_outgoing': 0.0,
                'transaction_count': 0,
                'currency': 'CZK'
            },
            'extraction_confidence': 0.0
        }


class ReceiptExtractor(DataExtractorBase):
    """
    Extracts ALL items from receipts

    Output format:
    {
        "items": [
            {
                "line_number": 1,
                "description": "Benzín Natural 95",
                "quantity": 45.5,
                "unit": "l",
                "unit_price": 36.90,
                "vat_rate": 21,
                "total": 1679.95
            }
        ],
        "summary": {
            "total": 1679.95,
            "vat_breakdown": {
                "21": 293.71,
                "15": 0.0,
                "10": 0.0
            },
            "currency": "CZK"
        },
        "eet": {
            "fik": "a1b2c3d4-...",
            "bkp": "12345678-..."
        }
    }
    """

    # EET patterns
    RE_EET_FIK = re.compile(r'(?:FIK|fik)\s*:?\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', re.I)
    RE_EET_BKP = re.compile(r'(?:BKP|bkp)\s*:?\s*([0-9A-F]{8}-[0-9A-F]{8}-[0-9A-F]{8}-[0-9A-F]{8}-[0-9A-F]{8})', re.I)

    # VAT breakdown patterns
    RE_VAT_BREAKDOWN = re.compile(r'(?:DPH|VAT)\s+(\d{1,2})\s*%\s*:?\s*(\d[\d\s,\.]+)', re.I)

    def extract(self, text: str, ocr_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Extract all items from receipt"""
        try:
            # Find items region
            items_region = self._find_items_region(text)

            if not items_region:
                self.logger.warning("No items region found in receipt")
                return self._empty_result()

            # Extract item rows
            rows = self._extract_item_rows(items_region)

            # Parse items
            items = []
            for idx, row_text in enumerate(rows, 1):
                item = self._parse_item(idx, row_text)
                if item:
                    items.append(item)

            # Extract EET codes
            eet = self._extract_eet(text)

            # Calculate summary
            summary = self._calculate_summary(items, text)

            return {
                'items': items,
                'summary': summary,
                'eet': eet,
                'extraction_confidence': self._calculate_confidence(items, text)
            }

        except Exception as e:
            self.logger.error(f"Receipt extraction failed: {e}")
            return self._empty_result()

    def _find_items_region(self, text: str) -> Optional[str]:
        """Find items listing in receipt"""
        lines = text.split('\n')

        # Items usually start after header and before total
        # Look for first line with amount
        start_idx = None
        for i, line in enumerate(lines):
            if self.RE_AMOUNT.search(line):
                start_idx = i
                break

        if start_idx is None:
            return None

        # Find end (before total/summary)
        end_keywords = ['celkem', 'total', 'suma', 'k úhradě', 'to pay', 'hotově', 'cash', 'karta', 'card']
        end_idx = len(lines)

        for i in range(start_idx, len(lines)):
            line_lower = lines[i].lower()
            if any(kw in line_lower for kw in end_keywords):
                # Check if this line contains the word AND an amount
                # (to avoid catching item names that happen to contain these words)
                if self.RE_AMOUNT.search(lines[i]):
                    # Look ahead - if next line doesn't have amount, this is probably the total
                    if i + 1 >= len(lines) or not self.RE_AMOUNT.search(lines[i + 1]):
                        end_idx = i
                        break

        return '\n'.join(lines[start_idx:end_idx])

    def _extract_item_rows(self, items_region: str) -> List[str]:
        """Extract individual item rows - IMPROVED to skip metadata"""
        lines = items_region.split('\n')

        # Metadata/header patterns to skip
        SKIP_PATTERNS = [
            r'^\s*(?:datum|date|paragon|receipt|účtenka|iČo|dič|dic|vat|tax|číslo|number)',
            r'^\s*(?:celkem|total|suma|sum|subtotal)',
            r'^\s*(?:dph|vat)\s+\d+\s*%',  # VAT breakdown lines
            r'^\s*===+\s*$',  # Separator lines
            r'^\s*---+\s*$',
            r'^\s*EET\s',  # EET lines
            r'^\s*(?:fik|bkp)\s*:',  # EET codes
        ]

        skip_pattern = re.compile('|'.join(SKIP_PATTERNS), re.IGNORECASE)

        rows = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip metadata/header/summary lines
            if skip_pattern.match(line):
                self.logger.debug(f"Skipping metadata line: {line[:40]}...")
                continue

            # Each line with an amount is an item
            if self.RE_AMOUNT.search(line):
                rows.append(line)
                self.logger.debug(f"Found item row: {line[:60]}...")

        self.logger.info(f"Extracted {len(rows)} item rows")
        return rows

    def _parse_item(self, line_number: int, row_text: str) -> Optional[Dict]:
        """Parse single item from row text"""
        try:
            # Extract amounts
            amounts = [self.parse_amount(m.group(1))
                      for m in self.RE_AMOUNT.finditer(row_text)]
            amounts = [a for a in amounts if a is not None]

            if not amounts:
                return None

            # Extract quantity (if present)
            qty_match = self.RE_QUANTITY.search(row_text)
            quantity = float(qty_match.group(1).replace(',', '.')) if qty_match else 1.0

            # Determine unit (l, kg, ks, etc.)
            unit_match = re.search(r'(\d+(?:[,\.]\d+)?)\s*(l|kg|ks|pcs|g|m)', row_text, re.I)
            unit = unit_match.group(2).lower() if unit_match else 'ks'

            # Typical receipt layout: [description] [quantity] [unit_price] [total]
            # or: [description] [quantity x unit_price] [total]

            if len(amounts) >= 2:
                unit_price = amounts[0]
                total = amounts[-1]
            else:
                # Only one amount - it's the total
                total = amounts[0]
                unit_price = total / Decimal(str(quantity)) if quantity > 0 else total

            # Extract description (text before first amount)
            first_amount_pos = row_text.find(str(amounts[0]))
            description = row_text[:first_amount_pos].strip()

            # Clean up description
            description = re.sub(r'^\d+[\s\.]+', '', description)  # Remove line numbers
            description = re.sub(r'\d+(?:[,\.]\d+)?\s*(?:l|kg|ks|pcs|g|m)\s*$', '', description, flags=re.I)  # Remove quantity/unit at end

            # Determine VAT rate (default 21% for most items)
            # Some receipts show VAT rate next to items
            vat_match = self.RE_PERCENTAGE.search(row_text)
            vat_rate = int(vat_match.group(1)) if vat_match else 21

            return {
                'line_number': line_number,
                'description': description or f"Item {line_number}",
                'quantity': quantity,
                'unit': unit,
                'unit_price': float(unit_price),
                'vat_rate': vat_rate,
                'total': float(total)
            }

        except Exception as e:
            self.logger.error(f"Failed to parse receipt item: {e}")
            return None

    def _extract_eet(self, text: str) -> Dict[str, str]:
        """Extract EET codes"""
        fik_match = self.RE_EET_FIK.search(text)
        bkp_match = self.RE_EET_BKP.search(text)

        return {
            'fik': fik_match.group(1) if fik_match else "",
            'bkp': bkp_match.group(1) if bkp_match else ""
        }

    def _calculate_summary(self, items: List[Dict], text: str) -> Dict[str, Any]:
        """Calculate receipt summary"""
        total = sum(item['total'] for item in items)

        # Try to extract VAT breakdown from text
        vat_breakdown = {'21': 0.0, '15': 0.0, '10': 0.0}

        for match in self.RE_VAT_BREAKDOWN.finditer(text):
            rate = match.group(1)
            amount = self.parse_amount(match.group(2))
            if amount and rate in vat_breakdown:
                vat_breakdown[rate] = float(amount)

        # If no breakdown found in text, calculate from items
        if sum(vat_breakdown.values()) == 0.0:
            for item in items:
                rate = str(item['vat_rate'])
                if rate in vat_breakdown:
                    # Calculate VAT from total
                    vat_amount = item['total'] * item['vat_rate'] / (100 + item['vat_rate'])
                    vat_breakdown[rate] += vat_amount

        return {
            'total': round(total, 2),
            'vat_breakdown': {k: round(v, 2) for k, v in vat_breakdown.items()},
            'currency': 'CZK',
            'item_count': len(items)
        }

    def _calculate_confidence(self, items: List[Dict], text: str) -> float:
        """Calculate extraction confidence"""
        if not items:
            return 0.0

        score = 50.0

        # Boost for multiple items
        score += min(len(items) * 3, 30)

        # Boost for EET codes present
        if self.RE_EET_FIK.search(text) or self.RE_EET_BKP.search(text):
            score += 15

        # Boost for non-generic descriptions
        non_generic = sum(1 for item in items if not item['description'].startswith('Item '))
        score += min(non_generic * 2, 5)

        return min(score, 100.0)

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'items': [],
            'summary': {
                'total': 0.0,
                'vat_breakdown': {'21': 0.0, '15': 0.0, '10': 0.0},
                'currency': 'CZK',
                'item_count': 0
            },
            'eet': {'fik': '', 'bkp': ''},
            'extraction_confidence': 0.0
        }


# Factory function for easy access
def create_extractor(doc_type: str, config: Optional[Dict] = None):
    """
    Factory function to create appropriate extractor

    Args:
        doc_type: Document type (Czech or English names supported)
                  EN: 'invoice', 'bank_statement', 'receipt'
                  CZ: 'faktura', 'bankovní_výpis', 'účtenka'
        config: Optional configuration dict

    Returns:
        Extractor instance or None if no extractor available for type
    """
    # CZ → EN mapping (from UniversalBusinessClassifier)
    cz_to_en = {
        'faktura': 'invoice',
        'účtenka': 'receipt',
        'bankovní_výpis': 'bank_statement',
        'bankovni_vypis': 'bank_statement',  # without diacritics
        'výpis_z_účtu': 'bank_statement',
        'vypis_z_uctu': 'bank_statement',  # without diacritics
        # Additional Czech variants
        'dobropis': 'invoice',  # credit note → treat as invoice
        'zálohová_faktura': 'invoice',
        'zalohova_faktura': 'invoice',
    }

    extractors = {
        'invoice': InvoiceExtractor,
        'bank_statement': BankStatementExtractor,
        'receipt': ReceiptExtractor
    }

    # Normalize doc_type
    normalized_type = doc_type.lower().strip()

    # Try CZ → EN mapping first
    if normalized_type in cz_to_en:
        normalized_type = cz_to_en[normalized_type]

    extractor_class = extractors.get(normalized_type)
    if not extractor_class:
        # Return None instead of raising error for unsupported types
        return None

    return extractor_class(config)


if __name__ == "__main__":
    # Simple test
    logging.basicConfig(level=logging.INFO)

    # Test invoice extraction
    print("=" * 70)
    print("INVOICE EXTRACTION TEST")
    print("=" * 70)

    invoice_text = """
    FAKTURA č. 2024001

    Položky:
    1. ChatGPT Plus API - November 2024    1 ks    150,00    21%    181,50
    2. Data storage                        50 GB   2,00      21%    121,00

    Celkem bez DPH: 250,00 Kč
    DPH 21%: 52,50 Kč
    Celkem k úhradě: 302,50 Kč
    """

    invoice_extractor = create_extractor('invoice')
    result = invoice_extractor.extract(invoice_text)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Test receipt extraction
    print("\n" + "=" * 70)
    print("RECEIPT EXTRACTION TEST")
    print("=" * 70)

    receipt_text = """
    ÚČTENKA

    Benzín Natural 95    45,5 l    36,90    1679,95
    Mytí auta                1 ks     150,00   150,00

    Celkem: 1829,95 Kč
    DPH 21%: 317,89 Kč

    FIK: a1b2c3d4-e5f6-7890-abcd-ef1234567890
    BKP: 12345678-90ABCDEF-12345678-90ABCDEF-12345678
    """

    receipt_extractor = create_extractor('receipt')
    result = receipt_extractor.extract(receipt_text)
    print(json.dumps(result, indent=2, ensure_ascii=False))
