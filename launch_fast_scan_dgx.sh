#!/bin/bash
# Launch FAST parallel email scanning on DGX (no LLM = 10-20x faster)
# Splits 125,118 emails into 4 chunks for parallel processing

MBOX_PATH="$HOME/thunderbird_INBOX"
OUTPUT_DIR="$HOME/maj-document-recognition/production_scan_output_fast"
TOTAL_EMAILS=125118

# Calculate chunk sizes
CHUNK_SIZE=$((TOTAL_EMAILS / 4))

echo "🚀 Launching FAST Parallel Email Scanner on DGX"
echo "================================================"
echo "Total emails: $TOTAL_EMAILS"
echo "Chunk size: $CHUNK_SIZE emails per instance"
echo "Output: $OUTPUT_DIR"
echo "Mode: FAST (no LLM calls = 10-20x faster)"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Launch 4 parallel instances
echo "📧 Instance 0: emails 0-$((CHUNK_SIZE-1))"
nohup python3 production_scan_fast.py \
    --mbox-path "$MBOX_PATH" \
    --output-dir "$OUTPUT_DIR" \
    --start-email 0 \
    --end-email $CHUNK_SIZE \
    --instance-id 0 \
    > "$OUTPUT_DIR/instance_0.log" 2>&1 &
echo "   PID: $!"

echo "📧 Instance 1: emails $CHUNK_SIZE-$((CHUNK_SIZE*2-1))"
nohup python3 production_scan_fast.py \
    --mbox-path "$MBOX_PATH" \
    --output-dir "$OUTPUT_DIR" \
    --start-email $CHUNK_SIZE \
    --end-email $((CHUNK_SIZE*2)) \
    --instance-id 1 \
    > "$OUTPUT_DIR/instance_1.log" 2>&1 &
echo "   PID: $!"

echo "📧 Instance 2: emails $((CHUNK_SIZE*2))-$((CHUNK_SIZE*3-1))"
nohup python3 production_scan_fast.py \
    --mbox-path "$MBOX_PATH" \
    --output-dir "$OUTPUT_DIR" \
    --start-email $((CHUNK_SIZE*2)) \
    --end-email $((CHUNK_SIZE*3)) \
    --instance-id 2 \
    > "$OUTPUT_DIR/instance_2.log" 2>&1 &
echo "   PID: $!"

echo "📧 Instance 3: emails $((CHUNK_SIZE*3))-END"
nohup python3 production_scan_fast.py \
    --mbox-path "$MBOX_PATH" \
    --output-dir "$OUTPUT_DIR" \
    --start-email $((CHUNK_SIZE*3)) \
    --instance-id 3 \
    > "$OUTPUT_DIR/instance_3.log" 2>&1 &
echo "   PID: $!"

echo ""
echo "✅ All 4 instances launched!"
echo ""
echo "Monitor progress with:"
echo "  tail -f $OUTPUT_DIR/instance_*.log"
echo ""
echo "Check status with:"
echo "  ps aux | grep production_scan_fast"
