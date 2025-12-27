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

"""Phase 6: Fix tags on uploaded documents"""
import json
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Config - ADMIN TOKEN with full permissions
PAPERLESS_URL = "http://192.168.10.200:8020"
PAPERLESS_TOKEN = "155c91425631202132bb769241ad7d3196428df0"
RESULTS_DIR = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output/phase1_results")

HEADERS = {
    "Authorization": f"Token {PAPERLESS_TOKEN}",
    "Content-Type": "application/json"
}

# Cache
tag_cache = {}
doc_cache = {}

def get_or_create_tag(name):
    """Get or create tag by name"""
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

    print(f"  Failed to create tag '{name}': {r.status_code} {r.text[:100]}")
    return None

def load_all_documents():
    """Load all documents from Paperless into cache"""
    print("Loading documents from Paperless...", flush=True)
    page = 1
    while True:
        r = requests.get(
            f"{PAPERLESS_URL}/api/documents/",
            headers=HEADERS,
            params={"page": page, "page_size": 100}
        )
        if r.status_code != 200:
            break

        data = r.json()
        results = data.get("results", [])
        if not results:
            break

        for doc in results:
            # Index by title (which contains email_id)
            title = doc.get("title", "")
            doc_cache[title] = doc["id"]

        if not data.get("next"):
            break
        page += 1

        if page % 10 == 0:
            print(f"  Loaded {len(doc_cache)} documents...", flush=True)

    print(f"Loaded {len(doc_cache)} documents from Paperless", flush=True)

def update_document_tag(doc_id, tag_id):
    """Add tag to document"""
    # First get current tags
    r = requests.get(f"{PAPERLESS_URL}/api/documents/{doc_id}/", headers=HEADERS)
    if r.status_code != 200:
        return False

    current_tags = r.json().get("tags", [])
    if tag_id in current_tags:
        return True  # Already has tag

    current_tags.append(tag_id)

    # Update
    r = requests.patch(
        f"{PAPERLESS_URL}/api/documents/{doc_id}/",
        headers=HEADERS,
        json={"tags": current_tags}
    )
    return r.status_code == 200

def process_result_file(result_file):
    """Process one result file and update tag"""
    try:
        with open(result_file) as f:
            data = json.load(f)

        email_id = data.get("email_id", "")
        doc_type = data.get("doc_type", "other")

        if not email_id or not doc_type:
            return None, "No email_id or doc_type"

        # Find document in Paperless by title
        doc_id = None
        for title, did in doc_cache.items():
            if email_id in title:
                doc_id = did
                break

        if not doc_id:
            return None, f"Document not found: {email_id[:50]}"

        # Get or create tag
        tag_id = get_or_create_tag(doc_type)
        if not tag_id:
            return None, f"Failed to get tag: {doc_type}"

        # Update document
        if update_document_tag(doc_id, tag_id):
            return True, doc_type
        else:
            return None, "Failed to update document"

    except Exception as e:
        return None, str(e)

# Pre-loaded result file stems for fast lookup
result_stems = set()

def load_result_stems():
    """Load all result file stems into memory for O(1) lookup"""
    global result_stems
    print("Loading result file index...", flush=True)
    result_stems = {rf.stem for rf in RESULTS_DIR.glob("*.json")}
    print(f"  Indexed {len(result_stems)} result files", flush=True)

def find_result_for_document(title):
    """Find result JSON file for a Paperless document by extracting email_id from title"""
    import re

    # Pattern: YYYYMMDD_HHMMSS_hexid_  (our email import format)
    match = re.match(r'(\d{8}_\d{6}_[a-f0-9]+)', title)
    if match:
        email_id = match.group(1)
        if email_id in result_stems:
            return RESULTS_DIR / f"{email_id}.json", email_id

    # For old format (1allpdf_...) - skip, these have different tags
    if title.startswith("1all"):
        return None, None

    return None, None


def process_document(doc_id, title):
    """Process one Paperless document - find result and update tag"""
    result_file, email_id = find_result_for_document(title)

    if not result_file:
        return None, "no_result"

    try:
        with open(result_file) as f:
            data = json.load(f)

        doc_type = data.get("doc_type", "other")
        if not doc_type:
            doc_type = "other"

        # Get or create tag
        tag_id = get_or_create_tag(doc_type)
        if not tag_id:
            return None, f"Failed to get tag: {doc_type}"

        # Update document
        if update_document_tag(doc_id, tag_id):
            return True, doc_type
        else:
            return None, "Failed to update"

    except Exception as e:
        return None, str(e)


def main():
    # Load result file index first
    load_result_stems()

    # Pre-create common tags
    print("Creating tags...", flush=True)
    common_tags = ["invoice", "contract", "receipt", "marketing", "correspondence",
                   "order", "delivery_note", "bank_statement", "legal", "other",
                   "loxone_statistics"]
    for tag in common_tags:
        get_or_create_tag(tag)
    print(f"Tags ready: {len(tag_cache)}", flush=True)

    # Iterate through Paperless documents (NOT result files!)
    print("\nLoading and processing Paperless documents...", flush=True)

    success = 0
    failed = 0
    no_result = 0
    by_type = {}
    total_docs = 0

    # First, get total count for progress bar
    r = requests.get(f"{PAPERLESS_URL}/api/documents/", headers=HEADERS, params={"page": 1, "page_size": 1})
    total_count = r.json().get("count", 0) if r.status_code == 200 else 0

    # Setup progress bar
    pbar = None
    if HAS_TQDM and total_count > 0:
        pbar = tqdm(total=total_count, desc="Phase6 Tag Fix", unit="doc",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")

    page = 1
    while True:
        r = requests.get(
            f"{PAPERLESS_URL}/api/documents/",
            headers=HEADERS,
            params={"page": page, "page_size": 100}
        )
        if r.status_code != 200:
            print(f"API error: {r.status_code}", flush=True)
            break

        data = r.json()
        results = data.get("results", [])
        if not results:
            break

        for doc in results:
            doc_id = doc["id"]
            title = doc.get("title", "")
            total_docs += 1

            ok, result = process_document(doc_id, title)
            if ok:
                success += 1
                by_type[result] = by_type.get(result, 0) + 1
            elif result == "no_result":
                no_result += 1
            else:
                failed += 1

            if pbar:
                pbar.update(1)
                pbar.set_postfix({"✓": success, "✗": failed, "skip": no_result})

        if not HAS_TQDM and total_docs % 500 == 0:
            print(f"[{total_docs}] Success: {success}, No result: {no_result}, Failed: {failed}", flush=True)

        if not data.get("next"):
            break
        page += 1

    if pbar:
        pbar.close()

    print(f"\n=== TAG FIX COMPLETE ===", flush=True)
    print(f"Total documents in Paperless: {total_docs}", flush=True)
    print(f"Success (tag updated): {success}", flush=True)
    print(f"No result file found: {no_result}", flush=True)
    print(f"Failed: {failed}", flush=True)
    print(f"By type: {by_type}", flush=True)

if __name__ == "__main__":
    main()
