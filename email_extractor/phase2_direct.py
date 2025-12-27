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
Phase 2: Direct qwen2.5:32b processing for failed extractions
=============================================================
Bypasses hierarchical voting, uses 32B directly.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import email
from email import policy
import logging
import re

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Invoice line items extractor (v1.1 - item_type, is_isdoc)
try:
    from src.ocr.data_extractors import InvoiceExtractor
    INVOICE_EXTRACTOR = InvoiceExtractor()
    INVOICE_EXTRACTOR_AVAILABLE = True
except ImportError:
    INVOICE_EXTRACTOR_AVAILABLE = False

# Document types that need invoice line extraction
INVOICE_TYPES = {"invoice", "receipt", "tax_document", "faktura", "uctenka", "danovy_doklad"}

# Auto-detect mount point
if Path("/home/puzik/mnt/acasis").exists():
    ACASIS_ROOT = Path("/home/puzik/mnt/acasis")
else:
    ACASIS_ROOT = Path("/Volumes/ACASIS")

BASE_DIR = ACASIS_ROOT / "apps/maj-document-recognition/phase1_output"
EMAIL_DIR = ACASIS_ROOT / "parallel_scan_1124_1205/thunderbird-emails"
INPUT_FILE = BASE_DIR / "phase2_to_process.jsonl"
RESULTS_DIR = BASE_DIR / "phase2_results"
FAILED_FILE = BASE_DIR / "phase2_failed.jsonl"
LOG_FILE = BASE_DIR / "phase2_direct.log"
STATS_FILE = BASE_DIR / "phase2_stats.json"

# ISDOC dir
ISDOC_DIR = BASE_DIR / "isdoc_xml"

# Setup logging
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
ISDOC_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [P2] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Try to import ollama
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama not available")

# System notification patterns
SYSTEM_NOTIFICATION_PATTERNS = {
    "from": [
        r"noreply@.*loxone",
        r"no-reply@",
        r"noreply@",
        r"donotreply@",
        r"notification@",
        r"alert@",
        r"system@",
        r"automat.*@",
        r"robot@",
        r"synology",
        r"diskstation",
    ],
    "subject": [
        r"^statistic",
        r"^alert:",
        r"^notification:",
        r"automatick[áé]",
        r"systémov[áé]",
        r"loxone",
        r"miniserver",
        r"^\[192\.168\.",  # IP address notifications (Synology, etc.)
    ]
}


def is_system_notification(metadata: dict) -> bool:
    """Check if email is a system notification"""
    from_addr = metadata.get("from", "").lower()
    subject = metadata.get("subject", "").lower()

    for pattern in SYSTEM_NOTIFICATION_PATTERNS["from"]:
        if re.search(pattern, from_addr, re.IGNORECASE):
            return True

    for pattern in SYSTEM_NOTIFICATION_PATTERNS["subject"]:
        if re.search(pattern, subject, re.IGNORECASE):
            return True

    return False


# Force classification keywords - NO "other" allowed
FORCE_CLASSIFY_KEYWORDS = {
    "it_notes": [
        "api", "key", "server", "docker", "linux", "windows", "hp", "ws",
        "workstation", "gemini", "claude", "ollama", "python", "git", "ssh",
        "backup", "nas", "disk", "storage", "config", "setup", "install",
        "xorg", "x11", "ubuntu", "debian", "macos", "terminal", "bash",
        "license", "licence", "product key", "activation", "vm", "virtual"
    ],
    "project_notes": [
        "katalog", "homepage", "web", "projekt", "airport", "tyrane",
        "design", "layout", "draft", "mockup", "wireframe", "prototype"
    ],
    "correspondence": [
        "schránka", "datová", "zpráva", "odpověď", "dotaz", "info", "fyi",
        "dobrý den", "zdravím", "děkuji", "prosím", "s pozdravem"
    ],
    "marketing": [
        "sleva", "akce", "nabídka", "newsletter", "odhlásit", "unsubscribe",
        "promo", "discount", "sale", "offer"
    ]
}


def force_classify_other(extracted: dict, meta: dict) -> str:
    """Force classify 'other' to a real category - 'other' is not allowed"""
    subject = meta.get("subject", "").lower()
    from_addr = meta.get("from", "").lower()
    summary = extracted.get("ai_summary", "").lower()
    keywords = extracted.get("ai_keywords", "").lower()

    all_text = f"{subject} {summary} {keywords}"

    # Check each category's keywords
    for category, kw_list in FORCE_CLASSIFY_KEYWORDS.items():
        for kw in kw_list:
            if kw in all_text:
                return category

    # Photo/image references -> project_notes
    if any(x in all_text for x in ["obrázk", "foto", "image", "screenshot", "snímek"]):
        return "project_notes"

    # Personal email domains -> correspondence
    personal_domains = ["@gmail", "@seznam", "@email", "@outlook", "@hotmail", "@yahoo"]
    if any(domain in from_addr for domain in personal_domains):
        return "correspondence"

    # Default fallback - correspondence (it's communication)
    return "correspondence"


CLASSIFY_PROMPT = """Analyzuj tento email a extrahuj strukturované informace.

EMAIL:
Od: {from_addr}
Komu: {to_addr}
Předmět: {subject}
Datum: {date}

OBSAH:
{body}

Odpověz POUZE validním JSON (bez markdown, bez ```json) s těmito poli:
{{
  "doc_typ": "invoice|order|contract|marketing|correspondence|receipt|bank_statement|system_notification|it_notes|other",
  "protistrana_nazev": "název firmy/odesílatele",
  "protistrana_ico": "IČO pokud je uvedeno",
  "castka_celkem": 0.0,
  "datum_dokumentu": "YYYY-MM-DD",
  "cislo_dokumentu": "číslo dokumentu",
  "mena": "CZK|EUR|USD",
  "kategorie": "energie|telekomunikace|nakupy|cestovani|smlouvy|korespondence|reklama|it|software|hardware|jine",
  "od_osoba": "jméno odesílatele",
  "od_firma": "firma odesílatele",
  "ai_summary": "AI souhrn max 50 slov",
  "ai_keywords": "klíčová slova oddělená čárkou"
}}

PRAVIDLA PRO KLASIFIKACI:
- it_notes = poznámky o IT/software/hardware (Windows, Linux, Xorg, produktové klíče, servery, Docker, atd.)
- system_notification = automatické notifikace ze systémů (Loxone, NAS, monitoring, backup hlášky)
- marketing = reklama, newslettery, promo akce
- correspondence = běžná komunikace s lidmi
"""


def get_email_body(email_id: str) -> str:
    """Find and read email body from Thunderbird folder"""
    for mailbox in EMAIL_DIR.iterdir():
        if not mailbox.is_dir():
            continue
        for folder in mailbox.iterdir():
            if email_id in folder.name:
                eml_path = folder / "message.eml"
                if eml_path.exists():
                    try:
                        with open(eml_path, 'rb') as f:
                            msg = email.message_from_binary_file(f, policy=policy.default)
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_content()
                                        break
                                    elif part.get_content_type() == "text/html":
                                        body = part.get_content()
                            else:
                                body = msg.get_content()
                            return str(body)[:4000] if body else ""
                    except Exception:
                        pass
    return ""


def call_ollama_32b(prompt: str) -> dict:
    """Call qwen2.5:32b via ollama"""
    if not OLLAMA_AVAILABLE:
        return {}

    try:
        response = ollama.chat(
            model="qwen2.5:32b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_predict": 1000}
        )

        content = response.get("message", {}).get("content", "")

        # Clean up JSON response
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Try to parse JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON in response
            match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return {}

    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return {}


def process_email(email_data: dict, body: str) -> dict:
    """Process single email with 32B model"""
    meta = email_data.get("metadata", {})

    # Pre-classify system notifications (skip LLM)
    if is_system_notification(meta):
        return {
            "email_id": email_data["email_id"],
            "doc_type": "system_notification",
            "extracted_fields": {
                "doc_typ": "system_notification",
                "protistrana_nazev": meta.get("from", "").split("<")[0].strip(),
                "kategorie": "system",
                "ai_summary": f"Systémová notifikace: {meta.get('subject', '')}",
                "email_from": meta.get("from", ""),
                "email_to": meta.get("to", ""),
                "email_subject": meta.get("subject", ""),
            },
            "source": "phase2_pattern_match",
            "timestamp": datetime.now().isoformat()
        }

    prompt = CLASSIFY_PROMPT.format(
        from_addr=meta.get("from", ""),
        to_addr=meta.get("to", ""),
        subject=meta.get("subject", ""),
        date=meta.get("date", ""),
        body=body[:3000]
    )

    extracted = call_ollama_32b(prompt)

    if extracted and extracted.get("doc_typ"):
        doc_type = extracted.get("doc_typ", "other")

        # Force classify "other" - no unclassified emails allowed
        if doc_type == "other":
            doc_type = force_classify_other(extracted, meta)
            extracted["doc_typ"] = doc_type
            extracted["force_classified"] = True

        result = {
            "email_id": email_data["email_id"],
            "doc_type": doc_type,
            "extracted_fields": extracted,
            "source": "phase2_qwen32b",
            "timestamp": datetime.now().isoformat()
        }

        # Add email metadata
        result["extracted_fields"]["email_from"] = meta.get("from", "")
        result["extracted_fields"]["email_to"] = meta.get("to", "")
        result["extracted_fields"]["email_subject"] = meta.get("subject", "")

        # v1.1: Extract invoice line items with item_type and ISDOC detection
        if INVOICE_EXTRACTOR_AVAILABLE and doc_type.lower() in INVOICE_TYPES:
            try:
                invoice_data = INVOICE_EXTRACTOR.extract(body)
                if invoice_data:
                    # Add invoice_subject (from line items descriptions)
                    if invoice_data.get("subject"):
                        result["extracted_fields"]["invoice_subject"] = invoice_data["subject"]

                    # Add item_type (service/goods/mixed)
                    if invoice_data.get("item_type"):
                        result["extracted_fields"]["item_type"] = invoice_data["item_type"]

                    # Add ISDOC detection
                    isdoc = invoice_data.get("isdoc", {})
                    if isdoc.get("is_isdoc"):
                        result["extracted_fields"]["is_isdoc"] = True
                        result["extracted_fields"]["isdoc_version"] = isdoc.get("version", "")
                        result["extracted_fields"]["isdoc_uuid"] = isdoc.get("uuid", "")

                    # Add line items as JSON
                    if invoice_data.get("line_items"):
                        result["extracted_fields"]["polozky_json"] = json.dumps(
                            invoice_data["line_items"], ensure_ascii=False
                        )
            except Exception as e:
                logger.debug(f"Invoice extraction failed: {e}")

        return result

    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE) as f:
        emails = [json.loads(line) for line in f if line.strip()]

    total = len(emails)
    logger.info(f"=" * 60)
    logger.info(f"PHASE 2: DIRECT 32B PROCESSING")
    logger.info(f"Model: qwen2.5:32b")
    logger.info(f"Total: {total} emails")
    logger.info(f"=" * 60)

    if args.start > 0:
        emails = emails[args.start:]
    if args.limit > 0:
        emails = emails[:args.limit]

    success = 0
    failed = 0
    by_type = {}

    # Setup progress bar
    if HAS_TQDM:
        pbar = tqdm(emails, desc="Phase2 Direct", unit="email",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
    else:
        pbar = emails

    for i, record in enumerate(pbar):
        email_id = record["email_id"]
        pos = args.start + i + 1

        # Get email body
        body = get_email_body(email_id)
        if not body:
            meta = record.get("metadata", {})
            body = f"Předmět: {meta.get('subject', '')}. Od: {meta.get('from', '')}"

        # Process
        result = process_email(record, body)

        if result:
            # Save result
            safe_id = email_id.replace("/", "_")[:100]
            result_path = RESULTS_DIR / f"{safe_id}.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            success += 1
            doc_type = result["doc_type"]
            by_type[doc_type] = by_type.get(doc_type, 0) + 1

            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed, "type": doc_type[:8]})
            elif pos % 10 == 0 or pos <= 5:
                logger.info(f"[{pos}/{total}] ✓ {doc_type}: {email_id[:50]}...")
        else:
            failed += 1
            with open(FAILED_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "email_id": email_id,
                    "reason": "32B extraction failed",
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False) + "\n")

            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed})
            elif pos % 10 == 0 or pos <= 5:
                logger.info(f"[{pos}/{total}] ✗ {email_id[:50]}...")

        # Progress every 100 (only without tqdm)
        if not HAS_TQDM and pos % 100 == 0:
            logger.info(f"Progress: {pos}/{total} | Success: {success} ({100*success/pos:.0f}%) | Failed: {failed}")

    # Final stats
    logger.info(f"=" * 60)
    logger.info(f"PHASE 2 COMPLETE")
    logger.info(f"  Success: {success}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Rate: {100*success/(success+failed):.1f}%")
    logger.info(f"  By type: {by_type}")
    logger.info(f"=" * 60)

    # Save stats
    stats = {
        "total": total,
        "processed": success + failed,
        "success": success,
        "failed": failed,
        "by_type": by_type,
        "end_time": datetime.now().isoformat()
    }
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


if __name__ == "__main__":
    main()
