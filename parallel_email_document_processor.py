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
Parallel Email & Document Processor
====================================
Distributed processing of emails (12/2024+) and documents (11/2024+)
across DGX (4 instances) and MacBook (2-4 instances).

Output:
- mail-1224-1205.json (emails with attachments)
- doc-1124-1205.json (documents from local & ACASIS)

Author: Claude Code
Date: 2025-12-05
"""

import os
import sys
import json
import hashlib
import argparse
import subprocess
import mailbox
import email
from pathlib import Path
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Set, Tuple, Optional
from email.header import decode_header
from email.utils import parsedate_to_datetime
import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(processName)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Date filters (timezone-aware for email comparison)
EMAIL_DATE_FROM = datetime(2024, 12, 1, tzinfo=timezone.utc)
DOCUMENT_DATE_FROM = datetime(2024, 11, 1)  # naive for file mtime
DATE_TO = datetime.now(timezone.utc)

# Document types
DOCUMENT_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.txt', '.rtf', '.csv',
    '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'
}


def decode_mime_header(header_value) -> str:
    """Decode MIME encoded header"""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding or 'utf-8', errors='replace')
            else:
                result += part
        return result
    except Exception:
        return str(header_value)


def compute_file_hash(filepath: Path) -> str:
    """Compute MD5 hash of file for deduplication"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return ""


def get_email_date(msg) -> Optional[datetime]:
    """Extract date from email message, ensuring timezone awareness"""
    date_str = msg.get('Date', '')
    if not date_str:
        return None
    try:
        email_date = parsedate_to_datetime(date_str)
        # Make timezone-aware if naive
        if email_date.tzinfo is None:
            email_date = email_date.replace(tzinfo=timezone.utc)
        return email_date
    except Exception:
        return None


def email_in_date_range(email_date: Optional[datetime]) -> bool:
    """Check if email date is within the target range (handles timezone comparison)"""
    if email_date is None:
        return False
    try:
        # Ensure both dates are timezone-aware
        if email_date.tzinfo is None:
            email_date = email_date.replace(tzinfo=timezone.utc)
        return email_date >= EMAIL_DATE_FROM
    except Exception:
        return False


# =============================================================================
# EMAIL PROCESSING
# =============================================================================

def process_email_chunk(args: Tuple[str, int, int, str, int]) -> Dict:
    """Process a chunk of emails from mbox file"""
    mbox_path, start_idx, end_idx, output_dir, instance_id = args

    logger.info(f"Instance {instance_id}: Processing emails {start_idx}-{end_idx}")

    results = {
        'instance_id': instance_id,
        'emails_processed': 0,
        'emails_in_range': 0,
        'attachments_found': 0,
        'emails': []
    }

    try:
        mbox = mailbox.mbox(mbox_path)

        for idx, msg in enumerate(mbox):
            if idx < start_idx:
                continue
            if idx >= end_idx:
                break

            results['emails_processed'] += 1

            # Check date filter (using safe timezone-aware comparison)
            email_date = get_email_date(msg)
            if not email_in_date_range(email_date):
                continue

            results['emails_in_range'] += 1

            # Extract email metadata
            email_record = {
                'idx': idx,
                'date': email_date.isoformat() if email_date else '',
                'from': decode_mime_header(msg.get('From', ''))[:100],
                'to': decode_mime_header(msg.get('To', ''))[:100],
                'subject': decode_mime_header(msg.get('Subject', ''))[:200],
                'attachments': []
            }

            # Extract attachments
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue

                filename = part.get_filename()
                if not filename:
                    continue

                decoded_filename = decode_mime_header(filename)
                ext = Path(decoded_filename).suffix.lower()

                if ext not in DOCUMENT_EXTENSIONS:
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if not payload or len(payload) < 100:
                        continue

                    # Save attachment
                    safe_filename = f"{idx:06d}_{decoded_filename}".replace('/', '_')
                    output_path = Path(output_dir) / f"instance_{instance_id}" / safe_filename
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(output_path, 'wb') as f:
                        f.write(payload)

                    attachment_record = {
                        'original_filename': decoded_filename,
                        'saved_as': str(output_path),
                        'size_bytes': len(payload),
                        'extension': ext,
                        'content_hash': hashlib.md5(payload).hexdigest()
                    }
                    email_record['attachments'].append(attachment_record)
                    results['attachments_found'] += 1

                except Exception as e:
                    logger.warning(f"Error extracting attachment: {e}")

            if email_record['attachments']:
                results['emails'].append(email_record)

            # Progress logging
            if results['emails_processed'] % 1000 == 0:
                logger.info(f"Instance {instance_id}: Processed {results['emails_processed']} emails, "
                           f"{results['emails_in_range']} in date range, "
                           f"{results['attachments_found']} attachments")

    except Exception as e:
        logger.error(f"Instance {instance_id} error: {e}")
        results['error'] = str(e)

    return results


def count_mbox_emails(mbox_path: str) -> int:
    """Count total emails in mbox"""
    count = 0
    mbox = mailbox.mbox(mbox_path)
    for _ in mbox:
        count += 1
    return count


def process_emails_parallel(mbox_path: str, output_dir: str, num_instances: int = 4) -> Dict:
    """Process mbox file in parallel instances"""
    logger.info(f"Counting emails in {mbox_path}...")
    total_emails = count_mbox_emails(mbox_path)
    logger.info(f"Total emails: {total_emails}")

    # Calculate chunks
    chunk_size = total_emails // num_instances
    chunks = []
    for i in range(num_instances):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < num_instances - 1 else total_emails
        chunks.append((mbox_path, start, end, output_dir, i))

    # Process in parallel
    all_results = []
    with ProcessPoolExecutor(max_workers=num_instances) as executor:
        futures = [executor.submit(process_email_chunk, chunk) for chunk in chunks]
        for future in as_completed(futures):
            result = future.result()
            all_results.append(result)
            logger.info(f"Instance {result['instance_id']} completed: "
                       f"{result['emails_in_range']} emails, {result['attachments_found']} attachments")

    # Merge results
    merged = {
        'timestamp': datetime.now().isoformat(),
        'mbox_path': mbox_path,
        'date_filter': f"{EMAIL_DATE_FROM.date()} - {DATE_TO.date()}",
        'total_emails_processed': sum(r['emails_processed'] for r in all_results),
        'total_emails_in_range': sum(r['emails_in_range'] for r in all_results),
        'total_attachments': sum(r['attachments_found'] for r in all_results),
        'emails': []
    }

    for result in sorted(all_results, key=lambda x: x['instance_id']):
        merged['emails'].extend(result['emails'])

    return merged


# =============================================================================
# DOCUMENT PROCESSING
# =============================================================================

def scan_documents_in_folder(args: Tuple[str, int, datetime, datetime]) -> Dict:
    """Scan folder for documents in date range"""
    folder_path, instance_id, date_from, date_to = args

    logger.info(f"Instance {instance_id}: Scanning {folder_path}")

    results = {
        'instance_id': instance_id,
        'folder': folder_path,
        'documents_found': 0,
        'documents_in_range': 0,
        'documents': []
    }

    folder = Path(folder_path)
    if not folder.exists():
        logger.warning(f"Folder not found: {folder_path}")
        return results

    for root, dirs, files in os.walk(folder):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for filename in files:
            if filename.startswith('.'):
                continue

            filepath = Path(root) / filename
            ext = filepath.suffix.lower()

            if ext not in DOCUMENT_EXTENSIONS:
                continue

            results['documents_found'] += 1

            try:
                stat = filepath.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)

                if mtime < date_from or mtime > date_to:
                    continue

                results['documents_in_range'] += 1

                doc_record = {
                    'path': str(filepath),
                    'filename': filename,
                    'extension': ext,
                    'size_bytes': stat.st_size,
                    'modified_date': mtime.isoformat(),
                    'content_hash': compute_file_hash(filepath)
                }
                results['documents'].append(doc_record)

            except Exception as e:
                logger.warning(f"Error processing {filepath}: {e}")

            if results['documents_found'] % 1000 == 0:
                logger.info(f"Instance {instance_id}: Scanned {results['documents_found']} files, "
                           f"{results['documents_in_range']} in date range")

    return results


def process_documents_parallel(folders: List[str], num_instances: int = 4) -> Dict:
    """Process multiple folders in parallel"""

    # Create tasks
    tasks = []
    for i, folder in enumerate(folders):
        tasks.append((folder, i, DOCUMENT_DATE_FROM, DATE_TO))

    # Process in parallel
    all_results = []
    with ProcessPoolExecutor(max_workers=num_instances) as executor:
        futures = [executor.submit(scan_documents_in_folder, task) for task in tasks]
        for future in as_completed(futures):
            result = future.result()
            all_results.append(result)
            logger.info(f"Folder {result['folder']}: {result['documents_in_range']} documents in range")

    # Merge results
    merged = {
        'timestamp': datetime.now().isoformat(),
        'date_filter': f"{DOCUMENT_DATE_FROM.date()} - {DATE_TO.date()}",
        'folders_scanned': folders,
        'total_documents_scanned': sum(r['documents_found'] for r in all_results),
        'total_documents_in_range': sum(r['documents_in_range'] for r in all_results),
        'documents': []
    }

    for result in all_results:
        merged['documents'].extend(result['documents'])

    return merged


# =============================================================================
# DEDUPLICATION & MERGING
# =============================================================================

def deduplicate_by_hash(records: List[Dict], hash_key: str = 'content_hash') -> Tuple[List[Dict], int]:
    """Remove duplicates based on content hash"""
    seen_hashes: Set[str] = set()
    unique_records = []
    duplicates = 0

    for record in records:
        content_hash = record.get(hash_key, '')
        if not content_hash or content_hash in seen_hashes:
            duplicates += 1
            continue
        seen_hashes.add(content_hash)
        unique_records.append(record)

    return unique_records, duplicates


def merge_email_results(result_files: List[str], output_path: str) -> Dict:
    """Merge multiple email result files"""
    merged_emails = []

    for filepath in result_files:
        if not Path(filepath).exists():
            continue
        with open(filepath, 'r') as f:
            data = json.load(f)
            merged_emails.extend(data.get('emails', []))

    # Deduplicate attachments by hash
    all_attachments = []
    for email_rec in merged_emails:
        for att in email_rec.get('attachments', []):
            att['email_subject'] = email_rec.get('subject', '')
            att['email_date'] = email_rec.get('date', '')
            att['email_from'] = email_rec.get('from', '')
            all_attachments.append(att)

    unique_attachments, dup_count = deduplicate_by_hash(all_attachments)

    result = {
        'timestamp': datetime.now().isoformat(),
        'total_emails': len(merged_emails),
        'total_attachments': len(all_attachments),
        'unique_attachments': len(unique_attachments),
        'duplicates_removed': dup_count,
        'attachments': unique_attachments
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"Merged email results saved: {output_path}")
    logger.info(f"  Total attachments: {len(all_attachments)}, Unique: {len(unique_attachments)}, Duplicates: {dup_count}")

    return result


def merge_document_results(result_files: List[str], output_path: str) -> Dict:
    """Merge multiple document result files"""
    all_documents = []

    for filepath in result_files:
        if not Path(filepath).exists():
            continue
        with open(filepath, 'r') as f:
            data = json.load(f)
            all_documents.extend(data.get('documents', []))

    unique_documents, dup_count = deduplicate_by_hash(all_documents)

    result = {
        'timestamp': datetime.now().isoformat(),
        'total_documents': len(all_documents),
        'unique_documents': len(unique_documents),
        'duplicates_removed': dup_count,
        'documents': unique_documents
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"Merged document results saved: {output_path}")
    logger.info(f"  Total documents: {len(all_documents)}, Unique: {len(unique_documents)}, Duplicates: {dup_count}")

    return result


# =============================================================================
# STATISTICS
# =============================================================================

def generate_statistics(email_result_path: str, doc_result_path: str) -> Dict:
    """Generate comprehensive statistics report"""
    stats = {
        'timestamp': datetime.now().isoformat(),
        'emails': {},
        'documents': {}
    }

    # Email statistics
    if Path(email_result_path).exists():
        with open(email_result_path, 'r') as f:
            email_data = json.load(f)

        attachments = email_data.get('attachments', [])
        ext_counts = {}
        for att in attachments:
            ext = att.get('extension', 'unknown')
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        stats['emails'] = {
            'total_attachments': email_data.get('total_attachments', 0),
            'unique_attachments': email_data.get('unique_attachments', 0),
            'duplicates_removed': email_data.get('duplicates_removed', 0),
            'by_extension': dict(sorted(ext_counts.items(), key=lambda x: -x[1]))
        }

    # Document statistics
    if Path(doc_result_path).exists():
        with open(doc_result_path, 'r') as f:
            doc_data = json.load(f)

        documents = doc_data.get('documents', [])
        ext_counts = {}
        folder_counts = {}

        for doc in documents:
            ext = doc.get('extension', 'unknown')
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

            folder = str(Path(doc.get('path', '')).parent)
            folder_counts[folder] = folder_counts.get(folder, 0) + 1

        # Top folders
        top_folders = dict(sorted(folder_counts.items(), key=lambda x: -x[1])[:20])

        stats['documents'] = {
            'total_documents': doc_data.get('total_documents', 0),
            'unique_documents': doc_data.get('unique_documents', 0),
            'duplicates_removed': doc_data.get('duplicates_removed', 0),
            'by_extension': dict(sorted(ext_counts.items(), key=lambda x: -x[1])),
            'top_folders': top_folders
        }

    return stats


def print_statistics(stats: Dict):
    """Print statistics report"""
    print("\n" + "=" * 70)
    print("📊 STATISTICS REPORT")
    print("=" * 70)

    if stats.get('emails'):
        email_stats = stats['emails']
        print("\n📧 EMAIL ATTACHMENTS (12/2024 - today)")
        print(f"  Total attachments: {email_stats.get('total_attachments', 0):,}")
        print(f"  Unique attachments: {email_stats.get('unique_attachments', 0):,}")
        print(f"  Duplicates removed: {email_stats.get('duplicates_removed', 0):,}")
        print("\n  By extension:")
        for ext, count in email_stats.get('by_extension', {}).items():
            print(f"    {ext}: {count:,}")

    if stats.get('documents'):
        doc_stats = stats['documents']
        print("\n📄 DOCUMENTS (11/2024 - today)")
        print(f"  Total documents: {doc_stats.get('total_documents', 0):,}")
        print(f"  Unique documents: {doc_stats.get('unique_documents', 0):,}")
        print(f"  Duplicates removed: {doc_stats.get('duplicates_removed', 0):,}")
        print("\n  By extension:")
        for ext, count in doc_stats.get('by_extension', {}).items():
            print(f"    {ext}: {count:,}")
        print("\n  Top folders:")
        for folder, count in list(doc_stats.get('top_folders', {}).items())[:10]:
            short_folder = folder[-60:] if len(folder) > 60 else folder
            print(f"    {short_folder}: {count:,}")

    print("\n" + "=" * 70)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Parallel Email & Document Processor')
    parser.add_argument('--mode', choices=['emails', 'documents', 'merge', 'stats', 'all'],
                       default='all', help='Processing mode')
    parser.add_argument('--mbox', help='Path to mbox file')
    parser.add_argument('--folders', nargs='+', help='Folders to scan for documents')
    parser.add_argument('--output-dir', default='./parallel_scan_output', help='Output directory')
    parser.add_argument('--instances', type=int, default=4, help='Number of parallel instances')
    parser.add_argument('--merge-files', nargs='+', help='Files to merge')
    parser.add_argument('--output', help='Output file path')

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == 'emails' and args.mbox:
        result = process_emails_parallel(args.mbox, str(output_dir), args.instances)
        output_file = output_dir / 'email_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Email results saved: {output_file}")

    elif args.mode == 'documents' and args.folders:
        result = process_documents_parallel(args.folders, args.instances)
        output_file = output_dir / 'document_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Document results saved: {output_file}")

    elif args.mode == 'merge' and args.merge_files and args.output:
        if 'email' in args.output.lower() or 'mail' in args.output.lower():
            merge_email_results(args.merge_files, args.output)
        else:
            merge_document_results(args.merge_files, args.output)

    elif args.mode == 'stats':
        email_path = output_dir / 'mail-1224-1205.json'
        doc_path = output_dir / 'doc-1124-1205.json'
        stats = generate_statistics(str(email_path), str(doc_path))
        print_statistics(stats)

        stats_file = output_dir / 'statistics_report.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        logger.info(f"Statistics saved: {stats_file}")

    elif args.mode == 'all':
        logger.info("Running complete pipeline...")
        logger.info("Use individual modes for distributed processing:")
        logger.info("  --mode emails --mbox <path> --instances 4")
        logger.info("  --mode documents --folders <paths> --instances 4")
        logger.info("  --mode merge --merge-files <files> --output <path>")
        logger.info("  --mode stats")


if __name__ == "__main__":
    main()
