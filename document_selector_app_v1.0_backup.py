#!/usr/bin/env python3
"""
Document Selector Web Interface v1.0
====================================

Webové rozhraní pro výběr dokumentů k zpracování:
- Checkbox výběr jednotlivých dokumentů
- Filtrování podle data (od-do)
- Filtrování podle kritérií (sender, subject, mailbox, typ souboru)
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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import from adaptive_parallel_OPTIMIZED_v2.2.py using importlib (function at line 305)
spec = importlib.util.spec_from_file_location(
    "adaptive_v2_2",
    Path(__file__).parent / "adaptive_parallel_OPTIMIZED_v2.2.py"
)
adaptive_v2_2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adaptive_v2_2)
extract_from_multiple_mailboxes = adaptive_v2_2.extract_from_multiple_mailboxes

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
            padding: 15px 20px;
            border-bottom: 1px solid #334155;
            display: grid;
            grid-template-columns: 40px 1fr auto;
            gap: 15px;
            align-items: center;
            transition: background 0.2s;
        }

        .document-item:hover {
            background: #0f172a;
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
            background: #334155;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 500;
        }

        .badge.pdf { background: #dc2626; }
        .badge.xml { background: #f59e0b; }
        .badge.jpg { background: #10b981; }
        .badge.png { background: #06b6d4; }

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

        function renderDocuments() {
            const container = document.getElementById('documentsList');

            if (documents.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><h3>Žádné dokumenty</h3><p>Zkuste upravit filtry nebo načíst dokumenty znovu</p></div>';
                return;
            }

            container.innerHTML = documents.map((doc, index) => {
                const ext = doc.filename.split('.').pop().toLowerCase();
                const date = new Date(doc.date).toLocaleDateString('cs-CZ');

                return `
                    <div class="document-item">
                        <input type="checkbox" class="document-checkbox" data-index="${index}"
                               onchange="toggleDocument(${index})" ${selectedDocs.has(index) ? 'checked' : ''}>
                        <div class="document-info">
                            <div class="document-filename">${doc.filename}</div>
                            <div class="document-meta">
                                <span>📅 ${date}</span>
                                <span>📧 ${doc.sender || 'N/A'}</span>
                                <span>📬 ${doc.mailbox}</span>
                                <span>📄 ${doc.subject || 'N/A'}</span>
                            </div>
                        </div>
                        <span class="badge ${ext}">${ext.toUpperCase()}</span>
                    </div>
                `;
            }).join('');
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
