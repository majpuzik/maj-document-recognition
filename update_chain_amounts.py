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
Update matched_document_chains.total_amount from document metadata
"""

import sqlite3
import json
from pathlib import Path

def main():
    print("="*80)
    print("💰 UPDATE CHAIN AMOUNTS FROM METADATA")
    print("="*80)

    # Connect to database
    db_path = Path(__file__).parent / "data" / "documents.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get all chains with NULL amounts that have an invoice
    print("\n🔍 Finding chains with NULL amounts...")
    cursor.execute("""
        SELECT id, chain_id, invoice_doc_id, order_doc_id, vendor_name
        FROM matched_document_chains
        WHERE total_amount IS NULL
          AND invoice_doc_id IS NOT NULL
    """)

    chains = cursor.fetchall()
    print(f"📄 Found {len(chains)} chains with NULL amounts\n")

    if not chains:
        print("✓ All chains already have amounts")
        conn.close()
        return

    # Update each chain
    updated = 0
    skipped = 0

    for chain_id_int, chain_id, invoice_doc_id, order_doc_id, vendor_name in chains:
        # Get invoice metadata
        cursor.execute("SELECT metadata FROM documents WHERE id = ?", (invoice_doc_id,))
        result = cursor.fetchone()

        if not result or not result[0]:
            print(f"⏭️  Chain #{chain_id_int} - No metadata for invoice #{invoice_doc_id}")
            skipped += 1
            continue

        try:
            metadata = json.loads(result[0])
            amount = metadata.get('amount_with_vat')

            if amount:
                # Update chain
                cursor.execute("""
                    UPDATE matched_document_chains
                    SET total_amount = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (amount, chain_id_int))
                conn.commit()

                print(f"✓ Chain #{chain_id_int} ({vendor_name or 'Unknown'}) - {amount} CZK (invoice #{invoice_doc_id})")
                updated += 1
            else:
                print(f"⏭️  Chain #{chain_id_int} - No amount in metadata (invoice #{invoice_doc_id})")
                skipped += 1

        except Exception as e:
            print(f"❌ Chain #{chain_id_int} - Error: {e}")
            skipped += 1

    conn.close()

    # Summary
    print("\n" + "="*80)
    print(f"✓ Successfully updated: {updated}")
    print(f"⏭️  Skipped (no amount): {skipped}")
    print(f"📄 Total processed: {len(chains)}")
    print("="*80)

if __name__ == "__main__":
    main()
