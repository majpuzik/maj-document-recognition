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
Thunderbird integration example
"""

import yaml
from pathlib import Path

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.thunderbird import ThunderbirdIntegration


def main():
    """Thunderbird example"""

    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    print("MAJ Document Recognition - Thunderbird Integration")
    print("=" * 50)

    # Initialize
    print("\nInitializing...")
    db = DatabaseManager(config)
    processor = DocumentProcessor(config)
    classifier = AIClassifier(config, db)
    thunderbird = ThunderbirdIntegration(config)

    # Scan emails
    days = int(input("\nEnter number of days to scan (30, 999999 for all): "))

    print(f"\nScanning Thunderbird emails from last {days} days...")
    emails = thunderbird.scan_emails(days_back=days)

    print(f"Found {len(emails)} emails with attachments")

    if not emails:
        print("No emails found!")
        return

    # Group by sender
    grouped = thunderbird.group_by_sender(emails)

    print(f"\nEmails grouped by {len(grouped)} senders:")
    for sender, sender_emails in grouped.items():
        print(f"  - {sender}: {len(sender_emails)} emails")

    # Process attachments
    process = input("\nProcess all attachments? (y/n): ")

    if process.lower() != 'y':
        print("Cancelled.")
        return

    total_attachments = 0
    processed = 0

    for email in emails:
        print(f"\nEmail: {email.get('subject')}")
        print(f"From: {email.get('sender')}")

        for attachment in email.get("attachments", []):
            total_attachments += 1
            print(f"  Processing: {Path(attachment).name}")

            try:
                # OCR
                ocr_result = processor.process_document(attachment)

                if not ocr_result.get("success"):
                    print(f"    ✗ OCR failed")
                    continue

                # Classify
                classification = classifier.classify(
                    ocr_result.get("text", ""),
                    ocr_result.get("metadata", {})
                )

                # Save
                doc_id = db.insert_document(
                    file_path=attachment,
                    ocr_text=ocr_result.get("text", ""),
                    ocr_confidence=ocr_result.get("confidence", 0),
                    document_type=classification.get("type"),
                    ai_confidence=classification.get("confidence", 0),
                    sender=email.get("sender"),
                    subject=email.get("subject"),
                    date_received=email.get("date")
                )

                print(f"    ✓ {classification.get('type')} ({classification.get('confidence', 0):.2%}) [ID: {doc_id}]")
                processed += 1

            except Exception as e:
                print(f"    ✗ Error: {e}")

    # Cleanup
    print("\nCleaning up temporary files...")
    thunderbird.cleanup_temp_files()

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total emails: {len(emails)}")
    print(f"Total attachments: {total_attachments}")
    print(f"Processed: {processed}")

    stats = db.get_statistics()
    print(f"Total documents in database: {stats.get('total_documents', 0)}")


if __name__ == "__main__":
    main()
