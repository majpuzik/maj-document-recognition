#!/bin/bash
# Launch B2 Docling on all machines in parallel
# Mac Mini: 10 instances
# MacBook: 15 instances
# DGX: 15 instances
# Total: 40 instances

set -e

SCRIPT_DIR="/home/puzik/document-pipeline"
SCRIPT="$SCRIPT_DIR/b2_docling_parallel.py"

# Copy script to DGX first
echo "=== Copying scripts to DGX ==="
scp /Volumes/ACASIS/apps/maj-document-recognition/document_pipeline/*.py dgx:$SCRIPT_DIR/
scp /Volumes/ACASIS/apps/maj-document-recognition/document_pipeline/*.sh dgx:$SCRIPT_DIR/

TOTAL_INSTANCES=40
INSTANCE=0

echo "=== Starting B2 Docling on all machines ==="
echo "Total instances: $TOTAL_INSTANCES"
echo ""

# Mac Mini M4: 10 instances (instance 0-9)
echo "=== Mac Mini M4: 10 instances ==="
for i in $(seq 0 9); do
    echo "Starting instance $i on Mac Mini..."
    nohup ~/.venvs/docling/bin/python $SCRIPT --instance $i --total-instances $TOTAL_INSTANCES --workers 2 \
        > /tmp/b2_instance_$i.log 2>&1 &
    echo "  PID: $!"
done

# MacBook Pro: 15 instances (instance 10-24)
echo ""
echo "=== MacBook Pro: 15 instances ==="
for i in $(seq 10 24); do
    echo "Starting instance $i on MacBook..."
    ssh majpuzik@192.168.10.102 "cd $SCRIPT_DIR && nohup python3 $SCRIPT --instance $i --total-instances $TOTAL_INSTANCES --workers 2 \
        > /tmp/b2_instance_$i.log 2>&1 &" 2>/dev/null &
    echo "  Started"
done

# DGX: 15 instances (instance 25-39)
echo ""
echo "=== DGX: 15 instances ==="
for i in $(seq 25 39); do
    echo "Starting instance $i on DGX..."
    ssh dgx "source /home/puzik/venv-docling/bin/activate && cd $SCRIPT_DIR && nohup python $SCRIPT --instance $i --total-instances $TOTAL_INSTANCES --workers 3 \
        > /tmp/b2_instance_$i.log 2>&1 &" 2>/dev/null &
    echo "  Started"
done

echo ""
echo "=== All instances started ==="
echo "Monitor with: ./monitor_b2.sh"
