#!/bin/bash
# Sync DGX scan results to ACASIS
# Run periodically while DGX scan is running

DGX_HOST="puzik@192.168.10.200"
DGX_PATH="/home/puzik/maj-document-recognition/production_scan_llm_v22/"
ACASIS_PATH="/Volumes/ACASIS/OneDrive_backup/DGX_Thunderbird_Scan/"

echo "=== DGX → ACASIS Sync $(date) ==="

# Check if ACASIS is mounted
if [ ! -d "/Volumes/ACASIS" ]; then
    echo "ERROR: ACASIS not mounted!"
    exit 1
fi

# Sync
rsync -avz --progress \
    "$DGX_HOST:$DGX_PATH" \
    "$ACASIS_PATH" \
    2>&1 | tail -20

echo ""
echo "=== Sync Complete ==="
echo "Total size: $(du -sh "$ACASIS_PATH" | cut -f1)"
