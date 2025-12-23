"""
SQLite database manager for document storage and management
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DatabaseManager:
    """Manage SQLite database for documents"""

    def __init__(self, config: dict):
        """
        Initialize DatabaseManager

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.db_config = config.get("database", {})

        self.db_path = Path(self.db_config.get("path", "data/documents.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection

        Returns:
            SQLite connection
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                file_name TEXT,
                file_size INTEGER,
                file_hash TEXT,
                ocr_text TEXT,
                ocr_confidence REAL,
                document_type TEXT,
                ai_confidence REAL,
                ai_method TEXT,
                sender TEXT,
                subject TEXT,
                date_received TEXT,
                metadata TEXT,
                paperless_id INTEGER,
                paperless_synced INTEGER DEFAULT 0,
                user_confirmed INTEGER DEFAULT 0,
                user_rating INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Training data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                text TEXT NOT NULL,
                document_type TEXT NOT NULL,
                confidence REAL,
                source TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
        """)

        # Classification history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                method TEXT,
                predicted_type TEXT,
                confidence REAL,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_sender ON documents(sender)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_paperless ON documents(paperless_id)")

        conn.commit()
        conn.close()

        self.logger.info("Database initialized")

    def insert_document(
        self,
        file_path: str,
        ocr_text: str = "",
        ocr_confidence: float = 0.0,
        document_type: str = None,
        ai_confidence: float = 0.0,
        ai_method: str = None,
        metadata: Dict = None,
        sender: str = None,
        subject: str = None,
        source: str = "PC slozka",
    ) -> int:
        """
        Insert document into database

        Args:
            file_path: Path to document file
            ocr_text: Extracted OCR text
            ocr_confidence: OCR confidence score
            document_type: Classified document type
            ai_confidence: AI classification confidence
            ai_method: AI classification method
            metadata: Additional metadata
            sender: Email sender
            subject: Email subject
            source: Document source (Email, PC slozka, Sken)

        Returns:
            Document ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        path = Path(file_path)
        file_name = path.name
        file_size = path.stat().st_size if path.exists() else 0

        # Calculate file hash
        import hashlib
        file_hash = None
        if path.exists():
            md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5.update(chunk)
            file_hash = md5.hexdigest()

        cursor.execute("""
            INSERT INTO documents (
                file_path, file_name, file_size, file_hash,
                ocr_text, ocr_confidence,
                document_type, ai_confidence, ai_method,
                sender, subject,
                metadata, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_path, file_name, file_size, file_hash,
            ocr_text, ocr_confidence,
            document_type, ai_confidence, ai_method,
            sender, subject,
            json.dumps(metadata) if metadata else None,
            source,
        ))

        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.logger.info(f"Inserted document (ID: {doc_id}): {file_name}")
        return doc_id

    def get_document(self, doc_id: int) -> Optional[Dict]:
        """
        Get document by ID

        Args:
            doc_id: Document ID

        Returns:
            Document dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()

        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_documents(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        document_type: Optional[str] = None,
        sender: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get all documents with optional filtering

        Args:
            limit: Maximum number of documents
            offset: Offset for pagination
            document_type: Filter by document type
            sender: Filter by sender

        Returns:
            List of document dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM documents WHERE 1=1"
        params = []

        if document_type:
            query += " AND document_type = ?"
            params.append(document_type)

        if sender:
            query += " AND sender LIKE ?"
            params.append(f"%{sender}%")

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def update_document(self, doc_id: int, **kwargs) -> bool:
        """
        Update document fields

        Args:
            doc_id: Document ID
            **kwargs: Fields to update

        Returns:
            True if successful
        """
        if not kwargs:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()

        # Build update query
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        query = f"UPDATE documents SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"

        values = list(kwargs.values()) + [doc_id]

        cursor.execute(query, values)
        conn.commit()
        conn.close()

        return True

    def mark_document_synced(self, doc_id: int, paperless_id: int) -> bool:
        """
        Mark document as synced to Paperless-NGX

        Args:
            doc_id: Document ID
            paperless_id: Paperless-NGX document ID

        Returns:
            True if successful
        """
        return self.update_document(
            doc_id,
            paperless_id=paperless_id,
            paperless_synced=1,
        )

    def get_unsynced_documents(self) -> List[Dict]:
        """
        Get documents not yet synced to Paperless-NGX

        Returns:
            List of document dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM documents
            WHERE paperless_synced = 0
            ORDER BY created_at ASC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_labeled_documents(self) -> List[Dict]:
        """
        Get documents with confirmed labels for ML training

        Returns:
            List of document dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM documents
            WHERE user_confirmed = 1
            AND document_type IS NOT NULL
            AND ocr_text IS NOT NULL
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def add_training_data(
        self,
        text: str,
        document_type: str,
        document_id: Optional[int] = None,
        confidence: float = 1.0,
        source: str = "manual",
    ) -> int:
        """
        Add training data for ML model

        Args:
            text: Document text
            document_type: Document type label
            document_id: Related document ID
            confidence: Confidence in label
            source: Source of label

        Returns:
            Training data ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO training_data (
                document_id, text, document_type, confidence, source
            ) VALUES (?, ?, ?, ?, ?)
        """, (document_id, text, document_type, confidence, source))

        training_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return training_id

    def get_new_samples_count(self) -> int:
        """
        Get count of new training samples

        Returns:
            Number of new samples
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count
            FROM training_data
            WHERE created_at > (
                SELECT COALESCE(MAX(created_at), '1970-01-01')
                FROM classification_history
                WHERE method = 'ml_model_training'
            )
        """)

        result = cursor.fetchone()
        conn.close()

        return result["count"] if result else 0

    def log_classification(
        self,
        document_id: int,
        method: str,
        predicted_type: str,
        confidence: float,
        metadata: Dict = None,
    ) -> int:
        """
        Log classification attempt

        Args:
            document_id: Document ID
            method: Classification method
            predicted_type: Predicted document type
            confidence: Confidence score
            metadata: Additional metadata

        Returns:
            Classification history ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO classification_history (
                document_id, method, predicted_type, confidence, metadata
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            document_id, method, predicted_type, confidence,
            json.dumps(metadata) if metadata else None,
        ))

        history_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return history_id

    def get_statistics(self) -> Dict:
        """
        Get database statistics

        Returns:
            Statistics dictionary
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        # Total documents
        cursor.execute("SELECT COUNT(*) as count FROM documents")
        stats["total_documents"] = cursor.fetchone()["count"]

        # Documents by type
        cursor.execute("""
            SELECT document_type, COUNT(*) as count
            FROM documents
            GROUP BY document_type
        """)
        stats["by_type"] = {row["document_type"]: row["count"] for row in cursor.fetchall()}

        # Synced documents
        cursor.execute("SELECT COUNT(*) as count FROM documents WHERE paperless_synced = 1")
        stats["synced_documents"] = cursor.fetchone()["count"]

        # Training samples
        cursor.execute("SELECT COUNT(*) as count FROM training_data")
        stats["training_samples"] = cursor.fetchone()["count"]

        conn.close()

        return stats
