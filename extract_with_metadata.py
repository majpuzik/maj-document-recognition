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
Extract documents from Thunderbird WITH email metadata
Saves both files and metadata.json for later processing
"""

import sys
import json
from pathlib import Path
import importlib.util

# Import adaptive_parallel_OPTIMIZED_v2.2 module
spec = importlib.util.spec_from_file_location(
    "adaptive_v2_2",
    Path(__file__).parent / "adaptive_parallel_OPTIMIZED_v2.2.py"
)
adaptive_v2_2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adaptive_v2_2)

def main():
    """Extract documents from Thunderbird and save metadata"""

    print("=" * 70)
    print("📨 THUNDERBIRD EXTRACTION WITH METADATA")
    print("=" * 70)
    print()
    print("📊 Limit: 3000 documents")
    print("📅 Latest documents first")
    print("💾 Saving metadata to JSON")
    print()

    # Thunderbird profile path
    profile_path = Path.home() / "Library" / "Thunderbird" / "Profiles"

    # Find first profile
    profiles = list(profile_path.glob("*.default*"))
    if not profiles:
        print("❌ No Thunderbird profile found")
        sys.exit(1)

    profile = profiles[0]
    print(f"📁 Profile: {profile.name}")
    print()

    # Temp directory for attachments
    temp_dir = Path(__file__).parent / "temp_attachments"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Extract documents from Thunderbird
        print("🔍 Extracting documents from Thunderbird...")
        print()

        result = adaptive_v2_2.extract_from_multiple_mailboxes(
            profile_path=profile,  # Pass as Path object
            temp_dir=temp_dir,     # Pass as Path object
            limit=3000,
            max_size_mb=3
        )

        print()
        print("=" * 70)
        print("✅ EXTRACTION COMPLETE")
        print("=" * 70)
        print(f"📊 Total extracted: {len(result)} documents")
        print()

        # Save metadata to JSON
        metadata_file = Path(__file__).parent / "attachments_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"💾 Metadata saved to: {metadata_file.name}")
        print()

        # Show sample of extracted documents
        if result:
            print("📄 Sample documents with metadata:")
            for i, doc in enumerate(result[:5], 1):
                print(f"\n   {i}. {doc['filename']}")
                print(f"      📧 From: {doc.get('sender', 'N/A')[:50]}")
                print(f"      💬 Subject: {doc.get('subject', 'N/A')[:50]}")
                print(f"      📁 Mailbox: {doc.get('mailbox', 'N/A')}")

            if len(result) > 5:
                print(f"\n   ... and {len(result) - 5} more")

        print()
        print("🎯 Next step: Run process_with_metadata.py to process these documents")
        print()

        return result

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
