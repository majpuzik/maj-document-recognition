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
Phase 1: Docling Extraction - Massively Parallel
=================================================
Extracts text from emails (EML + PDF attachments) using Docling.
Classifies with regex patterns, extracts 31 custom fields.

MACHINES:
- Mac Mini M4 Pro: 14 CPU, 64GB RAM, 10 processes
- MacBook Pro: 16 CPU, 128GB RAM, 15 processes
- DGX (Dell WS): 20 CPU, 120GB RAM, 15 processes

OUTPUT:
- phase1_results/{email_id}.json  (successful extractions)
- phase1_failed.jsonl             (failures for Phase 2)
- phase1_stats.json               (statistics)

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
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import time
import email
from email import policy
from email.parser import BytesParser

# Progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ISDOC integration
try:
    from isdoc_generator import generate_isdoc_for_result, should_generate_isdoc
except ImportError:
    from email_extractor.isdoc_generator import generate_isdoc_for_result, should_generate_isdoc

# Enhanced field extractor with direction, subtype, VAT breakdown
try:
    from src.ocr.enhanced_field_extractor import EnhancedFieldExtractor
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.ocr.enhanced_field_extractor import EnhancedFieldExtractor

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
    processes: int = 10

# Machine configurations
MACHINES = {
    "mac_mini": MachineConfig(
        name="Mac Mini M4 Pro",
        cpu_cores=14,
        ram_gb=64,
        docling_venv="/Users/m.a.j.puzik/.venvs/docling",
        processes=10
    ),
    "macbook": MachineConfig(
        name="MacBook Pro",
        cpu_cores=16,
        ram_gb=128,
        docling_venv="",  # Use system python
        processes=15
    ),
    "dgx": MachineConfig(
        name="DGX (Dell WS)",
        cpu_cores=20,
        ram_gb=120,
        docling_venv="/home/puzik/venv-docling",
        processes=15
    )
}

# Email directory
EMAIL_DIR = Path("/Volumes/ACASIS/parallel_scan_1124_1205/thunderbird-emails")

# Output directory
OUTPUT_DIR = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output")

# Document type patterns (for regex classification)
DOC_TYPE_PATTERNS = {
    "invoice": [
        r"faktur[ay]", r"invoice", r"rechnung", r"daňový doklad",
        r"číslo faktury", r"invoice.*number", r"variabilní symbol",
        r"celkem k úhradě", r"total amount", r"datum splatnosti"
    ],
    "contract": [
        r"smlouv[ay]", r"contract", r"vertrag", r"agreement",
        r"smluvní strany", r"contracting parties", r"podpis"
    ],
    "bank_statement": [
        r"výpis z účtu", r"bank statement", r"kontoauszug",
        r"zůstatek", r"balance", r"transakce", r"transaction"
    ],
    "order": [
        r"objednávk[ay]", r"order", r"bestellung", r"purchase order",
        r"č\. obj", r"order.*number"
    ],
    "delivery_note": [
        r"dodací list", r"delivery note", r"lieferschein",
        r"příjemka", r"předávací protokol"
    ],
    "receipt": [
        r"účtenk[ay]", r"pokladní doklad", r"receipt", r"kassenbon",
        r"paragon", r"stvrzenka"
    ],
    "tax_document": [
        r"daňov[ýé] přiznání", r"tax return", r"dph", r"vat",
        r"kontrolní hlášení"
    ],
    "correspondence": [
        r"vážen[ýá]", r"dear", r"sehr geehrte", r"dobrý den",
        r"s pozdravem", r"regards", r"mit freundlichen"
    ],
    "marketing": [
        r"newsletter", r"nabídka", r"offer", r"sleva", r"discount",
        r"akce", r"sale", r"unsubscribe", r"odhlásit"
    ]
}

# 31 Custom fields + 7 enhanced fields (38 total)
CUSTOM_FIELDS = [
    "doc_typ", "protistrana_nazev", "protistrana_ico", "protistrana_typ",
    "castka_celkem", "datum_dokumentu", "cislo_dokumentu", "mena",
    "stav_platby", "datum_splatnosti", "kategorie", "email_from",
    "email_to", "email_subject", "od_osoba", "od_osoba_role",
    "od_firma", "pro_osoba", "pro_osoba_role", "pro_firma",
    "predmet", "ai_summary", "ai_keywords", "ai_popis",
    "typ_sluzby", "nazev_sluzby", "predmet_typ", "predmet_nazev",
    "polozky_text", "polozky_json", "perioda",
    # Enhanced fields (new)
    "direction", "doc_subtype", "castka_zaklad", "castka_dph",
    "sazba_dph", "variabilni_symbol", "protistrana_dic"
]

# ============================================================================
# LOGGING
# ============================================================================

def setup_logging(instance_id: int, output_dir: Path) -> logging.Logger:
    """Setup logging for instance"""
    log_file = output_dir / f"phase1_instance_{instance_id}.log"

    logger = logging.getLogger(f"phase1_{instance_id}")
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear existing handlers

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        f'%(asctime)s - [P1-{instance_id}] - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# ============================================================================
# FIELD EXTRACTORS (REGEX-BASED)
# ============================================================================

class FieldExtractor:
    """Extract 31 custom fields using regex patterns"""

    # ICO patterns
    ICO_PATTERN = re.compile(r'IČO?[:\s]*(\d{8})', re.IGNORECASE)
    DIC_PATTERN = re.compile(r'DIČ[:\s]*(CZ\d{8,10})', re.IGNORECASE)

    # Amount patterns
    AMOUNT_PATTERNS = [
        re.compile(r'celkem[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)', re.IGNORECASE),
        re.compile(r'total[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)', re.IGNORECASE),
        re.compile(r'k úhradě[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)', re.IGNORECASE),
        re.compile(r'částka[:\s]*([0-9\s,.]+)\s*(Kč|CZK|EUR|€|\$|USD)', re.IGNORECASE),
    ]

    # Date patterns
    DATE_PATTERNS = [
        re.compile(r'(\d{1,2})[./](\d{1,2})[./](\d{4})'),
        re.compile(r'(\d{4})-(\d{2})-(\d{2})'),
    ]

    # Document number patterns
    DOC_NUM_PATTERNS = [
        re.compile(r'(?:faktura|invoice|doklad)[:\s#]*([A-Z0-9/-]+)', re.IGNORECASE),
        re.compile(r'č(?:íslo)?[:\s.]*([A-Z0-9/-]{5,})', re.IGNORECASE),
    ]

    # Variable symbol
    VS_PATTERN = re.compile(r'(?:VS|variabilní symbol)[:\s]*(\d{4,10})', re.IGNORECASE)

    # IBAN
    IBAN_PATTERN = re.compile(r'([A-Z]{2}\d{2}[A-Z0-9]{10,30})', re.IGNORECASE)

    # Company name patterns
    COMPANY_PATTERNS = [
        re.compile(r'(?:dodavatel|supplier|firma)[:\s]*([^\n,]{3,50})', re.IGNORECASE),
        re.compile(r'(?:odběratel|customer)[:\s]*([^\n,]{3,50})', re.IGNORECASE),
    ]

    @classmethod
    def extract_all(cls, text: str, email_meta: Dict) -> Dict[str, Any]:
        """Extract all 31 custom fields"""
        fields = {f: None for f in CUSTOM_FIELDS}

        if not text:
            return fields

        text_lower = text.lower()

        # 1. doc_typ - set by classifier
        # 2-4. protistrana
        ico_match = cls.ICO_PATTERN.search(text)
        if ico_match:
            fields["protistrana_ico"] = ico_match.group(1)

        for pattern in cls.COMPANY_PATTERNS:
            match = pattern.search(text)
            if match:
                fields["protistrana_nazev"] = match.group(1).strip()
                break

        # 5. castka_celkem
        for pattern in cls.AMOUNT_PATTERNS:
            match = pattern.search(text)
            if match:
                amount_str = match.group(1).replace(" ", "").replace(",", ".")
                try:
                    fields["castka_celkem"] = float(amount_str)
                except:
                    fields["castka_celkem"] = amount_str
                break

        # 6. datum_dokumentu
        for pattern in cls.DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                if len(groups[0]) == 4:  # YYYY-MM-DD
                    fields["datum_dokumentu"] = f"{groups[0]}-{groups[1]}-{groups[2]}"
                else:  # DD.MM.YYYY
                    fields["datum_dokumentu"] = f"{groups[2]}-{groups[1].zfill(2)}-{groups[0].zfill(2)}"
                break

        # 7. cislo_dokumentu
        for pattern in cls.DOC_NUM_PATTERNS:
            match = pattern.search(text)
            if match:
                fields["cislo_dokumentu"] = match.group(1)
                break

        # 8. mena
        if "kč" in text_lower or "czk" in text_lower:
            fields["mena"] = "CZK"
        elif "eur" in text_lower or "€" in text:
            fields["mena"] = "EUR"
        elif "usd" in text_lower or "$" in text:
            fields["mena"] = "USD"

        # 10. datum_splatnosti
        splatnost_match = re.search(r'splatnost[:\s]*(\d{1,2})[./](\d{1,2})[./](\d{4})', text, re.IGNORECASE)
        if splatnost_match:
            g = splatnost_match.groups()
            fields["datum_splatnosti"] = f"{g[2]}-{g[1].zfill(2)}-{g[0].zfill(2)}"

        # 12-14. email fields
        fields["email_from"] = email_meta.get("from", "")
        fields["email_to"] = email_meta.get("to", "")
        fields["email_subject"] = email_meta.get("subject", "")

        # 15-20. osoba/firma - basic extraction
        from_header = email_meta.get("from", "")
        if "<" in from_header:
            fields["od_osoba"] = from_header.split("<")[0].strip().strip('"')

        # 21. predmet
        fields["predmet"] = email_meta.get("subject", "")

        # 23. ai_keywords - basic keyword extraction
        keywords = []
        for word in ["faktura", "smlouva", "objednávka", "platba", "účet"]:
            if word in text_lower:
                keywords.append(word)
        fields["ai_keywords"] = ", ".join(keywords) if keywords else None

        return fields


# ============================================================================
# DOCLING EXTRACTOR
# ============================================================================

class DoclingExtractor:
    """Extract text from PDFs using Docling"""

    def __init__(self, venv_path: str, logger: logging.Logger):
        self.venv_path = venv_path
        self.logger = logger
        self.available = self._check_docling()

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
                self.logger.info("Docling available")
                return True
        except Exception as e:
            self.logger.warning(f"Docling check failed: {e}")
        return False

    def extract_pdf(self, pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
        """Extract text from PDF using Docling"""
        result = {
            "success": False,
            "text": "",
            "pages": 0,
            "error": None,
            "time_ms": 0
        }

        if not self.available:
            result["error"] = "Docling not available"
            return result

        start = time.time()

        try:
            if self.venv_path:
                python = f"{self.venv_path}/bin/python"
            else:
                python = "python3"

            # Docling extraction script
            script = f'''
import sys
from pathlib import Path
from docling.document_converter import DocumentConverter

try:
    converter = DocumentConverter()
    result = converter.convert(Path("{pdf_path}"))
    md = result.document.export_to_markdown()
    print("SUCCESS")
    print(md)
except Exception as e:
    print(f"ERROR: {{e}}")
'''

            proc = subprocess.run(
                [python, "-c", script],
                capture_output=True, text=True, timeout=120
            )

            output = proc.stdout
            if output.startswith("SUCCESS"):
                lines = output.split("\n", 1)
                result["text"] = lines[1] if len(lines) > 1 else ""
                result["pages"] = result["text"].count("---") + 1
                result["success"] = True
            else:
                result["error"] = proc.stderr[:500] if proc.stderr else output[:500]

        except subprocess.TimeoutExpired:
            result["error"] = "Timeout (>120s)"
        except Exception as e:
            result["error"] = str(e)[:500]

        result["time_ms"] = int((time.time() - start) * 1000)
        return result


# ============================================================================
# EMAIL PARSER
# ============================================================================

class EmailParser:
    """Parse EML files and extract content"""

    @staticmethod
    def parse_eml(eml_path: Path) -> Dict[str, Any]:
        """Parse EML file and extract metadata + body"""
        result = {
            "success": False,
            "metadata": {},
            "body_text": "",
            "body_html": "",
            "attachments": [],
            "error": None
        }

        try:
            with open(eml_path, 'rb') as f:
                msg = BytesParser(policy=policy.default).parse(f)

            # Extract metadata
            result["metadata"] = {
                "from": msg.get("From", ""),
                "to": msg.get("To", ""),
                "cc": msg.get("Cc", ""),
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", ""),
                "message_id": msg.get("Message-ID", ""),
            }

            # Extract body
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    disposition = str(part.get("Content-Disposition", ""))

                    if "attachment" in disposition:
                        # Track attachment
                        filename = part.get_filename()
                        if filename:
                            result["attachments"].append({
                                "filename": filename,
                                "content_type": content_type,
                                "size": len(part.get_payload(decode=True) or b"")
                            })
                    elif content_type == "text/plain":
                        try:
                            result["body_text"] = part.get_content()
                        except:
                            payload = part.get_payload(decode=True)
                            if payload:
                                result["body_text"] = payload.decode('utf-8', errors='ignore')
                    elif content_type == "text/html" and not result["body_text"]:
                        try:
                            html = part.get_content()
                        except:
                            payload = part.get_payload(decode=True)
                            html = payload.decode('utf-8', errors='ignore') if payload else ""

                        # Strip HTML tags
                        result["body_html"] = html
                        result["body_text"] = re.sub(r'<[^>]+>', ' ', html)
                        result["body_text"] = re.sub(r'\s+', ' ', result["body_text"]).strip()
            else:
                content_type = msg.get_content_type()
                try:
                    body = msg.get_content()
                except:
                    payload = msg.get_payload(decode=True)
                    body = payload.decode('utf-8', errors='ignore') if payload else ""

                if content_type == "text/html":
                    result["body_html"] = body
                    result["body_text"] = re.sub(r'<[^>]+>', ' ', body)
                    result["body_text"] = re.sub(r'\s+', ' ', result["body_text"]).strip()
                else:
                    result["body_text"] = body

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)[:500]

        return result


# ============================================================================
# DOCUMENT CLASSIFIER
# ============================================================================

class DocumentClassifier:
    """Classify documents using regex patterns"""

    @staticmethod
    def classify(text: str) -> Tuple[str, int]:
        """Classify document type and return confidence"""
        if not text:
            return "unknown", 0

        text_lower = text.lower()
        scores = {}

        for doc_type, patterns in DOC_TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches * 10
            scores[doc_type] = min(score, 95)  # Cap at 95%

        if not scores or max(scores.values()) == 0:
            return "other", 50

        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]

        # Minimum confidence threshold
        if confidence < 30:
            return "other", confidence

        return best_type, confidence


# ============================================================================
# PHASE 1 PROCESSOR
# ============================================================================

class Phase1Processor:
    """Main Phase 1 processor"""

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
        self.output_dir = output_dir
        self.results_dir = output_dir / "phase1_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.start_idx = start_idx
        self.end_idx = end_idx
        self.config = machine_config

        # Setup logging
        self.logger = setup_logging(instance_id, output_dir)

        # Initialize components
        self.docling = DoclingExtractor(machine_config.docling_venv, self.logger)
        self.email_parser = EmailParser()
        self.classifier = DocumentClassifier()
        self.enhanced_extractor = EnhancedFieldExtractor()

        # Failed items file (line-delimited JSON)
        self.failed_file = output_dir / f"phase1_failed_{instance_id}.jsonl"

        # Statistics
        self.stats = {
            "instance_id": instance_id,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "total": 0,
            "processed": 0,
            "success": 0,
            "failed": 0,
            "by_type": {},
            "start_time": None,
            "end_time": None
        }

    def _get_email_folders(self) -> List[Path]:
        """Get list of email folders to process"""
        all_folders = []

        # Get all mailbox folders
        for mailbox in sorted(self.email_dir.iterdir()):
            if not mailbox.is_dir() or mailbox.name.startswith('.'):
                continue

            # Get email folders within mailbox
            for email_folder in sorted(mailbox.iterdir()):
                if email_folder.is_dir():
                    all_folders.append(email_folder)

        # Return slice for this instance
        return all_folders[self.start_idx:self.end_idx]

    def _check_resources(self) -> bool:
        """Check if resources are within limits"""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent

        if cpu > self.config.max_cpu_percent:
            self.logger.warning(f"CPU {cpu:.0f}% > {self.config.max_cpu_percent}%, pausing...")
            return False
        if ram > self.config.max_ram_percent:
            self.logger.warning(f"RAM {ram:.0f}% > {self.config.max_ram_percent}%, pausing...")
            return False
        return True

    def _log_failed(self, email_id: str, reason: str, metadata: Dict = None):
        """Log failed item for Phase 2"""
        entry = {
            "email_id": email_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        with open(self.failed_file, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self.stats["failed"] += 1

    def _save_result(self, email_id: str, result: Dict):
        """Save successful result"""
        output_file = self.results_dir / f"{email_id}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        self.stats["success"] += 1

        # Update type stats
        doc_type = result.get("doc_type", "unknown")
        self.stats["by_type"][doc_type] = self.stats["by_type"].get(doc_type, 0) + 1

        # Generate ISDOC for accounting documents (invoice, receipt, tax_document, bank_statement)
        if should_generate_isdoc(doc_type):
            try:
                isdoc_result = {
                    "email_id": email_id,
                    "doc_type": doc_type,
                    "extracted_fields": result.get("fields", {}),
                    "text_content": ""  # Text is not stored in result
                }
                success, path_or_error = generate_isdoc_for_result(isdoc_result)
                if success:
                    result["isdoc_path"] = path_or_error
                    self.stats["isdoc_generated"] = self.stats.get("isdoc_generated", 0) + 1
                    self.logger.debug(f"ISDOC: {path_or_error}")
            except Exception as e:
                self.logger.warning(f"ISDOC generation failed: {e}")

    def process_email(self, email_folder: Path) -> bool:
        """Process single email folder"""
        email_id = email_folder.name

        # Find message.eml
        eml_file = email_folder / "message.eml"
        if not eml_file.exists():
            # Try to find any .eml file
            eml_files = list(email_folder.glob("*.eml"))
            if eml_files:
                eml_file = eml_files[0]
            else:
                self._log_failed(email_id, "No EML file found")
                return False

        # Parse email
        email_result = self.email_parser.parse_eml(eml_file)
        if not email_result["success"]:
            self._log_failed(email_id, f"EML parse error: {email_result['error']}")
            return False

        all_text = email_result["body_text"]

        # Find and process PDF attachments
        pdf_files = list(email_folder.glob("*.pdf")) + list(email_folder.glob("*.PDF"))
        pdf_texts = []

        for pdf_file in pdf_files:
            docling_result = self.docling.extract_pdf(pdf_file, self.output_dir / "docling_cache")
            if docling_result["success"]:
                pdf_texts.append(f"\n\n--- {pdf_file.name} ---\n\n{docling_result['text']}")

        # Combine all text
        all_text = all_text + "".join(pdf_texts)

        # Check if we have enough text
        if len(all_text.strip()) < 50:
            self._log_failed(email_id, "Insufficient text", email_result["metadata"])
            return False

        # Classify document
        doc_type, confidence = self.classifier.classify(all_text)

        # Extract 31 custom fields (basic)
        fields = FieldExtractor.extract_all(all_text, email_result["metadata"])
        fields["doc_typ"] = doc_type

        # Enhanced extraction (direction, subtype, VAT breakdown, category)
        email_from = email_result["metadata"].get("from", "")
        email_to = email_result["metadata"].get("to", "")
        enhanced = self.enhanced_extractor.extract_all(
            text=all_text,
            doc_type=doc_type,
            email_from=email_from,
            email_to=email_to
        )

        # Merge enhanced fields into basic fields
        enhanced_dict = self.enhanced_extractor.to_dict(enhanced)
        fields["direction"] = enhanced_dict.get("direction")
        fields["doc_subtype"] = enhanced_dict.get("doc_subtype")
        fields["castka_zaklad"] = enhanced_dict.get("castka_zaklad")
        fields["castka_dph"] = enhanced_dict.get("castka_dph")
        fields["sazba_dph"] = enhanced_dict.get("sazba_dph")
        fields["variabilni_symbol"] = enhanced_dict.get("variabilni_symbol")
        fields["protistrana_dic"] = enhanced_dict.get("protistrana_dic")

        # Override with enhanced values if they're better
        if enhanced_dict.get("castka_celkem") and not fields.get("castka_celkem"):
            fields["castka_celkem"] = enhanced_dict["castka_celkem"]
        if enhanced_dict.get("cislo_dokumentu") and not fields.get("cislo_dokumentu"):
            fields["cislo_dokumentu"] = enhanced_dict["cislo_dokumentu"]
        if enhanced_dict.get("protistrana_ico") and not fields.get("protistrana_ico"):
            fields["protistrana_ico"] = enhanced_dict["protistrana_ico"]
        if enhanced_dict.get("datum_dokumentu") and not fields.get("datum_dokumentu"):
            fields["datum_dokumentu"] = enhanced_dict["datum_dokumentu"]
        if enhanced_dict.get("datum_splatnosti") and not fields.get("datum_splatnosti"):
            fields["datum_splatnosti"] = enhanced_dict["datum_splatnosti"]
        if enhanced_dict.get("kategorie"):
            fields["kategorie"] = enhanced_dict["kategorie"]

        # Build result
        result = {
            "email_id": email_id,
            "email_folder": str(email_folder),
            "doc_type": doc_type,
            "doc_subtype": enhanced_dict.get("doc_subtype"),
            "direction": enhanced_dict.get("direction"),
            "confidence": confidence,
            "enhanced_confidence": enhanced.confidence,
            "phase": 1,
            "method": "docling+enhanced",
            "metadata": email_result["metadata"],
            "fields": fields,
            "text_length": len(all_text),
            "pdf_count": len(pdf_files),
            "timestamp": datetime.now().isoformat(),
            "content_hash": hashlib.md5(all_text.encode()).hexdigest()
        }

        # Save result
        self._save_result(email_id, result)
        return True

    def run(self):
        """Main processing loop"""
        self.stats["start_time"] = datetime.now().isoformat()

        self.logger.info("=" * 70)
        self.logger.info(f"PHASE 1: DOCLING EXTRACTION - Instance {self.instance_id}")
        self.logger.info(f"Machine: {self.config.name}")
        self.logger.info(f"Range: {self.start_idx} - {self.end_idx}")
        self.logger.info("=" * 70)

        email_folders = self._get_email_folders()
        self.stats["total"] = len(email_folders)

        self.logger.info(f"Found {len(email_folders)} emails to process")

        # Setup progress bar
        if HAS_TQDM:
            pbar = tqdm(email_folders, desc=f"[Inst{self.instance_id}] Phase1", unit="email",
                        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
        else:
            pbar = email_folders

        for idx, email_folder in enumerate(pbar):
            # Resource check
            while not self._check_resources():
                time.sleep(5)

            # Progress update
            if HAS_TQDM:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                success_rate = (self.stats["success"] / max(1, self.stats["processed"])) * 100
                pbar.set_postfix({
                    "✓": self.stats["success"],
                    "✗": self.stats["failed"],
                    "CPU": f"{cpu:.0f}%",
                    "RAM": f"{ram:.0f}%"
                })
            elif idx % 100 == 0:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                success_rate = (self.stats["success"] / max(1, self.stats["processed"])) * 100
                self.logger.info(
                    f"Progress: {idx}/{len(email_folders)} | "
                    f"Success: {self.stats['success']} ({success_rate:.0f}%) | "
                    f"CPU: {cpu:.0f}% | RAM: {ram:.0f}%"
                )

            # Process email
            try:
                success = self.process_email(email_folder)
                self.stats["processed"] += 1

                if success:
                    self.logger.debug(f"[{idx}] OK - {email_folder.name[:50]}")

            except Exception as e:
                self.logger.error(f"[{idx}] Exception: {e}")
                self._log_failed(email_folder.name, f"Exception: {e}")

        # Finalize
        self.stats["end_time"] = datetime.now().isoformat()
        self._save_stats()
        self._print_summary()

    def _save_stats(self):
        """Save statistics"""
        stats_file = self.output_dir / f"phase1_stats_{self.instance_id}.json"

        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Stats saved: {stats_file}")

    def _print_summary(self):
        """Print final summary"""
        self.logger.info("=" * 70)
        self.logger.info("PHASE 1 COMPLETE - SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"Total: {self.stats['total']}")
        self.logger.info(f"Processed: {self.stats['processed']}")
        self.logger.info(f"Success: {self.stats['success']}")
        self.logger.info(f"Failed: {self.stats['failed']}")
        self.logger.info(f"Success rate: {(self.stats['success']/max(1,self.stats['total']))*100:.1f}%")
        self.logger.info(f"ISDOC generated: {self.stats.get('isdoc_generated', 0)}")
        self.logger.info("-" * 70)
        self.logger.info("By document type:")
        for doc_type, count in sorted(self.stats["by_type"].items(), key=lambda x: -x[1]):
            self.logger.info(f"  {doc_type}: {count}")
        self.logger.info("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Phase 1: Docling Extraction')
    parser.add_argument('--machine', default='mac_mini', choices=MACHINES.keys(),
                        help='Machine configuration')
    parser.add_argument('--instance', type=int, default=0,
                        help='Instance ID (0-based)')
    parser.add_argument('--start', type=int, required=True,
                        help='Start email index')
    parser.add_argument('--end', type=int, required=True,
                        help='End email index')
    parser.add_argument('--email-dir', type=str, default=str(EMAIL_DIR),
                        help='Email directory')
    parser.add_argument('--output-dir', type=str, default=str(OUTPUT_DIR),
                        help='Output directory')

    args = parser.parse_args()

    config = MACHINES[args.machine]
    email_dir = Path(args.email_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = Phase1Processor(
        instance_id=args.instance,
        email_dir=email_dir,
        output_dir=output_dir,
        start_idx=args.start,
        end_idx=args.end,
        machine_config=config
    )

    processor.run()


if __name__ == "__main__":
    main()
