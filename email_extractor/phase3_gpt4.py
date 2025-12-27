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
Phase 3: GPT-4 Processing for Failed Documents
===============================================
Uses OpenAI GPT-4 API for documents that failed in Phase 2.
Last automatic attempt before manual review.

Input: phase2_failed.jsonl
Output: phase3_results/, phase3_failed.jsonl

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
import time

from openai import OpenAI

# Progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

# Paths
BASE_DIR = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output")
EMAIL_DIR = Path("/Volumes/ACASIS/parallel_scan_1124_1205/thunderbird-emails")
INPUT_FILE = BASE_DIR / "phase2_failed.jsonl"
RESULTS_DIR = BASE_DIR / "phase3_results"
FAILED_FILE = BASE_DIR / "phase3_failed.jsonl"
LOG_FILE = BASE_DIR / "phase3_gpt4.log"

# OpenAI config
MODEL = "gpt-4o"  # or "gpt-4-turbo" for cheaper option
MAX_TOKENS = 2000
TEMPERATURE = 0.1

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

SYSTEM_PROMPT = """Jsi expert na analýzu a klasifikaci dokumentů. Analyzuj email a extrahuj strukturované informace.

Odpověz POUZE validním JSON objektem s těmito poli:
{
  "doc_typ": "invoice|order|contract|marketing|correspondence|receipt|bank_statement|delivery_note|tax_document|other",
  "protistrana_nazev": "název firmy/odesílatele nebo null",
  "protistrana_ico": "IČO (8 číslic) nebo null",
  "protistrana_typ": "firma|osvc|fo|null",
  "castka_celkem": číslo nebo null,
  "datum_dokumentu": "YYYY-MM-DD nebo null",
  "cislo_dokumentu": "číslo dokumentu nebo null",
  "mena": "CZK|EUR|USD|null",
  "stav_platby": "zaplaceno|nezaplaceno|castecne|neznamy",
  "datum_splatnosti": "YYYY-MM-DD nebo null",
  "kategorie": "energie|telekomunikace|nakupy|cestovani|smlouvy|korespondence|reklama|finance|pojisteni|jine",
  "od_osoba": "jméno odesílatele nebo null",
  "od_osoba_role": "role/pozice nebo null",
  "od_firma": "firma odesílatele nebo null",
  "pro_osoba": "jméno příjemce nebo null",
  "pro_osoba_role": "role příjemce nebo null",
  "pro_firma": "firma příjemce nebo null",
  "predmet": "stručný popis o čem dokument je",
  "ai_summary": "souhrn max 100 slov",
  "ai_keywords": "klíčová slova oddělená čárkou",
  "ai_popis": "podrobnější popis obsahu",
  "typ_sluzby": "typ služby nebo null",
  "nazev_sluzby": "název služby nebo null",
  "predmet_typ": "typ předmětu nebo null",
  "predmet_nazev": "název předmětu nebo null",
  "polozky_text": "položky jako text nebo null",
  "perioda": "období dokumentu nebo null"
}

DŮLEŽITÉ:
- Odpověz POUZE JSON, žádný markdown, žádné vysvětlení
- Všechna pole musí být přítomna (použij null pokud nelze určit)
- Pro české dokumenty používej české hodnoty"""


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
                        return body[:6000]  # GPT-4 can handle more
    return ""


def process_with_gpt4(client: OpenAI, email_data: dict, body: str) -> dict:
    """Process email with GPT-4"""
    meta = email_data.get("metadata", {})

    user_content = f"""EMAIL:
Od: {meta.get("from", "")}
Komu: {meta.get("to", "")}
Předmět: {meta.get("subject", "")}
Datum: {meta.get("date", "")}

OBSAH:
{body[:5000]}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        # Build final result
        final_result = {
            "email_id": email_data["email_id"],
            "doc_type": result.get("doc_typ", "other"),
            "extracted_fields": {},
            "source": "phase3_gpt4",
            "model": MODEL,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            "timestamp": datetime.now().isoformat()
        }

        # Map all 31 fields
        for field in FIELD_NAMES:
            if field in result:
                final_result["extracted_fields"][field] = result[field]

        # Ensure email metadata is set
        final_result["extracted_fields"]["email_from"] = meta.get("from", "")
        final_result["extracted_fields"]["email_to"] = meta.get("to", "")
        final_result["extracted_fields"]["email_subject"] = meta.get("subject", "")

        return final_result

    except Exception as e:
        logger.error(f"GPT-4 error: {e}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0, help="Start from position")
    parser.add_argument("--limit", type=int, default=0, help="Process only N documents")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually call API")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-your"):
        logger.error("OPENAI_API_KEY not set or invalid")
        return

    # Initialize client
    client = OpenAI(api_key=api_key)

    # Load failed documents from Phase 2
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        logger.info("Phase 2 must complete first and generate phase2_failed.jsonl")
        return

    with open(INPUT_FILE) as f:
        emails = [json.loads(line) for line in f if line.strip()]

    total = len(emails)
    logger.info(f"Phase 3 GPT-4: {total} documents to process")
    logger.info(f"  Model: {MODEL}")

    if args.dry_run:
        logger.info("  DRY RUN - no API calls")

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
    total_tokens = 0

    # Setup progress bar
    if HAS_TQDM:
        pbar = tqdm(emails, desc="Phase3 GPT-4", unit="doc",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
    else:
        pbar = emails

    for i, record in enumerate(pbar):
        email_id = record.get("email_id", record.get("id", f"unknown_{i}"))
        pos = args.start + i + 1

        if not HAS_TQDM:
            logger.info(f"[{pos}/{total}] {email_id[:50]}...")

        if args.dry_run:
            if not HAS_TQDM:
                logger.info("  [DRY RUN] Skipped")
            continue

        # Get email body
        body = get_email_body(email_id)
        if not body:
            meta = record.get("metadata", {})
            body = f"Předmět: {meta.get('subject', '')}. Od: {meta.get('from', '')}"

        # Process with GPT-4
        result = process_with_gpt4(client, record, body)

        if result:
            # Save result
            result_path = RESULTS_DIR / f"{email_id}.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            success += 1
            tokens = result.get("usage", {}).get("total_tokens", 0)
            total_tokens += tokens
            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed, "tokens": total_tokens, "type": result['doc_type'][:8]})
            else:
                logger.info(f"  ✓ {result['doc_type']} ({tokens} tokens)")
        else:
            failed += 1
            # Log failure for Phase 4 (manual review)
            with open(FAILED_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "email_id": email_id,
                    "reason": "GPT-4 failed",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": record.get("metadata", {})
                }, ensure_ascii=False) + "\n")
            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed, "tokens": total_tokens})
            else:
                logger.info(f"  ✗ Failed")

        # Rate limiting - be gentle with API
        time.sleep(0.5)

    # Cost estimate (GPT-4o pricing: ~$5/1M input, ~$15/1M output)
    estimated_cost = (total_tokens / 1_000_000) * 10  # rough average

    logger.info(f"\nPhase 3 GPT-4 Complete:")
    logger.info(f"  ✓ Success: {success}")
    logger.info(f"  ✗ Failed: {failed} (→ Phase 4 manual review)")
    logger.info(f"  📊 Total tokens: {total_tokens:,}")
    logger.info(f"  💰 Estimated cost: ${estimated_cost:.2f}")


if __name__ == "__main__":
    main()
