"""
Thunderbird email integration
"""

import email
import logging
import os
from datetime import datetime, timedelta
from email.header import decode_header
from pathlib import Path
from typing import Dict, List, Optional

import mailbox


class ThunderbirdIntegration:
    """Integration with Thunderbird mail client"""

    def __init__(self, config: dict):
        """
        Initialize ThunderbirdIntegration

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.tb_config = config.get("thunderbird", {})

        self.profile_path = self._find_profile_path()
        self.temp_dir = Path(config.get("storage", {}).get("temp_folder", "data/temp"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _find_profile_path(self) -> Optional[Path]:
        """
        Find Thunderbird profile path

        Returns:
            Path to Thunderbird profile or None
        """
        configured_path = self.tb_config.get("profile_path")
        if configured_path and Path(configured_path).exists():
            return Path(configured_path)

        # Auto-detect on macOS
        home = Path.home()
        possible_paths = [
            home / "Library/Thunderbird/Profiles",
            home / ".thunderbird",  # Linux
            home / "AppData/Roaming/Thunderbird/Profiles",  # Windows
        ]

        for base_path in possible_paths:
            if base_path.exists():
                # Find default profile
                profiles = list(base_path.glob("*.default*"))
                if profiles:
                    self.logger.info(f"Found Thunderbird profile: {profiles[0]}")
                    return profiles[0]

        self.logger.warning("Could not auto-detect Thunderbird profile")
        return None

    def _decode_header(self, header: str) -> str:
        """
        Decode email header

        Args:
            header: Email header

        Returns:
            Decoded string
        """
        if not header:
            return ""

        decoded_parts = decode_header(header)
        decoded_str = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_str += part.decode(encoding or "utf-8", errors="ignore")
            else:
                decoded_str += part

        return decoded_str

    def _extract_attachments(self, msg: email.message.Message, email_id: str) -> List[str]:
        """
        Extract attachments from email message

        Args:
            msg: Email message object
            email_id: Unique email identifier

        Returns:
            List of saved attachment file paths
        """
        attachments = []
        allowed_extensions = self.tb_config.get("attachment_types", [".pdf", ".jpg", ".jpeg", ".png", ".docx"])

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue

            filename = part.get_filename()
            if not filename:
                continue

            # Check extension
            ext = Path(filename).suffix.lower()
            if ext not in allowed_extensions:
                continue

            try:
                # Decode filename
                filename = self._decode_header(filename)

                # Create safe filename
                safe_filename = f"{email_id}_{filename}"
                attachment_path = self.temp_dir / safe_filename

                # Save attachment
                with open(attachment_path, "wb") as f:
                    f.write(part.get_payload(decode=True))

                attachments.append(str(attachment_path))
                self.logger.debug(f"Extracted attachment: {filename}")

            except Exception as e:
                self.logger.error(f"Error extracting attachment {filename}: {e}")

        return attachments

    def scan_emails(
        self,
        days_back: Optional[int] = None,
        mailboxes: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Scan Thunderbird emails for attachments

        Args:
            days_back: Number of days to look back (None = use config)
            mailboxes: List of mailboxes to scan (None = use config)

        Returns:
            List of email dictionaries with attachments
        """
        if not self.profile_path:
            self.logger.error("No Thunderbird profile path available")
            return []

        # Get parameters
        if days_back is None:
            days_back = self.tb_config.get("max_days_back", 30)

        if mailboxes is None:
            mailboxes = self.tb_config.get("mailboxes", ["INBOX"])

        # Calculate cutoff date
        if days_back == 999999:
            cutoff_date = datetime(1970, 1, 1)
        else:
            cutoff_date = datetime.now() - timedelta(days=days_back)

        self.logger.info(f"Scanning emails from {cutoff_date.date()} in mailboxes: {mailboxes}")

        results = []

        # Scan mailboxes
        mail_dir = self.profile_path / "Mail" / "Local Folders"

        for mailbox_name in mailboxes:
            mailbox_file = mail_dir / mailbox_name

            if not mailbox_file.exists():
                # Try without extension
                mailbox_file = mail_dir / f"{mailbox_name}.msf"
                if not mailbox_file.exists():
                    self.logger.warning(f"Mailbox not found: {mailbox_name}")
                    continue

            try:
                self.logger.info(f"Processing mailbox: {mailbox_name}")
                mbox = mailbox.mbox(str(mailbox_file))

                for idx, msg in enumerate(mbox):
                    # Parse date
                    date_str = msg.get("Date", "")
                    try:
                        msg_date = email.utils.parsedate_to_datetime(date_str)
                        if msg_date.replace(tzinfo=None) < cutoff_date:
                            continue
                    except Exception:
                        pass  # Include if date parsing fails

                    # Extract attachments
                    email_id = f"{mailbox_name}_{idx}_{int(datetime.now().timestamp())}"
                    attachments = self._extract_attachments(msg, email_id)

                    if attachments:
                        results.append({
                            "id": email_id,
                            "sender": self._decode_header(msg.get("From", "")),
                            "recipient": self._decode_header(msg.get("To", "")),
                            "subject": self._decode_header(msg.get("Subject", "")),
                            "date": date_str,
                            "mailbox": mailbox_name,
                            "attachments": attachments,
                        })

            except Exception as e:
                self.logger.error(f"Error processing mailbox {mailbox_name}: {e}", exc_info=True)

        self.logger.info(f"Found {len(results)} emails with attachments")
        return results

    def group_by_sender(self, emails: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group emails by sender

        Args:
            emails: List of email dictionaries

        Returns:
            Dictionary mapping sender to list of emails
        """
        grouped = {}

        for email_data in emails:
            sender = email_data.get("sender", "unknown")

            if sender not in grouped:
                grouped[sender] = []

            grouped[sender].append(email_data)

        return grouped

    def cleanup_temp_files(self) -> None:
        """Remove temporary attachment files"""
        try:
            for file in self.temp_dir.glob("*"):
                file.unlink()
            self.logger.info("Temporary files cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up temp files: {e}")
