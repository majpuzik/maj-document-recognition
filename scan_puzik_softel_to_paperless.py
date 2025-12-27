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
Scan puzik@softel.cz mailbox and upload documents to Paperless
Owner: puzik

Version: 1.1.0
Changelog:
  - 1.1.0 (2025-12-23): Fixed encoding error for 'unknown-8bit' charset
  - 1.0.0 (2025-12-23): Initial version
"""

__version__ = "1.1.0"

import email
import email.utils
import hashlib
import logging
import mailbox
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from email.header import decode_header as email_decode_header

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paperless configuration
PAPERLESS_URL = "http://100.96.204.120:8020/api"
PAPERLESS_TOKEN = "e264c40b31756898bcb258d346c891a6d1b9d1be"
OWNER_USERNAME = "puzik"

# Mailbox path for puzik@softel.cz
MAILBOX_PATH = Path("/Users/m.a.j.puzik/Library/Thunderbird/Profiles/1oli4gwg.default-esr/ImapMail/email.active24-3.com/INBOX")

# Alternative path on external drive
EXTERNAL_MAILBOX_PATH = Path("/Volumes/TB501Pro Media/Thunderbird/Profiles/1oli4gwg.default-esr/ImapMail/email.active24-3.com/INBOX")

# Allowed attachment types
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.docx', '.doc', '.xlsx', '.xls'}


def decode_header(header: str) -> str:
    """Decode email header with robust encoding handling"""
    if not header:
        return ""

    try:
        decoded_parts = email_decode_header(header)
    except Exception:
        return str(header)

    decoded_str = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            # Handle unknown or invalid encodings
            try:
                if encoding and encoding.lower() in ('unknown-8bit', 'unknown'):
                    encoding = 'utf-8'
                decoded_str += part.decode(encoding or "utf-8", errors="ignore")
            except (LookupError, UnicodeDecodeError):
                decoded_str += part.decode("utf-8", errors="ignore")
        else:
            decoded_str += str(part)

    return decoded_str


def get_owner_id(session: requests.Session) -> int:
    """Get Paperless user ID for puzik"""
    try:
        resp = session.get(
            f"{PAPERLESS_URL}/users/",
            headers={"Authorization": f"Token {PAPERLESS_TOKEN}"}
        )
        resp.raise_for_status()
        data = resp.json()

        for user in data.get("results", []):
            if user.get("username") == OWNER_USERNAME:
                logger.info(f"Found owner '{OWNER_USERNAME}' with ID: {user['id']}")
                return user["id"]

        logger.warning(f"Owner '{OWNER_USERNAME}' not found!")
        return None
    except Exception as e:
        logger.error(f"Error getting owner ID: {e}")
        return None


def get_correspondent_id(session: requests.Session, email_address: str) -> int:
    """Get or create correspondent for email sender"""
    if not email_address:
        return None

    # Extract email from format "Name <email@domain.com>"
    if "<" in email_address and ">" in email_address:
        email_clean = email_address.split("<")[1].split(">")[0]
    else:
        email_clean = email_address

    try:
        # Search for existing correspondent
        resp = session.get(
            f"{PAPERLESS_URL}/correspondents/",
            params={"name__iexact": email_clean},
            headers={"Authorization": f"Token {PAPERLESS_TOKEN}"}
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("results"):
            return data["results"][0]["id"]

        # Create new correspondent
        resp = session.post(
            f"{PAPERLESS_URL}/correspondents/",
            json={"name": email_clean},
            headers={"Authorization": f"Token {PAPERLESS_TOKEN}"}
        )
        if resp.status_code in (200, 201):
            return resp.json().get("id")

    except Exception as e:
        logger.debug(f"Error with correspondent: {e}")

    return None


def upload_to_paperless(
    session: requests.Session,
    file_path: Path,
    title: str,
    correspondent_id: int = None,
    owner_id: int = None,
    created_date: str = None
) -> dict:
    """Upload document to Paperless"""
    try:
        with open(file_path, "rb") as f:
            files = {"document": (file_path.name, f)}
            data = {"title": title}

            if correspondent_id:
                data["correspondent"] = correspondent_id
            if owner_id:
                data["owner"] = owner_id
            if created_date:
                data["created"] = created_date

            resp = session.post(
                f"{PAPERLESS_URL}/documents/post_document/",
                files=files,
                data=data,
                headers={"Authorization": f"Token {PAPERLESS_TOKEN}"}
            )

            if resp.status_code in (200, 202):
                return {"success": True, "task_id": resp.text.strip('"')}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def scan_and_upload(mailbox_path: Path, limit: int = None):
    """Scan mailbox and upload attachments to Paperless"""

    if not mailbox_path.exists():
        logger.error(f"Mailbox not found: {mailbox_path}")
        return

    logger.info(f"Scanning mailbox: {mailbox_path}")
    logger.info(f"File size: {mailbox_path.stat().st_size / (1024*1024):.2f} MB")

    session = requests.Session()
    owner_id = get_owner_id(session)

    if not owner_id:
        logger.error("Cannot proceed without owner ID")
        return

    stats = {
        "total_emails": 0,
        "emails_with_attachments": 0,
        "attachments_uploaded": 0,
        "attachments_failed": 0,
        "duplicates_skipped": 0
    }

    uploaded_hashes = set()  # Track uploaded files to avoid duplicates

    try:
        mbox = mailbox.mbox(str(mailbox_path))

        for idx, msg in enumerate(mbox):
            if limit and idx >= limit:
                logger.info(f"Reached limit of {limit} emails")
                break

            stats["total_emails"] += 1

            if (idx + 1) % 100 == 0:
                logger.info(f"  Processed {idx+1} emails... ({stats['attachments_uploaded']} uploaded)")

            sender = decode_header(msg.get("From", ""))
            subject = decode_header(msg.get("Subject", ""))
            date_str = msg.get("Date", "")

            # Parse date
            created_date = None
            try:
                parsed_date = email.utils.parsedate_to_datetime(date_str)
                created_date = parsed_date.strftime("%Y-%m-%d")
            except:
                pass

            # Get correspondent
            correspondent_id = get_correspondent_id(session, sender)

            # Check for attachments
            has_attachment = False

            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue

                filename = part.get_filename()
                if not filename:
                    continue

                # Decode filename
                filename = decode_header(filename)
                ext = Path(filename).suffix.lower()

                if ext not in ALLOWED_EXTENSIONS:
                    continue

                has_attachment = True

                # Get attachment content
                try:
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue

                    # Calculate hash to detect duplicates
                    file_hash = hashlib.md5(payload).hexdigest()
                    if file_hash in uploaded_hashes:
                        stats["duplicates_skipped"] += 1
                        continue

                    # Save to temp file
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                        tmp.write(payload)
                        tmp_path = Path(tmp.name)

                    # Create title from subject + filename
                    title = f"{subject[:100]} - {filename}" if subject else filename

                    # Upload to Paperless
                    result = upload_to_paperless(
                        session=session,
                        file_path=tmp_path,
                        title=title,
                        correspondent_id=correspondent_id,
                        owner_id=owner_id,
                        created_date=created_date
                    )

                    # Cleanup temp file
                    tmp_path.unlink()

                    if result["success"]:
                        stats["attachments_uploaded"] += 1
                        uploaded_hashes.add(file_hash)
                        logger.debug(f"Uploaded: {filename}")
                    else:
                        stats["attachments_failed"] += 1
                        logger.warning(f"Failed to upload {filename}: {result.get('error')}")

                except Exception as e:
                    stats["attachments_failed"] += 1
                    logger.error(f"Error processing attachment {filename}: {e}")

            if has_attachment:
                stats["emails_with_attachments"] += 1

        # Final summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("SCAN COMPLETE - puzik@softel.cz → Paperless (owner=puzik)")
        logger.info("=" * 80)
        logger.info(f"Total emails scanned: {stats['total_emails']}")
        logger.info(f"Emails with attachments: {stats['emails_with_attachments']}")
        logger.info(f"Attachments uploaded: {stats['attachments_uploaded']}")
        logger.info(f"Attachments failed: {stats['attachments_failed']}")
        logger.info(f"Duplicates skipped: {stats['duplicates_skipped']}")
        logger.info("=" * 80)

        return stats

    except Exception as e:
        logger.error(f"Error scanning mailbox: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    # Check which mailbox path exists
    if MAILBOX_PATH.exists():
        mailbox_path = MAILBOX_PATH
    elif EXTERNAL_MAILBOX_PATH.exists():
        mailbox_path = EXTERNAL_MAILBOX_PATH
    else:
        logger.error("Mailbox not found at either location!")
        logger.error(f"  Local: {MAILBOX_PATH}")
        logger.error(f"  External: {EXTERNAL_MAILBOX_PATH}")
        sys.exit(1)

    # Parse optional limit argument
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            logger.info(f"Limiting to {limit} emails")
        except:
            pass

    scan_and_upload(mailbox_path, limit=limit)
