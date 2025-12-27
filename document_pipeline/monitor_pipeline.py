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
Pipeline Monitor - Real-time progress display
Shows: CPU/RAM usage, phase progress, document stats
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

DGX_BASE = "/home/puzik/document-pipeline"

def get_phase_stats(phase_dir):
    """Count files in phase output directory"""
    try:
        result = subprocess.run(
            ["ssh", "dgx", f"find {phase_dir} -name '*.json' | wc -l"],
            capture_output=True, text=True, timeout=10
        )
        return int(result.stdout.strip())
    except:
        return 0

def get_failed_count(failed_dir):
    """Count failed documents"""
    try:
        result = subprocess.run(
            ["ssh", "dgx", f"find {failed_dir} -name '*.json' | wc -l"],
            capture_output=True, text=True, timeout=10
        )
        return int(result.stdout.strip())
    except:
        return 0

def get_machine_stats(host):
    """Get CPU and RAM usage from machine"""
    try:
        if host == "local":
            import psutil
            return psutil.cpu_percent(), psutil.virtual_memory().percent
        else:
            result = subprocess.run(
                ["ssh", host, "python3 -c \"import psutil; print(psutil.cpu_percent(), psutil.virtual_memory().percent)\""],
                capture_output=True, text=True, timeout=10
            )
            parts = result.stdout.strip().split()
            return float(parts[0]), float(parts[1])
    except:
        return 0, 0

def get_running_instances(host, pattern):
    """Count running instances on host"""
    try:
        if host == "local":
            cmd = f"pgrep -f '{pattern}' | wc -l"
        else:
            cmd = f"ssh {host} \"pgrep -f '{pattern}' | wc -l\""
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return int(result.stdout.strip())
    except:
        return 0

def get_doc_type_stats():
    """Get document type distribution"""
    try:
        result = subprocess.run(
            ["ssh", "dgx", f"cat {DGX_BASE}/output/b2_docling/*.json 2>/dev/null | grep -o '\"doc_type\": \"[^\"]*\"' | sort | uniq -c | sort -rn | head -10"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except:
        return ""

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def main():
    while True:
        clear_screen()

        # Header
        print("=" * 70)
        print(f"  DOCUMENT PIPELINE MONITOR  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Machine stats
        print("\n📊 MACHINE STATUS (CPU% / RAM%)")
        print("-" * 40)

        mac_mini_cpu, mac_mini_ram = get_machine_stats("local")
        macbook_cpu, macbook_ram = get_machine_stats("majpuzik@192.168.10.102")
        dgx_cpu, dgx_ram = get_machine_stats("dgx")

        mac_mini_procs = get_running_instances("local", "b2_docling")
        macbook_procs = get_running_instances("majpuzik@192.168.10.102", "b2_docling")
        dgx_procs = get_running_instances("dgx", "b2_docling")

        print(f"  Mac Mini M4:  {mac_mini_cpu:5.1f}% / {mac_mini_ram:5.1f}%  [{mac_mini_procs} processes]")
        print(f"  MacBook Pro:  {macbook_cpu:5.1f}% / {macbook_ram:5.1f}%  [{macbook_procs} processes]")
        print(f"  DGX:          {dgx_cpu:5.1f}% / {dgx_ram:5.1f}%  [{dgx_procs} processes]")

        # Phase progress
        print("\n📈 PHASE PROGRESS")
        print("-" * 40)

        b2_success = get_phase_stats(f"{DGX_BASE}/output/b2_docling")
        b2_failed = get_failed_count(f"{DGX_BASE}/work/b2_failed")
        b3_success = get_phase_stats(f"{DGX_BASE}/output/b3_llm")
        b3_failed = get_failed_count(f"{DGX_BASE}/work/b3_failed")
        b4_success = get_phase_stats(f"{DGX_BASE}/output/b4_external")
        imported = get_phase_stats(f"{DGX_BASE}/output/imported")

        total_input = 245943  # OneDrive + Dropbox estimate

        print(f"  B2 Docling:   {b2_success:>6} success, {b2_failed:>5} failed")
        print(f"  B3 LLM 32B:   {b3_success:>6} success, {b3_failed:>5} failed")
        print(f"  B4 External:  {b4_success:>6} success")
        print(f"  Imported:     {imported:>6}")
        print(f"  ───────────────────────────────")
        print(f"  Total input:  ~{total_input:>6}")

        # Progress bar
        progress = (b2_success + b3_success + b4_success) / total_input * 100 if total_input > 0 else 0
        bar_len = 40
        filled = int(bar_len * progress / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\n  [{bar}] {progress:.1f}%")

        # Document types
        print("\n📁 DOCUMENT TYPES (Top 10)")
        print("-" * 40)
        doc_types = get_doc_type_stats()
        if doc_types:
            for line in doc_types.split('\n')[:10]:
                print(f"  {line}")
        else:
            print("  No data yet...")

        # Email import status (running in parallel)
        print("\n📧 EMAIL IMPORT STATUS")
        print("-" * 40)
        try:
            with open("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output/phase5_import.log") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    print(f"  {last_line}")
        except:
            print("  No email import data")

        print("\n" + "=" * 70)
        print("  Press Ctrl+C to exit")

        time.sleep(30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
