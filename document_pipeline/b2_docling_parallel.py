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
B2: Parallel Docling Processing
- Runs on all machines (Mac Mini, MacBook, DGX)
- Each instance processes a different range of documents
- Failed documents saved for B3 (LLM) processing
"""
import os
import sys
import json
import hashlib
import psutil
import time
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

# Config
DGX_BASE = "/home/puzik/document-pipeline"
INPUT_DIR = Path(f"{DGX_BASE}/input")
OUTPUT_DIR = Path(f"{DGX_BASE}/output/b2_docling")
FAILED_DIR = Path(f"{DGX_BASE}/work/b2_failed")
LOG_DIR = Path(f"{DGX_BASE}/logs")

MAX_CPU_PERCENT = 85
MAX_MEM_PERCENT = 85

# Field extraction patterns (28 fields)
FIELD_PATTERNS = {
    "doc_typ": ["faktura", "invoice", "smlouva", "contract", "účtenka", "receipt",
                "objednávka", "order", "dodací list", "delivery"],
    "protistrana_nazev": [],
    "protistrana_ico": [r"\b\d{8}\b"],
    "castka_celkem": [r"\d+[\s,]\d{2}\s*(Kč|CZK|EUR|USD)"],
    "datum_dokumentu": [r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}"],
    "cislo_dokumentu": [r"(č\.|číslo|number)[\s:]*(\d+[-/]?\d*)"],
    # ... etc
}

def check_resources():
    """Check if system resources are below threshold"""
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    return cpu < MAX_CPU_PERCENT and mem < MAX_MEM_PERCENT

def wait_for_resources():
    """Wait until resources are available"""
    while not check_resources():
        print(f"  Resources high (CPU: {psutil.cpu_percent()}%, MEM: {psutil.virtual_memory().percent}%), waiting...")
        time.sleep(10)

def get_file_hash(filepath):
    """Calculate MD5 hash of file"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def process_with_docling(pdf_path):
    """Process single PDF with Docling 2.64+"""
    try:
        from docling.document_converter import DocumentConverter

        # Simple converter - Docling 2.64 auto-detects format
        converter = DocumentConverter()

        # Convert
        result = converter.convert(str(pdf_path))

        # Extract text
        text = result.document.export_to_markdown()

        return {
            "success": True,
            "text": text,
            "pages": len(result.document.pages) if hasattr(result.document, 'pages') else 0,
            "tables": len(result.document.tables) if hasattr(result.document, 'tables') else 0
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def extract_fields(text, filename):
    """Extract 28 fields from text using patterns"""
    import re

    fields = {
        "doc_typ": "other",
        "protistrana_nazev": None,
        "protistrana_ico": None,
        "protistrana_typ": None,
        "castka_celkem": None,
        "datum_dokumentu": None,
        "cislo_dokumentu": None,
        "mena": None,
        "stav_platby": None,
        "datum_splatnosti": None,
        "kategorie": None,
        "email_from": None,
        "email_to": None,
        "email_subject": None,
        "od_osoba": None,
        "od_osoba_role": None,
        "od_firma": None,
        "pro_osoba": None,
        "pro_osoba_role": None,
        "pro_firma": None,
        "predmet": filename,
        "ai_summary": None,
        "ai_keywords": None,
        "ai_popis": None,
        "typ_sluzby": None,
        "nazev_sluzby": None,
        "predmet_typ": None,
        "predmet_nazev": None,
        "polozky_text": None,
        "polozky_json": None,
        "perioda": None
    }

    text_lower = text.lower()

    # Document type detection
    if any(x in text_lower for x in ["faktura", "invoice", "daňový doklad"]):
        fields["doc_typ"] = "invoice"
    elif any(x in text_lower for x in ["smlouva", "contract", "dohoda"]):
        fields["doc_typ"] = "contract"
    elif any(x in text_lower for x in ["účtenka", "receipt", "paragon"]):
        fields["doc_typ"] = "receipt"
    elif any(x in text_lower for x in ["objednávka", "order", "objednat"]):
        fields["doc_typ"] = "order"
    elif any(x in text_lower for x in ["výpis", "statement", "účet"]):
        fields["doc_typ"] = "bank_statement"

    # IČO extraction
    ico_match = re.search(r"IČO?[\s:]*(\d{8})", text)
    if ico_match:
        fields["protistrana_ico"] = ico_match.group(1)

    # Amount extraction
    amount_match = re.search(r"(\d+[\s\xa0]?\d*[,\.]\d{2})\s*(Kč|CZK|EUR|USD|€|\$)", text)
    if amount_match:
        fields["castka_celkem"] = amount_match.group(1).replace(" ", "").replace("\xa0", "")
        fields["mena"] = amount_match.group(2)

    # Date extraction
    date_match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", text)
    if date_match:
        fields["datum_dokumentu"] = f"{date_match.group(3)}-{date_match.group(2).zfill(2)}-{date_match.group(1).zfill(2)}"

    return fields

def process_document(pdf_path, output_dir, failed_dir):
    """Process single document through Docling pipeline"""
    file_hash = get_file_hash(pdf_path)
    output_file = output_dir / f"{file_hash}.json"

    # Skip if already processed
    if output_file.exists():
        return {"status": "skipped", "reason": "already_processed"}

    # Process with Docling
    result = process_with_docling(pdf_path)

    if result["success"]:
        # Extract fields
        fields = extract_fields(result["text"], pdf_path.name)

        # Save result
        output_data = {
            "file_path": str(pdf_path),
            "file_hash": file_hash,
            "processed_at": datetime.now().isoformat(),
            "method": "docling",
            "phase": "b2",
            "text_length": len(result["text"]),
            "pages": result.get("pages", 0),
            "tables": result.get("tables", 0),
            "doc_type": fields["doc_typ"],
            "fields": fields,
            "text_preview": result["text"][:2000]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        return {"status": "success", "doc_type": fields["doc_typ"]}
    else:
        # Save to failed for B3 processing
        failed_file = failed_dir / f"{file_hash}.json"
        failed_data = {
            "file_path": str(pdf_path),
            "file_hash": file_hash,
            "failed_at": datetime.now().isoformat(),
            "error": result["error"],
            "phase": "b2_failed"
        }

        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(failed_data, f, ensure_ascii=False, indent=2)

        return {"status": "failed", "error": result["error"]}

def main():
    parser = argparse.ArgumentParser(description='B2 Docling Parallel Processing')
    parser.add_argument('--instance', type=int, required=True, help='Instance number')
    parser.add_argument('--total-instances', type=int, required=True, help='Total instances')
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--source', type=str, default='all', help='Source: onedrive, dropbox, acasis, all')
    args = parser.parse_args()

    # Create directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Get all PDF files
    pdf_files = []
    sources = ['onedrive', 'dropbox', 'acasis'] if args.source == 'all' else [args.source]

    for source in sources:
        source_dir = INPUT_DIR / source
        if source_dir.exists():
            pdf_files.extend(source_dir.rglob("*.pdf"))
            pdf_files.extend(source_dir.rglob("*.PDF"))

    pdf_files = sorted(pdf_files)
    total_files = len(pdf_files)

    # Calculate range for this instance
    chunk_size = total_files // args.total_instances
    start_idx = args.instance * chunk_size
    end_idx = start_idx + chunk_size if args.instance < args.total_instances - 1 else total_files

    instance_files = pdf_files[start_idx:end_idx]

    print(f"=== B2 Docling Instance {args.instance}/{args.total_instances} ===")
    print(f"Total files: {total_files}")
    print(f"This instance: {len(instance_files)} files (index {start_idx}-{end_idx})")
    print(f"Workers: {args.workers}")
    print(f"Started: {datetime.now()}")
    print()

    # Process files
    success = 0
    failed = 0
    skipped = 0
    by_type = {}

    for i, pdf_path in enumerate(instance_files):
        # Check resources
        if i % 10 == 0:
            wait_for_resources()

        # Progress
        if i % 100 == 0:
            print(f"[{i}/{len(instance_files)}] Success: {success}, Failed: {failed}, Skipped: {skipped}")

        # Process
        result = process_document(pdf_path, OUTPUT_DIR, FAILED_DIR)

        if result["status"] == "success":
            success += 1
            doc_type = result.get("doc_type", "other")
            by_type[doc_type] = by_type.get(doc_type, 0) + 1
        elif result["status"] == "failed":
            failed += 1
        else:
            skipped += 1

    # Final stats
    print()
    print(f"=== Instance {args.instance} Complete ===")
    print(f"Success: {success}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"By type: {by_type}")
    print(f"Finished: {datetime.now()}")

    # Save stats
    stats_file = LOG_DIR / f"b2_stats_instance_{args.instance}.json"
    with open(stats_file, 'w') as f:
        json.dump({
            "instance": args.instance,
            "total_instances": args.total_instances,
            "files_processed": len(instance_files),
            "success": success,
            "failed": failed,
            "skipped": skipped,
            "by_type": by_type,
            "finished_at": datetime.now().isoformat()
        }, f, indent=2)

if __name__ == "__main__":
    main()
