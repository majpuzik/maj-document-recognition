# Invoice Extraction - Dokumentace

## Přehled

Modul pro extrakci dat z faktur včetně:
- Základní údaje (číslo, datum, částky)
- Položky faktury (line items)
- Klasifikace služba/zboží
- ISDOC detekce

## Instalace

```bash
pip install -e ".[dev]"
```

## Použití

### Základní extrakce

```python
from src.ocr.data_extractors import InvoiceExtractor

extractor = InvoiceExtractor()
result = extractor.extract(invoice_text)

print(result['subject'])      # "Hosting služby - prosinec 2025"
print(result['item_type'])    # "service"
print(result['line_items'])   # [{'description': '...', 'amount': 1000}, ...]
```

### Integrace s Paperless

```python
from src.ocr.extraction_schemas import load_field_ids, format_for_paperless

# 1. Načti field IDs z Paperless (jednou při startu)
load_field_ids(
    api_url="http://paperless:8000/api",
    api_token="your-token"
)

# 2. Extrahuj data
result = extractor.extract(invoice_text)

# 3. Formátuj pro Paperless
custom_fields = format_for_paperless(result, 'invoice')

# 4. Odešli do Paperless
requests.patch(
    f"{api_url}/documents/{doc_id}/",
    json={"custom_fields": custom_fields},
    headers={"Authorization": f"Token {token}"}
)
```

## Nová pole v1.1

### invoice_subject (Předmět faktury)

Automaticky extrahováno z:
1. Regex pattern: `předmět|subject|popis|description`
2. Fallback: Generováno z prvních položek faktury

```python
# Příklad výstupu
"ChatGPT Plus API - November 2024"
"Webhosting + doména - Q4/2025"
```

### item_type (Typ položek)

Klasifikace na základě klíčových slov:

| Hodnota | Klíčová slova |
|---------|---------------|
| `service` | služba, licence, hosting, API, předplatné, měsíční |
| `goods` | zboží, materiál, hardware, kus, ks, balení |
| `mixed` | Kombinace služeb i zboží |

```python
# Detekce
result = extractor.extract(text)
print(result['item_type'])  # "service" | "goods" | "mixed"

# Nebo per-item
for item in result['line_items']:
    print(item['item_type'])  # "service" | "goods"
```

### ISDOC detekce

Automatická detekce ISDOC XML formátu:

```python
result = extractor.extract(xml_content)

print(result['isdoc'])
# {
#   'is_isdoc': True,
#   'version': '6.0.2',
#   'uuid': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
# }
```

Detekce pomocí:
- XML namespace: `isdoc.cz`
- Atribut: `version="6.x.x"`
- Element: `<UUID>...</UUID>`

## Schema

### INVOICE_LINE_ITEMS_SCHEMA

```json
{
  "type": "object",
  "properties": {
    "subject": {"type": "string"},
    "item_type": {"enum": ["service", "goods", "mixed"]},
    "isdoc": {
      "is_isdoc": {"type": "boolean"},
      "version": {"type": "string"},
      "uuid": {"type": "string"}
    },
    "line_items": [{
      "line_number": {"type": "integer"},
      "description": {"type": "string"},
      "quantity": {"type": "number"},
      "unit_price": {"type": "number"},
      "total_gross": {"type": "number"},
      "item_type": {"enum": ["service", "goods"]}
    }],
    "summary": {
      "total_net": {"type": "number"},
      "total_vat": {"type": "number"},
      "total_gross": {"type": "number"},
      "currency": {"type": "string"}
    }
  }
}
```

## Paperless Custom Fields

### Vytvoření polí

Pole se vytvoří automaticky nebo manuálně v Paperless Admin:

```sql
-- Příklad SQL (PostgreSQL)
INSERT INTO documents_customfield (name, data_type, extra_data, created) VALUES
('invoice_subject', 'string', '{}', NOW()),
('item_type', 'select', '{"select_options": ["service", "goods", "mixed"]}', NOW()),
('is_isdoc', 'boolean', '{}', NOW()),
('isdoc_version', 'string', '{}', NOW()),
('isdoc_uuid', 'string', '{}', NOW());
```

### Dynamic Lookup

Kód automaticky zjistí správná ID:

```python
from src.ocr.extraction_schemas import load_field_ids, get_field_id

# Načti mapování z API
load_field_ids("http://paperless:8000/api", "token")

# Získej ID
field_id = get_field_id('invoice_subject')  # Vrátí správné ID pro danou instanci
```

## Testování

```bash
# Všechny testy
pytest tests/ -v

# Jen invoice testy
pytest tests/test_invoice_extraction.py -v

# S coverage
pytest --cov=src/ocr --cov-report=html
```

### Test data

Fixtures v `tests/fixtures/invoices/`:
- `invoice_cz_basic.pdf` - Základní česká faktura
- `invoice_cz_isdoc.xml` - ISDOC formát
- `invoice_service.pdf` - Faktura za služby
- `invoice_goods.pdf` - Faktura za zboží

## Troubleshooting

### Field ID not found

```
Warning: Failed to load Paperless fields
```

**Řešení:**
1. Ověř API URL a token
2. Zkontroluj že pole existují v Paperless
3. Zavolej `load_field_ids()` před použitím

### ISDOC not detected

**Řešení:**
1. Ověř že XML obsahuje ISDOC namespace
2. Zkontroluj encoding (UTF-8)

## Changelog

- **v1.1.0** (2025-12-27): Invoice subject, item_type, ISDOC
- **v1.0.0** (2025-11-30): Initial release
