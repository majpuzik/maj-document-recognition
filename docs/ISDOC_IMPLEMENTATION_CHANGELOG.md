# ISDOC Implementation for Paperless-NGX
## Changelog - December 7, 2025

### Summary
Added ISDOC 6.0.2 XML generation layer for all accounting documents in Paperless-NGX.
This creates standardized Czech electronic invoice format files alongside original documents.

### New Files Created

#### 1. `llm_metadata_extractor.py` (37.7 KB)
Extended metadata extractor with ISDOC generation capabilities:
- **ISDOCInvoiceData** dataclass - structured invoice data model
- **ISDOCGenerator** class - generates ISDOC 6.0.2 XML
- Regex patterns for Czech financial documents:
  - IČO (8-digit company ID)
  - DIČ (VAT number CZ + 8-10 digits)
  - Invoice numbers (multiple patterns)
  - Bank accounts (IBAN, local format)
  - Variable symbols
  - Amounts with VAT

#### 2. `generate_isdoc_for_all.py` (7.1 KB)
Repair script for processing existing documents:
- Dry-run mode (default) for preview
- `--apply` flag for actual generation
- `--types` filter for document types
- `--limit` for batch processing
- `--skip-existing` to avoid duplicates
- `--use-llm` for enhanced extraction

#### 3. `isdoc_generator_inline.py` (4.7 KB)
Inline script for Docker container execution:
- Self-contained Django setup
- Direct Document model access
- Simplified ISDOC generation
- Compatible with Paperless-NGX container

### ISDOC XML Format (6.0.2)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="http://isdoc.cz/namespace/2013" version="6.0.2">
  <DocumentType>1</DocumentType>
  <ID>invoice-number</ID>
  <UUID>document-id</UUID>
  <IssueDate>YYYY-MM-DD</IssueDate>
  <LocalCurrencyCode>CZK</LocalCurrencyCode>
  <AccountingSupplierParty>
    <Party>
      <PartyIdentification><ID>ICO</ID></PartyIdentification>
    </Party>
  </AccountingSupplierParty>
  <LegalMonetaryTotal>
    <TaxInclusiveAmount>amount</TaxInclusiveAmount>
    <PayableAmount>amount</PayableAmount>
  </LegalMonetaryTotal>
</Invoice>
```

### Execution Results
- **Total documents scanned**: 1,206
- **Accounting documents identified**: 76
- **ISDOC files generated**: 76
- **Output directory**: /usr/src/paperless/media/isdoc/

### Document Types Processed
- Faktury (invoices)
- Účtenky (receipts)  
- Dobropisy (credit notes)
- Proforma faktury
- Daňové doklady

### Integration Points
- Paperless-NGX document consumer
- LLM-based metadata extraction
- PostgreSQL database on DGX
- GPU-accelerated OCR

### Files Location on DGX
```
/home/puzik/paperless-ngx-gpu/
├── deploy.sh                    # Deployment script
├── docker-compose.yml           # PostgreSQL + GPU config
├── fix_document_dates.py        # Date correction utility
├── generate_isdoc_for_all.py    # ISDOC repair script
├── isdoc_generator_inline.py    # Inline ISDOC generator
├── llm_metadata_extractor.py    # Extended with ISDOC
└── merge_instances.py           # SQLite merger

/usr/src/paperless/media/isdoc/  # Inside container
└── *.isdoc                      # 76 generated files
```

### Usage Examples
```bash
# Dry run (preview)
docker exec -it paperless-ngx python /usr/src/paperless/scripts/generate_isdoc_for_all.py

# Generate ISDOC files
docker exec -it paperless-ngx python /usr/src/paperless/scripts/generate_isdoc_for_all.py --apply

# With LLM extraction
docker exec -it paperless-ngx python /usr/src/paperless/scripts/generate_isdoc_for_all.py --apply --use-llm

# Limit to 100 documents
docker exec -it paperless-ngx python /usr/src/paperless/scripts/generate_isdoc_for_all.py --apply --limit 100
```

### Related Changes
- Merged 13 SQLite instances into PostgreSQL
- Imported 1,206 documents with corrected dates
- LLM metadata extraction integrated
- GPU-accelerated processing on DGX

---
Generated: $(date +%Y-%m-%d)
Author: Claude Code Assistant
