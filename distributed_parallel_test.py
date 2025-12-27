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
DISTRIBUTED parallel processing across multiple Ollama servers
Processes up to 2000 emails from Thunderbird using multiple AI servers
"""

import sys
import psutil
import time
import threading
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging
import email
import mailbox
from datetime import datetime
import itertools

sys.path.insert(0, str(Path(__file__).parent))

from src.ocr.document_processor import DocumentProcessor
from src.ai.classifier_improved import ImprovedAIClassifier
from src.database.db_manager import DatabaseManager
from src.integrations.blacklist_whitelist import BlacklistWhitelist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/distributed_test.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# OLLAMA SERVERS - round-robin distribution
OLLAMA_SERVERS = [
    "http://localhost:11434",
    "http://192.168.10.83:11434",
]

# Global round-robin iterator
server_cycle = itertools.cycle(OLLAMA_SERVERS)

class ResourceMonitor:
    """Monitor LOCAL system resources only"""

    def __init__(self, max_cpu=90, max_mem=90, check_interval=30):
        self.max_cpu = max_cpu
        self.max_mem = max_mem
        self.check_interval = check_interval
        self.should_reduce = False
        self.current_workers = 0
        self.monitoring = False

    def check_resources(self):
        """Check if LOCAL resources are within limits"""
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent

        cpu_ok = cpu < self.max_cpu
        mem_ok = mem < self.max_mem

        return {
            "cpu": cpu,
            "mem": mem,
            "cpu_ok": cpu_ok,
            "mem_ok": mem_ok,
            "safe": cpu_ok and mem_ok
        }

    def start_monitoring(self, executor, futures_list):
        """Start background monitoring"""
        self.monitoring = True

        def monitor_loop():
            while self.monitoring and futures_list:
                time.sleep(self.check_interval)

                resources = self.check_resources()
                active = sum(1 for f in futures_list if not f.done())

                logger.info(f"📊 Monitor: CPU={resources['cpu']:.1f}% MEM={resources['mem']:.1f}% Active={active}")

                if not resources['safe']:
                    logger.warning(f"⚠️ LOCAL OVERLOAD! CPU={resources['cpu']:.1f}% MEM={resources['mem']:.1f}%")

                    # Cancel some futures to reduce load
                    cancelled = 0
                    for f in reversed(futures_list):
                        if not f.done() and not f.running():
                            f.cancel()
                            cancelled += 1
                            if cancelled >= 2:  # Cancel 2 at a time
                                break

                    if cancelled > 0:
                        logger.warning(f"🛑 Cancelled {cancelled} pending tasks to reduce LOCAL load")

                    time.sleep(5)  # Wait before next check

        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        return thread

def load_config():
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # BEST MODEL
    config['ai']['ollama']['model'] = 'qwen2.5:32b'
    config['ai']['ollama']['temperature'] = 0.05
    config['ai']['ollama']['timeout'] = 180

    return config

def extract_from_multiple_mailboxes(profile_path, temp_dir, limit=2000, max_size_mb=3):
    """Extract from multiple mailboxes"""

    mailboxes = [
        profile_path / "ImapMail/outlook.office365.com/INBOX",
        profile_path / "ImapMail/outlook.office365.com/Archive",
        profile_path / "ImapMail/outlook.office365.com/Archivovat",
        profile_path / "ImapMail/outlook.office365.com/Sent-1",
    ]

    all_attachments = []
    max_size_bytes = max_size_mb * 1024 * 1024

    for mailbox_path in mailboxes:
        if not mailbox_path.exists():
            logger.warning(f"Mailbox not found: {mailbox_path.name}")
            continue

        if len(all_attachments) >= limit:
            break

        logger.info(f"\n📬 Scanning: {mailbox_path.name}")

        try:
            mbox = mailbox.mbox(str(mailbox_path))
            count = 0

            for idx, msg in enumerate(mbox):
                if len(all_attachments) >= limit:
                    break

                sender = msg.get("From", "")
                subject = msg.get("Subject", "")

                for part in msg.walk():
                    if len(all_attachments) >= limit:
                        break

                    if part.get_content_maintype() == "multipart":
                        continue

                    filename = part.get_filename()
                    if not filename:
                        continue

                    ext = Path(filename).suffix.lower()
                    if ext not in ['.pdf', '.jpg', '.jpeg', '.png']:
                        continue

                    try:
                        payload = part.get_payload(decode=True)
                        if len(payload) > max_size_bytes:
                            continue

                        timestamp = int(datetime.now().timestamp() * 1000000)
                        safe_filename = f"doc_{len(all_attachments)}_{timestamp}_{filename}"
                        attachment_path = temp_dir / safe_filename

                        with open(attachment_path, "wb") as f:
                            f.write(payload)

                        all_attachments.append({
                            "path": str(attachment_path),
                            "filename": filename,
                            "sender": sender,
                            "subject": subject,
                            "mailbox": mailbox_path.name,
                            "size_kb": len(payload) / 1024
                        })

                        count += 1

                        if count % 50 == 0:
                            logger.info(f"  [{len(all_attachments)}/{limit}] extracted from {mailbox_path.name}")

                    except Exception as e:
                        logger.debug(f"Error extracting: {e}")

            logger.info(f"✓ {mailbox_path.name}: {count} attachments")

        except Exception as e:
            logger.error(f"Mailbox error {mailbox_path.name}: {e}")

    return all_attachments

def process_single_document(args):
    """Process one document - with distributed Ollama server"""
    attachment, config, idx, total, ollama_server = args

    # Override ollama host for this worker
    config['ai']['ollama']['host'] = ollama_server

    processor = DocumentProcessor(config)
    db = DatabaseManager(config)
    classifier = ImprovedAIClassifier(config, db)
    blacklist_whitelist = BlacklistWhitelist(config)

    result = {
        "idx": idx,
        "filename": attachment['filename'],
        "success": False,
        "server": ollama_server,
    }

    try:
        # OCR
        ocr_result = processor.process_document(attachment["path"])

        if not ocr_result.get("success"):
            result["error"] = "OCR failed"
            return result

        text = ocr_result.get("text", "")
        ocr_conf = ocr_result.get("confidence", 0)

        # AI
        classification = classifier.classify(text, ocr_result.get("metadata", {}))

        doc_type = classification.get("type", "jine")
        ai_conf = classification.get("confidence", 0)

        # Save
        doc_id = db.insert_document(
            file_path=attachment["path"],
            ocr_text=text,
            ocr_confidence=ocr_conf,
            document_type=doc_type,
            ai_confidence=ai_conf,
            metadata={
                **classification.get("metadata", {}),
                "sender": attachment["sender"],
                "subject": attachment["subject"],
                "mailbox": attachment["mailbox"],
                "ollama_server": ollama_server,
            }
        )

        result["success"] = True
        result["doc_type"] = doc_type
        result["confidence"] = ai_conf
        result["db_id"] = doc_id

        server_name = ollama_server.split("//")[1].split(":")[0]
        logger.info(f"[{idx}/{total}] ✓ {doc_type} ({ai_conf:.0%}) [{server_name}] - {attachment['filename'][:40]}")

        return result

    except Exception as e:
        logger.error(f"[{idx}/{total}] ✗ {e}")
        result["error"] = str(e)
        return result

def main():
    start_time = time.time()

    logger.info("="*80)
    logger.info("🚀 DISTRIBUTED PARALLEL PROCESSING - 2000 EMAILS")
    logger.info(f"Model: qwen2.5:32b (32.8B parameters)")
    logger.info(f"Ollama servers: {len(OLLAMA_SERVERS)}")
    for server in OLLAMA_SERVERS:
        logger.info(f"  - {server}")
    logger.info(f"Max workers: {len(OLLAMA_SERVERS) * 4} ({len(OLLAMA_SERVERS)} servers × 4 workers)")
    logger.info("="*80)

    # Setup
    config = load_config()
    temp_dir = Path("data/temp_distributed")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Extract
    logger.info("\n📧 EXTRACTING EMAILS...")
    profile_path = Path("/Users/m.a.j.puzik/Library/Thunderbird/Profiles/1oli4gwg.default-esr")

    attachments = extract_from_multiple_mailboxes(
        profile_path,
        temp_dir,
        limit=2000,
        max_size_mb=3
    )

    logger.info(f"\n✓ Extracted {len(attachments)} documents from {len(set(a['mailbox'] for a in attachments))} mailboxes")

    if not attachments:
        logger.error("No attachments!")
        return

    # Initial resource check
    monitor = ResourceMonitor(max_cpu=90, max_mem=90, check_interval=30)
    resources = monitor.check_resources()

    logger.info(f"\nInitial LOCAL state: CPU={resources['cpu']:.1f}% MEM={resources['mem']:.1f}%")

    # Determine workers based on number of servers
    num_servers = len(OLLAMA_SERVERS)
    max_workers = num_servers * 4  # 4 workers per server

    logger.info(f"Starting with {max_workers} workers ({num_servers} servers × 4)")

    # Process
    logger.info(f"\n🔄 PROCESSING {len(attachments)} DOCUMENTS...\n")

    # Distribute attachments across servers (round-robin)
    process_args = []
    for i, att in enumerate(attachments):
        server = next(server_cycle)
        process_args.append((att, config, i+1, len(attachments), server))

    results = []
    completed = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all
        futures_list = [executor.submit(process_single_document, args) for args in process_args]

        # Start monitoring LOCAL resources
        monitor.start_monitoring(executor, futures_list)

        # Collect results
        for future in as_completed(futures_list):
            try:
                result = future.result(timeout=300)  # 5 min timeout per doc
                results.append(result)
                completed += 1

                if completed % 20 == 0:
                    res = monitor.check_resources()
                    logger.info(f"\n📊 Progress: {completed}/{len(attachments)} | CPU={res['cpu']:.1f}% MEM={res['mem']:.1f}%\n")

            except Exception as e:
                logger.error(f"Task failed: {e}")
                completed += 1

    monitor.monitoring = False

    # Stats
    total_time = time.time() - start_time
    successful = sum(1 for r in results if r.get("success"))

    type_counts = Counter()
    total_conf = 0
    server_counts = Counter()

    for r in results:
        if r.get("success"):
            type_counts[r["doc_type"]] += 1
            total_conf += r["confidence"]
            server_counts[r["server"]] += 1

    avg_conf = total_conf / successful if successful > 0 else 0

    # Report
    logger.info(f"\n{'='*80}")
    logger.info("🎉 FINAL RESULTS")
    logger.info(f"{'='*80}")
    logger.info(f"⏱️  Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    logger.info(f"⚡ Avg/doc: {total_time/len(attachments):.1f}s")
    logger.info(f"📄 Processed: {len(results)}/{len(attachments)}")
    logger.info(f"✓ Success: {successful}")
    logger.info(f"✗ Failed: {len(results) - successful}")
    logger.info(f"🎯 Avg confidence: {avg_conf:.1%}")

    logger.info(f"\n📡 Server distribution:")
    for server, count in server_counts.items():
        pct = (count / successful * 100) if successful > 0 else 0
        server_name = server.split("//")[1].split(":")[0]
        logger.info(f"  {server_name:<20} {count:>4} ({pct:>5.1f}%)")

    logger.info(f"\n📊 Top 10 document types:")
    for doc_type, count in type_counts.most_common(10):
        pct = (count / successful * 100) if successful > 0 else 0
        logger.info(f"  {doc_type:<25} {count:>4} ({pct:>5.1f}%)")

    logger.info(f"\n💾 Database: data/documents.db")

    logger.info(f"{'='*80}\n")

    # Cleanup
    logger.info("🧹 Cleaning up...")
    cleaned = 0
    for att in attachments:
        try:
            Path(att["path"]).unlink(missing_ok=True)
            cleaned += 1
        except:
            pass
    logger.info(f"✓ Cleaned {cleaned} temp files")

if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    main()
