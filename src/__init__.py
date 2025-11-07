"""
MAJ Document Recognition System
Kompletní OCR systém pro klasifikaci dokumentů s AI integrací
"""

__version__ = "1.0.0"
__author__ = "MAJ"

from .ocr import DocumentProcessor, TextExtractor
from .ai import AIClassifier, MLModel
from .database import DatabaseManager
from .integrations import ThunderbirdIntegration, PaperlessAPI, BlacklistWhitelist

__all__ = [
    "DocumentProcessor",
    "TextExtractor",
    "AIClassifier",
    "MLModel",
    "DatabaseManager",
    "ThunderbirdIntegration",
    "PaperlessAPI",
    "BlacklistWhitelist",
]
