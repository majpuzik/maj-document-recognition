#!/bin/bash
# Check parallel upload status

echo "=== PARALELNÍ UPLOAD - STAV ==="
echo "Čas: $(date)"
echo ""

# DGX status
echo "📡 DGX (63,362 souborů):"
ssh dgx "tail -1 /tmp/upload_dgx.log 2>/dev/null | grep -o 'Upload:[^|]*|[^|]*|' | head -1" 2>/dev/null || echo "  (nelze připojit)"

# Local status
echo ""
echo "💻 Mac Mini (63,362 souborů):"
tail -1 /tmp/upload_local.log 2>/dev/null | grep -o 'Upload:[^|]*|[^|]*|' | head -1

echo ""
echo "📊 Celkem: 126,724 souborů"
echo ""

# Check if processes are running
echo "=== PROCESY ==="
echo "DGX:"
ssh dgx "pgrep -f parallel_upload_stuck && echo 'běží' || echo 'ukončen'" 2>/dev/null
echo "Local:"
pgrep -f parallel_upload_stuck && echo "běží" || echo "ukončen"
