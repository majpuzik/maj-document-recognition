"""
MAJ Amazon Invoices - Open Source
==================================
Parser pro Amazon Business CSV exporty s generováním PDF faktur a ISDOC dat.

Funkce:
- Multi-language CSV parser (DE/EN/CZ)
- PDF invoice generator (Amazon style)
- ISDOC data export
- Clean API with statistics

Package: maj-amazon-invoices
License: MIT
Fonts: DejaVu Sans (Bitstream Vera License)
"""

# Low-level components
from .amazon_invoice_csv import (
    AmazonInvoiceCSVParser,
    AmazonOrder,
    AmazonOrderItem,
    detect_amazon_csv,
    parse_amazon_csv,
    parse_amazon_csv_to_isdoc,
    Language,
)

from .amazon_invoice_pdf import (
    AmazonInvoicePDF,
    generate_amazon_invoice_pdf,
)

# High-level API
from .api import (
    AmazonInvoiceAPI,
    process_amazon_csv,
    OutputFormat,
    OutputLanguage,
    ProcessingResult,
    ProcessingStats,
    APIResponse,
)

__all__ = [
    # API (recommended)
    'AmazonInvoiceAPI',
    'process_amazon_csv',
    'OutputFormat',
    'OutputLanguage',
    'ProcessingResult',
    'ProcessingStats',
    'APIResponse',
    # Low-level CSV Parser
    'AmazonInvoiceCSVParser',
    'AmazonOrder',
    'AmazonOrderItem',
    'detect_amazon_csv',
    'parse_amazon_csv',
    'parse_amazon_csv_to_isdoc',
    'Language',
    # Low-level PDF Generator
    'AmazonInvoicePDF',
    'generate_amazon_invoice_pdf',
]

__version__ = '1.0.0'
__author__ = 'MAJ Development'
__license__ = 'MIT'
