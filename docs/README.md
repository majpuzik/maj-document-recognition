# MAJ Document Recognition

Kompletní OCR systém pro automatickou klasifikaci dokumentů s AI integrací, Thunderbird a Paperless-NGX podporou.

## Funkce

### 🔍 OCR Klasifikace
- Automatická detekce typu dokumentu (faktura, stvrzenka, bankovní výpis, právní dokument, reklama)
- Vícejazyčná podpora (čeština, němčina, angličtina)
- Pokročilé předzpracování obrázků pro lepší OCR výsledky
- Podpora formátů: PDF, JPG, PNG, DOCX

### 🤖 AI Systémy
- **Ollama integrace** - LLM klasifikace pomocí lokálního AI modelu
- **Vlastní ML model** - TF-IDF + Naive Bayes s automatickým učením
- **Reklamní filtr** - Detekce reklamních emailů a newsletterů
- **Soudní filtr** - Identifikace právních dokumentů
- **Ensemble klasifikace** - Kombinace všech metod pro maximální přesnost

### 📧 Thunderbird Integrace
- Automatické načítání emailů z lokálního profilu
- Extrakce příloh (PDF, obrázky, DOCX)
- Filtrování podle data (X dní zpět, 999999 = všechny)
- Seskupování podle odesílatele

### 📚 Paperless-NGX API
- Export dokumentů s detekcí duplikátů (checksum)
- Automatické vytváření tagů, correspondents, document types
- Update existujících dokumentů místo duplikace
- Dávkové zpracování

### 📋 Blacklist/Whitelist
- Automatická detekce známých reklam
- Whitelist ověřených dodavatelů
- Perzistentní úložiště (pickle)
- Auto-update na základě klasifikací

### 💾 SQLite Databáze
- Ukládání dokumentů s kompletními metadaty
- Historie klasifikací
- Trénovací data pro ML model
- Statistiky a reporty

### 🌐 Web GUI
- Moderní responsive rozhraní
- Přehled všech dokumentů
- Drag & drop upload
- Thunderbird import
- Paperless-NGX synchronizace
- Správa blacklistu/whitelistu

## Požadavky

### Systémové závislosti

```bash
# macOS
brew install tesseract
brew install poppler  # Pro PDF konverzi

# Ubuntu/Debian
sudo apt-get install tesseract-ocr
sudo apt-get install poppler-utils

# Windows
# Stáhněte Tesseract z: https://github.com/UB-Mannheim/tesseract/wiki
# Stáhněte Poppler z: https://blog.alivate.com.au/poppler-windows/
```

### Tesseract jazykové balíčky

```bash
# macOS
brew install tesseract-lang

# Ubuntu/Debian
sudo apt-get install tesseract-ocr-ces tesseract-ocr-deu tesseract-ocr-eng
```

### Python 3.8+

## Instalace

### 1. Klonování repozitáře

```bash
git clone https://github.com/majpuzik/maj-document-recognition.git
cd maj-document-recognition
```

### 2. Vytvoření virtuálního prostředí

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# nebo
venv\Scripts\activate  # Windows
```

### 3. Instalace balíčku

```bash
# Produkční instalace
pip install -e .

# Vývojová instalace (s test dependencies)
pip install -e ".[dev]"
```

### 4. Konfigurace

```bash
# Zkopírujte example config
cp config/paperless_config.example.json config/paperless_config.json

# Upravte config/config.yaml podle potřeby
nano config/config.yaml
```

## Použití

### Příkazová řádka

```bash
# Zpracování jednotlivého dokumentu
maj-docrecog process /path/to/document.pdf

# Skenování Thunderbird (posledních 30 dní)
maj-docrecog scan --days 30

# Export do Paperless-NGX
maj-docrecog export

# Spuštění web GUI
maj-docrecog web
```

### Web GUI

```bash
# Spuštění serveru
maj-docrecog-web

# Nebo pomocí Python
python -m src.web.app
```

Poté otevřete prohlížeč na: http://localhost:5000

### Python API

```python
import yaml
from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager

# Load config
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Initialize components
db = DatabaseManager(config)
processor = DocumentProcessor(config)
classifier = AIClassifier(config, db)

# Process document
ocr_result = processor.process_document("/path/to/document.pdf")
classification = classifier.classify(ocr_result["text"])

# Save to database
doc_id = db.insert_document(
    file_path="/path/to/document.pdf",
    ocr_text=ocr_result["text"],
    ocr_confidence=ocr_result["confidence"],
    document_type=classification["type"],
    ai_confidence=classification["confidence"],
)

print(f"Document classified as: {classification['type']}")
print(f"Confidence: {classification['confidence']:.2%}")
```

## Konfigurace

### Základní nastavení (config/config.yaml)

```yaml
# OCR
ocr:
  languages: ["ces", "deu", "eng"]
  preprocessing:
    enabled: true
    grayscale: true
    denoise: true
  confidence_threshold: 60

# AI
ai:
  ollama:
    enabled: true
    base_url: "http://localhost:11434"
    model: "llama3.2:3b"
  ml_model:
    enabled: true
    auto_train: true

# Thunderbird
thunderbird:
  max_days_back: 30

# Paperless
paperless:
  enabled: true
  url: "http://localhost:8000"
  api_token: "your-token"
```

### Paperless-NGX nastavení

1. Získejte API token z Paperless-NGX (Settings → API Tokens)
2. Upravte `config/paperless_config.json`
3. Nastavte `paperless.enabled: true` v `config.yaml`

## Testování

```bash
# Spuštění všech testů
pytest

# S coverage reportem
pytest --cov=src --cov-report=html

# Spuštění konkrétního testu
pytest tests/test_ai.py -v
```

## Struktura projektu

```
maj-document-recognition/
├── src/
│   ├── ocr/                    # OCR moduly
│   ├── ai/                     # AI klasifikace
│   ├── integrations/           # Thunderbird, Paperless, Blacklist
│   ├── database/               # SQLite databáze
│   └── web/                    # Flask web GUI
├── tests/                      # Unit testy
├── config/                     # Konfigurace
├── docs/                       # Dokumentace
├── data/                       # Data (vytvořeno automaticky)
│   ├── uploads/
│   ├── temp/
│   └── documents.db
└── logs/                       # Logy (vytvořeno automaticky)
```

## Troubleshooting

### Tesseract not found

```bash
# Nastavte cestu k Tesseract
export PATH="/usr/local/bin:$PATH"

# Nebo v Python kódu
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'
```

### Ollama connection error

```bash
# Zkontrolujte, že Ollama běží
curl http://localhost:11434/api/version

# Nebo vypněte Ollama v config.yaml
ai:
  ollama:
    enabled: false
```

### Thunderbird profile not found

Nastavte cestu ručně v `config/config.yaml`:

```yaml
thunderbird:
  profile_path: "/path/to/thunderbird/profile"
```

## Licence

MIT License - viz LICENSE soubor

## Autor

MAJ (m.a.j.puzik@example.com)

## Přispívání

Pull requesty jsou vítány! Pro větší změny prosím nejprve otevřete issue.

## Podpora

Pro issues a dotazy použijte GitHub Issues: https://github.com/majpuzik/maj-document-recognition/issues
