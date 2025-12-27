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
Distributed Translator with Load Balancing v1.0
Paralelni preklady pres vice stroju s monitoringem zateze.
Pri 85%+ CPU/GPU/RAM pozastavi, po uvolneni pokracuje.
"""

import os
import sys
import json
import time
import socket
import psutil
import subprocess
import threading
import requests
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from queue import Queue, Empty
import logging

# Konfigurace
OLLAMA_MODEL = "qwen2.5:14b"
LOAD_THRESHOLD = 85  # % - pri prekroceni pozastavit
CHECK_INTERVAL = 2   # sekundy mezi kontrolami zateze
TRANSLATION_TIMEOUT = 300  # 5 minut max na preklad

# PostgreSQL koordinacni databaze
PG_CONFIG = {
    "host": "192.168.10.35",
    "port": 5433,
    "database": "almquist_cdb",
    "user": "maj",
    "password": "maj_central_2024"
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SystemLoad:
    cpu_percent: float
    ram_percent: float
    gpu_percent: float
    gpu_memory_percent: float
    timestamp: datetime

    def is_overloaded(self) -> bool:
        return (self.cpu_percent > LOAD_THRESHOLD or
                self.ram_percent > LOAD_THRESHOLD or
                self.gpu_percent > LOAD_THRESHOLD or
                self.gpu_memory_percent > LOAD_THRESHOLD)

    def __str__(self):
        return f"CPU:{self.cpu_percent:.0f}% RAM:{self.ram_percent:.0f}% GPU:{self.gpu_percent:.0f}% VRAM:{self.gpu_memory_percent:.0f}%"


class SystemMonitor:
    """Monitoruje zatez systemu (CPU, RAM, GPU)"""

    def __init__(self):
        self.hostname = socket.gethostname()
        self._detect_gpu_type()

    def _detect_gpu_type(self):
        """Detekuje typ GPU (NVIDIA, Apple Silicon, zadne)"""
        self.gpu_type = None

        # NVIDIA
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                self.gpu_type = 'nvidia'
                logger.info(f"Detected NVIDIA GPU on {self.hostname}")
                return
        except:
            pass

        # Apple Silicon
        if sys.platform == 'darwin':
            try:
                result = subprocess.run(['sysctl', '-n', 'hw.optional.arm64'],
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and '1' in result.stdout:
                    self.gpu_type = 'apple'
                    logger.info(f"Detected Apple Silicon on {self.hostname}")
                    return
            except:
                pass

        logger.info(f"No GPU detected on {self.hostname}, using CPU only")

    def get_nvidia_stats(self) -> Tuple[float, float]:
        """Vrati (gpu_utilization, gpu_memory_percent) pro NVIDIA"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                gpu_util = float(parts[0].strip())
                mem_used = float(parts[1].strip())
                mem_total = float(parts[2].strip())
                mem_percent = (mem_used / mem_total) * 100 if mem_total > 0 else 0
                return gpu_util, mem_percent
        except:
            pass
        return 0.0, 0.0

    def get_apple_gpu_stats(self) -> Tuple[float, float]:
        """Vrati (gpu_utilization, gpu_memory_percent) pro Apple Silicon"""
        try:
            # powermetrics potrebuje sudo, pouzijeme odhad z RAM
            # Apple Silicon sdili pamet s GPU
            mem = psutil.virtual_memory()
            # Odhad GPU zateze z CPU (unified memory)
            cpu = psutil.cpu_percent(interval=0.1)
            return cpu * 0.5, mem.percent  # GPU sdili RAM
        except:
            return 0.0, 0.0

    def get_load(self) -> SystemLoad:
        """Vrati aktualni zatez systemu"""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent

        gpu_util, gpu_mem = 0.0, 0.0
        if self.gpu_type == 'nvidia':
            gpu_util, gpu_mem = self.get_nvidia_stats()
        elif self.gpu_type == 'apple':
            gpu_util, gpu_mem = self.get_apple_gpu_stats()

        return SystemLoad(
            cpu_percent=cpu,
            ram_percent=ram,
            gpu_percent=gpu_util,
            gpu_memory_percent=gpu_mem,
            timestamp=datetime.now()
        )


class TranslationQueue:
    """Fronta prekladu v PostgreSQL"""

    def __init__(self):
        self.conn = None
        self._connect()
        self._ensure_tables()

    def _connect(self):
        try:
            import psycopg2
            self.conn = psycopg2.connect(**PG_CONFIG)
            self.conn.autocommit = False
            logger.info("Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            raise

    def _ensure_tables(self):
        """Vytvori tabulky pokud neexistuji"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS translation_queue (
                    id SERIAL PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    source_lang VARCHAR(10),
                    target_lang VARCHAR(10) DEFAULT 'cs',
                    translated_text TEXT,
                    status VARCHAR(20) DEFAULT 'pending',
                    worker_id VARCHAR(100),
                    category VARCHAR(50),
                    tags TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS translation_workers (
                    worker_id VARCHAR(100) PRIMARY KEY,
                    hostname VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'idle',
                    cpu_percent FLOAT,
                    ram_percent FLOAT,
                    gpu_percent FLOAT,
                    gpu_memory_percent FLOAT,
                    translations_done INTEGER DEFAULT 0,
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_tq_status ON translation_queue(status);
                CREATE INDEX IF NOT EXISTS idx_tw_status ON translation_workers(status);
            """)
            self.conn.commit()
            logger.info("Database tables ready")

    def add_task(self, text: str, source_lang: str, category: str = None,
                 tags: List[str] = None, metadata: Dict = None) -> int:
        """Prida novou ulohu do fronty"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO translation_queue
                (source_text, source_lang, category, tags, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (text, source_lang, category,
                  json.dumps(tags) if tags else None,
                  json.dumps(metadata) if metadata else None))
            task_id = cur.fetchone()[0]
            self.conn.commit()
            return task_id

    def claim_task(self, worker_id: str) -> Optional[Dict]:
        """Prevezme dalsi ulohu pro workera (atomicky)"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE translation_queue
                SET status = 'processing',
                    worker_id = %s,
                    started_at = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id FROM translation_queue
                    WHERE status = 'pending'
                    ORDER BY id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, source_text, source_lang, category, tags, metadata
            """, (worker_id,))
            row = cur.fetchone()
            self.conn.commit()

            if row:
                # JSONB returns dict directly, TEXT needs json.loads
                tags = row[4]
                if isinstance(tags, str):
                    tags = json.loads(tags)
                metadata = row[5]
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                return {
                    'id': row[0],
                    'source_text': row[1],
                    'source_lang': row[2],
                    'category': row[3],
                    'tags': tags if tags else [],
                    'metadata': metadata if metadata else {}
                }
            return None

    def complete_task(self, task_id: int, translated_text: str):
        """Oznaci ulohu jako dokoncenoi"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE translation_queue
                SET status = 'completed',
                    translated_text = %s,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (translated_text, task_id))
            self.conn.commit()

    def fail_task(self, task_id: int, error: str):
        """Oznaci ulohu jako chybnou"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE translation_queue
                SET status = 'failed',
                    error_message = %s,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (error, task_id))
            self.conn.commit()

    def release_task(self, task_id: int):
        """Uvolni ulohu zpet do fronty (pri pozastaveni)"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE translation_queue
                SET status = 'pending',
                    worker_id = NULL,
                    started_at = NULL
                WHERE id = %s
            """, (task_id,))
            self.conn.commit()

    def get_stats(self) -> Dict:
        """Vrati statistiky fronty"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*) FROM translation_queue GROUP BY status
            """)
            stats = dict(cur.fetchall())

            cur.execute("""
                SELECT worker_id, status, cpu_percent, ram_percent,
                       gpu_percent, translations_done
                FROM translation_workers
                WHERE last_heartbeat > NOW() - INTERVAL '60 seconds'
            """)
            workers = [
                {'id': r[0], 'status': r[1], 'cpu': r[2], 'ram': r[3],
                 'gpu': r[4], 'done': r[5]}
                for r in cur.fetchall()
            ]

            return {'queue': stats, 'workers': workers}

    def get_completed(self) -> List[Dict]:
        """Vrati vsechny dokoncene preklady"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, source_text, source_lang, translated_text,
                       category, tags, metadata
                FROM translation_queue
                WHERE status = 'completed'
                ORDER BY id
            """)
            results = []
            for r in cur.fetchall():
                tags = r[5] if isinstance(r[5], (list, dict)) else (json.loads(r[5]) if r[5] else [])
                metadata = r[6] if isinstance(r[6], dict) else (json.loads(r[6]) if r[6] else {})
                results.append({
                    'id': r[0],
                    'source_text': r[1],
                    'source_lang': r[2],
                    'translated_text': r[3],
                    'category': r[4],
                    'tags': tags,
                    'metadata': metadata
                })
            return results


class TranslationWorker:
    """Worker ktery bezi na kazdem stroji a provadi preklady"""

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}"
        self.hostname = socket.gethostname()
        self.ollama_host = ollama_host
        self.monitor = SystemMonitor()
        self.queue = TranslationQueue()
        self.running = True
        self.paused = False
        self.current_task_id = None
        self.translations_done = 0

        logger.info(f"Worker {self.worker_id} initialized")
        logger.info(f"Ollama host: {ollama_host}")
        logger.info(f"Load threshold: {LOAD_THRESHOLD}%")

    def translate(self, text: str, source_lang: str) -> Optional[str]:
        """Prelozi text pres Ollama"""
        if source_lang == 'cs':
            return text  # Uz je cesky

        # Zkratime moc dlouhe texty
        if len(text) > 15000:
            text = text[:15000] + "..."

        lang_names = {
            'en': 'English', 'fr': 'French', 'de': 'German',
            'ru': 'Russian', 'pl': 'Polish', 'sk': 'Slovak',
            'hu': 'Hungarian', 'it': 'Italian', 'es': 'Spanish'
        }
        lang_name = lang_names.get(source_lang, source_lang)

        prompt = f"""Translate the following {lang_name} text to Czech.
Keep the meaning and style. Output only the Czech translation, nothing else.

Text to translate:
{text}

Czech translation:"""

        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3}
                },
                timeout=TRANSLATION_TIMEOUT
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
        except Exception as e:
            logger.warning(f"Translation failed: {e}")

        return None

    def update_status(self, status: str, load: SystemLoad):
        """Aktualizuje status workera v DB"""
        try:
            with self.queue.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO translation_workers
                    (worker_id, hostname, status, cpu_percent, ram_percent,
                     gpu_percent, gpu_memory_percent, translations_done, last_heartbeat)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (worker_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        cpu_percent = EXCLUDED.cpu_percent,
                        ram_percent = EXCLUDED.ram_percent,
                        gpu_percent = EXCLUDED.gpu_percent,
                        gpu_memory_percent = EXCLUDED.gpu_memory_percent,
                        translations_done = EXCLUDED.translations_done,
                        last_heartbeat = CURRENT_TIMESTAMP
                """, (self.worker_id, self.hostname, status,
                      load.cpu_percent, load.ram_percent,
                      load.gpu_percent, load.gpu_memory_percent,
                      self.translations_done))
                self.queue.conn.commit()
        except Exception as e:
            logger.error(f"Failed to update status: {e}")

    def run(self):
        """Hlavni smycka workera"""
        logger.info(f"Worker {self.worker_id} starting...")

        while self.running:
            try:
                load = self.monitor.get_load()

                # Kontrola pretizeni
                if load.is_overloaded():
                    if not self.paused:
                        logger.warning(f"OVERLOADED: {load} - pausing")
                        self.paused = True
                        # Uvolnit aktualni ulohu zpet do fronty
                        if self.current_task_id:
                            self.queue.release_task(self.current_task_id)
                            self.current_task_id = None
                    self.update_status('paused', load)
                    time.sleep(CHECK_INTERVAL * 2)
                    continue
                else:
                    if self.paused:
                        logger.info(f"Load normalized: {load} - resuming")
                        self.paused = False

                # Zkusit prevzit ulohu
                task = self.queue.claim_task(self.worker_id)

                if task:
                    self.current_task_id = task['id']
                    self.update_status('translating', load)

                    text_preview = task['source_text'][:100].replace('\n', ' ')
                    logger.info(f"Translating #{task['id']}: {text_preview}...")

                    # Preklad
                    translated = self.translate(task['source_text'], task['source_lang'])

                    if translated:
                        self.queue.complete_task(task['id'], translated)
                        self.translations_done += 1
                        logger.info(f"Completed #{task['id']} ({self.translations_done} total)")
                    else:
                        self.queue.fail_task(task['id'], "Translation returned empty")
                        logger.warning(f"Failed #{task['id']}")

                    self.current_task_id = None
                else:
                    # Zadna uloha - cekame
                    self.update_status('idle', load)
                    time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                self.running = False
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(CHECK_INTERVAL)

        # Uvolnit pripadnou rozdelanou ulohu
        if self.current_task_id:
            self.queue.release_task(self.current_task_id)

        logger.info(f"Worker {self.worker_id} stopped. Total translations: {self.translations_done}")


class Coordinator:
    """Koordinator ktery naplni frontu a sleduje progress"""

    def __init__(self):
        self.queue = TranslationQueue()

    def add_texts_from_rag(self, rag_file: str):
        """Nacte texty z RAG JSON a prida do fronty"""
        with open(rag_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        added = 0
        for doc in data.get('documents', []):
            text = doc.get('content', '')
            lang = doc.get('language', 'unknown')

            # Preskocit uz prelozene (cs)
            if lang == 'cs':
                continue

            # Preskocit kratke texty
            if len(text) < 100:
                continue

            self.queue.add_task(
                text=text,
                source_lang=lang,
                category=doc.get('category'),
                tags=doc.get('tags', []),
                metadata={
                    'title': doc.get('title'),
                    'url': doc.get('url'),
                    'original_id': doc.get('id')
                }
            )
            added += 1

        logger.info(f"Added {added} texts to translation queue")
        return added

    def add_texts_direct(self, texts: List[Dict]):
        """Prida texty primo"""
        added = 0
        for item in texts:
            if item.get('lang', 'unknown') == 'cs':
                continue

            self.queue.add_task(
                text=item['text'],
                source_lang=item.get('lang', 'unknown'),
                category=item.get('category'),
                tags=item.get('tags', []),
                metadata=item.get('metadata', {})
            )
            added += 1

        logger.info(f"Added {added} texts to translation queue")
        return added

    def monitor_progress(self, interval: int = 5):
        """Sleduje progress prekladu"""
        logger.info("Monitoring translation progress...")

        try:
            while True:
                stats = self.queue.get_stats()
                queue = stats['queue']
                workers = stats['workers']

                pending = queue.get('pending', 0)
                processing = queue.get('processing', 0)
                completed = queue.get('completed', 0)
                failed = queue.get('failed', 0)
                total = pending + processing + completed + failed

                # Progress bar
                if total > 0:
                    pct = (completed / total) * 100
                    bar_len = 30
                    filled = int(bar_len * completed / total)
                    bar = '=' * filled + '-' * (bar_len - filled)

                    print(f"\r[{bar}] {pct:.1f}% | "
                          f"Done:{completed} Pending:{pending} "
                          f"Processing:{processing} Failed:{failed} | "
                          f"Workers:{len(workers)}", end='', flush=True)

                # Konec?
                if pending == 0 and processing == 0:
                    print("\nAll translations completed!")
                    break

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nMonitoring stopped")

    def export_results(self, output_file: str):
        """Exportuje prelozene texty"""
        results = self.queue.get_completed()

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'total': len(results),
                'translations': results
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(results)} translations to {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Distributed Translator with Load Balancing')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Worker
    worker_parser = subparsers.add_parser('worker', help='Run translation worker')
    worker_parser.add_argument('--ollama', default='http://localhost:11434',
                               help='Ollama API host')

    # Add from RAG file
    add_parser = subparsers.add_parser('add', help='Add texts to queue')
    add_parser.add_argument('file', help='RAG JSON file')

    # Monitor
    subparsers.add_parser('monitor', help='Monitor progress')

    # Stats
    subparsers.add_parser('stats', help='Show queue statistics')

    # Export
    export_parser = subparsers.add_parser('export', help='Export completed translations')
    export_parser.add_argument('output', help='Output JSON file')

    args = parser.parse_args()

    if args.command == 'worker':
        worker = TranslationWorker(ollama_host=args.ollama)
        worker.run()

    elif args.command == 'add':
        coord = Coordinator()
        coord.add_texts_from_rag(args.file)

    elif args.command == 'monitor':
        coord = Coordinator()
        coord.monitor_progress()

    elif args.command == 'stats':
        queue = TranslationQueue()
        stats = queue.get_stats()
        print("\n=== Translation Queue Stats ===")
        print(f"Queue: {stats['queue']}")
        print(f"\nActive Workers ({len(stats['workers'])}):")
        for w in stats['workers']:
            print(f"  {w['id']}: {w['status']} | CPU:{w['cpu']:.0f}% RAM:{w['ram']:.0f}% GPU:{w['gpu']:.0f}% | Done:{w['done']}")

    elif args.command == 'export':
        coord = Coordinator()
        coord.export_results(args.output)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
