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
Extract structured metadata from invoices and orders using LLM
Extracts: amount_with_vat, vendor_name, vendor_ico, invoice_number, dates, etc.
"""

import sqlite3
import json
import requests
import sys
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/metadata_extraction.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# LLM Configuration
OLLAMA_SERVERS = [
    "http://192.168.10.83:11434",
    "http://192.168.10.35:11434",
    "http://localhost:11434"
]
MODEL = "qwen2.5:7b"  # Fast and accurate for Czech invoices

# JSON Schema for extraction
EXTRACTION_PROMPT = """Analyzuj tento text z faktury/objednávky a extrahuj strukturované informace.
Odpověz POUZE validním JSON objektem s těmito poli (použij null pokud informace chybí):

{
  "amount_with_vat": 12345.67,
  "amount_without_vat": 10200.00,
  "vat_amount": 2145.67,
  "currency": "CZK",
  "vendor_name": "Název dodavatele s.r.o.",
  "vendor_ico": "12345678",
  "vendor_dic": "CZ12345678",
  "invoice_number": "2024001",
  "variable_symbol": "123456",
  "order_number": "LO-2024-001",
  "invoice_date": "2024-06-26",
  "due_date": "2024-07-10",
  "customer_name": "Odběratel s.r.o.",
  "customer_ico": "87654321"
}

Pravidla:
- Částky jako čísla (float), ne stringy
- Datumy ve formátu YYYY-MM-DD
- IČO jako string (8 číslic)
- Čísla dokumentů jako stringy
- Částka "amount_with_vat" je nejdůležitější - vždy ji hledej (celkem k úhradě, total, apod.)

OCR TEXT:
{ocr_text}

JSON:"""


def get_available_ollama_server() -> Optional[str]:
    """Find first available Ollama server"""
    for server in OLLAMA_SERVERS:
        try:
            resp = requests.get(f"{server}/api/tags", timeout=2)
            if resp.status_code == 200:
                logger.info(f"✓ Using Ollama server: {server}")
                return server
        except:
            continue
    logger.error("❌ No Ollama server available!")
    return None


def extract_metadata_with_llm(ocr_text: str, ollama_server: str) -> Optional[Dict]:
    """Extract structured metadata from OCR text using LLM"""

    # Trim OCR text to first 3000 chars (most relevant info is at top)
    ocr_text_trimmed = ocr_text[:3000] if len(ocr_text) > 3000 else ocr_text

    prompt = EXTRACTION_PROMPT.format(ocr_text=ocr_text_trimmed)

    try:
        response = requests.post(
            f"{ollama_server}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent extraction
                    "num_predict": 500
                }
            },
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"LLM request failed: {response.status_code}")
            return None

        llm_output = response.json().get("response", "")

        # Try to extract JSON from response
        # Sometimes LLM adds extra text before/after JSON
        json_start = llm_output.find("{")
        json_end = llm_output.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = llm_output[json_start:json_end]
            metadata = json.loads(json_str)
            return metadata
        else:
            logger.warning("No JSON found in LLM response")
            return None

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.debug(f"LLM output: {llm_output[:500]}")
        return None
    except Exception as e:
        logger.error(f"LLM extraction error: {e}")
        return None


def process_document(doc_id: int, doc_type: str, ocr_text: str, current_metadata: str,
                     ollama_server: str, progress: str) -> tuple:
    """Process single document and extract metadata"""

    logger.info(f"{progress} Processing doc #{doc_id} ({doc_type})")

    # Parse current metadata
    try:
        metadata = json.loads(current_metadata) if current_metadata else {}
    except:
        metadata = {}

    # Check if already has amount_with_vat
    if metadata.get("amount_with_vat"):
        logger.info(f"  ⏭️  Doc #{doc_id} already has amount, skipping")
        return (doc_id, None, "skipped")

    # Extract metadata with LLM
    extracted = extract_metadata_with_llm(ocr_text, ollama_server)

    if not extracted:
        logger.warning(f"  ❌ Doc #{doc_id} - extraction failed")
        return (doc_id, None, "failed")

    # Merge with existing metadata
    metadata.update(extracted)

    # Log extracted amount
    amount = extracted.get("amount_with_vat")
    vendor = extracted.get("vendor_name", "N/A")

    if amount:
        logger.info(f"  ✓ Doc #{doc_id} - Amount: {amount} CZK, Vendor: {vendor}")
        return (doc_id, metadata, "success")
    else:
        logger.warning(f"  ⚠️  Doc #{doc_id} - No amount found")
        return (doc_id, metadata, "no_amount")


def update_document_metadata(conn: sqlite3.Connection, doc_id: int, metadata: Dict):
    """Update document metadata in database"""
    cursor = conn.cursor()
    metadata_json = json.dumps(metadata, ensure_ascii=False)

    cursor.execute("""
        UPDATE documents
        SET metadata = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (metadata_json, doc_id))

    conn.commit()


def main():
    """Main extraction workflow"""

    logger.info("="*80)
    logger.info("💰 INVOICE METADATA EXTRACTOR")
    logger.info("="*80)

    # Find Ollama server
    ollama_server = get_available_ollama_server()
    if not ollama_server:
        sys.exit(1)

    # Connect to database
    db_path = Path(__file__).parent / "data" / "documents.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Find documents that need metadata extraction
    logger.info("\n🔍 Finding documents to process...")

    cursor.execute("""
        SELECT d.id, d.document_type, d.ocr_text, d.metadata
        FROM documents d
        WHERE d.document_type IN ('faktura', 'objednávka', 'dodací list')
          AND d.ocr_text IS NOT NULL
          AND LENGTH(d.ocr_text) > 100
          AND (
              d.metadata IS NULL
              OR d.metadata NOT LIKE '%amount_with_vat%'
              OR json_extract(d.metadata, '$.amount_with_vat') IS NULL
          )
        ORDER BY d.id
    """)

    documents = cursor.fetchall()

    if not documents:
        logger.info("✓ No documents need metadata extraction")
        conn.close()
        return

    logger.info(f"📄 Found {len(documents)} documents to process")
    logger.info(f"📊 Using LLM: {MODEL} on {ollama_server}\n")

    # Process documents in parallel
    results = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "no_amount": 0
    }

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []

        for idx, (doc_id, doc_type, ocr_text, metadata) in enumerate(documents, 1):
            progress = f"[{idx}/{len(documents)}]"
            future = executor.submit(
                process_document,
                doc_id, doc_type, ocr_text, metadata,
                ollama_server, progress
            )
            futures.append(future)

        # Collect results
        for future in as_completed(futures):
            try:
                doc_id, extracted_metadata, status = future.result()

                if status == "success" and extracted_metadata:
                    update_document_metadata(conn, doc_id, extracted_metadata)
                    results["success"] += 1
                elif status == "no_amount" and extracted_metadata:
                    update_document_metadata(conn, doc_id, extracted_metadata)
                    results["no_amount"] += 1
                elif status == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1

            except Exception as e:
                logger.error(f"Error processing document: {e}")
                results["failed"] += 1

    conn.close()

    # Summary
    logger.info("\n" + "="*80)
    logger.info("📊 EXTRACTION SUMMARY")
    logger.info("="*80)
    logger.info(f"✓ Successfully extracted: {results['success']}")
    logger.info(f"⚠️  Extracted but no amount: {results['no_amount']}")
    logger.info(f"⏭️  Skipped (already has data): {results['skipped']}")
    logger.info(f"❌ Failed: {results['failed']}")
    logger.info(f"📄 Total processed: {len(documents)}")

    if results["success"] > 0:
        logger.info("\n🔄 Now run: python match_documents.py")
        logger.info("   to update document chains with extracted amounts")

    logger.info("="*80)


if __name__ == "__main__":
    main()
