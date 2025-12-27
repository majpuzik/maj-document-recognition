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
Universal Attachment Extractor - Paperless-NGX Style
====================================================
Extracts ALL document types from email attachments (not just PDF):
- PDF documents
- Word documents (.doc, .docx)
- Excel spreadsheets (.xls, .xlsx)
- PowerPoint presentations (.ppt, .pptx)
- Images (.jpg, .png, .tiff, .bmp) - with OCR capability
- Text files (.txt, .rtf, .odt)
- Archives (.zip, .rar) - for later processing

This is a supplementary scanner to run after the PDF scan.

Author: Claude Code
Date: 2025-12-05
"""

import sys
import json
import mailbox
import email
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any, Set
from email.header import decode_header
import mimetypes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Paperless-NGX style supported formats
SUPPORTED_DOCUMENTS = {
    # PDF
    'application/pdf': '.pdf',

    # Word Documents
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.ms-word': '.doc',

    # Excel Spreadsheets
    'application/vnd.ms-excel': '.xls',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/excel': '.xls',

    # PowerPoint
    'application/vnd.ms-powerpoint': '.ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',

    # OpenDocument formats
    'application/vnd.oasis.opendocument.text': '.odt',
    'application/vnd.oasis.opendocument.spreadsheet': '.ods',
    'application/vnd.oasis.opendocument.presentation': '.odp',

    # Text
    'text/plain': '.txt',
    'text/rtf': '.rtf',
    'application/rtf': '.rtf',
    'text/csv': '.csv',

    # Images (OCR capable)
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/tiff': '.tiff',
    'image/bmp': '.bmp',
    'image/gif': '.gif',

    # Archives (for later processing)
    'application/zip': '.zip',
    'application/x-rar-compressed': '.rar',
    'application/x-7z-compressed': '.7z',

    # Fallback for octet-stream (detect by filename)
    'application/octet-stream': None,  # Will use filename extension
}

# Extensions to look for in filename (for octet-stream detection)
DOCUMENT_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.txt', '.rtf', '.csv',
    '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif',
    '.zip', '.rar', '.7z'
}


def decode_mime_header(header_value):
    """Decode MIME encoded header (e.g., =?UTF-8?Q?...?=)"""
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


class UniversalAttachmentExtractor:
    """Extract all document types from emails"""

    def __init__(self, mbox_path: str, output_dir: str,
                 start_email: int = 0, end_email: int = None,
                 skip_pdfs: bool = True):
        """
        Args:
            mbox_path: Path to mbox file
            output_dir: Directory to save extracted files
            start_email: Start index
            end_email: End index (None for all)
            skip_pdfs: Skip PDFs (already extracted by main scanner)
        """
        self.mbox_path = Path(mbox_path)
        self.output_dir = Path(output_dir)
        self.start_email = start_email
        self.end_email = end_email
        self.skip_pdfs = skip_pdfs

        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Statistics
        self.stats = {
            'total_emails': 0,
            'emails_with_attachments': 0,
            'attachments_extracted': 0,
            'by_type': {},
            'skipped_pdfs': 0,
            'errors': []
        }

        # Track extracted files
        self.extracted_files = []

    def get_safe_filename(self, filename: str, email_idx: int, part_idx: int) -> str:
        """Create safe filename from potentially encoded MIME filename"""
        decoded = decode_mime_header(filename)

        # Remove path components
        decoded = Path(decoded).name if decoded else f"attachment_{email_idx}_{part_idx}"

        # Replace problematic characters
        safe = "".join(c if c.isalnum() or c in '.-_' else '_' for c in decoded)

        # Ensure unique filename
        return f"{email_idx:06d}_{safe}"

    def detect_document_type(self, part) -> Tuple[str, str]:
        """
        Detect document type from MIME part

        Returns:
            (mime_type, extension) or (None, None) if not a document
        """
        content_type = part.get_content_type()
        filename = part.get_filename()

        # Direct MIME type match
        if content_type in SUPPORTED_DOCUMENTS and content_type != 'application/octet-stream':
            ext = SUPPORTED_DOCUMENTS[content_type]
            return content_type, ext

        # For octet-stream, check filename extension
        if content_type == 'application/octet-stream' and filename:
            decoded_filename = decode_mime_header(filename)
            ext = Path(decoded_filename).suffix.lower()
            if ext in DOCUMENT_EXTENSIONS:
                # Guess MIME type from extension
                guessed_type, _ = mimetypes.guess_type(decoded_filename)
                return guessed_type or 'application/octet-stream', ext

        # Check filename extension as fallback
        if filename:
            decoded_filename = decode_mime_header(filename)
            ext = Path(decoded_filename).suffix.lower()
            if ext in DOCUMENT_EXTENSIONS:
                guessed_type, _ = mimetypes.guess_type(decoded_filename)
                return guessed_type or 'unknown', ext

        return None, None

    def extract_from_email(self, msg, email_idx: int) -> List[Dict]:
        """Extract all document attachments from email"""
        extracted = []

        email_date = msg.get('Date', '')
        email_from = decode_mime_header(msg.get('From', ''))
        email_subject = decode_mime_header(msg.get('Subject', 'No Subject'))

        part_idx = 0
        for part in msg.walk():
            # Skip multipart containers
            if part.get_content_maintype() == 'multipart':
                continue

            # Detect document type
            mime_type, ext = self.detect_document_type(part)

            if not mime_type:
                continue

            # Skip PDFs if requested
            if self.skip_pdfs and ext == '.pdf':
                self.stats['skipped_pdfs'] += 1
                continue

            # Get payload
            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                # Skip very small files (likely not documents)
                if len(payload) < 100:
                    continue

                # Generate filename
                original_filename = part.get_filename() or f"attachment{ext}"
                safe_filename = self.get_safe_filename(original_filename, email_idx, part_idx)

                # Ensure extension
                if not safe_filename.lower().endswith(ext):
                    safe_filename += ext

                # Save file
                output_path = self.output_dir / safe_filename
                with open(output_path, 'wb') as f:
                    f.write(payload)

                # Record extraction
                record = {
                    'email_idx': email_idx,
                    'email_date': email_date,
                    'email_from': email_from[:100],  # Truncate
                    'email_subject': email_subject[:200],
                    'original_filename': decode_mime_header(original_filename),
                    'saved_as': str(output_path),
                    'mime_type': mime_type,
                    'extension': ext,
                    'size_bytes': len(payload)
                }
                extracted.append(record)
                self.extracted_files.append(record)

                # Update stats
                self.stats['attachments_extracted'] += 1
                type_key = ext.lstrip('.')
                self.stats['by_type'][type_key] = self.stats['by_type'].get(type_key, 0) + 1

                part_idx += 1

            except Exception as e:
                self.stats['errors'].append(f"Email {email_idx}: {str(e)}")

        return extracted

    def scan_mbox(self):
        """Scan mbox and extract all documents"""
        logger.info("=" * 70)
        logger.info("UNIVERSAL ATTACHMENT EXTRACTOR - Paperless-NGX Style")
        logger.info("=" * 70)
        logger.info(f"Mbox: {self.mbox_path}")
        logger.info(f"Output: {self.output_dir}")
        logger.info(f"Range: {self.start_email} - {self.end_email or 'END'}")
        logger.info(f"Skip PDFs: {self.skip_pdfs}")
        logger.info("")

        mbox = mailbox.mbox(str(self.mbox_path))

        for idx, msg in enumerate(mbox):
            # Skip before range
            if idx < self.start_email:
                continue

            # Stop at end
            if self.end_email and idx >= self.end_email:
                break

            self.stats['total_emails'] += 1

            # Progress
            if self.stats['total_emails'] % 1000 == 0:
                logger.info(f"Progress: {self.stats['total_emails']} emails, "
                           f"{self.stats['attachments_extracted']} attachments extracted")

            # Extract attachments
            extracted = self.extract_from_email(msg, idx)
            if extracted:
                self.stats['emails_with_attachments'] += 1

        # Final report
        self._print_report()

        # Save results
        self._save_results()

    def _print_report(self):
        """Print extraction report"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("EXTRACTION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total emails scanned: {self.stats['total_emails']:,}")
        logger.info(f"Emails with attachments: {self.stats['emails_with_attachments']:,}")
        logger.info(f"Total attachments extracted: {self.stats['attachments_extracted']:,}")

        if self.skip_pdfs:
            logger.info(f"PDFs skipped (already processed): {self.stats['skipped_pdfs']:,}")

        logger.info("")
        logger.info("By type:")
        for ext, count in sorted(self.stats['by_type'].items(), key=lambda x: -x[1]):
            logger.info(f"  .{ext}: {count:,}")

        if self.stats['errors']:
            logger.info(f"\nErrors: {len(self.stats['errors'])}")

    def _save_results(self):
        """Save extraction results to JSON"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'mbox_path': str(self.mbox_path),
            'output_dir': str(self.output_dir),
            'stats': self.stats,
            'extracted_files': self.extracted_files
        }

        output_path = self.output_dir / 'extraction_results.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"\nResults saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract all document types from email attachments'
    )
    parser.add_argument('--mbox', required=True, help='Path to mbox file')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--start', type=int, default=0, help='Start email index')
    parser.add_argument('--end', type=int, default=None, help='End email index')
    parser.add_argument('--include-pdfs', action='store_true',
                       help='Include PDFs (by default skipped)')

    args = parser.parse_args()

    extractor = UniversalAttachmentExtractor(
        mbox_path=args.mbox,
        output_dir=args.output,
        start_email=args.start,
        end_email=args.end,
        skip_pdfs=not args.include_pdfs
    )

    extractor.scan_mbox()


if __name__ == "__main__":
    main()
