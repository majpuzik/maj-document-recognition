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
Quick test on 20 smaller documents (skip large PDFs)
"""

import email
import logging
import mailbox
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.blacklist_whitelist import BlacklistWhitelist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/quick_test.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def extract_small_attachments(mailbox_path, temp_dir, limit=20, max_size_mb=2):
    """Extract only smaller attachments for faster testing"""
    logger.info(f"Extracting small attachments (<{max_size_mb}MB) from: {mailbox_path.name}")

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
                    # Check size
                    payload = part.get_payload(decode=True)
                    if len(payload) > max_size_bytes:
                        logger.debug(f"  Skipping large file: {filename} ({len(payload)/(1024*1024):.1f}MB)")
                        continue

                    # Save
                    timestamp = int(datetime.now().timestamp() * 1000)
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

def process_documents(attachments, config, processor, classifier, db, blacklist_whitelist):
    """Process all documents"""
    results = {
        "processed": 0,
        "failed": 0,
        "by_type": Counter(),
        "faktury": 0,
        "stvrzenky": 0,
        "reklama": 0,
    }

    for idx, attachment in enumerate(attachments, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"[{idx}/{len(attachments)}] Processing: {attachment['filename']} ({attachment['size_kb']:.1f} KB)")

        try:
            file_path = attachment["path"]

            # OCR
            logger.info("  → OCR...")
            ocr_result = processor.process_document(file_path)

            if not ocr_result.get("success"):
                logger.error(f"  ✗ OCR failed")
                results["failed"] += 1
                continue

            text = ocr_result.get("text", "")
            logger.info(f"  ✓ OCR done ({len(text)} chars, {ocr_result.get('confidence', 0):.0f}% confidence)")

            # AI Classification
            logger.info("  → AI classification...")
            classification = classifier.classify(text, ocr_result.get("metadata", {}))

            doc_type = classification.get("type", "jine")
            ai_confidence = classification.get("confidence", 0)

            logger.info(f"  ✓ Type: {doc_type} ({ai_confidence:.0%} confidence)")

            # Check sender reputation
            sender = attachment["sender"]
            is_blacklisted = blacklist_whitelist.is_blacklisted(sender)
            is_whitelisted = blacklist_whitelist.is_whitelisted(sender)

            if is_blacklisted:
                logger.info(f"  ⚠ BLACKLISTED sender")
            if is_whitelisted:
                logger.info(f"  ✓ WHITELISTED sender")

            # Save
            doc_id = db.insert_document(
                file_path=file_path,
                ocr_text=text,
                ocr_confidence=ocr_result.get("confidence", 0),
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
            logger.info(f"  ✓ Saved (DB ID: {doc_id})")

            # Stats
            results["processed"] += 1
            results["by_type"][doc_type] += 1

            if doc_type == "faktura":
                results["faktury"] += 1
            elif doc_type == "stvrzenka":
                results["stvrzenky"] += 1
            elif doc_type == "reklama":
                results["reklama"] += 1

        except Exception as e:
            logger.error(f"  ✗ Error: {e}", exc_info=True)
            results["failed"] += 1

    return results

def main():
    import time
    start_time = time.time()

    logger.info("="*80)
    logger.info("Quick Test: 20 Small Documents")
    logger.info("="*80)

    config = load_config()
    db = DatabaseManager(config)
    processor = DocumentProcessor(config)
    classifier = AIClassifier(config, db)
    blacklist_whitelist = BlacklistWhitelist(config)

    temp_dir = Path("data/temp_quick")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Extract
    profile_path = Path("/Users/m.a.j.puzik/Library/Thunderbird/Profiles/1oli4gwg.default-esr")
    mailbox_path = profile_path / "ImapMail/outlook.office365.com/INBOX"

    logger.info(f"\nExtracting 20 small attachments...")
    attachments = extract_small_attachments(mailbox_path, temp_dir, limit=20, max_size_mb=1)

    logger.info(f"\nExtracted {len(attachments)} attachments")
    logger.info(f"\nProcessing...")

    # Process
    results = process_documents(attachments, config, processor, classifier, db, blacklist_whitelist)

    # Summary
    total_time = time.time() - start_time
    logger.info("\n" + "="*80)
    logger.info("FINAL RESULTS")
    logger.info("="*80)
    logger.info(f"⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"📄 Processed: {results['processed']}")
    logger.info(f"❌ Failed: {results['failed']}")
    logger.info(f"\n📊 Classification:")
    for doc_type, count in results["by_type"].most_common():
        logger.info(f"  - {doc_type}: {count}")
    logger.info(f"\n💰 Faktury: {results['faktury']}")
    logger.info(f"🧾 Stvrzenky: {results['stvrzenky']}")
    logger.info(f"📧 Reklama: {results['reklama']}")
    logger.info("="*80)

    # Cleanup
    for att in attachments:
        Path(att["path"]).unlink(missing_ok=True)

if __name__ == "__main__":
    main()
