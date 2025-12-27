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
Phase 5: Import to Paperless-NGX with Custom Fields
====================================================
Imports extracted documents with all 31 custom fields.

Version: 2.0.0
"""
import json
import os
import sys
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

# Progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Auto-detect paths
if Path("/home/puzik/mnt/acasis").exists():
    ACASIS_ROOT = Path("/home/puzik/mnt/acasis")
else:
    ACASIS_ROOT = Path("/Volumes/ACASIS")

# Config - Load from GUI config or use defaults
GUI_CONFIG_FILE = Path(__file__).parent.parent / "gui" / "config.json"
if GUI_CONFIG_FILE.exists():
    with open(GUI_CONFIG_FILE) as f:
        _cfg = json.load(f)
        PAPERLESS_URL = _cfg.get("paperless", {}).get("url", "http://192.168.10.200:8020")
        PAPERLESS_TOKEN = _cfg.get("paperless", {}).get("token", "")
else:
    PAPERLESS_URL = "http://192.168.10.200:8020"
    PAPERLESS_TOKEN = "155c91425631202132bb769241ad7d3196428df0"

BASE_DIR = ACASIS_ROOT / "apps/maj-document-recognition/phase1_output"
RESULTS_DIR = BASE_DIR / "phase1_results"
PHASE2_DIR = BASE_DIR / "phase2_results"
EMAIL_DIR = ACASIS_ROOT / "parallel_scan_1124_1205/thunderbird-emails"

# 31 Custom Fields mapping (field_name -> paperless_data_type)
CUSTOM_FIELDS = {
    "doc_typ": "string",
    "protistrana_nazev": "string",
    "protistrana_ico": "string",
    "protistrana_typ": "string",
    "castka_celkem": "float",
    "datum_dokumentu": "date",
    "cislo_dokumentu": "string",
    "mena": "string",
    "stav_platby": "string",
    "datum_splatnosti": "date",
    "kategorie": "string",
    "email_from": "string",
    "email_to": "string",
    "email_subject": "string",
    "od_osoba": "string",
    "od_osoba_role": "string",
    "od_firma": "string",
    "pro_osoba": "string",
    "pro_osoba_role": "string",
    "pro_firma": "string",
    "predmet": "string",
    "ai_summary": "string",
    "ai_keywords": "string",
    "ai_popis": "string",
    "typ_sluzby": "string",
    "nazev_sluzby": "string",
    "predmet_typ": "string",
    "predmet_nazev": "string",
    "polozky_text": "string",
    "polozky_json": "string",
    "perioda": "string",
}

HEADERS = {
    "Authorization": f"Token {PAPERLESS_TOKEN}"
}

# Cache for tags, correspondents, and custom fields
tag_cache = {}
correspondent_cache = {}
custom_field_cache = {}  # name -> field_id
document_type_cache = {}


def get_or_create_custom_field(name: str, data_type: str = "string") -> int:
    """Get or create a custom field in Paperless"""
    if name in custom_field_cache:
        return custom_field_cache[name]

    # Search existing
    r = requests.get(
        f"{PAPERLESS_URL}/api/custom_fields/",
        headers=HEADERS,
        params={"name": name}
    )
    if r.status_code == 200:
        results = r.json().get("results", [])
        for f in results:
            if f.get("name") == name:
                custom_field_cache[name] = f["id"]
                return f["id"]

    # Create new
    r = requests.post(
        f"{PAPERLESS_URL}/api/custom_fields/",
        headers=HEADERS,
        json={"name": name, "data_type": data_type}
    )
    if r.status_code == 201:
        custom_field_cache[name] = r.json()["id"]
        return custom_field_cache[name]

    return None


def get_or_create_document_type(name: str) -> int:
    """Get or create a document type in Paperless"""
    if not name:
        return None
    if name in document_type_cache:
        return document_type_cache[name]

    # Search existing
    r = requests.get(
        f"{PAPERLESS_URL}/api/document_types/",
        headers=HEADERS,
        params={"name__iexact": name}
    )
    if r.status_code == 200:
        results = r.json().get("results", [])
        if results:
            document_type_cache[name] = results[0]["id"]
            return document_type_cache[name]

    # Create new
    r = requests.post(
        f"{PAPERLESS_URL}/api/document_types/",
        headers=HEADERS,
        json={"name": name}
    )
    if r.status_code == 201:
        document_type_cache[name] = r.json()["id"]
        return document_type_cache[name]

    return None


def ensure_custom_fields_exist():
    """Pre-create all 31 custom fields"""
    print("Creating custom fields in Paperless...", flush=True)
    created = 0
    for field_name, data_type in CUSTOM_FIELDS.items():
        field_id = get_or_create_custom_field(field_name, data_type)
        if field_id:
            created += 1
    print(f"  Custom fields ready: {created}/{len(CUSTOM_FIELDS)}", flush=True)
    return created

def get_or_create_tag(name):
    if not name:
        return None
    if name in tag_cache:
        return tag_cache[name]
    
    # Search existing
    r = requests.get(f"{PAPERLESS_URL}/api/tags/", headers=HEADERS, params={"name__iexact": name})
    if r.status_code == 200:
        results = r.json().get("results", [])
        if results:
            tag_cache[name] = results[0]["id"]
            return tag_cache[name]
    
    # Create new
    r = requests.post(f"{PAPERLESS_URL}/api/tags/", headers=HEADERS, json={"name": name})
    if r.status_code == 201:
        tag_cache[name] = r.json()["id"]
        return tag_cache[name]
    return None

def get_or_create_correspondent(name):
    if not name:
        return None
    name = name[:128]  # Limit length
    if name in correspondent_cache:
        return correspondent_cache[name]
    
    r = requests.get(f"{PAPERLESS_URL}/api/correspondents/", headers=HEADERS, params={"name__iexact": name})
    if r.status_code == 200:
        results = r.json().get("results", [])
        if results:
            correspondent_cache[name] = results[0]["id"]
            return correspondent_cache[name]
    
    r = requests.post(f"{PAPERLESS_URL}/api/correspondents/", headers=HEADERS, json={"name": name})
    if r.status_code == 201:
        correspondent_cache[name] = r.json()["id"]
        return correspondent_cache[name]
    return None

def find_email_file(email_id):
    """Find the original email file"""
    for mailbox in EMAIL_DIR.iterdir():
        if not mailbox.is_dir():
            continue
        for folder in mailbox.iterdir():
            if email_id in folder.name:
                eml = folder / "message.eml"
                if eml.exists():
                    return eml
                # Check for PDF attachments
                for f in folder.glob("*.pdf"):
                    return f
    return None

def set_document_custom_fields(document_id: int, fields: dict):
    """Set custom fields on uploaded document"""
    if not document_id or not fields:
        return

    custom_fields_data = []

    for field_name, data_type in CUSTOM_FIELDS.items():
        value = fields.get(field_name)
        if value is None:
            continue

        field_id = custom_field_cache.get(field_name)
        if not field_id:
            field_id = get_or_create_custom_field(field_name, data_type)

        if field_id:
            # Format value based on type
            if data_type == "float" and value is not None:
                try:
                    value = float(value)
                except:
                    value = None
            elif data_type == "date" and value:
                # Ensure YYYY-MM-DD format
                if isinstance(value, str) and len(value) >= 10:
                    value = value[:10]
                else:
                    value = None

            if value is not None:
                custom_fields_data.append({
                    "field": field_id,
                    "value": value
                })

    if custom_fields_data:
        try:
            r = requests.patch(
                f"{PAPERLESS_URL}/api/documents/{document_id}/",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={"custom_fields": custom_fields_data},
                timeout=30
            )
            return r.status_code == 200
        except:
            pass

    return False


def import_document(result_file):
    """Import a single document to Paperless with custom fields"""
    try:
        with open(result_file) as f:
            data = json.load(f)

        email_id = data.get("email_id", "")
        # Try both field keys for compatibility
        fields = data.get("fields", data.get("extracted_fields", {}))
        doc_type = data.get("doc_type", "other")

        # Also get email folder directly from JSON if available
        email_folder = data.get("email_folder", "")

        # Find source file - first try direct email_folder, then search
        source_file = None
        if email_folder:
            folder_path = Path(email_folder)
            if folder_path.exists():
                eml = folder_path / "message.eml"
                if eml.exists():
                    source_file = eml
                else:
                    # Try PDF attachment
                    for pdf in folder_path.glob("*.pdf"):
                        source_file = pdf
                        break

        # Fallback to search
        if not source_file:
            source_file = find_email_file(email_id)

        if not source_file:
            return None, f"No source file for {email_id}"

        # Prepare metadata - also check root metadata
        metadata = data.get("metadata", {})
        title = fields.get("email_subject") or metadata.get("subject") or fields.get("ai_summary") or email_id
        if title:
            title = title[:128]
        else:
            title = email_id[:128]

        # Get correspondent from fields or metadata
        correspondent_name = fields.get("protistrana_nazev") or fields.get("od_firma") or fields.get("od_osoba")
        if not correspondent_name and metadata:
            # Extract from email From header
            from_header = metadata.get("from", "")
            if from_header:
                # Simple extraction: "Name <email>" -> "Name"
                if "<" in from_header:
                    correspondent_name = from_header.split("<")[0].strip().strip('"')
                else:
                    correspondent_name = from_header.split("@")[0] if "@" in from_header else from_header

        correspondent = get_or_create_correspondent(correspondent_name) if correspondent_name else None

        # Document type (map to Czech)
        doc_type_map = {
            "invoice": "Faktura",
            "order": "Objednávka",
            "contract": "Smlouva",
            "marketing": "Marketing",
            "correspondence": "Korespondence",
            "receipt": "Účtenka",
            "bank_statement": "Bankovní výpis",
            "tax_document": "Daňový doklad",
            "system_notification": "Systémová notifikace",
            "it_notes": "IT poznámky",
            "project_notes": "Projektové poznámky",
            "newsletter": "Newsletter",
            "other": "Ostatní"
        }
        paperless_doc_type = doc_type_map.get(doc_type, doc_type)
        doc_type_id = get_or_create_document_type(paperless_doc_type)

        # Tags based on doc_type and category
        tags = []
        tag_id = get_or_create_tag(paperless_doc_type)
        if tag_id:
            tags.append(tag_id)

        # Add category tag
        category = fields.get("kategorie")
        if category:
            cat_tag = get_or_create_tag(category)
            if cat_tag:
                tags.append(cat_tag)

        # Upload document
        with open(source_file, "rb") as f:
            files = {"document": (source_file.name, f)}
            upload_data = {
                "title": title,
            }
            if correspondent:
                upload_data["correspondent"] = correspondent
            if doc_type_id:
                upload_data["document_type"] = doc_type_id
            if tags:
                upload_data["tags"] = tags

            r = requests.post(
                f"{PAPERLESS_URL}/api/documents/post_document/",
                headers=HEADERS,
                files=files,
                data=upload_data,
                timeout=60
            )

            if r.status_code in (200, 201, 202):
                # Get document ID from response or task
                response_data = r.json() if r.text else {}

                # Handle both dict response and string (task UUID) response
                if isinstance(response_data, dict):
                    doc_id = response_data.get("id") or response_data.get("document_id")
                elif isinstance(response_data, str):
                    # Paperless returns task UUID as string for async processing
                    doc_id = response_data  # Store task ID for now
                else:
                    doc_id = None

                # For now, we return success and custom fields will be set in batch later
                return True, doc_type, doc_id, fields
            else:
                return None, f"Upload failed: {r.status_code}", None, None

    except Exception as e:
        # import traceback
        # traceback.print_exc()
        return None, str(e), None, None

def collect_all_results():
    """Collect results from Phase 1 and Phase 2"""
    results = []

    # Phase 1 results
    if RESULTS_DIR.exists():
        for f in RESULTS_DIR.glob("*.json"):
            results.append(("phase1", f))

    # Phase 2 results
    if PHASE2_DIR.exists():
        for f in PHASE2_DIR.glob("*.json"):
            results.append(("phase2", f))

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase 5: Import to Paperless-NGX with Custom Fields")
    parser.add_argument("--start", type=int, default=0, help="Start from position")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of imports (0 = all)")
    parser.add_argument("--phase", choices=["1", "2", "all"], default="all", help="Which phase results to import")
    parser.add_argument("--test", action="store_true", help="Test connection only")
    args = parser.parse_args()

    print("=" * 60, flush=True)
    print(f"Phase 5: Import to Paperless-NGX v2.0", flush=True)
    print(f"URL: {PAPERLESS_URL}", flush=True)
    print("=" * 60, flush=True)

    # Test connection
    try:
        r = requests.get(f"{PAPERLESS_URL}/api/documents/?page_size=1", headers=HEADERS, timeout=10)
        if r.status_code != 200:
            print(f"ERROR: Cannot connect to Paperless ({r.status_code})", flush=True)
            return
        print(f"Connection OK", flush=True)
    except Exception as e:
        print(f"ERROR: Cannot connect to Paperless: {e}", flush=True)
        return

    if args.test:
        print("Test mode - exiting", flush=True)
        return

    # Ensure custom fields exist
    ensure_custom_fields_exist()

    # Collect results
    all_results = collect_all_results()

    # Filter by phase
    if args.phase == "1":
        all_results = [(p, f) for p, f in all_results if p == "phase1"]
    elif args.phase == "2":
        all_results = [(p, f) for p, f in all_results if p == "phase2"]

    total = len(all_results)
    print(f"\nTotal results to import: {total}", flush=True)
    print(f"  Phase 1: {sum(1 for p, _ in all_results if p == 'phase1')}", flush=True)
    print(f"  Phase 2: {sum(1 for p, _ in all_results if p == 'phase2')}", flush=True)

    if args.start > 0:
        all_results = all_results[args.start:]
        print(f"Starting from: {args.start}", flush=True)

    if args.limit > 0:
        all_results = all_results[:args.limit]
        print(f"Limited to: {args.limit}", flush=True)

    success = 0
    failed = 0
    by_type = {}
    pending_custom_fields = []  # (doc_id, fields) for batch update

    # Setup progress bar for import
    if HAS_TQDM:
        pbar = tqdm(all_results, desc="Phase5 Import", unit="doc",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
    else:
        pbar = all_results

    for i, (phase, rf) in enumerate(pbar):
        pos = args.start + i + 1

        result = import_document(rf)

        if result[0]:  # ok
            success += 1
            doc_type = result[1]
            doc_id = result[2]
            fields = result[3]
            by_type[doc_type] = by_type.get(doc_type, 0) + 1

            # Queue custom fields update
            if doc_id and fields:
                pending_custom_fields.append((doc_id, fields))

            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed, "type": doc_type[:8] if doc_type else "?"})
        else:
            failed += 1
            error = result[1]
            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed})
            elif failed <= 10:
                print(f"  Error: {error}", flush=True)

        if not HAS_TQDM and pos % 100 == 0:
            print(f"[{pos}/{total}] Success: {success}, Failed: {failed}", flush=True)

    # Batch update custom fields
    if pending_custom_fields:
        print(f"\nUpdating custom fields for {len(pending_custom_fields)} documents...", flush=True)
        cf_success = 0

        if HAS_TQDM:
            cf_pbar = tqdm(pending_custom_fields, desc="Custom Fields", unit="doc")
        else:
            cf_pbar = pending_custom_fields

        for doc_id, fields in cf_pbar:
            if set_document_custom_fields(doc_id, fields):
                cf_success += 1
                if HAS_TQDM:
                    cf_pbar.set_postfix({"✓": cf_success})
        print(f"  Custom fields updated: {cf_success}/{len(pending_custom_fields)}", flush=True)

    print(f"\n{'=' * 60}", flush=True)
    print(f"IMPORT COMPLETE", flush=True)
    print(f"  Success: {success}", flush=True)
    print(f"  Failed: {failed}", flush=True)
    print(f"  By type: {json.dumps(by_type, indent=2)}", flush=True)
    print(f"{'=' * 60}", flush=True)

    # Save stats
    stats = {
        "timestamp": datetime.now().isoformat(),
        "paperless_url": PAPERLESS_URL,
        "total": total,
        "success": success,
        "failed": failed,
        "by_type": by_type
    }
    stats_file = BASE_DIR / "phase5_stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\nStats saved to: {stats_file}", flush=True)


if __name__ == "__main__":
    main()
