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
Process extracted files WITH metadata
Reads attachments_metadata.json and saves sender/subject/date to database
"""

import sys
import json
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
import logging
import importlib.util

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/process_with_metadata.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Import adaptive_parallel_OPTIMIZED_v2.2 module
spec = importlib.util.spec_from_file_location(
    "adaptive_v2_2",
    Path(__file__).parent / "adaptive_parallel_OPTIMIZED_v2.2.py"
)
adaptive_v2_2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adaptive_v2_2)

def main():
    """Process all files from temp_attachments directory WITH metadata"""
    start_time = time.time()

    logger.info("="*80)
    logger.info("📄 PROCESSING DOCUMENTS WITH EMAIL METADATA")
    logger.info("="*80)
    logger.info("Optimizations:")
    logger.info("  1. OCR CASCADE (ces → eng → deu) - 2.6× faster")
    logger.info("  2. FAST PRE-CLASSIFIER - 50% docs without OCR")
    logger.info("  3. DOCUMENT CACHE - skip duplicates")
    logger.info("  4. ADAPTIVE WORKERS - auto-scale 1-6")
    logger.info("  5. EMAIL METADATA - sender/subject/date saved to DB")
    logger.info("="*80)

    # Load metadata from JSON
    metadata_file = Path(__file__).parent / "attachments_metadata.json"

    if not metadata_file.exists():
        logger.error("❌ attachments_metadata.json not found")
        logger.error("   Run extract_with_metadata.py first!")
        sys.exit(1)

    logger.info(f"\n📂 Loading metadata from {metadata_file.name}")

    with open(metadata_file, 'r', encoding='utf-8') as f:
        attachments_data = json.load(f)

    logger.info(f"✓ Loaded metadata for {len(attachments_data)} documents")

    # Filter only files that exist
    attachments = []
    for att in attachments_data:
        file_path = Path(att['path'])
        if file_path.exists():
            attachments.append(att)
        else:
            logger.warning(f"File not found: {file_path.name}")

    logger.info(f"✓ Found {len(attachments)} files to process")

    if not attachments:
        logger.warning("⚠️ No files to process")
        sys.exit(0)

    # Load config
    config = adaptive_v2_2.load_config()

    logger.info(f"\n🔄 PROCESSING {len(attachments)} DOCUMENTS WITH METADATA...\n")

    # Setup processing args - pass full attachment dict with metadata
    process_args = [(att, config, i+1, len(attachments)) for i, att in enumerate(attachments)]

    # Process with parallel workers
    initial_workers = 4
    logger.info(f"Starting with {initial_workers} workers")

    results = []
    completed = 0

    with ProcessPoolExecutor(max_workers=initial_workers) as executor:
        futures_list = [executor.submit(adaptive_v2_2.process_single_document_optimized, args) for args in process_args]

        for future in as_completed(futures_list):
            try:
                result = future.result(timeout=300)
                results.append(result)
                completed += 1

                if completed % 50 == 0:
                    logger.info(f"\n📊 Progress: {completed}/{len(attachments)}\n")

            except Exception as e:
                logger.error(f"Task failed: {e}")
                completed += 1

    # Stats
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r.get("success"))

    type_counts = Counter()
    total_conf = 0

    for r in results:
        if r.get("success"):
            type_counts[r["doc_type"]] += 1
            total_conf += r.get("confidence", 0)

    avg_conf = total_conf / successful if successful > 0 else 0

    # Report
    logger.info(f"\n{'='*80}")
    logger.info("🎉 PROCESSING COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"⏱️  Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    logger.info(f"⚡ Avg/doc: {total_time/len(attachments):.1f}s")
    logger.info(f"📄 Processed: {len(results)}/{len(attachments)}")
    logger.info(f"✅ Successful: {successful} ({successful/len(results)*100:.1f}%)")
    logger.info(f"⭐ Avg confidence: {avg_conf:.2f}")
    logger.info(f"\n📊 Document types:")
    for doc_type, count in type_counts.most_common():
        logger.info(f"   {doc_type}: {count}")
    logger.info(f"{'='*80}")
    logger.info("\n📧 Email metadata (sender/subject/date) saved to database!")
    logger.info(f"{'='*80}\n")

if __name__ == "__main__":
    main()
