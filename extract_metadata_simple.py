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
Simple metadata extractor - extracts amounts from invoices using LLM
"""

import sqlite3
import json
import requests
import sys
from pathlib import Path

# LLM Config
OLLAMA_SERVER = "http://192.168.10.83:11434"
MODEL = "qwen2.5:7b"

EXTRACTION_PROMPT = """Analyzuj tento text z české faktury a extrahuj POUZE částku včetně DPH.
Odpověz validním JSON s tímto formátem:

{{"amount_with_vat": 12345.67, "currency": "CZK"}}

Hledej: "Celkem k úhradě", "K uhradě celkem", "Total", "Celkem včetně DPH".
Pokud částku nenajdeš, vrať: {{"amount_with_vat": null, "currency": null}}

FAKTURA:
{ocr_text}

JSON:"""


def extract_amount(ocr_text: str) -> dict:
    """Extract amount using LLM"""
    # Trim to first 2000 chars
    text = ocr_text[:2000] if len(ocr_text) > 2000 else ocr_text

    prompt = EXTRACTION_PROMPT.format(ocr_text=text)

    try:
        resp = requests.post(
            f"{OLLAMA_SERVER}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 100}
            },
            timeout=30
        )

        if resp.status_code != 200:
            return None

        llm_output = resp.json().get("response", "")

        # Extract JSON
        start = llm_output.find("{")
        end = llm_output.rfind("}") + 1

        if start >= 0 and end > start:
            json_str = llm_output[start:end]
            return json.loads(json_str)

    except Exception as e:
        print(f"  LLM error: {e}")

    return None


def main():
    print("="*80)
    print("💰 SIMPLE METADATA EXTRACTOR")
    print("="*80)

    # Connect to DB
    db_path = Path(__file__).parent / "data" / "documents.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get all documents with OCR text
    print("\n🔍 Loading documents...")
    cursor.execute("""
        SELECT id, document_type, ocr_text, metadata
        FROM documents
        WHERE document_type IN ('faktura', 'objednávka')
          AND ocr_text IS NOT NULL
          AND LENGTH(ocr_text) > 100
        ORDER BY id
    """)

    all_docs = cursor.fetchall()
    print(f"📄 Found {len(all_docs)} documents with OCR text")

    # Filter - only those WITHOUT amount_with_vat
    docs_to_process = []
    for doc_id, doc_type, ocr_text, metadata_str in all_docs:
        try:
            metadata = json.loads(metadata_str) if metadata_str else {}
        except:
            metadata = {}

        # Check if amount_with_vat exists and is not null
        if not metadata.get("amount_with_vat"):
            docs_to_process.append((doc_id, doc_type, ocr_text, metadata))

    print(f"🔧 Need to process: {len(docs_to_process)} documents")

    if not docs_to_process:
        print("✓ All documents already have metadata")
        conn.close()
        return

    print(f"\n🤖 Using LLM: {MODEL} on {OLLAMA_SERVER}\n")

    # Process each document
    success = 0
    failed = 0

    for idx, (doc_id, doc_type, ocr_text, metadata) in enumerate(docs_to_process, 1):
        print(f"[{idx}/{len(docs_to_process)}] Doc #{doc_id} ({doc_type})... ", end="", flush=True)

        # Extract amount
        extracted = extract_amount(ocr_text)

        if extracted and extracted.get("amount_with_vat"):
            amount = extracted["amount_with_vat"]
            currency = extracted.get("currency", "CZK")

            # Update metadata
            metadata["amount_with_vat"] = amount
            metadata["currency"] = currency

            # Save to DB
            metadata_json = json.dumps(metadata, ensure_ascii=False)
            cursor.execute("""
                UPDATE documents
                SET metadata = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (metadata_json, doc_id))
            conn.commit()

            print(f"✓ {amount} {currency}")
            success += 1
        else:
            print("❌ No amount found")
            failed += 1

    conn.close()

    # Summary
    print("\n" + "="*80)
    print(f"✓ Successfully extracted: {success}")
    print(f"❌ Failed: {failed}")
    print(f"📄 Total processed: {len(docs_to_process)}")
    print("="*80)

    if success > 0:
        print("\n🔄 Run: python match_documents.py")
        print("   to update document chains with extracted amounts")


if __name__ == "__main__":
    main()
