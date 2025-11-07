# API Dokumentace - MAJ Document Recognition

## Obsah

1. [Python API](#python-api)
2. [Web API (REST)](#web-api-rest)
3. [Příklady použití](#příklady-použití)

## Python API

### OCR Module

#### DocumentProcessor

```python
from src.ocr.document_processor import DocumentProcessor

# Inicializace
processor = DocumentProcessor(config)

# Zpracování dokumentu
result = processor.process_document("/path/to/document.pdf")

# Vrací:
{
    "success": True,
    "text": "Extrahovaný text...",
    "confidence": 95.5,
    "page_count": 1,
    "format": "pdf",
    "metadata": {...}
}
```

#### TextExtractor

```python
from src.ocr.text_extractor import TextExtractor

extractor = TextExtractor(config)

# Extrakce z obrázku
result = extractor.extract_from_image("/path/to/image.jpg")

# Extrakce z PDF
result = extractor.extract_from_pdf("/path/to/document.pdf")

# Extrakce z DOCX
result = extractor.extract_from_docx("/path/to/document.docx")

# Auto-detekce formátu
result = extractor.extract("/path/to/document")
```

### AI Module

#### AIClassifier

```python
from src.ai.classifier import AIClassifier

classifier = AIClassifier(config, db_manager)

# Klasifikace textu
classification = classifier.classify(
    text="Text dokumentu...",
    metadata={"file_path": "/path/to/doc"}
)

# Vrací:
{
    "type": "faktura",
    "confidence": 0.95,
    "method": "ensemble",
    "individual_results": [...]
}

# Pouze keywords
result = classifier.classify_with_keywords(text)

# Pouze Ollama
result = classifier.classify_with_ollama(text, metadata)
```

#### MLModel

```python
from src.ai.ml_model import MLModel

ml_model = MLModel(config, db_manager)

# Trénování modelu
texts = ["Text 1", "Text 2", ...]
labels = ["faktura", "stvrzenka", ...]
ml_model.train(texts, labels)

# Predikce
result = ml_model.predict("Nový text k klasifikaci")

# Vrací:
{
    "success": True,
    "type": "faktura",
    "confidence": 0.89,
    "probabilities": {
        "faktura": 0.89,
        "stvrzenka": 0.08,
        "jine": 0.03
    }
}

# Auto-trénování z databáze
ml_model.auto_train_from_db()
```

#### ReklamniFiltr

```python
from src.ai.reklamni_filtr import ReklamniFiltr

ad_filter = ReklamniFiltr(config)

# Detekce reklamy
result = ad_filter.is_advertisement("Text emailu...")

# Vrací:
{
    "is_ad": True,
    "confidence": 0.92,
    "keyword_matches": 5,
    "pattern_matches": 2
}

# Extrakce features
features = ad_filter.extract_ad_features(text)
```

#### SoudniFiltr

```python
from src.ai.soudni_filtr import SoudniFiltr

legal_filter = SoudniFiltr(config)

# Detekce právního dokumentu
result = legal_filter.is_legal_document("Text dokumentu...")

# Vrací:
{
    "is_legal": True,
    "confidence": 0.88,
    "keyword_matches": 3,
    "pattern_matches": 2,
    "court_matches": 1
}

# Extrakce features
features = legal_filter.extract_legal_features(text)
```

### Database Module

#### DatabaseManager

```python
from src.database.db_manager import DatabaseManager

db = DatabaseManager(config)

# Vložení dokumentu
doc_id = db.insert_document(
    file_path="/path/to/doc.pdf",
    ocr_text="Extrahovaný text",
    ocr_confidence=95.5,
    document_type="faktura",
    ai_confidence=0.9,
    sender="email@example.com"
)

# Získání dokumentu
document = db.get_document(doc_id)

# Seznam všech dokumentů
documents = db.get_all_documents(
    limit=50,
    offset=0,
    document_type="faktura",
    sender="example.com"
)

# Update dokumentu
db.update_document(doc_id, document_type="stvrzenka")

# Označení jako synchronizované
db.mark_document_synced(doc_id, paperless_id=123)

# Nesynchronizované dokumenty
unsynced = db.get_unsynced_documents()

# Dokumenty pro trénování
labeled = db.get_labeled_documents()

# Statistiky
stats = db.get_statistics()
```

### Integrations Module

#### ThunderbirdIntegration

```python
from src.integrations.thunderbird import ThunderbirdIntegration

tb = ThunderbirdIntegration(config)

# Skenování emailů
emails = tb.scan_emails(
    days_back=30,
    mailboxes=["INBOX", "Archive"]
)

# Vrací:
[
    {
        "id": "unique_id",
        "sender": "email@example.com",
        "subject": "Subject",
        "date": "...",
        "attachments": ["/path/to/attachment1.pdf", ...]
    },
    ...
]

# Seskupení podle odesílatele
grouped = tb.group_by_sender(emails)

# Cleanup temp souborů
tb.cleanup_temp_files()
```

#### PaperlessAPI

```python
from src.integrations.paperless_api import PaperlessAPI

paperless = PaperlessAPI(config)

# Test spojení
if paperless.test_connection():
    print("Connected to Paperless-NGX")

# Upload dokumentu
result = paperless.upload_document(
    file_path="/path/to/document.pdf",
    title="Faktura 123",
    document_type="Invoice",
    correspondent="Dodavatel XYZ",
    tags=["AI-Classified", "2024"]
)

# Check duplicates
existing = paperless.check_duplicate("/path/to/document.pdf")

# Get or create entities
tag_id = paperless.get_or_create_tag("TagName")
correspondent_id = paperless.get_or_create_correspondent("Correspondent")
doc_type_id = paperless.get_or_create_document_type("Document Type")
```

#### BlacklistWhitelist

```python
from src.integrations.blacklist_whitelist import BlacklistWhitelist

bl_wl = BlacklistWhitelist(config)

# Přidání do blacklistu
bl_wl.add_to_blacklist("spam@example.com")
bl_wl.add_to_blacklist("example.com")  # Celá doména

# Přidání do whitelistu
bl_wl.add_to_whitelist("trusted@example.com")

# Kontrola
if bl_wl.is_blacklisted("spam@example.com"):
    print("Blacklisted!")

if bl_wl.is_whitelisted("trusted@example.com"):
    print("Whitelisted!")

# Odebrání
bl_wl.remove_from_blacklist("spam@example.com")

# Získání seznamů
blacklist = bl_wl.get_blacklist()
whitelist = bl_wl.get_whitelist()

# Export/Import
data = bl_wl.export_to_dict()
bl_wl.import_from_dict(data)
```

## Web API (REST)

Base URL: `http://localhost:5000/api`

### Documents

#### GET /api/documents
Získání seznamu dokumentů

**Query Parameters:**
- `limit` (int): Maximální počet dokumentů
- `offset` (int): Offset pro stránkování
- `type` (string): Filtr podle typu
- `sender` (string): Filtr podle odesílatele

**Response:**
```json
{
  "success": true,
  "count": 50,
  "documents": [
    {
      "id": 1,
      "file_name": "document.pdf",
      "document_type": "faktura",
      "ai_confidence": 0.95,
      "created_at": "2024-01-01T12:00:00"
    }
  ]
}
```

#### GET /api/documents/:id
Získání konkrétního dokumentu

**Response:**
```json
{
  "success": true,
  "document": {
    "id": 1,
    "file_path": "/path/to/document.pdf",
    "ocr_text": "Extrahovaný text...",
    "document_type": "faktura",
    ...
  }
}
```

#### PUT /api/documents/:id
Update dokumentu

**Request Body:**
```json
{
  "document_type": "stvrzenka",
  "user_confirmed": 1
}
```

**Response:**
```json
{
  "success": true
}
```

#### POST /api/upload
Upload a zpracování dokumentu

**Form Data:**
- `file`: Soubor k uploadu

**Response:**
```json
{
  "success": true,
  "document_id": 123,
  "classification": {
    "type": "faktura",
    "confidence": 0.95,
    "method": "ensemble"
  }
}
```

### Thunderbird

#### POST /api/thunderbird/scan
Skenování Thunderbird

**Request Body:**
```json
{
  "days_back": 30
}
```

**Response:**
```json
{
  "success": true,
  "count": 25,
  "emails": [...]
}
```

### Paperless-NGX

#### POST /api/paperless/sync
Synchronizace s Paperless-NGX

**Response:**
```json
{
  "success": true,
  "total": 10,
  "synced": 8
}
```

### Blacklist/Whitelist

#### GET /api/blacklist
Získání blacklistu

**Response:**
```json
{
  "success": true,
  "blacklist": ["spam@example.com", "ads.com"]
}
```

#### POST /api/blacklist
Přidání do blacklistu

**Request Body:**
```json
{
  "email": "spam@example.com"
}
```

#### GET /api/whitelist
Získání whitelistu

#### POST /api/whitelist
Přidání do whitelistu

### Statistics

#### GET /api/statistics
Získání statistik

**Response:**
```json
{
  "success": true,
  "statistics": {
    "total_documents": 100,
    "synced_documents": 80,
    "training_samples": 50,
    "by_type": {
      "faktura": 40,
      "stvrzenka": 30,
      "jine": 30
    }
  }
}
```

## Příklady použití

### Kompletní workflow

```python
import yaml
from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.paperless_api import PaperlessAPI

# Load config
with open("config/config.yaml") as f:
    config = yaml.safe_load(f)

# Initialize
db = DatabaseManager(config)
processor = DocumentProcessor(config)
classifier = AIClassifier(config, db)
paperless = PaperlessAPI(config)

# Process document
file_path = "/path/to/invoice.pdf"

# 1. OCR
ocr_result = processor.process_document(file_path)
print(f"OCR Confidence: {ocr_result['confidence']:.1f}%")

# 2. Klasifikace
classification = classifier.classify(
    ocr_result["text"],
    ocr_result["metadata"]
)
print(f"Type: {classification['type']}")
print(f"AI Confidence: {classification['confidence']:.2%}")

# 3. Uložení do DB
doc_id = db.insert_document(
    file_path=file_path,
    ocr_text=ocr_result["text"],
    ocr_confidence=ocr_result["confidence"],
    document_type=classification["type"],
    ai_confidence=classification["confidence"],
    ai_method=classification["method"]
)

# 4. Export do Paperless
result = paperless.upload_document(
    file_path=file_path,
    title=f"Document {doc_id}",
    document_type=classification["type"],
    tags=["AI-Classified"]
)

if result["success"]:
    db.mark_document_synced(doc_id, result["paperless_id"])
    print(f"Synced to Paperless-NGX (ID: {result['paperless_id']})")
```

### Batch processing

```python
import glob
from pathlib import Path

# Get all PDFs in directory
pdf_files = glob.glob("/path/to/documents/*.pdf")

results = []
for pdf_file in pdf_files:
    try:
        # Process
        ocr_result = processor.process_document(pdf_file)
        classification = classifier.classify(ocr_result["text"])

        # Save
        doc_id = db.insert_document(
            file_path=pdf_file,
            ocr_text=ocr_result["text"],
            document_type=classification["type"],
            ai_confidence=classification["confidence"]
        )

        results.append({
            "file": Path(pdf_file).name,
            "type": classification["type"],
            "confidence": classification["confidence"]
        })

    except Exception as e:
        print(f"Error processing {pdf_file}: {e}")

# Summary
print(f"\nProcessed {len(results)} documents:")
for r in results:
    print(f"- {r['file']}: {r['type']} ({r['confidence']:.2%})")
```

### Custom classifier

```python
from src.ai.classifier import AIClassifier

class CustomClassifier(AIClassifier):
    def classify_invoice(self, text):
        """Custom invoice classification logic"""
        # Your custom logic here
        if "faktura" in text.lower() and "IČO" in text:
            return {
                "type": "faktura",
                "confidence": 0.99,
                "method": "custom"
            }
        return super().classify(text)

# Use custom classifier
custom_classifier = CustomClassifier(config, db)
result = custom_classifier.classify_invoice(text)
```
