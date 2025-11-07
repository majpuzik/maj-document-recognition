"""
Tests for AI module
"""

import pytest
from src.ai.classifier import AIClassifier
from src.ai.ml_model import MLModel
from src.ai.reklamni_filtr import ReklamniFiltr
from src.ai.soudni_filtr import SoudniFiltr


@pytest.fixture
def config():
    """Test configuration"""
    return {
        "ai": {
            "ollama": {
                "enabled": False,
            },
            "ml_model": {
                "enabled": True,
                "auto_train": False,
            },
        },
        "classification": {
            "types": ["faktura", "stvrzenka", "reklama", "jine"],
            "keywords": {
                "faktura": ["faktura", "invoice"],
                "reklama": ["sleva", "akce"],
            },
        },
    }


@pytest.fixture
def classifier(config):
    """AIClassifier instance"""
    return AIClassifier(config, db_manager=None)


@pytest.fixture
def reklamni_filtr(config):
    """ReklamniFiltr instance"""
    return ReklamniFiltr(config)


@pytest.fixture
def soudni_filtr(config):
    """SoudniFiltr instance"""
    return SoudniFiltr(config)


def test_reklamni_filtr_initialization(reklamni_filtr):
    """Test ReklamniFiltr initialization"""
    assert reklamni_filtr is not None
    assert len(reklamni_filtr.ad_keywords) > 0


def test_reklamni_filtr_detects_ad(reklamni_filtr):
    """Test advertisement detection"""
    text = "Exkluzivní sleva 50%! Neklikejte pro odhlášení z newsletteru!"
    result = reklamni_filtr.is_advertisement(text)
    assert result["is_ad"] is True
    assert result["confidence"] > 0.5


def test_reklamni_filtr_not_ad(reklamni_filtr):
    """Test non-advertisement detection"""
    text = "Faktura č. 123 za dodávku zboží."
    result = reklamni_filtr.is_advertisement(text)
    assert result["is_ad"] is False


def test_soudni_filtr_initialization(soudni_filtr):
    """Test SoudniFiltr initialization"""
    assert soudni_filtr is not None
    assert len(soudni_filtr.legal_keywords) > 0


def test_soudni_filtr_detects_legal(soudni_filtr):
    """Test legal document detection"""
    text = "Okresní soud v Praze, spisová značka 12K 123/2023, rozsudek podle §123"
    result = soudni_filtr.is_legal_document(text)
    assert result["is_legal"] is True
    assert result["confidence"] > 0.5


def test_classifier_keyword_matching(classifier):
    """Test keyword-based classification"""
    text = "Faktura č. 123 za dodávku"
    result = classifier.classify_with_keywords(text)
    assert result["success"] is True
    assert result["type"] == "faktura"
