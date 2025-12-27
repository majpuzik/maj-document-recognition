"""
MAJ Document Recognition System
Kompletní OCR systém pro klasifikaci dokumentů s AI integrací
"""

__version__ = "2.0.0"
__author__ = "MAJ Development"

from .ocr import DocumentProcessor, TextExtractor
from .ai import AIClassifier, MLModel
from .database import DatabaseManager
from .integrations import ThunderbirdIntegration, PaperlessAPI, BlacklistWhitelist

# Amazon Invoice Parser
from .maj_amazon_invoices import (
    process_amazon_csv,
    AmazonInvoiceAPI,
    OutputFormat,
    OutputLanguage,
)

__all__ = [
    # Core OCR
    "DocumentProcessor",
    "TextExtractor",
    # AI Classification
    "AIClassifier",
    "MLModel",
    # Database
    "DatabaseManager",
    # Integrations
    "ThunderbirdIntegration",
    "PaperlessAPI",
    "BlacklistWhitelist",
    # Amazon Invoices
    "process_amazon_csv",
    "AmazonInvoiceAPI",
    "OutputFormat",
    "OutputLanguage",
]
