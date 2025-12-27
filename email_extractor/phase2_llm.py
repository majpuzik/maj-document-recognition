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

"""Phase 2: LLM analysis for failed extractions - MULTI-MACHINE VERSION

Multi-machine support:
- Auto-detects hostname (spark* = DGX, macbook = MacBook, default = Mac Mini)
- File-based atomic locking prevents duplicate processing
- Skips already processed emails
- Progress bar with tqdm

Usage:
    python3 phase2_llm.py              # Run with defaults
    python3 phase2_llm.py --workers 2  # Run 2 parallel workers
"""
import json
import os
import sys
import socket
import time
import fcntl
import argparse
from datetime import datetime
from pathlib import Path
import email
from email import policy
import requests

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Note: Install tqdm for progress bar: pip install tqdm")

# Detect machine and set paths
HOSTNAME = socket.gethostname().lower()

if "dgx" in HOSTNAME or "puzik" in HOSTNAME or "spark" in HOSTNAME:
    # DGX paths
    BASE_DIR = Path("/home/puzik/mnt/acasis/apps/maj-document-recognition/phase1_output")
    EMAIL_DIR = Path("/home/puzik/mnt/acasis/parallel_scan_1124_1205/thunderbird-emails")
    OLLAMA_URL = "http://localhost:11434/api/generate"
elif "macbook" in HOSTNAME or "mbp" in HOSTNAME.lower():
    # MacBook paths
    BASE_DIR = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output")
    EMAIL_DIR = Path("/Volumes/ACASIS/parallel_scan_1124_1205/thunderbird-emails")
    OLLAMA_URL = "http://localhost:11434/api/generate"
else:
    # Default (Mac Mini or other)
    BASE_DIR = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output")
    EMAIL_DIR = Path("/Volumes/ACASIS/parallel_scan_1124_1205/thunderbird-emails")
    OLLAMA_URL = "http://localhost:11434/api/generate"

RESULTS_DIR = BASE_DIR / "phase2_results"
INPUT_FILE = BASE_DIR / "phase2_to_process.jsonl"
LOCK_DIR = BASE_DIR / "phase2_locks"
FAILED_FILE = BASE_DIR / "phase2_failed.jsonl"

# Model config
MODEL = "qwen2.5:32b"

PROMPT_TEMPLATE = """Analyzuj tento email a extrahuj informace.

Email:
Od: {from_addr}
Komu: {to_addr}
Předmět: {subject}
Datum: {date}

Obsah:
{body}

Odpověz POUZE validním JSON (bez markdown):
{{
  "doc_typ": "invoice|order|contract|marketing|correspondence|other",
  "protistrana_nazev": "název odesílatele/firmy",
  "protistrana_ico": "IČO pokud je v textu, jinak null",
  "predmet": "o čem email je",
  "ai_summary": "krátký souhrn (max 100 slov)",
  "kategorie": "kategorie dokumentu",
  "direction": "příjem|výdaj|neutrální",
  "castka_celkem": číslo nebo null
}}"""


def setup_dirs():
    """Create necessary directories"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)


def is_already_processed(email_id: str) -> bool:
    """Check if email was already processed"""
    # Check in phase2_results
    if (RESULTS_DIR / f"{email_id}.json").exists():
        return True
    # Also check in phase1_results (might have been processed there)
    phase1_results = BASE_DIR / "phase1_results"
    if (phase1_results / f"{email_id}.json").exists():
        return True
    return False


def try_claim(email_id: str) -> bool:
    """Try to claim an email for processing using file lock"""
    lock_file = LOCK_DIR / f"{email_id}.lock"
    try:
        # Create lock file atomically
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{HOSTNAME}:{datetime.now().isoformat()}".encode())
        os.close(fd)
        return True
    except FileExistsError:
        # Check if lock is stale (older than 10 minutes)
        try:
            mtime = lock_file.stat().st_mtime
            if time.time() - mtime > 600:  # 10 minutes
                lock_file.unlink()
                return try_claim(email_id)  # Retry
        except:
            pass
        return False
    except Exception as e:
        print(f"  Lock error: {e}")
        return False


def release_claim(email_id: str):
    """Release claim on email"""
    lock_file = LOCK_DIR / f"{email_id}.lock"
    try:
        lock_file.unlink()
    except:
        pass


def get_email_body(email_id: str) -> str:
    """Find and read email body"""
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
                            return str(body)[:4000]
                    except Exception as e:
                        print(f"  Email read error: {e}")
    return ""


def call_llm(prompt: str) -> dict:
    """Call Ollama LLM"""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 4096}
        }, timeout=180)

        if resp.status_code == 200:
            text = resp.json().get("response", "")
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
    except requests.exceptions.Timeout:
        print(f"  LLM timeout")
    except json.JSONDecodeError:
        print(f"  Invalid JSON response")
    except Exception as e:
        print(f"  LLM error: {e}")
    return {}


def save_failed(email_id: str, error: str, metadata: dict):
    """Log failed email"""
    with open(FAILED_FILE, "a") as f:
        f.write(json.dumps({
            "email_id": email_id,
            "error": error,
            "metadata": metadata,
            "machine": HOSTNAME,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Phase 2 LLM Processing")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers (future)")
    args = parser.parse_args()

    setup_dirs()

    if not INPUT_FILE.exists():
        print(f"No input file: {INPUT_FILE}")
        return

    # Load emails to process
    with open(INPUT_FILE) as f:
        emails = [json.loads(line) for line in f if line.strip()]

    print(f"[{HOSTNAME}] Phase 2: {len(emails)} emails, model={MODEL}", flush=True)
    print(f"Results: {RESULTS_DIR}", flush=True)

    success = 0
    failed = 0
    skipped = 0

    # Setup progress bar
    if HAS_TQDM:
        pbar = tqdm(emails, desc=f"[{HOSTNAME[:10]}] Phase2", unit="email",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
    else:
        pbar = emails

    for i, record in enumerate(pbar):
        email_id = record["email_id"]
        meta = record.get("metadata", {})

        # Skip already processed
        if is_already_processed(email_id):
            skipped += 1
            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed, "skip": skipped})
            continue

        # Try to claim
        if not try_claim(email_id):
            skipped += 1
            if HAS_TQDM:
                pbar.set_postfix({"✓": success, "✗": failed, "skip": skipped})
            continue

        try:
            if not HAS_TQDM:
                print(f"[{i+1}/{len(emails)}] {email_id[:50]}...", flush=True)

            # Get email body
            body = get_email_body(email_id)
            if not body:
                body = f"Předmět: {meta.get('subject', '')}"

            # Build prompt
            prompt = PROMPT_TEMPLATE.format(
                from_addr=meta.get("from", ""),
                to_addr=meta.get("to", ""),
                subject=meta.get("subject", ""),
                date=meta.get("date", ""),
                body=body[:3000]
            )

            # Call LLM
            result = call_llm(prompt)

            if result:
                full_result = {
                    "email_id": email_id,
                    "doc_type": result.get("doc_typ", "other"),
                    "extracted_fields": {
                        "doc_typ": result.get("doc_typ", "other"),
                        "email_from": meta.get("from", ""),
                        "email_to": meta.get("to", ""),
                        "email_subject": meta.get("subject", ""),
                        "datum_dokumentu": meta.get("date", ""),
                        "protistrana_nazev": result.get("protistrana_nazev", ""),
                        "protistrana_ico": result.get("protistrana_ico"),
                        "predmet": result.get("predmet", ""),
                        "ai_summary": result.get("ai_summary", ""),
                        "kategorie": result.get("kategorie", ""),
                        "direction": result.get("direction", "neutrální"),
                        "castka_celkem": result.get("castka_celkem")
                    },
                    "source": f"phase2_llm_{HOSTNAME}",
                    "method": "qwen2.5:32b",
                    "timestamp": datetime.now().isoformat()
                }

                result_path = RESULTS_DIR / f"{email_id}.json"
                with open(result_path, "w") as f:
                    json.dump(full_result, f, ensure_ascii=False, indent=2)

                success += 1
                if HAS_TQDM:
                    pbar.set_postfix({"✓": success, "✗": failed, "skip": skipped, "type": result.get("doc_typ", "?")[:8]})
                else:
                    print(f"  ✓ {result.get('doc_typ', 'other')}", flush=True)
            else:
                failed += 1
                save_failed(email_id, "LLM returned empty", meta)
                if HAS_TQDM:
                    pbar.set_postfix({"✓": success, "✗": failed, "skip": skipped})
                else:
                    print(f"  ✗ Failed", flush=True)

        finally:
            release_claim(email_id)

    if HAS_TQDM:
        pbar.close()

    print(f"\n[{HOSTNAME}] Phase 2 complete: {success} success, {failed} failed, {skipped} skipped")


if __name__ == "__main__":
    main()
