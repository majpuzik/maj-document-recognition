# Instalační příručka - MAJ Document Recognition

Detailní návod na instalaci a konfiguraci systému.

## Obsah

1. [Systémové požadavky](#systémové-požadavky)
2. [Instalace závislostí](#instalace-závislostí)
3. [Instalace projektu](#instalace-projektu)
4. [Konfigurace](#konfigurace)
5. [První spuštění](#první-spuštění)
6. [Integrace s Ollama](#integrace-s-ollama)
7. [Integrace s Paperless-NGX](#integrace-s-paperless-ngx)

## Systémové požadavky

### Minimální požadavky

- **OS:** macOS 10.15+, Ubuntu 20.04+, Windows 10+
- **Python:** 3.8 nebo vyšší
- **RAM:** 4 GB (8 GB doporučeno)
- **Disk:** 500 MB pro instalaci + prostor pro dokumenty
- **CPU:** 2 jádra (4 jádra doporučeno)

### Doporučené požadavky

- **OS:** macOS 13+, Ubuntu 22.04+
- **Python:** 3.11
- **RAM:** 16 GB
- **Disk:** 10 GB SSD
- **CPU:** 4+ jádra
- **GPU:** Volitelně pro rychlejší OCR (CUDA support)

## Instalace závislostí

### macOS

```bash
# Homebrew (pokud ještě není nainstalován)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Tesseract OCR
brew install tesseract
brew install tesseract-lang  # Jazykové balíčky

# Poppler (pro PDF konverzi)
brew install poppler

# Python 3.11
brew install python@3.11

# Ověření instalace
tesseract --version
python3 --version
```

### Ubuntu/Debian

```bash
# Aktualizace systému
sudo apt-get update
sudo apt-get upgrade -y

# Tesseract OCR
sudo apt-get install -y tesseract-ocr
sudo apt-get install -y tesseract-ocr-ces tesseract-ocr-deu tesseract-ocr-eng

# Poppler
sudo apt-get install -y poppler-utils

# Python 3.11
sudo apt-get install -y python3.11 python3.11-venv python3-pip

# Build tools
sudo apt-get install -y build-essential python3-dev

# Ověření instalace
tesseract --version
python3.11 --version
```

### Windows

1. **Tesseract OCR:**
   - Stáhněte instalátor: https://github.com/UB-Mannheim/tesseract/wiki
   - Spusťte instalátor a zapamatujte si cestu (např. `C:\Program Files\Tesseract-OCR`)
   - Přidejte cestu do PATH nebo nastavte v kódu:
     ```python
     import pytesseract
     pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
     ```

2. **Poppler:**
   - Stáhněte: https://blog.alivate.com.au/poppler-windows/
   - Rozbalte a přidejte `bin` složku do PATH

3. **Python 3.11:**
   - Stáhněte: https://www.python.org/downloads/
   - Instalace s volbou "Add Python to PATH"

## Instalace projektu

### 1. Získání projektu

```bash
# Git clone (pokud máte repository)
git clone https://github.com/majpuzik/maj-document-recognition.git
cd maj-document-recognition

# Nebo rozbalte ZIP soubor
unzip maj-document-recognition.zip
cd maj-document-recognition
```

### 2. Vytvoření virtuálního prostředí

```bash
# macOS/Linux
python3.11 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

Po aktivaci by se měl prompt změnit na `(venv) ...`

### 3. Upgrade pip

```bash
pip install --upgrade pip setuptools wheel
```

### 4. Instalace balíčku

```bash
# Základní instalace
pip install -e .

# S vývojovými nástroji (pro vývoj a testování)
pip install -e ".[dev]"

# Kontrola instalace
pip list | grep maj-document-recognition
```

### 5. Vytvoření adresářové struktury

```bash
# Vytvoření data adresářů
mkdir -p data/{uploads,temp,cache}
mkdir -p logs
mkdir -p config

# Linux/macOS oprávnění
chmod 755 data logs config
```

## Konfigurace

### 1. Základní konfigurace

```bash
# Zkopírování example konfigurace
cp config/paperless_config.example.json config/paperless_config.json

# Editace hlavní konfigurace
nano config/config.yaml  # nebo vim, VS Code, atd.
```

### 2. Důležité nastavení v config.yaml

```yaml
# Logging
app:
  log_level: "INFO"  # DEBUG pro více detailů
  log_file: "logs/app.log"

# Web server
web:
  host: "0.0.0.0"  # 127.0.0.1 pro pouze localhost
  port: 5000
  secret_key: "ZMĚŇTE-TOTO-V-PRODUKCI"  # Vygenerujte nový klíč!

# OCR jazyky (podle vašich potřeb)
ocr:
  languages:
    - "ces"  # Čeština
    - "deu"  # Němčina
    - "eng"  # Angličtina

# Thunderbird (volitelné)
thunderbird:
  profile_path: ""  # Ponechte prázdné pro auto-detekci
  max_days_back: 30

# Paperless (volitelné)
paperless:
  enabled: false  # Nastavte true po konfiguraci
  url: "http://localhost:8000"
  api_token: ""  # Vyplňte po získání tokenu
```

### 3. Generování bezpečného secret_key

```bash
# V Python
python -c "import secrets; print(secrets.token_hex(32))"

# Zkopírujte výstup do config.yaml jako secret_key
```

## První spuštění

### 1. Test základních funkcí

```bash
# Aktivujte venv (pokud ještě není)
source venv/bin/activate  # Linux/macOS
# nebo venv\Scripts\activate  # Windows

# Test OCR (vytvořte testovací dokument nebo použijte existující)
maj-docrecog process /path/to/test-document.pdf

# Mělo by vypsat:
# - OCR text
# - Klasifikaci typu
# - Confidence skóre
```

### 2. Spuštění databáze

Databáze se vytvoří automaticky při prvním spuštění:

```bash
# Kontrola vytvoření databáze
ls -lh data/documents.db

# Měla by se zobrazit SQLite databáze
```

### 3. Spuštění web GUI

```bash
maj-docrecog-web

# Mělo by se zobrazit:
# * Running on http://0.0.0.0:5000

# Otevřete prohlížeč: http://localhost:5000
```

### 4. Test základních funkcí přes GUI

1. **Upload dokumentu:**
   - Přejděte na tab "Nahrát"
   - Drag & drop PDF nebo obrázek
   - Zkontrolujte klasifikaci

2. **Zobrazení dokumentů:**
   - Přejděte na tab "Dokumenty"
   - Měl by se zobrazit nahraný dokument

3. **Statistiky:**
   - Přejděte na tab "Přehled"
   - Zkontrolujte statistiky

## Integrace s Ollama

### 1. Instalace Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows - stáhněte z https://ollama.ai/download
```

### 2. Stažení modelu

```bash
# Doporučený model (3B parametrů, rychlý)
ollama pull llama3.2:3b

# Nebo větší model (8B parametrů, přesnější)
ollama pull llama3.2:8b
```

### 3. Test Ollama

```bash
# Start Ollama serveru (obvykle běží automaticky)
ollama serve

# V jiném terminálu - test
curl http://localhost:11434/api/version

# Mělo by vrátit JSON s verzí
```

### 4. Konfigurace v projektu

V `config/config.yaml`:

```yaml
ai:
  ollama:
    enabled: true
    base_url: "http://localhost:11434"
    model: "llama3.2:3b"
    timeout: 30
    temperature: 0.1
```

### 5. Test AI klasifikace

```bash
# Zpracujte dokument s Ollama
maj-docrecog process /path/to/document.pdf

# V logu by mělo být: "Using Ollama for classification"
```

## Integrace s Paperless-NGX

### 1. Instalace Paperless-NGX (Docker)

```bash
# Vytvoření adresáře
mkdir -p ~/paperless-ngx
cd ~/paperless-ngx

# Stažení docker-compose
curl -O https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/docker/compose/docker-compose.postgres.yml

# Přejmenování
mv docker-compose.postgres.yml docker-compose.yml

# Editace .env souboru
nano .env

# Minimální konfigurace:
PAPERLESS_SECRET_KEY=your-secret-key
PAPERLESS_OCR_LANGUAGE=ces+deu+eng
PAPERLESS_TIME_ZONE=Europe/Prague

# Spuštění
docker-compose up -d
```

### 2. Získání API tokenu

1. Otevřete Paperless: http://localhost:8000
2. Vytvořte admin účet (při prvním spuštění)
3. Přejděte do: Settings → API Tokens
4. Klikněte "Create Token"
5. Zkopírujte token

### 3. Konfigurace v projektu

V `config/paperless_config.json`:

```json
{
  "paperless": {
    "url": "http://localhost:8000",
    "api_token": "VÁŠ-API-TOKEN",
    "verify_ssl": true,
    "auto_create_tags": true,
    "auto_create_correspondents": true,
    "auto_create_document_types": true,
    "check_duplicates": true
  }
}
```

V `config/config.yaml`:

```yaml
paperless:
  enabled: true
  url: "http://localhost:8000"
  api_token: "VÁŠ-API-TOKEN"
```

### 4. Test Paperless integrace

```bash
# Export dokumentu
maj-docrecog export

# Zkontrolujte v Paperless GUI, že se dokumenty objevily
```

## Troubleshooting

### Python ModuleNotFoundError

```bash
# Ujistěte se, že je aktivní venv
source venv/bin/activate

# Reinstalace
pip install -e .
```

### Tesseract not found

```bash
# Najděte Tesseract
which tesseract  # Linux/macOS
where tesseract  # Windows

# Nastavte v kódu (src/ocr/text_extractor.py)
import pytesseract
pytesseract.pytesseract.tesseract_cmd = '/path/to/tesseract'
```

### Permission denied (Linux)

```bash
# Oprava oprávnění
chmod -R 755 data logs config
chown -R $USER:$USER data logs config
```

### Port already in use

```bash
# Změňte port v config.yaml
web:
  port: 5001  # Nebo jiný volný port
```

## Další kroky

1. **Přečtěte si API dokumentaci:** `docs/API.md`
2. **Prozkoumejte příklady použití**
3. **Nastavte automatické zálohování databáze**
4. **Nakonfigurujte Thunderbird integraci**

## Získání pomoci

- **GitHub Issues:** https://github.com/majpuzik/maj-document-recognition/issues
- **Email:** m.a.j.puzik@example.com
- **Dokumentace:** https://github.com/majpuzik/maj-document-recognition/wiki
