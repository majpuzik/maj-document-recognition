#!/bin/bash
#
# Parallel Email Scanner Launcher
# ================================
# Launches 4 parallel instances to process 125,118 emails from Thunderbird INBOX
#
# Author: Claude Code
# Date: 2025-12-04
#

# Configuration
MBOX_PATH="$HOME/Library/Thunderbird/Profiles/1oli4gwg.default-esr/ImapMail/127.0.0.1/INBOX"
OUTPUT_DIR="$HOME/maj-document-recognition/parallel_scan_output"
TOTAL_EMAILS=125118
NUM_INSTANCES=4

# Calculate email ranges
EMAILS_PER_INSTANCE=$((TOTAL_EMAILS / NUM_INSTANCES))

echo "=========================================="
echo "🚀 PARALLEL EMAIL SCANNER"
echo "=========================================="
echo "Total emails: $TOTAL_EMAILS"
echo "Instances: $NUM_INSTANCES"
echo "Emails per instance: ~$EMAILS_PER_INSTANCE"
echo "Mbox: $MBOX_PATH"
echo "Output: $OUTPUT_DIR"
echo "=========================================="
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Memory check
echo "💾 Checking available memory..."
vm_stat | head -5
echo ""

# Function to monitor memory usage
monitor_memory() {
    while true; do
        sleep 30

        # Get system memory
        SYSTEM_MEMORY=$(vm_stat | perl -ne '/free:(\d+)/ and printf "%.1f", $1/256/1024')

        echo "$(date '+%H:%M:%S') | System Free Memory: ${SYSTEM_MEMORY}GB"

        # Check if memory is low (< 10GB)
        if (( $(echo "$SYSTEM_MEMORY < 10.0" | bc -l) )); then
            echo "⚠️  WARNING: Low memory! Free: ${SYSTEM_MEMORY}GB"
        fi
    done
}

# Start memory monitor in background
monitor_memory > "$OUTPUT_DIR/memory_monitor.log" 2>&1 &
MONITOR_PID=$!

echo "📊 Memory monitor started (PID: $MONITOR_PID)"
echo ""

# Launch parallel instances
PIDS=()

for i in {0..3}; do
    START=$((i * EMAILS_PER_INSTANCE))

    if [ $i -eq 3 ]; then
        # Last instance processes remaining emails
        END=$TOTAL_EMAILS
    else
        END=$(((i + 1) * EMAILS_PER_INSTANCE))
    fi

    LOG_FILE="$OUTPUT_DIR/instance_${i}.log"

    echo "🚀 Launching Instance $i:"
    echo "   Range: emails $START - $END"
    echo "   Log: $LOG_FILE"

    python3 "$HOME/maj-document-recognition/production_scan_parallel.py" \
        --mbox-path "$MBOX_PATH" \
        --output-dir "$OUTPUT_DIR" \
        --start-email $START \
        --end-email $END \
        --instance-id $i \
        > "$LOG_FILE" 2>&1 &

    PIDS[$i]=$!
    echo "   PID: ${PIDS[$i]}"
    echo ""

    # Stagger launches by 5 seconds to avoid initial load spike
    sleep 5
done

echo "=========================================="
echo "✅ All instances launched!"
echo "=========================================="
echo ""
echo "Instance PIDs:"
for i in {0..3}; do
    echo "   Instance $i: ${PIDS[$i]}"
done
echo ""
echo "Memory monitor PID: $MONITOR_PID"
echo ""

# Function to check if all instances are done
check_instances() {
    local all_done=true
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            all_done=false
            break
        fi
    done
    echo $all_done
}

# Monitor progress
echo "📊 Monitoring progress..."
echo "   (Press Ctrl+C to stop monitoring, instances will continue)"
echo ""

LAST_PROGRESS=""

while [ "$(check_instances)" = "false" ]; do
    # Show progress from each instance
    PROGRESS=""

    for i in {0..3}; do
        LOG_FILE="$OUTPUT_DIR/instance_${i}.log"

        if [ -f "$LOG_FILE" ]; then
            # Get last progress line
            LAST_LINE=$(tail -5 "$LOG_FILE" | grep -E "Processing:|Complete|PHASE" | tail -1)

            if [ -n "$LAST_LINE" ]; then
                PROGRESS="${PROGRESS}Instance $i: ${LAST_LINE}\n"
            fi
        fi
    done

    # Only print if progress changed
    if [ "$PROGRESS" != "$LAST_PROGRESS" ]; then
        clear
        echo "=========================================="
        echo "⏳ PARALLEL SCAN IN PROGRESS"
        echo "=========================================="
        echo -e "$PROGRESS"
        echo "=========================================="
        echo ""

        # Show memory usage
        SYSTEM_MEMORY=$(vm_stat | perl -ne '/free:(\d+)/ and printf "%.1f", $1/256/1024')
        echo "💾 System Free Memory: ${SYSTEM_MEMORY}GB"
        echo ""

        LAST_PROGRESS="$PROGRESS"
    fi

    sleep 10
done

# Stop memory monitor
kill $MONITOR_PID 2>/dev/null

echo ""
echo "=========================================="
echo "✅ ALL INSTANCES COMPLETE!"
echo "=========================================="
echo ""

# Collect statistics from all instances
echo "📊 Collecting statistics..."
echo ""

TOTAL_EMAILS_SCANNED=0
TOTAL_PDFS=0
TOTAL_CLASSIFIED=0
TOTAL_EXTRACTED=0

for i in {0..3}; do
    RESULT_FILE="$OUTPUT_DIR/instance_${i}/instance_${i}_results.json"

    if [ -f "$RESULT_FILE" ]; then
        echo "Instance $i results:"

        # Extract key stats using python
        python3 << EOF
import json
with open('$RESULT_FILE', 'r') as f:
    data = json.load(f)
    stats = data['statistics']
    print(f"   Emails scanned: {stats['total_emails']}")
    print(f"   PDFs extracted: {stats['pdfs_extracted']}")
    print(f"   Documents classified: {stats['documents_classified']}")
    print(f"   Documents extracted: {stats['documents_extracted']}")
    print(f"   Perfect consensus: {stats['perfect_consensus']}")
    print("")
EOF
    fi
done

echo "=========================================="
echo "📁 Output directory: $OUTPUT_DIR"
echo ""
echo "Log files:"
for i in {0..3}; do
    echo "   Instance $i: $OUTPUT_DIR/instance_${i}.log"
done
echo ""
echo "Result files:"
for i in {0..3}; do
    echo "   Instance $i: $OUTPUT_DIR/instance_${i}/instance_${i}_results.json"
done
echo ""
echo "Memory monitor: $OUTPUT_DIR/memory_monitor.log"
echo "=========================================="
echo ""
echo "✅ Parallel scan complete!"
