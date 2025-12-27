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
Test complete document processing pipeline on 100 documents
"""

import email
import logging
import mailbox
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.blacklist_whitelist import BlacklistWhitelist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/test_processing.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration"""
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def extract_attachments_from_emails(mailbox_path, temp_dir, limit=100):
    """Extract attachments from emails"""
    logger.info(f"Extracting attachments from: {mailbox_path.name}")

    temp_dir.mkdir(parents=True, exist_ok=True)
    attachments = []

    try:
        mbox = mailbox.mbox(str(mailbox_path))
        email_count = 0

        for idx, msg in enumerate(mbox):
            if len(attachments) >= limit:
                break

            # Extract metadata
            sender = msg.get("From", "")
            subject = msg.get("Subject", "")
            date_str = msg.get("Date", "")

            # Extract attachments
            for part in msg.walk():
                if len(attachments) >= limit:
                    break

                if part.get_content_maintype() == "multipart":
                    continue

                filename = part.get_filename()
                if not filename:
                    continue

                # Check extension
                ext = Path(filename).suffix.lower()
                if ext not in ['.pdf', '.jpg', '.jpeg', '.png', '.docx', '.doc']:
                    continue

                try:
                    # Create safe filename
                    timestamp = int(datetime.now().timestamp() * 1000)
                    safe_filename = f"email_{idx}_{timestamp}_{filename}"
                    attachment_path = temp_dir / safe_filename

                    # Save attachment
                    with open(attachment_path, "wb") as f:
                        f.write(part.get_payload(decode=True))

                    attachments.append({
                        "path": str(attachment_path),
                        "filename": filename,
                        "sender": sender,
                        "subject": subject,
                        "date": date_str,
                        "ext": ext
                    })

                    logger.info(f"  [{len(attachments)}/{limit}] Extracted: {filename} from {sender[:50]}")

                except Exception as e:
                    logger.error(f"Error extracting {filename}: {e}")

            email_count += 1

    except Exception as e:
        logger.error(f"Error reading mailbox: {e}", exc_info=True)

    logger.info(f"Extracted {len(attachments)} attachments from {email_count} emails")
    return attachments

def process_documents(attachments, config, processor, classifier, db, blacklist_whitelist):
    """Process all documents with OCR and AI"""
    logger.info(f"\nStarting document processing pipeline...")

    results = {
        "processed": 0,
        "failed": 0,
        "by_type": Counter(),
        "by_confidence": {"high": 0, "medium": 0, "low": 0},
        "reklama": 0,
        "soudni": 0,
        "faktury": 0,
        "stvrzenky": 0,
    }

    for idx, attachment in enumerate(attachments, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"Processing [{idx}/{len(attachments)}]: {attachment['filename']}")
        logger.info(f"From: {attachment['sender'][:70]}")
        logger.info(f"Subject: {attachment['subject'][:70]}")

        try:
            file_path = attachment["path"]

            # 1. OCR Processing
            logger.info("  → Running OCR...")
            ocr_result = processor.process_document(file_path)

            if not ocr_result.get("success"):
                logger.error(f"  ✗ OCR failed: {ocr_result.get('error')}")
                results["failed"] += 1
                continue

            text = ocr_result.get("text", "")
            ocr_confidence = ocr_result.get("confidence", 0)
            logger.info(f"  ✓ OCR completed (confidence: {ocr_confidence:.1f}%)")
            logger.info(f"  Text length: {len(text)} characters")
            logger.info(f"  Preview: {text[:150]}...")

            # 2. AI Classification
            logger.info("  → Classifying with AI...")
            classification = classifier.classify(text, ocr_result.get("metadata", {}))

            doc_type = classification.get("type", "jine")
            ai_confidence = classification.get("confidence", 0)

            logger.info(f"  ✓ Classification: {doc_type}")
            logger.info(f"  ✓ AI Confidence: {ai_confidence:.1%}")
            logger.info(f"  Metadata: {classification.get('metadata', {})}")

            # 3. Check blacklist/whitelist
            sender_email = attachment["sender"]
            is_blacklisted = blacklist_whitelist.is_blacklisted(sender_email)
            is_whitelisted = blacklist_whitelist.is_whitelisted(sender_email)

            if is_blacklisted:
                logger.info(f"  ⚠ Sender is BLACKLISTED (known spam)")
            if is_whitelisted:
                logger.info(f"  ✓ Sender is WHITELISTED (trusted)")

            # 4. Save to database
            logger.info("  → Saving to database...")
            doc_id = db.insert_document(
                file_path=file_path,
                ocr_text=text,
                ocr_confidence=ocr_confidence,
                document_type=doc_type,
                ai_confidence=ai_confidence,
                metadata={
                    **classification.get("metadata", {}),
                    "sender": attachment["sender"],
                    "subject": attachment["subject"],
                    "email_date": attachment["date"],
                    "is_blacklisted": is_blacklisted,
                    "is_whitelisted": is_whitelisted,
                }
            )
            logger.info(f"  ✓ Saved to database (ID: {doc_id})")

            # Update statistics
            results["processed"] += 1
            results["by_type"][doc_type] += 1

            if ai_confidence >= 0.8:
                results["by_confidence"]["high"] += 1
            elif ai_confidence >= 0.6:
                results["by_confidence"]["medium"] += 1
            else:
                results["by_confidence"]["low"] += 1

            if doc_type == "reklama":
                results["reklama"] += 1
            elif doc_type == "soudni_dokument":
                results["soudni"] += 1
            elif doc_type == "faktura":
                results["faktury"] += 1
            elif doc_type == "stvrzenka":
                results["stvrzenky"] += 1

        except Exception as e:
            logger.error(f"  ✗ Error processing document: {e}", exc_info=True)
            results["failed"] += 1

    return results

def print_summary(results, total_time):
    """Print final summary"""
    logger.info("\n" + "="*80)
    logger.info("FINAL SUMMARY - Document Processing Test")
    logger.info("="*80)
    logger.info(f"Total processing time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    logger.info(f"Average per document: {total_time/100:.2f} seconds")
    logger.info("")
    logger.info(f"✓ Successfully processed: {results['processed']}")
    logger.info(f"✗ Failed: {results['failed']}")
    logger.info("")
    logger.info("Classification by type:")
    for doc_type, count in results["by_type"].most_common():
        logger.info(f"  - {doc_type}: {count}")
    logger.info("")
    logger.info("Classification confidence:")
    logger.info(f"  - High (≥80%): {results['by_confidence']['high']}")
    logger.info(f"  - Medium (60-80%): {results['by_confidence']['medium']}")
    logger.info(f"  - Low (<60%): {results['by_confidence']['low']}")
    logger.info("")
    logger.info("Special categories:")
    logger.info(f"  - Faktury (Invoices): {results['faktury']}")
    logger.info(f"  - Stvrzenky (Receipts): {results['stvrzenky']}")
    logger.info(f"  - Reklama (Ads/Spam): {results['reklama']}")
    logger.info(f"  - Soudní dokumenty (Legal): {results['soudni']}")
    logger.info("="*80)

def main():
    import time
    start_time = time.time()

    logger.info("="*80)
    logger.info("MAJ Document Recognition - Full Processing Test (100 documents)")
    logger.info("="*80)

    # Load config
    logger.info("\nLoading configuration...")
    config = load_config()

    # Initialize components
    logger.info("Initializing components...")
    db = DatabaseManager(config)
    processor = DocumentProcessor(config)
    classifier = AIClassifier(config, db)
    blacklist_whitelist = BlacklistWhitelist(config)

    # Create temp directory
    temp_dir = Path("data/temp_test")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Extract attachments
    logger.info("\n" + "="*80)
    logger.info("STEP 1: Extracting attachments from Thunderbird")
    logger.info("="*80)

    profile_path = Path("/Users/m.a.j.puzik/Library/Thunderbird/Profiles/1oli4gwg.default-esr")
    mailbox_paths = [
        profile_path / "ImapMail/outlook.office365.com/INBOX",
        profile_path / "ImapMail/outlook.office365.com/Archivovat",
    ]

    all_attachments = []
    for mailbox_path in mailbox_paths:
        if not mailbox_path.exists():
            continue

        attachments = extract_attachments_from_emails(
            mailbox_path,
            temp_dir,
            limit=100 - len(all_attachments)
        )
        all_attachments.extend(attachments)

        if len(all_attachments) >= 100:
            break

    logger.info(f"\nTotal attachments extracted: {len(all_attachments)}")

    if len(all_attachments) == 0:
        logger.error("No attachments found! Exiting.")
        return

    # Process documents
    logger.info("\n" + "="*80)
    logger.info("STEP 2: Processing documents with OCR + AI")
    logger.info("="*80)

    results = process_documents(
        all_attachments[:100],  # Limit to 100
        config,
        processor,
        classifier,
        db,
        blacklist_whitelist
    )

    # Print summary
    total_time = time.time() - start_time
    print_summary(results, total_time)

    # Cleanup
    logger.info("\nCleaning up temporary files...")
    try:
        for attachment in all_attachments:
            Path(attachment["path"]).unlink(missing_ok=True)
        logger.info("✓ Cleanup completed")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

if __name__ == "__main__":
    main()
