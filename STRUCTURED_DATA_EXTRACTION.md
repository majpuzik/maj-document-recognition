# 💎 Extrakce strukturovaných dat pro RAG

## 🎯 Cíl
Extrahovat **VŠECHNA strukturovaná data** z dokumentů pro dokonalý RAG systém:
- ✅ Částky, měny, DPH z účtenek
- ✅ Všechny transakce z bankovních výpisů
- ✅ Všechny řádky z faktur (položky, ceny, DPH)
- ✅ Metadata pro RAG indexing

---

## 📋 CUSTOM FIELDS pro Paperless-NGX

### Základní finanční fields:
```python
CUSTOM_FIELDS = {
    # 1. Základní částky
    'amount_total': {
        'type': 'monetary',
        'description': 'Celková částka',
        'format': 'decimal(10,2)'
    },
    'amount_vat': {
        'type': 'monetary',
        'description': 'DPH',
        'format': 'decimal(10,2)'
    },
    'amount_net': {
        'type': 'monetary',
        'description': 'Částka bez DPH',
        'format': 'decimal(10,2)'
    },
    'currency': {
        'type': 'string',
        'description': 'Měna',
        'values': ['CZK', 'EUR', 'USD', 'GBP']
    },

    # 2. Datumy
    'date_issue': {
        'type': 'date',
        'description': 'Datum vystavení'
    },
    'date_due': {
        'type': 'date',
        'description': 'Datum splatnosti'
    },
    'date_paid': {
        'type': 'date',
        'description': 'Datum úhrady'
    },

    # 3. Identifikátory
    'invoice_number': {
        'type': 'string',
        'description': 'Číslo faktury/dokladu'
    },
    'variable_symbol': {
        'type': 'string',
        'description': 'Variabilní symbol'
    },
    'constant_symbol': {
        'type': 'string',
        'description': 'Konstantní symbol'
    },

    # 4. Dodavatel info
    'supplier_name': {
        'type': 'string',
        'description': 'Název dodavatele'
    },
    'supplier_ico': {
        'type': 'string',
        'description': 'IČO dodavatele'
    },
    'supplier_dic': {
        'type': 'string',
        'description': 'DIČ dodavatele'
    },

    # 5. Strukturovaná data (JSON)
    'line_items': {
        'type': 'json',
        'description': 'Položky dokladu (pole objektů)',
        'schema': 'LineItemsSchema'
    },
    'transactions': {
        'type': 'json',
        'description': 'Bankovní transakce (pole objektů)',
        'schema': 'TransactionsSchema'
    },
    'receipt_items': {
        'type': 'json',
        'description': 'Položky z účtenky (pole objektů)',
        'schema': 'ReceiptItemsSchema'
    }
}
```

---

## 📄 JSON SCHEMAS pro strukturovaná data

### 1. FAKTURA - Line Items
```json
{
  "line_items": [
    {
      "line_number": 1,
      "description": "ChatGPT Plus API - November 2024",
      "quantity": 1,
      "unit": "měsíc",
      "unit_price": 150.00,
      "vat_rate": 21,
      "vat_amount": 31.50,
      "total_net": 150.00,
      "total_gross": 181.50,
      "currency": "USD"
    },
    {
      "line_number": 2,
      "description": "Additional API Credits",
      "quantity": 10000,
      "unit": "tokens",
      "unit_price": 0.002,
      "vat_rate": 21,
      "vat_amount": 4.20,
      "total_net": 20.00,
      "total_gross": 24.20,
      "currency": "USD"
    }
  ],
  "summary": {
    "total_net": 170.00,
    "total_vat": 35.70,
    "total_gross": 205.70,
    "currency": "USD",
    "vat_breakdown": [
      {"rate": 21, "base": 170.00, "vat": 35.70}
    ]
  }
}
```

### 2. BANKOVNÍ VÝPIS - Transactions
```json
{
  "transactions": [
    {
      "date": "2024-11-01",
      "type": "debit",
      "amount": -150.00,
      "currency": "USD",
      "description": "OpenAI Invoice Nov 2024",
      "counterparty": "OpenAI OpCo LLC",
      "account_from": "CZ6508000000192000145399",
      "account_to": "US****1234",
      "variable_symbol": "2024110001",
      "constant_symbol": null,
      "specific_symbol": null,
      "reference": "INV-2024-001234"
    },
    {
      "date": "2024-11-05",
      "type": "debit",
      "amount": -50.00,
      "currency": "USD",
      "description": "Anthropic Claude API",
      "counterparty": "Anthropic PBC",
      "account_from": "CZ6508000000192000145399",
      "account_to": "US****5678",
      "variable_symbol": null,
      "constant_symbol": null,
      "specific_symbol": null,
      "reference": "claude-api-nov"
    }
  ],
  "summary": {
    "opening_balance": 5000.00,
    "closing_balance": 4800.00,
    "total_debits": -200.00,
    "total_credits": 0.00,
    "transaction_count": 2,
    "period_from": "2024-11-01",
    "period_to": "2024-11-30",
    "currency": "USD"
  }
}
```

### 3. ÚČTENKA - Receipt Items
```json
{
  "receipt_items": [
    {
      "line_number": 1,
      "description": "Káva Espresso",
      "quantity": 2,
      "unit_price": 45.00,
      "vat_rate": 15,
      "vat_amount": 11.74,
      "total": 101.74,
      "category": "nápoje"
    },
    {
      "line_number": 2,
      "description": "Croissant",
      "quantity": 1,
      "unit_price": 35.00,
      "vat_rate": 15,
      "vat_amount": 4.57,
      "total": 39.57,
      "category": "pečivo"
    }
  ],
  "payment": {
    "method": "card",
    "card_last4": "1234",
    "authorization": "OK",
    "terminal_id": "12345678"
  },
  "summary": {
    "subtotal": 80.00,
    "vat": 16.31,
    "total": 96.31,
    "currency": "CZK",
    "vat_breakdown": [
      {"rate": 15, "base": 80.00, "vat": 16.31}
    ]
  },
  "eet": {
    "fik": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "bkp": "12345678-12345678-12345678-12345678-12345678",
    "verified": true
  }
}
```

---

## 🔍 EXTRAKTORY

### Extraktor 1: Faktura
```python
class InvoiceExtractor:
    """Extrahuje strukturovaná data z faktur"""

    def extract(self, text: str, ocr_result: dict) -> dict:
        """
        Extrahuje všechna data z faktury

        Returns:
            {
                'invoice_number': str,
                'date_issue': str,
                'date_due': str,
                'supplier': {...},
                'customer': {...},
                'line_items': [...],
                'summary': {...}
            }
        """
        data = {}

        # 1. Základní info
        data['invoice_number'] = self.extract_invoice_number(text)
        data['date_issue'] = self.extract_date(text, type='issue')
        data['date_due'] = self.extract_date(text, type='due')

        # 2. Dodavatel
        data['supplier'] = {
            'name': self.extract_supplier_name(text),
            'ico': self.extract_ico(text),
            'dic': self.extract_dic(text),
            'address': self.extract_address(text, party='supplier')
        }

        # 3. Odběratel
        data['customer'] = {
            'name': self.extract_customer_name(text),
            'ico': self.extract_ico(text, party='customer'),
            'address': self.extract_address(text, party='customer')
        }

        # 4. Položky (kritické pro RAG!)
        data['line_items'] = self.extract_line_items(text, ocr_result)

        # 5. Souhrn
        data['summary'] = self.calculate_summary(data['line_items'])

        return data

    def extract_line_items(self, text: str, ocr_result: dict) -> list:
        """
        Extrahuje jednotlivé položky z tabulky

        Použije:
        - Regex patterns pro strukturované řádky
        - OCR bounding boxes pro identifikaci tabulek
        - ML model pro klasifikaci sloupců
        """
        items = []

        # Najdi tabulku položek
        table_region = self.find_table_region(ocr_result)

        # Extrahuj řádky
        rows = self.extract_table_rows(table_region)

        for idx, row in enumerate(rows, 1):
            item = {
                'line_number': idx,
                'description': self.extract_description(row),
                'quantity': self.extract_quantity(row),
                'unit': self.extract_unit(row),
                'unit_price': self.extract_unit_price(row),
                'vat_rate': self.extract_vat_rate(row),
                'vat_amount': self.extract_vat_amount(row),
                'total_net': self.extract_total_net(row),
                'total_gross': self.extract_total_gross(row),
                'currency': self.extract_currency(row)
            }
            items.append(item)

        return items
```

### Extraktor 2: Bankovní výpis
```python
class BankStatementExtractor:
    """Extrahuje transakce z bankovních výpisů"""

    def extract(self, text: str, ocr_result: dict) -> dict:
        """
        Extrahuje všechny transakce z výpisu

        Returns:
            {
                'account': {...},
                'period': {...},
                'transactions': [...],
                'summary': {...}
            }
        """
        data = {}

        # 1. Číslo účtu
        data['account'] = {
            'number': self.extract_account_number(text),
            'bank_code': self.extract_bank_code(text),
            'iban': self.extract_iban(text)
        }

        # 2. Období
        data['period'] = {
            'from': self.extract_period_from(text),
            'to': self.extract_period_to(text)
        }

        # 3. Transakce (každý řádek!)
        data['transactions'] = self.extract_transactions(text, ocr_result)

        # 4. Souhrn
        data['summary'] = self.calculate_summary(data['transactions'])

        return data

    def extract_transactions(self, text: str, ocr_result: dict) -> list:
        """
        Extrahuje VŠECHNY transakce z výpisu

        Pro každou transakci:
        - Datum
        - Typ (debit/credit)
        - Částka
        - Měna
        - Protiúčet
        - Název protistrany
        - Variabilní/Konstantní/Specifický symbol
        - Popis/Reference
        """
        transactions = []

        # Najdi oblast transakcí
        trans_region = self.find_transactions_region(ocr_result)

        # Extrahuj jednotlivé řádky
        rows = self.extract_transaction_rows(trans_region)

        for row in rows:
            trans = {
                'date': self.extract_date(row),
                'type': self.determine_type(row),  # debit/credit
                'amount': self.extract_amount(row),
                'currency': self.extract_currency(row),
                'description': self.extract_description(row),
                'counterparty': self.extract_counterparty(row),
                'account_from': self.extract_account_from(row),
                'account_to': self.extract_account_to(row),
                'variable_symbol': self.extract_vs(row),
                'constant_symbol': self.extract_ks(row),
                'specific_symbol': self.extract_ss(row),
                'reference': self.extract_reference(row)
            }
            transactions.append(trans)

        return transactions
```

### Extraktor 3: Účtenka
```python
class ReceiptExtractor:
    """Extrahuje data z účtenek (CZ Receipt Intelligence)"""

    def extract(self, text: str) -> dict:
        """
        Extrahuje data z účtenky

        Returns:
            {
                'store': {...},
                'receipt_items': [...],
                'payment': {...},
                'summary': {...},
                'eet': {...}
            }
        """
        data = {}

        # 1. Obchod
        data['store'] = {
            'name': self.extract_store_name(text),
            'ico': self.extract_ico(text),
            'dic': self.extract_dic(text),
            'address': self.extract_address(text)
        }

        # 2. Položky
        data['receipt_items'] = self.extract_items(text)

        # 3. Platba
        data['payment'] = {
            'method': self.extract_payment_method(text),
            'card_last4': self.extract_card_last4(text) if 'card' in payment_method else None,
            'authorization': self.extract_auth_code(text),
            'terminal_id': self.extract_terminal_id(text)
        }

        # 4. Souhrn
        data['summary'] = self.calculate_summary(data['receipt_items'])

        # 5. EET
        data['eet'] = {
            'fik': self.extract_fik(text),
            'bkp': self.extract_bkp(text),
            'verified': self.verify_eet(data['eet'])
        }

        return data
```

---

## 📊 PŘÍKLAD: Kompletní záznam v Paperless

### Faktura od OpenAI (úplná)
```json
{
  // Základní Paperless fields
  "title": "Invoice OpenAI November 2024",
  "document_type": 1,  // Invoice
  "correspondent": 5,  // OpenAI
  "created": "2024-11-30",

  // Hierarchické tagy
  "tags": [
    12,  // supplier:OpenAI
    34,  // cat:financial
    56,  // sub:faktura
    78,  // type:faktura-dodavatelska
    90,  // meta:high-confidence
    91   // period:2024-11
  ],

  // Custom fields - Základní
  "custom_fields": [
    {"field": 1, "value": "205.70"},           // amount_total
    {"field": 2, "value": "35.70"},            // amount_vat
    {"field": 3, "value": "170.00"},           // amount_net
    {"field": 4, "value": "USD"},              // currency
    {"field": 5, "value": "2024-11-30"},       // date_issue
    {"field": 6, "value": "2024-12-15"},       // date_due
    {"field": 7, "value": "INV-2024-001234"},  // invoice_number
    {"field": 8, "value": "OpenAI OpCo LLC"},  // supplier_name

    // Custom fields - Strukturovaná data (JSON!)
    {"field": 20, "value": JSON.stringify({
      "line_items": [
        {
          "line_number": 1,
          "description": "ChatGPT Plus API - November 2024",
          "quantity": 1,
          "unit": "měsíc",
          "unit_price": 150.00,
          "vat_rate": 21,
          "total_gross": 181.50
        },
        {
          "line_number": 2,
          "description": "Additional API Credits",
          "quantity": 10000,
          "unit": "tokens",
          "unit_price": 0.002,
          "vat_rate": 21,
          "total_gross": 24.20
        }
      ],
      "summary": {
        "total_net": 170.00,
        "total_vat": 35.70,
        "total_gross": 205.70
      }
    })}
  ]
}
```

---

## 🔍 RAG QUERIES - Příklady

### 1. "Kolik platím OpenAI měsíčně?"
```python
# RAG vyhledá:
filters = {
    "tags": ["supplier:OpenAI", "cat:financial"],
    "custom_fields": {
        "currency": "USD"
    }
}

# Z custom_fields.line_items extrahuje:
monthly_costs = []
for doc in results:
    line_items = json.loads(doc.custom_fields['line_items'])
    for item in line_items:
        if 'monthly' in item['description'].lower():
            monthly_costs.append(item['total_gross'])

# RAG odpověď:
"Měsíčně platíte OpenAI průměrně $150 za ChatGPT Plus API
 + variabilní náklady za API credits cca $20-50."
```

### 2. "Kdo mi poslal nejvíc peněz v listopadu?"
```python
# RAG vyhledá:
filters = {
    "tags": ["cat:financial", "sub:vypis", "period:2024-11"]
}

# Z custom_fields.transactions extrahuje:
credits_by_counterparty = {}
for doc in results:
    transactions = json.loads(doc.custom_fields['transactions'])
    for trans in transactions:
        if trans['type'] == 'credit':
            counterparty = trans['counterparty']
            credits_by_counterparty[counterparty] += trans['amount']

# RAG odpověď:
"V listopadu jste dostal nejvíce peněz od:
 1. Client ABC: 15 000 CZK
 2. Client XYZ: 8 500 CZK"
```

### 3. "Jaké položky jsem nakupoval na účtenkách s DPH 21%?"
```python
# RAG vyhledá:
filters = {
    "tags": ["cat:financial", "sub:uctenka"]
}

# Z custom_fields.receipt_items filtruje:
items_with_21_vat = []
for doc in results:
    items = json.loads(doc.custom_fields['receipt_items'])
    for item in items:
        if item['vat_rate'] == 21:
            items_with_21_vat.append({
                'description': item['description'],
                'total': item['total'],
                'store': doc.correspondent
            })

# RAG odpověď:
"Položky s DPH 21%:
 - Elektronika v Alza.cz: 5 položek, celkem 12 500 Kč
 - Software licence: 3 položky, celkem 8 900 Kč"
```

---

## ✅ FINÁLNÍ STRUKTURA

```
DOKUMENT V PAPERLESS:
├── Tags (hierarchické)
│   ├── supplier:OpenAI
│   ├── cat:financial
│   ├── sub:faktura
│   └── type:faktura-dodavatelska
│
├── Custom Fields (jednoduchá)
│   ├── amount_total: 205.70
│   ├── currency: USD
│   ├── invoice_number: INV-2024-001234
│   └── date_due: 2024-12-15
│
└── Custom Fields (JSON strukturovaná)
    ├── line_items: [{...}, {...}]      ← Pro faktury
    ├── transactions: [{...}, {...}]    ← Pro výpisy
    └── receipt_items: [{...}, {...}]   ← Pro účtenky
```

---

## 🚀 IMPLEMENTAČNÍ PLÁN

Po schválení:

1. **`data_extractors.py`**
   - InvoiceExtractor
   - BankStatementExtractor
   - ReceiptExtractor

2. **`custom_fields_manager.py`**
   - Vytvoří všechny custom fields v Paperless
   - Validuje JSON schemas

3. **`classify_and_extract.py`**
   - Klasifikuje + Extrahuje strukturovaná data
   - Ukládá do Paperless s full metadata

4. **`rag_indexer.py`**
   - Indexuje dokumenty včetně JSON dat
   - Připraví pro RAG queries

---

**Toto je KOMPLETNÍ systém pro perfektní RAG! 💎**

Čekám na schválení implementace!
