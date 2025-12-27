#!/usr/bin/env python3
"""
NAS5 Docker Apps Collection
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
ISDOC Generator Wrapper
=======================
Wrapper pro generování ISDOC XML pro účetní dokumenty.
Volá se z Phase 1 (Docling) a Phase 2 (LLM) pro dokumenty typu:
- invoice, receipt, tax_document

Author: Claude Code
Date: 2025-12-16
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.llm_metadata_extractor import ISDOCGenerator, ISDOCInvoiceData

# ISDOC output directory
ISDOC_DIR = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output/isdoc_xml")

# Document types that should get ISDOC
ACCOUNTING_TYPES = {"invoice", "receipt", "tax_document", "bank_statement"}


def should_generate_isdoc(doc_type: str) -> bool:
    """Check if document type requires ISDOC"""
    return doc_type.lower() in ACCOUNTING_TYPES


def generate_isdoc_for_result(result: dict) -> tuple[bool, str]:
    """
    Generate ISDOC XML for a processing result.

    Args:
        result: Dictionary with email_id, doc_type, extracted_fields, text_content

    Returns:
        (success, path_or_error)
    """
    doc_type = result.get("doc_type", "other")

    if not should_generate_isdoc(doc_type):
        return False, f"Not accounting type: {doc_type}"

    try:
        ISDOC_DIR.mkdir(parents=True, exist_ok=True)

        email_id = result.get("email_id", "unknown")
        fields = result.get("extracted_fields", {})
        text = result.get("text_content", "")

        # If no text, try to build from fields
        if not text:
            text = build_text_from_fields(fields)

        generator = ISDOCGenerator()

        # Extract invoice data from text
        invoice_data = generator.extract_invoice_data(text, email_id)

        # Override with extracted fields if available
        if fields.get("cislo_dokumentu"):
            invoice_data.invoice_id = fields["cislo_dokumentu"]
        if fields.get("datum_dokumentu"):
            try:
                invoice_data.issue_date = datetime.strptime(fields["datum_dokumentu"], "%Y-%m-%d")
            except:
                pass
        if fields.get("datum_splatnosti"):
            try:
                invoice_data.due_date = datetime.strptime(fields["datum_splatnosti"], "%Y-%m-%d")
            except:
                pass
        if fields.get("castka_celkem"):
            invoice_data.total_amount = float(fields["castka_celkem"])
        if fields.get("mena"):
            invoice_data.currency = fields["mena"]
        if fields.get("protistrana_nazev"):
            invoice_data.supplier_name = fields["protistrana_nazev"]
        if fields.get("protistrana_ico"):
            invoice_data.supplier_ico = fields["protistrana_ico"]

        # Generate XML
        xml_content = generator.generate_xml(invoice_data)

        # Save
        output_path = ISDOC_DIR / f"{email_id}.isdoc.xml"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        return True, str(output_path)

    except Exception as e:
        return False, str(e)


def build_text_from_fields(fields: dict) -> str:
    """Build pseudo-text from extracted fields for ISDOC extraction"""
    parts = []

    if fields.get("protistrana_nazev"):
        parts.append(f"Dodavatel: {fields['protistrana_nazev']}")
    if fields.get("protistrana_ico"):
        parts.append(f"IČO: {fields['protistrana_ico']}")
    if fields.get("cislo_dokumentu"):
        parts.append(f"Číslo faktury: {fields['cislo_dokumentu']}")
    if fields.get("datum_dokumentu"):
        parts.append(f"Datum: {fields['datum_dokumentu']}")
    if fields.get("datum_splatnosti"):
        parts.append(f"Splatnost: {fields['datum_splatnosti']}")
    if fields.get("castka_celkem"):
        parts.append(f"Celkem: {fields['castka_celkem']} {fields.get('mena', 'CZK')}")
    if fields.get("polozky_text"):
        parts.append(f"Položky: {fields['polozky_text']}")

    return "\n".join(parts)


def process_result_file(result_path: Path) -> tuple[bool, str]:
    """Process a single result JSON file and generate ISDOC if applicable"""
    try:
        with open(result_path) as f:
            result = json.load(f)

        return generate_isdoc_for_result(result)

    except Exception as e:
        return False, str(e)


def main():
    """CLI for batch ISDOC generation"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate ISDOC XML for accounting documents")
    parser.add_argument("--input", type=str, help="Input directory with result JSON files")
    parser.add_argument("--single", type=str, help="Single result JSON file")
    parser.add_argument("--filter", type=str, default="invoice,receipt,tax_document",
                       help="Document types to process (comma-separated)")
    args = parser.parse_args()

    ISDOC_DIR.mkdir(parents=True, exist_ok=True)

    if args.single:
        ok, result = process_result_file(Path(args.single))
        print(f"{'✓' if ok else '✗'} {result}")
        return

    input_dir = Path(args.input) if args.input else Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output/phase1_results")

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        return

    allowed_types = set(args.filter.split(","))
    success = 0
    skipped = 0
    failed = 0

    result_files = list(input_dir.glob("*.json"))
    total = len(result_files)

    print(f"Processing {total} result files...")
    print(f"Filter: {allowed_types}")

    for i, rf in enumerate(result_files):
        if i % 100 == 0:
            print(f"[{i}/{total}] Success: {success}, Skipped: {skipped}, Failed: {failed}")

        try:
            with open(rf) as f:
                result = json.load(f)

            doc_type = result.get("doc_type", "other")

            if doc_type not in allowed_types:
                skipped += 1
                continue

            ok, msg = generate_isdoc_for_result(result)
            if ok:
                success += 1
            else:
                failed += 1

        except Exception as e:
            failed += 1

    print(f"\n=== ISDOC Generation Complete ===")
    print(f"Success: {success}")
    print(f"Skipped (non-accounting): {skipped}")
    print(f"Failed: {failed}")
    print(f"Output: {ISDOC_DIR}")


if __name__ == "__main__":
    main()
