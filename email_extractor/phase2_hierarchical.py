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
Phase 2: Hierarchical AI processing for failed extractions
===========================================================
Uses AIVoter hierarchical mode:
  1. czech-finance-speed (7.6B) - rychlý CZ specialist
  2. qwen2.5:14b - validace
  3. qwen2.5:32b - arbitr pokud 1+2 nesouhlasí

Author: Claude Code
Date: 2025-12-16
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import email
from email import policy
import logging

# Progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_consensus_trainer import AIVoter

# ISDOC integration
try:
    from isdoc_generator import generate_isdoc_for_result, should_generate_isdoc
except ImportError:
    from email_extractor.isdoc_generator import generate_isdoc_for_result, should_generate_isdoc

# Paths - auto-detect based on system
if Path("/home/puzik/mnt/acasis").exists():
    # DGX with SSHFS mount
    ACASIS_ROOT = Path("/home/puzik/mnt/acasis")
else:
    # Mac with direct mount
    ACASIS_ROOT = Path("/Volumes/ACASIS")

BASE_DIR = ACASIS_ROOT / "apps/maj-document-recognition/phase1_output"
EMAIL_DIR = ACASIS_ROOT / "parallel_scan_1124_1205/thunderbird-emails"
INPUT_FILE = BASE_DIR / "phase2_to_process.jsonl"
RESULTS_DIR = BASE_DIR / "phase2_results"
FAILED_FILE = BASE_DIR / "phase2_failed.jsonl"
LOG_FILE = BASE_DIR / "phase2_hierarchical.log"

# 31 Custom Fields
FIELD_NAMES = [
    "doc_typ", "protistrana_nazev", "protistrana_ico", "protistrana_typ",
    "castka_celkem", "datum_dokumentu", "cislo_dokumentu", "mena",
    "stav_platby", "datum_splatnosti", "kategorie", "email_from",
    "email_to", "email_subject", "od_osoba", "od_osoba_role",
    "od_firma", "pro_osoba", "pro_osoba_role", "pro_firma",
    "predmet", "ai_summary", "ai_keywords", "ai_popis",
    "typ_sluzby", "nazev_sluzby", "predmet_typ", "predmet_nazev",
    "polozky_text", "polozky_json", "perioda"
]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """Analyzuj tento email a extrahuj strukturované informace.

EMAIL:
Od: {from_addr}
Komu: {to_addr}
Předmět: {subject}
Datum: {date}

OBSAH:
{body}

Odpověz POUZE validním JSON (bez markdown) s těmito poli:
{{
  "doc_typ": "invoice|order|contract|marketing|correspondence|receipt|bank_statement|other",
  "protistrana_nazev": "název firmy/odesílatele",
  "protistrana_ico": "IČO pokud je uvedeno",
  "protistrana_typ": "firma|osvc|fo",
  "castka_celkem": 0.0,
  "datum_dokumentu": "YYYY-MM-DD",
  "cislo_dokumentu": "číslo dokumentu",
  "mena": "CZK|EUR|USD",
  "stav_platby": "zaplaceno|nezaplaceno|castecne|neznamy",
  "datum_splatnosti": "YYYY-MM-DD",
  "kategorie": "energie|telekomunikace|nakupy|cestovani|smlouvy|korespondence|reklama|jine",
  "od_osoba": "jméno odesílatele",
  "od_osoba_role": "role/pozice",
  "od_firma": "firma odesílatele",
  "pro_osoba": "jméno příjemce",
  "pro_osoba_role": "role příjemce",
  "pro_firma": "firma příjemce",
  "predmet": "stručný popis o čem dokument je",
  "ai_summary": "AI souhrn max 100 slov",
  "ai_keywords": "klíčová slova oddělená čárkou",
  "ai_popis": "podrobnější AI popis obsahu",
  "typ_sluzby": "typ služby pokud je",
  "nazev_sluzby": "název služby",
  "predmet_typ": "typ předmětu",
  "predmet_nazev": "název předmětu",
  "polozky_text": "položky jako text",
  "perioda": "období dokumentu"
}}
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
                        return body[:4000]
    return ""


def process_with_ai_voter(voter: AIVoter, email_data: dict, body: str) -> dict:
    """Process email with hierarchical AIVoter"""
    meta = email_data.get("metadata", {})

    # Build prompt
    prompt = CLASSIFY_PROMPT.format(
        from_addr=meta.get("from", ""),
        to_addr=meta.get("to", ""),
        subject=meta.get("subject", ""),
        date=meta.get("date", ""),
        body=body[:3000]
    )

    try:
        # Use AIVoter hierarchical mode
        consensus, details = voter.vote(prompt, "correspondence")

        if "error" not in consensus:
            result = {
                "email_id": email_data["email_id"],
                "doc_type": consensus.get("doc_typ", "other"),
                "extracted_fields": {},
                "source": "phase2_hierarchical",
                "ai_details": {
                    "models_used": details.get("models_used", []),
                    "escalated_to_32b": details.get("escalated_to_32b", False),
                    "consensus_level": details.get("consensus_level", "")
                },
                "timestamp": datetime.now().isoformat()
            }

            # Map all 31 fields
            for field in FIELD_NAMES:
                if field in consensus:
                    result["extracted_fields"][field] = consensus[field]

            # Add email metadata
            result["extracted_fields"]["email_from"] = meta.get("from", "")
            result["extracted_fields"]["email_to"] = meta.get("to", "")
            result["extracted_fields"]["email_subject"] = meta.get("subject", "")
            result["extracted_fields"]["datum_dokumentu"] = meta.get("date", "")

            return result

    except Exception as e:
        logger.error(f"AIVoter error: {e}")

    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0, help="Start from position")
    parser.add_argument("--limit", type=int, default=0, help="Process only N documents")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load emails to process
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE) as f:
        emails = [json.loads(line) for line in f if line.strip()]

    total = len(emails)
    logger.info(f"Phase 2 Hierarchical: {total} emails to process")
    logger.info(f"  Models: czech-finance-speed (7.6B) → qwen2.5:14b → qwen2.5:32b")

    # Initialize AIVoter with hierarchical mode
    voter = AIVoter(use_external_apis=False, hierarchical=True)
    logger.info(f"  Initialized: {len(voter.models)} models")

    # Skip to start position
    if args.start > 0:
        emails = emails[args.start:]
        logger.info(f"  Starting from position {args.start}")

    # Limit if specified
    if args.limit > 0:
        emails = emails[:args.limit]
        logger.info(f"  Processing {len(emails)} documents")

    success = 0
    failed = 0
    escalated = 0

    # Setup progress bar
    if HAS_TQDM:
        pbar = tqdm(emails, desc="Phase2 Hierarchical", unit="email",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
    else:
        pbar = emails

    for i, record in enumerate(pbar):
        email_id = record["email_id"]
        pos = args.start + i + 1

        if not HAS_TQDM:
            logger.info(f"[{pos}/{total}] {email_id[:50]}...")

        # Get email body
        body = get_email_body(email_id)
        if not body:
            meta = record.get("metadata", {})
            body = f"Předmět: {meta.get('subject', '')}. Od: {meta.get('from', '')}"

        # Process with AIVoter
        result = process_with_ai_voter(voter, record, body)

        if result:
            # Save result
            result_path = RESULTS_DIR / f"{email_id}.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            success += 1
            if result.get("ai_details", {}).get("escalated_to_32b"):
                escalated += 1
                if HAS_TQDM:
                    pbar.set_postfix({"✓": success, "✗": failed, "↗32B": escalated, "type": result['doc_type'][:8]})
                else:
                    logger.info(f"  ✓ {result['doc_type']} (32B arbitr)")
            else:
                if HAS_TQDM:
                    pbar.set_postfix({"✓": success, "✗": failed, "↗32B": escalated, "type": result['doc_type'][:8]})
                else:
                    logger.info(f"  ✓ {result['doc_type']} (bez 32B)")

            # Generate ISDOC for accounting documents
            doc_type = result.get("doc_type", "other")
            if should_generate_isdoc(doc_type):
                try:
                    isdoc_input = {
                        "email_id": email_id,
                        "doc_type": doc_type,
                        "extracted_fields": result.get("extracted_fields", {}),
                        "text_content": body[:2000] if body else ""
                    }
                    ok, isdoc_path = generate_isdoc_for_result(isdoc_input)
                    if ok:
                        result["isdoc_path"] = isdoc_path
                        logger.info(f"  📋 ISDOC: {Path(isdoc_path).name}")
                except Exception as e:
                    logger.warning(f"  ⚠ ISDOC failed: {e}")
        else:
            failed += 1
            # Log failure
            with open(FAILED_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "email_id": email_id,
                    "reason": "AIVoter failed",
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False) + "\n")
            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed, "↗32B": escalated})
            else:
                logger.info(f"  ✗ Failed")

    logger.info(f"\nPhase 2 Hierarchical Complete:")
    logger.info(f"  ✓ Success: {success}")
    logger.info(f"  ✗ Failed: {failed}")
    logger.info(f"  ↗ Escalated to 32B: {escalated}")


if __name__ == "__main__":
    main()
