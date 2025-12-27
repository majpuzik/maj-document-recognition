#!/bin/bash
#
# Distributed Thunderbird Email Extraction Launcher
# ==================================================
# Launches extraction instances across all available machines
#
# Configuration:
# - Mac Mini M4:  11 instances (0-10)
# - MacBook Pro:  13 instances (11-23)
# - DGX Spark:    17 instances (24-40)
# - Dell WS:      95 instances (41-135)
# Total: 136 instances for 27,784 emails (~204 emails/instance)
#

# Configuration
MBOX_PATH="/Volumes/ACASIS/LargeFiles/Alle E-Mails einschließlich Spam-Nachrichten und E-002.mbox"
OUTPUT_DIR="/Volumes/ACASIS/apps/maj-document-recognition/extraction_output"
SCRIPT_PATH="/Volumes/ACASIS/apps/maj-document-recognition/thunderbird_docling_extractor.py"
TOTAL_EMAILS=27784
EMAILS_PER_INSTANCE=204

# Machine configs
MACMINI_IP="localhost"
MACBOOK_IP="100.90.154.98"
MACBOOK_USER="majpuzik"
DGX_IP="100.96.204.120"
DGX_USER="puzik"
DELL_IP="100.77.108.70"
DELL_USER="maj"

# Instance ranges
MACMINI_START=0
MACMINI_END=10
MACBOOK_START=11
MACBOOK_END=23
DGX_START=24
DGX_END=40
DELL_START=41
DELL_END=135

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================================"
echo " DISTRIBUTED THUNDERBIRD EXTRACTION LAUNCHER"
echo "============================================================"
echo ""
echo "Configuration:"
echo "  Mbox: $MBOX_PATH"
echo "  Total emails: $TOTAL_EMAILS"
echo "  Emails/instance: $EMAILS_PER_INSTANCE"
echo "  Total instances: 136"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to calculate email range for instance
calc_range() {
    local instance=$1
    local start=$((instance * EMAILS_PER_INSTANCE))
    local end=$((start + EMAILS_PER_INSTANCE))
    if [ $end -gt $TOTAL_EMAILS ]; then
        end=$TOTAL_EMAILS
    fi
    echo "$start $end"
}

# Function to launch on remote machine
launch_remote() {
    local user=$1
    local host=$2
    local instance_start=$3
    local instance_end=$4
    local machine_name=$5

    echo -e "${YELLOW}Launching on $machine_name ($host)...${NC}"

    for i in $(seq $instance_start $instance_end); do
        range=($(calc_range $i))
        email_start=${range[0]}
        email_end=${range[1]}

        echo "  Instance $i: emails $email_start-$email_end"

        # SSH command to launch instance
        ssh -o ConnectTimeout=10 "$user@$host" "
            cd /tmp && \
            nohup python3 '$SCRIPT_PATH' \
                --mbox '$MBOX_PATH' \
                --output '$OUTPUT_DIR' \
                --start $email_start \
                --end $email_end \
                --instance $i \
                > extraction_instance_${i}.log 2>&1 &
        " &
    done

    echo -e "${GREEN}✓ $machine_name: $((instance_end - instance_start + 1)) instances launched${NC}"
}

# Function to launch locally
launch_local() {
    local instance_start=$1
    local instance_end=$2

    echo -e "${YELLOW}Launching on Mac Mini (local)...${NC}"

    for i in $(seq $instance_start $instance_end); do
        range=($(calc_range $i))
        email_start=${range[0]}
        email_end=${range[1]}

        echo "  Instance $i: emails $email_start-$email_end"

        nohup python3 "$SCRIPT_PATH" \
            --mbox "$MBOX_PATH" \
            --output "$OUTPUT_DIR" \
            --start $email_start \
            --end $email_end \
            --instance $i \
            > "$OUTPUT_DIR/extraction_instance_${i}.log" 2>&1 &
    done

    echo -e "${GREEN}✓ Mac Mini: $((instance_end - instance_start + 1)) instances launched${NC}"
}

# Launch based on argument
case "${1:-all}" in
    macmini)
        launch_local $MACMINI_START $MACMINI_END
        ;;
    macbook)
        launch_remote "$MACBOOK_USER" "$MACBOOK_IP" $MACBOOK_START $MACBOOK_END "MacBook Pro"
        ;;
    dgx)
        launch_remote "$DGX_USER" "$DGX_IP" $DGX_START $DGX_END "DGX Spark"
        ;;
    dell)
        launch_remote "$DELL_USER" "$DELL_IP" $DELL_START $DELL_END "Dell WS"
        ;;
    all)
        echo "Launching ALL instances across all machines..."
        echo ""
        launch_local $MACMINI_START $MACMINI_END
        sleep 2
        launch_remote "$MACBOOK_USER" "$MACBOOK_IP" $MACBOOK_START $MACBOOK_END "MacBook Pro"
        sleep 2
        launch_remote "$DGX_USER" "$DGX_IP" $DGX_START $DGX_END "DGX Spark"
        sleep 2
        launch_remote "$DELL_USER" "$DELL_IP" $DELL_START $DELL_END "Dell WS"
        ;;
    status)
        echo "Checking instance status..."
        echo ""
        echo "Local (Mac Mini):"
        ps aux | grep thunderbird_docling | grep -v grep | wc -l
        echo ""
        echo "MacBook:"
        ssh -o ConnectTimeout=5 "$MACBOOK_USER@$MACBOOK_IP" "ps aux | grep thunderbird_docling | grep -v grep | wc -l" 2>/dev/null || echo "Unreachable"
        echo ""
        echo "DGX:"
        ssh -o ConnectTimeout=5 "$DGX_USER@$DGX_IP" "ps aux | grep thunderbird_docling | grep -v grep | wc -l" 2>/dev/null || echo "Unreachable"
        echo ""
        echo "Dell WS:"
        ssh -o ConnectTimeout=5 "$DELL_USER@$DELL_IP" "ps aux | grep thunderbird_docling | grep -v grep | wc -l" 2>/dev/null || echo "Unreachable"
        ;;
    *)
        echo "Usage: $0 {all|macmini|macbook|dgx|dell|status}"
        exit 1
        ;;
esac

echo ""
echo "============================================================"
echo " Launch complete. Monitor with: $0 status"
echo "============================================================"
