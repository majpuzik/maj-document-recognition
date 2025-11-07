# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added
- Initial release of MAJ Document Recognition
- OCR processing with Tesseract
  - PDF, JPG, PNG, DOCX support
  - Advanced image preprocessing
  - Multi-language support (CZ, DE, EN)
- AI classification system
  - Ollama LLM integration
  - Custom ML model (TF-IDF + Naive Bayes)
  - Ensemble classification
  - Advertisement detection filter
  - Legal document detection filter
- Thunderbird integration
  - Automatic email scanning
  - Attachment extraction
  - Sender grouping
- Paperless-NGX API integration
  - Document upload
  - Duplicate detection
  - Automatic tag/correspondent creation
- Blacklist/Whitelist management
  - Persistent storage
  - Domain-based filtering
  - Auto-update from classifications
- SQLite database
  - Document metadata storage
  - Classification history
  - Training data management
- Web GUI (Flask)
  - Document browser
  - Drag & drop upload
  - Thunderbird import
  - Paperless sync
  - Statistics dashboard
- Complete test suite
  - Unit tests for all modules
  - Integration tests
  - pytest configuration
- Documentation
  - Installation guide
  - API documentation
  - Usage examples
- Development tools
  - Makefile for common tasks
  - Black code formatting
  - pytest configuration
  - Type hints support

### Changed
- N/A (initial release)

### Deprecated
- N/A (initial release)

### Removed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Security
- N/A (initial release)

## [Unreleased]

### Planned Features
- [ ] EasyOCR alternative engine
- [ ] Support for more document types
- [ ] Advanced ML model training UI
- [ ] Email notification system
- [ ] REST API authentication
- [ ] Docker containerization
- [ ] Multi-user support
- [ ] Cloud storage integration (S3, Google Drive)
- [ ] Advanced reporting and analytics
- [ ] Mobile app support
