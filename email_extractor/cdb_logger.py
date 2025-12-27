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
CDB Logger - Centralized Database Logging
==========================================
Logs extraction runs to SQLite database on DGX.

Database: /home/puzik/almquist-central-log/almquist.db

Tables:
- email_extraction_runs: Run metadata
- email_extraction_items: Individual item results
- email_extraction_errors: Error log

Author: Claude Code
Date: 2025-12-15
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import subprocess
import logging


# ============================================================================
# CONFIGURATION
# ============================================================================

# CDB location
CDB_PATH = Path("/home/puzik/almquist-central-log/almquist.db")

# For remote access from Mac
DGX_HOST = "dgx"  # Assumes SSH config
DGX_CDB_PATH = "/home/puzik/almquist-central-log/almquist.db"

# Schema
SCHEMA = """
-- Email extraction runs table
CREATE TABLE IF NOT EXISTS email_extraction_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    phase INTEGER NOT NULL,
    machine TEXT,
    instance_id INTEGER,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT DEFAULT 'running',
    total_emails INTEGER DEFAULT 0,
    processed INTEGER DEFAULT 0,
    success INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    stats_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Individual item results (optional, for detailed tracking)
CREATE TABLE IF NOT EXISTS email_extraction_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    email_id TEXT NOT NULL,
    doc_type TEXT,
    confidence INTEGER,
    success BOOLEAN,
    error_message TEXT,
    fields_json TEXT,
    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES email_extraction_runs(run_id)
);

-- Error log
CREATE TABLE IF NOT EXISTS email_extraction_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    email_id TEXT,
    phase INTEGER,
    stage TEXT,
    error_type TEXT,
    error_message TEXT,
    stack_trace TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES email_extraction_runs(run_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_runs_phase ON email_extraction_runs(phase);
CREATE INDEX IF NOT EXISTS idx_runs_status ON email_extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_items_run ON email_extraction_items(run_id);
CREATE INDEX IF NOT EXISTS idx_items_doc_type ON email_extraction_items(doc_type);
CREATE INDEX IF NOT EXISTS idx_errors_run ON email_extraction_errors(run_id);
"""


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class RunRecord:
    """Record for a processing run"""
    run_id: str
    phase: int
    machine: str
    instance_id: int
    start_time: str
    end_time: str = None
    status: str = "running"
    total_emails: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    stats_json: str = None


@dataclass
class ItemRecord:
    """Record for a processed item"""
    run_id: str
    email_id: str
    doc_type: str = None
    confidence: int = 0
    success: bool = False
    error_message: str = None
    fields_json: str = None


@dataclass
class ErrorRecord:
    """Record for an error"""
    run_id: str
    email_id: str = None
    phase: int = None
    stage: str = None
    error_type: str = None
    error_message: str = None
    stack_trace: str = None


# ============================================================================
# LOCAL CDB LOGGER (Direct SQLite)
# ============================================================================

class LocalCDBLogger:
    """Logger for direct SQLite access (when running on DGX)"""

    def __init__(self, db_path: Path = CDB_PATH, logger: logging.Logger = None):
        self.db_path = db_path
        self.logger = logger or logging.getLogger(__name__)
        self._conn = None
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure database schema exists"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as conn:
                conn.executescript(SCHEMA)
                conn.commit()

            self.logger.info(f"CDB initialized: {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize CDB: {e}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def log_run_start(self, run: RunRecord):
        """Log run start"""
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT INTO email_extraction_runs
                (run_id, phase, machine, instance_id, start_time, status, total_emails)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id, run.phase, run.machine, run.instance_id,
                run.start_time, run.status, run.total_emails
            ))
            conn.commit()
            self.logger.info(f"Run started: {run.run_id}")
        except Exception as e:
            self.logger.error(f"Failed to log run start: {e}")

    def log_run_update(self, run_id: str, processed: int, success: int, failed: int):
        """Update run progress"""
        try:
            conn = self._get_conn()
            conn.execute("""
                UPDATE email_extraction_runs
                SET processed = ?, success = ?, failed = ?
                WHERE run_id = ?
            """, (processed, success, failed, run_id))
            conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to update run: {e}")

    def log_run_end(self, run_id: str, status: str, stats: Dict = None):
        """Log run completion"""
        try:
            conn = self._get_conn()
            stats_json = json.dumps(stats, ensure_ascii=False) if stats else None

            conn.execute("""
                UPDATE email_extraction_runs
                SET end_time = ?, status = ?, stats_json = ?
                WHERE run_id = ?
            """, (datetime.now().isoformat(), status, stats_json, run_id))
            conn.commit()
            self.logger.info(f"Run completed: {run_id} ({status})")
        except Exception as e:
            self.logger.error(f"Failed to log run end: {e}")

    def log_item(self, item: ItemRecord):
        """Log processed item"""
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT INTO email_extraction_items
                (run_id, email_id, doc_type, confidence, success, error_message, fields_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item.run_id, item.email_id, item.doc_type, item.confidence,
                item.success, item.error_message, item.fields_json
            ))
            conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to log item: {e}")

    def log_error(self, error: ErrorRecord):
        """Log error"""
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT INTO email_extraction_errors
                (run_id, email_id, phase, stage, error_type, error_message, stack_trace)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                error.run_id, error.email_id, error.phase, error.stage,
                error.error_type, error.error_message, error.stack_trace
            ))
            conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to log error: {e}")

    def get_run_stats(self, run_id: str) -> Optional[Dict]:
        """Get run statistics"""
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT * FROM email_extraction_runs WHERE run_id = ?",
                (run_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        except Exception as e:
            self.logger.error(f"Failed to get run stats: {e}")
        return None

    def get_recent_runs(self, limit: int = 10) -> List[Dict]:
        """Get recent runs"""
        try:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT * FROM email_extraction_runs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to get recent runs: {e}")
        return []

    def get_error_summary(self, run_id: str) -> List[Dict]:
        """Get error summary for a run"""
        try:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT stage, error_type, COUNT(*) as count
                FROM email_extraction_errors
                WHERE run_id = ?
                GROUP BY stage, error_type
                ORDER BY count DESC
            """, (run_id,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Failed to get error summary: {e}")
        return []

    def close(self):
        """Close connection"""
        if self._conn:
            self._conn.close()
            self._conn = None


# ============================================================================
# REMOTE CDB LOGGER (Via SSH)
# ============================================================================

class RemoteCDBLogger:
    """Logger for remote SQLite access (from Mac to DGX via SSH)"""

    def __init__(self, host: str = DGX_HOST, db_path: str = DGX_CDB_PATH,
                 logger: logging.Logger = None):
        self.host = host
        self.db_path = db_path
        self.logger = logger or logging.getLogger(__name__)
        self._ensure_schema()

    def _run_sql(self, sql: str, params: tuple = None) -> Optional[str]:
        """Execute SQL on remote database via SSH"""
        try:
            # Build sqlite3 command
            if params:
                # Escape parameters
                escaped = []
                for p in params:
                    if p is None:
                        escaped.append("NULL")
                    elif isinstance(p, (int, float)):
                        escaped.append(str(p))
                    elif isinstance(p, bool):
                        escaped.append("1" if p else "0")
                    else:
                        escaped.append(f"'{str(p).replace(chr(39), chr(39)+chr(39))}'")

                # Replace ? placeholders
                for val in escaped:
                    sql = sql.replace("?", val, 1)

            cmd = f'sqlite3 "{self.db_path}" "{sql}"'

            result = subprocess.run(
                ["ssh", self.host, cmd],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                self.logger.error(f"SSH SQL error: {result.stderr}")
                return None

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            self.logger.error("SSH command timed out")
        except Exception as e:
            self.logger.error(f"SSH SQL error: {e}")
        return None

    def _ensure_schema(self):
        """Ensure remote database schema exists"""
        # Create directory if needed
        subprocess.run(
            ["ssh", self.host, f"mkdir -p $(dirname {self.db_path})"],
            capture_output=True
        )

        # Apply schema
        for statement in SCHEMA.split(";"):
            statement = statement.strip()
            if statement:
                self._run_sql(statement)

        self.logger.info(f"Remote CDB initialized: {self.host}:{self.db_path}")

    def log_run_start(self, run: RunRecord):
        """Log run start"""
        sql = """INSERT INTO email_extraction_runs
                 (run_id, phase, machine, instance_id, start_time, status, total_emails)
                 VALUES (?, ?, ?, ?, ?, ?, ?)"""
        self._run_sql(sql, (
            run.run_id, run.phase, run.machine, run.instance_id,
            run.start_time, run.status, run.total_emails
        ))

    def log_run_update(self, run_id: str, processed: int, success: int, failed: int):
        """Update run progress"""
        sql = """UPDATE email_extraction_runs
                 SET processed = ?, success = ?, failed = ?
                 WHERE run_id = ?"""
        self._run_sql(sql, (processed, success, failed, run_id))

    def log_run_end(self, run_id: str, status: str, stats: Dict = None):
        """Log run completion"""
        stats_json = json.dumps(stats, ensure_ascii=False).replace("'", "''") if stats else ""
        sql = """UPDATE email_extraction_runs
                 SET end_time = ?, status = ?, stats_json = ?
                 WHERE run_id = ?"""
        self._run_sql(sql, (datetime.now().isoformat(), status, stats_json, run_id))

    def log_error(self, error: ErrorRecord):
        """Log error"""
        sql = """INSERT INTO email_extraction_errors
                 (run_id, email_id, phase, stage, error_type, error_message)
                 VALUES (?, ?, ?, ?, ?, ?)"""
        self._run_sql(sql, (
            error.run_id, error.email_id, error.phase, error.stage,
            error.error_type, error.error_message[:500] if error.error_message else None
        ))


# ============================================================================
# FACTORY
# ============================================================================

def get_cdb_logger(logger: logging.Logger = None) -> LocalCDBLogger:
    """
    Get appropriate CDB logger based on environment.

    Returns LocalCDBLogger if running on DGX, RemoteCDBLogger otherwise.
    """
    # Check if we're on DGX (check for local db path)
    if CDB_PATH.exists() or CDB_PATH.parent.exists():
        return LocalCDBLogger(CDB_PATH, logger)

    # Try remote
    try:
        result = subprocess.run(
            ["ssh", DGX_HOST, "echo OK"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return RemoteCDBLogger(DGX_HOST, DGX_CDB_PATH, logger)
    except:
        pass

    # Fallback to local (will create in current dir)
    local_path = Path("./email_extraction.db")
    if logger:
        logger.warning(f"Using local fallback DB: {local_path}")
    return LocalCDBLogger(local_path, logger)


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI for CDB management"""
    import argparse

    parser = argparse.ArgumentParser(description='CDB Logger CLI')
    parser.add_argument('--list', action='store_true', help='List recent runs')
    parser.add_argument('--run-id', type=str, help='Show details for run')
    parser.add_argument('--errors', action='store_true', help='Show error summary')
    parser.add_argument('--init', action='store_true', help='Initialize database')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger = get_cdb_logger()

    if args.init:
        print("Database initialized")

    elif args.list:
        runs = logger.get_recent_runs(20)
        print("\nRecent Runs:")
        print("-" * 80)
        for run in runs:
            print(f"{run['run_id'][:20]:20s} | Phase {run['phase']} | "
                  f"{run['status']:10s} | {run['processed']:6d}/{run['total_emails']:6d} | "
                  f"{run['machine'] or 'unknown':10s}")

    elif args.run_id:
        stats = logger.get_run_stats(args.run_id)
        if stats:
            print(f"\nRun: {args.run_id}")
            print("-" * 40)
            for key, value in stats.items():
                print(f"  {key}: {value}")

            if args.errors:
                print("\nErrors:")
                errors = logger.get_error_summary(args.run_id)
                for err in errors:
                    print(f"  {err['stage']}/{err['error_type']}: {err['count']}")
        else:
            print(f"Run not found: {args.run_id}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
