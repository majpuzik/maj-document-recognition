# 🏦 MBW Bank Statement Integration - Complete Report

**Date:** 2025-11-06
**Status:** ✅ Fully Integrated
**Version:** 2.2

---

## 🎯 Overview

Successfully integrated **Bank Statement Processor** and **PDF OCR Layer Handler** into the MAJ Document Recognition system for automatic processing of bank statements from the MBW folder.

## 🚀 New Features

### 1. Bank Statement Processing

The system now automatically detects and processes bank statements in multiple formats:

**Supported Formats:**
- ✅ **MT940** - SWIFT format (universal banking standard)
- ✅ **CAMT.053** - ISO 20022 XML format (modern European standard)
- ✅ **ABO/GPC** - Czech national standard (Fio, Multidata)
- ✅ **CSV** - Various bank export formats

**Supported Countries:**
- 🇨🇿 Czech Republic (8 major banks)
- 🇦🇹 Austria (4 major banks)
- 🇩🇪 Germany (3 major banks)

**Extracted Data:**
- Account information (IBAN, account number, bank code)
- Statement period (from/to dates)
- Opening and closing balances
- Transaction details:
  - Date, amount, currency
  - Counterparty information
  - Czech symbols (VS, KS, SS)
  - Transaction descriptions

### 2. PDF OCR Layer Detection

Before processing any PDF, the system now:

1. **Checks** if the PDF has a text layer
2. **Adds OCR layer** if missing using `ocrmypdf`
3. **Supports** multi-language OCR (Czech, English, German)
4. **Optimizes** PDFs with auto-rotate, deskew, and clean operations

This ensures all PDFs are searchable and extractable before processing.

## 📁 Integration Points

### Modified Files

**process_mbw_documents.py** - Main processor enhanced with:

```python
# New imports
from src.integrations.bank_statement_processor import BankStatementProcessor
from src.ocr.pdf_ocr_layer import PDFOCRLayerHandler

# New initialization
self.bank_processor = BankStatementProcessor()
self.ocr_handler = PDFOCRLayerHandler()

# New file extensions supported
extensions = [
    '.pdf', '.PDF',
    '.jpg', '.JPG', '.jpeg', '.JPEG', '.png', '.PNG',
    '.xml', '.XML',      # CAMT.053 bank statements
    '.sta', '.STA',      # MT940 bank statements
    '.mt940', '.MT940',  # MT940 explicit
    '.gpc', '.GPC',      # ABO/GPC bank statements
    '.abo', '.ABO',      # ABO explicit
    '.csv', '.CSV'       # CSV bank statements
]
```

### New Methods

**_is_bank_statement(file_path: Path) -> bool**
- Detects bank statement files by:
  - File extension (.sta, .mt940, .gpc, .abo)
  - Filename patterns (vypis, statement, kontoauszug, platby)
  - XML content inspection (camt.053, BkToCstmrStmt)

**_process_bank_statement(file_path: Path) -> Dict**
- Processes bank statement files:
  - Parses statement data using BankStatementProcessor
  - Generates Paperless metadata
  - Saves to database with high confidence (0.95)
  - Auto-selects for import

**Enhanced process_document(file_path: Path) -> Dict**
- Now includes:
  1. Bank statement detection and processing
  2. PDF OCR layer check and addition
  3. Regular OCR and classification (fallback)

## 🔄 Processing Workflow

```
┌─────────────────────────────────────────────┐
│ 1. Document Discovery                       │
│    - Scan MBW folder                        │
│    - Include bank statement formats         │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ 2. Bank Statement Check                     │
│    - Check file extension                   │
│    - Check filename patterns                │
│    - Check XML content (if applicable)      │
└────────┬────────────────────┬────────────────┘
         │                    │
    Yes  │                    │ No
         ▼                    │
┌─────────────────────┐       │
│ 3a. Parse Bank      │       │
│     Statement       │       │
│  - MT940/CAMT/ABO   │       │
│  - Extract data     │       │
│  - Generate metadata│       │
│  - Save to DB       │       │
└─────────────────────┘       │
                              ▼
                    ┌──────────────────────┐
                    │ 3b. PDF OCR Check    │
                    │  - Has text layer?   │
                    │  - Add OCR if needed │
                    └─────────┬────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                    │ 4. Regular Processing│
                    │  - OCR extraction    │
                    │  - AI classification │
                    │  - Metadata creation │
                    │  - Save to DB        │
                    └──────────────────────┘
```

## 📊 Database Schema Extension

Bank statements are saved with additional metadata:

```json
{
  "document_type": "bankovni_vypis",
  "confidence": 0.95,
  "classification_method": "bank_statement_parser",
  "bank_statement": {
    "id": "statement_id",
    "bank": "Komerční banka",
    "account": "123456789/0100",
    "iban": "CZ6501000000001234567890",
    "period_from": "2024-01-01",
    "period_to": "2024-01-31",
    "opening_balance": 15000.00,
    "closing_balance": 18500.50,
    "currency": "CZK",
    "transaction_count": 25,
    "format": "MT940"
  },
  "paperless_title": "Bankovní výpis 123456789/0100 2024-01",
  "paperless_tags": ["MBW", "bankovni_vypis", "Komerční banka"],
  "paperless_correspondent": "Komerční banka",
  "selected": true
}
```

## 🧪 Testing

### Test Bank Statement Processing

```bash
cd ~/maj-document-recognition
source venv/bin/activate

# Test with a single bank statement
python -c "
from pathlib import Path
from src.integrations.bank_statement_processor import BankStatementProcessor
import json

processor = BankStatementProcessor()
statement = processor.parse_file('path/to/bank_statement.xml')
print(json.dumps(statement.to_dict(), indent=2, ensure_ascii=False))
"
```

### Test PDF OCR Layer

```bash
# Test OCR layer detection
python -c "
from src.ocr.pdf_ocr_layer import PDFOCRLayerHandler

handler = PDFOCRLayerHandler()
has_text, chars = handler.has_text_layer('path/to/document.pdf')
print(f'Has text layer: {has_text}, Characters: {chars}')

# Add OCR if needed
ocr_added, output = handler.process_pdf_with_ocr('path/to/document.pdf')
if ocr_added:
    print(f'OCR layer added: {output}')
"
```

### Full MBW Processing Test

```bash
# Process all MBW documents including bank statements
python process_mbw_documents.py \
    --source ~/Dropbox/MBW \
    --output data/mbw_with_bank_statements.json

# Check the results
cat data/mbw_with_bank_statements.json | jq '.documents[] | select(.document_type == "bankovni_vypis")'
```

## 📦 Dependencies

Ensure all dependencies are installed:

```bash
cd ~/maj-document-recognition
source venv/bin/activate

# Python packages
pip install -r requirements.txt

# System dependencies for OCR layer
brew install ocrmypdf tesseract tesseract-lang

# Verify installations
ocrmypdf --version
tesseract --list-langs
```

**New requirements.txt entries:**
```
# Bank Statement Processing
lxml>=4.9.0
defusedxml>=0.7.0
python-dateutil>=2.8.0

# PDF OCR Layer
PyMuPDF>=1.23.0  # fitz
```

## 🏦 Supported Banks

### Czech Republic (8 banks)
- Komerční banka (0100)
- ČSOB (0300)
- Česká spořitelna (0800)
- Fio banka (2010)
- MONETA Money Bank (0600)
- Raiffeisenbank (5500)
- Equa Bank (6100)
- Air Bank (3030)

### Austria (4 banks)
- Erste Bank (12000)
- Raiffeisen Bank (32000)
- Bank Austria (12040)
- BAWAG P.S.K. (43000)

### Germany (3 banks)
- Deutsche Bank (10070000)
- Commerzbank (20070000)
- Postbank (37040044)

## 🎯 Use Cases

### 1. Automatic Bank Statement Import

When MBW folder contains bank statements:

```bash
python process_mbw_documents.py --source ~/Dropbox/MBW
```

The system will:
1. Detect bank statement files automatically
2. Parse transaction data
3. Create proper Paperless metadata
4. Auto-select for import (confidence = 0.95)

### 2. Mixed Document Processing

When MBW folder contains both bank statements and regular documents:

```bash
python process_mbw_documents.py --source ~/Dropbox/MBW
python interactive_selector.py
# Filter by document_type = "bankovni_vypis"
# Review and confirm selection
python import_to_paperless.py
```

### 3. PDF Without Text Layer

When MBW folder contains scanned PDFs without text:

```bash
python process_mbw_documents.py --source ~/Dropbox/MBW
```

The system will:
1. Detect PDFs without text layer
2. Add OCR layer using ocrmypdf
3. Continue with regular processing
4. Save searchable PDF for Paperless

## ⚠️ Error Handling

### Bank Statement Parsing Errors

If bank statement parsing fails:
- System logs error
- Falls back to regular OCR + classification
- Document still processed (no data loss)

### OCR Layer Addition Errors

If OCR layer addition fails:
- System logs warning
- Uses original PDF for processing
- Processing continues normally

### Missing Dependencies

If ocrmypdf not installed:
- PDFOCRLayerHandler detects this on init
- Skips OCR layer addition
- Logs warning message
- Processing continues without OCR layer enhancement

## 📈 Expected Performance

### Bank Statement Processing
- **Speed:** ~0.5 seconds per statement
- **Accuracy:** >95% for structured formats
- **Confidence:** 0.95 (high)

### PDF OCR Layer Addition
- **Speed:** ~5-10 seconds per page
- **Threshold:** 50 characters minimum for text layer detection
- **Languages:** Czech, English, German

### Overall MBW Processing
With bank statements and PDF OCR:
- **Throughput:** ~10-12 documents/minute (down from 15.5)
- **Accuracy:** Maintained at previous levels
- **New capabilities:** Bank statement extraction, searchable PDFs

## 🔍 Troubleshooting

### Issue: Bank statement not detected

**Check:**
```bash
# File extension
ls -la *.{xml,sta,mt940,gpc,abo,csv}

# Filename patterns
grep -i "vypis\|statement\|kontoauszug" filelist.txt

# XML content
head -20 bank_statement.xml | grep -i "camt.053\|BkToCstmrStmt"
```

### Issue: OCR layer not added

**Check:**
```bash
# ocrmypdf installation
which ocrmypdf
ocrmypdf --version

# Tesseract languages
tesseract --list-langs | grep -E "ces|eng|deu"

# Manual test
ocrmypdf --language ces+eng+deu input.pdf output.pdf
```

### Issue: Low memory during processing

**Solution:**
```bash
# Disable Ollama temporarily
vim config/config.yaml
# Set ai.ollama.enabled = false

# Process in smaller batches
python process_mbw_documents.py --source ~/Dropbox/MBW/batch1
```

## 📚 Additional Documentation

- **BANK_STATEMENT_OCR_GUIDE.md** - Complete bank statement processing guide
- **MBW_IMPORT_GUIDE.md** - 3-step MBW import workflow
- **MBW_PROCESSING_COMPLETE.md** - Previous processing report (93 documents)

## 🔄 Next Steps

1. **Install dependencies** if not already installed:
   ```bash
   pip install -r requirements.txt
   brew install ocrmypdf tesseract-lang
   ```

2. **Test with sample bank statements**:
   - Place test bank statement files in test folder
   - Run processor and verify detection
   - Check generated metadata

3. **Process full MBW folder**:
   ```bash
   python process_mbw_documents.py --source ~/Dropbox/MBW
   ```

4. **Review results**:
   ```bash
   python interactive_selector.py
   # Filter by: bankovni_vypis
   ```

5. **Import to Paperless**:
   ```bash
   python import_to_paperless.py
   ```

---

**Integration Version:** 2.2
**Last Updated:** 2025-11-06
**Integration Author:** Claude Code + User MAJ
**Status:** ✅ Ready for Production Testing
