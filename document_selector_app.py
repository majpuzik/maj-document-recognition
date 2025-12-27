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
Document Selector Web Interface v1.1 - CARD DESIGN
===================================================

Webové rozhraní pro výběr dokumentů k zpracování:
- Checkbox výběr jednotlivých dokumentů
- Filtrování podle data (od-do)
- Filtrování podle kritérií (sender, subject, mailbox, typ souboru)
- ✨ NEW: PDF OCR detection & auto-fix
- ✨ NEW: Unknown format detection s červeným rámečkem
- ✨ NEW: Card design podobný Marketing Groups
- Náhled dokumentů před zpracováním
- Spuštění zpracování vybraných dokumentů
"""

from flask import Flask, render_template_string, request, jsonify
import sys
from pathlib import Path
from datetime import datetime, timedelta
import os
import json
import importlib.util
import sqlite3

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import from adaptive_parallel_OPTIMIZED_v2.2.py using importlib (function at line 305)
try:
    spec = importlib.util.spec_from_file_location(
        "adaptive_v2_2",
        Path(__file__).parent / "adaptive_parallel_OPTIMIZED_v2.2.py"
    )
    adaptive_v2_2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adaptive_v2_2)
    extract_from_multiple_mailboxes = adaptive_v2_2.extract_from_multiple_mailboxes
except ImportError as e:
    print(f"Warning: Could not import adaptive_v2_2 module: {e}")
    print("Thunderbird extraction will not work, but database endpoints will still function")
    extract_from_multiple_mailboxes = None

# Import OCR checker for PDF detection & unknown format handling
try:
    from pdf_ocr_checker import check_and_fix_pdf, is_supported_format
except ImportError:
    print("Warning: pdf_ocr_checker not available")
    check_and_fix_pdf = None
    is_supported_format = None

app = Flask(__name__)

# Store extracted documents in memory
DOCUMENTS_CACHE = []
PROCESSING_STATUS = {"running": False, "progress": 0, "total": 0}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document Selector - MAJ Document Recognition</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }

        h1 {
            color: #60a5fa;
            font-size: 2em;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #94a3b8;
            font-size: 1.1em;
        }

        .filters {
            background: #1e293b;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .filter-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }

        .filter-group {
            display: flex;
            flex-direction: column;
        }

        label {
            color: #94a3b8;
            font-size: 0.9em;
            margin-bottom: 5px;
            font-weight: 500;
        }

        input, select {
            background: #0f172a;
            color: #e2e8f0;
            border: 1px solid #334155;
            padding: 10px;
            border-radius: 6px;
            font-size: 1em;
            transition: all 0.3s;
        }

        input:focus, select:focus {
            outline: none;
            border-color: #60a5fa;
            box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
        }

        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }

        button {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 500;
        }

        button:hover {
            background: #2563eb;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        }

        button:active {
            transform: translateY(0);
        }

        button.secondary {
            background: #475569;
        }

        button.secondary:hover {
            background: #334155;
        }

        button.danger {
            background: #ef4444;
        }

        button.danger:hover {
            background: #dc2626;
        }

        button.success {
            background: #10b981;
        }

        button.success:hover {
            background: #059669;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: #1e293b;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .stat-value {
            font-size: 2.5em;
            color: #60a5fa;
            font-weight: bold;
        }

        .stat-label {
            color: #94a3b8;
            font-size: 0.9em;
            margin-top: 5px;
        }

        .documents {
            background: #1e293b;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .documents-header {
            background: #334155;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .documents-list {
            max-height: 600px;
            overflow-y: auto;
        }

        .document-item {
            background: #1e293b;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 12px;
            display: grid;
            grid-template-columns: 40px 1fr auto;
            gap: 15px;
            align-items: center;
            transition: all 0.2s;
            border: 2px solid #334155;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .document-item:hover {
            background: #0f172a;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        }

        /* v1.1: Card borders based on OCR status */
        .document-item.unknown-format {
            border-color: #ef4444;
            background: rgba(239, 68, 68, 0.05);
        }

        .document-item.has-ocr {
            border-color: #10b981;
        }

        .document-item.no-ocr {
            border-color: #f59e0b;
        }

        .document-item.ocr-fixed {
            border-color: #3b82f6;
        }

        .document-checkbox {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }

        .document-info {
            flex: 1;
        }

        .document-filename {
            color: #e2e8f0;
            font-weight: 500;
            margin-bottom: 5px;
        }

        .document-meta {
            color: #94a3b8;
            font-size: 0.85em;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }

        .document-meta span {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
            text-transform: uppercase;
            display: inline-block;
            margin-right: 5px;
        }

        /* File type badges */
        .badge.pdf { background: #dc2626; color: white; }
        .badge.xml { background: #f59e0b; color: white; }
        .badge.jpg { background: #10b981; color: white; }
        .badge.png { background: #06b6d4; color: white; }

        /* OCR status badges (podobné SUB badge v Marketing Groups) */
        .badge-ocr {
            background: #10b981;
            color: white;
        }

        .badge-success {
            background: #10b981;
            color: white;
        }

        .badge-warning {
            background: #f59e0b;
            color: white;
        }

        .badge-danger {
            background: #ef4444;
            color: white;
        }

        .badge-info {
            background: #3b82f6;
            color: white;
        }

        .badge-format {
            background: #334155;
            color: #e2e8f0;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #94a3b8;
        }

        .spinner {
            border: 4px solid #334155;
            border-top: 4px solid #60a5fa;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .progress-bar {
            background: #0f172a;
            border-radius: 8px;
            overflow: hidden;
            height: 30px;
            margin-top: 15px;
            display: none;
        }

        .progress-bar.active {
            display: block;
        }

        .progress-fill {
            background: linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%);
            height: 100%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 500;
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #94a3b8;
        }

        .empty-state-icon {
            font-size: 4em;
            margin-bottom: 20px;
            opacity: 0.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 Document Selector</h1>
            <p class="subtitle">Vyberte dokumenty k zpracování pomocí AI rozpoznávání</p>
        </div>

        <div class="filters">
            <h3 style="color: #60a5fa; margin-bottom: 15px;">🔍 Filtry</h3>

            <div class="filter-row">
                <div class="filter-group">
                    <label for="dateFrom">Datum od:</label>
                    <input type="date" id="dateFrom" value="{{ date_from }}">
                </div>

                <div class="filter-group">
                    <label for="dateTo">Datum do:</label>
                    <input type="date" id="dateTo" value="{{ date_to }}">
                </div>

                <div class="filter-group">
                    <label for="mailbox">Mailbox:</label>
                    <select id="mailbox">
                        <option value="">Všechny</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="fileType">Typ souboru:</label>
                    <select id="fileType">
                        <option value="">Všechny</option>
                        <option value="pdf">PDF</option>
                        <option value="xml">XML</option>
                        <option value="jpg">JPG</option>
                        <option value="png">PNG</option>
                    </select>
                </div>
            </div>

            <div class="filter-row">
                <div class="filter-group">
                    <label for="sender">Odesílatel (obsahuje):</label>
                    <input type="text" id="sender" placeholder="např. faktura@, banka@">
                </div>

                <div class="filter-group">
                    <label for="subject">Předmět (obsahuje):</label>
                    <input type="text" id="subject" placeholder="např. Faktura, Výpis">
                </div>

                <div class="filter-group">
                    <label for="limit">Maximální počet:</label>
                    <input type="number" id="limit" value="100" min="1" max="2000">
                </div>
            </div>

            <div class="button-group">
                <button onclick="loadDocuments()" class="success">🔄 Načíst dokumenty</button>
                <button onclick="loadUnclassifiedDocuments()" class="success">📋 Načíst neklasifikované</button>
                <button onclick="clearFilters()" class="secondary">🗑️ Vymazat filtry</button>
            </div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="totalDocs">0</div>
                <div class="stat-label">Celkem dokumentů</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="selectedDocs">0</div>
                <div class="stat-label">Vybraných</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="pdfCount">0</div>
                <div class="stat-label">PDF</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="xmlCount">0</div>
                <div class="stat-label">XML</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="imageCount">0</div>
                <div class="stat-label">Obrázky</div>
            </div>
        </div>

        <div class="documents">
            <div class="documents-header">
                <div>
                    <input type="checkbox" id="selectAll" style="margin-right: 10px; cursor: pointer;">
                    <label for="selectAll" style="cursor: pointer; color: #e2e8f0;">Vybrat vše</label>
                </div>
                <div class="button-group" style="margin: 0;">
                    <button onclick="processSelected()" class="success">▶️ Zpracovat vybrané</button>
                    <button onclick="exportSelection()" class="secondary">💾 Export výběru</button>
                </div>
            </div>

            <div class="progress-bar" id="progressBar">
                <div class="progress-fill" id="progressFill">0%</div>
            </div>

            <div class="documents-list" id="documentsList">
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Načítání dokumentů...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let documents = [];
        let selectedDocs = new Set();

        // Load documents on page load
        window.addEventListener('DOMContentLoaded', function() {
            // Set default date range (last 30 days)
            const today = new Date();
            const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
            document.getElementById('dateTo').value = today.toISOString().split('T')[0];
            document.getElementById('dateFrom').value = thirtyDaysAgo.toISOString().split('T')[0];

            loadDocuments();
        });

        async function loadDocuments() {
            const filters = {
                date_from: document.getElementById('dateFrom').value,
                date_to: document.getElementById('dateTo').value,
                mailbox: document.getElementById('mailbox').value,
                file_type: document.getElementById('fileType').value,
                sender: document.getElementById('sender').value,
                subject: document.getElementById('subject').value,
                limit: parseInt(document.getElementById('limit').value)
            };

            document.getElementById('documentsList').innerHTML = '<div class="loading"><div class="spinner"></div><p>Načítání dokumentů...</p></div>';

            try {
                const response = await fetch('/api/documents', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(filters)
                });

                const data = await response.json();
                documents = data.documents || [];
                selectedDocs.clear();

                renderDocuments();
                updateStats();
                updateMailboxes();
            } catch (error) {
                document.getElementById('documentsList').innerHTML =
                    '<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>Chyba při načítání</h3><p>' + error.message + '</p></div>';
            }
        }

        async function loadUnclassifiedDocuments() {
            document.getElementById('documentsList').innerHTML = '<div class="loading"><div class="spinner"></div><p>Načítání neklasifikovaných dokumentů...</p></div>';

            try {
                const limit = parseInt(document.getElementById('limit').value);
                const response = await fetch(`/api/documents/unclassified?limit=${limit}`, {
                    method: 'GET',
                    headers: {'Content-Type': 'application/json'}
                });

                const data = await response.json();

                if (!data.success) {
                    throw new Error(data.error || 'Nepodařilo se načíst dokumenty');
                }

                documents = data.documents || [];
                selectedDocs.clear();

                renderUnclassifiedDocuments();
                updateStats();
            } catch (error) {
                document.getElementById('documentsList').innerHTML =
                    '<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>Chyba při načítání</h3><p>' + error.message + '</p></div>';
            }
        }

        function renderDocuments() {
            const container = document.getElementById('documentsList');

            if (documents.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><h3>Žádné dokumenty</h3><p>Zkuste upravit filtry nebo načíst dokumenty znovu</p></div>';
                return;
            }

            container.innerHTML = documents.map((doc, index) => {
                const ext = doc.filename.split('.').pop().toLowerCase();
                const date = new Date(doc.date).toLocaleDateString('cs-CZ');

                // v1.1: Determine card class based on OCR status
                let cardClass = 'document-item';
                if (doc.is_supported === false) {
                    cardClass += ' unknown-format';
                } else if (doc.format === 'PDF Document') {
                    if (doc.has_ocr) {
                        cardClass += ' has-ocr';
                    } else if (doc.ocr_fixed) {
                        cardClass += ' ocr-fixed';
                    } else {
                        cardClass += ' no-ocr';
                    }
                }

                // v1.1: Build badges (podobné SUB badge v Marketing Groups)
                let badges = `<span class="badge ${ext}">${ext.toUpperCase()}</span>`;

                if (doc.is_supported === false) {
                    badges += '<span class="badge badge-danger">❌ NEZNÁMÝ</span>';
                } else if (doc.format === 'PDF Document') {
                    if (doc.has_ocr) {
                        badges += '<span class="badge badge-success">✅ OCR</span>';
                    } else if (doc.ocr_fixed) {
                        badges += '<span class="badge badge-info">🔧 FIXED</span>';
                    } else if (doc.ocr_status === 'error') {
                        badges += '<span class="badge badge-danger">❌ OCR ERR</span>';
                    } else {
                        badges += '<span class="badge badge-warning">⚠️ BEZ OCR</span>';
                    }
                }

                // v1.1: OCR message (pokud existuje)
                let ocrInfo = '';
                if (doc.ocr_message) {
                    const isWarning = doc.ocr_message.includes('❌') || doc.ocr_message.includes('⚠️');
                    const infoStyle = isWarning ? 'color: #fbbf24; font-size: 0.85em; font-style: italic; margin-top: 5px;' : 'color: #60a5fa; font-size: 0.85em; margin-top: 5px;';
                    ocrInfo = `<div style="${infoStyle}">${escapeHtml(doc.ocr_message)}</div>`;
                }

                return `
                    <div class="${cardClass}">
                        <input type="checkbox" class="document-checkbox" data-index="${index}"
                               onchange="toggleDocument(${index})" ${selectedDocs.has(index) ? 'checked' : ''}>
                        <div class="document-info">
                            <div class="document-filename">
                                📄 ${escapeHtml(doc.filename)}
                                <div style="margin-top: 5px;">${badges}</div>
                            </div>
                            <div class="document-meta">
                                <span>📅 ${date}</span>
                                <span>📧 ${escapeHtml(doc.sender) || 'N/A'}</span>
                                <span>📬 ${doc.mailbox}</span>
                            </div>
                            ${ocrInfo}
                        </div>
                    </div>
                `;
            }).join('');
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function renderUnclassifiedDocuments() {
            const container = document.getElementById('documentsList');

            if (documents.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><h3>Vše klasifikováno</h3><p>Žádné neklasifikované dokumenty k revizi</p></div>';
                return;
            }

            container.innerHTML = documents.map((doc, index) => {
                const ext = (doc.file_name || '').split('.').pop().toLowerCase();
                const date = doc.date_received || doc.created_at || 'N/A';
                const docType = doc.document_type || 'jine';
                const confidence = doc.ai_confidence ? (doc.ai_confidence * 100).toFixed(0) + '%' : 'N/A';

                // Determine card color based on document type
                let cardClass = 'document-item';
                const typeColors = {
                    'faktura': 'has-ocr',      // green
                    'bankovni_vypis': 'has-ocr',
                    'stvrzenka': 'has-ocr',
                    'objednavka': 'has-ocr',
                    'reklama': 'no-ocr',       // yellow
                    'jine': 'ocr-fixed',       // blue
                    'soudni_dokument': 'unknown-format' // red
                };
                cardClass += ' ' + (typeColors[docType] || 'ocr-fixed');

                // Build badges
                let badges = `<span class="badge ${ext}">${ext.toUpperCase()}</span>`;
                badges += `<span class="badge badge-info">📊 ${docType.toUpperCase()}</span>`;
                badges += `<span class="badge badge-warning">🎯 ${confidence}</span>`;

                // Classification actions
                const actions = `
                    <div style="margin-top: 10px; display: flex; gap: 10px;">
                        <button onclick="confirmDoc(${doc.id})" class="success" style="padding: 8px 16px; font-size: 0.9em;">✓ Potvrdit</button>
                        <button onclick="showChangeDialog(${doc.id}, '${docType}')" class="secondary" style="padding: 8px 16px; font-size: 0.9em;">✎ Změnit</button>
                    </div>
                `;

                return `
                    <div class="${cardClass}">
                        <div class="document-info" style="width: 100%;">
                            <div class="document-filename">
                                📄 ${escapeHtml(doc.file_name || 'N/A')}
                                <div style="margin-top: 5px;">${badges}</div>
                            </div>
                            <div class="document-meta">
                                <span>📧 ${escapeHtml(doc.sender) || 'Unknown'}</span>
                                <span>📅 ${date}</span>
                                ${doc.subject ? '<span>💬 ' + escapeHtml(doc.subject) + '</span>' : ''}
                            </div>
                            ${actions}
                        </div>
                    </div>
                `;
            }).join('');
        }

        async function confirmDoc(docId) {
            try {
                const response = await fetch('/api/classify/confirm', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({document_ids: [docId]})
                });

                const data = await response.json();
                if (data.success) {
                    // Remove confirmed document from list
                    documents = documents.filter(d => d.id !== docId);
                    renderUnclassifiedDocuments();
                    updateStats();
                    alert('✅ Dokument potvrzen');
                } else {
                    alert('❌ Chyba: ' + data.error);
                }
            } catch (error) {
                alert('❌ Chyba: ' + error.message);
            }
        }

        function showChangeDialog(docId, currentType) {
            const types = ['faktura', 'bankovni_vypis', 'stvrzenka', 'objednavka', 'vyzva_k_platbe', 'oznameni_o_zaplaceni', 'soudni_dokument', 'reklama', 'obchodni_korespondence', 'jine'];
            const newType = prompt(`Změnit typ dokumentu z "${currentType}" na:\n\n${types.map((t, i) => `${i+1}. ${t}`).join('\n')}\n\nZadejte číslo (1-${types.length}):`, '');

            if (newType && newType >= 1 && newType <= types.length) {
                changeDocType(docId, types[newType - 1]);
            } else if (newType !== null) {
                alert('❌ Neplatná volba');
            }
        }

        async function changeDocType(docId, newType) {
            try {
                const response = await fetch('/api/classify/change', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        document_id: docId,
                        document_type: newType,
                        rating: 5
                    })
                });

                const data = await response.json();
                if (data.success) {
                    // Remove changed document from list
                    documents = documents.filter(d => d.id !== docId);
                    renderUnclassifiedDocuments();
                    updateStats();
                    alert(`✅ Dokument překlasifikován: ${data.old_type} → ${data.new_type}`);
                } else {
                    alert('❌ Chyba: ' + data.error);
                }
            } catch (error) {
                alert('❌ Chyba: ' + error.message);
            }
        }

        function toggleDocument(index) {
            if (selectedDocs.has(index)) {
                selectedDocs.delete(index);
            } else {
                selectedDocs.add(index);
            }
            updateStats();
        }

        document.getElementById('selectAll').addEventListener('change', function(e) {
            if (e.target.checked) {
                documents.forEach((doc, i) => selectedDocs.add(i));
            } else {
                selectedDocs.clear();
            }
            renderDocuments();
            updateStats();
        });

        function updateStats() {
            document.getElementById('totalDocs').textContent = documents.length;
            document.getElementById('selectedDocs').textContent = selectedDocs.size;

            const pdfCount = documents.filter(d => d.filename.toLowerCase().endsWith('.pdf')).length;
            const xmlCount = documents.filter(d => d.filename.toLowerCase().endsWith('.xml')).length;
            const imageCount = documents.filter(d => /\.(jpg|jpeg|png)$/i.test(d.filename)).length;

            document.getElementById('pdfCount').textContent = pdfCount;
            document.getElementById('xmlCount').textContent = xmlCount;
            document.getElementById('imageCount').textContent = imageCount;
        }

        function updateMailboxes() {
            const mailboxes = [...new Set(documents.map(d => d.mailbox))];
            const select = document.getElementById('mailbox');
            select.innerHTML = '<option value="">Všechny</option>' +
                mailboxes.map(m => `<option value="${m}">${m}</option>`).join('');
        }

        async function processSelected() {
            if (selectedDocs.size === 0) {
                alert('Vyberte alespoň jeden dokument!');
                return;
            }

            if (!confirm(`Opravdu chcete zpracovat ${selectedDocs.size} dokumentů?`)) {
                return;
            }

            const selectedDocuments = Array.from(selectedDocs).map(i => documents[i]);

            document.getElementById('progressBar').classList.add('active');
            document.getElementById('progressFill').style.width = '0%';
            document.getElementById('progressFill').textContent = '0%';

            try {
                const response = await fetch('/api/process', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({documents: selectedDocuments})
                });

                const data = await response.json();

                if (data.success) {
                    alert(`Zpracování spuštěno! ${data.total} dokumentů bude zpracováno.`);
                    monitorProgress();
                } else {
                    alert('Chyba: ' + data.error);
                }
            } catch (error) {
                alert('Chyba při spouštění: ' + error.message);
            }
        }

        async function monitorProgress() {
            const interval = setInterval(async () => {
                try {
                    const response = await fetch('/api/progress');
                    const data = await response.json();

                    if (!data.running) {
                        clearInterval(interval);
                        document.getElementById('progressBar').classList.remove('active');
                        alert(`Zpracování dokončeno! Úspěšně: ${data.progress}/${data.total}`);
                        return;
                    }

                    const percent = Math.round((data.progress / data.total) * 100);
                    document.getElementById('progressFill').style.width = percent + '%';
                    document.getElementById('progressFill').textContent = `${data.progress}/${data.total} (${percent}%)`;
                } catch (error) {
                    console.error('Error monitoring progress:', error);
                }
            }, 1000);
        }

        function exportSelection() {
            const selected = Array.from(selectedDocs).map(i => documents[i]);
            const dataStr = JSON.stringify(selected, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);

            const exportFileDefaultName = `document_selection_${new Date().toISOString().split('T')[0]}.json`;

            const linkElement = document.createElement('a');
            linkElement.setAttribute('href', dataUri);
            linkElement.setAttribute('download', exportFileDefaultName);
            linkElement.click();
        }

        function clearFilters() {
            document.getElementById('dateFrom').value = '';
            document.getElementById('dateTo').value = '';
            document.getElementById('mailbox').value = '';
            document.getElementById('fileType').value = '';
            document.getElementById('sender').value = '';
            document.getElementById('subject').value = '';
            document.getElementById('limit').value = '100';
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Main page with document selector"""
    today = datetime.now().strftime('%Y-%m-%d')
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    return render_template_string(
        HTML_TEMPLATE,
        date_from=thirty_days_ago,
        date_to=today
    )


@app.route('/api/documents', methods=['POST'])
def get_documents():
    """Load documents from Thunderbird with filters"""
    global DOCUMENTS_CACHE

    try:
        if extract_from_multiple_mailboxes is None:
            return jsonify({
                'success': False,
                'error': 'Thunderbird extraction not available - missing dependencies'
            }), 503

        filters = request.json

        # Extract documents from Thunderbird
        profile_path = Path.home() / "Library" / "Thunderbird" / "Profiles"
        temp_dir = Path("/tmp/doc_selector_attachments")
        temp_dir.mkdir(exist_ok=True)

        limit = filters.get('limit', 100)

        # Extract attachments
        attachments = extract_from_multiple_mailboxes(
            profile_path=str(profile_path),
            temp_dir=str(temp_dir),
            limit=limit,
            max_size_mb=3
        )

        # Apply filters
        filtered = []
        for att in attachments:
            # Date filter
            if filters.get('date_from'):
                date_from = datetime.fromisoformat(filters['date_from'])
                if att['date'] < date_from:
                    continue

            if filters.get('date_to'):
                date_to = datetime.fromisoformat(filters['date_to']) + timedelta(days=1)
                if att['date'] >= date_to:
                    continue

            # Mailbox filter
            if filters.get('mailbox') and att['mailbox'] != filters['mailbox']:
                continue

            # File type filter
            if filters.get('file_type'):
                ext = att['filename'].split('.')[-1].lower()
                if ext != filters['file_type'].lower():
                    continue

            # Sender filter
            if filters.get('sender') and filters['sender'].lower() not in att['sender'].lower():
                continue

            # Subject filter
            if filters.get('subject') and filters['subject'].lower() not in att['subject'].lower():
                continue

            filtered.append(att)

        # Convert datetime to string for JSON
        for att in filtered:
            att['date'] = att['date'].isoformat()

        # v1.1: Check format & OCR for each document
        for att in filtered:
            # 1. Check if format is supported
            is_supported, format_type, format_msg = is_supported_format(att['path'])
            att['is_supported'] = is_supported
            att['format'] = format_type
            att['format_message'] = format_msg

            # 2. For PDF - check and add OCR if needed
            if format_type == 'PDF Document':
                try:
                    ocr_result = check_and_fix_pdf(att['path'], auto_fix=True)
                    att['has_ocr'] = ocr_result['has_ocr']
                    att['ocr_fixed'] = ocr_result['fixed']
                    att['ocr_status'] = ocr_result['status']
                    att['ocr_message'] = ocr_result['message']
                except Exception as e:
                    att['has_ocr'] = False
                    att['ocr_fixed'] = False
                    att['ocr_status'] = 'error'
                    att['ocr_message'] = f"❌ Chyba při OCR: {str(e)}"
            else:
                # Non-PDF files
                att['has_ocr'] = None
                att['ocr_fixed'] = False
                att['ocr_status'] = 'n/a'
                att['ocr_message'] = ''

        DOCUMENTS_CACHE = filtered

        return jsonify({
            'success': True,
            'documents': filtered,
            'total': len(filtered)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/process', methods=['POST'])
def process_documents():
    """Start processing selected documents"""
    global PROCESSING_STATUS

    try:
        data = request.json
        documents = data.get('documents', [])

        if not documents:
            return jsonify({'success': False, 'error': 'No documents selected'})

        # Start processing in background
        PROCESSING_STATUS = {
            'running': True,
            'progress': 0,
            'total': len(documents)
        }

        # Here you would start the actual processing
        # For now, we'll just simulate it
        import threading

        def process_in_background():
            import time
            from adaptive_parallel_OPTIMIZED_v2_2 import main as process_main

            # TODO: Integrate with v2.2 processing
            for i, doc in enumerate(documents):
                time.sleep(1)  # Simulate processing
                PROCESSING_STATUS['progress'] = i + 1

            PROCESSING_STATUS['running'] = False

        thread = threading.Thread(target=process_in_background, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'total': len(documents),
            'message': f'Processing started for {len(documents)} documents'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get current processing progress"""
    return jsonify(PROCESSING_STATUS)


@app.route('/api/documents/unclassified', methods=['GET'])
def get_unclassified_documents():
    """Get unclassified documents from database (user_confirmed=0)"""
    try:
        db_path = Path('data/documents.db')
        if not db_path.exists():
            return jsonify({'success': False, 'error': 'Database not found', 'documents': []})

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        group_by_sender = request.args.get('group_by_sender', 'false').lower() == 'true'

        # Query unclassified documents
        query = """
            SELECT
                id, file_name, file_path, document_type,
                ai_confidence, sender, subject, date_received,
                created_at, ai_method, ocr_confidence
            FROM documents
            WHERE user_confirmed = 0
            ORDER BY sender, date_received DESC
            LIMIT ? OFFSET ?
        """

        cursor.execute(query, (limit, offset))
        rows = cursor.fetchall()

        # Convert to dictionaries
        documents = []
        for row in rows:
            doc = dict(row)
            documents.append(doc)

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM documents WHERE user_confirmed = 0")
        total_count = cursor.fetchone()[0]

        conn.close()

        # Group by sender if requested
        if group_by_sender:
            grouped = {}
            for doc in documents:
                sender = doc['sender'] or 'Unknown'
                if sender not in grouped:
                    grouped[sender] = []
                grouped[sender].append(doc)

            return jsonify({
                'success': True,
                'total': total_count,
                'grouped': grouped,
                'sender_count': len(grouped)
            })

        return jsonify({
            'success': True,
            'total': total_count,
            'documents': documents
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/classify/confirm', methods=['POST'])
def confirm_classification():
    """Confirm AI classification for document(s)"""
    try:
        data = request.json
        document_ids = data.get('document_ids', [])

        if not document_ids:
            return jsonify({'success': False, 'error': 'No document IDs provided'}), 400

        db_path = Path('data/documents.db')
        if not db_path.exists():
            return jsonify({'success': False, 'error': 'Database not found'}), 404

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Update user_confirmed to 1
        placeholders = ','.join('?' * len(document_ids))
        query = f"""
            UPDATE documents
            SET user_confirmed = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        """

        cursor.execute(query, document_ids)
        conn.commit()
        updated_count = cursor.rowcount
        conn.close()

        return jsonify({
            'success': True,
            'updated': updated_count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/classify/change', methods=['POST'])
def change_classification():
    """Change classification for document and learn from it"""
    try:
        data = request.json
        document_id = data.get('document_id')
        new_type = data.get('document_type')
        user_rating = data.get('rating', 5)  # Default rating 5/5

        if not document_id or not new_type:
            return jsonify({'success': False, 'error': 'Missing document_id or document_type'}), 400

        db_path = Path('data/documents.db')
        if not db_path.exists():
            return jsonify({'success': False, 'error': 'Database not found'}), 404

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get old classification for learning
        cursor.execute("""
            SELECT document_type, ai_confidence, ocr_text, sender
            FROM documents WHERE id = ?
        """, (document_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Document not found'}), 404

        old_type, old_confidence, ocr_text, sender = row

        # Update document with new classification
        cursor.execute("""
            UPDATE documents
            SET document_type = ?,
                user_confirmed = 1,
                user_rating = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_type, user_rating, document_id))

        # Add to training data for ML learning
        if ocr_text:
            cursor.execute("""
                INSERT INTO training_data (document_id, text, document_type, confidence, source)
                VALUES (?, ?, ?, ?, 'user_correction')
            """, (document_id, ocr_text, new_type, 1.0))

        # Add to classification history
        cursor.execute("""
            INSERT INTO classification_history (document_id, method, predicted_type, confidence, metadata)
            VALUES (?, 'user_correction', ?, 1.0, ?)
        """, (document_id, new_type, f'{{"old_type": "{old_type}", "old_confidence": {old_confidence}}}'))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'document_id': document_id,
            'old_type': old_type,
            'new_type': new_type,
            'message': 'Classification updated and added to training data'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/groups/by-sender', methods=['GET'])
def group_by_sender():
    """Group documents by sender with statistics"""
    try:
        db_path = Path('data/documents.db')
        if not db_path.exists():
            return jsonify({'success': False, 'error': 'Database not found'}), 404

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get only unclassified documents parameter
        unclassified_only = request.args.get('unclassified_only', 'true').lower() == 'true'

        # Query to group by sender
        where_clause = "WHERE user_confirmed = 0" if unclassified_only else ""
        query = f"""
            SELECT
                sender,
                COUNT(*) as document_count,
                COUNT(CASE WHEN user_confirmed = 0 THEN 1 END) as unclassified_count,
                GROUP_CONCAT(DISTINCT document_type) as document_types
            FROM documents
            {where_clause}
            GROUP BY sender
            ORDER BY document_count DESC
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        groups = []
        for row in rows:
            groups.append({
                'sender': row['sender'] or 'Unknown',
                'document_count': row['document_count'],
                'unclassified_count': row['unclassified_count'],
                'document_types': row['document_types'].split(',') if row['document_types'] else []
            })

        conn.close()

        return jsonify({
            'success': True,
            'groups': groups,
            'total_senders': len(groups)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 70)
    print("📄 DOCUMENT SELECTOR WEB INTERFACE")
    print("=" * 70)
    print()
    print("🌐 Opening: http://localhost:5050")
    print()
    print("Features:")
    print("  ✅ Checkbox selection")
    print("  ✅ Date range filter (od-do)")
    print("  ✅ Mailbox, file type, sender, subject filters")
    print("  ✅ Live processing progress")
    print("  ✅ Export selection to JSON")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 70)

    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)
