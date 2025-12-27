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
Parallel upload of stuck consume files to Paperless DGX
=======================================================
Reads file list and uploads directly to Paperless API.
"""
import argparse
import json
import os
import sys
import hashlib
import email
from email import policy
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Paperless DGX config - CORRECTED
PAPERLESS_URL = "http://192.168.10.200:8020"
PAPERLESS_TOKEN = "155c91425631202132bb769241ad7d3196428df0"

# Try to import correspondent normalizer
try:
    from correspondent_normalizer import get_best_correspondent_name, normalize_correspondent
    HAS_NORMALIZER = True
except ImportError:
    HAS_NORMALIZER = False
    def get_best_correspondent_name(name):
        return name
    def normalize_correspondent(name):
        return name.lower().strip()

HEADERS = {
    "Authorization": f"Token {PAPERLESS_TOKEN}"
}

# Stats
stats = {
    "uploaded": 0,
    "skipped": 0,
    "failed": 0,
    "by_type": {}
}

# MD5 cache for deduplication
uploaded_hashes = set()

def get_file_hash(filepath):
    """Calculate MD5 hash of file"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def extract_email_metadata(eml_path):
    """Extract metadata from .eml file"""
    try:
        with open(eml_path, 'rb') as f:
            msg = email.message_from_binary_file(f, policy=policy.default)

        return {
            "from": str(msg.get("From", "")),
            "to": str(msg.get("To", "")),
            "subject": str(msg.get("Subject", "")),
            "date": str(msg.get("Date", ""))
        }
    except:
        return {}

def get_or_create_correspondent(name):
    """Get or create correspondent by normalized name"""
    if not name:
        return None

    # Normalize the name
    normalized = normalize_correspondent(name)
    display_name = get_best_correspondent_name(name)

    try:
        # Search for existing correspondent
        response = requests.get(
            f"{PAPERLESS_URL}/api/correspondents/",
            headers=HEADERS,
            params={'name__icontains': normalized[:20]},
            timeout=10
        )
        if response.status_code == 200:
            results = response.json().get('results', [])
            for c in results:
                if normalize_correspondent(c['name']) == normalized:
                    return c['id']

        # Create new correspondent
        response = requests.post(
            f"{PAPERLESS_URL}/api/correspondents/",
            headers={**HEADERS, 'Content-Type': 'application/json'},
            json={'name': display_name},
            timeout=10
        )
        if response.status_code in [200, 201]:
            return response.json().get('id')
    except Exception:
        pass

    return None


def upload_to_paperless(filepath, title=None, tags=None, correspondent_name=None):
    """Upload single file to Paperless DGX"""
    filepath = Path(filepath)

    if not filepath.exists():
        return False, "File not found"

    # Generate title from filename if not provided
    if not title:
        title = filepath.stem[:128]

    # Check hash for deduplication
    file_hash = get_file_hash(filepath)
    if file_hash in uploaded_hashes:
        return None, "duplicate"

    try:
        with open(filepath, 'rb') as f:
            files = {
                'document': (filepath.name, f, 'application/octet-stream')
            }
            data = {
                'title': title
            }
            if tags:
                data['tags'] = tags

            # Get or create correspondent
            if correspondent_name:
                correspondent_id = get_or_create_correspondent(correspondent_name)
                if correspondent_id:
                    data['correspondent'] = correspondent_id

            response = requests.post(
                f"{PAPERLESS_URL}/api/documents/post_document/",
                headers=HEADERS,
                files=files,
                data=data,
                timeout=60
            )

        if response.status_code in [200, 201, 202]:
            uploaded_hashes.add(file_hash)
            return True, response.json() if response.text else {}
        else:
            return False, f"HTTP {response.status_code}: {response.text[:100]}"

    except Exception as e:
        return False, str(e)

def extract_sender_name(from_header):
    """Extract clean sender name from email From header"""
    if not from_header:
        return None

    import re
    # Match "Name <email>" format
    match = re.match(r'^([^<]+)\s*<[^>]+>$', from_header)
    if match:
        return match.group(1).strip().strip('"\'')

    # Match just email format
    match = re.match(r'^<?([^@]+)@[^>]+>?$', from_header)
    if match:
        name = match.group(1).replace('.', ' ').replace('_', ' ')
        return name.title()

    return from_header


def process_file(filepath):
    """Process single file - extract metadata and upload"""
    filepath = Path(filepath)
    ext = filepath.suffix.lower()

    title = filepath.stem[:128]
    tags = []
    correspondent = None

    # For .eml files, extract metadata for better title
    if ext == '.eml':
        meta = extract_email_metadata(filepath)
        if meta.get('subject'):
            title = f"{filepath.stem[:40]}_{meta['subject'][:80]}"
        tags = ['email-import']

        # Extract correspondent from sender
        if meta.get('from'):
            correspondent = extract_sender_name(meta['from'])
    elif ext == '.pdf':
        tags = ['pdf-import']

    result, msg = upload_to_paperless(filepath, title, tags, correspondent)
    return filepath.name, ext, result, msg

def main():
    parser = argparse.ArgumentParser(description="Upload stuck files to Paperless DGX")
    parser.add_argument("--file-list", required=True, help="File containing list of files to upload")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers")
    parser.add_argument("--start", type=int, default=0, help="Start from position")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files")
    args = parser.parse_args()

    # Load file list
    with open(args.file_list) as f:
        files = [line.strip() for line in f if line.strip()]

    total = len(files)
    print(f"=== Parallel Upload to Paperless DGX ===")
    print(f"Total files: {total}")
    print(f"Workers: {args.workers}")
    print(f"Target: {PAPERLESS_URL}")

    # Apply start/limit
    if args.start > 0:
        files = files[args.start:]
        print(f"Starting from: {args.start}")
    if args.limit > 0:
        files = files[:args.limit]
        print(f"Limited to: {args.limit}")

    print(f"Processing: {len(files)} files")
    print("=" * 50)

    uploaded = 0
    skipped = 0
    failed = 0
    by_type = {}

    # Progress bar
    if HAS_TQDM:
        pbar = tqdm(total=len(files), desc="Upload", unit="file",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        for future in as_completed(futures):
            try:
                name, ext, result, msg = future.result()

                if result is True:
                    uploaded += 1
                    by_type[ext] = by_type.get(ext, 0) + 1
                elif result is None:
                    skipped += 1  # duplicate
                else:
                    failed += 1

                if HAS_TQDM:
                    pbar.update(1)
                    pbar.set_postfix({"✓": uploaded, "skip": skipped, "✗": failed})
                elif (uploaded + skipped + failed) % 100 == 0:
                    print(f"Progress: {uploaded + skipped + failed}/{len(files)} | Uploaded: {uploaded} | Skip: {skipped} | Failed: {failed}")

            except Exception as e:
                failed += 1
                if HAS_TQDM:
                    pbar.update(1)

    if HAS_TQDM:
        pbar.close()

    # Final stats
    print("\n" + "=" * 50)
    print("=== UPLOAD COMPLETE ===")
    print(f"Uploaded: {uploaded}")
    print(f"Skipped (duplicates): {skipped}")
    print(f"Failed: {failed}")
    print(f"By type: {by_type}")

    # Save stats
    stats = {
        "completed": datetime.now().isoformat(),
        "uploaded": uploaded,
        "skipped": skipped,
        "failed": failed,
        "by_type": by_type
    }

    stats_file = Path(args.file_list).parent / f"upload_stats_{Path(args.file_list).stem}.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Stats saved to: {stats_file}")

if __name__ == "__main__":
    main()
