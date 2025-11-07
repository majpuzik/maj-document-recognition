# 🏦 Bankovní výpisy + OCR Layer - Implementace

Kompletní systém pro zpracování bankovních výpisů s automatickým přidáním OCR vrstvy do PDF.

## 🎯 Funkce

### 1. Bank Statement Processor
Univerzální parser podporující:

**Formáty:**
- ✅ **MT940** - SWIFT formát (všechny banky CZ, AT, DE)
- ✅ **CAMT.053** - ISO 20022 XML (moderní evropské banky)
- ✅ **CSV** - Komerční banka, ČSOB, Erste, Deutsche Bank
- ✅ **ABO/GPC** - Český národní standard (Fio, Multidata)

**Podporované země:**
- 🇨🇿 Česká republika
- 🇦🇹 Rakousko  
- 🇩🇪 Německo

**Extrahovaná data:**
- Číslo účtu, IBAN, kód banky
- Období výpisu (od-do)
- Počáteční a konečný zůstatek
- Detaily transakcí:
  - Datum, částka, měna
  - Protistrana (jméno, účet, banka)
  - České symboly (VS, KS, SS)
  - Popis transakce

### 2. PDF OCR Layer Handler
Automatická detekce a přidání OCR vrstvy do PDF:

**Funkce:**
- ✅ Detekce existence textové vrstvy v PDF
- ✅ Automatické přidání OCR pomocí `ocrmypdf`
- ✅ Podpora českého, anglického a německého jazyka
- ✅ Optimalizace a vyčištění stránek
- ✅ Auto-rotate a deskew
- ✅ Batch processing celých složek

## 📦 Instalace závislostí

### Základní závislosti

```bash
cd ~/maj-document-recognition
source venv/bin/activate

# Python balíčky
pip install PyMuPDF  # fitz - PDF manipulation
pip install lxml defusedxml  # XML parsing
pip install python-dateutil  # Date parsing

# OCRmyPDF pro přidání OCR vrstvy
brew install ocrmypdf tesseract tesseract-lang

# Nebo na Linux:
# sudo apt-get install ocrmypdf tesseract-ocr tesseract-ocr-ces tesseract-ocr-deu
```

## 🚀 Použití

### Příklad 1: Zpracování bankovního výpisu

```python
from src.integrations.bank_statement_processor import BankStatementProcessor

# Initialize processor
processor = BankStatementProcessor()

# Parse bank statement (auto-detects format)
statement = processor.parse_file("vypis.mt940")

# Print info
print(f"Bank: {statement.bank_name}")
print(f"Account: {statement.account_number}")
print(f"Period: {statement.from_date} - {statement.to_date}")
print(f"Opening balance: {statement.opening_balance} {statement.currency}")
print(f"Closing balance: {statement.closing_balance} {statement.currency}")
print(f"Transactions: {len(statement.transactions)}")

# Export to JSON
import json
with open('statement.json', 'w') as f:
    json.dump(statement.to_dict(), f, indent=2, ensure_ascii=False)

# Generate Paperless metadata
metadata = processor.generate_paperless_metadata(statement)
print(f"Paperless title: {metadata['title']}")
print(f"Tags: {metadata['tags']}")
```

### Příklad 2: OCR layer detection a přidání

```python
from src.ocr.pdf_ocr_layer import PDFOCRLayerHandler

# Initialize handler
ocr_handler = PDFOCRLayerHandler()

# Check if PDF has text layer
has_text, char_count = ocr_handler.has_text_layer("document.pdf")
print(f"Has text layer: {has_text} ({char_count} characters)")

# Add OCR layer if needed
ocr_added, output_path = ocr_handler.process_pdf_with_ocr("document.pdf")
if ocr_added:
    print(f"✅ OCR layer added: {output_path}")
else:
    print(f"📄 PDF already has text layer")
```

### Příklad 3: Batch processing složky s bankovními výpisy

```python
from pathlib import Path
from src.integrations.bank_statement_processor import BankStatementProcessor
from src.ocr.pdf_ocr_layer import PDFOCRLayerHandler

# Initialize
processor = BankStatementProcessor()
ocr_handler = PDFOCRLayerHandler()

# Find all bank statement files
statements_dir = Path("~/Dropbox/MBW").expanduser()
files = list(statements_dir.glob("*.{pdf,xml,sta,csv}"))

results = []

for file in files:
    print(f"\nProcessing: {file.name}")
    
    # If PDF, ensure it has OCR layer
    if file.suffix.lower() == '.pdf':
        ocr_added, ocr_file = ocr_handler.process_pdf_with_ocr(str(file))
        file_to_process = ocr_file
    else:
        file_to_process = str(file)
    
    # Try to parse as bank statement
    try:
        statement = processor.parse_file(file_to_process)
        
        # Generate Paperless metadata
        metadata = processor.generate_paperless_metadata(statement)
        
        results.append({
            "file": file.name,
            "success": True,
            "statement_id": statement.statement_id,
            "transactions": len(statement.transactions),
            "metadata": metadata
        })
        
        print(f"✅ Parsed: {len(statement.transactions)} transactions")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        results.append({
            "file": file.name,
            "success": False,
            "error": str(e)
        })

# Save results
import json
with open('bank_statements_processed.json', 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
```

## 🔧 Integrace s MBW procesorem

Upravený `process_mbw_documents.py` s podporou bank statements a OCR:

```python
# Na začátku souboru přidat:
from src.integrations.bank_statement_processor import BankStatementProcessor
from src.ocr.pdf_ocr_layer import PDFOCRLayerHandler

class MBWDocumentProcessor:
    def __init__(self, config_path: str = "config/config.yaml"):
        # ... existing code ...
        
        # Add bank statement processor
        self.bank_processor = BankStatementProcessor()
        
        # Add OCR layer handler
        self.ocr_handler = PDFOCRLayerHandler()
    
    def process_document(self, file_path: Path) -> Dict:
        # ... existing code ...
        
        # NEW: If PDF, ensure OCR layer exists
        if file_path.suffix.lower() == '.pdf':
            ocr_added, ocr_file = self.ocr_handler.process_pdf_with_ocr(str(file_path))
            if ocr_added:
                self.logger.info(f"🔍 OCR layer added to {file_path.name}")
                # Use OCR'd version for further processing
                file_path = Path(ocr_file)
        
        # NEW: Try to parse as bank statement first
        if self._is_bank_statement(file_path):
            return self._process_bank_statement(file_path)
        
        # Continue with regular OCR + classification
        # ... existing code ...
    
    def _is_bank_statement(self, file_path: Path) -> bool:
        """Check if file might be a bank statement"""
        # Check file extension
        if file_path.suffix.lower() in ['.sta', '.mt940', '.gpc', '.abo']:
            return True
        
        # Check filename patterns
        filename_lower = file_path.name.lower()
        if any(pattern in filename_lower for pattern in 
              ['vypis', 'statement', 'kontoauszug', 'platby']):
            return True
        
        # For XML, check content
        if file_path.suffix.lower() == '.xml':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(1000)  # First 1000 chars
                    if 'camt.053' in content or 'BkToCstmrStmt' in content:
                        return True
            except:
                pass
        
        return False
    
    def _process_bank_statement(self, file_path: Path) -> Dict:
        """Process bank statement file"""
        self.logger.info(f"📊 Processing as bank statement: {file_path.name}")
        
        try:
            # Parse bank statement
            statement = self.bank_processor.parse_file(str(file_path))
            
            # Generate Paperless metadata
            paperless_meta = self.bank_processor.generate_paperless_metadata(statement)
            
            # File metadata
            stat = file_path.stat()
            
            result = {
                "success": True,
                "file_path": str(file_path),
                "file_name": file_path.name,
                "file_size": stat.st_size,
                "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
                "file_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                
                # Bank statement specific
                "document_type": "bankovni_vypis",
                "confidence": 0.95,  # High confidence for structured data
                "classification_method": "bank_statement_parser",
                
                # Bank statement data
                "bank_statement": {
                    "id": statement.statement_id,
                    "bank": statement.bank_name,
                    "account": statement.account_number,
                    "iban": statement.iban,
                    "period_from": statement.from_date.isoformat() if statement.from_date else None,
                    "period_to": statement.to_date.isoformat() if statement.to_date else None,
                    "opening_balance": float(statement.opening_balance),
                    "closing_balance": float(statement.closing_balance),
                    "currency": statement.currency,
                    "transaction_count": len(statement.transactions),
                    "format": statement.original_format
                },
                
                # Paperless metadata
                "paperless_title": paperless_meta['title'],
                "paperless_tags": paperless_meta['tags'],
                "paperless_correspondent": paperless_meta['correspondent'],
                
                # Auto-select high confidence documents
                "selected": True,
            }
            
            # Save to DB
            doc_id = self.db_manager.insert_document(
                file_path=str(file_path),
                ocr_text=f"Bank statement: {statement.account_number}, {len(statement.transactions)} transactions",
                ocr_confidence=0.95,
                document_type="bankovni_vypis",
                ai_confidence=0.95,
                ai_method="bank_statement_parser",
                metadata=result
            )
            result["db_id"] = doc_id
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing bank statement: {e}")
            # Fall back to regular processing
            return None
```

## 📊 Podporované banky

### Česká republika
| Banka | Kód | Formáty |
|-------|-----|---------|
| Komerční banka | 0100 | MT940, CSV |
| ČSOB | 0300 | MT940, CAMT.053 |
| Česká spořitelna | 0800 | MT940, CSV |
| Fio banka | 2010 | ABO, CSV |
| MONETA Money Bank | 0600 | MT940, CSV |
| Raiffeisenbank | 5500 | MT940, CAMT.053 |

### Rakousko
| Banka | Kód | Formáty |
|-------|-----|---------|
| Erste Bank | 12000 | MT940, CAMT.053 |
| Raiffeisen Bank | 32000 | MT940, CSV |
| Bank Austria | 12040 | CAMT.053 |
| BAWAG P.S.K. | 43000 | CSV, MT940 |

### Německo
| Banka | Kód | Formáty |
|-------|-----|---------|
| Deutsche Bank | 10070000 | MT940, CAMT.053 |
| Commerzbank | 20070000 | MT940, CSV |
| Postbank | 37040044 | MT940, CSV |

## 🧪 Testování

```bash
cd ~/maj-document-recognition
source venv/bin/activate

# Test bank statement parsing
python -c "
from src.integrations.bank_statement_processor import BankStatementProcessor
import json

processor = BankStatementProcessor()
statement = processor.parse_file('test_data/vypis.mt940')
print(json.dumps(statement.to_dict(), indent=2, ensure_ascii=False))
"

# Test OCR layer detection
python -c "
from src.ocr.pdf_ocr_layer import PDFOCRLayerHandler

handler = PDFOCRLayerHandler()
has_text, chars = handler.has_text_layer('test.pdf')
print(f'Has text: {has_text}, Characters: {chars}')
"
```

## 📝 Výstupní formát pro Paperless

```json
{
  "title": "Bankovní výpis 123456789/0100 2024-01",
  "document_type": "bankovni_vypis",
  "tags": ["bankovní_výpis", "Komerční banka"],
  "correspondent": "Komerční banka",
  "date": "2024-01-31",
  "custom_fields": {
    "account_number": "123456789/0100",
    "iban": "CZ6501000000001234567890",
    "period_from": "2024-01-01",
    "period_to": "2024-01-31",
    "opening_balance": 15000.00,
    "closing_balance": 18500.50,
    "transaction_count": 25,
    "currency": "CZK"
  }
}
```

## ⚠️ Troubleshooting

### OCRmyPDF chyby

```bash
# Check installation
ocrmypdf --version

# Check tesseract languages
tesseract --list-langs

# Install missing languages
brew install tesseract-lang
```

### Bank statement parsing chyby

```bash
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check format detection
processor = BankStatementProcessor()
with open('vypis.txt', 'r') as f:
    content = f.read()
format_type = processor.detect_format(content)
print(f"Detected format: {format_type}")
```

## 📚 Dodatečné zdroje

- [MT940 Format Specification](https://www.swift.com/standards/mt-messages/mt940)
- [ISO 20022 CAMT.053](https://www.iso20022.org/)
- [OCRmyPDF Documentation](https://ocrmypdf.readthedocs.io/)
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)

---

**Version:** 1.0.0  
**Last Updated:** 2025-11-06  
**Author:** MAJ + Claude Code
