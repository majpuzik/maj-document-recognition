#!/usr/bin/env python3
"""
Amazon Invoice Parser API
==========================
Clean API for parsing Amazon Business CSV exports and generating invoices.

Features:
- Multiple output formats (PDF, ISDOC, both)
- Language options (Czech, bilingual, original)
- Row range selection
- Error handling with detailed messages
- Usage statistics logging

Author: MAJ Development
License: MIT
Date: 2025-12-27
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple, Union
from enum import Enum

from .amazon_invoice_csv import (
    AmazonInvoiceCSVParser,
    AmazonOrder,
    detect_amazon_csv,
    Language,
)
from .amazon_invoice_pdf import AmazonInvoicePDF


class OutputFormat(Enum):
    """Output format options"""
    PDF = "pdf"
    ISDOC = "isdoc"
    BOTH = "both"


class OutputLanguage(Enum):
    """Language options for generated documents"""
    CZECH = "cs"           # Czech only
    BILINGUAL = "bilingual"  # Czech + English (default)
    ORIGINAL = "original"   # Keep original language from CSV


@dataclass
class ProcessingResult:
    """Result of processing a single order"""
    order_number: str
    success: bool
    pdf_path: Optional[str] = None
    isdoc_path: Optional[str] = None
    isdoc_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessingStats:
    """Statistics from processing"""
    total_orders: int = 0
    successful: int = 0
    failed: int = 0
    total_amount: float = 0.0
    currency: str = "EUR"
    processing_time_ms: int = 0
    csv_language: str = "unknown"
    rows_processed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class APIResponse:
    """API response structure"""
    success: bool
    message: str
    results: List[ProcessingResult] = field(default_factory=list)
    stats: Optional[ProcessingStats] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "results": [r.to_dict() for r in self.results],
            "stats": self.stats.to_dict() if self.stats else None,
            "errors": self.errors,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str, ensure_ascii=False)


class AmazonInvoiceAPI:
    """
    Main API for Amazon Invoice processing

    Usage:
        api = AmazonInvoiceAPI()
        response = api.process(
            csv_path='bestellungen.csv',
            output_dir='faktury/',
            output_format=OutputFormat.BOTH,
            language=OutputLanguage.BILINGUAL
        )

        if response.success:
            for result in response.results:
                print(f"{result.order_number}: {result.pdf_path}")
    """

    def __init__(self, stats_callback=None):
        """
        Initialize API

        Args:
            stats_callback: Optional callback function for usage statistics
                           Called with (stats: ProcessingStats, metadata: dict)
        """
        self.parser = AmazonInvoiceCSVParser()
        self.pdf_generator = AmazonInvoicePDF()
        self.stats_callback = stats_callback

    def process(
        self,
        csv_path: str,
        output_dir: str = ".",
        output_format: OutputFormat = OutputFormat.BOTH,
        language: OutputLanguage = OutputLanguage.BILINGUAL,
        row_start: Optional[int] = None,
        row_end: Optional[int] = None,
        log_stats: bool = True,
    ) -> APIResponse:
        """
        Process Amazon CSV and generate invoices

        Args:
            csv_path: Path to Amazon Business CSV export
            output_dir: Directory for output files
            output_format: PDF, ISDOC, or BOTH (default: BOTH)
            language: CZECH, BILINGUAL, or ORIGINAL (default: BILINGUAL)
            row_start: Start row (1-based, excluding header). None = from beginning
            row_end: End row (1-based, excluding header). None = to end
            log_stats: Whether to log usage statistics (default: True)

        Returns:
            APIResponse with results and statistics
        """
        start_time = datetime.now()
        errors = []
        results = []

        # Validate inputs
        if not os.path.exists(csv_path):
            return APIResponse(
                success=False,
                message=f"Soubor nenalezen / File not found: {csv_path}",
                errors=[f"FileNotFoundError: {csv_path}"]
            )

        # Check if it's Amazon CSV
        if not detect_amazon_csv(csv_path):
            return APIResponse(
                success=False,
                message="Nerozpoznaný formát CSV / Unrecognized CSV format",
                errors=[
                    "Soubor neodpovídá formátu Amazon Business CSV exportu.",
                    "File does not match Amazon Business CSV export format.",
                    "Očekávané vzory názvů: bestellungen_von_*, invoices_from_*, objednavky_od_*",
                    "Nebo CSV musí obsahovat sloupce: ASIN, Bestellnummer/Order Number"
                ]
            )

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Parse CSV
        try:
            orders = self._parse_with_range(csv_path, row_start, row_end)
        except Exception as e:
            return APIResponse(
                success=False,
                message=f"Chyba při parsování CSV / CSV parsing error",
                errors=[
                    f"ParseError: {str(e)}",
                    "Zkontrolujte formát CSV souboru a kódování (UTF-8).",
                    "Check CSV file format and encoding (UTF-8)."
                ]
            )

        if not orders:
            return APIResponse(
                success=False,
                message="Žádné objednávky nenalezeny / No orders found",
                errors=["CSV soubor neobsahuje žádné platné objednávky."]
            )

        # Process each order
        stats = ProcessingStats(
            total_orders=len(orders),
            csv_language=self.parser.language.value,
            rows_processed=sum(len(o.items) for o in orders)
        )

        for order in orders:
            result = self._process_order(
                order,
                output_path,
                output_format,
                language
            )
            results.append(result)

            if result.success:
                stats.successful += 1
                stats.total_amount += order.total_incl_vat
                stats.currency = order.currency
            else:
                stats.failed += 1
                if result.error:
                    errors.append(f"{order.order_number}: {result.error}")

        # Calculate processing time
        end_time = datetime.now()
        stats.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Log statistics
        if log_stats and self.stats_callback:
            try:
                self.stats_callback(stats, {
                    "csv_path": csv_path,
                    "output_format": output_format.value,
                    "language": language.value,
                    "row_range": f"{row_start or 1}-{row_end or 'end'}",
                })
            except Exception as e:
                errors.append(f"Stats logging failed: {str(e)}")

        # Build response
        success = stats.failed == 0
        if success:
            message = f"Úspěšně zpracováno {stats.successful} objednávek / Successfully processed {stats.successful} orders"
        else:
            message = f"Zpracováno {stats.successful}/{stats.total_orders} objednávek / Processed {stats.successful}/{stats.total_orders} orders"

        return APIResponse(
            success=success,
            message=message,
            results=results,
            stats=stats,
            errors=errors
        )

    def _parse_with_range(
        self,
        csv_path: str,
        row_start: Optional[int],
        row_end: Optional[int]
    ) -> List[AmazonOrder]:
        """Parse CSV with optional row range"""
        import csv

        # Detect delimiter
        delimiter = self.parser.detect_delimiter(csv_path)

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=delimiter)

            # Always read header (row 0)
            headers = next(reader)
            self.parser.headers = headers
            self.parser.language = self.parser.detect_language(headers)
            self.parser.column_map = self.parser.build_column_map(headers)

            if not self.parser.column_map.get('order_number'):
                raise ValueError("Nelze najít sloupec s číslem objednávky / Cannot find order number column")

            # Read data rows with range
            orders: Dict[str, AmazonOrder] = {}
            row_num = 0

            for row in reader:
                row_num += 1

                # Skip rows before start
                if row_start and row_num < row_start:
                    continue

                # Stop after end
                if row_end and row_num > row_end:
                    break

                if not row or len(row) < 5:
                    continue

                order_number = self.parser.get_value(row, 'order_number')
                if not order_number:
                    continue

                if order_number not in orders:
                    orders[order_number] = self.parser._create_order(row)

                item = self.parser._create_item(row)
                if item:
                    orders[order_number].items.append(item)

            return list(orders.values())

    def _process_order(
        self,
        order: AmazonOrder,
        output_path: Path,
        output_format: OutputFormat,
        language: OutputLanguage
    ) -> ProcessingResult:
        """Process single order"""
        result = ProcessingResult(
            order_number=order.order_number,
            success=True
        )

        try:
            # Generate PDF
            if output_format in (OutputFormat.PDF, OutputFormat.BOTH):
                pdf_path = output_path / f"{order.order_number}.pdf"
                self.pdf_generator.generate(order, str(pdf_path))
                result.pdf_path = str(pdf_path)

            # Generate ISDOC data
            if output_format in (OutputFormat.ISDOC, OutputFormat.BOTH):
                isdoc_data = order.to_isdoc_dict()
                result.isdoc_data = isdoc_data

                # Save ISDOC JSON
                isdoc_path = output_path / f"{order.order_number}_isdoc.json"
                with open(isdoc_path, 'w', encoding='utf-8') as f:
                    json.dump(isdoc_data, f, indent=2, default=str, ensure_ascii=False)
                result.isdoc_path = str(isdoc_path)

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def validate_csv(self, csv_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate CSV file without processing

        Returns:
            (is_valid, message, details)
        """
        details = {
            "is_amazon_csv": False,
            "language": None,
            "delimiter": None,
            "row_count": 0,
            "order_count": 0,
            "columns_found": [],
            "columns_missing": [],
        }

        if not os.path.exists(csv_path):
            return False, f"Soubor nenalezen: {csv_path}", details

        details["is_amazon_csv"] = detect_amazon_csv(csv_path)

        if not details["is_amazon_csv"]:
            return False, "Nerozpoznaný formát Amazon CSV", details

        try:
            delimiter = self.parser.detect_delimiter(csv_path)
            details["delimiter"] = repr(delimiter)

            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                import csv
                reader = csv.reader(f, delimiter=delimiter)
                headers = next(reader)

                language = self.parser.detect_language(headers)
                details["language"] = language.value

                # Set parser language before building column map
                self.parser.language = language
                column_map = self.parser.build_column_map(headers)
                details["columns_found"] = list(column_map.keys())

                # Check required columns
                required = ['order_number', 'order_date', 'currency', 'total_incl_vat']
                details["columns_missing"] = [c for c in required if c not in column_map]

                # Count rows and orders
                order_numbers = set()
                for row in reader:
                    details["row_count"] += 1
                    if column_map.get('order_number') and len(row) > column_map['order_number']:
                        order_num = row[column_map['order_number']].strip()
                        if order_num:
                            order_numbers.add(order_num)

                details["order_count"] = len(order_numbers)

            if details["columns_missing"]:
                return False, f"Chybí povinné sloupce: {details['columns_missing']}", details

            return True, f"Validní CSV: {details['order_count']} objednávek, jazyk {details['language']}", details

        except Exception as e:
            return False, f"Chyba při validaci: {str(e)}", details


# Default stats callback - logs to CDB if available
def log_stats_to_cdb(stats: ProcessingStats, metadata: Dict[str, Any]):
    """Log usage statistics to Central Database"""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host='192.168.10.35',
            port=5433,
            database='almquist_cdb',
            user='maj',
            password='maj_central_2024'
        )
        cur = conn.cursor()

        event_metadata = {
            **stats.to_dict(),
            **metadata,
            "timestamp": datetime.now().isoformat(),
        }

        cur.execute("""
            INSERT INTO events (timestamp, event_type, component, version, status, metadata)
            VALUES (NOW(), %s, %s, %s, %s, %s)
        """, (
            'amazon_invoice_processed',
            'maj-amazon-invoices',
            '1.0.0',
            'completed' if stats.failed == 0 else 'partial',
            json.dumps(event_metadata)
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        # Silently fail - stats logging should not break processing
        pass


# Convenience function for simple usage
def process_amazon_csv(
    csv_path: str,
    output_dir: str = ".",
    output_format: str = "both",
    language: str = "bilingual",
    row_start: Optional[int] = None,
    row_end: Optional[int] = None,
    log_stats: bool = True,
) -> APIResponse:
    """
    Simple function to process Amazon CSV

    Args:
        csv_path: Path to CSV file
        output_dir: Output directory (default: current)
        output_format: "pdf", "isdoc", or "both" (default: "both")
        language: "cs", "bilingual", or "original" (default: "bilingual")
        row_start: First row to process (1-based, optional)
        row_end: Last row to process (1-based, optional)
        log_stats: Log usage statistics (default: True)

    Returns:
        APIResponse with results

    Example:
        response = process_amazon_csv(
            'bestellungen.csv',
            output_dir='faktury/',
            output_format='both'
        )
        print(response.to_json())
    """
    # Convert string params to enums
    format_map = {"pdf": OutputFormat.PDF, "isdoc": OutputFormat.ISDOC, "both": OutputFormat.BOTH}
    lang_map = {"cs": OutputLanguage.CZECH, "bilingual": OutputLanguage.BILINGUAL, "original": OutputLanguage.ORIGINAL}

    api = AmazonInvoiceAPI(stats_callback=log_stats_to_cdb if log_stats else None)

    return api.process(
        csv_path=csv_path,
        output_dir=output_dir,
        output_format=format_map.get(output_format, OutputFormat.BOTH),
        language=lang_map.get(language, OutputLanguage.BILINGUAL),
        row_start=row_start,
        row_end=row_end,
        log_stats=log_stats,
    )


if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("Amazon Invoice Parser API")
    print("=" * 70)

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/amazon_invoices"

        response = process_amazon_csv(csv_path, output_dir)
        print(response.to_json())
    else:
        print("""
Použití / Usage:
    python api.py <csv_soubor> [výstupní_adresář]

Příklad / Example:
    python api.py bestellungen_von_2025.csv ./faktury/

API v Pythonu / Python API:
    from parsers.api import process_amazon_csv, AmazonInvoiceAPI

    # Jednoduché použití
    response = process_amazon_csv('soubor.csv', output_dir='faktury/')

    # Pokročilé použití
    api = AmazonInvoiceAPI()
    response = api.process(
        csv_path='soubor.csv',
        output_dir='faktury/',
        output_format=OutputFormat.BOTH,
        language=OutputLanguage.BILINGUAL,
        row_start=1,
        row_end=100
    )

    print(response.to_json())
""")
