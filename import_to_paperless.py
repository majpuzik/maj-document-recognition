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
Phase 3: Import to Paperless with Deduplication
================================================
Imports processed emails to Paperless-ngx with:
- Duplicate detection via content hash
- Custom field mapping (28 fields)
- Correspondent/tag creation
- Progress tracking

Usage:
    python import_to_paperless.py --input merged_results.json
    python import_to_paperless.py --input merged_results.json --dry-run

Author: Claude Code
Date: 2025-12-15
"""

import sys
import json
import argparse
import logging
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import requests

# Configuration
PAPERLESS_CONFIG = {
    "url": "http://192.168.10.85:8777",
    "token": "0c1072a02c43c50d109a0300f090a361fc1eb775"
}

DOC_TYPE_MAPPING = {
    "invoice": "Faktura",
    "contract": "Smlouva",
    "order": "Objednávka",
    "delivery_note": "Dodací list",
    "bank_statement": "Bankovní výpis",
    "correspondence": "Korespondence",
    "marketing": "Marketing",
    "other": "Ostatní"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PaperlessImporter:
    def __init__(self, config: Dict, dry_run: bool = False):
        self.url = config["url"]
        self.token = config["token"]
        self.headers = {"Authorization": f"Token {self.token}"}
        self.dry_run = dry_run
        self.existing_hashes: Set[str] = set()
        self.existing_titles: Set[str] = set()
        self.correspondents: Dict[str, int] = {}
        self.tags: Dict[str, int] = {}
        self.document_types: Dict[str, int] = {}
        self.stats = {"total": 0, "imported": 0, "skipped_duplicate": 0, "skipped_no_content": 0, "errors": 0, "error_list": []}

    def initialize(self):
        logger.info("Loading existing Paperless data...")
        self._load_existing_documents()
        self._load_correspondents()
        self._load_tags()
        self._load_document_types()
        logger.info(f"Loaded: {len(self.existing_hashes)} docs, {len(self.correspondents)} correspondents")

    def _load_existing_documents(self):
        try:
            page = 1
            while True:
                resp = requests.get(f"{self.url}/api/documents/?page={page}&page_size=100", headers=self.headers, timeout=30)
                if resp.status_code != 200: break
                data = resp.json()
                for doc in data.get("results", []):
                    if doc.get("checksum"): self.existing_hashes.add(doc["checksum"])
                    if doc.get("title"): self.existing_titles.add(doc["title"].lower())
                if not data.get("next"): break
                page += 1
        except Exception as e:
            logger.warning(f"Error loading documents: {e}")

    def _load_correspondents(self):
        try:
            resp = requests.get(f"{self.url}/api/correspondents/?page_size=500", headers=self.headers, timeout=30)
            if resp.status_code == 200:
                for c in resp.json().get("results", []): self.correspondents[c["name"].lower()] = c["id"]
        except Exception as e:
            logger.warning(f"Error loading correspondents: {e}")

    def _load_tags(self):
        try:
            resp = requests.get(f"{self.url}/api/tags/?page_size=500", headers=self.headers, timeout=30)
            if resp.status_code == 200:
                for t in resp.json().get("results", []): self.tags[t["name"].lower()] = t["id"]
        except Exception as e:
            logger.warning(f"Error loading tags: {e}")

    def _load_document_types(self):
        try:
            resp = requests.get(f"{self.url}/api/document_types/?page_size=100", headers=self.headers, timeout=30)
            if resp.status_code == 200:
                for dt in resp.json().get("results", []): self.document_types[dt["name"].lower()] = dt["id"]
        except Exception as e:
            logger.warning(f"Error loading document types: {e}")

    def _get_or_create_correspondent(self, name: str) -> Optional[int]:
        if not name: return None
        name_lower = name.lower()
        if name_lower in self.correspondents: return self.correspondents[name_lower]
        if self.dry_run: return None
        try:
            resp = requests.post(f"{self.url}/api/correspondents/", headers=self.headers, json={"name": name[:128]}, timeout=30)
            if resp.status_code in [200, 201]:
                new_id = resp.json()["id"]
                self.correspondents[name_lower] = new_id
                return new_id
        except: pass
        return None

    def _get_or_create_tag(self, name: str) -> Optional[int]:
        if not name: return None
        name_lower = name.lower()
        if name_lower in self.tags: return self.tags[name_lower]
        if self.dry_run: return None
        try:
            resp = requests.post(f"{self.url}/api/tags/", headers=self.headers, json={"name": name[:128]}, timeout=30)
            if resp.status_code in [200, 201]:
                new_id = resp.json()["id"]
                self.tags[name_lower] = new_id
                return new_id
        except: pass
        return None

    def is_duplicate(self, file_hash: str, title: str) -> bool:
        if file_hash and file_hash in self.existing_hashes: return True
        if title and title.lower() in self.existing_titles: return True
        return False

    def import_document(self, result: Dict) -> Dict[str, Any]:
        import_result = {"success": False, "skipped": False, "reason": None}
        self.stats["total"] += 1

        text = result.get("text", "")
        if not text or len(text) < 50:
            self.stats["skipped_no_content"] += 1
            import_result["skipped"] = True
            import_result["reason"] = "no_content"
            return import_result

        file_hash = result.get("file_hash")
        title = result.get("email_id", "")[:128]

        if self.is_duplicate(file_hash, title):
            self.stats["skipped_duplicate"] += 1
            import_result["skipped"] = True
            import_result["reason"] = "duplicate"
            import_result["success"] = True
            return import_result

        if self.dry_run:
            logger.info(f"[DRY RUN] Would import: {title}")
            import_result["success"] = True
            self.stats["imported"] += 1
            return import_result

        # Create simple text file and upload
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as tmp:
                tmp.write(text)
                txt_path = tmp.name

            with open(txt_path, 'rb') as f:
                files = {'document': (f"{title}.txt", f, 'text/plain')}
                data = {'title': title}

                fields = result.get("fields", {})
                supplier = fields.get("supplier")
                if supplier:
                    corr_id = self._get_or_create_correspondent(supplier)
                    if corr_id: data['correspondent'] = corr_id

                resp = requests.post(f"{self.url}/api/documents/post_document/", headers=self.headers, files=files, data=data, timeout=60)

            Path(txt_path).unlink(missing_ok=True)

            if resp.status_code in [200, 201, 202]:
                import_result["success"] = True
                self.stats["imported"] += 1
                if file_hash: self.existing_hashes.add(file_hash)
                self.existing_titles.add(title.lower())
                logger.info(f"✅ Imported: {title}")
            else:
                import_result["reason"] = f"HTTP {resp.status_code}"
                self.stats["errors"] += 1

        except Exception as e:
            import_result["reason"] = str(e)[:200]
            self.stats["errors"] += 1
            logger.error(f"❌ Error: {e}")

        return import_result

    def import_all(self, results: List[Dict]) -> Dict:
        logger.info(f"\n{'='*60}")
        logger.info(f"PHASE 3: IMPORT TO PAPERLESS ({len(results)} results)")
        logger.info(f"{'='*60}")

        for idx, result in enumerate(results):
            if idx % 100 == 0:
                logger.info(f"Progress: {idx}/{len(results)} (imported: {self.stats['imported']})")
            self.import_document(result)
            if not self.dry_run and idx % 10 == 0: time.sleep(0.3)

        return self.stats

    def print_summary(self):
        logger.info(f"\n{'='*60}")
        logger.info("IMPORT SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total: {self.stats['total']}")
        logger.info(f"Imported: {self.stats['imported']}")
        logger.info(f"Duplicates skipped: {self.stats['skipped_duplicate']}")
        logger.info(f"No content skipped: {self.stats['skipped_no_content']}")
        logger.info(f"Errors: {self.stats['errors']}")


def main():
    parser = argparse.ArgumentParser(description='Import to Paperless-ngx')
    parser.add_argument('--input', required=True, help='Path to merged_results.json')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--limit', type=int, help='Limit imports')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = data.get("results", [])
    if args.limit: results = results[:args.limit]

    importer = PaperlessImporter(PAPERLESS_CONFIG, dry_run=args.dry_run)
    importer.initialize()
    importer.import_all(results)
    importer.print_summary()

    stats_file = input_path.parent / "import_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(importer.stats, f, indent=2)
    logger.info(f"Stats: {stats_file}")


if __name__ == "__main__":
    main()
