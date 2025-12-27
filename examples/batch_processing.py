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
Batch processing example - process multiple documents
"""

import glob
import yaml
from pathlib import Path

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier import AIClassifier
from src.database.db_manager import DatabaseManager


def main():
    """Batch process documents"""

    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    print("MAJ Document Recognition - Batch Processing")
    print("=" * 50)

    # Get directory
    directory = input("Enter directory path with documents: ")

    if not Path(directory).exists():
        print(f"Error: Directory not found: {directory}")
        return

    # Initialize
    print("\nInitializing...")
    db = DatabaseManager(config)
    processor = DocumentProcessor(config)
    classifier = AIClassifier(config, db)

    # Find documents
    patterns = ["*.pdf", "*.jpg", "*.jpeg", "*.png"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(str(Path(directory) / pattern)))

    print(f"Found {len(files)} documents")

    if not files:
        print("No documents found!")
        return

    # Process each file
    results = []
    errors = []

    for i, file_path in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Processing: {Path(file_path).name}")

        try:
            # OCR
            ocr_result = processor.process_document(file_path)

            if not ocr_result.get("success"):
                errors.append({
                    "file": file_path,
                    "error": ocr_result.get("error")
                })
                print(f"   ✗ OCR failed: {ocr_result.get('error')}")
                continue

            # Classify
            classification = classifier.classify(
                ocr_result.get("text", ""),
                ocr_result.get("metadata", {})
            )

            # Save
            doc_id = db.insert_document(
                file_path=file_path,
                ocr_text=ocr_result.get("text", ""),
                ocr_confidence=ocr_result.get("confidence", 0),
                document_type=classification.get("type"),
                ai_confidence=classification.get("confidence", 0),
                ai_method=classification.get("method")
            )

            results.append({
                "file": Path(file_path).name,
                "type": classification.get("type"),
                "confidence": classification.get("confidence", 0),
                "doc_id": doc_id
            })

            print(f"   ✓ {classification.get('type')} ({classification.get('confidence', 0):.2%})")

        except Exception as e:
            errors.append({
                "file": file_path,
                "error": str(e)
            })
            print(f"   ✗ Error: {e}")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total files: {len(files)}")
    print(f"Processed: {len(results)}")
    print(f"Errors: {len(errors)}")

    if results:
        print("\nProcessed documents:")
        for r in results:
            print(f"  - {r['file']}: {r['type']} ({r['confidence']:.2%}) [ID: {r['doc_id']}]")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {Path(e['file']).name}: {e['error']}")

    # Type breakdown
    type_counts = {}
    for r in results:
        doc_type = r["type"]
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

    if type_counts:
        print("\nDocuments by type:")
        for doc_type, count in type_counts.items():
            print(f"  - {doc_type}: {count}")


if __name__ == "__main__":
    main()
