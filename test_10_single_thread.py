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
Quick test: Process first 10 documents WITH metadata (single-threaded)
No multiprocessing = no pickle error
"""

import sys
import json
import time
from pathlib import Path
from collections import Counter
import logging

sys.path.insert(0, str(Path(__file__).parent))

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier_improved import ImprovedAIClassifier
from src.database.db_manager import DatabaseManager
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/test_10_single.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    config_path = Path(__file__).parent / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

def process_document(attachment, config, idx, total):
    """Process single document"""
    file_path = Path(attachment['path'])

    logger.info(f"[{idx}/{total}] Processing: {file_path.name}")

    try:
        # Initialize components
        db = DatabaseManager(config)
        doc_processor = DocumentProcessor(config)
        classifier = ImprovedAIClassifier(config)

        # Extract text (OCR/PDF)
        ocr_result = doc_processor.process_document(str(file_path))
        text = ocr_result['text']

        if not text:
            logger.info(f"  ❌ No text extracted")
            return {"success": False}

        logger.info(f"  ✓ Text extracted: {len(text)} chars")

        # AI Classification (pass attachment metadata)
        classification = classifier.classify(text, attachment)
        doc_type = classification.get('type', 'jine')
        confidence = classification.get('confidence', 0.0)

        logger.info(f"  ✓ Classified as: {doc_type} ({confidence:.2f})")

        # Save to database WITH METADATA
        doc_id = db.insert_document(
            file_path=str(file_path),
            ocr_text=text,
            ocr_confidence=ocr_result['confidence'],
            document_type=doc_type,
            ai_confidence=confidence,
            ai_method=classification.get('method', 'llm'),
            sender=attachment.get('sender'),  # ✓ Email metadata
            subject=attachment.get('subject'),  # ✓ Email metadata
            metadata={
                'mailbox': attachment.get('mailbox'),
                'date': attachment.get('date'),
                'filename': attachment.get('filename')
            }
        )

        logger.info(f"  ✓ Saved to DB (ID: {doc_id}) with sender: {attachment.get('sender', 'N/A')[:50]}")

        return {
            "success": True,
            "doc_type": doc_type,
            "confidence": confidence
        }

    except Exception as e:
        logger.error(f"  ❌ Error: {e}")
        import traceback
        logger.error(f"  Traceback: {traceback.format_exc()}")
        return {"success": False, "error": str(e)}

def main():
    start_time = time.time()

    logger.info("="*80)
    logger.info("📄 TEST: 10 DOCUMENTS WITH METADATA (SINGLE-THREADED)")
    logger.info("="*80)

    # Load metadata
    metadata_file = Path(__file__).parent / "attachments_metadata.json"

    if not metadata_file.exists():
        logger.error("❌ attachments_metadata.json not found")
        sys.exit(1)

    with open(metadata_file, 'r', encoding='utf-8') as f:
        attachments_data = json.load(f)

    # Take first 10
    attachments = []
    for att in attachments_data:
        if Path(att['path']).exists():
            attachments.append(att)
        if len(attachments) >= 10:
            break

    logger.info(f"✓ Found {len(attachments)} files to process\n")

    # Load config
    config = load_config()

    # Process documents
    results = []
    for i, att in enumerate(attachments, 1):
        result = process_document(att, config, i, len(attachments))
        results.append(result)
        print()  # Empty line between documents

    # Stats
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r.get("success") and not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))

    type_counts = Counter()
    total_conf = 0

    for r in results:
        if r.get("success") and not r.get("skipped"):
            type_counts[r["doc_type"]] += 1
            total_conf += r.get("confidence", 0)

    avg_conf = total_conf / successful if successful > 0 else 0

    # Report
    logger.info("="*80)
    logger.info("🎉 TEST COMPLETE")
    logger.info("="*80)
    logger.info(f"⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"⚡ Avg/doc: {total_time/len(attachments):.1f}s")
    logger.info(f"📄 Processed: {len(results)}")
    logger.info(f"✅ New documents: {successful}")
    logger.info(f"⏭️  Skipped (duplicates): {skipped}")
    logger.info(f"⭐ Avg confidence: {avg_conf:.2f}")
    logger.info(f"\n📊 Document types:")
    for doc_type, count in type_counts.most_common():
        logger.info(f"   {doc_type}: {count}")
    logger.info("="*80)
    logger.info("\n📧 Email metadata (sender/subject/date) saved to database!")
    logger.info("="*80)

if __name__ == "__main__":
    main()
