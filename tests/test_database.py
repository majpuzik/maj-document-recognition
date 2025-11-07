"""
Tests for database module
"""

import pytest
from pathlib import Path
from src.database.db_manager import DatabaseManager


@pytest.fixture
def config(tmp_path):
    """Test configuration"""
    return {
        "database": {
            "path": str(tmp_path / "test.db"),
            "backup_enabled": False,
        }
    }


@pytest.fixture
def db(config):
    """DatabaseManager instance"""
    return DatabaseManager(config)


def test_database_initialization(db):
    """Test database initialization"""
    assert db is not None
    assert db.db_path.exists()


def test_insert_document(db):
    """Test inserting document"""
    doc_id = db.insert_document(
        file_path="/test/document.pdf",
        ocr_text="Test text",
        ocr_confidence=95.5,
        document_type="faktura",
        ai_confidence=0.9,
    )

    assert doc_id > 0


def test_get_document(db):
    """Test getting document"""
    doc_id = db.insert_document(
        file_path="/test/document.pdf",
        ocr_text="Test text",
        document_type="faktura",
    )

    document = db.get_document(doc_id)
    assert document is not None
    assert document["id"] == doc_id
    assert document["file_path"] == "/test/document.pdf"


def test_get_all_documents(db):
    """Test getting all documents"""
    db.insert_document(file_path="/test/doc1.pdf", document_type="faktura")
    db.insert_document(file_path="/test/doc2.pdf", document_type="stvrzenka")

    documents = db.get_all_documents()
    assert len(documents) >= 2


def test_filter_by_type(db):
    """Test filtering by document type"""
    db.insert_document(file_path="/test/doc1.pdf", document_type="faktura")
    db.insert_document(file_path="/test/doc2.pdf", document_type="stvrzenka")

    faktury = db.get_all_documents(document_type="faktura")
    assert len(faktury) >= 1
    assert all(doc["document_type"] == "faktura" for doc in faktury)


def test_update_document(db):
    """Test updating document"""
    doc_id = db.insert_document(
        file_path="/test/document.pdf",
        document_type="jine",
    )

    result = db.update_document(doc_id, document_type="faktura")
    assert result is True

    document = db.get_document(doc_id)
    assert document["document_type"] == "faktura"


def test_mark_synced(db):
    """Test marking document as synced"""
    doc_id = db.insert_document(file_path="/test/document.pdf")

    result = db.mark_document_synced(doc_id, paperless_id=123)
    assert result is True

    document = db.get_document(doc_id)
    assert document["paperless_synced"] == 1
    assert document["paperless_id"] == 123


def test_get_statistics(db):
    """Test getting statistics"""
    db.insert_document(file_path="/test/doc1.pdf", document_type="faktura")
    db.insert_document(file_path="/test/doc2.pdf", document_type="faktura")
    db.insert_document(file_path="/test/doc3.pdf", document_type="stvrzenka")

    stats = db.get_statistics()
    assert stats["total_documents"] >= 3
    assert "faktura" in stats["by_type"]
    assert stats["by_type"]["faktura"] >= 2
