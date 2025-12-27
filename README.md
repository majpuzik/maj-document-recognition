# MAJ Document Recognition

🤖 **Inteligentní OCR systém** pro automatickou klasifikaci dokumentů s AI, Thunderbird a Paperless-NGX integrací.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🎉 **NOVÉ v2.0** - Production Ready! (2025-11-06)

**6 hlavních vylepšení implementováno:**
- ⚡ **Distributed Processing** - 8× rychlejší zpracování napříč více Ollama servery
- 🔍 **Cascade OCR** - 3-5× rychlejší s postupným testováním jazyků (CZ→EN→DE)
- 💾 **Progress Persistence** - Resume po crash, session management
- 🔍 **Auto Server Discovery** - Automatické hledání Ollama serverů v síti
- 🧠 **Context-Aware Classification** - +20% confidence s učením z historických dat
- 📊 **Export & Reporting** - JSON/CSV/Markdown exporty a statistiky

**📖 v2.0 Dokumentace:**
- [V2.0_COMPLETE_SUMMARY.txt](V2.0_COMPLETE_SUMMARY.txt) - Kompletní přehled všech features
- [PRODUCTION_STATUS_REPORT.md](PRODUCTION_STATUS_REPORT.md) - Production status a metriky
- [IMPROVEMENTS_V2.md](IMPROVEMENTS_V2.md) - Detailní popis vylepšení
- [DISTRIBUTED_README.md](DISTRIBUTED_README.md) - Guide pro distributed processing
- [WHATS_NEW.md](WHATS_NEW.md) - Changelog a migration guide

**🚀 Quick Start v2.0:**
```bash
# Najít Ollama servery
python distributed_cli.py discover

# Spustit distribuované zpracování
python distributed_cli.py run --limit 2000

# Exportovat výsledky
python export_results.py --format all
```

---

## 🆕 **NOVÉ v2.1** - REST API + System Notifications (2025-12-17)

**Nové funkce:**
- 🌐 **REST API** - Flask server pro klasifikaci a extrakci dat
- ⚡ **System Notification Detection** - Pattern-based detekce (30x rychlejší než LLM)
- 🏠 **Loxone Support** - Automatická detekce Loxone Miniserver notifikací
- 📊 **Paperless-NGX Validator** - Validace databáze proti oficiálním pravidlům

### System Notification Patterns

Automatická detekce systémových emailů **BEZ LLM** (pattern matching):

| Pattern Type | Examples |
|--------------|----------|
| **From address** | `noreply@*loxone*`, `noreply@`, `notification@`, `alert@` |
| **Subject** | `^Statistic`, `Loxone`, `Miniserver`, `^Alert:` |

**Rychlost:** ~100 emailů/min (vs 3/min s LLM)

### REST API

```bash
# Spustit API server
cd api && python server.py --port 8780

# Klasifikovat dokument
curl -X POST http://localhost:8780/api/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Faktura č. 123", "from": "noreply@loxone.com"}'

# Response pro system notification:
{
  "doc_type": "system_notification",
  "confidence": 0.99,
  "model": "pattern_match"
}
```

**📖 API dokumentace:** [api/README.md](api/README.md)

---

## ✨ Základní funkce

- 🔍 **OCR zpracování** - PDF, obrázky, DOCX s pokročilým předzpracováním
- 🤖 **AI klasifikace** - Ollama LLM, vlastní ML model (TF-IDF + Naive Bayes)
- 📧 **Thunderbird integrace** - Automatický import emailových příloh
- 📚 **Paperless-NGX API** - Export dokumentů s detekcí duplikátů
- 🚫 **Blacklist/Whitelist** - Správa známých odesílatelů
- 💾 **SQLite databáze** - Metadata, historie, trénovací data
- 🌐 **Web GUI** - Moderní responsive rozhraní
- 🌍 **Vícejazyčnost** - Čeština, němčina, angličtina

## 🚀 Rychlý start

```bash
# Instalace závislostí (macOS)
brew install tesseract poppler

# Vytvoření venv a instalace
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Spuštění web GUI
maj-docrecog-web
```

Otevřete http://localhost:5000

## 📖 Dokumentace

- [README.md](docs/README.md) - Kompletní dokumentace
- [INSTALACE.md](docs/INSTALACE.md) - Detailní instalační návod
- [API.md](docs/API.md) - Python a REST API dokumentace

## 💻 Použití

### Příkazová řádka

```bash
# Zpracování dokumentu
maj-docrecog process /path/to/document.pdf

# Skenování Thunderbird
maj-docrecog scan --days 30

# Export do Paperless-NGX
maj-docrecog export

# Web GUI
maj-docrecog web
```

### Python API

```python
from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier

# OCR
processor = DocumentProcessor(config)
result = processor.process_document("invoice.pdf")

# AI klasifikace
classifier = AIClassifier(config)
classification = classifier.classify(result["text"])

print(f"Type: {classification['type']}")
print(f"Confidence: {classification['confidence']:.2%}")
```

## 🧪 Testování

```bash
# Všechny testy
pytest

# S coverage
pytest --cov=src --cov-report=html

# Konkrétní test
pytest tests/test_ai.py -v
```

## 📁 Struktura projektu

```
maj-document-recognition/
├── src/
│   ├── ocr/           # OCR moduly
│   ├── ai/            # AI klasifikace
│   ├── integrations/  # Thunderbird, Paperless, Blacklist
│   ├── database/      # SQLite databáze
│   └── web/           # Flask web GUI
├── tests/             # Unit testy
├── config/            # Konfigurace
├── docs/              # Dokumentace
└── data/              # Data (auto-vytvoření)
```

## 🔧 Konfigurace

### Základní nastavení (config/config.yaml)

```yaml
ocr:
  languages: ["ces", "deu", "eng"]
  preprocessing:
    enabled: true

ai:
  ollama:
    enabled: true
    model: "llama3.2:3b"
  ml_model:
    auto_train: true

paperless:
  enabled: true
  url: "http://localhost:8000"
  api_token: "your-token"
```

## 🤝 Přispívání

Pull requesty jsou vítány! Pro větší změny prosím nejprve otevřete issue.

1. Fork projektu
2. Vytvořte feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit změny (`git commit -m 'Add AmazingFeature'`)
4. Push do branch (`git push origin feature/AmazingFeature`)
5. Otevřete Pull Request

## 📝 Licence

MIT License - viz [LICENSE](LICENSE) soubor

## 👤 Autor

**MAJ**
- Email: m.a.j.puzik@example.com
- GitHub: [@majpuzik](https://github.com/majpuzik)

## 🙏 Poděkování

- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [Ollama](https://ollama.ai/)
- [Paperless-NGX](https://github.com/paperless-ngx/paperless-ngx)
- [scikit-learn](https://scikit-learn.org/)

## 📊 Statistiky

![GitHub stars](https://img.shields.io/github/stars/majpuzik/maj-document-recognition?style=social)
![GitHub forks](https://img.shields.io/github/forks/majpuzik/maj-document-recognition?style=social)
![GitHub issues](https://img.shields.io/github/issues/majpuzik/maj-document-recognition)

---

**Made with ❤️ by MAJ**
