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
Merge Duplicate Correspondents in Paperless-NGX
===============================================
Identifies and merges duplicate correspondents based on normalized names.
"""

import argparse
import json
import sys
from typing import Dict, List, Optional
import requests

from correspondent_normalizer import (
    normalize_correspondent,
    get_canonical_name,
    find_duplicates,
    get_best_correspondent_name,
)

# Default Paperless configuration
DEFAULT_PAPERLESS_URL = "http://192.168.10.200:8020"
DEFAULT_PAPERLESS_TOKEN = "155c91425631202132bb769241ad7d3196428df0"


class PaperlessMerger:
    def __init__(self, url: str, token: str, dry_run: bool = True):
        self.url = url.rstrip('/')
        self.headers = {"Authorization": f"Token {token}"}
        self.dry_run = dry_run

    def get_correspondents(self) -> List[Dict]:
        """Fetch all correspondents from Paperless"""
        response = requests.get(
            f"{self.url}/api/correspondents/?page_size=5000",
            headers=self.headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json().get('results', [])

    def get_documents_by_correspondent(self, correspondent_id: int) -> List[int]:
        """Get all document IDs for a correspondent"""
        doc_ids = []
        page = 1
        while True:
            response = requests.get(
                f"{self.url}/api/documents/",
                headers=self.headers,
                params={
                    'correspondent__id': correspondent_id,
                    'page': page,
                    'page_size': 100
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            doc_ids.extend([d['id'] for d in data.get('results', [])])
            if not data.get('next'):
                break
            page += 1
        return doc_ids

    def update_document_correspondent(self, doc_id: int, correspondent_id: int) -> bool:
        """Update a document's correspondent"""
        if self.dry_run:
            return True

        response = requests.patch(
            f"{self.url}/api/documents/{doc_id}/",
            headers={**self.headers, 'Content-Type': 'application/json'},
            json={'correspondent': correspondent_id},
            timeout=30
        )
        return response.status_code == 200

    def rename_correspondent(self, correspondent_id: int, new_name: str) -> bool:
        """Rename a correspondent"""
        if self.dry_run:
            return True

        response = requests.patch(
            f"{self.url}/api/correspondents/{correspondent_id}/",
            headers={**self.headers, 'Content-Type': 'application/json'},
            json={'name': new_name},
            timeout=30
        )
        return response.status_code == 200

    def delete_correspondent(self, correspondent_id: int) -> bool:
        """Delete a correspondent (only if no documents)"""
        if self.dry_run:
            return True

        response = requests.delete(
            f"{self.url}/api/correspondents/{correspondent_id}/",
            headers=self.headers,
            timeout=30
        )
        return response.status_code in (200, 204)

    def merge_group(self, group: List[Dict], target_name: Optional[str] = None) -> Dict:
        """
        Merge a group of duplicate correspondents.

        Args:
            group: List of correspondent dicts to merge
            target_name: Optional name to use for merged correspondent

        Returns:
            Dict with merge results
        """
        if len(group) < 2:
            return {'status': 'skip', 'reason': 'Not enough to merge'}

        # Sort by document count (keep the one with most docs)
        sorted_group = sorted(group, key=lambda x: -x['document_count'])
        primary = sorted_group[0]
        to_merge = sorted_group[1:]

        # Determine best name
        if target_name:
            best_name = target_name
        else:
            all_names = [c['name'] for c in group]
            best_name = get_canonical_name(all_names)

        result = {
            'primary_id': primary['id'],
            'primary_name': primary['name'],
            'target_name': best_name,
            'merged': [],
            'documents_moved': 0,
            'errors': []
        }

        # Rename primary if needed
        if primary['name'] != best_name:
            if self.rename_correspondent(primary['id'], best_name):
                result['renamed'] = True
            else:
                result['errors'].append(f"Failed to rename {primary['id']} to {best_name}")

        # Merge others into primary
        for c in to_merge:
            doc_ids = self.get_documents_by_correspondent(c['id'])

            for doc_id in doc_ids:
                if self.update_document_correspondent(doc_id, primary['id']):
                    result['documents_moved'] += 1
                else:
                    result['errors'].append(f"Failed to move doc {doc_id}")

            # Delete the now-empty correspondent
            if self.delete_correspondent(c['id']):
                result['merged'].append({
                    'id': c['id'],
                    'name': c['name'],
                    'docs': len(doc_ids)
                })
            else:
                result['errors'].append(f"Failed to delete correspondent {c['id']}")

        return result


def main():
    parser = argparse.ArgumentParser(
        description='Merge duplicate correspondents in Paperless-NGX'
    )
    parser.add_argument(
        '--url', default=DEFAULT_PAPERLESS_URL,
        help='Paperless URL'
    )
    parser.add_argument(
        '--token', default=DEFAULT_PAPERLESS_TOKEN,
        help='Paperless API token'
    )
    parser.add_argument(
        '--dry-run', action='store_true', default=True,
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--execute', action='store_true',
        help='Actually execute the merge (disables dry-run)'
    )
    parser.add_argument(
        '--min-docs', type=int, default=1,
        help='Minimum total documents in group to process'
    )
    parser.add_argument(
        '--output', '-o', help='Output JSON file for results'
    )

    args = parser.parse_args()

    dry_run = not args.execute
    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("Use --execute to actually merge correspondents")
        print("=" * 60)
        print()

    merger = PaperlessMerger(args.url, args.token, dry_run=dry_run)

    print(f"Fetching correspondents from {args.url}...")
    correspondents = merger.get_correspondents()
    print(f"Found {len(correspondents)} correspondents")

    print("\nFinding duplicates...")
    duplicates = find_duplicates(correspondents)
    print(f"Found {len(duplicates)} duplicate groups")

    # Filter by minimum documents
    filtered = {
        k: v for k, v in duplicates.items()
        if sum(c['document_count'] for c in v) >= args.min_docs
    }
    print(f"Processing {len(filtered)} groups with >= {args.min_docs} documents")

    results = []
    total_merged = 0
    total_docs_moved = 0

    for norm_name, group in sorted(
        filtered.items(),
        key=lambda x: -sum(c['document_count'] for c in x[1])
    ):
        total_docs = sum(c['document_count'] for c in group)
        print(f"\n--- Group: '{norm_name}' ({total_docs} docs, {len(group)} correspondents) ---")

        for c in group:
            print(f"  {c['id']:4}: {c['name']} ({c['document_count']} docs)")

        result = merger.merge_group(group)
        results.append({
            'normalized': norm_name,
            'group': group,
            **result
        })

        if result.get('merged'):
            total_merged += len(result['merged'])
            total_docs_moved += result['documents_moved']
            print(f"  -> Merged {len(result['merged'])} into '{result['target_name']}' (id:{result['primary_id']})")
            print(f"     Moved {result['documents_moved']} documents")

        if result.get('errors'):
            print(f"  ERRORS: {result['errors']}")

    print("\n" + "=" * 60)
    print(f"SUMMARY")
    print(f"  Groups processed: {len(filtered)}")
    print(f"  Correspondents merged: {total_merged}")
    print(f"  Documents moved: {total_docs_moved}")
    print("=" * 60)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump({
                'dry_run': dry_run,
                'groups_processed': len(filtered),
                'correspondents_merged': total_merged,
                'documents_moved': total_docs_moved,
                'results': results
            }, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")


if __name__ == '__main__':
    main()
