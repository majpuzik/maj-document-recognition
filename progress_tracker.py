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
Progress Persistence - Resume processing after crash
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set
import hashlib


class ProgressTracker:
    """
    Track processing progress and enable resume after crash

    Features:
    - Tracks processed files (by hash)
    - Saves progress every N documents
    - Enables resume from crash
    - Tracks failed documents for retry
    """

    def __init__(self, db_path: str = "data/progress.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize progress database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Progress table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                file_hash TEXT PRIMARY KEY,
                file_path TEXT,
                status TEXT,  -- 'completed', 'failed', 'processing'
                processed_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)

        # Session table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                total_files INTEGER,
                processed_files INTEGER,
                failed_files INTEGER,
                status TEXT  -- 'running', 'completed', 'crashed'
            )
        """)

        conn.commit()
        conn.close()

    def _hash_file(self, file_path: str) -> str:
        """Generate hash for file (for deduplication)"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except:
            # If file can't be read, use path hash
            return hashlib.sha256(file_path.encode()).hexdigest()[:16]

    def create_session(self, total_files: int) -> str:
        """Create new processing session"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (session_id, started_at, total_files, processed_files, failed_files, status)
            VALUES (?, ?, ?, 0, 0, 'running')
        """, (session_id, datetime.now(), total_files))

        conn.commit()
        conn.close()

        return session_id

    def mark_completed(self, file_path: str, session_id: str = None):
        """Mark file as completed"""
        file_hash = self._hash_file(file_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO progress (file_hash, file_path, status, processed_at)
            VALUES (?, ?, 'completed', ?)
        """, (file_hash, file_path, datetime.now()))

        # Update session stats
        if session_id:
            cursor.execute("""
                UPDATE sessions
                SET processed_files = processed_files + 1
                WHERE session_id = ?
            """, (session_id,))

        conn.commit()
        conn.close()

    def mark_failed(self, file_path: str, error: str, session_id: str = None):
        """Mark file as failed"""
        file_hash = self._hash_file(file_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check retry count
        cursor.execute("SELECT retry_count FROM progress WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        retry_count = row[0] + 1 if row else 1

        cursor.execute("""
            INSERT OR REPLACE INTO progress (file_hash, file_path, status, processed_at, error_message, retry_count)
            VALUES (?, ?, 'failed', ?, ?, ?)
        """, (file_hash, file_path, datetime.now(), error, retry_count))

        # Update session stats
        if session_id:
            cursor.execute("""
                UPDATE sessions
                SET failed_files = failed_files + 1
                WHERE session_id = ?
            """, (session_id,))

        conn.commit()
        conn.close()

    def is_processed(self, file_path: str) -> bool:
        """Check if file was already processed successfully"""
        file_hash = self._hash_file(file_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status FROM progress WHERE file_hash = ? AND status = 'completed'
        """, (file_hash,))

        result = cursor.fetchone()
        conn.close()

        return result is not None

    def get_unprocessed_files(self, all_files: List[str]) -> List[str]:
        """Filter out already processed files"""
        unprocessed = []

        for file_path in all_files:
            if not self.is_processed(file_path):
                unprocessed.append(file_path)

        return unprocessed

    def get_failed_files(self, max_retries: int = 3) -> List[Dict]:
        """Get failed files for retry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file_path, error_message, retry_count
            FROM progress
            WHERE status = 'failed' AND retry_count < ?
            ORDER BY processed_at DESC
        """, (max_retries,))

        failed = [
            {
                'file_path': row[0],
                'error': row[1],
                'retry_count': row[2]
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return failed

    def complete_session(self, session_id: str):
        """Mark session as completed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET completed_at = ?, status = 'completed'
            WHERE session_id = ?
        """, (datetime.now(), session_id))

        conn.commit()
        conn.close()

    def crash_session(self, session_id: str):
        """Mark session as crashed (for recovery)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE sessions
            SET status = 'crashed'
            WHERE session_id = ?
        """, (session_id,))

        conn.commit()
        conn.close()

    def get_session_stats(self, session_id: str = None) -> Dict:
        """Get session statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if session_id:
            cursor.execute("""
                SELECT * FROM sessions WHERE session_id = ?
            """, (session_id,))
        else:
            cursor.execute("""
                SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1
            """)

        row = cursor.fetchone()
        conn.close()

        if not row:
            return {}

        return {
            'session_id': row[0],
            'started_at': row[1],
            'completed_at': row[2],
            'total_files': row[3],
            'processed_files': row[4],
            'failed_files': row[5],
            'status': row[6]
        }

    def get_overall_stats(self) -> Dict:
        """Get overall statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total processed
        cursor.execute("SELECT COUNT(*) FROM progress WHERE status = 'completed'")
        completed = cursor.fetchone()[0]

        # Total failed
        cursor.execute("SELECT COUNT(*) FROM progress WHERE status = 'failed'")
        failed = cursor.fetchone()[0]

        # Sessions
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'crashed'")
        crashed_sessions = cursor.fetchone()[0]

        conn.close()

        return {
            'total_completed': completed,
            'total_failed': failed,
            'total_sessions': total_sessions,
            'crashed_sessions': crashed_sessions,
            'success_rate': (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
        }

    def export_report(self, output_path: str):
        """Export progress report to JSON"""
        stats = self.get_overall_stats()

        # Get last 10 sessions
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM sessions ORDER BY started_at DESC LIMIT 10
        """)

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'session_id': row[0],
                'started_at': str(row[1]),
                'completed_at': str(row[2]) if row[2] else None,
                'total_files': row[3],
                'processed_files': row[4],
                'failed_files': row[5],
                'status': row[6]
            })

        conn.close()

        report = {
            'generated_at': datetime.now().isoformat(),
            'overall_stats': stats,
            'recent_sessions': sessions
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)


def main():
    """CLI for progress tracker"""
    import argparse

    parser = argparse.ArgumentParser(description="Progress Tracker CLI")
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--session', help='Show specific session')
    parser.add_argument('--failed', action='store_true', help='List failed files')
    parser.add_argument('--export', help='Export report to JSON')
    parser.add_argument('--reset', action='store_true', help='Reset all progress (DANGER!)')

    args = parser.parse_args()

    tracker = ProgressTracker()

    if args.stats:
        stats = tracker.get_overall_stats()
        print("\n📊 Overall Statistics:")
        print(f"   Completed: {stats['total_completed']}")
        print(f"   Failed: {stats['total_failed']}")
        print(f"   Success rate: {stats['success_rate']:.1f}%")
        print(f"   Sessions: {stats['total_sessions']}")
        print(f"   Crashed: {stats['crashed_sessions']}")

    elif args.session:
        stats = tracker.get_session_stats(args.session)
        if stats:
            print(f"\n📋 Session: {stats['session_id']}")
            print(f"   Started: {stats['started_at']}")
            print(f"   Status: {stats['status']}")
            print(f"   Progress: {stats['processed_files']}/{stats['total_files']}")
            print(f"   Failed: {stats['failed_files']}")
        else:
            print(f"❌ Session not found: {args.session}")

    elif args.failed:
        failed = tracker.get_failed_files()
        print(f"\n❌ Failed files ({len(failed)}):")
        for f in failed:
            print(f"   {f['file_path']}")
            print(f"      Error: {f['error']}")
            print(f"      Retries: {f['retry_count']}")

    elif args.export:
        tracker.export_report(args.export)
        print(f"✅ Report exported to: {args.export}")

    elif args.reset:
        confirm = input("⚠️  This will DELETE all progress! Type 'yes' to confirm: ")
        if confirm == 'yes':
            Path(tracker.db_path).unlink()
            print("✅ Progress reset")
        else:
            print("❌ Cancelled")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
