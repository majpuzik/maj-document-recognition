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
Quick script to scan Thunderbird IMAP mailboxes for 1000 emails
"""

import email
import email.utils
import logging
import mailbox
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def scan_mailbox_file(mailbox_path, limit=1000):
    """Scan a single mailbox file"""
    logger.info(f"Scanning mailbox: {mailbox_path}")
    logger.info(f"File size: {mailbox_path.stat().st_size / (1024*1024):.2f} MB")

    try:
        mbox = mailbox.mbox(str(mailbox_path))

        total_emails = 0
        emails_with_attachments = 0
        total_attachments = 0

        for idx, msg in enumerate(mbox):
            if idx >= limit:
                logger.info(f"Reached limit of {limit} emails")
                break

            total_emails += 1

            # Count attachments
            attachment_count = 0
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue

                filename = part.get_filename()
                if filename:
                    # Check if it's a document attachment
                    ext = Path(filename).suffix.lower()
                    if ext in ['.pdf', '.jpg', '.jpeg', '.png', '.docx', '.doc']:
                        attachment_count += 1

            if attachment_count > 0:
                emails_with_attachments += 1
                total_attachments += attachment_count

                sender = msg.get("From", "")
                subject = msg.get("Subject", "")
                date_str = msg.get("Date", "")

                if idx < 10:  # Show first 10 emails with attachments
                    logger.info(f"  Email {idx+1}: From={sender[:50]}, Subject={subject[:50]}, Attachments={attachment_count}")

            if (idx + 1) % 100 == 0:
                logger.info(f"  Processed {idx+1} emails... ({emails_with_attachments} with attachments)")

        logger.info(f"\nResults for {mailbox_path.name}:")
        logger.info(f"  Total emails scanned: {total_emails}")
        logger.info(f"  Emails with attachments: {emails_with_attachments}")
        logger.info(f"  Total attachments found: {total_attachments}")

        return {
            "mailbox": mailbox_path.name,
            "total_emails": total_emails,
            "emails_with_attachments": emails_with_attachments,
            "total_attachments": total_attachments
        }

    except Exception as e:
        logger.error(f"Error scanning mailbox: {e}", exc_info=True)
        return None

def main():
    # Thunderbird profile path
    profile_path = Path("/Users/m.a.j.puzik/Library/Thunderbird/Profiles/1oli4gwg.default-esr")

    # IMAP mailbox paths
    imap_dir = profile_path / "ImapMail/outlook.office365.com"

    mailboxes_to_scan = [
        imap_dir / "INBOX",
        imap_dir / "Archive",
        imap_dir / "Archivovat",
        imap_dir / "Sent-1",
    ]

    logger.info("=" * 80)
    logger.info("MAJ Document Recognition - Thunderbird Email Scanner")
    logger.info("=" * 80)
    logger.info(f"Profile: {profile_path}")
    logger.info(f"Scanning limit: 1000 emails per mailbox")
    logger.info("")

    total_results = {
        "total_emails": 0,
        "emails_with_attachments": 0,
        "total_attachments": 0
    }

    for mailbox_path in mailboxes_to_scan:
        if not mailbox_path.exists():
            logger.warning(f"Mailbox not found: {mailbox_path}")
            continue

        logger.info("")
        logger.info("-" * 80)
        result = scan_mailbox_file(mailbox_path, limit=1000)

        if result:
            total_results["total_emails"] += result["total_emails"]
            total_results["emails_with_attachments"] += result["emails_with_attachments"]
            total_results["total_attachments"] += result["total_attachments"]

    logger.info("")
    logger.info("=" * 80)
    logger.info("OVERALL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total emails scanned: {total_results['total_emails']}")
    logger.info(f"Emails with document attachments: {total_results['emails_with_attachments']}")
    logger.info(f"Total document attachments: {total_results['total_attachments']}")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
