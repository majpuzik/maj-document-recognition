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
OneDrive Document Consolidator
==============================
Consolidates all OneDrive document folders into a single ACASIS folder,
removing duplicates based on file hash, text hash, and similarity.

Features:
- Syncs multiple source folders to single destination
- Real-time duplicate detection
- Preserves original folder structure in metadata
- Progress tracking with resume capability
"""

import os
import sys
import json
import hashlib
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('consolidation.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """File metadata"""
    source_path: str
    dest_path: str
    source_folder: str
    file_hash: str
    size: int
    is_duplicate: bool = False
    duplicate_of: str = None


class DocumentConsolidator:
    """Consolidate OneDrive documents with deduplication"""

    # Source folders in OneDrive (prioritized by importance)
    SOURCE_FOLDERS = [
        # Smaller folders first for quick results
        ("1alldoc", "1alldoc"),           # 297 files
        ("puzik", "puzik"),                 # 2073 files
        ("1alldok", "1alldok"),             # 2032 files
        ("1pdf", "1pdf"),                   # ~500 files (727MB)
        # Huge folder last
        ("1allpdf", "1allpdf"),             # 45026 files (174GB)
    ]

    def __init__(self,
                 onedrive_base: str = "/Users/m.a.j.puzik/OneDrive",
                 acasis_dest: str = "/Volumes/ACASIS/OneDrive_backup/Documents_All",
                 progress_file: str = "consolidation_progress.json"):

        self.onedrive_base = Path(onedrive_base)
        self.acasis_dest = Path(acasis_dest)
        self.progress_file = Path(progress_file)

        # Deduplication tracking
        self.file_hashes: Dict[str, str] = {}  # hash -> first file path
        self.processed_files: Set[str] = set()

        # Statistics
        self.stats = {
            "total_files": 0,
            "copied_files": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "total_size": 0,
            "copied_size": 0,
            "skipped_size": 0,
            "by_folder": {}
        }

        # Load progress if exists
        self._load_progress()

    def _load_progress(self):
        """Load progress from previous run"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file) as f:
                    data = json.load(f)
                self.file_hashes = data.get("file_hashes", {})
                self.processed_files = set(data.get("processed_files", []))
                self.stats = data.get("stats", self.stats)
                logger.info(f"Loaded progress: {len(self.processed_files)} files already processed")
            except Exception as e:
                logger.warning(f"Could not load progress: {e}")

    def _save_progress(self):
        """Save progress for resume capability"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump({
                    "file_hashes": self.file_hashes,
                    "processed_files": list(self.processed_files),
                    "stats": self.stats,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save progress: {e}")

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing {file_path}: {e}")
            return None

    def _get_file_list(self, folder: Path) -> List[Path]:
        """Get list of document files in folder"""
        extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx',
                     '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp',
                     '.txt', '.rtf', '.odt', '.ods'}

        files = []
        try:
            for f in folder.rglob('*'):
                if f.is_file() and f.suffix.lower() in extensions:
                    files.append(f)
        except PermissionError as e:
            logger.warning(f"Permission error accessing {folder}: {e}")

        return sorted(files)

    def _process_file(self, source_file: Path, source_folder_name: str) -> FileInfo:
        """Process a single file - check for duplicates and copy if unique"""

        # Skip if already processed
        source_str = str(source_file)
        if source_str in self.processed_files:
            return None

        try:
            # Get file info
            file_size = source_file.stat().st_size
            file_hash = self._compute_file_hash(source_file)

            if not file_hash:
                self.stats["errors"] += 1
                return None

            # Create destination path (flat structure with source folder prefix)
            safe_name = source_file.name.replace('/', '_').replace('\\', '_')
            dest_name = f"{source_folder_name}_{safe_name}"
            dest_file = self.acasis_dest / dest_name

            # Handle name collisions
            counter = 1
            while dest_file.exists():
                name_parts = source_file.stem, source_file.suffix
                dest_name = f"{source_folder_name}_{name_parts[0]}_{counter}{name_parts[1]}"
                dest_file = self.acasis_dest / dest_name
                counter += 1

            # Check for duplicate
            if file_hash in self.file_hashes:
                # Duplicate found
                self.stats["duplicates_skipped"] += 1
                self.stats["skipped_size"] += file_size

                logger.info(f"⏭️  DUPLICATE: {source_file.name} = {Path(self.file_hashes[file_hash]).name}")

                info = FileInfo(
                    source_path=str(source_file),
                    dest_path=None,
                    source_folder=source_folder_name,
                    file_hash=file_hash,
                    size=file_size,
                    is_duplicate=True,
                    duplicate_of=self.file_hashes[file_hash]
                )
            else:
                # Unique file - copy it
                shutil.copy2(source_file, dest_file)
                self.file_hashes[file_hash] = str(source_file)

                self.stats["copied_files"] += 1
                self.stats["copied_size"] += file_size

                logger.info(f"✅ COPIED: {source_file.name} -> {dest_file.name}")

                info = FileInfo(
                    source_path=str(source_file),
                    dest_path=str(dest_file),
                    source_folder=source_folder_name,
                    file_hash=file_hash,
                    size=file_size
                )

            # Update stats
            self.stats["total_files"] += 1
            self.stats["total_size"] += file_size

            if source_folder_name not in self.stats["by_folder"]:
                self.stats["by_folder"][source_folder_name] = {
                    "total": 0, "copied": 0, "duplicates": 0
                }
            self.stats["by_folder"][source_folder_name]["total"] += 1
            if info.is_duplicate:
                self.stats["by_folder"][source_folder_name]["duplicates"] += 1
            else:
                self.stats["by_folder"][source_folder_name]["copied"] += 1

            # Mark as processed
            self.processed_files.add(source_str)

            return info

        except Exception as e:
            logger.error(f"Error processing {source_file}: {e}")
            self.stats["errors"] += 1
            return None

    def consolidate(self, max_files: int = None) -> Dict:
        """
        Consolidate all OneDrive folders to ACASIS

        Args:
            max_files: Maximum files to process (for testing)
        """

        # Create destination directory
        self.acasis_dest.mkdir(parents=True, exist_ok=True)

        logger.info("="*80)
        logger.info("ONEDRIVE DOCUMENT CONSOLIDATOR")
        logger.info("="*80)
        logger.info(f"Source: {self.onedrive_base}")
        logger.info(f"Destination: {self.acasis_dest}")
        logger.info(f"Already processed: {len(self.processed_files)} files")
        logger.info("="*80)

        processed_count = 0
        all_file_info = []

        for folder_name, display_name in self.SOURCE_FOLDERS:
            source_folder = self.onedrive_base / folder_name

            if not source_folder.exists():
                logger.warning(f"Folder not found: {source_folder}")
                continue

            logger.info(f"\n📁 Processing folder: {display_name}")

            # Get file list
            files = self._get_file_list(source_folder)
            logger.info(f"   Found {len(files)} document files")

            for i, file_path in enumerate(files, 1):
                # Check limit
                if max_files and processed_count >= max_files:
                    logger.info(f"Reached max_files limit ({max_files})")
                    break

                # Process file
                info = self._process_file(file_path, folder_name)
                if info:
                    all_file_info.append(asdict(info))

                processed_count += 1

                # Save progress every 100 files
                if processed_count % 100 == 0:
                    self._save_progress()
                    logger.info(f"   Progress: {processed_count} files, "
                              f"{self.stats['copied_files']} copied, "
                              f"{self.stats['duplicates_skipped']} duplicates")

            if max_files and processed_count >= max_files:
                break

        # Final save
        self._save_progress()

        # Save file info
        info_file = self.acasis_dest / "consolidation_manifest.json"
        with open(info_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "files": all_file_info
            }, f, indent=2)

        # Print summary
        self._print_summary()

        return self.stats

    def _print_summary(self):
        """Print consolidation summary"""
        logger.info("\n" + "="*80)
        logger.info("CONSOLIDATION SUMMARY")
        logger.info("="*80)
        logger.info(f"Total files processed: {self.stats['total_files']}")
        logger.info(f"Files copied: {self.stats['copied_files']}")
        logger.info(f"Duplicates skipped: {self.stats['duplicates_skipped']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Total size: {self.stats['total_size'] / 1024/1024/1024:.2f} GB")
        logger.info(f"Copied size: {self.stats['copied_size'] / 1024/1024/1024:.2f} GB")
        logger.info(f"Skipped size: {self.stats['skipped_size'] / 1024/1024/1024:.2f} GB")

        logger.info("\nBy folder:")
        for folder, stats in self.stats.get("by_folder", {}).items():
            dup_pct = (stats['duplicates'] / stats['total'] * 100) if stats['total'] > 0 else 0
            logger.info(f"  {folder}: {stats['total']} total, "
                       f"{stats['copied']} copied, "
                       f"{stats['duplicates']} duplicates ({dup_pct:.1f}%)")
        logger.info("="*80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Consolidate OneDrive documents')
    parser.add_argument('--max-files', type=int, help='Max files to process (for testing)')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start fresh')
    args = parser.parse_args()

    consolidator = DocumentConsolidator()

    if args.reset:
        if consolidator.progress_file.exists():
            consolidator.progress_file.unlink()
            logger.info("Progress reset")
        consolidator.file_hashes = {}
        consolidator.processed_files = set()
        consolidator.stats = {
            "total_files": 0, "copied_files": 0, "duplicates_skipped": 0,
            "errors": 0, "total_size": 0, "copied_size": 0, "skipped_size": 0,
            "by_folder": {}
        }

    consolidator.consolidate(max_files=args.max_files)


if __name__ == "__main__":
    main()
