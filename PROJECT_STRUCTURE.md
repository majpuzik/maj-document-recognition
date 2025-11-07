# MAJ Document Recognition - Project Structure

## Directory Structure

```
maj-document-recognition/
├── src/                          # Source code
│   ├── __init__.py
│   ├── main.py                   # CLI entry point
│   ├── ocr/                      # OCR modules
│   │   ├── __init__.py
│   │   ├── document_processor.py # Document preprocessing & OCR
│   │   └── text_extractor.py     # Text extraction from various formats
│   ├── ai/                       # AI classification
│   │   ├── __init__.py
│   │   ├── classifier.py         # Main AI classifier (ensemble)
│   │   ├── ml_model.py           # ML model (TF-IDF + Naive Bayes)
│   │   ├── reklamni_filtr.py     # Advertisement detection
│   │   └── soudni_filtr.py       # Legal document detection
│   ├── integrations/             # External integrations
│   │   ├── __init__.py
│   │   ├── thunderbird.py        # Thunderbird email integration
│   │   ├── paperless_api.py      # Paperless-NGX API
│   │   └── blacklist_whitelist.py # Blacklist/Whitelist management
│   ├── database/                 # Database layer
│   │   ├── __init__.py
│   │   └── db_manager.py         # SQLite database manager
│   └── web/                      # Web GUI
│       ├── __init__.py
│       ├── app.py                # Flask application
│       └── templates/
│           └── index.html        # Main web interface
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_ocr.py              # OCR module tests
│   ├── test_ai.py               # AI module tests
│   ├── test_integrations.py     # Integration tests
│   └── test_database.py         # Database tests
├── config/                       # Configuration files
│   ├── config.yaml              # Main configuration
│   └── paperless_config.example.json  # Paperless example config
├── docs/                         # Documentation
│   ├── README.md                # Full documentation
│   ├── INSTALACE.md             # Installation guide (Czech)
│   └── API.md                   # API documentation
├── examples/                     # Usage examples
│   ├── basic_usage.py           # Basic example
│   ├── batch_processing.py      # Batch processing
│   └── thunderbird_example.py   # Thunderbird integration
├── data/                         # Data directory (created at runtime)
│   ├── uploads/                 # Uploaded files
│   ├── temp/                    # Temporary files
│   ├── cache/                   # Cache files
│   └── documents.db             # SQLite database
├── logs/                         # Log files (created at runtime)
│   └── app.log
├── README.md                     # Project README
├── LICENSE                       # MIT License
├── CHANGELOG.md                  # Version history
├── PROJECT_STRUCTURE.md          # This file
├── setup.py                      # Package setup
├── pyproject.toml                # Modern Python project config
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Pytest configuration
├── Makefile                      # Common tasks
├── INSTALL.sh                    # Quick install script
└── .gitignore                    # Git ignore rules
```

## Module Descriptions

### Core Modules (src/)

#### OCR Module (src/ocr/)
- **document_processor.py**: Main document processing with image preprocessing (grayscale, denoising, deskewing, contrast enhancement)
- **text_extractor.py**: Text extraction from PDF, images, and DOCX files using Tesseract OCR

#### AI Module (src/ai/)
- **classifier.py**: Ensemble classifier combining multiple methods
  - Ollama LLM classification
  - ML model classification
  - Keyword-based classification
  - Advertisement detection
  - Legal document detection
- **ml_model.py**: Custom ML model using TF-IDF vectorization and Naive Bayes
  - Auto-training from database
  - Persistent model storage
- **reklamni_filtr.py**: Advertisement detection using keywords and structural patterns
- **soudni_filtr.py**: Legal document detection using legal keywords, case numbers, and court identifiers

#### Integrations Module (src/integrations/)
- **thunderbird.py**: Thunderbird email integration
  - Auto-detect profile path
  - Email scanning with date filters
  - Attachment extraction
  - Sender grouping
- **paperless_api.py**: Paperless-NGX REST API client
  - Document upload
  - Duplicate detection (checksum)
  - Auto-create tags, correspondents, document types
- **blacklist_whitelist.py**: Sender blacklist/whitelist management
  - Persistent storage (pickle)
  - Domain-based filtering
  - Auto-update from classifications

#### Database Module (src/database/)
- **db_manager.py**: SQLite database manager
  - Document metadata storage
  - Classification history
  - Training data management
  - Statistics and reporting

#### Web Module (src/web/)
- **app.py**: Flask web application
  - REST API endpoints
  - Document management
  - Thunderbird scanning
  - Paperless synchronization
- **templates/index.html**: Modern responsive web interface
  - Document browser
  - Drag & drop upload
  - Statistics dashboard
  - Blacklist/Whitelist management

### Tests (tests/)
- **test_ocr.py**: OCR module tests
- **test_ai.py**: AI classification tests
- **test_integrations.py**: Integration tests
- **test_database.py**: Database tests

### Configuration (config/)
- **config.yaml**: Main configuration file
  - OCR settings
  - AI settings (Ollama, ML model)
  - Thunderbird settings
  - Paperless settings
  - Database settings
- **paperless_config.json**: Paperless-NGX specific configuration

### Documentation (docs/)
- **README.md**: Complete project documentation
- **INSTALACE.md**: Detailed installation guide (Czech)
- **API.md**: Python and REST API documentation

### Examples (examples/)
- **basic_usage.py**: Basic document processing example
- **batch_processing.py**: Batch processing multiple documents
- **thunderbird_example.py**: Thunderbird email scanning example

## Key Features by Module

### OCR Features
- ✅ Multi-format support (PDF, JPG, PNG, DOCX)
- ✅ Multi-language OCR (Czech, German, English)
- ✅ Image preprocessing for better accuracy
- ✅ Confidence scoring
- ✅ Page count detection

### AI Features
- ✅ Ensemble classification (multiple methods)
- ✅ Ollama LLM integration
- ✅ Custom ML model with auto-training
- ✅ Advertisement detection
- ✅ Legal document detection
- ✅ Keyword-based classification
- ✅ Confidence scoring

### Integration Features
- ✅ Thunderbird email scanning
- ✅ Attachment extraction
- ✅ Paperless-NGX upload
- ✅ Duplicate detection
- ✅ Blacklist/Whitelist management
- ✅ Auto-create Paperless entities

### Database Features
- ✅ Document metadata storage
- ✅ OCR text storage
- ✅ Classification history
- ✅ Training data management
- ✅ Statistics and reporting
- ✅ Paperless sync tracking

### Web GUI Features
- ✅ Modern responsive interface
- ✅ Document browser with filters
- ✅ Drag & drop upload
- ✅ Thunderbird import
- ✅ Paperless synchronization
- ✅ Statistics dashboard
- ✅ Blacklist/Whitelist management

## Technology Stack

### Backend
- **Python 3.8+**: Main programming language
- **Flask**: Web framework
- **SQLite**: Database
- **Tesseract OCR**: OCR engine
- **scikit-learn**: ML framework
- **Ollama**: LLM integration

### Libraries
- **pytesseract**: Tesseract Python wrapper
- **pdf2image**: PDF to image conversion
- **Pillow**: Image processing
- **opencv-python**: Advanced image preprocessing
- **python-docx**: DOCX file handling
- **requests**: HTTP client
- **pyyaml**: YAML configuration
- **flask-cors**: CORS support

### Development Tools
- **pytest**: Testing framework
- **black**: Code formatting
- **flake8**: Linting
- **mypy**: Type checking

## Entry Points

### Command Line
- `maj-docrecog`: Main CLI tool
  - `maj-docrecog process <file>`: Process single document
  - `maj-docrecog scan`: Scan Thunderbird
  - `maj-docrecog export`: Export to Paperless
  - `maj-docrecog web`: Start web GUI

- `maj-docrecog-web`: Start web server

### Python API
```python
from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager
```

### Web API
- Base URL: `http://localhost:5000/api`
- Endpoints: `/documents`, `/upload`, `/thunderbird/scan`, `/paperless/sync`, etc.

## Development Workflow

1. **Setup**: Run `./INSTALL.sh` or `make install-dev`
2. **Configure**: Edit `config/config.yaml`
3. **Code**: Make changes in `src/`
4. **Test**: Run `make test` or `pytest`
5. **Format**: Run `make format`
6. **Lint**: Run `make lint`
7. **Run**: Run `make run` or `maj-docrecog-web`

## Testing

```bash
# All tests
pytest

# With coverage
make test-cov

# Specific module
pytest tests/test_ai.py -v
```

## Deployment

### Development
```bash
python -m src.web.app
```

### Production
```bash
# Use gunicorn or uwsgi
gunicorn -w 4 -b 0.0.0.0:5000 src.web.app:app
```

### Docker (planned)
```bash
docker-compose up
```

## License

MIT License - see LICENSE file
