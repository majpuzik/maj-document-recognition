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
Thunderbird Email Extractor with Docling
=========================================
Extracts emails from Thunderbird mbox, converts to PDF+OCR using docling,
classifies with 32B AI model, and prepares for Paperless import.

Features:
- Docling for primary PDF+OCR conversion (emails + attachments)
- Fallback to original CascadeTextExtractor if docling fails
- 32B AI model (qwen2.5:32b) for classification
- Distributed processing support (instance-based partitioning)
- Detailed failure logging for analysis

Author: Claude Code
Date: 2025-12-14
"""

import sys
import os
import json
import mailbox
import email
import tempfile
import logging
import argparse
import psutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

# Add src paths
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ai'))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Instance %(instance_id)s] - %(levelname)s - %(message)s'
)


class DoclingProcessor:
    """Docling-based document processor with fallback"""

    def __init__(self, logger):
        self.logger = logger
        self.docling_available = self._check_docling()

        # Initialize fallback extractor
        try:
            from text_extractor_cascade import CascadeTextExtractor
            config = {"ocr": {"cascade_threshold": 60.0, "min_text_length": 50}}
            self.fallback_extractor = CascadeTextExtractor(config)
            self.fallback_available = True
        except ImportError:
            self.fallback_extractor = None
            self.fallback_available = False
            self.logger.warning("⚠️ Fallback OCR not available")

    def _check_docling(self) -> bool:
        """Check if docling is available"""
        try:
            result = subprocess.run(
                ['docling', '--version'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.logger.info(f"✅ Docling available: {result.stdout.strip()}")
                return True
        except Exception as e:
            self.logger.warning(f"⚠️ Docling not available: {e}")
        return False

    def process_with_docling(self, input_path: str, output_dir: str) -> Dict[str, Any]:
        """Process document with docling"""
        result = {
            'success': False,
            'method': 'docling',
            'text': '',
            'pages': 0,
            'error': None
        }

        if not self.docling_available:
            result['error'] = 'Docling not available'
            return result

        try:
            # Run docling to convert to markdown (includes OCR)
            cmd = [
                'docling',
                '--input', input_path,
                '--output', output_dir,
                '--format', 'md',
                '--ocr'
            ]

            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )

            if proc.returncode != 0:
                result['error'] = f"Docling failed: {proc.stderr}"
                return result

            # Find output file
            output_files = list(Path(output_dir).glob('*.md'))
            if output_files:
                text = output_files[0].read_text(encoding='utf-8')
                result['text'] = text
                result['pages'] = text.count('\n---\n') + 1  # Estimate pages
                result['success'] = True
            else:
                result['error'] = 'No output file generated'

        except subprocess.TimeoutExpired:
            result['error'] = 'Docling timeout (>300s)'
        except Exception as e:
            result['error'] = str(e)

        return result

    def process_with_fallback(self, pdf_path: str) -> Dict[str, Any]:
        """Process PDF with fallback OCR"""
        result = {
            'success': False,
            'method': 'fallback_ocr',
            'text': '',
            'pages': 0,
            'error': None
        }

        if not self.fallback_available:
            result['error'] = 'Fallback OCR not available'
            return result

        try:
            extraction = self.fallback_extractor.extract_from_pdf(pdf_path)
            text = extraction.get('text', '')

            if text and len(text) >= 50:
                result['text'] = text
                result['pages'] = extraction.get('pages', 1)
                result['success'] = True
                result['confidence'] = extraction.get('confidence', 0)
            else:
                result['error'] = f'Insufficient text: {len(text)} chars'

        except Exception as e:
            result['error'] = str(e)

        return result


class ThunderbirdDoclingExtractor:
    """Main extractor class for Thunderbird emails with docling"""

    # 28 Paperless custom fields
    PAPERLESS_FIELDS = [
        'doc_type', 'ai_description', 'ai_keywords', 'counterparty_name',
        'recipient_name', 'recipient_type', 'is_business', 'total_amount',
        'document_date', 'due_date', 'email_from', 'email_to', 'email_subject',
        'email_date', 'currency', 'invoice_number', 'order_number',
        'vat_amount', 'vat_rate', 'payment_method', 'iban', 'bank_name',
        'language', 'page_count', 'file_hash', 'source_file',
        'processing_method', 'confidence_score'
    ]

    def __init__(self, mbox_path: str, output_dir: str,
                 start_email: int = 0, end_email: int = None,
                 instance_id: int = 0, ollama_url: str = "http://localhost:11434"):

        self.mbox_path = Path(mbox_path)
        self.output_dir = Path(output_dir)
        self.start_email = start_email
        self.end_email = end_email
        self.instance_id = instance_id
        self.ollama_url = ollama_url

        # Create directories
        self.instance_dir = self.output_dir / f"instance_{instance_id}"
        self.instance_dir.mkdir(parents=True, exist_ok=True)

        self.pdf_dir = self.instance_dir / "pdfs"
        self.pdf_dir.mkdir(exist_ok=True)

        self.temp_dir = self.instance_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)

        # Logger
        self.logger = logging.LoggerAdapter(
            logging.getLogger(__name__),
            {'instance_id': instance_id}
        )

        # Initialize processors
        self.docling = DoclingProcessor(self.logger)

        # Statistics
        self.stats = {
            'instance_id': instance_id,
            'start_email': start_email,
            'end_email': end_email,
            'total_emails': 0,
            'emails_processed': 0,
            'docling_success': 0,
            'docling_failed': 0,
            'fallback_success': 0,
            'fallback_failed': 0,
            'ai_classified': 0,
            'ai_failed': 0,
            'by_type': {},
            'errors': []
        }

        # Results
        self.results = []

        self.logger.info(f"🚀 Thunderbird Docling Extractor Instance {instance_id}")
        self.logger.info(f"   Email range: {start_email} - {end_email or 'END'}")
        self.logger.info(f"   Output: {self.instance_dir}")
        self.logger.info(f"   Ollama: {ollama_url}")

    def _get_resource_usage(self) -> Dict[str, float]:
        """Get current CPU and RAM usage"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'ram_percent': psutil.virtual_memory().percent,
            'ram_available_gb': psutil.virtual_memory().available / (1024**3)
        }

    def _check_resource_limit(self, max_percent: float = 85.0) -> bool:
        """Check if we're within resource limits"""
        usage = self._get_resource_usage()
        return usage['cpu_percent'] < max_percent and usage['ram_percent'] < max_percent

    def _email_to_html(self, msg: email.message.EmailMessage) -> str:
        """Convert email message to HTML for docling processing"""
        html_parts = []

        # Header
        html_parts.append("<html><head><meta charset='utf-8'></head><body>")
        html_parts.append("<div class='email-header'>")
        html_parts.append(f"<p><strong>From:</strong> {msg.get('From', 'Unknown')}</p>")
        html_parts.append(f"<p><strong>To:</strong> {msg.get('To', 'Unknown')}</p>")
        html_parts.append(f"<p><strong>Subject:</strong> {msg.get('Subject', 'No Subject')}</p>")
        html_parts.append(f"<p><strong>Date:</strong> {msg.get('Date', 'Unknown')}</p>")
        html_parts.append("</div><hr>")

        # Body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/html':
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='replace')
                        break
                elif content_type == 'text/plain' and not body:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = f"<pre>{payload.decode('utf-8', errors='replace')}</pre>"
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                if msg.get_content_type() == 'text/html':
                    body = payload.decode('utf-8', errors='replace')
                else:
                    body = f"<pre>{payload.decode('utf-8', errors='replace')}</pre>"

        html_parts.append(f"<div class='email-body'>{body}</div>")
        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    def _extract_attachments(self, msg: email.message.EmailMessage, email_id: int) -> List[Path]:
        """Extract all attachments from email"""
        attachments = []

        if not msg.is_multipart():
            return attachments

        for i, part in enumerate(msg.walk()):
            content_type = part.get_content_type()
            filename = part.get_filename()

            # Skip main email parts
            if content_type in ['text/plain', 'text/html', 'multipart/alternative', 'multipart/mixed']:
                continue

            if filename or content_type.startswith('application/'):
                if not filename:
                    ext = content_type.split('/')[-1]
                    filename = f"attachment_{i}.{ext}"

                # Save attachment
                safe_name = f"{email_id:06d}_{i:02d}_{filename}"
                safe_name = "".join(c if c.isalnum() or c in '._-' else '_' for c in safe_name)

                attachment_path = self.pdf_dir / safe_name

                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        with open(attachment_path, 'wb') as f:
                            f.write(payload)
                        attachments.append(attachment_path)
                except Exception as e:
                    self.logger.error(f"   Failed to extract attachment {filename}: {e}")

        return attachments

    def _classify_with_ai(self, text: str) -> Dict[str, Any]:
        """Classify document using 32B AI model"""
        import requests

        result = {
            'success': False,
            'doc_type': 'unknown',
            'confidence': 0,
            'fields': {},
            'error': None
        }

        # Prompt for classification
        prompt = f"""Analyze this document and extract metadata in JSON format.

Document text:
{text[:8000]}

Return ONLY valid JSON with these fields:
{{
  "doc_type": "invoice|receipt|contract|email|newsletter|notification|statement|report|other",
  "confidence": 0-100,
  "counterparty_name": "company/person name or null",
  "total_amount": "amount with currency or null",
  "document_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "invoice_number": "number or null",
  "currency": "EUR|CZK|USD or null",
  "language": "cs|en|de|other",
  "ai_description": "brief description in 1-2 sentences",
  "ai_keywords": "comma-separated keywords"
}}"""

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "qwen2.5:32b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=120
            )

            if response.status_code == 200:
                resp_text = response.json().get('response', '')

                # Extract JSON from response
                import re
                json_match = re.search(r'\{[^{}]*\}', resp_text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    result['doc_type'] = parsed.get('doc_type', 'unknown')
                    result['confidence'] = parsed.get('confidence', 0)
                    result['fields'] = parsed
                    result['success'] = True
            else:
                result['error'] = f"Ollama error: {response.status_code}"

        except Exception as e:
            result['error'] = str(e)

        return result

    def process_email(self, email_id: int, msg: email.message.EmailMessage) -> Dict[str, Any]:
        """Process single email with docling + AI"""

        result = {
            'email_id': email_id,
            'instance_id': self.instance_id,
            'email_from': msg.get('From', ''),
            'email_to': msg.get('To', ''),
            'email_subject': msg.get('Subject', ''),
            'email_date': msg.get('Date', ''),
            'success': False,
            'processing_method': None,
            'doc_type': None,
            'confidence': 0,
            'fields': {},
            'attachments': [],
            'errors': []
        }

        # Step 1: Convert email to HTML and save
        try:
            html_content = self._email_to_html(msg)
            html_path = self.temp_dir / f"email_{email_id:06d}.html"
            html_path.write_text(html_content, encoding='utf-8')
        except Exception as e:
            result['errors'].append(f"HTML conversion failed: {e}")
            self.stats['errors'].append({'email_id': email_id, 'stage': 'html', 'error': str(e)})
            return result

        # Step 2: Process with docling
        docling_output = self.temp_dir / f"docling_{email_id:06d}"
        docling_output.mkdir(exist_ok=True)

        docling_result = self.docling.process_with_docling(str(html_path), str(docling_output))

        if docling_result['success']:
            result['processing_method'] = 'docling'
            result['text'] = docling_result['text']
            self.stats['docling_success'] += 1
        else:
            # Log docling failure
            self.stats['docling_failed'] += 1
            result['errors'].append(f"Docling failed: {docling_result['error']}")
            self.stats['errors'].append({
                'email_id': email_id,
                'stage': 'docling',
                'error': docling_result['error']
            })

            # Try fallback - convert HTML to text directly
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                text = soup.get_text(separator='\n', strip=True)

                if len(text) >= 50:
                    result['processing_method'] = 'fallback_html'
                    result['text'] = text
                    self.stats['fallback_success'] += 1
                else:
                    self.stats['fallback_failed'] += 1
                    result['errors'].append('Fallback: insufficient text')
                    self.stats['errors'].append({
                        'email_id': email_id,
                        'stage': 'fallback',
                        'error': 'Insufficient text'
                    })
            except Exception as e:
                self.stats['fallback_failed'] += 1
                result['errors'].append(f"Fallback failed: {e}")
                self.stats['errors'].append({
                    'email_id': email_id,
                    'stage': 'fallback',
                    'error': str(e)
                })

        # Step 3: Extract attachments
        attachments = self._extract_attachments(msg, email_id)
        result['attachments'] = [str(a) for a in attachments]

        # Process each attachment with docling
        for att_path in attachments:
            if att_path.suffix.lower() == '.pdf':
                att_output = self.temp_dir / f"att_{email_id:06d}_{att_path.stem}"
                att_output.mkdir(exist_ok=True)

                att_result = self.docling.process_with_docling(str(att_path), str(att_output))

                if not att_result['success']:
                    # Try fallback for PDF
                    att_result = self.docling.process_with_fallback(str(att_path))

                if att_result['success'] and att_result['text']:
                    result['text'] = result.get('text', '') + '\n\n--- ATTACHMENT ---\n\n' + att_result['text']

        # Step 4: AI Classification
        if result.get('text') and len(result['text']) >= 50:
            ai_result = self._classify_with_ai(result['text'])

            if ai_result['success']:
                result['doc_type'] = ai_result['doc_type']
                result['confidence'] = ai_result['confidence']
                result['fields'] = ai_result['fields']
                result['success'] = True
                self.stats['ai_classified'] += 1

                # Track by type
                doc_type = ai_result['doc_type']
                if doc_type not in self.stats['by_type']:
                    self.stats['by_type'][doc_type] = 0
                self.stats['by_type'][doc_type] += 1
            else:
                self.stats['ai_failed'] += 1
                result['errors'].append(f"AI classification failed: {ai_result['error']}")
                self.stats['errors'].append({
                    'email_id': email_id,
                    'stage': 'ai_classification',
                    'error': ai_result['error']
                })

        # Compute file hash for deduplication
        if result.get('text'):
            result['file_hash'] = hashlib.md5(result['text'].encode()).hexdigest()

        return result

    def run(self):
        """Main processing loop"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"🚀 THUNDERBIRD DOCLING EXTRACTOR - INSTANCE {self.instance_id}")
        self.logger.info("=" * 80)

        # Open mbox
        self.logger.info(f"📧 Opening mbox: {self.mbox_path}")
        mbox = mailbox.mbox(str(self.mbox_path))

        # Count and process
        processed = 0
        for idx, msg in enumerate(mbox):
            # Skip before range
            if idx < self.start_email:
                continue

            # Stop after range
            if self.end_email and idx >= self.end_email:
                break

            self.stats['total_emails'] += 1

            # Check resource limits
            if not self._check_resource_limit(85.0):
                self.logger.warning("⚠️ Resource limit reached, pausing...")
                import time
                time.sleep(5)

            # Progress log
            if processed % 50 == 0:
                usage = self._get_resource_usage()
                self.logger.info(f"📊 Progress: {processed}/{self.end_email - self.start_email if self.end_email else '?'} | "
                               f"CPU: {usage['cpu_percent']:.0f}% | RAM: {usage['ram_percent']:.0f}%")

            # Process email
            try:
                result = self.process_email(idx, msg)
                self.results.append(result)
                self.stats['emails_processed'] += 1

                if result['success']:
                    self.logger.info(f"✅ [{idx}] {result['doc_type']} ({result['confidence']}%) - {result['email_subject'][:50]}")
                else:
                    self.logger.info(f"⚠️ [{idx}] Failed - {result['email_subject'][:50]}")

            except Exception as e:
                self.logger.error(f"❌ [{idx}] Exception: {e}")
                self.stats['errors'].append({'email_id': idx, 'stage': 'process', 'error': str(e)})

            processed += 1

        # Save results
        self._save_results()
        self._print_statistics()

    def _save_results(self):
        """Save results to JSON working file"""
        output_file = self.instance_dir / f"instance_{self.instance_id}_results.json"

        report = {
            'scan_date': datetime.now().isoformat(),
            'instance_id': self.instance_id,
            'mbox_path': str(self.mbox_path),
            'email_range': [self.start_email, self.end_email],
            'statistics': self.stats,
            'results': self.results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Save errors separately for analysis
        if self.stats['errors']:
            errors_file = self.instance_dir / f"instance_{self.instance_id}_errors.json"
            with open(errors_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats['errors'], f, indent=2, ensure_ascii=False)

        self.logger.info(f"💾 Results saved: {output_file}")

    def _print_statistics(self):
        """Print final statistics"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 FINAL STATISTICS")
        self.logger.info("=" * 80)
        self.logger.info(f"Total emails: {self.stats['total_emails']}")
        self.logger.info(f"Processed: {self.stats['emails_processed']}")
        self.logger.info(f"Docling success: {self.stats['docling_success']}")
        self.logger.info(f"Docling failed: {self.stats['docling_failed']}")
        self.logger.info(f"Fallback success: {self.stats['fallback_success']}")
        self.logger.info(f"Fallback failed: {self.stats['fallback_failed']}")
        self.logger.info(f"AI classified: {self.stats['ai_classified']}")
        self.logger.info(f"AI failed: {self.stats['ai_failed']}")
        self.logger.info(f"Errors logged: {len(self.stats['errors'])}")

        if self.stats['by_type']:
            self.logger.info("\nBy document type:")
            for doc_type, count in sorted(self.stats['by_type'].items(), key=lambda x: -x[1]):
                self.logger.info(f"  {doc_type}: {count}")


def main():
    parser = argparse.ArgumentParser(description='Thunderbird Docling Extractor')
    parser.add_argument('--mbox', required=True, help='Path to mbox file')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--start', type=int, default=0, help='Start email index')
    parser.add_argument('--end', type=int, default=None, help='End email index')
    parser.add_argument('--instance', type=int, default=0, help='Instance ID')
    parser.add_argument('--ollama', default='http://localhost:11434', help='Ollama URL')

    args = parser.parse_args()

    extractor = ThunderbirdDoclingExtractor(
        mbox_path=args.mbox,
        output_dir=args.output,
        start_email=args.start,
        end_email=args.end,
        instance_id=args.instance,
        ollama_url=args.ollama
    )

    extractor.run()


if __name__ == "__main__":
    main()
