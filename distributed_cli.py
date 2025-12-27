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
CLI interface for distributed document processing
Simple wrapper for easy invocation
"""

import argparse
import subprocess
import sys
import json
from pathlib import Path

def find_ollama_servers():
    """Find Ollama servers in network"""
    print("🔍 Searching for Ollama servers...")

    try:
        result = subprocess.run(
            ["nmap", "-p", "11434", "192.168.10.0/24", "--open", "-T4"],
            capture_output=True,
            text=True,
            timeout=30
        )

        servers = []
        lines = result.stdout.split('\n')
        for i, line in enumerate(lines):
            if '11434/tcp open' in line:
                # Get IP from previous lines
                for j in range(i-1, max(i-5, 0), -1):
                    if 'Nmap scan report' in lines[j]:
                        ip = lines[j].split('(')[-1].split(')')[0]
                        if not ip:
                            ip = lines[j].split()[-1]
                        servers.append(f"http://{ip}:11434")
                        break

        # Always include localhost
        if "http://localhost:11434" not in servers:
            servers.insert(0, "http://localhost:11434")

        return servers
    except Exception as e:
        print(f"⚠️ nmap search failed: {e}")
        return ["http://localhost:11434"]


def check_server_models(server):
    """Check available models on server"""
    try:
        import requests
        response = requests.get(f"{server}/api/tags", timeout=5)
        data = response.json()
        models = [m['name'] for m in data.get('models', [])]
        return models
    except Exception as e:
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Distributed Document Processing CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-discover and process 2000 emails
  %(prog)s run --limit 2000

  # Use specific servers
  %(prog)s run --servers localhost 192.168.10.83

  # List available servers
  %(prog)s discover

  # Monitor running process
  %(prog)s monitor
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Start distributed processing')
    run_parser.add_argument('--limit', type=int, default=2000, help='Number of documents to process')
    run_parser.add_argument('--workers-per-server', type=int, default=4, help='Workers per Ollama server')
    run_parser.add_argument('--servers', nargs='+', help='Specific Ollama server IPs')
    run_parser.add_argument('--model', default='qwen2.5:32b', help='Ollama model to use')
    run_parser.add_argument('--max-cpu', type=int, default=90, help='Max CPU percentage')
    run_parser.add_argument('--max-mem', type=int, default=90, help='Max memory percentage')

    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover Ollama servers')

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor running process')
    monitor_parser.add_argument('--interval', type=int, default=60, help='Refresh interval in seconds')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show processing statistics')

    args = parser.parse_args()

    if args.command == 'discover':
        servers = find_ollama_servers()
        print(f"\n✅ Found {len(servers)} Ollama server(s):")
        for server in servers:
            print(f"\n📡 {server}")
            models = check_server_models(server)
            if models:
                print(f"   Models: {', '.join(models[:3])}...")
            else:
                print(f"   ⚠️ Cannot connect or no models")

    elif args.command == 'run':
        # Find or use specified servers
        if args.servers:
            servers = [f"http://{s}:11434" if ':' not in s else s for s in args.servers]
        else:
            servers = find_ollama_servers()

        print(f"\n🚀 Starting distributed processing:")
        print(f"   📊 Documents: {args.limit}")
        print(f"   🖥️  Servers: {len(servers)}")
        print(f"   ⚙️  Workers: {len(servers) * args.workers_per_server}")
        print(f"   🤖 Model: {args.model}")
        print(f"   📈 Limits: CPU={args.max_cpu}% MEM={args.max_mem}%")

        for server in servers:
            print(f"      - {server}")

        print(f"\n📝 Log: logs/distributed_run.log")
        print(f"💾 Database: data/documents.db")
        print(f"\nℹ️  Monitor with: distributed_cli.py monitor\n")

        # Start processing
        subprocess.run([
            sys.executable,
            "distributed_parallel_test.py"
        ])

    elif args.command == 'monitor':
        # Run monitoring script in watch loop
        try:
            import time
            while True:
                subprocess.run(["/tmp/monitor_distributed.sh"])
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\n✋ Monitoring stopped")

    elif args.command == 'stats':
        # Show database statistics
        import sqlite3
        db_path = Path("data/documents.db")

        if not db_path.exists():
            print("❌ No database found. Run processing first.")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Total documents
        cursor.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]

        # By type
        cursor.execute("""
            SELECT document_type, COUNT(*) as count
            FROM documents
            GROUP BY document_type
            ORDER BY count DESC
        """)

        print(f"\n📊 Processing Statistics\n")
        print(f"Total documents: {total}")
        print(f"\n📋 By type:")
        for row in cursor.fetchall():
            print(f"   {row[0]:<25} {row[1]:>5}")

        # By server (if metadata exists)
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
                print(f"\n🌐 By server:")
                for row in servers:
                    server_name = row[0].split('//')[1].split(':')[0] if '//' in row[0] else row[0]
                    print(f"   {server_name:<20} {row[1]:>5}")
        except:
            pass

        conn.close()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
