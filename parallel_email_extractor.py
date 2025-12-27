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
Parallel Email Extractor - 3-Phase Processing System
=====================================================
Extracts emails from Thunderbird, processes with Docling+OCR,
classifies with 32B AI, imports to Paperless with deduplication.

STROJE:
- Mac Mini M4 Pro: 14 CPU, 64GB RAM
- DGX (Dell WS): 20 CPU, 120GB RAM

FÁZE:
1. Docling extrakce (PDF+OCR) - paralelně na všech strojích
2. AI klasifikace 32B (fallback pokud Docling selže)
3. Import do Paperless s deduplikací

Author: Claude Code
Date: 2025-12-15
"""

import sys
import os
import json
import hashlib
import logging
import argparse
import subprocess
import psutil
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class MachineConfig:
    """Configuration for a processing machine"""
    name: str
    cpu_cores: int
    ram_gb: int
    max_cpu_percent: float = 85.0
    max_ram_percent: float = 85.0
    docling_venv: str = ""
    ollama_url: str = "http://localhost:11434"

    @property
    def max_instances(self) -> int:
        """Calculate max parallel instances (1 instance per 2 cores, min RAM 4GB each)"""
        by_cpu = int(self.cpu_cores * (self.max_cpu_percent / 100) / 2)
        by_ram = int(self.ram_gb * (self.max_ram_percent / 100) / 4)
        return max(1, min(by_cpu, by_ram))


# Machine configurations
MACHINES = {
    "mac_mini": MachineConfig(
        name="Mac Mini M4 Pro",
        cpu_cores=14,
        ram_gb=64,
        docling_venv="/Users/m.a.j.puzik/.venvs/docling",
        ollama_url="http://localhost:11434"
    ),
    "dgx": MachineConfig(
        name="DGX (Dell WS)",
        cpu_cores=20,
        ram_gb=120,
        docling_venv="/home/puzik/venv-docling",
        ollama_url="http://localhost:11434"
    ),
    "macbook": MachineConfig(
        name="MacBook Pro",
        cpu_cores=16,
        ram_gb=128,
        docling_venv="",  # Empty = use system python3 in PATH
        ollama_url="http://localhost:11434"
    )
}

# Paperless configuration
PAPERLESS_CONFIG = {
    "url": "http://192.168.10.85:8777",
    "token": "0c1072a02c43c50d109a0300f090a361fc1eb775"
}

# 28 Custom fields mapping
CUSTOM_FIELDS = {
    "supplier": 1,
    "customer": 2,
    "invoice_number": 3,
    "invoice_date": 4,
    "due_date": 5,
    "total_amount": 6,
    "currency": 7,
    "vat_amount": 8,
    "iban": 9,
    "swift": 10,
    "variable_symbol": 11,
    "payment_method": 12,
    "order_number": 13,
    "delivery_date": 14,
    "contract_number": 15,
    "subject": 16,
    "sender_email": 17,
    "recipient_email": 18,
    "document_language": 19,
    "confidence_score": 20,
    "processing_method": 21,
    "extracted_entities": 22,
    "keywords": 23,
    "category": 24,
    "subcategory": 25,
    "priority": 26,
    "action_required": 27,
    "notes": 28
}

# ============================================================================
# LOGGING
# ============================================================================

def setup_logging(instance_id: int, output_dir: Path) -> logging.Logger:
    """Setup logging for instance"""
    log_file = output_dir / f"instance_{instance_id}.log"

    logger = logging.getLogger(f"instance_{instance_id}")
    logger.setLevel(logging.INFO)

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        f'%(asctime)s - [Instance {instance_id}] - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# ============================================================================
# PHASE 1: DOCLING EXTRACTION
# ============================================================================

class DoclingExtractor:
    """Phase 1: Extract text from emails using Docling"""

    def __init__(self, venv_path: str, logger: logging.Logger):
        self.venv_path = venv_path
        self.logger = logger
        self.docling_available = self._check_docling()

    def _check_docling(self) -> bool:
        """Check if docling is available"""
        try:
            if self.venv_path:
                python = f"{self.venv_path}/bin/python"
            else:
                python = "python3"

            result = subprocess.run(
                [python, "-c", "from docling.document_converter import DocumentConverter; print('OK')"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and 'OK' in result.stdout:
                self.logger.info("✅ Docling available")
                return True
        except Exception as e:
            self.logger.warning(f"⚠️ Docling check failed: {e}")
        return False

    def extract_with_docling(self, input_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Extract text using Docling"""
        result = {
            "success": False,
            "method": "docling",
            "text": "",
            "pages": 0,
            "error": None,
            "processing_time": 0
        }

        if not self.docling_available:
            result["error"] = "Docling not available"
            return result

        start_time = time.time()

        try:
            if self.venv_path:
                python = f"{self.venv_path}/bin/python"
            else:
                python = "python3"

            # Create docling extraction script
            script = f'''
import sys
from pathlib import Path
from docling.document_converter import DocumentConverter

input_path = Path("{input_path}")
output_dir = Path("{output_dir}")
output_dir.mkdir(parents=True, exist_ok=True)

converter = DocumentConverter()

try:
    result = converter.convert(input_path)

    # Export to markdown
    md_content = result.document.export_to_markdown()

    output_file = output_dir / (input_path.stem + ".md")
    output_file.write_text(md_content)

    print(f"SUCCESS|{{len(md_content)}}|{{output_file}}")
except Exception as e:
    print(f"ERROR|{{str(e)}}")
'''

            proc = subprocess.run(
                [python, "-c", script],
                capture_output=True, text=True, timeout=300
            )

            if proc.returncode == 0 and "SUCCESS" in proc.stdout:
                parts = proc.stdout.strip().split("|")
                text_len = int(parts[1])
                output_file = Path(parts[2])

                if output_file.exists():
                    result["text"] = output_file.read_text()
                    result["pages"] = result["text"].count("\n---\n") + 1
                    result["success"] = True
            else:
                error_msg = proc.stderr or proc.stdout
                if "ERROR|" in error_msg:
                    error_msg = error_msg.split("ERROR|")[1].strip()
                result["error"] = error_msg[:500]

        except subprocess.TimeoutExpired:
            result["error"] = "Docling timeout (>300s)"
        except Exception as e:
            result["error"] = str(e)[:500]

        result["processing_time"] = time.time() - start_time
        return result


# ============================================================================
# PHASE 2: AI CLASSIFICATION (FALLBACK)
# ============================================================================

class AIClassifier:
    """Phase 2: Classify documents using 32B AI model"""

    def __init__(self, ollama_url: str, logger: logging.Logger):
        self.ollama_url = ollama_url
        self.logger = logger
        self.model = "qwen2.5:32b"
        self.available = self._check_ollama()

    def _check_ollama(self) -> bool:
        """Check if Ollama is available with 32B model"""
        try:
            import requests
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if any("32b" in m.lower() or "qwen" in m.lower() for m in models):
                    self.logger.info(f"✅ Ollama available with models: {models}")
                    return True
                self.logger.warning(f"⚠️ Ollama running but no 32B model. Available: {models}")
                # Try to find best available model
                for m in models:
                    if any(x in m.lower() for x in ["llama", "qwen", "mistral"]):
                        self.model = m
                        self.logger.info(f"Using fallback model: {m}")
                        return True
        except Exception as e:
            self.logger.warning(f"⚠️ Ollama check failed: {e}")
        return False

    def classify(self, text: str, email_metadata: Dict) -> Dict[str, Any]:
        """Classify document using AI"""
        result = {
            "success": False,
            "doc_type": "unknown",
            "confidence": 0,
            "fields": {},
            "error": None
        }

        if not self.available:
            result["error"] = "Ollama not available"
            return result

        if not text or len(text) < 50:
            result["error"] = "Insufficient text for classification"
            return result

        # Truncate text for prompt
        text_sample = text[:4000] if len(text) > 4000 else text

        prompt = f"""Analyze this email/document and extract information.

EMAIL METADATA:
- Subject: {email_metadata.get('subject', 'N/A')}
- From: {email_metadata.get('from', 'N/A')}
- Date: {email_metadata.get('date', 'N/A')}

CONTENT:
{text_sample}

Respond in JSON format:
{{
    "doc_type": "invoice|contract|order|delivery_note|bank_statement|correspondence|marketing|other",
    "confidence": 0-100,
    "language": "cs|en|de|other",
    "supplier": "company name or null",
    "customer": "company name or null",
    "invoice_number": "number or null",
    "total_amount": "amount or null",
    "currency": "CZK|EUR|USD|null",
    "invoice_date": "YYYY-MM-DD or null",
    "keywords": ["keyword1", "keyword2"],
    "summary": "one sentence summary"
}}"""

        try:
            import requests
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=120
            )

            if resp.status_code == 200:
                response_text = resp.json().get("response", "")

                # Extract JSON from response
                import re
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    ai_result = json.loads(json_match.group())

                    result["success"] = True
                    result["doc_type"] = ai_result.get("doc_type", "unknown")
                    result["confidence"] = ai_result.get("confidence", 50)
                    result["fields"] = {
                        "supplier": ai_result.get("supplier"),
                        "customer": ai_result.get("customer"),
                        "invoice_number": ai_result.get("invoice_number"),
                        "total_amount": ai_result.get("total_amount"),
                        "currency": ai_result.get("currency"),
                        "invoice_date": ai_result.get("invoice_date"),
                        "keywords": ai_result.get("keywords", []),
                        "summary": ai_result.get("summary"),
                        "language": ai_result.get("language")
                    }
            else:
                result["error"] = f"Ollama error: {resp.status_code}"

        except json.JSONDecodeError as e:
            result["error"] = f"JSON parse error: {e}"
        except Exception as e:
            result["error"] = str(e)[:200]

        return result


# ============================================================================
# PHASE 3: PAPERLESS IMPORT WITH DEDUPLICATION
# ============================================================================

class PaperlessImporter:
    """Phase 3: Import to Paperless with deduplication"""

    def __init__(self, config: Dict, logger: logging.Logger):
        self.url = config["url"]
        self.token = config["token"]
        self.logger = logger
        self.existing_hashes = set()
        self._load_existing_hashes()

    def _load_existing_hashes(self):
        """Load existing document hashes from Paperless"""
        try:
            import requests
            headers = {"Authorization": f"Token {self.token}"}

            # Get all documents with checksum
            page = 1
            while True:
                resp = requests.get(
                    f"{self.url}/api/documents/?page={page}&page_size=100",
                    headers=headers, timeout=30
                )
                if resp.status_code != 200:
                    break

                data = resp.json()
                for doc in data.get("results", []):
                    if doc.get("checksum"):
                        self.existing_hashes.add(doc["checksum"])

                if not data.get("next"):
                    break
                page += 1

            self.logger.info(f"📚 Loaded {len(self.existing_hashes)} existing document hashes")

        except Exception as e:
            self.logger.warning(f"⚠️ Could not load existing hashes: {e}")

    def is_duplicate(self, file_hash: str) -> bool:
        """Check if document already exists"""
        return file_hash in self.existing_hashes

    def import_document(self, pdf_path: Path, metadata: Dict, fields: Dict) -> Dict[str, Any]:
        """Import document to Paperless"""
        result = {
            "success": False,
            "document_id": None,
            "skipped_duplicate": False,
            "error": None
        }

        # Check for duplicate
        file_hash = metadata.get("file_hash")
        if file_hash and self.is_duplicate(file_hash):
            result["skipped_duplicate"] = True
            result["success"] = True
            self.logger.info(f"⏭️ Skipping duplicate: {pdf_path.name}")
            return result

        try:
            import requests
            headers = {"Authorization": f"Token {self.token}"}

            # Upload document
            with open(pdf_path, 'rb') as f:
                files = {'document': (pdf_path.name, f, 'application/pdf')}
                data = {
                    'title': metadata.get('title', pdf_path.stem)[:128],
                }

                # Add correspondent if available
                if fields.get('supplier'):
                    data['correspondent'] = fields['supplier']

                resp = requests.post(
                    f"{self.url}/api/documents/post_document/",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60
                )

            if resp.status_code in [200, 201, 202]:
                task_id = resp.json().get("task_id")
                result["success"] = True
                result["task_id"] = task_id

                # Add hash to avoid re-importing
                if file_hash:
                    self.existing_hashes.add(file_hash)

                self.logger.info(f"✅ Uploaded: {pdf_path.name}")
            else:
                result["error"] = f"Upload failed: {resp.status_code} - {resp.text[:200]}"

        except Exception as e:
            result["error"] = str(e)[:200]

        return result


# ============================================================================
# EMAIL PROCESSOR (MAIN WORKER)
# ============================================================================

class EmailProcessor:
    """Main email processing worker"""

    def __init__(
        self,
        instance_id: int,
        email_dir: Path,
        output_dir: Path,
        start_idx: int,
        end_idx: int,
        machine_config: MachineConfig
    ):
        self.instance_id = instance_id
        self.email_dir = email_dir
        self.output_dir = output_dir / f"instance_{instance_id}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.start_idx = start_idx
        self.end_idx = end_idx
        self.machine_config = machine_config

        # Setup logging
        self.logger = setup_logging(instance_id, self.output_dir)

        # Initialize components
        self.docling = DoclingExtractor(machine_config.docling_venv, self.logger)
        self.classifier = AIClassifier(machine_config.ollama_url, self.logger)
        self.importer = PaperlessImporter(PAPERLESS_CONFIG, self.logger)

        # Statistics
        self.stats = {
            "total": 0,
            "processed": 0,
            "docling_success": 0,
            "docling_failed": 0,
            "ai_classified": 0,
            "ai_failed": 0,
            "imported": 0,
            "duplicates_skipped": 0,
            "errors": []
        }

        # Results
        self.results = []

    def _get_email_folders(self) -> List[Path]:
        """Get list of email folders to process"""
        all_folders = sorted([
            d for d in self.email_dir.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ])

        # Get subfolders (actual email folders)
        email_folders = []
        for folder in all_folders:
            for subfolder in folder.iterdir():
                if subfolder.is_dir():
                    email_folders.append(subfolder)

        email_folders = sorted(email_folders)

        # Return slice for this instance
        return email_folders[self.start_idx:self.end_idx]

    def _check_resources(self) -> bool:
        """Check if resources are within limits"""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent

        if cpu > self.machine_config.max_cpu_percent:
            self.logger.warning(f"⚠️ CPU at {cpu}%, waiting...")
            return False
        if ram > self.machine_config.max_ram_percent:
            self.logger.warning(f"⚠️ RAM at {ram}%, waiting...")
            return False
        return True

    def process_email(self, email_folder: Path) -> Dict[str, Any]:
        """Process single email folder"""
        result = {
            "email_id": email_folder.name,
            "success": False,
            "docling_result": None,
            "ai_result": None,
            "import_result": None,
            "errors": []
        }

        # Find files in email folder
        files = list(email_folder.glob("*"))
        eml_file = next((f for f in files if f.suffix.lower() == ".eml"), None)
        body_file = next((f for f in files if f.name == "body.txt"), None)
        pdf_files = [f for f in files if f.suffix.lower() == ".pdf"]
        metadata_file = next((f for f in files if f.name == "metadata.json"), None)

        # Load metadata
        metadata = {}
        if metadata_file and metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
            except:
                pass

        all_text = ""

        # PHASE 1: Docling extraction for PDFs
        for pdf_file in pdf_files:
            docling_output = self.output_dir / "docling" / email_folder.name
            docling_result = self.docling.extract_with_docling(pdf_file, docling_output)

            if docling_result["success"]:
                all_text += f"\n\n--- {pdf_file.name} ---\n\n" + docling_result["text"]
                self.stats["docling_success"] += 1
                result["docling_result"] = "success"
            else:
                self.stats["docling_failed"] += 1
                result["errors"].append(f"Docling failed: {docling_result['error']}")

                # Log failure for later analysis
                self.stats["errors"].append({
                    "email_id": email_folder.name,
                    "file": pdf_file.name,
                    "stage": "docling",
                    "error": docling_result["error"]
                })

        # Add body text from EML or body.txt
        email_body = ""
        if eml_file and eml_file.exists():
            try:
                import email
                from email import policy
                from email.parser import BytesParser

                with open(eml_file, 'rb') as f:
                    msg = BytesParser(policy=policy.default).parse(f)

                # Extract subject and from for metadata
                if not metadata.get("subject"):
                    metadata["subject"] = msg.get("Subject", "")
                if not metadata.get("from"):
                    metadata["from"] = msg.get("From", "")
                if not metadata.get("date"):
                    metadata["date"] = msg.get("Date", "")

                # Get email body (prefer plain text, fallback to HTML)
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            email_body = part.get_content()
                            break
                        elif content_type == "text/html" and not email_body:
                            # Strip HTML tags for basic extraction
                            import re
                            html = part.get_content()
                            email_body = re.sub(r'<[^>]+>', ' ', html)
                            email_body = re.sub(r'\s+', ' ', email_body)
                else:
                    email_body = msg.get_content()
            except Exception as e:
                self.logger.debug(f"EML parse error: {e}")

        if not email_body and body_file and body_file.exists():
            try:
                email_body = body_file.read_text(errors='ignore')
            except:
                pass

        all_text = email_body + all_text

        # Compute file hash for deduplication
        if all_text:
            result["file_hash"] = hashlib.md5(all_text.encode()).hexdigest()

        # PHASE 2: AI Classification
        if all_text and len(all_text) >= 50:
            ai_result = self.classifier.classify(all_text, metadata)
            result["ai_result"] = ai_result

            if ai_result["success"]:
                self.stats["ai_classified"] += 1
                result["doc_type"] = ai_result["doc_type"]
                result["confidence"] = ai_result["confidence"]
                result["fields"] = ai_result["fields"]
                result["success"] = True
            else:
                self.stats["ai_failed"] += 1
                result["errors"].append(f"AI failed: {ai_result['error']}")

                self.stats["errors"].append({
                    "email_id": email_folder.name,
                    "stage": "ai_classification",
                    "error": ai_result["error"]
                })

        return result

    def run(self):
        """Main processing loop"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"🚀 PARALLEL EMAIL EXTRACTOR - INSTANCE {self.instance_id}")
        self.logger.info(f"📁 Processing emails {self.start_idx} to {self.end_idx}")
        self.logger.info("=" * 80)

        email_folders = self._get_email_folders()
        self.stats["total"] = len(email_folders)

        self.logger.info(f"📧 Found {len(email_folders)} emails to process")

        for idx, email_folder in enumerate(email_folders):
            # Check resources
            while not self._check_resources():
                time.sleep(5)

            # Progress
            if idx % 50 == 0:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                self.logger.info(
                    f"📊 Progress: {idx}/{len(email_folders)} | "
                    f"CPU: {cpu:.0f}% | RAM: {ram:.0f}%"
                )

            # Process email
            try:
                result = self.process_email(email_folder)
                self.results.append(result)
                self.stats["processed"] += 1

                if result["success"]:
                    self.logger.info(
                        f"✅ [{idx}] {result.get('doc_type', '?')} "
                        f"({result.get('confidence', 0)}%) - {email_folder.name[:40]}"
                    )
                else:
                    self.logger.info(f"⚠️ [{idx}] Failed - {email_folder.name[:40]}")

            except Exception as e:
                self.logger.error(f"❌ [{idx}] Exception: {e}")
                self.stats["errors"].append({
                    "email_id": email_folder.name,
                    "stage": "process",
                    "error": str(e)
                })

        # Save results
        self._save_results()
        self._print_statistics()

    def _save_results(self):
        """Save results to JSON"""
        output_file = self.output_dir / f"results.json"

        report = {
            "scan_date": datetime.now().isoformat(),
            "instance_id": self.instance_id,
            "email_range": [self.start_idx, self.end_idx],
            "statistics": self.stats,
            "results": self.results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        # Save errors separately
        if self.stats["errors"]:
            errors_file = self.output_dir / "errors.json"
            with open(errors_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats["errors"], f, indent=2, ensure_ascii=False)

        self.logger.info(f"💾 Results saved: {output_file}")

    def _print_statistics(self):
        """Print final statistics"""
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 FINAL STATISTICS")
        self.logger.info("=" * 80)
        self.logger.info(f"Total emails: {self.stats['total']}")
        self.logger.info(f"Processed: {self.stats['processed']}")
        self.logger.info(f"Docling success: {self.stats['docling_success']}")
        self.logger.info(f"Docling failed: {self.stats['docling_failed']}")
        self.logger.info(f"AI classified: {self.stats['ai_classified']}")
        self.logger.info(f"AI failed: {self.stats['ai_failed']}")
        self.logger.info(f"Errors logged: {len(self.stats['errors'])}")


# ============================================================================
# LAUNCHER
# ============================================================================

def calculate_distribution(total_emails: int, machines: Dict[str, MachineConfig]) -> List[Dict]:
    """Calculate email distribution across machines and instances"""
    distributions = []

    # Calculate total instances
    total_instances = sum(m.max_instances for m in machines.values())
    emails_per_instance = total_emails // total_instances

    current_idx = 0
    instance_id = 0

    for machine_name, config in machines.items():
        for i in range(config.max_instances):
            start_idx = current_idx
            end_idx = min(current_idx + emails_per_instance, total_emails)

            # Last instance gets remaining
            if instance_id == total_instances - 1:
                end_idx = total_emails

            distributions.append({
                "instance_id": instance_id,
                "machine": machine_name,
                "start_idx": start_idx,
                "end_idx": end_idx,
                "email_count": end_idx - start_idx
            })

            current_idx = end_idx
            instance_id += 1

    return distributions


def main():
    parser = argparse.ArgumentParser(description='Parallel Email Extractor')
    parser.add_argument('--email-dir', required=True, help='Directory with email folders')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--instance', type=int, default=None, help='Run specific instance')
    parser.add_argument('--start', type=int, default=None, help='Start email index')
    parser.add_argument('--end', type=int, default=None, help='End email index')
    parser.add_argument('--machine', default='mac_mini', choices=MACHINES.keys(), help='Machine to use')
    parser.add_argument('--plan', action='store_true', help='Show distribution plan only')

    args = parser.parse_args()

    email_dir = Path(args.email_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Count emails
    total_emails = sum(1 for d in email_dir.iterdir() if d.is_dir() for sd in d.iterdir() if sd.is_dir())

    print(f"\n{'='*80}")
    print(f"📧 PARALLEL EMAIL EXTRACTOR")
    print(f"{'='*80}")
    print(f"Email directory: {email_dir}")
    print(f"Total emails: {total_emails}")
    print(f"Output directory: {output_dir}")

    # Calculate distribution
    distributions = calculate_distribution(total_emails, MACHINES)

    print(f"\n📊 Distribution Plan:")
    print("-" * 60)
    for d in distributions:
        print(f"  Instance {d['instance_id']:2d} ({d['machine']:10s}): "
              f"emails {d['start_idx']:6d} - {d['end_idx']:6d} ({d['email_count']:5d} emails)")
    print("-" * 60)
    print(f"  Total instances: {len(distributions)}")

    if args.plan:
        return

    # Run specific instance or all
    if args.instance is not None:
        # Run single instance
        dist = distributions[args.instance]
        config = MACHINES[dist["machine"]]

        processor = EmailProcessor(
            instance_id=dist["instance_id"],
            email_dir=email_dir,
            output_dir=output_dir,
            start_idx=args.start if args.start else dist["start_idx"],
            end_idx=args.end if args.end else dist["end_idx"],
            machine_config=config
        )
        processor.run()

    elif args.start is not None and args.end is not None:
        # Run with manual range
        config = MACHINES[args.machine]

        processor = EmailProcessor(
            instance_id=0,
            email_dir=email_dir,
            output_dir=output_dir,
            start_idx=args.start,
            end_idx=args.end,
            machine_config=config
        )
        processor.run()

    else:
        print("\n⚠️ Specify --instance N or --start/--end to run processing")
        print("   Use --plan to see distribution only")


if __name__ == "__main__":
    main()
