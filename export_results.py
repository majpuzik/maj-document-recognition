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
Export processing results to various formats
"""

import sqlite3
import json
import csv
from pathlib import Path
from datetime import datetime
from collections import Counter
import sys


def export_to_json(db_path, output_path):
    """Export to JSON"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            file_path,
            ocr_text,
            ocr_confidence,
            document_type,
            ai_confidence,
            created_at,
            metadata
        FROM documents
        ORDER BY created_at DESC
    """)

    documents = []
    for row in cursor.fetchall():
        doc = dict(row)
        # Parse metadata if it's string
        if isinstance(doc['metadata'], str):
            try:
                doc['metadata'] = json.loads(doc['metadata'])
            except:
                pass
        documents.append(doc)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'export_date': datetime.now().isoformat(),
            'total_documents': len(documents),
            'documents': documents
        }, f, indent=2, ensure_ascii=False)

    conn.close()
    return len(documents)


def export_to_csv(db_path, output_path):
    """Export to CSV"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            file_path,
            document_type,
            ai_confidence,
            ocr_confidence,
            created_at
        FROM documents
        ORDER BY created_at DESC
    """)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'File Path', 'Type', 'AI Confidence', 'OCR Confidence', 'Created At'])

        count = 0
        for row in cursor.fetchall():
            writer.writerow(row)
            count += 1

    conn.close()
    return count


def generate_statistics(db_path):
    """Generate comprehensive statistics"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        'generated_at': datetime.now().isoformat(),
        'database': str(db_path)
    }

    # Total documents
    cursor.execute("SELECT COUNT(*) FROM documents")
    stats['total_documents'] = cursor.fetchone()[0]

    # By type
    cursor.execute("""
        SELECT document_type, COUNT(*) as count, AVG(ai_confidence) as avg_conf
        FROM documents
        GROUP BY document_type
        ORDER BY count DESC
    """)
    stats['by_type'] = [
        {
            'type': row[0],
            'count': row[1],
            'avg_confidence': round(row[2], 2) if row[2] else 0
        }
        for row in cursor.fetchall()
    ]

    # Average confidences
    cursor.execute("SELECT AVG(ai_confidence), AVG(ocr_confidence) FROM documents")
    ai_conf, ocr_conf = cursor.fetchone()
    stats['average_confidence'] = {
        'ai': round(ai_conf, 2) if ai_conf else 0,
        'ocr': round(ocr_conf, 2) if ocr_conf else 0
    }

    # By server (if distributed)
    try:
        cursor.execute("""
            SELECT
                json_extract(metadata, '$.ollama_server') as server,
                COUNT(*) as count
            FROM documents
            WHERE json_extract(metadata, '$.ollama_server') IS NOT NULL
            GROUP BY server
        """)
        servers = cursor.fetchall()
        if servers:
            stats['by_server'] = [
                {
                    'server': row[0],
                    'count': row[1]
                }
                for row in servers
            ]
    except:
        pass

    # Processing timeline (by hour)
    cursor.execute("""
        SELECT
            strftime('%Y-%m-%d %H:00', created_at) as hour,
            COUNT(*) as count
        FROM documents
        GROUP BY hour
        ORDER BY hour DESC
        LIMIT 24
    """)
    stats['timeline'] = [
        {'hour': row[0], 'count': row[1]}
        for row in cursor.fetchall()
    ]

    conn.close()
    return stats


def generate_report(db_path, output_dir):
    """Generate complete report in multiple formats"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Statistics JSON
    stats = generate_statistics(db_path)
    stats_file = output_dir / f"statistics_{timestamp}.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    # Full export JSON
    json_file = output_dir / f"documents_{timestamp}.json"
    json_count = export_to_json(db_path, json_file)

    # CSV export
    csv_file = output_dir / f"documents_{timestamp}.csv"
    csv_count = export_to_csv(db_path, csv_file)

    # Markdown report
    md_file = output_dir / f"report_{timestamp}.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(f"# Document Processing Report\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- **Total Documents**: {stats['total_documents']}\n")
        f.write(f"- **Average AI Confidence**: {stats['average_confidence']['ai']:.1%}\n")
        f.write(f"- **Average OCR Confidence**: {stats['average_confidence']['ocr']:.1%}\n\n")

        f.write(f"## By Document Type\n\n")
        f.write(f"| Type | Count | Avg Confidence |\n")
        f.write(f"|------|-------|----------------|\n")
        for item in stats['by_type']:
            f.write(f"| {item['type']} | {item['count']} | {item['avg_confidence']:.1%} |\n")

        if 'by_server' in stats:
            f.write(f"\n## By Server (Distributed)\n\n")
            f.write(f"| Server | Count |\n")
            f.write(f"|--------|-------|\n")
            for item in stats['by_server']:
                server_name = item['server'].split('//')[1].split(':')[0]
                f.write(f"| {server_name} | {item['count']} |\n")

        f.write(f"\n## Processing Timeline (Last 24h)\n\n")
        f.write(f"| Hour | Documents |\n")
        f.write(f"|------|----------|\n")
        for item in stats['timeline']:
            f.write(f"| {item['hour']} | {item['count']} |\n")

    return {
        'statistics': str(stats_file),
        'json': str(json_file),
        'csv': str(csv_file),
        'markdown': str(md_file),
        'document_count': json_count
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Export processing results")
    parser.add_argument('--db', default='data/documents.db', help='Database path')
    parser.add_argument('--output', default='data/exports', help='Output directory')
    parser.add_argument('--format', choices=['json', 'csv', 'all'], default='all', help='Export format')

    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    if args.format == 'all':
        print("📊 Generating complete report...")
        result = generate_report(db_path, args.output)
        print(f"\n✅ Report generated!")
        print(f"\n📁 Files:")
        print(f"   Statistics: {result['statistics']}")
        print(f"   JSON:       {result['json']}")
        print(f"   CSV:        {result['csv']}")
        print(f"   Markdown:   {result['markdown']}")
        print(f"\n📄 Documents: {result['document_count']}")

    elif args.format == 'json':
        output = Path(args.output) / f"documents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        count = export_to_json(db_path, output)
        print(f"✅ Exported {count} documents to {output}")

    elif args.format == 'csv':
        output = Path(args.output) / f"documents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        count = export_to_csv(db_path, output)
        print(f"✅ Exported {count} documents to {output}")


if __name__ == "__main__":
    main()
