"""
Document Matching System - Párování objednávek, faktur, dodacích listů a plateb

Tento modul implementuje inteligentní párování business dokumentů na základě:
- Čísel objednávek
- Čísel faktur
- Částek
- Dat
- Vendor/Dodavatel informací
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..database.db_manager import DatabaseManager


@dataclass
class ExtractedInfo:
    """Extrahované informace z dokumentu"""

    # Identifikátory
    order_number: Optional[str] = None
    invoice_number: Optional[str] = None
    delivery_note_number: Optional[str] = None
    variable_symbol: Optional[str] = None

    # Částky
    amount_without_vat: Optional[float] = None
    vat_amount: Optional[float] = None
    amount_with_vat: Optional[float] = None

    # Data
    issue_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None

    # Strany
    vendor_name: Optional[str] = None
    vendor_ico: Optional[str] = None
    customer_name: Optional[str] = None
    customer_ico: Optional[str] = None

    # Reference
    references: List[str] = None

    def __post_init__(self):
        if self.references is None:
            self.references = []


class DocumentExtractor:
    """Extraktor klíčových informací z dokumentů"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Regex patterns pro různé typy čísel
        self.patterns = {
            'order_number': [
                r'(?:objedn[áa]vk[ay]?)\s+[č.:]?\s*([A-Z0-9\-/]+)',
                r'(?:obj\.[^a-zA-Z]\s*)\s*([A-Z0-9\-/]+)',
                r'(?:PO|P\.O\.|purchase\s+order)[\s:#]*([A-Z0-9\-/]+)',
                r'(?:bestellung|bestellnr)[\s:.]*([A-Z0-9\-/]+)',
            ],
            'invoice_number': [
                r'(?:faktur[ay]?|invoice|rechnung)\s*[č.:]?\s*([A-Z0-9\-/]+)',
                r'(?:fa|fv|inv)[\s.:#]*([0-9]{6,})',
                r'(?:daň\.?\s*doklad|tax\s+document)[\s:]([0-9]+)',
            ],
            'delivery_note_number': [
                r'(?:dodac[íi]\s*list|delivery\s*note|lieferschein)\s*[č.:]?\s*([A-Z0-9\-/]+)',
                r'(?:DL|DN)[\s.:#]*([A-Z0-9\-/]+)',
            ],
            'variable_symbol': [
                r'(?:var\.?\s*symbol|VS|variabiln[íi]\s*symbol)[\s:]*([0-9]{6,})',
                r'(?:reference|referenz)[\s:]*([0-9]{6,})',
            ],
            'amount': [
                r'(?:celkem|total|gesamt|k\s*úhradě)[\s:]*([0-9\s]+[,.]?[0-9]*)\s*(?:Kč|CZK|EUR|€)',
                r'([0-9]{1,3}(?:[\s,.][0-9]{3})*[,.][0-9]{2})\s*(?:Kč|CZK|EUR|€)',
            ],
            'ico': [
                r'(?:IČO?|ičo)[\s:]*([0-9]{8})',
                r'(?:company\s+id|ID)[\s:]*([0-9]{8})',
            ],
            'date': [
                r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
                r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',
            ],
        }

    def extract(self, text: str, doc_type: str) -> ExtractedInfo:
        """
        Extrahuje klíčové informace z textu dokumentu

        Args:
            text: OCR text dokumentu
            doc_type: Typ dokumentu (faktura, objednavka, atd.)

        Returns:
            ExtractedInfo objekt s nalezenými daty
        """
        info = ExtractedInfo()

        # Normalizace textu
        text = text.replace('\n', ' ').replace('\r', ' ')
        text_lower = text.lower()

        # Extrakce dle typu dokumentu
        if doc_type == 'objednavka':
            info.order_number = self._extract_order_number(text)
            info.amount_with_vat = self._extract_amount(text)
            info.delivery_date = self._extract_delivery_date(text)

        elif doc_type == 'faktura':
            info.invoice_number = self._extract_invoice_number(text)
            info.order_number = self._extract_reference_order(text)
            info.amount_with_vat = self._extract_amount(text)
            info.variable_symbol = self._extract_variable_symbol(text)
            info.issue_date = self._extract_issue_date(text)
            info.due_date = self._extract_due_date(text)

        elif doc_type == 'dodaci_list':
            info.delivery_note_number = self._extract_delivery_note_number(text)
            info.order_number = self._extract_reference_order(text)
            info.invoice_number = self._extract_reference_invoice(text)
            info.delivery_date = self._extract_delivery_date(text)

        elif doc_type in ['oznameni_o_zaplaceni', 'bankovni_vypis']:
            info.variable_symbol = self._extract_variable_symbol(text)
            info.amount_with_vat = self._extract_amount(text)
            info.issue_date = self._extract_payment_date(text)
            info.invoice_number = self._extract_reference_invoice(text)

        # Společné extrakce
        info.vendor_ico = self._extract_vendor_ico(text)
        info.vendor_name = self._extract_vendor_name(text)
        info.references = self._extract_all_references(text)

        return info

    def _extract_order_number(self, text: str) -> Optional[str]:
        """Extrahuje číslo objednávky"""
        for pattern in self.patterns['order_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().upper()
        return None

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """Extrahuje číslo faktury"""
        for pattern in self.patterns['invoice_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().upper()
        return None

    def _extract_delivery_note_number(self, text: str) -> Optional[str]:
        """Extrahuje číslo dodacího listu"""
        for pattern in self.patterns['delivery_note_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().upper()
        return None

    def _extract_variable_symbol(self, text: str) -> Optional[str]:
        """Extrahuje variabilní symbol"""
        for pattern in self.patterns['variable_symbol']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_amount(self, text: str) -> Optional[float]:
        """Extrahuje částku"""
        for pattern in self.patterns['amount']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(' ', '').replace(',', '.')
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None

    def _extract_vendor_ico(self, text: str) -> Optional[str]:
        """Extrahuje IČO dodavatele"""
        matches = []
        for pattern in self.patterns['ico']:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(match.group(1))

        # Vrátí první nalezené IČO (předpokládáme že je to vendor)
        return matches[0] if matches else None

    def _extract_vendor_name(self, text: str) -> Optional[str]:
        """Extrahuje název dodavatele z prvních řádků"""
        lines = text.split('\n')[:10]  # Prvních 10 řádků

        # Hledáme řádky s "s.r.o.", "a.s.", "GmbH", atd.
        company_patterns = [
            r'([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž\s]+(?:s\.r\.o\.|a\.s\.|spol\.|GmbH|AG|Ltd))',
        ]

        for line in lines:
            for pattern in company_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()

        return None

    def _extract_reference_order(self, text: str) -> Optional[str]:
        """Extrahuje odkaz na objednávku z faktury/dodacího listu"""
        return self._extract_order_number(text)

    def _extract_reference_invoice(self, text: str) -> Optional[str]:
        """Extrahuje odkaz na fakturu"""
        return self._extract_invoice_number(text)

    def _extract_issue_date(self, text: str) -> Optional[datetime]:
        """Extrahuje datum vystavení"""
        # Hledáme "datum vystavení", "vydáno", "issued", atd.
        patterns = [
            r'(?:datum\s*vyst|vystaveno|vydáno|issued|ausgestellt)[\s:]*(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    day, month, year = match.groups()
                    return datetime(int(year), int(month), int(day))
                except (ValueError, AttributeError):
                    continue

        return None

    def _extract_due_date(self, text: str) -> Optional[datetime]:
        """Extrahuje datum splatnosti"""
        patterns = [
            r'(?:splatnost|due\s+date|fällig)[\s:]*(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    day, month, year = match.groups()
                    return datetime(int(year), int(month), int(day))
                except (ValueError, AttributeError):
                    continue

        return None

    def _extract_delivery_date(self, text: str) -> Optional[datetime]:
        """Extrahuje datum dodání"""
        patterns = [
            r'(?:dodán[oí]|dodan[oí]\s*list|delivered|geliefert)[\s:]*(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
            r'(?:expedováno|shipped)[\s:]*(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    day, month, year = match.groups()
                    return datetime(int(year), int(month), int(day))
                except (ValueError, AttributeError):
                    continue

        return None

    def _extract_payment_date(self, text: str) -> Optional[datetime]:
        """Extrahuje datum platby"""
        patterns = [
            r'(?:zaplaceno|paid|bezahlt)[\s:]*(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    day, month, year = match.groups()
                    return datetime(int(year), int(month), int(day))
                except (ValueError, AttributeError):
                    continue

        return None

    def _extract_all_references(self, text: str) -> List[str]:
        """Extrahuje všechny možné reference z dokumentu"""
        references = []

        # Všechny regex patterny
        all_patterns = (
            self.patterns['order_number'] +
            self.patterns['invoice_number'] +
            self.patterns['delivery_note_number'] +
            self.patterns['variable_symbol']
        )

        for pattern in all_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                ref = match.group(1).strip().upper()
                if ref and ref not in references:
                    references.append(ref)

        return references[:10]  # Max 10 referencí


class DocumentMatcher:
    """Hlavní třída pro párování dokumentů"""

    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializace document matcheru

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.extractor = DocumentExtractor()
        self.logger = logging.getLogger(__name__)

        # Inicializace matching tabulky
        self._init_matching_table()

    def _init_matching_table(self) -> None:
        """Vytvoří tabulku pro matched documents"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Tabulka pro matched document chains
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matched_document_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id TEXT UNIQUE NOT NULL,
                order_doc_id INTEGER,
                invoice_doc_id INTEGER,
                delivery_note_doc_id INTEGER,
                payment_doc_id INTEGER,
                complaint_doc_id INTEGER,
                refund_doc_id INTEGER,

                total_amount REAL,
                vendor_name TEXT,
                vendor_ico TEXT,

                order_number TEXT,
                invoice_number TEXT,
                variable_symbol TEXT,

                order_date TEXT,
                invoice_date TEXT,
                delivery_date TEXT,
                payment_date TEXT,

                status TEXT,
                confidence REAL,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (order_doc_id) REFERENCES documents(id),
                FOREIGN KEY (invoice_doc_id) REFERENCES documents(id),
                FOREIGN KEY (delivery_note_doc_id) REFERENCES documents(id),
                FOREIGN KEY (payment_doc_id) REFERENCES documents(id)
            )
        """)

        # Tabulka pro extracted metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,

                order_number TEXT,
                invoice_number TEXT,
                delivery_note_number TEXT,
                variable_symbol TEXT,

                amount_without_vat REAL,
                vat_amount REAL,
                amount_with_vat REAL,

                issue_date TEXT,
                due_date TEXT,
                delivery_date TEXT,
                payment_date TEXT,

                vendor_name TEXT,
                vendor_ico TEXT,
                customer_name TEXT,
                customer_ico TEXT,

                ref_numbers TEXT,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
        """)

        # Indexy
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_order_number ON document_metadata(order_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_invoice_number ON document_metadata(invoice_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_variable_symbol ON document_metadata(variable_symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chains_status ON matched_document_chains(status)")

        conn.commit()
        conn.close()

        self.logger.info("Matching tables initialized")

    def extract_and_store_metadata(self, doc_id: int) -> Optional[ExtractedInfo]:
        """
        Extrahuje metadata z dokumentu a uloží je do DB

        Args:
            doc_id: ID dokumentu

        Returns:
            ExtractedInfo objekt nebo None
        """
        # Načti dokument
        doc = self.db.get_document(doc_id)
        if not doc:
            self.logger.warning(f"Document {doc_id} not found")
            return None

        # Extrahuj metadata
        info = self.extractor.extract(doc['ocr_text'] or '', doc['document_type'])

        # Ulož do DB
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO document_metadata (
                document_id, order_number, invoice_number, delivery_note_number,
                variable_symbol, amount_with_vat, issue_date, due_date,
                delivery_date, vendor_name, vendor_ico, ref_numbers
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            info.order_number,
            info.invoice_number,
            info.delivery_note_number,
            info.variable_symbol,
            info.amount_with_vat,
            info.issue_date.isoformat() if info.issue_date else None,
            info.due_date.isoformat() if info.due_date else None,
            info.delivery_date.isoformat() if info.delivery_date else None,
            info.vendor_name,
            info.vendor_ico,
            json.dumps(info.references),
        ))

        conn.commit()
        conn.close()

        self.logger.info(f"Stored metadata for document {doc_id}")
        return info

    def match_documents(self, doc_id: int) -> Optional[Dict]:
        """
        Najde matching dokumenty pro daný dokument

        Args:
            doc_id: ID dokumentu

        Returns:
            Dictionary s matched document chain
        """
        # Získej metadata dokumentu
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM document_metadata WHERE document_id = ?", (doc_id,))
        metadata = cursor.fetchone()

        if not metadata:
            # Zkus extrahovat metadata
            self.extract_and_store_metadata(doc_id)
            cursor.execute("SELECT * FROM document_metadata WHERE document_id = ?", (doc_id,))
            metadata = cursor.fetchone()

        if not metadata:
            return None

        metadata = dict(metadata)

        # Najdi related dokumenty
        matches = {
            'order': None,
            'invoice': None,
            'delivery_note': None,
            'payment': None,
        }

        # Match by order number
        if metadata['order_number']:
            cursor.execute("""
                SELECT d.*, dm.* FROM documents d
                JOIN document_metadata dm ON d.id = dm.document_id
                WHERE dm.order_number = ? AND d.id != ?
                ORDER BY d.created_at DESC
            """, (metadata['order_number'], doc_id))

            for row in cursor.fetchall():
                row_dict = dict(row)
                doc_type = row_dict['document_type']

                if doc_type == 'objednavka' and not matches['order']:
                    matches['order'] = row_dict
                elif doc_type == 'faktura' and not matches['invoice']:
                    matches['invoice'] = row_dict
                elif doc_type == 'dodaci_list' and not matches['delivery_note']:
                    matches['delivery_note'] = row_dict

        # Match by invoice number
        if metadata['invoice_number']:
            cursor.execute("""
                SELECT d.*, dm.* FROM documents d
                JOIN document_metadata dm ON d.id = dm.document_id
                WHERE dm.invoice_number = ? AND d.id != ?
                ORDER BY d.created_at DESC
            """, (metadata['invoice_number'], doc_id))

            for row in cursor.fetchall():
                row_dict = dict(row)
                doc_type = row_dict['document_type']

                if doc_type == 'faktura' and not matches['invoice']:
                    matches['invoice'] = row_dict
                elif doc_type == 'dodaci_list' and not matches['delivery_note']:
                    matches['delivery_note'] = row_dict
                elif doc_type in ['oznameni_o_zaplaceni', 'bankovni_vypis'] and not matches['payment']:
                    matches['payment'] = row_dict

        # Match by variable symbol
        if metadata['variable_symbol']:
            cursor.execute("""
                SELECT d.*, dm.* FROM documents d
                JOIN document_metadata dm ON d.id = dm.document_id
                WHERE dm.variable_symbol = ? AND d.id != ?
                ORDER BY d.created_at DESC
            """, (metadata['variable_symbol'], doc_id))

            for row in cursor.fetchall():
                row_dict = dict(row)
                doc_type = row_dict['document_type']

                if doc_type == 'faktura' and not matches['invoice']:
                    matches['invoice'] = row_dict
                elif doc_type in ['oznameni_o_zaplaceni', 'bankovni_vypis'] and not matches['payment']:
                    matches['payment'] = row_dict

        conn.close()

        return matches if any(matches.values()) else None

    def create_or_update_chain(
        self,
        order_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        delivery_id: Optional[int] = None,
        payment_id: Optional[int] = None,
    ) -> str:
        """
        Vytvoří nebo updatuje document chain

        Args:
            order_id: ID objednávky
            invoice_id: ID faktury
            delivery_id: ID dodacího listu
            payment_id: ID platby

        Returns:
            Chain ID
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Vygeneruj chain_id
        chain_id = f"CHAIN-{order_id or invoice_id or delivery_id or payment_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Získej metadata z dokumentů
        order_number = None
        invoice_number = None
        variable_symbol = None
        total_amount = None
        vendor_name = None
        vendor_ico = None

        for doc_id in [order_id, invoice_id, delivery_id, payment_id]:
            if doc_id:
                cursor.execute("SELECT * FROM document_metadata WHERE document_id = ?", (doc_id,))
                meta = cursor.fetchone()
                if meta:
                    meta = dict(meta)
                    order_number = order_number or meta.get('order_number')
                    invoice_number = invoice_number or meta.get('invoice_number')
                    variable_symbol = variable_symbol or meta.get('variable_symbol')
                    total_amount = total_amount or meta.get('amount_with_vat')
                    vendor_name = vendor_name or meta.get('vendor_name')
                    vendor_ico = vendor_ico or meta.get('vendor_ico')

        # Zjisti status
        status = self._determine_chain_status(order_id, invoice_id, delivery_id, payment_id)

        # Vytvoř nebo updatuj chain
        cursor.execute("""
            INSERT OR REPLACE INTO matched_document_chains (
                chain_id, order_doc_id, invoice_doc_id, delivery_note_doc_id,
                payment_doc_id, total_amount, vendor_name, vendor_ico,
                order_number, invoice_number, variable_symbol, status, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chain_id, order_id, invoice_id, delivery_id, payment_id,
            total_amount, vendor_name, vendor_ico,
            order_number, invoice_number, variable_symbol, status, 0.85
        ))

        conn.commit()
        conn.close()

        self.logger.info(f"Created/updated chain: {chain_id}")
        return chain_id

    def _determine_chain_status(
        self,
        order_id: Optional[int],
        invoice_id: Optional[int],
        delivery_id: Optional[int],
        payment_id: Optional[int],
    ) -> str:
        """Určí status document chainu"""
        if payment_id:
            return 'completed'
        elif delivery_id:
            return 'delivered'
        elif invoice_id:
            return 'invoiced'
        elif order_id:
            return 'ordered'
        else:
            return 'unknown'

    def get_all_chains(self, status: Optional[str] = None) -> List[Dict]:
        """
        Získá všechny document chains

        Args:
            status: Filtrovat podle statusu (ordered, invoiced, delivered, completed)

        Returns:
            List chain dictionaries
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM matched_document_chains WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def match_all_documents(self, limit: Optional[int] = None) -> Dict:
        """
        Spáruje všechny dokumenty v databázi

        Args:
            limit: Omezit počet dokumentů

        Returns:
            Statistics dictionary
        """
        self.logger.info("Starting full document matching...")

        # Získej všechny dokumenty
        docs = self.db.get_all_documents(limit=limit)

        stats = {
            'total_documents': len(docs),
            'extracted_metadata': 0,
            'matched_chains': 0,
            'by_type': {},
        }

        # 1. Extrahuj metadata ze všech dokumentů
        for doc in docs:
            try:
                self.extract_and_store_metadata(doc['id'])
                stats['extracted_metadata'] += 1
            except Exception as e:
                self.logger.error(f"Error extracting metadata from doc {doc['id']}: {e}")

        # 2. Vytvoř matching chains
        orders = [d for d in docs if d['document_type'] == 'objednavka']
        invoices = [d for d in docs if d['document_type'] == 'faktura']

        for order in orders:
            matches = self.match_documents(order['id'])
            if matches:
                self.create_or_update_chain(
                    order_id=order['id'],
                    invoice_id=matches['invoice']['id'] if matches['invoice'] else None,
                    delivery_id=matches['delivery_note']['id'] if matches['delivery_note'] else None,
                    payment_id=matches['payment']['id'] if matches['payment'] else None,
                )
                stats['matched_chains'] += 1

        for invoice in invoices:
            matches = self.match_documents(invoice['id'])
            if matches and matches['order']:
                # Chain už může existovat z orders
                continue

            if matches:
                self.create_or_update_chain(
                    order_id=matches['order']['id'] if matches['order'] else None,
                    invoice_id=invoice['id'],
                    delivery_id=matches['delivery_note']['id'] if matches['delivery_note'] else None,
                    payment_id=matches['payment']['id'] if matches['payment'] else None,
                )
                stats['matched_chains'] += 1

        self.logger.info(f"Matching completed: {stats}")
        return stats
