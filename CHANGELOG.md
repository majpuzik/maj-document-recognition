# Changelog

All notable changes to maj-document-recognition.

## [1.1.0] - 2025-12-27

### Added

#### Invoice Fields v1.1
Nová pole pro extrakci faktur:

| Pole | Typ | Popis |
|------|-----|-------|
| `invoice_subject` | string | Předmět faktury - souhrn položek |
| `item_type` | enum | Klasifikace: `service`, `goods`, `mixed` |
| `is_isdoc` | boolean | Dokument je ISDOC XML |
| `isdoc_version` | string | Verze ISDOC (např. 6.0.2) |
| `isdoc_uuid` | string | UUID ISDOC dokumentu |

#### Dynamic Paperless Field Lookup
- `load_field_ids(api_url, token)` - Runtime načtení field IDs z Paperless API
- `get_field_id(field_name)` - Získání ID podle jména
- Žádné hardcoded instance-specific IDs
- Funguje na libovolné Paperless instanci

### Changed
- `format_for_paperless()` - Používá dynamický lookup místo hardcoded IDs
- `INVOICE_LINE_ITEMS_SCHEMA` - Rozšířeno o nová pole

### Files Modified
- `src/ocr/extraction_schemas.py` - Schema + dynamic lookup
- `src/ocr/data_extractors.py` - Extraction metody

### Paperless Custom Fields

#### DGX (spark-47f9)
| Pole | ID |
|------|-----|
| invoice_subject | 31 |
| item_type | 30 |
| is_isdoc | 150 |
| isdoc_version | 151 |
| isdoc_uuid | 152 |

#### Dell-WS
| Pole | ID |
|------|-----|
| invoice_subject | 23 |
| item_type | 24 |
| is_isdoc | 25 |
| isdoc_version | 26 |
| isdoc_uuid | 27 |

---

## [1.0.0] - 2025-11-30

### Added
- Initial release
- OCR extraction (Tesseract, EasyOCR)
- Invoice line items extraction
- Bank statement parsing
- Receipt extraction with EET
- Paperless-NGX integration
