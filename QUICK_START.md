# MAJ Document Recognition - Quick Start Guide

## 🚀 5-Minute Setup

### 1. Prerequisites Check

```bash
# Check Python version (need 3.8+)
python3 --version

# Check Tesseract (install if missing)
tesseract --version
```

**Don't have Tesseract?**
- macOS: `brew install tesseract tesseract-lang`
- Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-ces tesseract-ocr-deu`
- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

### 2. Automatic Installation

```bash
# Run the install script
./INSTALL.sh

# Or manual installation:
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .
```

### 3. First Run

```bash
# Activate virtual environment
source venv/bin/activate

# Start web interface
maj-docrecog-web

# Open browser: http://localhost:5000
```

### 4. Test with Sample Document

```bash
# Process a PDF or image
maj-docrecog process /path/to/document.pdf

# You should see:
# - OCR extracted text
# - Document type classification
# - Confidence score
```

## 📋 Common Tasks

### Process Single Document
```bash
maj-docrecog process invoice.pdf
```

### Scan Thunderbird Emails (Last 30 Days)
```bash
maj-docrecog scan --days 30
```

### Export to Paperless-NGX
```bash
# First configure Paperless in config/paperless_config.json
maj-docrecog export
```

### Web Interface
```bash
maj-docrecog-web
# Then open http://localhost:5000
```

## ⚙️ Configuration

Edit `config/config.yaml`:

```yaml
# Minimal working config
ocr:
  languages: ["ces", "deu", "eng"]  # Your languages

ai:
  ollama:
    enabled: false  # Set true if you have Ollama
  ml_model:
    enabled: true
    auto_train: true

paperless:
  enabled: false  # Set true after configuration
```

## 🔧 Optional: Ollama Setup

For AI-powered classification:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Download model
ollama pull llama3.2:3b

# Enable in config/config.yaml
ai:
  ollama:
    enabled: true
```

## 🔧 Optional: Paperless-NGX Setup

```bash
# 1. Get Paperless running (Docker recommended)
# 2. Get API token from Paperless Settings → API Tokens
# 3. Edit config/paperless_config.json:
{
  "paperless": {
    "url": "http://localhost:8000",
    "api_token": "YOUR_TOKEN_HERE"
  }
}
# 4. Enable in config/config.yaml
```

## 📖 Next Steps

1. **Read full documentation**: `docs/README.md`
2. **Try examples**: `python examples/basic_usage.py`
3. **Run tests**: `pytest`
4. **Explore web interface**: http://localhost:5000

## 🆘 Troubleshooting

### "Tesseract not found"
```bash
# Find tesseract
which tesseract

# Add to PATH or set in code
export PATH="/usr/local/bin:$PATH"
```

### "ModuleNotFoundError"
```bash
# Ensure venv is activated
source venv/bin/activate

# Reinstall
pip install -e .
```

### "Port 5000 already in use"
Edit `config/config.yaml`:
```yaml
web:
  port: 5001  # Use different port
```

## 🎯 What Can You Do?

✅ **OCR Processing**
- Extract text from PDFs, images, DOCX
- Multi-language support
- High accuracy with preprocessing

✅ **AI Classification**
- Automatic document type detection
- Faktura, stvrzenka, legal documents, ads
- 90%+ accuracy with ensemble methods

✅ **Email Integration**
- Scan Thunderbird mailboxes
- Extract and classify attachments
- Group by sender

✅ **Paperless Integration**
- Auto-upload to Paperless-NGX
- Duplicate detection
- Auto-create tags and correspondents

✅ **Blacklist/Whitelist**
- Block known spammers
- Whitelist trusted senders
- Auto-learning

## 📊 Example Workflow

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Process some documents
maj-docrecog process invoice1.pdf
maj-docrecog process receipt2.jpg

# 3. Or scan Thunderbird
maj-docrecog scan --days 7

# 4. View results in web interface
maj-docrecog-web
# Open http://localhost:5000

# 5. Export to Paperless (if configured)
maj-docrecog export
```

## 🎉 You're Ready!

The system is now running. Check out:
- Web interface: http://localhost:5000
- Full docs: `docs/README.md`
- API docs: `docs/API.md`
- Examples: `examples/`

**Need help?** Open an issue on GitHub or check the documentation.

**Enjoy! 🚀**
