"""
Tests for OCR module
"""

import pytest
from pathlib import Path
from src.ocr.text_extractor import TextExtractor
from src.ocr.document_processor import DocumentProcessor


@pytest.fixture
def config():
    """Test configuration"""
    return {
        "ocr": {
            "languages": ["eng"],
            "preprocessing": {
                "enabled": True,
                "grayscale": True,
                "denoise": False,
                "deskew": False,
                "contrast_enhancement": True,
            },
            "confidence_threshold": 60,
        }
    }


@pytest.fixture
def text_extractor(config):
    """TextExtractor instance"""
    return TextExtractor(config)


@pytest.fixture
def document_processor(config):
    """DocumentProcessor instance"""
    return DocumentProcessor(config)


def test_text_extractor_initialization(text_extractor):
    """Test TextExtractor initialization"""
    assert text_extractor is not None
    assert text_extractor.languages == "eng"


def test_document_processor_initialization(document_processor):
    """Test DocumentProcessor initialization"""
    assert document_processor is not None
    assert document_processor.text_extractor is not None


def test_extract_from_nonexistent_file(text_extractor):
    """Test extracting from non-existent file"""
    result = text_extractor.extract("nonexistent.pdf")
    assert result["success"] is False
    assert "error" in result


# Add more tests as needed
