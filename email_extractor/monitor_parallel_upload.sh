#!/bin/bash
# Monitor 8 parallel upload instances (4 MacBook + 4 DGX)

echo "=== PARALELNI UPLOAD MONITOR ==="
echo "Cas: $(date)"
echo "Celkem: 126,724 souboru (8 x ~15,840)"
echo ""

echo "== MACBOOK (4 instance x 4 workers = 16 paralelnich) =="
mb_total=0
SSHPASS='4438' sshpass -e ssh -o StrictHostKeyChecking=no majpuzik@100.90.154.98 "
for i in 1 2 3 4; do
  progress=\$(tail -c 200 /tmp/upload_mb_\$i.log 2>/dev/null | tr '\r' '\n' | grep -oE '[0-9]+/158[0-9]{2}' | tail -1)
  if [ -n \"\$progress\" ]; then
    echo \"  Instance \$i: \$progress\"
  else
    echo \"  Instance \$i: starting...\"
  fi
done
" 2>/dev/null

echo ""
echo "== DGX (4 instance x 4 workers = 16 paralelnich) =="
ssh dgx "
dgx_total=0
for i in 1 2 3 4; do
  progress=\$(tail -c 200 /tmp/upload_dgx_\$i.log 2>/dev/null | tr '\r' '\n' | grep -oE '[0-9]+/158[0-9]{2}' | tail -1)
  if [ -n \"\$progress\" ]; then
    current=\$(echo \$progress | cut -d/ -f1)
    dgx_total=\$((dgx_total + current))
    echo \"  Instance \$i: \$progress\"
  else
    echo \"  Instance \$i: starting...\"
  fi
done
echo \"  CELKEM DGX: \$dgx_total / 63,362\"
" 2>/dev/null

echo ""
echo "== PROCESY =="
echo "MacBook: $(SSHPASS='4438' sshpass -e ssh -o StrictHostKeyChecking=no majpuzik@100.90.154.98 'pgrep -f parallel_upload_stuck | wc -l' 2>/dev/null | tr -d ' ') procesů"
echo "DGX: $(ssh dgx 'pgrep -f parallel_upload_stuck | wc -l' 2>/dev/null | tr -d ' ') procesů"
