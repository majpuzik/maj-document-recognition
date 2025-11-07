#!/usr/bin/env python3
"""
Bank Statement Processor for MAJ Document Recognition
Supports: MT940, CAMT.053 (XML), CSV, ABO/GPC formats
Countries: CZ, AT, DE
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BankTransaction:
    """Bank transaction data structure"""
    
    def __init__(self):
        self.transaction_id: str = ""
        self.date: Optional[datetime] = None
        self.value_date: Optional[datetime] = None
        self.amount: Decimal = Decimal('0')
        self.currency: str = "CZK"
        self.transaction_type: str = ""
        self.description: str = ""
        self.reference: str = ""
        
        # Counterparty
        self.counterparty_name: Optional[str] = None
        self.counterparty_account: Optional[str] = None
        self.counterparty_bank: Optional[str] = None
        
        # Czech-specific symbols
        self.variable_symbol: Optional[str] = None
        self.constant_symbol: Optional[str] = None
        self.specific_symbol: Optional[str] = None
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return {
            "id": self.transaction_id,
            "date": self.date.isoformat() if self.date else None,
            "value_date": self.value_date.isoformat() if self.value_date else None,
            "amount": float(self.amount),
            "currency": self.currency,
            "type": self.transaction_type,
            "description": self.description,
            "reference": self.reference,
            "counterparty": {
                "name": self.counterparty_name,
                "account": self.counterparty_account,
                "bank": self.counterparty_bank
            },
            "czech_symbols": {
                "vs": self.variable_symbol,
                "ks": self.constant_symbol,
                "ss": self.specific_symbol
            } if self.variable_symbol else None
        }


class BankStatement:
    """Bank statement data structure"""
    
    def __init__(self):
        self.statement_id: str = ""
        self.account_number: str = ""
        self.iban: Optional[str] = None
        self.bank_code: str = ""
        self.currency: str = "CZK"
        self.from_date: Optional[datetime] = None
        self.to_date: Optional[datetime] = None
        self.opening_balance: Decimal = Decimal('0')
        self.closing_balance: Decimal = Decimal('0')
        self.transactions: List[BankTransaction] = []
        self.original_format: str = ""
        self.bank_name: str = ""
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return {
            "statement_id": self.statement_id,
            "account": {
                "number": self.account_number,
                "iban": self.iban,
                "bank_code": self.bank_code,
                "currency": self.currency
            },
            "period": {
                "from": self.from_date.isoformat() if self.from_date else None,
                "to": self.to_date.isoformat() if self.to_date else None
            },
            "balances": {
                "opening": float(self.opening_balance),
                "closing": float(self.closing_balance)
            },
            "transactions": [t.to_dict() for t in self.transactions],
            "metadata": {
                "format": self.original_format,
                "bank": self.bank_name,
                "transaction_count": len(self.transactions)
            }
        }


class BankStatementProcessor:
    """Universal bank statement processor"""
    
    CZECH_BANKS = {
        "0100": "Komerční banka",
        "0300": "ČSOB",
        "0600": "MONETA Money Bank",
        "0800": "Česká spořitelna",
        "2010": "Fio banka",
        "2700": "UniCredit Bank",
        "3030": "Air Bank",
        "5500": "Raiffeisenbank"
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def detect_format(self, content: str) -> str:
        """Detect bank statement format"""
        
        content_upper = content.upper()
        
        # MT940 format
        if ':20:' in content and ':25:' in content and ':60F:' in content:
            return "MT940"
        
        # CAMT.053 XML format
        if '<Document xmlns=' in content and 'camt.053' in content:
            return "CAMT053"
        
        # ABO/GPC format
        if content.startswith('074') or 'ABO' in content_upper:
            return "ABO"
        
        # CSV format (heuristic)
        lines = content.strip().split('\n')
        if len(lines) > 1:
            first_line = lines[0]
            if ';' in first_line or ',' in first_line:
                # Check for common CSV headers
                if any(header in first_line.lower() for header in 
                      ['datum', 'date', 'amount', 'částka', 'betrag']):
                    return "CSV"
        
        return "UNKNOWN"
    
    def parse_file(self, file_path: str) -> BankStatement:
        """Parse bank statement file"""
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        format_type = self.detect_format(content)
        
        if format_type == "MT940":
            return self.parse_mt940(content)
        elif format_type == "CAMT053":
            return self.parse_camt053(content)
        elif format_type == "ABO":
            return self.parse_abo(content)
        elif format_type == "CSV":
            return self.parse_csv(content)
        else:
            raise ValueError(f"Unknown or unsupported format: {file_path}")
    
    def parse_mt940(self, content: str) -> BankStatement:
        """Parse MT940 SWIFT format"""
        
        statement = BankStatement()
        statement.original_format = "MT940"
        
        # Extract statement number (:20:)
        match = re.search(r':20:([\w\d]+)', content)
        if match:
            statement.statement_id = match.group(1)
        
        # Extract account number (:25:)
        match = re.search(r':25:(\w+)?/(\d+)', content)
        if match:
            statement.bank_code = match.group(1) or ""
            statement.account_number = match.group(2)
            statement.bank_name = self.CZECH_BANKS.get(statement.bank_code, "")
        
        # Extract opening balance (:60F:)
        match = re.search(r':60F:([CD])(\d{6})(\w{3})([\d,]+)', content)
        if match:
            debit_credit = match.group(1)
            date_str = match.group(2)
            statement.currency = match.group(3)
            amount_str = match.group(4).replace(',', '.')
            
            statement.opening_balance = Decimal(amount_str)
            if debit_credit == 'D':
                statement.opening_balance = -statement.opening_balance
            
            statement.from_date = datetime.strptime(date_str, '%y%m%d')
        
        # Extract closing balance (:62F:)
        match = re.search(r':62F:([CD])(\d{6})(\w{3})([\d,]+)', content)
        if match:
            debit_credit = match.group(1)
            date_str = match.group(2)
            amount_str = match.group(4).replace(',', '.')
            
            statement.closing_balance = Decimal(amount_str)
            if debit_credit == 'D':
                statement.closing_balance = -statement.closing_balance
            
            statement.to_date = datetime.strptime(date_str, '%y%m%d')
        
        # Extract transactions (:61: and :86:)
        transaction_pattern = re.compile(
            r':61:(\d{6})(\d{4})?([CD])([\d,]+).*?:86:(.*?)(?=:61:|:62:|$)',
            re.DOTALL
        )
        
        for match in transaction_pattern.finditer(content):
            trans = BankTransaction()
            
            # Date
            date_str = match.group(1)
            trans.date = datetime.strptime(date_str, '%y%m%d')
            trans.value_date = trans.date
            
            # Amount
            debit_credit = match.group(3)
            amount_str = match.group(4).replace(',', '.')
            trans.amount = Decimal(amount_str)
            if debit_credit == 'D':
                trans.amount = -trans.amount
                trans.transaction_type = "DEBIT"
            else:
                trans.transaction_type = "CREDIT"
            
            trans.currency = statement.currency
            
            # Description from :86: field
            description = match.group(5).strip()
            trans.description = ' '.join(description.split())
            
            # Extract Czech symbols from description
            vs_match = re.search(r'VS[:\s]*(\d+)', description)
            if vs_match:
                trans.variable_symbol = vs_match.group(1)
            
            ks_match = re.search(r'KS[:\s]*(\d+)', description)
            if ks_match:
                trans.constant_symbol = ks_match.group(1)
            
            ss_match = re.search(r'SS[:\s]*(\d+)', description)
            if ss_match:
                trans.specific_symbol = ss_match.group(1)
            
            # Generate transaction ID
            trans.transaction_id = f"{statement.statement_id}_{len(statement.transactions)+1}"
            
            statement.transactions.append(trans)
        
        return statement
    
    def parse_camt053(self, content: str) -> BankStatement:
        """Parse CAMT.053 XML format (ISO 20022)"""
        
        statement = BankStatement()
        statement.original_format = "CAMT053"
        
        try:
            root = ET.fromstring(content)
            
            # Namespace handling
            ns = {'ns': 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.02'}
            if not root.findall('.//ns:Stmt', ns):
                # Try without namespace
                ns = {'ns': ''}
            
            # Statement info
            stmt = root.find('.//ns:Stmt', ns)
            if stmt is None:
                stmt = root.find('.//Stmt')  # Try without namespace
            
            if stmt is not None:
                # Statement ID
                stmt_id = stmt.find('.//ns:Id', ns)
                if stmt_id is not None:
                    statement.statement_id = stmt_id.text
                
                # Account info
                acct = stmt.find('.//ns:Acct', ns)
                if acct is not None:
                    iban_elem = acct.find('.//ns:IBAN', ns)
                    if iban_elem is not None:
                        statement.iban = iban_elem.text
                        # Extract bank code and account from IBAN
                        if statement.iban.startswith('CZ'):
                            statement.bank_code = statement.iban[4:8]
                            statement.account_number = statement.iban[8:]
                    
                    ccy_elem = acct.find('.//ns:Ccy', ns)
                    if ccy_elem is not None:
                        statement.currency = ccy_elem.text
                
                # Balances
                for bal in stmt.findall('.//ns:Bal', ns):
                    tp = bal.find('.//ns:Cd', ns)
                    amt = bal.find('.//ns:Amt', ns)
                    dt = bal.find('.//ns:Dt', ns)
                    
                    if tp is not None and amt is not None:
                        amount = Decimal(amt.text)
                        
                        if tp.text == 'OPBD':  # Opening balance
                            statement.opening_balance = amount
                            if dt is not None:
                                statement.from_date = datetime.fromisoformat(dt.text.split('T')[0])
                        
                        elif tp.text == 'CLBD':  # Closing balance
                            statement.closing_balance = amount
                            if dt is not None:
                                statement.to_date = datetime.fromisoformat(dt.text.split('T')[0])
                
                # Transactions
                for entry in stmt.findall('.//ns:Ntry', ns):
                    trans = BankTransaction()
                    
                    # Amount and direction
                    amt_elem = entry.find('.//ns:Amt', ns)
                    if amt_elem is not None:
                        trans.amount = Decimal(amt_elem.text)
                        trans.currency = amt_elem.get('Ccy', statement.currency)
                    
                    cd_dbt_ind = entry.find('.//ns:CdtDbtInd', ns)
                    if cd_dbt_ind is not None:
                        if cd_dbt_ind.text == 'DBIT':
                            trans.amount = -trans.amount
                            trans.transaction_type = "DEBIT"
                        else:
                            trans.transaction_type = "CREDIT"
                    
                    # Dates
                    bkg_dt = entry.find('.//ns:BookgDt/ns:Dt', ns)
                    if bkg_dt is not None:
                        trans.date = datetime.fromisoformat(bkg_dt.text.split('T')[0])
                    
                    val_dt = entry.find('.//ns:ValDt/ns:Dt', ns)
                    if val_dt is not None:
                        trans.value_date = datetime.fromisoformat(val_dt.text.split('T')[0])
                    else:
                        trans.value_date = trans.date
                    
                    # Reference
                    ref = entry.find('.//ns:AcctSvcrRef', ns)
                    if ref is not None:
                        trans.reference = ref.text
                        trans.transaction_id = ref.text
                    else:
                        trans.transaction_id = f"CAMT_{len(statement.transactions)+1}"
                    
                    # Description
                    desc = entry.find('.//ns:AddtlTxInf', ns)
                    if desc is not None:
                        trans.description = desc.text
                    
                    statement.transactions.append(trans)
            
            statement.bank_name = self.CZECH_BANKS.get(statement.bank_code, "")
            
        except ET.ParseError as e:
            raise ValueError(f"XML parsing error: {e}")
        
        return statement
    
    def parse_abo(self, content: str) -> BankStatement:
        """Parse ABO/GPC format (Czech national standard)"""
        
        statement = BankStatement()
        statement.original_format = "ABO"
        
        lines = content.strip().split('\n')
        
        for line in lines:
            if not line or len(line) < 3:
                continue
            
            record_type = line[:3]
            
            if record_type == '074':  # Header
                statement.account_number = line[3:19].strip()
                statement.bank_code = line[19:23].strip()
                statement.bank_name = self.CZECH_BANKS.get(statement.bank_code, "")
                statement.statement_id = line[23:26].strip()
                
                # Date
                date_str = line[26:32]  # YYMMDD
                statement.from_date = datetime.strptime(date_str, '%y%m%d')
                
            elif record_type == '075':  # Transaction
                trans = BankTransaction()
                
                # Transaction data
                trans.counterparty_account = line[3:19].strip()
                trans.counterparty_bank = line[19:23].strip()
                
                # Amount (in haléře/cents)
                amount_str = line[48:60].strip()
                trans.amount = Decimal(amount_str) / 100
                
                # Debit/Credit indicator
                indicator = line[60]
                if indicator == '1':  # Debit
                    trans.amount = -trans.amount
                    trans.transaction_type = "DEBIT"
                else:
                    trans.transaction_type = "CREDIT"
                
                # Variable symbol
                vs = line[61:71].strip()
                if vs and vs != '0' * len(vs):
                    trans.variable_symbol = vs
                
                # Constant symbol
                ks = line[71:75].strip()
                if ks and ks != '0' * len(ks):
                    trans.constant_symbol = ks
                
                # Specific symbol
                ss = line[75:85].strip()
                if ss and ss != '0' * len(ss):
                    trans.specific_symbol = ss
                
                # Date
                date_str = line[85:91]  # YYMMDD
                trans.date = datetime.strptime(date_str, '%y%m%d')
                trans.value_date = trans.date
                
                trans.currency = "CZK"
                trans.transaction_id = f"ABO_{len(statement.transactions)+1}"
                
                statement.transactions.append(trans)
        
        # Calculate balances
        if statement.transactions:
            statement.closing_balance = sum(t.amount for t in statement.transactions)
        
        return statement
    
    def parse_csv(self, content: str) -> BankStatement:
        """Parse CSV format (various banks)"""
        
        import csv
        from io import StringIO
        
        statement = BankStatement()
        statement.original_format = "CSV"
        
        # Detect delimiter
        delimiter = ';' if ';' in content.split('\n')[0] else ','
        
        reader = csv.DictReader(StringIO(content), delimiter=delimiter)
        
        for row in reader:
            trans = BankTransaction()
            
            # Date (try various column names)
            for date_col in ['Datum', 'Date', 'Datum zaúčtování', 'Buchungstag']:
                if date_col in row:
                    try:
                        trans.date = datetime.strptime(row[date_col], '%d.%m.%Y')
                    except:
                        try:
                            trans.date = datetime.fromisoformat(row[date_col])
                        except:
                            pass
                    break
            
            trans.value_date = trans.date
            
            # Amount
            for amt_col in ['Částka', 'Amount', 'Betrag', 'Castka']:
                if amt_col in row:
                    amt_str = row[amt_col].replace(' ', '').replace(',', '.')
                    trans.amount = Decimal(amt_str)
                    break
            
            # Currency
            trans.currency = row.get('Měna', row.get('Currency', 'CZK'))
            
            # Type
            if trans.amount < 0:
                trans.transaction_type = "DEBIT"
            else:
                trans.transaction_type = "CREDIT"
            
            # Description
            for desc_col in ['Popis', 'Description', 'Verwendungszweck', 'Název']:
                if desc_col in row:
                    trans.description = row[desc_col]
                    break
            
            # Czech symbols
            if 'VS' in row:
                trans.variable_symbol = row['VS']
            if 'KS' in row:
                trans.constant_symbol = row['KS']
            if 'SS' in row:
                trans.specific_symbol = row['SS']
            
            trans.transaction_id = f"CSV_{len(statement.transactions)+1}"
            statement.transactions.append(trans)
        
        # Calculate totals
        if statement.transactions:
            statement.closing_balance = sum(t.amount for t in statement.transactions)
        
        return statement
    
    def generate_paperless_metadata(self, statement: BankStatement) -> Dict:
        """Generate Paperless-NGX metadata for bank statement"""
        
        metadata = {
            "title": f"Bankovní výpis {statement.account_number} {statement.from_date.strftime('%Y-%m')}",
            "document_type": "bankovni_vypis",
            "tags": ["bankovní_výpis", statement.bank_name] if statement.bank_name else ["bankovní_výpis"],
            "correspondent": statement.bank_name,
            "date": statement.to_date,
            "custom_fields": {
                "account_number": statement.account_number,
                "iban": statement.iban,
                "period_from": statement.from_date.isoformat() if statement.from_date else None,
                "period_to": statement.to_date.isoformat() if statement.to_date else None,
                "opening_balance": float(statement.opening_balance),
                "closing_balance": float(statement.closing_balance),
                "transaction_count": len(statement.transactions),
                "currency": statement.currency
            }
        }
        
        return metadata
