"""
Blacklist/Whitelist management for known senders
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, List, Set


class BlacklistWhitelist:
    """Manage blacklist and whitelist for email senders and domains"""

    def __init__(self, config: dict):
        """
        Initialize BlacklistWhitelist

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.lists_config = config.get("lists", {})

        self.blacklist_file = Path(self.lists_config.get("blacklist_file", "config/blacklist.pkl"))
        self.whitelist_file = Path(self.lists_config.get("whitelist_file", "config/whitelist.pkl"))

        # Ensure parent directories exist
        self.blacklist_file.parent.mkdir(parents=True, exist_ok=True)
        self.whitelist_file.parent.mkdir(parents=True, exist_ok=True)

        # Load lists
        self.blacklist: Set[str] = self._load_list(self.blacklist_file)
        self.whitelist: Set[str] = self._load_list(self.whitelist_file)

        self.logger.info(
            f"Loaded {len(self.blacklist)} blacklist and {len(self.whitelist)} whitelist entries"
        )

    def _load_list(self, file_path: Path) -> Set[str]:
        """
        Load list from pickle file

        Args:
            file_path: Path to pickle file

        Returns:
            Set of email addresses/domains
        """
        if file_path.exists():
            try:
                with open(file_path, "rb") as f:
                    data = pickle.load(f)
                    if isinstance(data, set):
                        return data
                    elif isinstance(data, list):
                        return set(data)
                    else:
                        self.logger.warning(f"Invalid list format in {file_path}")
                        return set()
            except Exception as e:
                self.logger.error(f"Error loading list from {file_path}: {e}")
                return set()
        else:
            return set()

    def _save_list(self, file_path: Path, data: Set[str]) -> bool:
        """
        Save list to pickle file

        Args:
            file_path: Path to pickle file
            data: Set of email addresses/domains

        Returns:
            True if successful
        """
        try:
            with open(file_path, "wb") as f:
                pickle.dump(data, f)
            return True
        except Exception as e:
            self.logger.error(f"Error saving list to {file_path}: {e}")
            return False

    def _extract_domain(self, email: str) -> str:
        """
        Extract domain from email address

        Args:
            email: Email address

        Returns:
            Domain part
        """
        if "@" in email:
            return email.split("@")[1].lower()
        return email.lower()

    def is_blacklisted(self, email: str) -> bool:
        """
        Check if email/domain is blacklisted

        Args:
            email: Email address

        Returns:
            True if blacklisted
        """
        email_lower = email.lower()
        domain = self._extract_domain(email)

        return email_lower in self.blacklist or domain in self.blacklist

    def is_whitelisted(self, email: str) -> bool:
        """
        Check if email/domain is whitelisted

        Args:
            email: Email address

        Returns:
            True if whitelisted
        """
        email_lower = email.lower()
        domain = self._extract_domain(email)

        return email_lower in self.whitelist or domain in self.whitelist

    def add_to_blacklist(self, email: str) -> bool:
        """
        Add email/domain to blacklist

        Args:
            email: Email address or domain

        Returns:
            True if successful
        """
        email_lower = email.lower()
        self.blacklist.add(email_lower)

        # Remove from whitelist if present
        if email_lower in self.whitelist:
            self.whitelist.remove(email_lower)
            self._save_list(self.whitelist_file, self.whitelist)

        return self._save_list(self.blacklist_file, self.blacklist)

    def add_to_whitelist(self, email: str) -> bool:
        """
        Add email/domain to whitelist

        Args:
            email: Email address or domain

        Returns:
            True if successful
        """
        email_lower = email.lower()
        self.whitelist.add(email_lower)

        # Remove from blacklist if present
        if email_lower in self.blacklist:
            self.blacklist.remove(email_lower)
            self._save_list(self.blacklist_file, self.blacklist)

        return self._save_list(self.whitelist_file, self.whitelist)

    def remove_from_blacklist(self, email: str) -> bool:
        """
        Remove email/domain from blacklist

        Args:
            email: Email address or domain

        Returns:
            True if successful
        """
        email_lower = email.lower()
        if email_lower in self.blacklist:
            self.blacklist.remove(email_lower)
            return self._save_list(self.blacklist_file, self.blacklist)
        return False

    def remove_from_whitelist(self, email: str) -> bool:
        """
        Remove email/domain from whitelist

        Args:
            email: Email address or domain

        Returns:
            True if successful
        """
        email_lower = email.lower()
        if email_lower in self.whitelist:
            self.whitelist.remove(email_lower)
            return self._save_list(self.whitelist_file, self.whitelist)
        return False

    def get_blacklist(self) -> List[str]:
        """
        Get all blacklist entries

        Returns:
            List of blacklisted emails/domains
        """
        return sorted(list(self.blacklist))

    def get_whitelist(self) -> List[str]:
        """
        Get all whitelist entries

        Returns:
            List of whitelisted emails/domains
        """
        return sorted(list(self.whitelist))

    def auto_update_from_classifications(self, classifications: List[Dict]) -> None:
        """
        Automatically update lists based on classifications

        Args:
            classifications: List of classification results
        """
        if not self.lists_config.get("auto_update", True):
            return

        for classification in classifications:
            sender = classification.get("sender", "").lower()
            if not sender:
                continue

            doc_type = classification.get("type", "")

            # Blacklist known advertisers
            if doc_type == "reklama" and classification.get("confidence", 0) > 0.8:
                if not self.is_blacklisted(sender):
                    self.logger.info(f"Auto-blacklisting advertiser: {sender}")
                    self.add_to_blacklist(sender)

            # Whitelist known correspondents
            elif doc_type in ["faktura", "stvrzenka", "bankovni_vypis"] and classification.get("confidence", 0) > 0.9:
                if not self.is_whitelisted(sender):
                    self.logger.info(f"Auto-whitelisting correspondent: {sender}")
                    self.add_to_whitelist(sender)

    def export_to_dict(self) -> Dict:
        """
        Export lists to dictionary

        Returns:
            Dictionary with blacklist and whitelist
        """
        return {
            "blacklist": self.get_blacklist(),
            "whitelist": self.get_whitelist(),
        }

    def import_from_dict(self, data: Dict) -> bool:
        """
        Import lists from dictionary

        Args:
            data: Dictionary with blacklist and whitelist

        Returns:
            True if successful
        """
        try:
            if "blacklist" in data:
                self.blacklist = set(data["blacklist"])
                self._save_list(self.blacklist_file, self.blacklist)

            if "whitelist" in data:
                self.whitelist = set(data["whitelist"])
                self._save_list(self.whitelist_file, self.whitelist)

            return True
        except Exception as e:
            self.logger.error(f"Error importing lists: {e}")
            return False
