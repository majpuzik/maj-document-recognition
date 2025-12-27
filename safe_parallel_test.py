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
SAFE parallel processing with resource monitoring
Max 3 workers to stay under 70% CPU/Memory
"""

import email
import logging
import mailbox
import sys
import psutil
import time
from datetime import datetime
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

sys.path.insert(0, str(Path(__file__).parent))

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier_improved import ImprovedAIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.blacklist_whitelist import BlacklistWhitelist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(processName)s] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/safe_parallel_test.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

def check_system_resources():
    """Check if system resources are within limits"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    mem_percent = memory.percent

    return {
        "cpu_percent": cpu_percent,
        "mem_percent": mem_percent,
        "cpu_ok": cpu_percent < 70,
        "mem_ok": mem_percent < 70,
        "safe": cpu_percent < 70 and mem_percent < 70
    }

def load_config():
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Use BEST model but with longer timeout
    config['ai']['ollama']['model'] = 'qwen2.5:72b'
    config['ai']['ollama']['temperature'] = 0.05
    config['ai']['ollama']['timeout'] = 180

    return config

def extract_attachments_from_emails(mailbox_path, temp_dir, limit=30, max_size_mb=2):
    """Extract smaller attachments for safer processing"""
    logger.info(f"Extracting attachments (<{max_size_mb}MB)")

    temp_dir.mkdir(parents=True, exist_ok=True)
    attachments = []
    max_size_bytes = max_size_mb * 1024 * 1024

    try:
        mbox = mailbox.mbox(str(mailbox_path))

        for idx, msg in enumerate(mbox):
            if len(attachments) >= limit:
                break

            sender = msg.get("From", "")
            subject = msg.get("Subject", "")

            for part in msg.walk():
                if len(attachments) >= limit:
                    break

                if part.get_content_maintype() == "multipart":
                    continue

                filename = part.get_filename()
                if not filename:
                    continue

                ext = Path(filename).suffix.lower()
                if ext not in ['.pdf', '.jpg', '.jpeg', '.png']:
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if len(payload) > max_size_bytes:
                        logger.debug(f"Skipping large file: {filename}")
                        continue

                    timestamp = int(datetime.now().timestamp() * 1000000)
                    safe_filename = f"safe_{idx}_{timestamp}_{filename}"
                    attachment_path = temp_dir / safe_filename

                    with open(attachment_path, "wb") as f:
                        f.write(payload)

                    attachments.append({
                        "path": str(attachment_path),
                        "filename": filename,
                        "sender": sender,
                        "subject": subject,
                        "size_kb": len(payload) / 1024
                    })

                    logger.info(f"  [{len(attachments)}/{limit}] {filename} ({len(payload)/1024:.1f} KB)")

                except Exception as e:
                    logger.error(f"Error: {e}")

    except Exception as e:
        logger.error(f"Mailbox error: {e}", exc_info=True)

    return attachments

def process_single_document(args):
    """Process one document"""
    attachment, config, idx, total = args

    processor = DocumentProcessor(config)
    db = DatabaseManager(config)
    classifier = ImprovedAIClassifier(config, db)
    blacklist_whitelist = BlacklistWhitelist(config)

    result = {
        "idx": idx,
        "filename": attachment['filename'],
        "success": False,
    }

    try:
        logger.info(f"[{idx}/{total}] {attachment['filename']}")

        # OCR
        ocr_result = processor.process_document(attachment["path"])

        if not ocr_result.get("success"):
            result["error"] = "OCR failed"
            return result

        text = ocr_result.get("text", "")
        ocr_conf = ocr_result.get("confidence", 0)

        # AI Classification
        classification = classifier.classify(text, ocr_result.get("metadata", {}))

        doc_type = classification.get("type", "jine")
        ai_conf = classification.get("confidence", 0)

        logger.info(f"[{idx}/{total}] ✓ {doc_type} ({ai_conf:.0%})")

        # Save to DB
        doc_id = db.insert_document(
            file_path=attachment["path"],
            ocr_text=text,
            ocr_confidence=ocr_conf,
            document_type=doc_type,
            ai_confidence=ai_conf,
            metadata={
                **classification.get("metadata", {}),
                "sender": attachment["sender"],
                "subject": attachment["subject"],
            }
        )

        result["success"] = True
        result["doc_type"] = doc_type
        result["confidence"] = ai_conf
        result["db_id"] = doc_id

        return result

    except Exception as e:
        logger.error(f"[{idx}/{total}] Error: {e}")
        result["error"] = str(e)
        return result

def main():
    start_time = time.time()

    logger.info("="*80)
    logger.info("🛡️ SAFE PARALLEL PROCESSING (Max 3 workers, resource monitored)")
    logger.info("="*80)

    # Check initial resources
    resources = check_system_resources()
    logger.info(f"Initial system state:")
    logger.info(f"  CPU: {resources['cpu_percent']:.1f}%")
    logger.info(f"  Memory: {resources['mem_percent']:.1f}%")

    if not resources['safe']:
        logger.error("❌ System already overloaded! Exiting.")
        logger.error(f"CPU: {resources['cpu_percent']:.1f}% (limit 70%)")
        logger.error(f"Memory: {resources['mem_percent']:.1f}% (limit 70%)")
        return

    # Load config
    config = load_config()

    # Extract attachments
    temp_dir = Path("data/temp_safe")
    temp_dir.mkdir(parents=True, exist_ok=True)

    profile_path = Path("/Users/m.a.j.puzik/Library/Thunderbird/Profiles/1oli4gwg.default-esr")
    mailbox_path = profile_path / "ImapMail/outlook.office365.com/INBOX"

    logger.info("\nExtracting attachments...")
    attachments = extract_attachments_from_emails(mailbox_path, temp_dir, limit=30, max_size_mb=2)

    logger.info(f"\n✓ Extracted {len(attachments)} attachments")

    if not attachments:
        logger.error("No attachments found!")
        return

    # Process with LIMITED workers (max 3)
    MAX_WORKERS = 3
    logger.info(f"\n🛡️ Using {MAX_WORKERS} workers (safe mode)\n")

    process_args = [(att, config, i+1, len(attachments)) for i, att in enumerate(attachments)]

    results = []
    completed = 0

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_document, args): args for args in process_args}

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                completed += 1

                # Check resources every 5 documents
                if completed % 5 == 0:
                    resources = check_system_resources()
                    logger.info(f"📊 System check [{completed}/{len(attachments)}]: CPU={resources['cpu_percent']:.1f}%, MEM={resources['mem_percent']:.1f}%")

                    if not resources['safe']:
                        logger.warning(f"⚠️ Resources exceeded limits!")
                        logger.warning(f"CPU: {resources['cpu_percent']:.1f}% / Memory: {resources['mem_percent']:.1f}%")

                if result["success"]:
                    logger.info(f"✓ {completed}/{len(attachments)}: {result['doc_type']}")

            except Exception as e:
                logger.error(f"Task error: {e}")

    # Statistics
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r["success"])

    type_counts = Counter()
    total_confidence = 0

    for r in results:
        if r["success"]:
            type_counts[r["doc_type"]] += 1
            total_confidence += r["confidence"]

    avg_conf = total_confidence / successful if successful > 0 else 0

    # Final report
    logger.info(f"\n{'='*80}")
    logger.info("🎉 RESULTS")
    logger.info(f"{'='*80}")
    logger.info(f"⏱️  Time: {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"⚡ Avg/doc: {total_time/len(attachments):.1f}s")
    logger.info(f"✓ Success: {successful}/{len(attachments)}")
    logger.info(f"🎯 Avg confidence: {avg_conf:.1%}")

    logger.info(f"\n📊 Classification:")
    for doc_type, count in type_counts.most_common():
        pct = (count / successful * 100) if successful > 0 else 0
        logger.info(f"  {doc_type:<20} {count:>3} ({pct:>5.1f}%)")

    # Final resource check
    resources = check_system_resources()
    logger.info(f"\nFinal system state:")
    logger.info(f"  CPU: {resources['cpu_percent']:.1f}% {'✓' if resources['cpu_ok'] else '❌'}")
    logger.info(f"  Memory: {resources['mem_percent']:.1f}% {'✓' if resources['mem_ok'] else '❌'}")

    logger.info(f"{'='*80}\n")

    # Cleanup
    for att in attachments:
        Path(att["path"]).unlink(missing_ok=True)

if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    main()
