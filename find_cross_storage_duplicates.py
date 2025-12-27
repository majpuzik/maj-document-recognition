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
Cross-Storage Duplicate Finder
==============================
Find duplicate files across Dropbox, Local SSD and ACASIS.
Strategy: Files in Dropbox are "source of truth" - delete duplicates from local/ACASIS.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cross_storage_duplicates.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    """File metadata record"""
    path: str
    size: int
    hash: str
    location: str  # 'dropbox', 'local', 'acasis'


class CrossStorageDuplicateFinder:
    """Find duplicates across multiple storage locations"""

    # Storage locations
    LOCATIONS = {
        'dropbox': '/Users/m.a.j.puzik/Dropbox',
        'local_documents': '/Users/m.a.j.puzik/Documents',
        'local_downloads': '/Users/m.a.j.puzik/Downloads',
        'local_desktop': '/Users/m.a.j.puzik/Desktop',
        'onedrive_local': '/Users/m.a.j.puzik/OneDrive',
        'acasis_onedrive': '/Volumes/ACASIS/OneDrive_backup',
    }

    # File extensions to check
    EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx',
                  '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp',
                  '.txt', '.rtf', '.odt', '.ods', '.zip', '.rar'}

    def __init__(self, output_dir: str = '.'):
        self.output_dir = Path(output_dir)
        self.files_by_hash: Dict[str, List[FileRecord]] = {}
        self.stats = {
            'total_files': 0,
            'unique_files': 0,
            'duplicates': 0,
            'potential_savings_bytes': 0,
            'by_location': {}
        }

    def _compute_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.debug(f"Error hashing {file_path}: {e}")
            return None

    def _scan_location(self, location_name: str, location_path: str) -> List[FileRecord]:
        """Scan a storage location for files"""
        records = []
        path = Path(location_path)

        if not path.exists():
            logger.warning(f"Location not found: {location_path}")
            return records

        logger.info(f"📂 Scanning {location_name}: {location_path}")

        file_count = 0
        for root, dirs, files in os.walk(path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for filename in files:
                if filename.startswith('.'):
                    continue

                file_path = Path(root) / filename
                suffix = file_path.suffix.lower()

                if suffix not in self.EXTENSIONS:
                    continue

                try:
                    file_size = file_path.stat().st_size

                    # Skip very small files (likely not important)
                    if file_size < 1024:  # 1KB minimum
                        continue

                    file_hash = self._compute_hash(file_path)
                    if file_hash:
                        records.append(FileRecord(
                            path=str(file_path),
                            size=file_size,
                            hash=file_hash,
                            location=location_name
                        ))
                        file_count += 1

                        if file_count % 1000 == 0:
                            logger.info(f"   {location_name}: {file_count} files scanned...")

                except Exception as e:
                    logger.debug(f"Error processing {file_path}: {e}")

        logger.info(f"   ✅ {location_name}: {file_count} files found")
        return records

    def scan_all_locations(self) -> Dict:
        """Scan all storage locations"""
        logger.info("=" * 80)
        logger.info("CROSS-STORAGE DUPLICATE FINDER")
        logger.info("=" * 80)
        logger.info(f"Timestamp: {datetime.now().isoformat()}")

        all_records = []

        for location_name, location_path in self.LOCATIONS.items():
            records = self._scan_location(location_name, location_path)
            all_records.extend(records)
            self.stats['by_location'][location_name] = len(records)

        self.stats['total_files'] = len(all_records)
        logger.info(f"\n📊 Total files scanned: {len(all_records)}")

        # Group by hash
        for record in all_records:
            if record.hash not in self.files_by_hash:
                self.files_by_hash[record.hash] = []
            self.files_by_hash[record.hash].append(record)

        return self.stats

    def find_duplicates(self) -> Dict:
        """Find duplicate files across locations"""
        logger.info("\n" + "=" * 80)
        logger.info("ANALYZING DUPLICATES")
        logger.info("=" * 80)

        duplicates = {
            'dropbox_has_local_copy': [],      # Files in Dropbox that exist locally -> delete local
            'dropbox_has_acasis_copy': [],     # Files in Dropbox that exist on ACASIS -> delete ACASIS
            'local_only': [],                   # Files only on local -> move to ACASIS
            'acasis_only': [],                  # Files only on ACASIS -> keep
            'multiple_copies': []               # Files with 3+ copies
        }

        for file_hash, records in self.files_by_hash.items():
            if len(records) == 1:
                self.stats['unique_files'] += 1
                continue

            self.stats['duplicates'] += len(records) - 1

            # Analyze locations
            locations = {r.location for r in records}
            dropbox_records = [r for r in records if r.location == 'dropbox']
            local_records = [r for r in records if r.location.startswith('local') or r.location == 'onedrive_local']
            acasis_records = [r for r in records if r.location.startswith('acasis')]

            if len(records) >= 3:
                duplicates['multiple_copies'].append({
                    'hash': file_hash,
                    'size': records[0].size,
                    'copies': [asdict(r) for r in records]
                })

            # If in Dropbox and also locally -> mark local for deletion
            if dropbox_records and local_records:
                for local_rec in local_records:
                    duplicates['dropbox_has_local_copy'].append({
                        'dropbox_path': dropbox_records[0].path,
                        'local_path': local_rec.path,
                        'size': local_rec.size
                    })
                    self.stats['potential_savings_bytes'] += local_rec.size

            # If in Dropbox and also on ACASIS -> mark ACASIS for deletion
            if dropbox_records and acasis_records:
                for acasis_rec in acasis_records:
                    duplicates['dropbox_has_acasis_copy'].append({
                        'dropbox_path': dropbox_records[0].path,
                        'acasis_path': acasis_rec.path,
                        'size': acasis_rec.size
                    })
                    self.stats['potential_savings_bytes'] += acasis_rec.size

        # Calculate savings
        savings_gb = self.stats['potential_savings_bytes'] / (1024**3)
        logger.info(f"\n📊 DUPLICATE ANALYSIS RESULTS:")
        logger.info(f"   Total unique files: {self.stats['unique_files']}")
        logger.info(f"   Total duplicate copies: {self.stats['duplicates']}")
        logger.info(f"   Files in Dropbox with local copy: {len(duplicates['dropbox_has_local_copy'])}")
        logger.info(f"   Files in Dropbox with ACASIS copy: {len(duplicates['dropbox_has_acasis_copy'])}")
        logger.info(f"   Potential space savings: {savings_gb:.2f} GB")

        return duplicates

    def generate_cleanup_script(self, duplicates: Dict) -> str:
        """Generate shell script to clean up duplicates"""
        script_path = self.output_dir / 'cleanup_duplicates.sh'

        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Cross-Storage Duplicate Cleanup Script\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("# WARNING: Review before executing!\n\n")

            f.write("# ============================================\n")
            f.write("# DELETE LOCAL COPIES (Dropbox is source)\n")
            f.write("# ============================================\n\n")

            for item in duplicates['dropbox_has_local_copy'][:100]:  # First 100
                local_path = item['local_path'].replace("'", "'\\''")
                f.write(f"rm '{local_path}'  # Exists in Dropbox: {Path(item['dropbox_path']).name}\n")

            if len(duplicates['dropbox_has_local_copy']) > 100:
                f.write(f"\n# ... and {len(duplicates['dropbox_has_local_copy']) - 100} more local files\n")

            f.write("\n\n# ============================================\n")
            f.write("# DELETE ACASIS COPIES (Dropbox is source)\n")
            f.write("# ============================================\n\n")

            for item in duplicates['dropbox_has_acasis_copy'][:100]:  # First 100
                acasis_path = item['acasis_path'].replace("'", "'\\''")
                f.write(f"rm '{acasis_path}'  # Exists in Dropbox: {Path(item['dropbox_path']).name}\n")

            if len(duplicates['dropbox_has_acasis_copy']) > 100:
                f.write(f"\n# ... and {len(duplicates['dropbox_has_acasis_copy']) - 100} more ACASIS files\n")

        os.chmod(script_path, 0o755)
        logger.info(f"\n📝 Cleanup script generated: {script_path}")
        return str(script_path)

    def save_report(self, duplicates: Dict) -> str:
        """Save full report as JSON"""
        report_path = self.output_dir / 'duplicate_report.json'

        report = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'duplicates': duplicates,
            'locations': self.LOCATIONS
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"📊 Full report saved: {report_path}")
        return str(report_path)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Find cross-storage duplicates')
    parser.add_argument('--output', default='.', help='Output directory')
    parser.add_argument('--generate-script', action='store_true', help='Generate cleanup script')
    args = parser.parse_args()

    finder = CrossStorageDuplicateFinder(output_dir=args.output)

    # Scan all locations
    finder.scan_all_locations()

    # Find duplicates
    duplicates = finder.find_duplicates()

    # Save report
    finder.save_report(duplicates)

    # Generate cleanup script if requested
    if args.generate_script:
        finder.generate_cleanup_script(duplicates)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files scanned: {finder.stats['total_files']:,}")
    print(f"Unique files: {finder.stats['unique_files']:,}")
    print(f"Duplicate copies: {finder.stats['duplicates']:,}")
    print(f"Potential savings: {finder.stats['potential_savings_bytes'] / (1024**3):.2f} GB")
    print("\nFiles to delete (safe - exist in Dropbox):")
    print(f"  - Local copies: {len(duplicates['dropbox_has_local_copy']):,}")
    print(f"  - ACASIS copies: {len(duplicates['dropbox_has_acasis_copy']):,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
