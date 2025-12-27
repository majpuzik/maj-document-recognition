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
Phase 2 MacBook - LLM klasifikace od KONCE seznamu
Běží paralelně s DGX (který jede od začátku)
"""

import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import ollama

# Progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Paths
ACASIS_ROOT = Path("/Volumes/ACASIS")
BASE_DIR = ACASIS_ROOT / "apps/maj-document-recognition/phase1_output"
EMAIL_DIR = ACASIS_ROOT / "parallel_scan_1124_1205/thunderbird-emails"
INPUT_FILE = BASE_DIR / "phase2_to_process.jsonl"
RESULTS_DIR = BASE_DIR / "phase2_results"
FAILED_FILE = BASE_DIR / "phase2_failed_macbook.jsonl"
LOG_FILE = BASE_DIR / "phase2_macbook.log"
STATS_FILE = BASE_DIR / "phase2_macbook_stats.json"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [P2-MAC] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Model
MODEL = "qwen2.5:32b"

# 31 custom fields
CUSTOM_FIELDS = [
    "doc_typ", "protistrana_nazev", "protistrana_ico", "protistrana_typ",
    "castka_celkem", "datum_dokumentu", "cislo_dokumentu", "mena",
    "stav_platby", "datum_splatnosti", "kategorie", "email_from",
    "email_to", "email_subject", "od_osoba", "od_osoba_role", "od_firma",
    "pro_osoba", "pro_osoba_role", "pro_firma", "predmet", "ai_summary",
    "ai_keywords", "ai_popis", "typ_sluzby", "nazev_sluzby", "predmet_typ",
    "predmet_nazev", "polozky_text", "polozky_json", "perioda"
]

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
    subject = meta.get("subject", meta.get("email_subject", "")).lower()
    from_addr = meta.get("from", meta.get("email_from", "")).lower()
    summary = extracted.get("ai_summary", "").lower()
    keywords_data = extracted.get("ai_keywords", "")
    keywords = keywords_data if isinstance(keywords_data, str) else " ".join(keywords_data) if keywords_data else ""
    keywords = keywords.lower()

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


CLASSIFICATION_PROMPT = """Analyzuj tento email/dokument a extrahuj informace.

DOKUMENT:
{text}

Odpověz POUZE validním JSON objektem s těmito poli:
{{
  "doc_typ": "faktura|smlouva|objednavka|dodaci_list|uctenka|vypis|potvrzeni|reklamace|nabidka|poptavka|newsletter|reklama|spam|system_notification|it_notes|other",
  "protistrana_nazev": "název firmy/osoby nebo null",
  "protistrana_ico": "IČO nebo null",
  "castka_celkem": číslo nebo null,
  "datum_dokumentu": "YYYY-MM-DD nebo null",
  "cislo_dokumentu": "číslo dokumentu nebo null",
  "mena": "CZK|EUR|USD nebo null",
  "ai_summary": "krátký souhrn max 100 znaků",
  "ai_keywords": ["klíčové", "slova"],
  "kategorie": "finance|smlouvy|komunikace|marketing|it|software|hardware|other"
}}

PRAVIDLA PRO KLASIFIKACI:
- it_notes = poznámky o IT/software/hardware (Windows, Linux, Xorg, produktové klíče, servery, Docker)
- system_notification = automatické notifikace (Loxone, NAS, monitoring, backup)
- marketing = reklama, newslettery

POUZE JSON, žádný další text!"""


def get_processed_ids() -> set:
    """Get already processed email IDs"""
    processed = set()
    for f in RESULTS_DIR.glob("*.json"):
        processed.add(f.stem)
    return processed


def load_failed_to_process() -> list:
    """Load emails to process, REVERSED order"""
    emails = []
    with open(INPUT_FILE, 'r') as f:
        for line in f:
            if line.strip():
                emails.append(json.loads(line))
    # Reverse - MacBook processes from end
    return list(reversed(emails))


def classify_with_llm(text: str) -> dict:
    """Classify using qwen2.5:32b"""
    prompt = CLASSIFICATION_PROMPT.format(text=text[:8000])

    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1}
    )

    content = response['message']['content']

    # Extract JSON
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        return json.loads(json_match.group())

    raise ValueError(f"No JSON in response: {content[:200]}")


def get_email_body(email_id: str) -> str:
    """Try to find email body from original folder"""
    # Search in thunderbird-emails directory
    for mailbox in EMAIL_DIR.iterdir():
        if mailbox.is_dir():
            for folder in mailbox.iterdir():
                if folder.is_dir() and email_id in folder.name:
                    eml_path = folder / "message.eml"
                    if eml_path.exists():
                        try:
                            import email
                            from email import policy
                            with open(eml_path, 'rb') as f:
                                msg = email.message_from_binary_file(f, policy=policy.default)

                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    ct = part.get_content_type()
                                    if ct == 'text/plain':
                                        body = part.get_content()
                                        break
                                    elif ct == 'text/html' and not body:
                                        body = part.get_content()
                            else:
                                body = msg.get_content()

                            return body if body else ""
                        except:
                            pass
    return ""


def process_email(email_data: dict) -> dict:
    """Process single email"""
    email_id = email_data.get('email_id', 'unknown')
    meta = email_data.get('metadata', {})

    # Pre-classify system notifications (skip LLM - much faster!)
    if is_system_notification(meta):
        return {
            "email_id": email_id,
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
            "timestamp": datetime.now().isoformat(),
            "metadata": meta
        }

    # Try to get body
    text = get_email_body(email_id)

    # Fallback: use metadata (like DGX does)
    if not text:
        text = f"Předmět: {meta.get('subject', '')}. Od: {meta.get('from', '')}"

    if not text or len(text) < 3:
        # Last resort - use email_id itself
        text = f"Email: {email_id}"

    # Classify
    extracted = classify_with_llm(text)
    doc_type = extracted.get("doc_typ", "other")

    # Force classify "other" - no unclassified emails allowed
    if doc_type == "other":
        doc_type = force_classify_other(extracted, meta)
        extracted["doc_typ"] = doc_type
        extracted["force_classified"] = True

    # Build result (same format as DGX)
    result = {
        "email_id": email_id,
        "doc_type": doc_type,
        "extracted_fields": extracted,
        "source": "phase2_macbook",
        "timestamp": datetime.now().isoformat(),
        "metadata": meta
    }

    return result


def safe_filename(email_id: str) -> str:
    """Create safe filename from email_id"""
    return re.sub(r'[^\w\-_.]', '_', email_id)[:200]


def main():
    logger.info(f"=== Phase 2 MacBook Started (from END) ===")
    logger.info(f"Model: {MODEL}")

    # Load data
    emails = load_failed_to_process()
    processed = get_processed_ids()

    logger.info(f"Total failed: {len(emails)}")
    logger.info(f"Already processed: {len(processed)}")

    # Filter already done
    to_process = [e for e in emails if safe_filename(e.get('email_id', '')) not in processed]
    logger.info(f"To process: {len(to_process)}")

    stats = {
        "started": datetime.now().isoformat(),
        "total": len(to_process),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "by_type": {}
    }

    # Setup progress bar
    if HAS_TQDM:
        pbar = tqdm(to_process, desc="Phase2 MacBook", unit="email",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
    else:
        pbar = to_process

    for i, email_data in enumerate(pbar, 1):
        email_id = email_data.get('email_id', 'unknown')
        safe_id = safe_filename(email_id)

        # Skip if already processed (by DGX)
        result_path = RESULTS_DIR / f"{safe_id}.json"
        if result_path.exists():
            stats['skipped'] += 1
            if HAS_TQDM:
                pbar.set_postfix({"✓": stats['success'], "✗": stats['failed'], "skip": stats['skipped']})
            else:
                logger.info(f"[{i}/{len(to_process)}] Skip (done): {email_id[:50]}...")
            continue

        try:
            result = process_email(email_data)

            # Save result
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            doc_type = result.get('doc_typ', 'unknown')
            stats['success'] += 1
            stats['by_type'][doc_type] = stats['by_type'].get(doc_type, 0) + 1

            if HAS_TQDM:
                pbar.set_postfix({"✓": stats['success'], "✗": stats['failed'], "type": doc_type[:8]})
            else:
                logger.info(f"[{i}/{len(to_process)}] ✓ {doc_type}: {email_id[:50]}...")

        except Exception as e:
            stats['failed'] += 1
            if HAS_TQDM:
                pbar.set_postfix({"✓": stats['success'], "✗": stats['failed']})
            else:
                logger.error(f"[{i}/{len(to_process)}] ✗ {email_id[:50]}: {e}")

            # Log failure
            with open(FAILED_FILE, 'a') as f:
                f.write(json.dumps({
                    "email_id": email_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }) + "\n")

        # Save stats periodically
        if i % 10 == 0:
            stats['last_update'] = datetime.now().isoformat()
            with open(STATS_FILE, 'w') as f:
                json.dump(stats, f, indent=2)

    # Final stats
    stats['completed'] = datetime.now().isoformat()
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

    logger.info(f"=== Phase 2 MacBook Complete ===")
    logger.info(f"Success: {stats['success']}, Failed: {stats['failed']}")


if __name__ == "__main__":
    main()
