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
Simpler version - no dependencies on adaptive module
"""

import sys
import json
import mailbox
from pathlib import Path
from datetime import datetime

def extract_from_thunderbird(profile_path, temp_dir, limit=3000, max_size_mb=3):
    """Extract attachments from Thunderbird mailboxes"""

    mailboxes = [
        profile_path / "ImapMail/outlook.office365.com/INBOX",
        profile_path / "ImapMail/outlook.office365.com/Archive",
        profile_path / "ImapMail/outlook.office365.com/Archivovat",
        profile_path / "ImapMail/outlook.office365.com/Sent-1",
    ]

    all_attachments = []
    max_size_bytes = max_size_mb * 1024 * 1024

    for mailbox_path in mailboxes:
        if not mailbox_path.exists():
            print(f"⚠️ Mailbox not found: {mailbox_path.name}")
            continue

        if len(all_attachments) >= limit:
            break

        print(f"\n📬 Scanning: {mailbox_path.name}")

        try:
            mbox = mailbox.mbox(str(mailbox_path))
            count = 0

            for idx, msg in enumerate(mbox):
                if len(all_attachments) >= limit:
                    break

                sender = str(msg.get("From", ""))
                subject = str(msg.get("Subject", ""))
                date = str(msg.get("Date", ""))

                for part in msg.walk():
                    if len(all_attachments) >= limit:
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
                        payload = part.get_payload(decode=True)
                        if len(payload) > max_size_bytes:
                            continue

                        timestamp = int(datetime.now().timestamp() * 1000000)
                        safe_filename = f"doc_{len(all_attachments)}_{timestamp}_{filename}"
                        attachment_path = temp_dir / safe_filename

                        with open(attachment_path, "wb") as f:
                            f.write(payload)

                        all_attachments.append({
                            "path": str(attachment_path),
                            "filename": filename,
                            "sender": sender,
                            "subject": subject,
                            "date": date,
                            "mailbox": mailbox_path.name,
                            "size_kb": len(payload) / 1024
                        })

                        count += 1

                        if count % 50 == 0:
                            print(f"  [{len(all_attachments)}/{limit}] extracted from {mailbox_path.name}")

                    except Exception as e:
                        pass  # Skip problematic attachments

            print(f"✓ {mailbox_path.name}: {count} attachments")

        except Exception as e:
            print(f"❌ Mailbox error {mailbox_path.name}: {e}")

    return all_attachments


def main():
    """Extract documents from Thunderbird and save metadata"""

    print("=" * 70)
    print("📨 THUNDERBIRD EXTRACTION WITH METADATA")
    print("=" * 70)
    print()
    print("📊 Limit: 5000 documents")
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

        result = extract_from_thunderbird(
            profile_path=profile,
            temp_dir=temp_dir,
            limit=5000,
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
