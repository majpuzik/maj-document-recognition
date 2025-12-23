#!/usr/bin/env python3
"""
Main entry point for MAJ Document Recognition System
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import yaml

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.thunderbird import ThunderbirdIntegration
from src.integrations.paperless_api import PaperlessAPI


def setup_logging(config: dict) -> None:
    """Setup logging configuration"""
    log_level = getattr(logging, config.get("app", {}).get("log_level", "INFO"))
    log_file = config.get("app", {}).get("log_file", "logs/app.log")

    # Create logs directory
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to load config from {config_path}: {e}")
        return {}


def process_document(
    file_path: str,
    config: dict,
    db: DatabaseManager,
    processor: DocumentProcessor,
    classifier: AIClassifier,
    source: str = "PC slozka",
    email_from: str = None,
    email_to: str = None,
    email_subject: str = None,
) -> None:
    """Process a single document"""
    logger = logging.getLogger(__name__)
    logger.info(f"Processing document: {file_path}")

    try:
        # Extract text using OCR
        logger.info("Extracting text with OCR...")
        ocr_result = processor.process_document(file_path)

        if not ocr_result.get("success"):
            logger.error(f"OCR failed: {ocr_result.get('error')}")
            return

        # Classify document
        logger.info("Classifying document with AI...")
        classification = classifier.classify(
            ocr_result.get("text", ""),
            ocr_result.get("metadata", {}),
        )

        # Build metadata with email info
        doc_metadata = classification.get("metadata", {}) or {}
        if email_from:
            doc_metadata["email_from"] = email_from
        if email_to:
            doc_metadata["email_to"] = email_to
        if email_subject:
            doc_metadata["email_subject"] = email_subject

        # Save to database
        logger.info("Saving to database...")
        doc_id = db.insert_document(
            file_path=file_path,
            ocr_text=ocr_result.get("text", ""),
            ocr_confidence=ocr_result.get("confidence", 0),
            document_type=classification.get("type"),
            ai_confidence=classification.get("confidence", 0),
            metadata=doc_metadata,
            source=source,
            sender=email_from,
            subject=email_subject,
        )

        logger.info(f"Document processed successfully (ID: {doc_id})")
        logger.info(f"Type: {classification.get('type')}, Confidence: {classification.get('confidence'):.2%}")

    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)


def scan_thunderbird(
    config: dict,
    db: DatabaseManager,
    processor: DocumentProcessor,
    classifier: AIClassifier,
    days_back: Optional[int] = None,
) -> None:
    """Scan Thunderbird mailbox for documents"""
    logger = logging.getLogger(__name__)
    logger.info("Starting Thunderbird scan...")

    try:
        tb = ThunderbirdIntegration(config)
        emails = tb.scan_emails(days_back=days_back)

        logger.info(f"Found {len(emails)} emails with attachments")

        for email_data in emails:
            logger.info(f"Processing email from {email_data.get('sender')} - {email_data.get('subject')}")

            for attachment in email_data.get("attachments", []):
                process_document(
                    file_path=attachment,
                    config=config,
                    db=db,
                    processor=processor,
                    classifier=classifier,
                    source="Email",
                    email_from=email_data.get("sender"),
                    email_to=email_data.get("recipient"),
                    email_subject=email_data.get("subject"),
                )

        logger.info("Thunderbird scan completed")

    except Exception as e:
        logger.error(f"Error scanning Thunderbird: {e}", exc_info=True)


def export_to_paperless(config: dict, db: DatabaseManager) -> None:
    """Export documents to Paperless-NGX"""
    logger = logging.getLogger(__name__)
    logger.info("Starting Paperless-NGX export...")

    try:
        paperless = PaperlessAPI(config)

        # Get unsynced documents
        documents = db.get_unsynced_documents()
        logger.info(f"Found {len(documents)} documents to export")

        for doc in documents:
            logger.info(f"Exporting document {doc['id']}: {doc['file_path']}")

            # Extract email fields from metadata
            metadata = doc.get("metadata") or {}
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            email_from = doc.get("sender") or metadata.get("email_from")
            email_to = metadata.get("email_to")
            email_subject = doc.get("subject") or metadata.get("email_subject")

            # Resolve owner from recipient email
            owner_id = paperless.resolve_owner_from_email(email_to) if email_to else None

            result = paperless.upload_document(
                file_path=doc["file_path"],
                title=doc.get("title"),
                document_type=doc.get("document_type"),
                tags=doc.get("tags", []),
                correspondent=doc.get("correspondent"),
                source=doc.get("source", "PC slozka"),
                email_from=email_from,
                email_to=email_to,
                email_subject=email_subject,
                owner_id=owner_id,
            )

            if result.get("success"):
                db.mark_document_synced(doc["id"], result.get("paperless_id"))
                owner_info = f", owner={owner_id}" if owner_id else ""
                logger.info(f"Document exported successfully (Paperless ID: {result.get('paperless_id')}{owner_info})")
            else:
                logger.error(f"Export failed: {result.get('error')}")

        logger.info("Paperless-NGX export completed")

    except Exception as e:
        logger.error(f"Error exporting to Paperless: {e}", exc_info=True)


def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description="MAJ Document Recognition System - OCR a AI klasifikace dokumentů"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to configuration file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Process command
    process_parser = subparsers.add_parser("process", help="Process a single document")
    process_parser.add_argument("file", type=str, help="Path to document file")

    # Scan Thunderbird command
    scan_parser = subparsers.add_parser("scan", help="Scan Thunderbird mailbox")
    scan_parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Scan emails from last N days (default: from config)",
    )

    # Export to Paperless command
    subparsers.add_parser("export", help="Export documents to Paperless-NGX")

    # Web GUI command
    subparsers.add_parser("web", help="Start web GUI")

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info(f"Starting MAJ Document Recognition System v{config.get('app', {}).get('version', '1.0.0')}")

    # Initialize components
    db = DatabaseManager(config)
    processor = DocumentProcessor(config)
    classifier = AIClassifier(config, db)

    # Execute command
    if args.command == "process":
        process_document(args.file, config, db, processor, classifier)

    elif args.command == "scan":
        scan_thunderbird(config, db, processor, classifier, args.days)

    elif args.command == "export":
        export_to_paperless(config, db)

    elif args.command == "web":
        from src.web.app import create_app
        app = create_app(config)
        app.run(
            host=config.get("web", {}).get("host", "0.0.0.0"),
            port=config.get("web", {}).get("port", 5000),
            debug=config.get("app", {}).get("debug", False),
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
