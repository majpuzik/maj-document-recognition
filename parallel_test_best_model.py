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
PARALLEL processing with BEST model (qwen2.5:72b)
"""

import email
import logging
import mailbox
import sys
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
        logging.FileHandler("logs/parallel_test.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # ✅ USE BEST MODEL - qwen2.5:72b
    config['ai']['ollama']['model'] = 'qwen2.5:72b'
    config['ai']['ollama']['temperature'] = 0.05
    config['ai']['ollama']['timeout'] = 120

    return config

def extract_attachments_from_emails(mailbox_path, temp_dir, limit=100, max_size_mb=5):
    """Extract attachments"""
    logger.info(f"Extracting attachments (<{max_size_mb}MB) from: {mailbox_path.name}")

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
            date_str = msg.get("Date", "")

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
                        continue

                    timestamp = int(datetime.now().timestamp() * 1000000)  # Microseconds for uniqueness
                    safe_filename = f"email_{idx}_{timestamp}_{filename}"
                    attachment_path = temp_dir / safe_filename

                    with open(attachment_path, "wb") as f:
                        f.write(payload)

                    attachments.append({
                        "path": str(attachment_path),
                        "filename": filename,
                        "sender": sender,
                        "subject": subject,
                        "date": date_str,
                        "ext": ext,
                        "size_kb": len(payload) / 1024
                    })

                    logger.info(f"  [{len(attachments)}/{limit}] {filename} ({len(payload)/1024:.1f} KB)")

                except Exception as e:
                    logger.error(f"Error extracting {filename}: {e}")

    except Exception as e:
        logger.error(f"Error reading mailbox: {e}", exc_info=True)

    return attachments

def process_single_document(args):
    """
    Process a single document - this runs in parallel

    Args:
        args: tuple of (attachment_dict, config_dict, idx, total)
    """
    attachment, config, idx, total = args

    # Create new instances in this process
    processor = DocumentProcessor(config)
    db = DatabaseManager(config)
    classifier = ImprovedAIClassifier(config, db)
    blacklist_whitelist = BlacklistWhitelist(config)

    result = {
        "idx": idx,
        "filename": attachment['filename'],
        "success": False,
        "doc_type": None,
        "confidence": 0,
    }

    try:
        logger.info(f"[{idx}/{total}] Processing: {attachment['filename']} ({attachment['size_kb']:.1f} KB)")

        file_path = attachment["path"]

        # OCR
        ocr_result = processor.process_document(file_path)

        if not ocr_result.get("success"):
            logger.error(f"[{idx}/{total}] OCR failed")
            result["error"] = "OCR failed"
            return result

        text = ocr_result.get("text", "")
        ocr_confidence = ocr_result.get("confidence", 0)

        logger.info(f"[{idx}/{total}] OCR: {len(text)} chars, {ocr_confidence:.0f}% confidence")

        # AI Classification with BEST MODEL
        classification = classifier.classify(text, ocr_result.get("metadata", {}))

        doc_type = classification.get("type", "jine")
        ai_confidence = classification.get("confidence", 0)

        logger.info(f"[{idx}/{total}] ✓ {doc_type} ({ai_confidence:.0%} confidence)")

        # Check sender
        sender = attachment["sender"]
        is_blacklisted = blacklist_whitelist.is_blacklisted(sender)
        is_whitelisted = blacklist_whitelist.is_whitelisted(sender)

        # Save to database
        doc_id = db.insert_document(
            file_path=file_path,
            ocr_text=text,
            ocr_confidence=ocr_confidence,
            document_type=doc_type,
            ai_confidence=ai_confidence,
            metadata={
                **classification.get("metadata", {}),
                "sender": sender,
                "subject": attachment["subject"],
                "is_blacklisted": is_blacklisted,
                "is_whitelisted": is_whitelisted,
            }
        )

        result["success"] = True
        result["doc_type"] = doc_type
        result["confidence"] = ai_confidence
        result["ocr_confidence"] = ocr_confidence
        result["db_id"] = doc_id

        return result

    except Exception as e:
        logger.error(f"[{idx}/{total}] Error: {e}", exc_info=True)
        result["error"] = str(e)
        return result

def main():
    import time
    start_time = time.time()

    logger.info("="*80)
    logger.info("🚀 PARALLEL PROCESSING WITH BEST MODEL (qwen2.5:72b)")
    logger.info("="*80)

    # Load config
    config = load_config()

    # Create temp directory
    temp_dir = Path("data/temp_parallel")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Extract attachments
    logger.info(f"\n{'='*80}")
    logger.info("STEP 1: Extracting attachments from Thunderbird")
    logger.info(f"{'='*80}")

    profile_path = Path("/Users/m.a.j.puzik/Library/Thunderbird/Profiles/1oli4gwg.default-esr")
    mailbox_path = profile_path / "ImapMail/outlook.office365.com/INBOX"

    attachments = extract_attachments_from_emails(mailbox_path, temp_dir, limit=50, max_size_mb=3)

    logger.info(f"\n✓ Extracted {len(attachments)} attachments")

    if len(attachments) == 0:
        logger.error("No attachments found! Exiting.")
        return

    # Process in parallel
    logger.info(f"\n{'='*80}")
    logger.info(f"STEP 2: Processing {len(attachments)} documents in PARALLEL")
    logger.info(f"Using model: qwen2.5:72b (72.7B parameters)")
    logger.info(f"CPU cores: {mp.cpu_count()}")
    logger.info(f"{'='*80}\n")

    # Determine number of workers
    # Use CPU count - 2 to leave some headroom
    num_workers = max(1, mp.cpu_count() - 2)
    logger.info(f"🔥 Using {num_workers} parallel workers\n")

    # Prepare args for parallel processing
    process_args = [(att, config, i+1, len(attachments)) for i, att in enumerate(attachments)]

    results = []
    completed = 0

    # Process in parallel
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(process_single_document, args): args for args in process_args}

        # Collect results as they complete
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                completed += 1

                if result["success"]:
                    logger.info(f"✓ Completed {completed}/{len(attachments)}: {result['filename']} → {result['doc_type']}")
                else:
                    logger.error(f"✗ Failed {completed}/{len(attachments)}: {result['filename']}")

            except Exception as e:
                logger.error(f"Task failed: {e}")

    # Calculate statistics
    total_time = time.time() - start_time

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    type_counts = Counter()
    total_confidence = 0

    for r in results:
        if r["success"]:
            type_counts[r["doc_type"]] += 1
            total_confidence += r["confidence"]

    avg_confidence = total_confidence / successful if successful > 0 else 0

    # Print summary
    logger.info(f"\n{'='*80}")
    logger.info("🎉 FINAL RESULTS")
    logger.info(f"{'='*80}")
    logger.info(f"⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"⚡ Avg per document: {total_time/len(attachments):.1f}s")
    logger.info(f"📄 Processed: {successful}/{len(attachments)}")
    logger.info(f"✓ Success: {successful}")
    logger.info(f"✗ Failed: {failed}")
    logger.info(f"🎯 Average confidence: {avg_confidence:.1%}")

    logger.info(f"\n📊 Classification breakdown:")
    for doc_type, count in type_counts.most_common():
        percentage = (count / successful * 100) if successful > 0 else 0
        logger.info(f"  {doc_type:<25} {count:>3} ({percentage:>5.1f}%)")

    # Calculate improvement vs single-threaded
    single_thread_estimate = total_time * num_workers
    speedup = single_thread_estimate / total_time

    logger.info(f"\n🚀 Parallelization speedup:")
    logger.info(f"  Estimated single-thread time: {single_thread_estimate:.1f}s ({single_thread_estimate/60:.1f} min)")
    logger.info(f"  Actual parallel time: {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"  Speedup: {speedup:.1f}x faster!")

    logger.info(f"{'='*80}\n")

    # Cleanup
    logger.info("Cleaning up temporary files...")
    try:
        for att in attachments:
            Path(att["path"]).unlink(missing_ok=True)
        logger.info("✓ Cleanup completed")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

if __name__ == "__main__":
    # Set start method for macOS
    mp.set_start_method('spawn', force=True)
    main()
