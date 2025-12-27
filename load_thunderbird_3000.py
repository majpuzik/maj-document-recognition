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
Load 3000 latest documents from Thunderbird
"""

import sys
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
    """Load 3000 documents from Thunderbird and process them"""

    print("=" * 70)
    print("📨 THUNDERBIRD DOCUMENT LOADER")
    print("=" * 70)
    print()
    print("📊 Limit: 3000 documents")
    print("📅 Latest documents first")
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

        # Show sample of extracted documents
        if result:
            print("📄 Sample documents:")
            for i, doc_path in enumerate(result[:10], 1):
                print(f"   {i}. {Path(doc_path).name}")

            if len(result) > 10:
                print(f"   ... and {len(result) - 10} more")

        print()
        print("🎯 Next step: Run adaptive_parallel_OPTIMIZED_v2.2.py to process these documents")
        print()

        return result

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
