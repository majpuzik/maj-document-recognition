# Invoice Extraction v1.1 - New Fields

**Date:** 2025-12-27
**Author:** Claude Code
**Version:** 1.1.0

## Overview

Extended invoice extraction with new fields for better categorization and ISDOC support.

## New Fields

### 1. Invoice Subject (`invoice_subject`)
- **Purpose:** Předmět faktury - summary of invoiced items
- **Paperless ID:** 23
- **Type:** string (max 200 chars)
- **Extraction:**
  - Primary: Regex pattern `předmět|subject|popis|description`
  - Fallback: Generated from first line item descriptions

### 2. Item Type (`item_type`)
- **Purpose:** Classification of invoice items as service or goods
- **Paperless ID:** 24
- **Type:** select
- **Values:** `service`, `goods`, `mixed`
- **Detection Keywords:**

| Service (služba) | Goods (zboží) |
|-----------------|---------------|
| služba, služby | zboží, goods |
| service, services | materiál, material |
| práce, work | produkt, product |
| poradenství, consulting | výrobek, item |
| podpora, support | kus, ks, pcs |
| údržba, maintenance | balení, package |
| licence, license | hardware |
| předplatné, subscription | přístroj, device |
| pronájem, rental | součástka, component |
| hosting, api, software | náhradní díl |
| měsíční, roční | spotřební |

### 3. ISDOC Detection

#### is_isdoc (ID: 25)
- **Type:** boolean
- **Detection:** XML with ISDOC namespace or version attribute

#### isdoc_version (ID: 26)
- **Type:** string
- **Example:** `6.0.2`

#### isdoc_uuid (ID: 27)
- **Type:** string (UUID format)
- **Example:** `a1b2c3d4-e5f6-7890-abcd-ef1234567890`

## Schema Changes

### extraction_schemas.py

```python
INVOICE_LINE_ITEMS_SCHEMA = {
    "properties": {
        "subject": {"type": "string"},           # NEW
        "item_type": {"enum": ["service", "goods", "mixed"]},  # NEW
        "isdoc": {                                # NEW
            "is_isdoc": {"type": "boolean"},
            "version": {"type": "string"},
            "uuid": {"type": "string"}
        },
        "line_items": [...],
        "summary": [...]
    }
}
```

### data_extractors.py

New methods in `InvoiceExtractor`:
- `_extract_subject(text, line_items)` - Extract invoice subject
- `_detect_item_type(description)` - Detect per-item type
- `_determine_overall_item_type(line_items)` - Overall invoice type
- `_detect_isdoc(text)` - Detect ISDOC XML

### accounting_db.py

New columns in `invoices` table:
```sql
subject TEXT,                    -- Předmět faktury
item_type TEXT DEFAULT "goods",  -- service/goods/mixed
is_isdoc INTEGER DEFAULT 0,      -- 1 if ISDOC format
isdoc_version TEXT,              -- ISDOC version
isdoc_uuid TEXT                  -- ISDOC UUID
```

## Paperless Custom Fields

| Field | ID | Type | Description |
|-------|-----|------|-------------|
| invoice_subject | 23 | string | Předmět faktury |
| item_type | 24 | select | service/goods/mixed |
| is_isdoc | 25 | boolean | Is ISDOC format |
| isdoc_version | 26 | string | ISDOC version |
| isdoc_uuid | 27 | string | ISDOC UUID |

## Usage Example

```python
from src.ocr.data_extractors import InvoiceExtractor

extractor = InvoiceExtractor()
result = extractor.extract(invoice_text)

print(result['subject'])      # "ChatGPT Plus API - November 2024"
print(result['item_type'])    # "service"
print(result['isdoc'])        # {'is_isdoc': True, 'version': '6.0.2'}
```

## Migration

For existing documents, run re-extraction to populate new fields:
```bash
python3 reprocess_invoices.py --update-fields subject,item_type,isdoc
```

## Changelog

- **v1.1.0** (2025-12-27): Added subject, item_type, ISDOC detection
- **v1.0.0** (2025-11-30): Initial release with line items extraction
