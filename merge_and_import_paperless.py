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
Merge Results and Import to Paperless
======================================
Phase 2: Merges all instance results and imports to Paperless-ngx,
skipping documents that already exist.

Author: Claude Code
Date: 2025-12-14
"""

import os
import sys
import json
import requests
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Set
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PaperlessImporter:
    """Import documents to Paperless-ngx"""

    # 28 custom fields mapping
    FIELD_MAPPING = {
        'doc_type': 'doc_typ',
        'ai_description': 'ai_popis',
        'ai_keywords': 'ai_keywords',
        'counterparty_name': 'protistrana_nazev',
        'recipient_name': 'prijemce_nazev',
        'recipient_type': 'prijemce_typ',
        'is_business': 'je_firemni',
        'total_amount': 'castka_celkem',
        'document_date': 'datum_dokumentu',
        'due_date': 'datum_splatnosti',
        'email_from': 'email_from',
        'email_to': 'email_to',
        'email_subject': 'email_subject',
        'email_date': 'email_date',
        'currency': 'mena',
        'invoice_number': 'cislo_faktury',
        'order_number': 'cislo_objednavky',
        'vat_amount': 'castka_dph',
        'vat_rate': 'sazba_dph',
        'payment_method': 'zpusob_platby',
        'iban': 'iban',
        'bank_name': 'nazev_banky',
        'language': 'jazyk',
        'page_count': 'pocet_stran',
        'file_hash': 'file_hash',
        'source_file': 'zdrojovy_soubor',
        'processing_method': 'metoda_zpracovani',
        'confidence_score': 'confidence'
    }

    def __init__(self, paperless_url: str, token: str):
        self.paperless_url = paperless_url.rstrip('/')
        self.headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }
        self.existing_hashes: Set[str] = set()
        self.field_ids: Dict[str, int] = {}

        # Load existing document hashes
        self._load_existing_hashes()
        # Load custom field IDs
        self._load_field_ids()

    def _load_existing_hashes(self):
        """Load hashes of existing documents to skip duplicates"""
        logger.info("Loading existing document hashes...")

        try:
            # Get all documents with file_hash field
            page = 1
            while True:
                response = requests.get(
                    f"{self.paperless_url}/api/documents/",
                    headers=self.headers,
                    params={'page': page, 'page_size': 100}
                )

                if response.status_code != 200:
                    logger.error(f"Failed to load documents: {response.status_code}")
                    break

                data = response.json()
                documents = data.get('results', [])

                if not documents:
                    break

                for doc in documents:
                    # Try to get hash from custom fields
                    custom_fields = doc.get('custom_fields', [])
                    for cf in custom_fields:
                        if cf.get('field') == self.field_ids.get('file_hash'):
                            if cf.get('value'):
                                self.existing_hashes.add(cf['value'])

                    # Also hash by content checksum if available
                    if doc.get('checksum'):
                        self.existing_hashes.add(doc['checksum'])

                if not data.get('next'):
                    break
                page += 1

            logger.info(f"Loaded {len(self.existing_hashes)} existing document hashes")

        except Exception as e:
            logger.error(f"Error loading existing hashes: {e}")

    def _load_field_ids(self):
        """Load custom field IDs from Paperless"""
        logger.info("Loading custom field IDs...")

        try:
            response = requests.get(
                f"{self.paperless_url}/api/custom_fields/",
                headers=self.headers
            )

            if response.status_code == 200:
                fields = response.json().get('results', [])
                for field in fields:
                    self.field_ids[field['name']] = field['id']
                logger.info(f"Loaded {len(self.field_ids)} custom field IDs")
            else:
                logger.error(f"Failed to load fields: {response.status_code}")

        except Exception as e:
            logger.error(f"Error loading field IDs: {e}")

    def is_duplicate(self, file_hash: str) -> bool:
        """Check if document already exists"""
        return file_hash in self.existing_hashes

    def import_document(self, result: Dict[str, Any], pdf_path: str = None) -> bool:
        """Import single document to Paperless"""

        file_hash = result.get('file_hash', '')

        # Skip duplicates
        if file_hash and self.is_duplicate(file_hash):
            logger.info(f"  ⏭️ Skipping duplicate: {result.get('email_subject', 'unknown')[:50]}")
            return False

        try:
            # Prepare custom fields
            custom_fields = []
            fields = result.get('fields', {})

            for our_field, paperless_field in self.FIELD_MAPPING.items():
                if paperless_field in self.field_ids:
                    value = fields.get(our_field) or result.get(our_field)
                    if value is not None:
                        custom_fields.append({
                            'field': self.field_ids[paperless_field],
                            'value': str(value)[:500]  # Truncate long values
                        })

            # If we have a PDF, upload it
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    files = {'document': f}
                    data = {
                        'title': result.get('email_subject', 'Imported Email')[:128],
                        'correspondent': result.get('email_from', '')[:128],
                    }

                    response = requests.post(
                        f"{self.paperless_url}/api/documents/post_document/",
                        headers={'Authorization': self.headers['Authorization']},
                        files=files,
                        data=data
                    )

                    if response.status_code in [200, 201, 202]:
                        logger.info(f"  ✅ Uploaded: {result.get('email_subject', 'unknown')[:50]}")

                        # Add hash to existing
                        if file_hash:
                            self.existing_hashes.add(file_hash)

                        return True
                    else:
                        logger.error(f"  ❌ Upload failed: {response.status_code} - {response.text[:200]}")
                        return False

            # No PDF - create document from text
            else:
                # Create a text file
                text_content = result.get('text', '')
                if not text_content:
                    logger.warning(f"  ⚠️ No content for: {result.get('email_subject', 'unknown')[:50]}")
                    return False

                # Save as temp file and upload
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
                    tf.write(text_content)
                    temp_path = tf.name

                try:
                    with open(temp_path, 'rb') as f:
                        files = {'document': (f"{result.get('email_id', 0)}.txt", f, 'text/plain')}
                        data = {
                            'title': result.get('email_subject', 'Imported Email')[:128],
                        }

                        response = requests.post(
                            f"{self.paperless_url}/api/documents/post_document/",
                            headers={'Authorization': self.headers['Authorization']},
                            files=files,
                            data=data
                        )

                        if response.status_code in [200, 201, 202]:
                            logger.info(f"  ✅ Uploaded text: {result.get('email_subject', 'unknown')[:50]}")
                            if file_hash:
                                self.existing_hashes.add(file_hash)
                            return True
                        else:
                            logger.error(f"  ❌ Upload failed: {response.status_code}")
                            return False
                finally:
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"  ❌ Import error: {e}")
            return False


def merge_results(output_dir: str) -> List[Dict[str, Any]]:
    """Merge all instance result files"""

    output_path = Path(output_dir)
    all_results = []
    stats = {
        'instances_found': 0,
        'total_results': 0,
        'successful': 0,
        'failed': 0,
        'by_type': {}
    }

    logger.info(f"Scanning for results in: {output_dir}")

    # Find all instance directories
    for instance_dir in sorted(output_path.glob("instance_*")):
        if not instance_dir.is_dir():
            continue

        # Find results file
        results_files = list(instance_dir.glob("*_results.json"))
        if not results_files:
            continue

        stats['instances_found'] += 1

        for results_file in results_files:
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                results = data.get('results', [])
                all_results.extend(results)

                for r in results:
                    stats['total_results'] += 1
                    if r.get('success'):
                        stats['successful'] += 1
                        doc_type = r.get('doc_type', 'unknown')
                        stats['by_type'][doc_type] = stats['by_type'].get(doc_type, 0) + 1
                    else:
                        stats['failed'] += 1

                logger.info(f"  ✓ {instance_dir.name}: {len(results)} results")

            except Exception as e:
                logger.error(f"  ✗ {results_file}: {e}")

    logger.info(f"\n📊 Merge Statistics:")
    logger.info(f"  Instances: {stats['instances_found']}")
    logger.info(f"  Total results: {stats['total_results']}")
    logger.info(f"  Successful: {stats['successful']}")
    logger.info(f"  Failed: {stats['failed']}")

    if stats['by_type']:
        logger.info(f"\n  By type:")
        for doc_type, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
            logger.info(f"    {doc_type}: {count}")

    return all_results


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Merge and Import to Paperless')
    parser.add_argument('--output-dir', required=True, help='Directory with instance results')
    parser.add_argument('--paperless-url', default='http://192.168.10.200:8020',
                        help='Paperless URL')
    parser.add_argument('--token', default='ee4da3480b3d80e7d5d8763cdd8c79b529a3a07b',
                        help='Paperless API token')
    parser.add_argument('--dry-run', action='store_true', help='Only merge, don\'t import')
    parser.add_argument('--save-merged', help='Save merged results to file')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(" MERGE AND IMPORT TO PAPERLESS")
    logger.info("=" * 60)

    # Phase 1: Merge results
    logger.info("\n📁 PHASE 1: Merging results from all instances...")
    results = merge_results(args.output_dir)

    if not results:
        logger.error("No results found to import!")
        return

    # Save merged results if requested
    if args.save_merged:
        with open(args.save_merged, 'w', encoding='utf-8') as f:
            json.dump({
                'merge_date': datetime.now().isoformat(),
                'total_results': len(results),
                'results': results
            }, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Merged results saved to: {args.save_merged}")

    if args.dry_run:
        logger.info("\n🔍 Dry run - not importing to Paperless")
        return

    # Phase 2: Import to Paperless
    logger.info(f"\n📤 PHASE 2: Importing to Paperless ({args.paperless_url})...")

    importer = PaperlessImporter(args.paperless_url, args.token)

    imported = 0
    skipped = 0
    failed = 0

    for i, result in enumerate(results, 1):
        if i % 100 == 0:
            logger.info(f"  Progress: {i}/{len(results)} ({imported} imported, {skipped} skipped)")

        if not result.get('success'):
            skipped += 1
            continue

        # Find associated PDF if exists
        pdf_path = None
        if result.get('attachments'):
            for att in result['attachments']:
                if att.lower().endswith('.pdf') and os.path.exists(att):
                    pdf_path = att
                    break

        if importer.import_document(result, pdf_path):
            imported += 1
        elif importer.is_duplicate(result.get('file_hash', '')):
            skipped += 1
        else:
            failed += 1

    logger.info("\n" + "=" * 60)
    logger.info(" IMPORT COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Total processed: {len(results)}")
    logger.info(f"  Imported: {imported}")
    logger.info(f"  Skipped (duplicates/failed): {skipped}")
    logger.info(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
