#!/bin/bash
# B1: Copy all documents to DGX for processing
# Sources: OneDrive (MacBook), Dropbox (8TB), ACASIS scans

set -e

DGX_USER="puzik"
DGX_HOST="dgx"
DGX_BASE="/home/puzik/document-pipeline/input"

MACBOOK_USER="majpuzik"
MACBOOK_HOST="192.168.10.102"

LOG_FILE="/home/puzik/document-pipeline/logs/b1_copy_$(date +%Y%m%d_%H%M%S).log"

echo "=== B1: Document Copy to DGX ===" | tee -a $LOG_FILE
echo "Started: $(date)" | tee -a $LOG_FILE

# Create subdirectories on DGX
ssh $DGX_HOST "mkdir -p $DGX_BASE/{onedrive,dropbox,acasis}"

# 1. Copy OneDrive from MacBook
echo "" | tee -a $LOG_FILE
echo "=== 1. OneDrive from MacBook ===" | tee -a $LOG_FILE
echo "Source: $MACBOOK_USER@$MACBOOK_HOST:~/Library/CloudStorage/OneDrive-Osobní/" | tee -a $LOG_FILE
echo "Target: $DGX_HOST:$DGX_BASE/onedrive/" | tee -a $LOG_FILE

# Use rsync through DGX (MacBook -> DGX)
ssh $DGX_HOST "rsync -avz --progress --include='*.pdf' --include='*.PDF' --include='*/' --exclude='*' \
    $MACBOOK_USER@$MACBOOK_HOST:'/Users/majpuzik/Library/CloudStorage/OneDrive-Osobní/' \
    $DGX_BASE/onedrive/ 2>&1" | tee -a $LOG_FILE &

ONEDRIVE_PID=$!

# 2. Copy Dropbox (accessible via mount on DGX)
echo "" | tee -a $LOG_FILE
echo "=== 2. Dropbox from 8TB SSD ===" | tee -a $LOG_FILE
echo "Source: /home/puzik/mnt/8tb-ssd/Dropbox/" | tee -a $LOG_FILE
echo "Target: $DGX_BASE/dropbox/" | tee -a $LOG_FILE

ssh $DGX_HOST "rsync -avz --progress --include='*.pdf' --include='*.PDF' --include='*/' --exclude='*' \
    /home/puzik/mnt/8tb-ssd/Dropbox/ \
    $DGX_BASE/dropbox/ 2>&1" | tee -a $LOG_FILE &

DROPBOX_PID=$!

# 3. Copy ACASIS scans
echo "" | tee -a $LOG_FILE
echo "=== 3. ACASIS scans ===" | tee -a $LOG_FILE
echo "Source: /home/puzik/mnt/acasis/" | tee -a $LOG_FILE
echo "Target: $DGX_BASE/acasis/" | tee -a $LOG_FILE

ssh $DGX_HOST "rsync -avz --progress --include='*.pdf' --include='*.PDF' --include='*/' --exclude='*' \
    /home/puzik/mnt/acasis/bank_statements_metadata/../ \
    $DGX_BASE/acasis/ 2>&1" | tee -a $LOG_FILE &

ACASIS_PID=$!

# Wait for all copies
echo "" | tee -a $LOG_FILE
echo "Waiting for all copies to complete..." | tee -a $LOG_FILE
wait $ONEDRIVE_PID $DROPBOX_PID $ACASIS_PID

# Count results
echo "" | tee -a $LOG_FILE
echo "=== Copy Complete ===" | tee -a $LOG_FILE
ssh $DGX_HOST "echo 'OneDrive PDFs:' && find $DGX_BASE/onedrive -name '*.pdf' -o -name '*.PDF' | wc -l"
ssh $DGX_HOST "echo 'Dropbox PDFs:' && find $DGX_BASE/dropbox -name '*.pdf' -o -name '*.PDF' | wc -l"
ssh $DGX_HOST "echo 'ACASIS PDFs:' && find $DGX_BASE/acasis -name '*.pdf' -o -name '*.PDF' | wc -l"

echo "" | tee -a $LOG_FILE
echo "Finished: $(date)" | tee -a $LOG_FILE
