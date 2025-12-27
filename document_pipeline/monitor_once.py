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

"""Single-run monitor - use with: watch -n 10 ./monitor_once.py"""
import subprocess
import re
from datetime import datetime

def cmd(c, timeout=8):
    try:
        r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ""

print("=" * 70)
print(f"  📊 PIPELINE MONITOR  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# ==== SYSTEM RESOURCES (all 4 machines) ====
print("\n📈 SYSTÉMOVÉ ZDROJE (CPU/RAM/GPU/DISK)")
print("-" * 70)

# Mac Mini M4 (local)
cpu = cmd("python3 -c 'import psutil; print(int(psutil.cpu_percent()))'")
ram = cmd("python3 -c 'import psutil; print(int(psutil.virtual_memory().percent))'")
disk = cmd("df -h /Volumes/ACASIS 2>/dev/null | tail -1 | awk '{print $5}'") or "?"
print(f"  Mac Mini M4:   CPU {cpu:>3}%  RAM {ram:>3}%  Disk {disk}")

# DGX
dgx = cmd("ssh -o ConnectTimeout=3 dgx 'python3 -c \"import psutil; print(int(psutil.cpu_percent()), int(psutil.virtual_memory().percent))\" 2>/dev/null; df -h /home 2>/dev/null | tail -1 | awk \"{print \\$5}\"; nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1' 2>/dev/null")
if dgx:
    lines = dgx.split('\n')
    if len(lines) >= 1:
        parts = lines[0].split()
        dgx_cpu = parts[0] if len(parts) > 0 else "?"
        dgx_ram = parts[1] if len(parts) > 1 else "?"
        dgx_disk = lines[1] if len(lines) > 1 else "?"
        dgx_gpu = lines[2] if len(lines) > 2 else "?"
        print(f"  DGX:           CPU {dgx_cpu:>3}%  RAM {dgx_ram:>3}%  Disk {dgx_disk}  GPU {dgx_gpu}")

# Dell (Tailscale)
dell = cmd("ssh -o ConnectTimeout=3 maj@100.77.108.70 'python3 -c \"import psutil; print(int(psutil.cpu_percent()), int(psutil.virtual_memory().percent))\" 2>/dev/null; df -h /home 2>/dev/null | tail -1 | awk \"{print \\$5}\"; nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1' 2>/dev/null")
if dell:
    lines = dell.split('\n')
    if len(lines) >= 1:
        parts = lines[0].split()
        dell_cpu = parts[0] if len(parts) > 0 else "?"
        dell_ram = parts[1] if len(parts) > 1 else "?"
        dell_disk = lines[1] if len(lines) > 1 else "?"
        dell_gpu = lines[2] if len(lines) > 2 else "?"
        print(f"  Dell:          CPU {dell_cpu:>3}%  RAM {dell_ram:>3}%  Disk {dell_disk}  GPU {dell_gpu}")

# MacBook
mb = cmd("ssh -o ConnectTimeout=3 majpuzik@192.168.10.102 'python3 -c \"import psutil; print(int(psutil.cpu_percent()), int(psutil.virtual_memory().percent))\" 2>/dev/null; df -h / 2>/dev/null | tail -1 | awk \"{print \\$5}\"' 2>/dev/null")
if mb:
    lines = mb.split('\n')
    if len(lines) >= 1:
        parts = lines[0].split()
        mb_cpu = parts[0] if len(parts) > 0 else "?"
        mb_ram = parts[1] if len(parts) > 1 else "?"
        mb_disk = lines[1] if len(lines) > 1 else "?"
        print(f"  MacBook Pro:   CPU {mb_cpu:>3}%  RAM {mb_ram:>3}%  Disk {mb_disk}")

# ==== EMAIL IMPORT ====
print("\n🔷 FÁZE A: EMAIL IMPORT DO PAPERLESS")
print("-" * 50)
log = cmd("tail -1 /Volumes/ACASIS/apps/maj-document-recognition/phase1_output/phase5_import.log")
if log:
    m = re.search(r'\[(\d+)/(\d+)\].*Success: (\d+).*Failed: (\d+)', log)
    if m:
        cur, tot, suc, fail = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
        pct = cur/tot*100
        bar = "█" * int(pct/2.5) + "░" * (40 - int(pct/2.5))
        print(f"  [{bar}] {pct:.1f}%")
        print(f"  Dokumenty: {cur:,} / {tot:,}")
        print(f"  Úspěšné: {suc}  |  Selhané: {fail}")

running = cmd("pgrep -f phase5_import | wc -l").strip()
print(f"  Status: {'🟢 BĚŽÍ' if running and int(running) > 0 else '⏹️ DOKONČENO'}")

# B1 Copy
print("\n🔷 FÁZE B1: KOPÍROVÁNÍ DOKUMENTŮ NA DGX")
print("-" * 50)
db_count = cmd("ssh -o ConnectTimeout=5 dgx 'find /home/puzik/document-pipeline/input/dropbox -name \"*.pdf\" -o -name \"*.PDF\" 2>/dev/null | wc -l'")
od_count = cmd("ssh -o ConnectTimeout=5 dgx 'find /home/puzik/document-pipeline/input/onedrive -name \"*.pdf\" -o -name \"*.PDF\" 2>/dev/null | wc -l'")
ac_count = cmd("ssh -o ConnectTimeout=5 dgx 'find /home/puzik/document-pipeline/input/acasis -name \"*.pdf\" -o -name \"*.PDF\" 2>/dev/null | wc -l'")
db_pct = int(db_count or 0) / 81607 * 100
od_pct = int(od_count or 0) / 164336 * 100
ac_pct = int(ac_count or 0) / 100000 * 100  # estimate ~100k
print(f"  Dropbox:  {int(db_count or 0):>7,} / 81,607  ({db_pct:.1f}%)")
print(f"  OneDrive: {int(od_count or 0):>7,} / 164,336 ({od_pct:.1f}%)")
print(f"  ACASIS:   {int(ac_count or 0):>7,} / ~100,000 ({ac_pct:.1f}%)")

rsync_running = cmd("ssh -o ConnectTimeout=3 dgx 'pgrep -f rsync | wc -l' 2>/dev/null").strip()
print(f"  Rsync procesy: {rsync_running or '0'}")

# B2 Docling
print("\n🔷 FÁZE B2: DOCLING ANALÝZA (~120 instancí)")
print("-" * 50)
mm = cmd("pgrep -f 'b2_docling|docling_parallel' | wc -l").strip() or "0"
mb = cmd("ssh -o ConnectTimeout=3 majpuzik@192.168.10.102 'pgrep -f b2_docling | wc -l' 2>/dev/null").strip() or "0"
dx = cmd("ssh -o ConnectTimeout=3 dgx 'pgrep -f b2_docling | wc -l' 2>/dev/null").strip() or "0"
dl = cmd("ssh -o ConnectTimeout=3 maj@100.77.108.70 'pgrep -f b2_docling | wc -l' 2>/dev/null").strip() or "0"
total = int(mm)+int(mb)+int(dx)+int(dl)
print(f"  Mac Mini M4:  {mm:>3} instancí")
print(f"  MacBook Pro:  {mb:>3} instancí")
print(f"  DGX:          {dx:>3} instancí")
print(f"  Dell:         {dl:>3} instancí")
print(f"  ─────────────────────────")
print(f"  CELKEM:       {total:>3} instancí")

b2_ok = cmd("ssh -o ConnectTimeout=5 dgx 'find /home/puzik/document-pipeline/output/b2_docling -name \"*.json\" 2>/dev/null | wc -l'") or "0"
b2_fail = cmd("ssh -o ConnectTimeout=5 dgx 'find /home/puzik/document-pipeline/work/b2_failed -name \"*.json\" 2>/dev/null | wc -l'") or "0"
print(f"\n  Zpracováno: ✓ {b2_ok} úspěšných  |  ✗ {b2_fail} selhalo")

# Doc types from B2
types = cmd("ssh -o ConnectTimeout=5 dgx 'grep -h doc_type /home/puzik/document-pipeline/output/b2_docling/*.json 2>/dev/null | sort | uniq -c | sort -rn | head -5'")
if types and types.strip():
    print(f"\n  Typy dokumentů:")
    for line in types.split('\n')[:5]:
        if line.strip():
            print(f"    {line.strip()}")

# B3-B6
print("\n🔷 FÁZE B3-B6: NÁSLEDUJÍCÍ KROKY")
print("-" * 50)
b3 = cmd("pgrep -f 'b3_llm|llm_32b' | wc -l").strip() or "0"
print(f"  B3 LLM 32B:     {b3} instancí  (čeká na B2)")
print(f"  B4 Externí:     - (čeká)")
print(f"  B5 Manuální:    - (čeká)")
print(f"  B6 Import:      - (čeká)")

print("\n" + "=" * 70)
print("  Pro kontinuální: watch -n 10 ./monitor_once.py")
print("=" * 70)
