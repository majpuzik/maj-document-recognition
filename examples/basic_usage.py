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
Basic usage example for MAJ Document Recognition
"""

import yaml
from pathlib import Path

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager


def main():
    """Main example function"""

    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    print("MAJ Document Recognition - Basic Usage Example")
    print("=" * 50)

    # Initialize components
    print("\n1. Initializing components...")
    db = DatabaseManager(config)
    processor = DocumentProcessor(config)
    classifier = AIClassifier(config, db)
    print("   ✓ Components initialized")

    # Example document (replace with your path)
    document_path = input("\nEnter path to document (PDF/JPG/PNG): ")

    if not Path(document_path).exists():
        print(f"Error: File not found: {document_path}")
        return

    # Process document
    print("\n2. Processing document with OCR...")
    ocr_result = processor.process_document(document_path)

    if not ocr_result.get("success"):
        print(f"   ✗ OCR failed: {ocr_result.get('error')}")
        return

    print(f"   ✓ OCR completed")
    print(f"   - Confidence: {ocr_result.get('confidence', 0):.1f}%")
    print(f"   - Text length: {len(ocr_result.get('text', ''))} characters")
    print(f"   - First 100 chars: {ocr_result.get('text', '')[:100]}...")

    # Classify document
    print("\n3. Classifying document with AI...")
    classification = classifier.classify(
        ocr_result.get("text", ""),
        ocr_result.get("metadata", {})
    )

    print(f"   ✓ Classification completed")
    print(f"   - Type: {classification.get('type')}")
    print(f"   - Confidence: {classification.get('confidence', 0):.2%}")
    print(f"   - Method: {classification.get('method')}")

    # Save to database
    print("\n4. Saving to database...")
    doc_id = db.insert_document(
        file_path=document_path,
        ocr_text=ocr_result.get("text", ""),
        ocr_confidence=ocr_result.get("confidence", 0),
        document_type=classification.get("type"),
        ai_confidence=classification.get("confidence", 0),
        ai_method=classification.get("method"),
        metadata=classification.get("metadata", {})
    )

    print(f"   ✓ Document saved (ID: {doc_id})")

    # Display statistics
    print("\n5. Database statistics:")
    stats = db.get_statistics()
    print(f"   - Total documents: {stats.get('total_documents', 0)}")
    print(f"   - Documents by type:")
    for doc_type, count in stats.get("by_type", {}).items():
        print(f"     * {doc_type or 'Unknown'}: {count}")

    print("\n" + "=" * 50)
    print("Example completed successfully!")


if __name__ == "__main__":
    main()
