#!/bin/bash
# B2 Docling - Launch on ALL 4 machines (~120 processes)
# Usage: ./launch_b2_all.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
B2_SCRIPT="$SCRIPT_DIR/b2_docling_parallel.py"

# Machine configuration
# Total ~120 processes distributed across 4 machines
MAC_MINI_PROCS=30
MACBOOK_PROCS=30
DGX_PROCS=30
DELL_PROCS=30
TOTAL_PROCS=$((MAC_MINI_PROCS + MACBOOK_PROCS + DGX_PROCS + DELL_PROCS))

echo "=================================================="
echo "  B2 DOCLING PARALLEL LAUNCHER"
echo "  Total: $TOTAL_PROCS processes across 4 machines"
echo "=================================================="

# Function to get instance range for machine
get_range() {
    local start=$1
    local count=$2
    echo "$start $((start + count - 1))"
}

# Mac Mini M4 (local): instances 0-29
echo ""
echo "=== MAC MINI M4 (local) - $MAC_MINI_PROCS processes ==="
for i in $(seq 0 $((MAC_MINI_PROCS - 1))); do
    echo "Starting instance $i..."
    source ~/.venvs/docling/bin/activate
    nohup python3 "$B2_SCRIPT" --instance $i --total-instances $TOTAL_PROCS --workers 2 \
        > /tmp/b2_instance_${i}.log 2>&1 &
done
echo "Mac Mini: $MAC_MINI_PROCS processes started"

# MacBook Pro: instances 30-59
echo ""
echo "=== MACBOOK PRO - $MACBOOK_PROCS processes ==="
MACBOOK_START=$MAC_MINI_PROCS
ssh majpuzik@192.168.10.102 "
    cd /tmp
    for i in \$(seq $MACBOOK_START $((MACBOOK_START + MACBOOK_PROCS - 1))); do
        echo \"Starting instance \$i...\"
        nohup python3 $B2_SCRIPT --instance \$i --total-instances $TOTAL_PROCS --workers 2 \
            > /tmp/b2_instance_\${i}.log 2>&1 &
    done
    echo 'MacBook: $MACBOOK_PROCS processes started'
"

# DGX: instances 60-89
echo ""
echo "=== DGX - $DGX_PROCS processes ==="
DGX_START=$((MAC_MINI_PROCS + MACBOOK_PROCS))
ssh dgx "
    source ~/venv-docling/bin/activate
    for i in \$(seq $DGX_START $((DGX_START + DGX_PROCS - 1))); do
        echo \"Starting instance \$i...\"
        nohup python3 /home/puzik/document-pipeline/b2_docling_parallel.py \
            --instance \$i --total-instances $TOTAL_PROCS --workers 2 \
            > /tmp/b2_instance_\${i}.log 2>&1 &
    done
    echo 'DGX: $DGX_PROCS processes started'
"

# Dell: instances 90-119
echo ""
echo "=== DELL (Tailscale) - $DELL_PROCS processes ==="
DELL_START=$((MAC_MINI_PROCS + MACBOOK_PROCS + DGX_PROCS))
ssh maj@100.77.108.70 "
    source ~/venv-docling/bin/activate
    for i in \$(seq $DELL_START $((DELL_START + DELL_PROCS - 1))); do
        echo \"Starting instance \$i...\"
        nohup python3 /home/maj/document-pipeline/b2_docling_parallel.py \
            --instance \$i --total-instances $TOTAL_PROCS --workers 2 \
            > /tmp/b2_instance_\${i}.log 2>&1 &
    done
    echo 'Dell: $DELL_PROCS processes started'
"

echo ""
echo "=================================================="
echo "  ALL $TOTAL_PROCS INSTANCES LAUNCHED!"
echo "=================================================="
echo "Monitor: python3 $SCRIPT_DIR/monitor_pipeline.py"
