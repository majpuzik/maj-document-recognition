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
ISDOC Repair Script - Generate ISDOC XML for all accounting documents in Paperless-NGX

This script processes all existing documents in Paperless-NGX and generates
ISDOC 6.0.2 XML files for accounting documents (invoices, receipts, etc.)

Usage:
    # Dry run (preview what would be generated)
    docker exec -it paperless-ngx python /usr/src/paperless/scripts/generate_isdoc_for_all.py

    # Generate ISDOC files
    docker exec -it paperless-ngx python /usr/src/paperless/scripts/generate_isdoc_for_all.py --apply

    # Generate for specific document types
    docker exec -it paperless-ngx python /usr/src/paperless/scripts/generate_isdoc_for_all.py --apply --types invoice,receipt

    # Limit number of documents
    docker exec -it paperless-ngx python /usr/src/paperless/scripts/generate_isdoc_for_all.py --apply --limit 100
"""

import os
import sys
import argparse
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')

try:
    import django
    django.setup()
    from documents.models import Document, DocumentType
except ImportError:
    print("Error: Must run inside Paperless container")
    print("Usage: docker exec -it paperless-ngx python /path/generate_isdoc_for_all.py")
    sys.exit(1)

# Import ISDOC generator from the main module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from llm_metadata_extractor import ISDOCGenerator, MetadataExtractor
except ImportError:
    print("Error: llm_metadata_extractor.py not found")
    print("Make sure to copy it to /usr/src/paperless/scripts/")
    sys.exit(1)


def is_accounting_document(doc, doc_types):
    """Check if document is likely an accounting document"""
    # Check by document type
    if doc.document_type and doc.document_type.name.lower() in doc_types:
        return True

    # Check by content patterns
    accounting_patterns = [
        r'faktura', r'invoice', r'účtenka', r'receipt',
        r'dobropis', r'credit.?note', r'proforma',
        r'daňový doklad', r'tax.?document',
        r'IČO', r'DIČ', r'celkem', r'total',
        r'k úhradě', r'payable', r'splatnost', r'due.?date'
    ]

    if doc.content:
        import re
        content_lower = doc.content.lower()[:5000]  # Check first 5000 chars
        for pattern in accounting_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Generate ISDOC XML for accounting documents")
    parser.add_argument("--apply", action="store_true", help="Actually generate files (default: dry run)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents")
    parser.add_argument("--types", type=str, default="invoice,faktura,receipt,účtenka,dobropis,credit",
                       help="Document types to process (comma-separated)")
    parser.add_argument("--output", type=str, default="/usr/src/paperless/media/isdoc",
                       help="Output directory for ISDOC files")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM for extraction (slower but better)")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                       help="Skip documents that already have ISDOC files")

    args = parser.parse_args()

    print("=" * 70)
    print("ISDOC REPAIR SCRIPT")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN (use --apply to generate)'}")
    print(f"Output: {args.output}")
    print(f"Use LLM: {args.use_llm}")
    print("=" * 70)

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    # Initialize extractor and generator
    extractor = MetadataExtractor(use_llm=args.use_llm)
    isdoc_gen = ISDOCGenerator(extractor)

    # Parse document types
    doc_types = [t.strip().lower() for t in args.types.split(',')]

    # Get all documents
    docs = Document.objects.all()
    if args.limit:
        docs = docs[:args.limit]

    total = docs.count()
    print(f"\nProcessing {total} documents...")

    # Statistics
    stats = {
        'processed': 0,
        'generated': 0,
        'skipped_not_accounting': 0,
        'skipped_no_content': 0,
        'skipped_existing': 0,
        'errors': 0,
    }

    for i, doc in enumerate(docs, 1):
        # Progress
        if i % 100 == 0:
            print(f"Progress: {i}/{total} ({100*i/total:.1f}%)")

        # Skip if no content
        if not doc.content:
            stats['skipped_no_content'] += 1
            continue

        # Check if accounting document
        if not is_accounting_document(doc, doc_types):
            stats['skipped_not_accounting'] += 1
            continue

        # Check if ISDOC already exists
        base_name = os.path.splitext(doc.original_filename or f"doc_{doc.id}")[0]
        isdoc_filename = f"{base_name}_{doc.id}.isdoc"
        isdoc_path = os.path.join(args.output, isdoc_filename)

        if args.skip_existing and os.path.exists(isdoc_path):
            stats['skipped_existing'] += 1
            continue

        stats['processed'] += 1

        try:
            # Extract invoice data
            data = isdoc_gen.extract_invoice_data(doc.content, doc.original_filename or "")

            # Check if we have minimum required data
            if not data.total_with_vat and not data.invoice_number and not data.supplier_ico:
                print(f"  Doc {doc.id}: Insufficient data, skipping")
                continue

            if args.apply:
                # Generate and save ISDOC
                xml = isdoc_gen.generate_xml(data)
                isdoc_gen.save_isdoc(xml, isdoc_path)
                stats['generated'] += 1
                print(f"  Doc {doc.id}: Generated {isdoc_filename}")
            else:
                # Dry run - show what would be generated
                print(f"  Doc {doc.id}: Would generate {isdoc_filename}")
                print(f"    Invoice: {data.invoice_number or 'N/A'}")
                print(f"    Supplier: {data.supplier_name or 'N/A'} (IČO: {data.supplier_ico or 'N/A'})")
                print(f"    Amount: {data.total_with_vat:.2f} {data.currency}")

        except Exception as e:
            print(f"  Doc {doc.id}: Error - {e}")
            stats['errors'] += 1

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total documents:          {total}")
    print(f"Processed:                {stats['processed']}")
    print(f"Generated ISDOC files:    {stats['generated']}")
    print(f"Skipped (not accounting): {stats['skipped_not_accounting']}")
    print(f"Skipped (no content):     {stats['skipped_no_content']}")
    print(f"Skipped (already exists): {stats['skipped_existing']}")
    print(f"Errors:                   {stats['errors']}")
    print(f"\nOutput directory: {args.output}")

    if not args.apply:
        print("\n*** DRY RUN - No files were generated ***")
        print("*** Run with --apply to generate ISDOC files ***")


if __name__ == "__main__":
    main()
