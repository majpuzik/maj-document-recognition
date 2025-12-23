"""
Flask web application for document management
"""

import logging
import os
from pathlib import Path
from typing import Dict

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.blacklist_whitelist import BlacklistWhitelist
from src.integrations.paperless_api import PaperlessAPI
from src.integrations.thunderbird import ThunderbirdIntegration
from src.ocr.document_processor import DocumentProcessor


def create_app(config: dict) -> Flask:
    """
    Create Flask application

    Args:
        config: Application configuration

    Returns:
        Flask app instance
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.get("web", {}).get("secret_key", "dev-secret-key")
    app.config["MAX_CONTENT_LENGTH"] = config.get("storage", {}).get("max_file_size_mb", 50) * 1024 * 1024

    CORS(app)

    # Initialize components
    db = DatabaseManager(config)
    processor = DocumentProcessor(config)
    classifier = AIClassifier(config, db)
    thunderbird = ThunderbirdIntegration(config)
    paperless = PaperlessAPI(config) if config.get("paperless", {}).get("enabled") else None
    blacklist_whitelist = BlacklistWhitelist(config)

    # Store in app context
    app.db = db
    app.processor = processor
    app.classifier = classifier
    app.thunderbird = thunderbird
    app.paperless = paperless
    app.blacklist_whitelist = blacklist_whitelist
    app.config_dict = config

    logger = logging.getLogger(__name__)

    # Routes
    @app.route("/")
    def index():
        """Main page"""
        return render_template("index.html")

    @app.route("/api/documents", methods=["GET"])
    def get_documents():
        """Get all documents with optional filtering"""
        limit = request.args.get("limit", type=int)
        offset = request.args.get("offset", 0, type=int)
        doc_type = request.args.get("type")
        sender = request.args.get("sender")

        documents = db.get_all_documents(
            limit=limit,
            offset=offset,
            document_type=doc_type,
            sender=sender,
        )

        return jsonify({
            "success": True,
            "count": len(documents),
            "documents": documents,
        })

    @app.route("/api/documents/<int:doc_id>", methods=["GET"])
    def get_document(doc_id):
        """Get single document"""
        document = db.get_document(doc_id)

        if document:
            return jsonify({
                "success": True,
                "document": document,
            })
        else:
            return jsonify({
                "success": False,
                "error": "Document not found",
            }), 404

    @app.route("/api/documents/<int:doc_id>", methods=["PUT"])
    def update_document(doc_id):
        """Update document"""
        data = request.json

        success = db.update_document(doc_id, **data)

        return jsonify({
            "success": success,
        })

    @app.route("/api/upload", methods=["POST"])
    def upload_document():
        """Upload and process document"""
        if "file" not in request.files:
            return jsonify({
                "success": False,
                "error": "No file provided",
            }), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({
                "success": False,
                "error": "No file selected",
            }), 400

        # Save file
        upload_folder = Path(config.get("storage", {}).get("upload_folder", "data/uploads"))
        upload_folder.mkdir(parents=True, exist_ok=True)

        file_path = upload_folder / file.filename
        file.save(file_path)

        # Process document
        try:
            ocr_result = processor.process_document(str(file_path))

            if not ocr_result.get("success"):
                return jsonify({
                    "success": False,
                    "error": ocr_result.get("error"),
                }), 500

            classification = classifier.classify(
                ocr_result.get("text", ""),
                ocr_result.get("metadata", {}),
            )

            # Save to database
            doc_id = db.insert_document(
                file_path=str(file_path),
                ocr_text=ocr_result.get("text", ""),
                ocr_confidence=ocr_result.get("confidence", 0),
                document_type=classification.get("type"),
                ai_confidence=classification.get("confidence", 0),
                ai_method=classification.get("method"),
                metadata=classification.get("metadata", {}),
            )

            return jsonify({
                "success": True,
                "document_id": doc_id,
                "classification": classification,
            })

        except Exception as e:
            logger.error(f"Error processing upload: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e),
            }), 500

    @app.route("/api/thunderbird/scan", methods=["POST"])
    def scan_thunderbird():
        """Scan Thunderbird mailbox"""
        data = request.json or {}
        days_back = data.get("days_back")

        try:
            emails = thunderbird.scan_emails(days_back=days_back)

            return jsonify({
                "success": True,
                "count": len(emails),
                "emails": emails,
            })

        except Exception as e:
            logger.error(f"Error scanning Thunderbird: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e),
            }), 500

    @app.route("/api/paperless/sync", methods=["POST"])
    def sync_paperless():
        """Sync documents to Paperless-NGX"""
        if not paperless:
            return jsonify({
                "success": False,
                "error": "Paperless-NGX not enabled",
            }), 400

        try:
            documents = db.get_unsynced_documents()
            synced_count = 0

            for doc in documents:
                result = paperless.upload_document(
                    file_path=doc["file_path"],
                    title=doc.get("file_name"),
                    document_type=doc.get("document_type"),
                    correspondent=doc.get("sender"),
                )

                if result.get("success"):
                    db.mark_document_synced(doc["id"], result.get("paperless_id"))
                    synced_count += 1

            return jsonify({
                "success": True,
                "total": len(documents),
                "synced": synced_count,
            })

        except Exception as e:
            logger.error(f"Error syncing to Paperless: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e),
            }), 500

    @app.route("/api/blacklist", methods=["GET"])
    def get_blacklist():
        """Get blacklist"""
        return jsonify({
            "success": True,
            "blacklist": blacklist_whitelist.get_blacklist(),
        })

    @app.route("/api/whitelist", methods=["GET"])
    def get_whitelist():
        """Get whitelist"""
        return jsonify({
            "success": True,
            "whitelist": blacklist_whitelist.get_whitelist(),
        })

    @app.route("/api/blacklist", methods=["POST"])
    def add_to_blacklist():
        """Add to blacklist"""
        data = request.json
        email = data.get("email")

        if not email:
            return jsonify({
                "success": False,
                "error": "Email required",
            }), 400

        success = blacklist_whitelist.add_to_blacklist(email)

        return jsonify({
            "success": success,
        })

    @app.route("/api/whitelist", methods=["POST"])
    def add_to_whitelist():
        """Add to whitelist"""
        data = request.json
        email = data.get("email")

        if not email:
            return jsonify({
                "success": False,
                "error": "Email required",
            }), 400

        success = blacklist_whitelist.add_to_whitelist(email)

        return jsonify({
            "success": success,
        })

    @app.route("/api/statistics", methods=["GET"])
    def get_statistics():
        """Get database statistics"""
        stats = db.get_statistics()

        return jsonify({
            "success": True,
            "statistics": stats,
        })

    return app


def main():
    """Main entry point for web app"""
    import yaml

    # Load config
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    app = create_app(config)

    app.run(
        host=config.get("web", {}).get("host", "0.0.0.0"),
        port=config.get("web", {}).get("port", 5000),
        debug=config.get("app", {}).get("debug", False),
    )


if __name__ == "__main__":
    main()
