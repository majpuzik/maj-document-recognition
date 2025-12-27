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
MAJ-DOCUMENT-RECOGNITION API Server
====================================
REST API pro zpracování dokumentů a emailů.

Endpoints:
- POST /api/extract      - Extrakce dat z dokumentu
- POST /api/classify     - Klasifikace typu dokumentu
- GET  /api/status       - Stav zpracování
- GET  /api/stats        - Statistiky
- GET  /api/health       - Health check
- GET  /api/docs         - API dokumentace

Author: Claude Code
Version: 1.0.0
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import hashlib

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)
CORS(app)

# Config
API_VERSION = "1.4.0"
API_NAME = "MAJ-Document-Recognition API"

# Auto-detect paths
if Path("/home/puzik/mnt/acasis").exists():
    ACASIS_ROOT = Path("/home/puzik/mnt/acasis")
else:
    ACASIS_ROOT = Path("/Volumes/ACASIS")

BASE_DIR = ACASIS_ROOT / "apps/maj-document-recognition"
PHASE1_DIR = BASE_DIR / "phase1_output"
PHASE2_DIR = PHASE1_DIR / "phase2_results"
RESULTS_DIR = PHASE1_DIR / "phase1_results"

# Try imports
try:
    from email_extractor.phase2_direct import (
        call_ollama_32b, CLASSIFY_PROMPT, is_system_notification, force_classify_other
    )
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    is_system_notification = None
    force_classify_other = None

try:
    from src.ocr.document_processor import DocumentProcessor
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "api": API_NAME,
        "version": API_VERSION,
        "timestamp": datetime.now().isoformat(),
        "features": {
            "llm": LLM_AVAILABLE,
            "ocr": OCR_AVAILABLE
        }
    })


@app.route('/api/docs', methods=['GET'])
def docs():
    """API documentation"""
    return jsonify({
        "api": API_NAME,
        "version": API_VERSION,
        "description": "REST API pro extrakci a klasifikaci dokumentů z emailů",
        "endpoints": {
            "GET /api/health": {
                "description": "Health check",
                "response": {"status": "ok", "version": "string"}
            },
            "GET /api/docs": {
                "description": "Tato dokumentace"
            },
            "GET /api/stats": {
                "description": "Statistiky zpracování",
                "response": {
                    "phase1": {"total": "int", "success": "int", "failed": "int"},
                    "phase2": {"total": "int", "success": "int", "failed": "int"},
                    "by_type": {"invoice": "int", "contract": "int", "...": "int"}
                }
            },
            "GET /api/status": {
                "description": "Stav aktuálního zpracování",
                "response": {"running": "bool", "progress": "int", "total": "int"}
            },
            "POST /api/classify": {
                "description": "Klasifikace typu dokumentu",
                "request": {
                    "text": "string (obsah dokumentu)",
                    "subject": "string (předmět emailu, optional)",
                    "from": "string (odesílatel, optional)"
                },
                "response": {
                    "doc_type": "invoice|order|contract|marketing|correspondence|receipt|bank_statement|other",
                    "confidence": "float 0-1",
                    "extracted_fields": {}
                }
            },
            "POST /api/extract": {
                "description": "Extrakce strukturovaných dat z dokumentu",
                "request": {
                    "text": "string (obsah dokumentu)",
                    "doc_type": "string (typ dokumentu, optional)"
                },
                "response": {
                    "fields": {
                        "protistrana_nazev": "string",
                        "protistrana_ico": "string",
                        "castka_celkem": "float",
                        "datum_dokumentu": "YYYY-MM-DD",
                        "cislo_dokumentu": "string",
                        "mena": "CZK|EUR|USD",
                        "ai_summary": "string",
                        "ai_keywords": "string"
                    }
                }
            },
            "GET /api/result/<email_id>": {
                "description": "Získat výsledek zpracování emailu",
                "response": {"email_id": "string", "doc_type": "string", "extracted_fields": {}}
            },
            "GET /api/results": {
                "description": "Seznam zpracovaných dokumentů",
                "params": {
                    "type": "filter by doc_type",
                    "limit": "max results (default 100)",
                    "offset": "pagination offset"
                }
            }
        },
        "doc_types": [
            "invoice - Faktura",
            "order - Objednávka",
            "contract - Smlouva",
            "marketing - Reklamní email",
            "correspondence - Korespondence",
            "receipt - Účtenka/Potvrzení",
            "bank_statement - Bankovní výpis",
            "tax_document - Daňový doklad",
            "system_notification - Systémová notifikace (Loxone, noreply, automatické emaily)",
            "it_notes - IT poznámky (Windows, Linux, servery, Docker, licence, konfigurace)",
            "project_notes - Projektové poznámky (webové projekty, design, wireframes)"
        ],
        "force_classification": {
            "description": "API nikdy nevrátí 'other' - vždy vybere nejlepší kategorii",
            "keywords": {
                "it_notes": ["api", "key", "server", "docker", "linux", "windows", "xorg", "x11", "license"],
                "project_notes": ["katalog", "homepage", "web", "projekt", "design", "mockup"],
                "correspondence": ["schránka", "datová", "zpráva", "odpověď", "dobrý den"],
                "marketing": ["sleva", "akce", "nabídka", "newsletter", "unsubscribe"]
            }
        },
        "extracted_fields": [
            "doc_typ - Typ dokumentu",
            "protistrana_nazev - Název protistrany",
            "protistrana_ico - IČO protistrany",
            "protistrana_typ - Typ (firma/OSVČ/FO)",
            "castka_celkem - Celková částka",
            "datum_dokumentu - Datum dokumentu",
            "cislo_dokumentu - Číslo dokumentu",
            "mena - Měna (CZK/EUR/USD)",
            "stav_platby - Stav platby",
            "datum_splatnosti - Datum splatnosti",
            "kategorie - Kategorie",
            "email_from - Email odesílatele",
            "email_to - Email příjemce",
            "email_subject - Předmět",
            "od_osoba - Jméno odesílatele",
            "od_firma - Firma odesílatele",
            "ai_summary - AI souhrn",
            "ai_keywords - Klíčová slova"
        ]
    })


@app.route('/api/stats', methods=['GET'])
def stats():
    """Processing statistics"""
    # Collect stats from all phases
    phase1_stats = {"total": 0, "success": 0, "failed": 0, "by_type": {}}
    phase2_stats = {"total": 0, "success": 0, "failed": 0}

    # Phase 1 stats
    for stats_file in PHASE1_DIR.glob("phase1_stats_*.json"):
        try:
            with open(stats_file) as f:
                data = json.load(f)
                phase1_stats["success"] += data.get("success", 0)
                phase1_stats["failed"] += data.get("failed", 0)
                for doc_type, count in data.get("by_type", {}).items():
                    phase1_stats["by_type"][doc_type] = phase1_stats["by_type"].get(doc_type, 0) + count
        except:
            pass

    phase1_stats["total"] = phase1_stats["success"] + phase1_stats["failed"]

    # Phase 2 stats
    phase2_stats_file = PHASE1_DIR / "phase2_stats.json"
    if phase2_stats_file.exists():
        try:
            with open(phase2_stats_file) as f:
                data = json.load(f)
                phase2_stats = {
                    "total": data.get("total", 0),
                    "success": data.get("success", 0),
                    "failed": data.get("failed", 0)
                }
        except:
            pass

    # Count actual results
    phase1_results = len(list(RESULTS_DIR.glob("*.json"))) if RESULTS_DIR.exists() else 0
    phase2_results = len(list(PHASE2_DIR.glob("*.json"))) if PHASE2_DIR.exists() else 0

    return jsonify({
        "phase1": {
            **phase1_stats,
            "results_count": phase1_results
        },
        "phase2": {
            **phase2_stats,
            "results_count": phase2_results
        },
        "total_results": phase1_results + phase2_results,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/status', methods=['GET'])
def status():
    """Current processing status"""
    # Check if Phase 2 is running
    phase2_log = PHASE1_DIR / "phase2_direct.log"
    running = False
    progress = 0
    total = 0

    if phase2_log.exists():
        try:
            with open(phase2_log) as f:
                lines = f.readlines()
                for line in reversed(lines[-50:]):
                    if "Progress:" in line:
                        # Parse: Progress: 100/2418 | Success: 95
                        import re
                        match = re.search(r'Progress: (\d+)/(\d+)', line)
                        if match:
                            progress = int(match.group(1))
                            total = int(match.group(2))
                            running = True
                            break
                    elif "PHASE 2 COMPLETE" in line:
                        running = False
                        break
        except:
            pass

    return jsonify({
        "phase2_running": running,
        "progress": progress,
        "total": total,
        "percent": round(100 * progress / total, 1) if total > 0 else 0,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/classify', methods=['POST'])
def classify():
    """Classify document type using LLM"""
    if not LLM_AVAILABLE:
        return jsonify({"error": "LLM not available"}), 503

    data = request.json or {}
    text = data.get("text", "")
    subject = data.get("subject", "")
    from_addr = data.get("from", "")

    if not text and not subject:
        return jsonify({"error": "Missing 'text' or 'subject'"}), 400

    # Pre-classify system notifications (skip LLM - much faster!)
    if is_system_notification and is_system_notification({"from": from_addr, "subject": subject}):
        return jsonify({
            "doc_type": "system_notification",
            "confidence": 0.99,
            "extracted_fields": {
                "doc_typ": "system_notification",
                "protistrana_nazev": from_addr.split("<")[0].strip() if from_addr else "",
                "kategorie": "system",
                "ai_summary": f"Systémová notifikace: {subject}",
                "email_from": from_addr,
                "email_subject": subject
            },
            "model": "pattern_match",
            "note": "Detected as system notification (Loxone, noreply, etc.)"
        })

    prompt = CLASSIFY_PROMPT.format(
        from_addr=from_addr,
        to_addr=data.get("to", ""),
        subject=subject,
        date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
        body=text[:3000]
    )

    result = call_ollama_32b(prompt)

    if result:
        doc_type = result.get("doc_typ", "other")

        # Force classify "other" - no unclassified documents allowed
        if doc_type == "other" and force_classify_other:
            meta = {"from": from_addr, "subject": subject}
            doc_type = force_classify_other(result, meta)
            result["doc_typ"] = doc_type
            result["force_classified"] = True

        return jsonify({
            "doc_type": doc_type,
            "confidence": 0.85,
            "extracted_fields": result,
            "model": "qwen2.5:32b"
        })
    else:
        return jsonify({"error": "Classification failed"}), 500


@app.route('/api/extract', methods=['POST'])
def extract():
    """Extract structured data from document"""
    if not LLM_AVAILABLE:
        return jsonify({"error": "LLM not available"}), 503

    data = request.json or {}
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "Missing 'text'"}), 400

    prompt = f"""Extrahuj strukturovaná data z tohoto dokumentu.

DOKUMENT:
{text[:4000]}

Odpověz POUZE validním JSON:
{{
  "protistrana_nazev": "název firmy/osoby",
  "protistrana_ico": "IČO",
  "castka_celkem": 0.0,
  "datum_dokumentu": "YYYY-MM-DD",
  "cislo_dokumentu": "číslo",
  "mena": "CZK|EUR|USD",
  "ai_summary": "souhrn max 50 slov",
  "ai_keywords": "klíčová slova"
}}
"""

    result = call_ollama_32b(prompt)

    if result:
        return jsonify({
            "fields": result,
            "model": "qwen2.5:32b"
        })
    else:
        return jsonify({"error": "Extraction failed"}), 500


@app.route('/api/result/<email_id>', methods=['GET'])
def get_result(email_id):
    """Get processing result for specific email"""
    # Search in Phase 1 results
    result_file = RESULTS_DIR / f"{email_id}.json"
    if result_file.exists():
        with open(result_file) as f:
            return jsonify(json.load(f))

    # Search in Phase 2 results
    result_file = PHASE2_DIR / f"{email_id}.json"
    if result_file.exists():
        with open(result_file) as f:
            return jsonify(json.load(f))

    return jsonify({"error": "Result not found"}), 404


@app.route('/api/results', methods=['GET'])
def list_results():
    """List processed documents"""
    doc_type = request.args.get('type')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))

    results = []

    # Collect from Phase 1
    if RESULTS_DIR.exists():
        for f in list(RESULTS_DIR.glob("*.json"))[offset:offset+limit]:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    if doc_type and data.get("doc_type") != doc_type:
                        continue
                    results.append({
                        "email_id": data.get("email_id", f.stem),
                        "doc_type": data.get("doc_type", "unknown"),
                        "source": data.get("source", "phase1")
                    })
            except:
                pass

    return jsonify({
        "results": results[:limit],
        "count": len(results),
        "offset": offset,
        "limit": limit
    })


# ============================================================================
# PAPERLESS-NGX INTEGRATION
# ============================================================================

# Try to import PaperlessAPI
try:
    from src.integrations.paperless_api import PaperlessAPI
    PAPERLESS_AVAILABLE = True
except ImportError:
    PAPERLESS_AVAILABLE = False


@app.route('/api/upload_paperless', methods=['POST'])
def upload_paperless():
    """
    Upload document to Paperless-ngx with classification and user tag.

    Request body:
    {
        "file_path": "/path/to/document.pdf",
        "paperless_url": "http://192.168.10.35:8000",
        "paperless_token": "your-api-token",
        "user_tag": "Martin",  # Required - user permission tag
        "title": "Faktura 2025001",
        "doc_type": "invoice",
        "correspondent": "Vodafone",
        "tags": ["Faktura", "Telekomunikace"],
        "custom_fields": {
            "castka": 1210.0,
            "ico": "25788001"
        }
    }
    """
    if not PAPERLESS_AVAILABLE:
        return jsonify({"error": "Paperless integration not available"}), 503

    data = request.json or {}

    # Required fields
    file_path = data.get("file_path")
    paperless_url = data.get("paperless_url")
    paperless_token = data.get("paperless_token")
    user_tag = data.get("user_tag")

    if not file_path:
        return jsonify({"error": "Missing 'file_path'"}), 400
    if not paperless_url:
        return jsonify({"error": "Missing 'paperless_url'"}), 400
    if not paperless_token:
        return jsonify({"error": "Missing 'paperless_token'"}), 400
    if not user_tag:
        return jsonify({"error": "Missing 'user_tag' - required for access control"}), 400

    if not Path(file_path).exists():
        return jsonify({"error": f"File not found: {file_path}"}), 404

    # Initialize Paperless API
    config = {
        "paperless": {
            "url": paperless_url,
            "api_token": paperless_token,
            "auto_create_tags": True,
            "auto_create_correspondents": True,
            "auto_create_document_types": True,
            "check_duplicates": True
        }
    }

    try:
        api = PaperlessAPI(config)

        # Test connection
        if not api.test_connection():
            return jsonify({"error": "Cannot connect to Paperless-ngx"}), 503

        # Prepare tags - always include user_tag first
        tags = [f"User:{user_tag}"]  # Prefix for clarity
        if data.get("tags"):
            tags.extend(data.get("tags"))

        # Upload document
        result = api.upload_document(
            file_path=file_path,
            title=data.get("title"),
            document_type=data.get("doc_type"),
            correspondent=data.get("correspondent"),
            tags=tags
        )

        if result.get("success"):
            return jsonify({
                "success": True,
                "paperless_id": result.get("paperless_id"),
                "duplicate": result.get("duplicate", False),
                "user_tag": f"User:{user_tag}",
                "paperless_url": f"{paperless_url}/documents/{result.get('paperless_id')}"
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Upload failed")
            }), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/classify_and_upload', methods=['POST'])
def classify_and_upload():
    """
    Classify document and upload to Paperless-ngx in one call.

    Request body:
    {
        "file_path": "/path/to/document.pdf",
        "text": "OCR text of document (optional, will extract if not provided)",
        "subject": "Email subject",
        "from": "sender@email.cz",
        "paperless_url": "http://192.168.10.35:8000",
        "paperless_token": "your-api-token",
        "user_tag": "Martin"  # Required
    }
    """
    if not PAPERLESS_AVAILABLE or not LLM_AVAILABLE:
        return jsonify({
            "error": "Required features not available",
            "paperless": PAPERLESS_AVAILABLE,
            "llm": LLM_AVAILABLE
        }), 503

    data = request.json or {}

    # Required fields
    file_path = data.get("file_path")
    paperless_url = data.get("paperless_url")
    paperless_token = data.get("paperless_token")
    user_tag = data.get("user_tag")

    if not all([file_path, paperless_url, paperless_token, user_tag]):
        return jsonify({
            "error": "Missing required fields",
            "required": ["file_path", "paperless_url", "paperless_token", "user_tag"]
        }), 400

    text = data.get("text", "")
    subject = data.get("subject", "")
    from_addr = data.get("from", "")

    # If no text provided, try OCR
    if not text and OCR_AVAILABLE:
        try:
            processor = DocumentProcessor()
            ocr_result = processor.process_file(file_path)
            text = ocr_result.get("text", "")
        except:
            pass

    if not text and not subject:
        return jsonify({"error": "No text content available for classification"}), 400

    # Step 1: Classify
    if is_system_notification and is_system_notification({"from": from_addr, "subject": subject}):
        doc_type = "system_notification"
        classification = {
            "doc_typ": "system_notification",
            "protistrana_nazev": from_addr.split("<")[0].strip() if from_addr else "",
            "ai_summary": f"Systémová notifikace: {subject}"
        }
    else:
        prompt = CLASSIFY_PROMPT.format(
            from_addr=from_addr,
            to_addr=data.get("to", ""),
            subject=subject,
            date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
            body=text[:3000]
        )
        classification = call_ollama_32b(prompt)

        if not classification:
            return jsonify({"error": "Classification failed"}), 500

        doc_type = classification.get("doc_typ", "other")

        if doc_type == "other" and force_classify_other:
            doc_type = force_classify_other(classification, {"from": from_addr, "subject": subject})
            classification["doc_typ"] = doc_type

    # Map doc_type to Czech
    doc_type_map = {
        "invoice": "Faktura",
        "order": "Objednávka",
        "contract": "Smlouva",
        "marketing": "Marketing",
        "correspondence": "Korespondence",
        "receipt": "Účtenka",
        "bank_statement": "Bankovní výpis",
        "tax_document": "Daňový doklad",
        "system_notification": "Systémová notifikace",
        "it_notes": "IT poznámky",
        "project_notes": "Projektové poznámky"
    }

    # Step 2: Upload to Paperless
    config = {
        "paperless": {
            "url": paperless_url,
            "api_token": paperless_token,
            "auto_create_tags": True,
            "auto_create_correspondents": True,
            "auto_create_document_types": True,
            "check_duplicates": True
        }
    }

    try:
        api = PaperlessAPI(config)

        # Prepare tags
        tags = [f"User:{user_tag}"]
        tags.append(doc_type_map.get(doc_type, "Ostatní"))

        # Add keywords as tags if available
        keywords = classification.get("ai_keywords", "")
        if keywords:
            for kw in keywords.split(",")[:3]:
                kw = kw.strip()
                if kw and len(kw) > 2:
                    tags.append(kw)

        # Generate title
        title = classification.get("ai_summary", subject or Path(file_path).stem)[:100]

        # Upload
        result = api.upload_document(
            file_path=file_path,
            title=title,
            document_type=doc_type_map.get(doc_type, "Ostatní"),
            correspondent=classification.get("protistrana_nazev"),
            tags=tags
        )

        return jsonify({
            "success": result.get("success", False),
            "classification": {
                "doc_type": doc_type,
                "extracted_fields": classification
            },
            "paperless": {
                "id": result.get("paperless_id"),
                "duplicate": result.get("duplicate", False),
                "url": f"{paperless_url}/documents/{result.get('paperless_id')}" if result.get("paperless_id") else None
            },
            "user_tag": f"User:{user_tag}"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "classification": {"doc_type": doc_type, "extracted_fields": classification},
            "error": str(e)
        }), 500


# Document type mapping
DOC_TYPE_MAP = {
    "invoice": "Faktura",
    "order": "Objednávka",
    "contract": "Smlouva",
    "marketing": "Marketing",
    "correspondence": "Korespondence",
    "receipt": "Účtenka",
    "bank_statement": "Bankovní výpis",
    "tax_document": "Daňový doklad",
    "system_notification": "Systémová notifikace",
    "it_notes": "IT poznámky",
    "project_notes": "Projektové poznámky",
    "other": "Ostatní"
}


@app.route('/api/workflow', methods=['POST'])
def workflow():
    """
    Kompletní workflow pro zpracování dokumentu.

    Kroky:
    1. Validace vstupu
    2. OCR extrakce (pokud není text)
    3. LLM klasifikace typu dokumentu
    4. LLM extrakce strukturovaných dat
    5. Upload do Paperless-ngx s user tagem
    6. Vrácení kompletního výsledku
    """
    import time
    start_time = time.time()

    data = request.json or {}
    steps_completed = []
    result = {
        "success": False,
        "workflow": {"steps_completed": [], "duration_ms": 0},
        "document": {},
        "ocr": {"performed": False},
        "classification": {},
        "extraction": {},
        "paperless": {"uploaded": False}
    }

    # =========================================================================
    # STEP 1: Validate input
    # =========================================================================
    file_path = data.get("file_path")
    if not file_path:
        return jsonify({"error": "Missing 'file_path'", "step": "validate"}), 400

    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        return jsonify({"error": f"File not found: {file_path}", "step": "validate"}), 404

    result["document"] = {
        "file_path": str(file_path_obj),
        "file_name": file_path_obj.name,
        "file_size": file_path_obj.stat().st_size,
        "file_type": file_path_obj.suffix.lower()
    }
    steps_completed.append("validate")

    # Check Paperless requirements (unless skipping)
    skip_paperless = data.get("skip_paperless", False)
    dry_run = data.get("dry_run", False)

    if not skip_paperless and not dry_run:
        if not data.get("paperless_url"):
            return jsonify({"error": "Missing 'paperless_url'", "step": "validate"}), 400
        if not data.get("paperless_token"):
            return jsonify({"error": "Missing 'paperless_token'", "step": "validate"}), 400
        if not data.get("user_tag"):
            return jsonify({"error": "Missing 'user_tag' - required for access control", "step": "validate"}), 400

    # =========================================================================
    # STEP 2: OCR extraction (if no text provided)
    # =========================================================================
    text = data.get("text", "")
    subject = data.get("subject", "")
    from_addr = data.get("from", "")

    if not text:
        if OCR_AVAILABLE:
            try:
                processor = DocumentProcessor()
                ocr_result = processor.process_file(str(file_path_obj))
                text = ocr_result.get("text", "")
                result["ocr"] = {
                    "performed": True,
                    "text_length": len(text),
                    "text_preview": text[:200] + "..." if len(text) > 200 else text
                }
                steps_completed.append("ocr")
            except Exception as e:
                result["ocr"] = {"performed": False, "error": str(e)}
        else:
            result["ocr"] = {"performed": False, "reason": "OCR not available"}
    else:
        result["ocr"] = {
            "performed": False,
            "reason": "Text provided in request",
            "text_length": len(text),
            "text_preview": text[:200] + "..." if len(text) > 200 else text
        }

    if not text and not subject:
        return jsonify({
            "error": "No text content available for processing",
            "step": "ocr",
            "hint": "Provide 'text' or 'subject' in request, or ensure OCR is available"
        }), 400

    # =========================================================================
    # STEP 3: Classification
    # =========================================================================
    if not LLM_AVAILABLE:
        return jsonify({"error": "LLM not available for classification", "step": "classify"}), 503

    classification = {}
    doc_type = "other"

    # Pre-classify system notifications (fast path)
    if is_system_notification and is_system_notification({"from": from_addr, "subject": subject}):
        doc_type = "system_notification"
        classification = {
            "doc_typ": "system_notification",
            "protistrana_nazev": from_addr.split("<")[0].strip() if from_addr else "",
            "ai_summary": f"Systémová notifikace: {subject}",
            "ai_keywords": "system, notification, automated"
        }
        result["classification"] = {
            "doc_type": doc_type,
            "doc_type_cs": "Systémová notifikace",
            "confidence": 0.99,
            "model": "pattern_match",
            "fast_path": True
        }
    else:
        # Full LLM classification
        prompt = CLASSIFY_PROMPT.format(
            from_addr=from_addr,
            to_addr=data.get("to", ""),
            subject=subject,
            date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
            body=text[:3000]
        )

        classification = call_ollama_32b(prompt) or {}

        if not classification:
            return jsonify({"error": "Classification failed", "step": "classify"}), 500

        doc_type = classification.get("doc_typ", "other")

        # Force classify "other"
        if doc_type == "other" and force_classify_other:
            doc_type = force_classify_other(classification, {"from": from_addr, "subject": subject})
            classification["doc_typ"] = doc_type
            classification["force_classified"] = True

        result["classification"] = {
            "doc_type": doc_type,
            "doc_type_cs": DOC_TYPE_MAP.get(doc_type, "Ostatní"),
            "confidence": 0.85,
            "model": "qwen2.5:32b",
            "fast_path": False
        }

    steps_completed.append("classify")

    # =========================================================================
    # STEP 4: Data extraction
    # =========================================================================
    skip_extraction = data.get("skip_extraction", False)

    if not skip_extraction:
        extraction = {
            "protistrana_nazev": classification.get("protistrana_nazev", ""),
            "protistrana_ico": classification.get("protistrana_ico", ""),
            "protistrana_dic": classification.get("protistrana_dic", ""),
            "castka_celkem": classification.get("castka_celkem"),
            "castka_zaklad": classification.get("castka_zaklad"),
            "castka_dph": classification.get("castka_dph"),
            "datum_dokumentu": classification.get("datum_dokumentu", ""),
            "datum_splatnosti": classification.get("datum_splatnosti", ""),
            "cislo_dokumentu": classification.get("cislo_dokumentu", ""),
            "mena": classification.get("mena", "CZK"),
            "vs": classification.get("vs", ""),
            "cislo_uctu": classification.get("cislo_uctu", ""),
            "ai_summary": classification.get("ai_summary", ""),
            "ai_keywords": classification.get("ai_keywords", ""),
            "kategorie": classification.get("kategorie", ""),
            "email_from": from_addr,
            "email_subject": subject
        }

        # Clean None/empty values
        extraction = {k: v for k, v in extraction.items() if v is not None and v != ""}

        result["extraction"] = extraction
        steps_completed.append("extract")
    else:
        result["extraction"] = {"skipped": True}

    # =========================================================================
    # STEP 5: Upload to Paperless-ngx
    # =========================================================================
    if not skip_paperless and not dry_run:
        if not PAPERLESS_AVAILABLE:
            result["paperless"] = {"uploaded": False, "error": "Paperless integration not available"}
        else:
            try:
                paperless_url = data.get("paperless_url")
                paperless_token = data.get("paperless_token")
                user_tag = data.get("user_tag")

                config = {
                    "paperless": {
                        "url": paperless_url,
                        "api_token": paperless_token,
                        "auto_create_tags": True,
                        "auto_create_correspondents": True,
                        "auto_create_document_types": True,
                        "check_duplicates": True
                    }
                }

                api = PaperlessAPI(config)

                # Test connection
                if not api.test_connection():
                    result["paperless"] = {"uploaded": False, "error": "Cannot connect to Paperless-ngx"}
                else:
                    # Prepare tags
                    tags = [f"User:{user_tag}"]
                    doc_type_cs = DOC_TYPE_MAP.get(doc_type, "Ostatní")
                    tags.append(doc_type_cs)

                    # Add keywords as tags
                    keywords = classification.get("ai_keywords", "")
                    if keywords:
                        for kw in keywords.split(",")[:3]:
                            kw = kw.strip()
                            if kw and len(kw) > 2 and len(kw) < 30:
                                tags.append(kw)

                    # Generate title
                    title = classification.get("ai_summary", "")
                    if not title:
                        title = subject or file_path_obj.stem
                    title = title[:100]

                    # Correspondent
                    correspondent = classification.get("protistrana_nazev", "")

                    # Upload
                    upload_result = api.upload_document(
                        file_path=str(file_path_obj),
                        title=title,
                        document_type=doc_type_cs,
                        correspondent=correspondent if correspondent else None,
                        tags=tags
                    )

                    if upload_result.get("success"):
                        result["paperless"] = {
                            "uploaded": True,
                            "id": upload_result.get("paperless_id"),
                            "duplicate": upload_result.get("duplicate", False),
                            "url": f"{paperless_url}/documents/{upload_result.get('paperless_id')}",
                            "tags": tags,
                            "correspondent": correspondent,
                            "document_type": doc_type_cs,
                            "title": title
                        }
                        steps_completed.append("upload")
                    else:
                        result["paperless"] = {
                            "uploaded": False,
                            "error": upload_result.get("error", "Upload failed")
                        }

            except Exception as e:
                result["paperless"] = {"uploaded": False, "error": str(e)}

    elif dry_run:
        # Dry run - show what would be uploaded
        user_tag = data.get("user_tag", "unknown")
        tags = [f"User:{user_tag}"]
        doc_type_cs = DOC_TYPE_MAP.get(doc_type, "Ostatní")
        tags.append(doc_type_cs)

        keywords = classification.get("ai_keywords", "")
        if keywords:
            for kw in keywords.split(",")[:3]:
                kw = kw.strip()
                if kw and len(kw) > 2:
                    tags.append(kw)

        result["paperless"] = {
            "uploaded": False,
            "dry_run": True,
            "would_upload": {
                "title": classification.get("ai_summary", subject or file_path_obj.stem)[:100],
                "document_type": doc_type_cs,
                "correspondent": classification.get("protistrana_nazev", ""),
                "tags": tags
            }
        }
        steps_completed.append("dry_run")
    else:
        result["paperless"] = {"uploaded": False, "skipped": True}

    # =========================================================================
    # Finalize
    # =========================================================================
    duration_ms = int((time.time() - start_time) * 1000)

    result["success"] = True
    result["workflow"] = {
        "steps_completed": steps_completed,
        "duration_ms": duration_ms
    }

    return jsonify(result)


@app.route('/api/scan', methods=['POST'])
def scan_mailbox():
    """
    Scan Thunderbird/IMAP mailbox and extract attachments.

    Request:
    {
        "mailbox_path": "/path/to/INBOX",  # Direct path to mbox file
        "max_emails": 999999,               # Optional limit
        "extract_to": "/tmp/attachments"    # Optional output dir
    }

    Response:
    {
        "success": true,
        "total_emails": 2797,
        "emails_with_attachments": 164,
        "attachments": [
            {
                "file_path": "/tmp/attachments/email_123_invoice.pdf",
                "from": "sender@email.cz",
                "to": "puzik@softel.cz",
                "subject": "Faktura 2025001",
                "date": "2025-01-15"
            }
        ]
    }
    """
    import mailbox as mbox_module
    import email.utils
    from email.header import decode_header
    import tempfile

    data = request.json or {}
    mailbox_path = data.get("mailbox_path")

    if not mailbox_path:
        return jsonify({"error": "Missing 'mailbox_path'"}), 400

    mailbox_file = Path(mailbox_path)
    if not mailbox_file.exists():
        return jsonify({"error": f"Mailbox not found: {mailbox_path}"}), 404

    max_emails = data.get("max_emails", 999999)
    extract_to = Path(data.get("extract_to", tempfile.mkdtemp(prefix="maj_scan_")))
    extract_to.mkdir(parents=True, exist_ok=True)

    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.docx', '.doc', '.xlsx', '.xls'}

    def decode_hdr(header):
        if not header:
            return ""
        try:
            decoded_parts = decode_header(header)
            result = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    try:
                        if encoding and encoding.lower() in ('unknown-8bit', 'unknown'):
                            encoding = 'utf-8'
                        result += part.decode(encoding or 'utf-8', errors='ignore')
                    except:
                        result += part.decode('utf-8', errors='ignore')
                else:
                    result += str(part)
            return result
        except:
            return str(header)

    results = []
    total_emails = 0
    emails_with_attachments = 0

    try:
        mbox = mbox_module.mbox(str(mailbox_file))

        for idx, msg in enumerate(mbox):
            if idx >= max_emails:
                break

            total_emails += 1

            # Extract metadata
            from_addr = decode_hdr(msg.get("From", ""))
            to_addr = decode_hdr(msg.get("To", ""))
            subject = decode_hdr(msg.get("Subject", ""))
            date_str = msg.get("Date", "")

            # Parse date
            try:
                parsed_date = email.utils.parsedate_to_datetime(date_str)
                date_formatted = parsed_date.strftime("%Y-%m-%d")
            except:
                date_formatted = ""

            # Extract attachments
            has_attachment = False
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue

                filename = part.get_filename()
                if not filename:
                    continue

                filename = decode_hdr(filename)
                ext = Path(filename).suffix.lower()

                if ext not in allowed_extensions:
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue

                    # Save attachment
                    safe_filename = f"email_{idx}_{filename}"
                    attachment_path = extract_to / safe_filename

                    with open(attachment_path, "wb") as f:
                        f.write(payload)

                    results.append({
                        "file_path": str(attachment_path),
                        "original_filename": filename,
                        "from": from_addr,
                        "to": to_addr,
                        "subject": subject,
                        "date": date_formatted,
                        "email_index": idx
                    })

                    has_attachment = True

                except Exception as e:
                    pass  # Skip failed attachments

            if has_attachment:
                emails_with_attachments += 1

            # Progress log
            if (idx + 1) % 500 == 0:
                print(f"Scanned {idx + 1} emails, found {len(results)} attachments...")

        return jsonify({
            "success": True,
            "total_emails": total_emails,
            "emails_with_attachments": emails_with_attachments,
            "attachments_count": len(results),
            "extract_dir": str(extract_to),
            "attachments": results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/classify_file', methods=['POST'])
def classify_file():
    """
    Classify uploaded file - for Paperless pre-consume script.

    Request: multipart/form-data with 'file' field

    Response:
    {
        "success": true,
        "doc_type": "invoice",
        "tags": ["Faktura", "finance"],
        "correspondent": "Vodafone",
        "title": "Faktura 2025001",
        "custom_fields": {...}
    }
    """
    import tempfile

    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded", "field": "file"}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Save to temp file
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        # OCR extraction
        text = ""
        if OCR_AVAILABLE:
            try:
                processor = DocumentProcessor()
                ocr_result = processor.process_file(str(tmp_path))
                text = ocr_result.get("text", "")
            except Exception as e:
                pass

        if not text:
            # Try to read as text
            try:
                with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read(5000)
            except:
                pass

        if not text:
            return jsonify({
                "success": False,
                "error": "Could not extract text from file",
                "doc_type": "other",
                "tags": ["Nezpracováno"],
                "title": file.filename
            })

        # Classify
        if not LLM_AVAILABLE:
            return jsonify({"error": "LLM not available"}), 503

        prompt = CLASSIFY_PROMPT.format(
            from_addr="",
            to_addr="",
            subject=file.filename,
            date=datetime.now().strftime("%Y-%m-%d"),
            body=text[:3000]
        )

        classification = call_ollama_32b(prompt) or {}
        doc_type = classification.get("doc_typ", "other")

        # Force classify
        if doc_type == "other" and force_classify_other:
            doc_type = force_classify_other(classification, {"subject": file.filename})
            classification["doc_typ"] = doc_type

        # Build response for pre-consume
        doc_type_cs = DOC_TYPE_MAP.get(doc_type, "Ostatní")

        tags = [doc_type_cs]
        keywords = classification.get("ai_keywords", "")
        if keywords:
            for kw in keywords.split(",")[:3]:
                kw = kw.strip()
                if kw and 2 < len(kw) < 30:
                    tags.append(kw)

        title = classification.get("ai_summary", "")
        if not title:
            title = file.filename
        title = title[:100]

        correspondent = classification.get("protistrana_nazev", "")

        return jsonify({
            "success": True,
            "doc_type": doc_type,
            "doc_type_cs": doc_type_cs,
            "tags": tags,
            "correspondent": correspondent if correspondent else None,
            "title": title,
            "custom_fields": {
                "castka_celkem": classification.get("castka_celkem"),
                "datum_dokumentu": classification.get("datum_dokumentu"),
                "cislo_dokumentu": classification.get("cislo_dokumentu"),
                "protistrana_ico": classification.get("protistrana_ico"),
                "ai_summary": classification.get("ai_summary"),
                "ai_keywords": classification.get("ai_keywords")
            }
        })

    finally:
        # Cleanup temp file
        try:
            tmp_path.unlink()
        except:
            pass


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API info"""
    return jsonify({
        "api": API_NAME,
        "version": API_VERSION,
        "docs": "/api/docs",
        "health": "/api/health",
        "stats": "/api/stats",
        "workflow": "/api/workflow",
        "scan": "/api/scan",
        "paperless_available": PAPERLESS_AVAILABLE
    })


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=API_NAME)
    parser.add_argument('--host', default='0.0.0.0', help='Host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8765, help='Port (default: 8765)')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()

    # Port Authority integration
    sys.path.insert(0, "/Volumes/ACASIS/apps/lib")
    try:
        import portauth
        port = portauth.allocate("doc-recognition-api", ttl_seconds=86400)
        print(f"Port Authority: allocated port {port}")
    except Exception as e:
        print(f"Port Authority unavailable ({e}), using default port {args.port}")
        port = args.port

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  {API_NAME} v{API_VERSION}
╠══════════════════════════════════════════════════════════════╣
║  Endpoints:
║    GET  /api/docs      - API dokumentace
║    GET  /api/health    - Health check
║    GET  /api/stats     - Statistiky zpracování
║    GET  /api/status    - Stav Phase 2
║    POST /api/classify  - Klasifikace dokumentu
║    POST /api/extract   - Extrakce dat
║    GET  /api/results   - Seznam výsledků
╠══════════════════════════════════════════════════════════════╣
║  Features: LLM={LLM_AVAILABLE} OCR={OCR_AVAILABLE}
╚══════════════════════════════════════════════════════════════╝
    """)

    app.run(host=args.host, port=port, debug=args.debug)
