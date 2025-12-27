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

"""Label Loxone emails as loxone_statistics"""
import json
import os
from datetime import datetime
from pathlib import Path

FAILED_DIR = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output")
RESULTS_DIR = FAILED_DIR / "phase1_results"

loxone_count = 0
other_failed = []

# Process all failed files
for failed_file in FAILED_DIR.glob("phase1_failed_*.jsonl"):
    with open(failed_file) as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            
            # Check if Loxone
            from_addr = record.get("metadata", {}).get("from", "")
            if "loxonecloud.com" in from_addr.lower():
                # Create result for Loxone
                email_id = record["email_id"]
                result = {
                    "email_id": email_id,
                    "doc_type": "loxone_statistics",
                    "extracted_fields": {
                        "doc_typ": "loxone_statistics",
                        "email_from": record["metadata"].get("from", ""),
                        "email_to": record["metadata"].get("to", ""),
                        "email_subject": record["metadata"].get("subject", ""),
                        "datum_dokumentu": record["metadata"].get("date", ""),
                        "protistrana_nazev": "Loxone",
                        "kategorie": "automatické notifikace",
                        "ai_summary": "Automatická statistika z Loxone home automation systému"
                    },
                    "source": "loxone_labeling",
                    "timestamp": datetime.now().isoformat()
                }
                
                # Save result
                result_path = RESULTS_DIR / f"{email_id}.json"
                with open(result_path, "w") as rf:
                    json.dump(result, rf, ensure_ascii=False, indent=2)
                loxone_count += 1
            else:
                other_failed.append(record)

# Save non-Loxone failures for Phase 2
with open(FAILED_DIR / "phase2_to_process.jsonl", "w") as f:
    for record in other_failed:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Loxone labeled: {loxone_count}")
print(f"Non-Loxone for Phase 2: {len(other_failed)}")
