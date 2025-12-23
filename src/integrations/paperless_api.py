"""
Paperless-NGX API integration
"""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional

import requests


class PaperlessAPI:
    """Integration with Paperless-NGX document management system"""

    def __init__(self, config: dict):
        """
        Initialize PaperlessAPI

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.paperless_config = config.get("paperless", {})

        self.base_url = self.paperless_config.get("url", "").rstrip("/")
        self.api_token = self.paperless_config.get("api_token", "")
        self.verify_ssl = self.paperless_config.get("verify_ssl", True)
        self.timeout = self.paperless_config.get("timeout", 30)

        self.headers = {
            "Authorization": f"Token {self.api_token}",
        }

        # Cache for IDs
        self._tag_cache = {}
        self._correspondent_cache = {}
        self._document_type_cache = {}

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        files: Dict = None,
    ) -> Dict:
        """
        Make API request to Paperless-NGX

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            files: Files to upload

        Returns:
            Response dictionary
        """
        url = f"{self.base_url}/api/{endpoint.lstrip('/')}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers if not files else {"Authorization": self.headers["Authorization"]},
                json=data if not files else None,
                data=data if files else None,
                files=files,
                verify=self.verify_ssl,
                timeout=self.timeout,
            )

            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code,
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "status_code": response.status_code,
                }

        except Exception as e:
            self.logger.error(f"API request error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def _calculate_checksum(self, file_path: str) -> str:
        """
        Calculate file checksum

        Args:
            file_path: Path to file

        Returns:
            MD5 checksum
        """
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def check_duplicate(self, file_path: str) -> Optional[Dict]:
        """
        Check if document already exists in Paperless

        Args:
            file_path: Path to file

        Returns:
            Existing document or None
        """
        if not self.paperless_config.get("check_duplicates", True):
            return None

        method = self.paperless_config.get("duplicate_check_method", "checksum")

        if method == "checksum":
            checksum = self._calculate_checksum(file_path)

            # Search by checksum
            result = self._make_request(
                "GET",
                f"documents/?checksum={checksum}",
            )

            if result.get("success") and result.get("data", {}).get("results"):
                return result["data"]["results"][0]

        return None

    def get_or_create_tag(self, tag_name: str) -> Optional[int]:
        """
        Get or create tag

        Args:
            tag_name: Tag name

        Returns:
            Tag ID or None
        """
        if tag_name in self._tag_cache:
            return self._tag_cache[tag_name]

        # Search for existing tag
        result = self._make_request("GET", f"tags/?name={tag_name}")

        if result.get("success"):
            results = result.get("data", {}).get("results", [])
            if results:
                tag_id = results[0]["id"]
                self._tag_cache[tag_name] = tag_id
                return tag_id

        # Create new tag
        if self.paperless_config.get("auto_create_tags", True):
            result = self._make_request(
                "POST",
                "tags/",
                data={"name": tag_name},
            )

            if result.get("success"):
                tag_id = result["data"]["id"]
                self._tag_cache[tag_name] = tag_id
                return tag_id

        return None

    def get_or_create_correspondent(self, correspondent_name: str) -> Optional[int]:
        """
        Get or create correspondent

        Args:
            correspondent_name: Correspondent name

        Returns:
            Correspondent ID or None
        """
        if correspondent_name in self._correspondent_cache:
            return self._correspondent_cache[correspondent_name]

        # Search for existing correspondent
        result = self._make_request("GET", f"correspondents/?name={correspondent_name}")

        if result.get("success"):
            results = result.get("data", {}).get("results", [])
            if results:
                correspondent_id = results[0]["id"]
                self._correspondent_cache[correspondent_name] = correspondent_id
                return correspondent_id

        # Create new correspondent
        if self.paperless_config.get("auto_create_correspondents", True):
            result = self._make_request(
                "POST",
                "correspondents/",
                data={"name": correspondent_name},
            )

            if result.get("success"):
                correspondent_id = result["data"]["id"]
                self._correspondent_cache[correspondent_name] = correspondent_id
                return correspondent_id

        return None

    def get_or_create_document_type(self, type_name: str) -> Optional[int]:
        """
        Get or create document type

        Args:
            type_name: Document type name

        Returns:
            Document type ID or None
        """
        if type_name in self._document_type_cache:
            return self._document_type_cache[type_name]

        # Search for existing document type
        result = self._make_request("GET", f"document_types/?name={type_name}")

        if result.get("success"):
            results = result.get("data", {}).get("results", [])
            if results:
                doc_type_id = results[0]["id"]
                self._document_type_cache[type_name] = doc_type_id
                return doc_type_id

        # Create new document type
        if self.paperless_config.get("auto_create_document_types", True):
            result = self._make_request(
                "POST",
                "document_types/",
                data={"name": type_name},
            )

            if result.get("success"):
                doc_type_id = result["data"]["id"]
                self._document_type_cache[type_name] = doc_type_id
                return doc_type_id

        return None

    def set_custom_field(self, document_id: int, field_id: int, value: str) -> bool:
        """
        Set custom field value on document

        Args:
            document_id: Paperless document ID
            field_id: Custom field ID
            value: Field value

        Returns:
            True if successful
        """
        try:
            # Get current document
            result = self._make_request("GET", f"documents/{document_id}/")
            if not result.get("success"):
                return False

            current_fields = result.get("data", {}).get("custom_fields", [])

            # Update or add field
            updated = False
            for field in current_fields:
                if field.get("field") == field_id:
                    field["value"] = value
                    updated = True
                    break

            if not updated:
                current_fields.append({"field": field_id, "value": value})

            # Update document
            update_result = self._make_request(
                "PATCH",
                f"documents/{document_id}/",
                data={"custom_fields": current_fields},
            )

            return update_result.get("success", False)

        except Exception as e:
            self.logger.error(f"Error setting custom field: {e}")
            return False

    def upload_document(
        self,
        file_path: str,
        title: Optional[str] = None,
        document_type: Optional[str] = None,
        correspondent: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> Dict:
        """
        Upload document to Paperless-NGX

        Args:
            file_path: Path to document file
            title: Document title
            document_type: Document type
            correspondent: Correspondent name
            tags: List of tag names
            source: Document source ("Email", "PC slozka", "Sken")

        Returns:
            Upload result dictionary
        """
        # Field ID pro zdroj_dokumentu
        ZDROJ_FIELD_ID = 149
        if not Path(file_path).exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }

        # Check for duplicates
        existing = self.check_duplicate(file_path)
        if existing:
            self.logger.info(f"Document already exists (ID: {existing['id']})")
            return {
                "success": True,
                "paperless_id": existing["id"],
                "duplicate": True,
            }

        try:
            # Prepare metadata
            metadata = {}

            if title:
                metadata["title"] = title

            if document_type:
                doc_type_id = self.get_or_create_document_type(document_type)
                if doc_type_id:
                    metadata["document_type"] = doc_type_id

            if correspondent:
                correspondent_id = self.get_or_create_correspondent(correspondent)
                if correspondent_id:
                    metadata["correspondent"] = correspondent_id

            if tags:
                tag_ids = []
                for tag_name in tags:
                    tag_id = self.get_or_create_tag(tag_name)
                    if tag_id:
                        tag_ids.append(tag_id)
                if tag_ids:
                    metadata["tags"] = tag_ids

            # Upload file
            with open(file_path, "rb") as f:
                files = {"document": f}

                result = self._make_request(
                    "POST",
                    "documents/post_document/",
                    data=metadata,
                    files=files,
                )

            if result.get("success"):
                paperless_id = result.get("data", {}).get("id")
                self.logger.info(f"Document uploaded successfully: {file_path}")

                # Set source field if provided
                if source and paperless_id:
                    self.set_custom_field(paperless_id, ZDROJ_FIELD_ID, source)
                    self.logger.info(f"Set zdroj_dokumentu={source} for document {paperless_id}")

                return {
                    "success": True,
                    "paperless_id": paperless_id,
                    "duplicate": False,
                }
            else:
                return result

        except Exception as e:
            self.logger.error(f"Error uploading document: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def test_connection(self) -> bool:
        """
        Test connection to Paperless-NGX

        Returns:
            True if connection successful
        """
        result = self._make_request("GET", "documents/?page_size=1")
        return result.get("success", False)
