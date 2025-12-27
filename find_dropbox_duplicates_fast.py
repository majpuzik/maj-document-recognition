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
Fast Dropbox Duplicate Finder
=============================
Quick scan to find duplicates between Dropbox and local folders.
Skips large OneDrive folder for speed.
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    path: str
    size: int
    hash: str
    location: str


class FastDuplicateFinder:
    """Fast duplicate finder for Dropbox vs local folders"""

    # Only small folders - skip OneDrive
    LOCATIONS = {
        'dropbox': '/Users/m.a.j.puzik/Dropbox',
        'documents': '/Users/m.a.j.puzik/Documents',
        'downloads': '/Users/m.a.j.puzik/Downloads',
        'desktop': '/Users/m.a.j.puzik/Desktop',
    }

    EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx',
                  '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp',
                  '.txt', '.rtf', '.odt', '.ods', '.zip', '.rar'}

    def __init__(self):
        self.files_by_hash: Dict[str, List[FileRecord]] = {}
        self.dropbox_hashes: Set[str] = set()
        self.stats = {'dropbox': 0, 'local': 0, 'duplicates': 0, 'savings_bytes': 0}

    def _compute_hash(self, file_path: Path) -> str:
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None

    def _scan_folder(self, name: str, path: str) -> List[FileRecord]:
        records = []
        folder = Path(path)
        if not folder.exists():
            return records

        logger.info(f"📂 Scanning {name}: {path}")
        count = 0

        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in files:
                if filename.startswith('.'):
                    continue
                file_path = Path(root) / filename
                if file_path.suffix.lower() not in self.EXTENSIONS:
                    continue
                try:
                    size = file_path.stat().st_size
                    if size < 1024:
                        continue
                    file_hash = self._compute_hash(file_path)
                    if file_hash:
                        records.append(FileRecord(str(file_path), size, file_hash, name))
                        count += 1
                        if count % 1000 == 0:
                            logger.info(f"   {name}: {count} files...")
                except:
                    pass

        logger.info(f"   ✅ {name}: {count} files")
        return records

    def find_duplicates(self):
        """Find files in local folders that also exist in Dropbox"""
        logger.info("=" * 60)
        logger.info("FAST DROPBOX DUPLICATE FINDER")
        logger.info("=" * 60)

        # First scan Dropbox
        dropbox_records = self._scan_folder('dropbox', self.LOCATIONS['dropbox'])
        self.stats['dropbox'] = len(dropbox_records)
        for rec in dropbox_records:
            self.dropbox_hashes.add(rec.hash)
            if rec.hash not in self.files_by_hash:
                self.files_by_hash[rec.hash] = []
            self.files_by_hash[rec.hash].append(rec)

        # Scan local folders
        local_records = []
        for name, path in self.LOCATIONS.items():
            if name == 'dropbox':
                continue
            records = self._scan_folder(name, path)
            local_records.extend(records)
            for rec in records:
                if rec.hash not in self.files_by_hash:
                    self.files_by_hash[rec.hash] = []
                self.files_by_hash[rec.hash].append(rec)

        self.stats['local'] = len(local_records)

        # Find duplicates (local files that exist in Dropbox)
        duplicates_to_delete = []
        for rec in local_records:
            if rec.hash in self.dropbox_hashes:
                dropbox_file = next(r for r in self.files_by_hash[rec.hash] if r.location == 'dropbox')
                duplicates_to_delete.append({
                    'local_path': rec.path,
                    'dropbox_path': dropbox_file.path,
                    'size': rec.size,
                    'location': rec.location
                })
                self.stats['duplicates'] += 1
                self.stats['savings_bytes'] += rec.size

        # Generate report
        savings_mb = self.stats['savings_bytes'] / (1024 * 1024)
        logger.info("\n" + "=" * 60)
        logger.info("RESULTS")
        logger.info("=" * 60)
        logger.info(f"Dropbox files: {self.stats['dropbox']:,}")
        logger.info(f"Local files (Documents/Downloads/Desktop): {self.stats['local']:,}")
        logger.info(f"Duplicates found (safe to delete): {self.stats['duplicates']:,}")
        logger.info(f"Potential space savings: {savings_mb:.1f} MB")

        # Save results
        results = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'duplicates_to_delete': duplicates_to_delete
        }

        with open('dropbox_duplicates_report.json', 'w') as f:
            json.dump(results, f, indent=2)

        # Generate deletion script
        if duplicates_to_delete:
            with open('delete_local_dropbox_duplicates.sh', 'w') as f:
                f.write("#!/bin/bash\n")
                f.write("# Delete local files that exist in Dropbox\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Files to delete: {len(duplicates_to_delete)}\n")
                f.write(f"# Space savings: {savings_mb:.1f} MB\n\n")
                for item in duplicates_to_delete:
                    local = item['local_path'].replace("'", "'\\''")
                    f.write(f"rm '{local}'  # Also in Dropbox\n")
            os.chmod('delete_local_dropbox_duplicates.sh', 0o755)
            logger.info(f"\n📝 Deletion script: delete_local_dropbox_duplicates.sh")

        logger.info(f"📊 Full report: dropbox_duplicates_report.json")
        return results


if __name__ == "__main__":
    finder = FastDuplicateFinder()
    finder.find_duplicates()
