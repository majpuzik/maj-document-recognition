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
Paperless-NGX Database Validator
================================
Validuje databázi Paperless-NGX dle oficiálních pravidel.

Pravidla dle https://docs.paperless-ngx.com/api/ a https://docs.paperless-ngx.com/usage/

Použití:
    # PostgreSQL (DGX)
    python paperless_validator.py --host localhost --port 5432 --db paperless --user paperless --password paperless

    # SQLite
    python paperless_validator.py --sqlite /path/to/db.sqlite3

    # Docker kontejner
    python paperless_validator.py --docker paperless-postgres

Author: Claude Code
Version: 1.0.0
Date: 2025-12-16
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import re

# ============================================================================
# PAPERLESS-NGX VALIDATION RULES
# Zdroj: https://docs.paperless-ngx.com/api/, https://docs.paperless-ngx.com/usage/
# ============================================================================

VALIDATION_RULES = {
    "documents_document": {
        "description": "Hlavní tabulka dokumentů",
        "rules": [
            {"name": "title_not_null", "sql": "SELECT COUNT(*) FROM documents_document WHERE title IS NULL OR title = ''", "expected": 0, "severity": "error"},
            {"name": "created_not_null", "sql": "SELECT COUNT(*) FROM documents_document WHERE created IS NULL", "expected": 0, "severity": "error"},
            {"name": "checksum_unique", "sql": "SELECT COUNT(*) FROM (SELECT checksum FROM documents_document GROUP BY checksum HAVING COUNT(*) > 1) t", "expected": 0, "severity": "error"},
            {"name": "correspondent_fk_valid", "sql": "SELECT COUNT(*) FROM documents_document d WHERE d.correspondent_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM documents_correspondent c WHERE c.id = d.correspondent_id)", "expected": 0, "severity": "error"},
            {"name": "document_type_fk_valid", "sql": "SELECT COUNT(*) FROM documents_document d WHERE d.document_type_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM documents_documenttype t WHERE t.id = d.document_type_id)", "expected": 0, "severity": "error"},
            {"name": "storage_path_fk_valid", "sql": "SELECT COUNT(*) FROM documents_document d WHERE d.storage_path_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM documents_storagepath s WHERE s.id = d.storage_path_id)", "expected": 0, "severity": "error"},
        ]
    },
    "documents_tag": {
        "description": "Tagy pro organizaci dokumentů",
        "rules": [
            {"name": "name_not_null", "sql": "SELECT COUNT(*) FROM documents_tag WHERE name IS NULL OR name = ''", "expected": 0, "severity": "error"},
            {"name": "name_unique", "sql": "SELECT COUNT(*) FROM (SELECT name FROM documents_tag GROUP BY name HAVING COUNT(*) > 1) t", "expected": 0, "severity": "error"},
            {"name": "color_hex_format", "sql": "SELECT COUNT(*) FROM documents_tag WHERE color IS NOT NULL AND color !~ '^#[0-9a-fA-F]{6}$'", "expected": 0, "severity": "warning"},
        ]
    },
    "documents_correspondent": {
        "description": "Odesílatelé/příjemci dokumentů",
        "rules": [
            {"name": "name_not_null", "sql": "SELECT COUNT(*) FROM documents_correspondent WHERE name IS NULL OR name = ''", "expected": 0, "severity": "error"},
            {"name": "name_unique", "sql": "SELECT COUNT(*) FROM (SELECT name FROM documents_correspondent GROUP BY name HAVING COUNT(*) > 1) t", "expected": 0, "severity": "error"},
            {"name": "matching_algorithm_valid", "sql": "SELECT COUNT(*) FROM documents_correspondent WHERE matching_algorithm NOT BETWEEN 1 AND 6", "expected": 0, "severity": "error"},
        ]
    },
    "documents_documenttype": {
        "description": "Typy dokumentů (faktura, smlouva, ...)",
        "rules": [
            {"name": "name_not_null", "sql": "SELECT COUNT(*) FROM documents_documenttype WHERE name IS NULL OR name = ''", "expected": 0, "severity": "error"},
            {"name": "name_unique", "sql": "SELECT COUNT(*) FROM (SELECT name FROM documents_documenttype GROUP BY name HAVING COUNT(*) > 1) t", "expected": 0, "severity": "error"},
        ]
    },
    "documents_customfield": {
        "description": "Definice custom polí",
        "rules": [
            {"name": "name_not_null", "sql": "SELECT COUNT(*) FROM documents_customfield WHERE name IS NULL OR name = ''", "expected": 0, "severity": "error"},
            {"name": "name_unique", "sql": "SELECT COUNT(*) FROM (SELECT name FROM documents_customfield GROUP BY name HAVING COUNT(*) > 1) t", "expected": 0, "severity": "error"},
            {"name": "data_type_valid", "sql": "SELECT COUNT(*) FROM documents_customfield WHERE data_type NOT IN ('string', 'boolean', 'date', 'url', 'integer', 'float', 'monetary', 'documentlink', 'select')", "expected": 0, "severity": "error"},
        ]
    },
    "documents_customfieldinstance": {
        "description": "Instance custom polí na dokumentech",
        "rules": [
            {"name": "field_fk_valid", "sql": "SELECT COUNT(*) FROM documents_customfieldinstance cfi WHERE NOT EXISTS (SELECT 1 FROM documents_customfield cf WHERE cf.id = cfi.field_id)", "expected": 0, "severity": "error"},
            {"name": "document_fk_valid", "sql": "SELECT COUNT(*) FROM documents_customfieldinstance cfi WHERE NOT EXISTS (SELECT 1 FROM documents_document d WHERE d.id = cfi.document_id)", "expected": 0, "severity": "error"},
            {"name": "no_duplicate_field_per_doc", "sql": "SELECT COUNT(*) FROM (SELECT document_id, field_id FROM documents_customfieldinstance GROUP BY document_id, field_id HAVING COUNT(*) > 1) t", "expected": 0, "severity": "error"},
        ]
    },
    "documents_storagepath": {
        "description": "Cesty pro ukládání dokumentů",
        "rules": [
            {"name": "name_not_null", "sql": "SELECT COUNT(*) FROM documents_storagepath WHERE name IS NULL OR name = ''", "expected": 0, "severity": "error"},
            {"name": "name_unique", "sql": "SELECT COUNT(*) FROM (SELECT name FROM documents_storagepath GROUP BY name HAVING COUNT(*) > 1) t", "expected": 0, "severity": "error"},
            {"name": "path_not_null", "sql": "SELECT COUNT(*) FROM documents_storagepath WHERE path IS NULL OR path = ''", "expected": 0, "severity": "error"},
        ]
    },
    "documents_document_tags": {
        "description": "Vazební tabulka dokument-tagy",
        "rules": [
            {"name": "document_fk_valid", "sql": "SELECT COUNT(*) FROM documents_document_tags dt WHERE NOT EXISTS (SELECT 1 FROM documents_document d WHERE d.id = dt.document_id)", "expected": 0, "severity": "error"},
            {"name": "tag_fk_valid", "sql": "SELECT COUNT(*) FROM documents_document_tags dt WHERE NOT EXISTS (SELECT 1 FROM documents_tag t WHERE t.id = dt.tag_id)", "expected": 0, "severity": "error"},
        ]
    },
}

# Dotazy pro kontrolu osiřelých záznamů
ORPHAN_CHECKS = [
    {"name": "orphan_correspondents", "sql": "SELECT COUNT(*) FROM documents_correspondent c WHERE NOT EXISTS (SELECT 1 FROM documents_document d WHERE d.correspondent_id = c.id)", "severity": "info"},
    {"name": "orphan_document_types", "sql": "SELECT COUNT(*) FROM documents_documenttype t WHERE NOT EXISTS (SELECT 1 FROM documents_document d WHERE d.document_type_id = t.id)", "severity": "info"},
    {"name": "orphan_tags", "sql": "SELECT COUNT(*) FROM documents_tag t WHERE NOT EXISTS (SELECT 1 FROM documents_document_tags dt WHERE dt.tag_id = t.id)", "severity": "info"},
    {"name": "orphan_custom_fields", "sql": "SELECT COUNT(*) FROM documents_customfield cf WHERE NOT EXISTS (SELECT 1 FROM documents_customfieldinstance cfi WHERE cfi.field_id = cf.id)", "severity": "info"},
]

# Dotazy pro statistiky
STATS_QUERIES = {
    "total_documents": "SELECT COUNT(*) FROM documents_document",
    "total_tags": "SELECT COUNT(*) FROM documents_tag",
    "total_correspondents": "SELECT COUNT(*) FROM documents_correspondent",
    "total_document_types": "SELECT COUNT(*) FROM documents_documenttype",
    "total_custom_fields": "SELECT COUNT(*) FROM documents_customfield",
    "total_custom_field_instances": "SELECT COUNT(*) FROM documents_customfieldinstance",
    "total_storage_paths": "SELECT COUNT(*) FROM documents_storagepath",
    "total_document_tag_relations": "SELECT COUNT(*) FROM documents_document_tags",
}


@dataclass
class ValidationResult:
    """Výsledek validace jednoho pravidla"""
    table: str
    rule: str
    expected: int
    actual: int
    passed: bool
    severity: str
    message: str


class PaperlessValidator:
    """
    Validátor pro Paperless-NGX databázi.

    Podporuje:
    - PostgreSQL (přímé připojení nebo Docker kontejner)
    - SQLite

    Příklad použití:

        # PostgreSQL via Docker
        validator = PaperlessValidator(docker_container="paperless-postgres")
        report = validator.validate_all()
        validator.print_report(report)

        # SQLite
        validator = PaperlessValidator(sqlite_path="/path/to/db.sqlite3")
        report = validator.validate_all()
    """

    def __init__(
        self,
        host: str = None,
        port: int = 5432,
        database: str = "paperless",
        user: str = "paperless",
        password: str = None,
        sqlite_path: str = None,
        docker_container: str = None
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.sqlite_path = sqlite_path
        self.docker_container = docker_container

        # Určení typu připojení
        if sqlite_path:
            self.db_type = "sqlite"
        elif docker_container:
            self.db_type = "docker"
        else:
            self.db_type = "postgresql"

    def execute_query(self, sql: str) -> int:
        """
        Vykoná SQL dotaz a vrátí výsledek (COUNT).

        Args:
            sql: SQL dotaz vracející jednu hodnotu

        Returns:
            Celočíselný výsledek dotazu
        """
        if self.db_type == "docker":
            return self._execute_docker(sql)
        elif self.db_type == "sqlite":
            return self._execute_sqlite(sql)
        else:
            return self._execute_postgresql(sql)

    def _execute_docker(self, sql: str) -> int:
        """Vykoná SQL přes Docker kontejner"""
        cmd = [
            "docker", "exec", self.docker_container,
            "psql", "-U", self.user, "-d", self.database,
            "-t", "-c", sql
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return int(result.stdout.strip())
            else:
                raise Exception(f"Docker exec failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Query timeout")

    def _execute_sqlite(self, sql: str) -> int:
        """Vykoná SQL na SQLite databázi"""
        import sqlite3
        # Upravit SQL pro SQLite (regex syntax)
        sql = sql.replace("!~", "NOT GLOB").replace("~", "GLOB")
        sql = sql.replace("'^#[0-9a-fA-F]{6}$'", "'#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'")

        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchone()[0]
        conn.close()
        return int(result)

    def _execute_postgresql(self, sql: str) -> int:
        """Vykoná SQL na PostgreSQL"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            cursor = conn.cursor()
            cursor.execute(sql)
            result = cursor.fetchone()[0]
            conn.close()
            return int(result)
        except ImportError:
            raise Exception("psycopg2 not installed. Use: pip install psycopg2-binary")

    def validate_table(self, table: str) -> List[ValidationResult]:
        """
        Validuje jednu tabulku dle definovaných pravidel.

        Args:
            table: Název tabulky

        Returns:
            Seznam výsledků validace
        """
        results = []

        if table not in VALIDATION_RULES:
            return results

        table_config = VALIDATION_RULES[table]

        for rule in table_config["rules"]:
            try:
                actual = self.execute_query(rule["sql"])
                passed = actual == rule["expected"]

                if passed:
                    message = "OK"
                else:
                    message = f"Očekáváno {rule['expected']}, nalezeno {actual}"

                results.append(ValidationResult(
                    table=table,
                    rule=rule["name"],
                    expected=rule["expected"],
                    actual=actual,
                    passed=passed,
                    severity=rule["severity"],
                    message=message
                ))
            except Exception as e:
                results.append(ValidationResult(
                    table=table,
                    rule=rule["name"],
                    expected=rule["expected"],
                    actual=-1,
                    passed=False,
                    severity="error",
                    message=f"Query failed: {str(e)}"
                ))

        return results

    def validate_all(self) -> Dict[str, Any]:
        """
        Provede kompletní validaci databáze.

        Returns:
            Slovník s výsledky validace, statistikami a orphany
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "db_type": self.db_type,
            "validation_results": [],
            "stats": {},
            "orphans": {},
            "summary": {
                "total_rules": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
                "errors": 0
            }
        }

        # Validace všech tabulek
        for table in VALIDATION_RULES:
            results = self.validate_table(table)
            for r in results:
                report["validation_results"].append({
                    "table": r.table,
                    "rule": r.rule,
                    "expected": r.expected,
                    "actual": r.actual,
                    "passed": r.passed,
                    "severity": r.severity,
                    "message": r.message
                })

                report["summary"]["total_rules"] += 1
                if r.passed:
                    report["summary"]["passed"] += 1
                else:
                    report["summary"]["failed"] += 1
                    if r.severity == "error":
                        report["summary"]["errors"] += 1
                    elif r.severity == "warning":
                        report["summary"]["warnings"] += 1

        # Statistiky
        for name, sql in STATS_QUERIES.items():
            try:
                report["stats"][name] = self.execute_query(sql)
            except:
                report["stats"][name] = -1

        # Orphan check
        for check in ORPHAN_CHECKS:
            try:
                report["orphans"][check["name"]] = self.execute_query(check["sql"])
            except:
                report["orphans"][check["name"]] = -1

        return report

    def print_report(self, report: Dict[str, Any], verbose: bool = False):
        """
        Vytiskne validační report do konzole.

        Args:
            report: Výsledek validate_all()
            verbose: Zobrazit i úspěšné testy
        """
        print("\n" + "=" * 70)
        print("  PAPERLESS-NGX DATABASE VALIDATION REPORT")
        print("=" * 70)
        print(f"  Timestamp: {report['timestamp']}")
        print(f"  DB Type: {report['db_type']}")
        print("=" * 70)

        # Statistiky
        print("\n📊 STATISTIKY:")
        print("-" * 40)
        for name, value in report["stats"].items():
            print(f"  {name}: {value:,}")

        # Validace
        print("\n✅ VALIDACE:")
        print("-" * 40)

        current_table = None
        for r in report["validation_results"]:
            if r["table"] != current_table:
                current_table = r["table"]
                print(f"\n  [{current_table}]")

            if r["passed"]:
                if verbose:
                    print(f"    ✓ {r['rule']}: OK")
            else:
                icon = "✗" if r["severity"] == "error" else "⚠"
                print(f"    {icon} {r['rule']}: {r['message']}")

        # Orphans
        print("\n⚠️  NEPOUŽITÉ ZÁZNAMY:")
        print("-" * 40)
        for name, count in report["orphans"].items():
            if count > 0:
                print(f"  {name}: {count}")

        # Shrnutí
        print("\n" + "=" * 70)
        summary = report["summary"]
        status = "✅ PASSED" if summary["errors"] == 0 else "❌ FAILED"
        print(f"  VÝSLEDEK: {status}")
        print(f"  Pravidel: {summary['total_rules']}")
        print(f"  Úspěšných: {summary['passed']}")
        print(f"  Chyb: {summary['errors']}")
        print(f"  Varování: {summary['warnings']}")
        print("=" * 70 + "\n")

    def export_json(self, report: Dict[str, Any], path: str):
        """Exportuje report do JSON souboru"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Report uložen: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Paperless-NGX Database Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Příklady:
  # Docker kontejner
  python paperless_validator.py --docker paperless-postgres

  # PostgreSQL přímo
  python paperless_validator.py --host localhost --port 5432 --db paperless --user paperless

  # SQLite
  python paperless_validator.py --sqlite /path/to/db.sqlite3

  # Export do JSON
  python paperless_validator.py --docker paperless-postgres --output report.json
        """
    )

    # Connection options
    parser.add_argument("--docker", metavar="CONTAINER", help="Docker container name")
    parser.add_argument("--sqlite", metavar="PATH", help="Path to SQLite database")
    parser.add_argument("--host", help="PostgreSQL host")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port")
    parser.add_argument("--db", default="paperless", help="Database name")
    parser.add_argument("--user", default="paperless", help="Database user")
    parser.add_argument("--password", help="Database password")

    # Output options
    parser.add_argument("--output", "-o", metavar="FILE", help="Export report to JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all tests")

    args = parser.parse_args()

    # Vytvořit validátor
    if args.docker:
        validator = PaperlessValidator(docker_container=args.docker)
    elif args.sqlite:
        validator = PaperlessValidator(sqlite_path=args.sqlite)
    elif args.host:
        validator = PaperlessValidator(
            host=args.host,
            port=args.port,
            database=args.db,
            user=args.user,
            password=args.password
        )
    else:
        parser.print_help()
        print("\n❌ Chyba: Specifikujte --docker, --sqlite nebo --host")
        sys.exit(1)

    # Spustit validaci
    print("🔍 Validuji Paperless-NGX databázi...")
    report = validator.validate_all()

    # Výstup
    validator.print_report(report, verbose=args.verbose)

    if args.output:
        validator.export_json(report, args.output)

    # Exit code
    if report["summary"]["errors"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
