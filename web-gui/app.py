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
Document Matching Web GUI
Simple Flask application to view matched and unmatched documents
"""

import sys
import yaml
from pathlib import Path
from flask import Flask, render_template, jsonify
from flask_cors import CORS

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db_manager import DatabaseManager
from src.matching.document_matcher import DocumentMatcher

app = Flask(__name__)
CORS(app)

# Load config
config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Initialize database
db = DatabaseManager(config)
matcher = DocumentMatcher(db)


@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/api/chains')
def get_chains():
    """Get all document chains"""
    try:
        chains = matcher.get_all_chains()

        # Group by status
        by_status = {
            'completed': [],
            'delivered': [],
            'invoiced': [],
            'ordered': [],
            'unknown': []
        }

        for chain in chains:
            status = chain.get('status', 'unknown')
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(chain)

        return jsonify({
            'success': True,
            'chains': chains,
            'by_status': by_status,
            'total': len(chains)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chains/<status>')
def get_chains_by_status(status):
    """Get chains filtered by status"""
    try:
        chains = matcher.get_all_chains(status=status)
        return jsonify({
            'success': True,
            'chains': chains,
            'total': len(chains)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/unmatched')
def get_unmatched():
    """Get unmatched documents"""
    try:
        # Get all documents
        conn = db._get_connection()
        cursor = conn.cursor()

        # Documents not in any chain
        cursor.execute("""
            SELECT d.id, d.file_name, d.document_type, d.classification_date
            FROM documents d
            LEFT JOIN matched_document_chains c ON (
                d.id = c.order_doc_id OR
                d.id = c.invoice_doc_id OR
                d.id = c.delivery_note_doc_id OR
                d.id = c.payment_doc_id OR
                d.id = c.complaint_doc_id OR
                d.id = c.refund_doc_id
            )
            WHERE c.id IS NULL
            ORDER BY d.classification_date DESC
            LIMIT 500
        """)

        unmatched = []
        for row in cursor.fetchall():
            unmatched.append({
                'id': row[0],
                'file_name': row[1],
                'document_type': row[2],
                'classification_date': row[3]
            })

        conn.close()

        return jsonify({
            'success': True,
            'unmatched': unmatched,
            'total': len(unmatched)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/document/<int:doc_id>')
def get_document(doc_id):
    """Get document details"""
    try:
        # Get document
        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT d.*, m.*
            FROM documents d
            LEFT JOIN document_metadata m ON d.id = m.document_id
            WHERE d.id = ?
        """, (doc_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404

        # Build document object
        doc = {
            'id': row[0],
            'file_name': row[1],
            'document_type': row[2],
            'classification_date': row[3],
            'metadata': {
                'order_number': row[10] if len(row) > 10 else None,
                'invoice_number': row[11] if len(row) > 11 else None,
                'delivery_note_number': row[12] if len(row) > 12 else None,
                'variable_symbol': row[13] if len(row) > 13 else None,
                'amount_with_vat': row[16] if len(row) > 16 else None,
                'vendor_name': row[20] if len(row) > 20 else None,
                'vendor_ico': row[21] if len(row) > 21 else None,
            }
        }

        return jsonify({
            'success': True,
            'document': doc
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats')
def get_stats():
    """Get statistics"""
    try:
        conn = db._get_connection()
        cursor = conn.cursor()

        # Total documents
        cursor.execute("SELECT COUNT(*) FROM documents")
        total_docs = cursor.fetchone()[0]

        # Total chains
        cursor.execute("SELECT COUNT(*) FROM matched_document_chains")
        total_chains = cursor.fetchone()[0]

        # Chains by status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM matched_document_chains
            GROUP BY status
        """)
        by_status = dict(cursor.fetchall())

        # Documents in chains
        cursor.execute("""
            SELECT COUNT(DISTINCT doc_id) FROM (
                SELECT order_doc_id AS doc_id FROM matched_document_chains WHERE order_doc_id IS NOT NULL
                UNION
                SELECT invoice_doc_id FROM matched_document_chains WHERE invoice_doc_id IS NOT NULL
                UNION
                SELECT delivery_note_doc_id FROM matched_document_chains WHERE delivery_note_doc_id IS NOT NULL
                UNION
                SELECT payment_doc_id FROM matched_document_chains WHERE payment_doc_id IS NOT NULL
            )
        """)
        docs_in_chains = cursor.fetchone()[0]

        conn.close()

        return jsonify({
            'success': True,
            'stats': {
                'total_documents': total_docs,
                'total_chains': total_chains,
                'documents_in_chains': docs_in_chains,
                'unmatched_documents': total_docs - docs_in_chains,
                'by_status': by_status
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  📋 Document Matching Web GUI")
    print("="*60)
    print(f"\n  🌐 Running on http://localhost:7775")
    print(f"\n  Press CTRL+C to quit\n")

    app.run(host='0.0.0.0', port=7775, debug=True)
