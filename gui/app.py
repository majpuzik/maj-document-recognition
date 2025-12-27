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
MAJ Document Recognition - Configuration GUI
=============================================
Webové rozhraní pro konfiguraci a spuštění zpracování dokumentů.

Spuštění: python gui/app.py
URL: http://localhost:8080

Version: 1.2.0
Changelog:
  - 1.2.0 (2025-12-24): Added Paperless document management endpoints
    - /api/paperless/documents_without_tags - list unclassified documents
    - /api/paperless/delete_documents - soft delete documents (to trash)
    - /api/paperless/trash - check trash count
    - /api/paperless/empty_trash - permanently delete trashed documents
  - 1.1.0: Added Port Authority integration
  - 1.0.0: Initial version
"""

__version__ = "1.2.0"

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import subprocess
import threading
import socket
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# Known Paperless instances with tokens (can be extended)
KNOWN_PAPERLESS_INSTANCES = [
    {"name": "DGX - Almquist Paperless", "url": "http://192.168.10.200:8010", "token": "031648a715841d24ad2043d25adbbee8b667c59f"},
    {"name": "DGX - Paperless NGX", "url": "http://192.168.10.200:8020", "token": "155c91425631202132bb769241ad7d3196428df0"},
    {"name": "DGX - Paperless RAG", "url": "http://192.168.10.200:8030", "token": ""},
    {"name": "NAS5 - Paperless", "url": "http://192.168.10.85:8777", "token": "155c91425631202132bb769241ad7d3196428df0"},
]

def check_paperless_instance(url, timeout=2, token=None):
    """Check if URL is a valid Paperless instance and get document count"""
    try:
        r = requests.get(f"{url}/api/", timeout=timeout)
        if r.status_code in (200, 401, 403):
            result = {
                "url": url,
                "status": "online",
                "version": "Paperless-NGX",
                "doc_count": 0,
                "token": token or ""
            }
            headers = {"Authorization": f"Token {token}"} if token else {}

            # Try to get version/info
            try:
                info = requests.get(f"{url}/api/ui_settings/", timeout=timeout, headers=headers)
                if info.status_code == 200:
                    data = info.json()
                    result["version"] = data.get("settings", {}).get("app_title", "Paperless-NGX")
            except:
                pass
            # Try to get document count (with auth if token provided)
            try:
                docs = requests.get(f"{url}/api/documents/?page_size=1", timeout=timeout, headers=headers)
                if docs.status_code == 200:
                    result["doc_count"] = docs.json().get("count", 0)
            except:
                pass
            return result
    except:
        pass
    return None

def scan_network_for_paperless(ports=[8000, 8777, 8080], timeout=1):
    """Scan local network for Paperless instances"""
    instances = []

    # Get local IP range
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        base_ip = ".".join(local_ip.split(".")[:-1])
    except:
        base_ip = "192.168.10"

    # Check known instances first (with tokens)
    for inst in KNOWN_PAPERLESS_INSTANCES:
        result = check_paperless_instance(inst["url"], timeout, token=inst.get("token"))
        if result:
            result["name"] = inst["name"]
            if not result.get("token") and inst.get("token"):
                result["token"] = inst["token"]
            instances.append(result)

    # Quick scan common IPs
    common_ips = [35, 85, 200, 100, 1, 10, 20, 30, 40, 50]

    def check_ip_port(ip, port):
        url = f"http://{base_ip}.{ip}:{port}"
        return check_paperless_instance(url, timeout)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for ip in common_ips:
            for port in ports:
                futures.append(executor.submit(check_ip_port, ip, port))

        for future in as_completed(futures, timeout=10):
            try:
                result = future.result()
                if result and not any(i["url"] == result["url"] for i in instances):
                    result["name"] = f"Paperless @ {result['url'].split('//')[1]}"
                    instances.append(result)
            except:
                pass

    return instances

# Config file path
CONFIG_FILE = Path(__file__).parent / "config.json"

# Default config
DEFAULT_CONFIG = {
    "imap": {
        "host": "",
        "port": 993,
        "user": "",
        "password": "",
        "mailbox": "INBOX",
        "ssl": True
    },
    "paperless": {
        "url": "http://192.168.10.200:8020",
        "token": ""
    },
    "processing": {
        "parallel_processes": 10,
        "ollama_model": "qwen2.5:32b",
        "ollama_url": "http://192.168.10.35:11434"
    },
    "job": {
        "name": "",
        "id": "",
        "datetime": ""
    }
}

def load_config():
    """Load config from file or return defaults"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save config to file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# Processing status
processing_status = {
    "running": False,
    "phase": None,
    "progress": 0,
    "total": 0,
    "processed": 0,
    "success": 0,
    "failed": 0,
    "message": "",
    "start_time": None,
    "current_file": "",
    "log": [],
    # Document types breakdown
    "doc_types": {
        "faktura": 0,
        "smlouva": 0,
        "objednavka": 0,
        "uctenka": 0,
        "vypis": 0,
        "korespondence": 0,
        "marketing": 0,
        "other": 0
    },
    # Import to Paperless status
    "import": {
        "total": 0,
        "success": 0,
        "failed": 0,
        "errors": []  # List of {"file": ..., "error": ...}
    }
}

@app.route("/")
def index():
    """Main configuration page"""
    config = load_config()
    # Get cached or scan for Paperless instances
    instances = scan_network_for_paperless()
    return render_template("index.html", config=config, status=processing_status, paperless_instances=instances)

@app.route("/scan_paperless")
def scan_paperless():
    """Scan network for Paperless instances"""
    instances = scan_network_for_paperless()
    return jsonify({"instances": instances})

@app.route("/save", methods=["POST"])
def save():
    """Save configuration"""
    config = load_config()

    # IMAP
    config["imap"]["host"] = request.form.get("imap_host", "")
    config["imap"]["port"] = int(request.form.get("imap_port", 993))
    config["imap"]["user"] = request.form.get("imap_user", "")
    config["imap"]["password"] = request.form.get("imap_password", "")
    config["imap"]["mailbox"] = request.form.get("imap_mailbox", "INBOX")

    # Paperless
    config["paperless"]["url"] = request.form.get("paperless_url", "")
    config["paperless"]["token"] = request.form.get("paperless_token", "")

    # Processing
    config["processing"]["parallel_processes"] = int(request.form.get("parallel_processes", 10))
    config["processing"]["ollama_model"] = request.form.get("ollama_model", "qwen2.5:32b")

    # Job info
    if "job" not in config:
        config["job"] = {}
    config["job"]["name"] = request.form.get("job_name", "")
    config["job"]["id"] = request.form.get("job_id", "")
    config["job"]["datetime"] = request.form.get("job_datetime", "")

    save_config(config)
    return redirect(url_for("index"))

@app.route("/test_imap", methods=["POST"])
def test_imap():
    """Test IMAP connection"""
    import imaplib

    data = request.json
    try:
        if data.get("ssl", True):
            mail = imaplib.IMAP4_SSL(data["host"], int(data.get("port", 993)))
        else:
            mail = imaplib.IMAP4(data["host"], int(data.get("port", 143)))

        mail.login(data["user"], data["password"])
        status, messages = mail.select(data.get("mailbox", "INBOX"))
        count = int(messages[0])
        mail.logout()

        return jsonify({"success": True, "message": f"Připojeno! {count} emailů v {data.get('mailbox', 'INBOX')}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/test_paperless", methods=["POST"])
def test_paperless():
    """Test Paperless connection"""
    import requests

    data = request.json
    try:
        url = data["url"].rstrip("/")
        headers = {"Authorization": f"Token {data['token']}"}

        r = requests.get(f"{url}/api/documents/?page_size=1", headers=headers, timeout=10)
        if r.status_code == 200:
            total = r.json().get("count", 0)
            return jsonify({"success": True, "message": f"Připojeno! {total} dokumentů v Paperless"})
        else:
            return jsonify({"success": False, "message": f"HTTP {r.status_code}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/get_paperless_token", methods=["POST"])
def get_paperless_token():
    """Get Paperless token using username/password"""
    import requests

    data = request.json
    try:
        url = data["url"].rstrip("/")
        r = requests.post(
            f"{url}/api/token/",
            json={"username": data["username"], "password": data["password"]},
            timeout=10
        )
        if r.status_code == 200:
            token = r.json().get("token")
            return jsonify({"success": True, "token": token})
        else:
            return jsonify({"success": False, "message": f"HTTP {r.status_code}: {r.text}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/start", methods=["POST"])
def start_processing():
    """Start document processing"""
    global processing_status
    from datetime import datetime

    if processing_status["running"]:
        return jsonify({"success": False, "message": "Zpracování již běží"})

    config = load_config()

    # Validate config
    if not config["imap"]["host"] or not config["imap"]["user"]:
        return jsonify({"success": False, "message": "IMAP není nakonfigurován"})

    if not config["paperless"]["url"] or not config["paperless"]["token"]:
        return jsonify({"success": False, "message": "Paperless není nakonfigurován"})

    # Reset and start processing in background
    processing_status["running"] = True
    processing_status["phase"] = "Starting"
    processing_status["progress"] = 0
    processing_status["total"] = 0
    processing_status["processed"] = 0
    processing_status["success"] = 0
    processing_status["failed"] = 0
    processing_status["message"] = "Spouštím zpracování..."
    processing_status["start_time"] = datetime.now().isoformat()
    processing_status["current_file"] = ""
    processing_status["log"] = []
    # Reset document types
    processing_status["doc_types"] = {
        "faktura": 0, "smlouva": 0, "objednavka": 0, "uctenka": 0,
        "vypis": 0, "korespondence": 0, "marketing": 0, "other": 0
    }
    # Reset import status
    processing_status["import"] = {"total": 0, "success": 0, "failed": 0, "errors": []}

    thread = threading.Thread(target=run_processing, args=(config,))
    thread.daemon = True
    thread.start()

    return jsonify({"success": True, "message": "Zpracování spuštěno"})

def run_processing(config):
    """Run the full processing pipeline"""
    global processing_status

    try:
        base_dir = Path(__file__).parent.parent

        # Phase 1: Fetch emails
        processing_status["phase"] = "Phase 1: IMAP Fetch"
        processing_status["message"] = "Stahuji emaily..."

        # Save config for scripts
        env_file = base_dir / ".env"
        with open(env_file, "w") as f:
            f.write(f"IMAP_HOST={config['imap']['host']}\n")
            f.write(f"IMAP_PORT={config['imap']['port']}\n")
            f.write(f"IMAP_USER={config['imap']['user']}\n")
            f.write(f"IMAP_PASSWORD={config['imap']['password']}\n")
            f.write(f"IMAP_MAILBOX={config['imap']['mailbox']}\n")
            f.write(f"PAPERLESS_URL={config['paperless']['url']}\n")
            f.write(f"PAPERLESS_TOKEN={config['paperless']['token']}\n")
            f.write(f"OLLAMA_MODEL={config['processing']['ollama_model']}\n")

        # Run Phase 1
        phase1_script = base_dir / "email_extractor" / "phase1_docling.py"
        if phase1_script.exists():
            subprocess.run(["python3", str(phase1_script)], cwd=str(base_dir))

        # Phase 2: LLM Classification
        processing_status["phase"] = "Phase 2: LLM Classification"
        processing_status["message"] = "Klasifikuji dokumenty..."

        phase2_script = base_dir / "email_extractor" / "phase2_llm.py"
        if phase2_script.exists():
            subprocess.run(["python3", str(phase2_script)], cwd=str(base_dir))

        # Phase 5: Import to Paperless
        processing_status["phase"] = "Phase 5: Paperless Import"
        processing_status["message"] = "Importuji do Paperless..."

        phase5_script = base_dir / "email_extractor" / "phase5_import.py"
        if phase5_script.exists():
            subprocess.run(["python3", str(phase5_script)], cwd=str(base_dir))

        processing_status["phase"] = "Complete"
        processing_status["message"] = "Zpracování dokončeno!"
        processing_status["progress"] = 100

    except Exception as e:
        processing_status["message"] = f"Chyba: {str(e)}"
    finally:
        processing_status["running"] = False

def get_file_based_progress():
    """Get progress by counting actual result files"""
    base_dir = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output")

    # Count Phase 1 results
    phase1_results = base_dir / "phase1_results"
    phase1_count = len(list(phase1_results.glob("*.json"))) if phase1_results.exists() else 0

    # Count Phase 2 to process
    phase2_input = base_dir / "phase2_to_process.jsonl"
    phase2_total = 0
    if phase2_input.exists():
        with open(phase2_input) as f:
            phase2_total = sum(1 for _ in f)

    # Count Phase 2 results (which go to phase1_results with source=phase2_llm)
    phase2_results = base_dir / "phase2_results"
    phase2_count = len(list(phase2_results.glob("*.json"))) if phase2_results.exists() else 0

    # Count doc types from result files
    doc_types = {
        "faktura": 0, "smlouva": 0, "objednavka": 0, "uctenka": 0,
        "vypis": 0, "korespondence": 0, "marketing": 0, "other": 0
    }
    type_map = {
        "invoice": "faktura", "faktura": "faktura",
        "contract": "smlouva", "smlouva": "smlouva",
        "order": "objednavka", "objednavka": "objednavka",
        "receipt": "uctenka", "uctenka": "uctenka",
        "bank_statement": "vypis", "vypis": "vypis",
        "correspondence": "korespondence", "korespondence": "korespondence",
        "marketing": "marketing", "newsletter": "marketing",
    }

    # Scan phase1_results for doc types
    if phase1_results.exists():
        import json as json_mod
        for f in list(phase1_results.glob("*.json"))[-500:]:  # Last 500 for speed
            try:
                with open(f) as fp:
                    data = json_mod.load(fp)
                    doc_type = data.get("doc_type", data.get("extracted_fields", {}).get("doc_typ", "other"))
                    mapped = type_map.get(doc_type.lower() if doc_type else "other", "other")
                    doc_types[mapped] += 1
            except:
                pass

    return {
        "phase1_count": phase1_count,
        "phase2_total": phase2_total,
        "phase2_count": phase2_count,
        "doc_types": doc_types
    }

@app.route("/status")
def get_status():
    """Get processing status - full API with file-based progress"""
    import subprocess
    status = processing_status.copy()

    # Always get file-based progress
    file_progress = get_file_based_progress()

    # Check if phase2_llm.py is actually running
    try:
        result = subprocess.run(["pgrep", "-f", "phase2_llm.py"], capture_output=True, timeout=2)
        phase2_running = result.returncode == 0
    except:
        phase2_running = False

    # Auto-detect phase from running processes
    if phase2_running and not status.get("phase"):
        status["phase"] = "Phase 2: LLM Classification"
        status["running"] = True
        status["message"] = f"Zpracovávám {file_progress['phase2_count']}/{file_progress['phase2_total']} emailů..."

    # Always show actual file counts if available
    if file_progress["phase2_total"] > 0:
        status["total"] = file_progress["phase2_total"]
        status["processed"] = file_progress["phase2_count"]
        status["progress"] = int(100 * file_progress["phase2_count"] / max(1, file_progress["phase2_total"]))

    # Always update doc_types from files
    if sum(file_progress["doc_types"].values()) > 0:
        status["doc_types"] = file_progress["doc_types"]

    # Add file counts
    status["file_counts"] = {
        "phase1_results": file_progress["phase1_count"],
        "phase2_total": file_progress["phase2_total"],
        "phase2_results": file_progress["phase2_count"]
    }

    return jsonify(status)

@app.route("/api/status")
def api_status():
    """Full API status with all details and file-based progress"""
    status = processing_status.copy()

    # Supplement with file-based progress
    file_progress = get_file_based_progress()

    # Override with actual file counts
    if "Phase 2" in str(status.get("phase", "")):
        status["total"] = file_progress["phase2_total"]
        status["processed"] = file_progress["phase2_count"]
        status["progress"] = int(100 * file_progress["phase2_count"] / max(1, file_progress["phase2_total"]))
    elif "Phase 1" in str(status.get("phase", "")):
        status["processed"] = file_progress["phase1_count"]

    # Update doc_types from files
    if sum(file_progress["doc_types"].values()) > sum(status.get("doc_types", {}).values()):
        status["doc_types"] = file_progress["doc_types"]

    # Add file counts for debugging
    status["file_counts"] = {
        "phase1_results": file_progress["phase1_count"],
        "phase2_total": file_progress["phase2_total"],
        "phase2_results": file_progress["phase2_count"]
    }

    return jsonify({
        "status": "ok",
        "data": status
    })

@app.route("/api/doc_types")
def api_doc_types():
    """Get document types breakdown"""
    return jsonify({
        "status": "ok",
        "doc_types": processing_status.get("doc_types", {}),
        "total": sum(processing_status.get("doc_types", {}).values())
    })

@app.route("/api/import_status")
def api_import_status():
    """Get import to Paperless status"""
    return jsonify({
        "status": "ok",
        "import": processing_status.get("import", {}),
        "paperless_url": load_config().get("paperless", {}).get("url", "")
    })

@app.route("/api/errors")
def api_errors():
    """Get list of import errors"""
    return jsonify({
        "status": "ok",
        "errors": processing_status.get("import", {}).get("errors", []),
        "count": len(processing_status.get("import", {}).get("errors", []))
    })

@app.route("/api/update", methods=["POST"])
def api_update():
    """
    Update status from external scripts (phase1, phase2, phase5).
    POST JSON with fields to update:
    {
        "processed": 100,
        "success": 95,
        "failed": 5,
        "current_file": "email_123.eml",
        "message": "Processing...",
        "doc_type": "faktura",  # Increments counter
        "import_success": true/false,
        "import_error": {"file": "...", "error": "..."}
    }
    """
    global processing_status
    data = request.json or {}

    # Update basic counters
    for key in ["processed", "success", "failed", "total", "progress"]:
        if key in data:
            processing_status[key] = data[key]

    # Update strings
    for key in ["current_file", "message", "phase"]:
        if key in data:
            processing_status[key] = data[key]

    # Increment document type counter
    if "doc_type" in data:
        doc_type = data["doc_type"].lower()
        # Map to known types
        type_map = {
            "invoice": "faktura", "faktura": "faktura",
            "contract": "smlouva", "smlouva": "smlouva",
            "order": "objednavka", "objednavka": "objednavka",
            "receipt": "uctenka", "uctenka": "uctenka",
            "bank_statement": "vypis", "vypis": "vypis",
            "correspondence": "korespondence", "korespondence": "korespondence",
            "marketing": "marketing", "newsletter": "marketing",
        }
        mapped = type_map.get(doc_type, "other")
        processing_status["doc_types"][mapped] = processing_status["doc_types"].get(mapped, 0) + 1

    # Update import status
    if "import_success" in data:
        processing_status["import"]["total"] += 1
        if data["import_success"]:
            processing_status["import"]["success"] += 1
        else:
            processing_status["import"]["failed"] += 1

    # Add import error
    if "import_error" in data:
        err = data["import_error"]
        # Keep only last 100 errors
        if len(processing_status["import"]["errors"]) >= 100:
            processing_status["import"]["errors"] = processing_status["import"]["errors"][-99:]
        processing_status["import"]["errors"].append(err)

    # Add to log
    if "log" in data:
        if len(processing_status["log"]) >= 100:
            processing_status["log"] = processing_status["log"][-99:]
        processing_status["log"].append(data["log"])

    return jsonify({"status": "ok", "updated": list(data.keys())})

@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset all status counters"""
    global processing_status
    processing_status["processed"] = 0
    processing_status["success"] = 0
    processing_status["failed"] = 0
    processing_status["progress"] = 0
    processing_status["log"] = []
    processing_status["doc_types"] = {
        "faktura": 0, "smlouva": 0, "objednavka": 0, "uctenka": 0,
        "vypis": 0, "korespondence": 0, "marketing": 0, "other": 0
    }
    processing_status["import"] = {"total": 0, "success": 0, "failed": 0, "errors": []}
    return jsonify({"status": "ok", "message": "Status reset"})

@app.route("/stop", methods=["POST"])
def stop_processing():
    """Stop processing"""
    global processing_status
    processing_status["running"] = False
    processing_status["message"] = "Zastaveno uživatelem"
    return jsonify({"success": True})


# =============================================================================
# PAPERLESS DOCUMENT MANAGEMENT - Delete uploaded documents
# =============================================================================

@app.route("/api/paperless/documents_without_tags", methods=["GET"])
def get_documents_without_tags():
    """Get documents without tags (candidates for deletion)"""
    config = load_config()
    url = config.get("paperless", {}).get("url", "").rstrip("/")
    token = config.get("paperless", {}).get("token", "")

    if not url or not token:
        return jsonify({"success": False, "error": "Paperless not configured"})

    try:
        # Get recent documents and filter locally (API filtering unreliable)
        headers = {"Authorization": f"Token {token}"}
        page_size = request.args.get("page_size", 100, type=int)

        resp = requests.get(
            f"{url}/api/documents/",
            params={"ordering": "-id", "page_size": page_size, "fields": "id,title,tags,document_type,added"},
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        # Filter documents without tags
        no_tags = [
            {"id": d["id"], "title": d["title"][:80], "added": d["added"]}
            for d in data.get("results", [])
            if d.get("tags") == [] and d.get("document_type") is None
        ]

        return jsonify({
            "success": True,
            "count": len(no_tags),
            "total_scanned": len(data.get("results", [])),
            "documents": no_tags
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/paperless/delete_documents", methods=["POST"])
def delete_documents():
    """Soft delete documents by ID list (moves to trash)"""
    config = load_config()
    url = config.get("paperless", {}).get("url", "").rstrip("/")
    token = config.get("paperless", {}).get("token", "")

    if not url or not token:
        return jsonify({"success": False, "error": "Paperless not configured"})

    data = request.json or {}
    doc_ids = data.get("ids", [])

    if not doc_ids:
        return jsonify({"success": False, "error": "No document IDs provided"})

    headers = {"Authorization": f"Token {token}"}
    deleted = 0
    failed = 0
    errors = []

    for doc_id in doc_ids:
        try:
            resp = requests.delete(
                f"{url}/api/documents/{doc_id}/",
                headers=headers,
                timeout=10
            )
            if resp.status_code in (200, 204):
                deleted += 1
            else:
                failed += 1
                errors.append({"id": doc_id, "error": f"HTTP {resp.status_code}"})
        except Exception as e:
            failed += 1
            errors.append({"id": doc_id, "error": str(e)})

    return jsonify({
        "success": True,
        "deleted": deleted,
        "failed": failed,
        "errors": errors[:10]  # Limit errors returned
    })


@app.route("/api/paperless/trash", methods=["GET"])
def get_trash():
    """Get documents in trash"""
    config = load_config()
    url = config.get("paperless", {}).get("url", "").rstrip("/")
    token = config.get("paperless", {}).get("token", "")

    if not url or not token:
        return jsonify({"success": False, "error": "Paperless not configured"})

    try:
        headers = {"Authorization": f"Token {token}"}
        resp = requests.get(
            f"{url}/api/trash/",
            params={"page_size": 1},
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        return jsonify({
            "success": True,
            "count": data.get("count", 0)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/paperless/empty_trash", methods=["POST"])
def empty_trash():
    """Permanently delete all documents in trash"""
    config = load_config()
    url = config.get("paperless", {}).get("url", "").rstrip("/")
    token = config.get("paperless", {}).get("token", "")

    if not url or not token:
        return jsonify({"success": False, "error": "Paperless not configured"})

    try:
        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(
            f"{url}/api/trash/empty/",
            json={"action": "empty"},
            headers=headers,
            timeout=120
        )

        if resp.status_code == 200:
            data = resp.json()
            return jsonify({
                "success": True,
                "deleted_count": len(data.get("doc_ids", [])),
                "result": data.get("result")
            })
        else:
            return jsonify({
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}"
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/Volumes/ACASIS/apps/lib")

    try:
        import portauth
        port = portauth.allocate("doc-recognition-gui", ttl_seconds=86400)
        print(f"Port Authority: allocated port {port}")
    except Exception as e:
        print(f"Port Authority unavailable ({e}), using default port 8080")
        port = 8080

    app.run(host="0.0.0.0", port=port, debug=True)
