#!/bin/bash
# =============================================================================
# PARALLEL EMAIL EXTRACTION LAUNCHER
# =============================================================================
# Spouští paralelní extrakci emailů na Mac Mini a DGX
#
# Použití:
#   ./launch_parallel_extraction.sh              # Zobrazí plán
#   ./launch_parallel_extraction.sh --run        # Spustí všechny instance
#   ./launch_parallel_extraction.sh --run --local # Spustí jen lokální instance
#
# =============================================================================

set -e

# Configuration
EMAIL_DIR="/Volumes/ACASIS/parallel_scan_1124_1205/thunderbird-emails"
OUTPUT_DIR="/Volumes/ACASIS/parallel_scan_output_$(date +%Y%m%d_%H%M%S)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/parallel_email_extractor.py"

# Mac Mini config
MAC_MINI_VENV="$HOME/.venvs/docling"
MAC_MINI_INSTANCES=6  # 14 CPU * 85% / 2 = 5.95, zaokrouhleno na 6

# DGX config
DGX_HOST="dgx"
DGX_VENV="/home/puzik/mnt/dell-wd/venv-ml"
DGX_INSTANCES=8  # 20 CPU * 85% / 2 = 8.5, zaokrouhleno na 8
DGX_EMAIL_DIR="/home/puzik/mnt/acasis/parallel_scan_1124_1205/thunderbird-emails"
DGX_OUTPUT_DIR="/home/puzik/mnt/acasis/parallel_scan_output_$(date +%Y%m%d_%H%M%S)"
DGX_SCRIPT="/home/puzik/mnt/acasis/apps/maj-document-recognition/parallel_email_extractor.py"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "============================================================================="
echo "  PARALLEL EMAIL EXTRACTION LAUNCHER"
echo "============================================================================="
echo -e "${NC}"

# Count emails
echo -e "${YELLOW}Counting emails...${NC}"
TOTAL_EMAILS=$(find "$EMAIL_DIR" -mindepth 2 -maxdepth 2 -type d 2>/dev/null | wc -l | tr -d ' ')
echo -e "${GREEN}Total emails: $TOTAL_EMAILS${NC}"

# Calculate distribution
TOTAL_INSTANCES=$((MAC_MINI_INSTANCES + DGX_INSTANCES))
EMAILS_PER_INSTANCE=$((TOTAL_EMAILS / TOTAL_INSTANCES))

echo ""
echo -e "${BLUE}Distribution Plan:${NC}"
echo "-----------------------------------------------------------------------------"
echo -e "  ${GREEN}Mac Mini M4 Pro${NC}: $MAC_MINI_INSTANCES instances (14 CPU, 64GB RAM)"
echo -e "  ${GREEN}DGX (Dell WS)${NC}:   $DGX_INSTANCES instances (20 CPU, 120GB RAM)"
echo "-----------------------------------------------------------------------------"
echo "  Total instances: $TOTAL_INSTANCES"
echo "  Emails per instance: ~$EMAILS_PER_INSTANCE"
echo ""

# Show instance distribution
echo -e "${BLUE}Instance Distribution:${NC}"
echo "-----------------------------------------------------------------------------"

CURRENT_IDX=0
for i in $(seq 0 $((MAC_MINI_INSTANCES - 1))); do
    START=$CURRENT_IDX
    END=$((CURRENT_IDX + EMAILS_PER_INSTANCE))
    echo -e "  Instance $i  (Mac Mini):  $START - $END  ($EMAILS_PER_INSTANCE emails)"
    CURRENT_IDX=$END
done

for i in $(seq 0 $((DGX_INSTANCES - 1))); do
    INSTANCE_ID=$((MAC_MINI_INSTANCES + i))
    START=$CURRENT_IDX
    if [ $i -eq $((DGX_INSTANCES - 1)) ]; then
        END=$TOTAL_EMAILS
    else
        END=$((CURRENT_IDX + EMAILS_PER_INSTANCE))
    fi
    echo -e "  Instance $INSTANCE_ID  (DGX):       $START - $END  ($((END - START)) emails)"
    CURRENT_IDX=$END
done
echo "-----------------------------------------------------------------------------"

# Check for --run flag
if [[ "$1" != "--run" ]]; then
    echo ""
    echo -e "${YELLOW}Dry run mode. Use --run to start processing.${NC}"
    echo ""
    echo "Commands to run manually:"
    echo ""
    echo "# Mac Mini instances:"
    CURRENT_IDX=0
    for i in $(seq 0 $((MAC_MINI_INSTANCES - 1))); do
        START=$CURRENT_IDX
        END=$((CURRENT_IDX + EMAILS_PER_INSTANCE))
        echo "source $MAC_MINI_VENV/bin/activate && python $PYTHON_SCRIPT --email-dir '$EMAIL_DIR' --output-dir '$OUTPUT_DIR' --start $START --end $END --machine mac_mini &"
        CURRENT_IDX=$END
    done
    echo ""
    echo "# DGX instances:"
    for i in $(seq 0 $((DGX_INSTANCES - 1))); do
        START=$CURRENT_IDX
        if [ $i -eq $((DGX_INSTANCES - 1)) ]; then
            END=$TOTAL_EMAILS
        else
            END=$((CURRENT_IDX + EMAILS_PER_INSTANCE))
        fi
        echo "ssh $DGX_HOST \"source $DGX_VENV/bin/activate && python $DGX_SCRIPT --email-dir '$DGX_EMAIL_DIR' --output-dir '$DGX_OUTPUT_DIR' --start $START --end $END --machine dgx\" &"
        CURRENT_IDX=$END
    done
    exit 0
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"
echo -e "${GREEN}Output directory: $OUTPUT_DIR${NC}"

# Check if --local flag
LOCAL_ONLY=false
if [[ "$2" == "--local" ]]; then
    LOCAL_ONLY=true
    echo -e "${YELLOW}Running local instances only (Mac Mini)${NC}"
fi

# Start timestamp
START_TIME=$(date +%s)

echo ""
echo -e "${GREEN}Starting parallel extraction...${NC}"
echo ""

# PID array for tracking
PIDS=()

# Launch Mac Mini instances
echo -e "${BLUE}Launching Mac Mini instances...${NC}"
CURRENT_IDX=0
for i in $(seq 0 $((MAC_MINI_INSTANCES - 1))); do
    START=$CURRENT_IDX
    END=$((CURRENT_IDX + EMAILS_PER_INSTANCE))

    LOG_FILE="$OUTPUT_DIR/mac_mini_instance_${i}.log"

    echo "  Starting instance $i: emails $START-$END"

    (
        source "$MAC_MINI_VENV/bin/activate"
        python "$PYTHON_SCRIPT" \
            --email-dir "$EMAIL_DIR" \
            --output-dir "$OUTPUT_DIR" \
            --start $START \
            --end $END \
            --machine mac_mini \
            2>&1 | tee "$LOG_FILE"
    ) &

    PIDS+=($!)
    CURRENT_IDX=$END

    # Small delay between starts
    sleep 2
done

# Launch DGX instances (if not local only)
if [ "$LOCAL_ONLY" = false ]; then
    echo ""
    echo -e "${BLUE}Launching DGX instances...${NC}"

    for i in $(seq 0 $((DGX_INSTANCES - 1))); do
        INSTANCE_ID=$((MAC_MINI_INSTANCES + i))
        START=$CURRENT_IDX
        if [ $i -eq $((DGX_INSTANCES - 1)) ]; then
            END=$TOTAL_EMAILS
        else
            END=$((CURRENT_IDX + EMAILS_PER_INSTANCE))
        fi

        LOG_FILE="$OUTPUT_DIR/dgx_instance_${INSTANCE_ID}.log"

        echo "  Starting instance $INSTANCE_ID on DGX: emails $START-$END"

        ssh "$DGX_HOST" "
            source $DGX_VENV/bin/activate
            mkdir -p $DGX_OUTPUT_DIR
            python $DGX_SCRIPT \
                --email-dir '$DGX_EMAIL_DIR' \
                --output-dir '$DGX_OUTPUT_DIR' \
                --start $START \
                --end $END \
                --machine dgx
        " > "$LOG_FILE" 2>&1 &

        PIDS+=($!)
        CURRENT_IDX=$END

        sleep 2
    done
fi

echo ""
echo -e "${GREEN}All instances started. PIDs: ${PIDS[*]}${NC}"
echo ""
echo -e "${YELLOW}Waiting for completion...${NC}"
echo "Monitor progress with: tail -f $OUTPUT_DIR/*.log"
echo ""

# Wait for all processes
FAILED=0
for pid in "${PIDS[@]}"; do
    if ! wait $pid; then
        ((FAILED++))
    fi
done

# End timestamp
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${BLUE}=============================================================================${NC}"
echo -e "${GREEN}  EXTRACTION COMPLETE${NC}"
echo -e "${BLUE}=============================================================================${NC}"
echo "  Duration: $((DURATION / 60)) minutes $((DURATION % 60)) seconds"
echo "  Output: $OUTPUT_DIR"
echo "  Failed instances: $FAILED"
echo ""

# Merge results
echo -e "${YELLOW}Merging results...${NC}"
python3 << EOF
import json
from pathlib import Path
from datetime import datetime

output_dir = Path("$OUTPUT_DIR")
all_results = []
total_stats = {
    "total": 0,
    "processed": 0,
    "docling_success": 0,
    "docling_failed": 0,
    "ai_classified": 0,
    "ai_failed": 0,
    "errors": []
}

for result_file in output_dir.glob("*/results.json"):
    try:
        data = json.loads(result_file.read_text())
        all_results.extend(data.get("results", []))

        stats = data.get("statistics", {})
        for key in ["total", "processed", "docling_success", "docling_failed", "ai_classified", "ai_failed"]:
            total_stats[key] += stats.get(key, 0)
        total_stats["errors"].extend(stats.get("errors", []))
    except Exception as e:
        print(f"Error reading {result_file}: {e}")

# Save merged results
merged_file = output_dir / "merged_results.json"
merged_data = {
    "merge_date": datetime.now().isoformat(),
    "total_results": len(all_results),
    "statistics": total_stats,
    "results": all_results
}

with open(merged_file, 'w', encoding='utf-8') as f:
    json.dump(merged_data, f, indent=2, ensure_ascii=False, default=str)

print(f"Merged {len(all_results)} results to {merged_file}")
print(f"Statistics:")
print(f"  Total: {total_stats['total']}")
print(f"  Processed: {total_stats['processed']}")
print(f"  Docling success: {total_stats['docling_success']}")
print(f"  Docling failed: {total_stats['docling_failed']}")
print(f"  AI classified: {total_stats['ai_classified']}")
print(f"  AI failed: {total_stats['ai_failed']}")
print(f"  Errors: {len(total_stats['errors'])}")

# Save all errors
if total_stats["errors"]:
    errors_file = output_dir / "all_errors.json"
    with open(errors_file, 'w', encoding='utf-8') as f:
        json.dump(total_stats["errors"], f, indent=2, ensure_ascii=False)
    print(f"Errors saved to {errors_file}")
EOF

echo ""
echo -e "${GREEN}Ready for Phase 3: Import to Paperless${NC}"
echo "Run: python $SCRIPT_DIR/import_to_paperless.py --input $OUTPUT_DIR/merged_results.json"
