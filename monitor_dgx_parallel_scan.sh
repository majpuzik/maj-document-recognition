#!/bin/bash
#
# DGX Parallel Scan Monitor v2
# ============================
# Monitors all 4 parallel instances on DGX (production_scan_llm_v22)
#

clear

DGX_HOST="puzik@192.168.10.200"
SCAN_DIR="~/maj-document-recognition/production_scan_llm_v22"

echo "================================================================================"
echo "📊 DGX PARALLEL SCAN MONITOR v2"
echo "================================================================================"
echo ""

# Check if instances are running
RUNNING=$(ssh $DGX_HOST "ps aux | grep 'production_scan_parallel.py' | grep -v grep | wc -l" 2>/dev/null)
echo "🚀 Running instances: $RUNNING / 4"
echo ""

# Get email scan progress from logs
echo "================================================================================"
echo "📧 FÁZE 1: SKENOVÁNÍ EMAILŮ"
echo "================================================================================"
echo ""

TOTAL_SCANNED=0
for i in {0..3}; do
    EMAILS=$(ssh $DGX_HOST "grep 'Total emails scanned:' $SCAN_DIR/instance_${i}.log 2>/dev/null | tail -1 | awk '{print \$NF}'" 2>/dev/null)
    if [ -n "$EMAILS" ] && [ "$EMAILS" != "" ]; then
        TOTAL_SCANNED=$((TOTAL_SCANNED + EMAILS))
        echo "  Instance $i: $EMAILS emailů ✅"
    else
        echo "  Instance $i: probíhá..."
    fi
done

echo ""
echo "  ═══════════════════════════════════════"
echo "  📬 CELKEM PROSKENOVÁNO: $TOTAL_SCANNED / 125,121 emailů"
if [ $TOTAL_SCANNED -gt 0 ]; then
    PCT=$(echo "scale=1; $TOTAL_SCANNED * 100 / 125121" | bc 2>/dev/null || echo "?")
    echo "  📈 Progress emailů: ${PCT}%"
fi
echo ""

# Get PDF processing progress
echo "================================================================================"
echo "🔍 FÁZE 2: AI ZPRACOVÁNÍ PDF"
echo "================================================================================"
echo ""

TOTAL_PDFS=0
TOTAL_PROCESSED=0
TOTAL_TO_PROCESS=0

for i in {0..3}; do
    # Get current progress [X/Y]
    PROGRESS=$(ssh $DGX_HOST "grep -E '\[[0-9]+/[0-9]+\]' $SCAN_DIR/instance_${i}.log 2>/dev/null | tail -1" 2>/dev/null)

    # Count extracted PDFs
    PDF_COUNT=$(ssh $DGX_HOST "ls -1 $SCAN_DIR/instance_${i}/*.pdf 2>/dev/null | wc -l" 2>/dev/null)
    TOTAL_PDFS=$((TOTAL_PDFS + PDF_COUNT))

    if [ -n "$PROGRESS" ]; then
        # Extract X/Y from [X/Y]
        CURRENT=$(echo "$PROGRESS" | grep -oE '\[([0-9]+)/([0-9]+)\]' | sed 's/\[//;s/\]//' | cut -d'/' -f1)
        TOTAL=$(echo "$PROGRESS" | grep -oE '\[([0-9]+)/([0-9]+)\]' | sed 's/\[//;s/\]//' | cut -d'/' -f2)

        if [ -n "$CURRENT" ] && [ -n "$TOTAL" ]; then
            TOTAL_PROCESSED=$((TOTAL_PROCESSED + CURRENT))
            TOTAL_TO_PROCESS=$((TOTAL_TO_PROCESS + TOTAL))

            if [ "$CURRENT" -eq "$TOTAL" ]; then
                echo "  Instance $i: ✅ HOTOVO ($CURRENT/$TOTAL) | $PDF_COUNT PDF"
            else
                INST_PCT=$(echo "scale=0; $CURRENT * 100 / $TOTAL" | bc 2>/dev/null || echo "?")
                echo "  Instance $i: [$CURRENT/$TOTAL] ${INST_PCT}% | $PDF_COUNT PDF"
            fi
        fi
    else
        # Check if completed
        COMPLETED=$(ssh $DGX_HOST "grep 'COMPLETE' $SCAN_DIR/instance_${i}.log 2>/dev/null | tail -1" 2>/dev/null)
        if [ -n "$COMPLETED" ]; then
            echo "  Instance $i: ✅ HOTOVO | $PDF_COUNT PDF"
        else
            echo "  Instance $i: čeká... | $PDF_COUNT PDF"
        fi
    fi
done

echo ""
echo "  ═══════════════════════════════════════"
echo "  📄 CELKEM PDF NALEZENO: $TOTAL_PDFS"
echo "  🤖 AI ZPRACOVÁNO: $TOTAL_PROCESSED / $TOTAL_TO_PROCESS"
if [ $TOTAL_TO_PROCESS -gt 0 ]; then
    AI_PCT=$(echo "scale=1; $TOTAL_PROCESSED * 100 / $TOTAL_TO_PROCESS" | bc 2>/dev/null || echo "?")
    echo "  📈 Progress AI: ${AI_PCT}%"
fi
echo ""

# Get all attachments extraction progress (FÁZE 3)
echo "================================================================================"
echo "📎 FÁZE 3: EXTRAKCE VŠECH PŘÍLOH (Paperless-NGX style)"
echo "================================================================================"
echo ""

ALL_ATT_RUNNING=$(ssh $DGX_HOST "pgrep -f 'extract_all_attachments.py'" 2>/dev/null)
if [ -n "$ALL_ATT_RUNNING" ]; then
    echo "  Status: 🟢 BĚŽÍ (PID: $ALL_ATT_RUNNING)"
    PROGRESS_LINE=$(ssh $DGX_HOST "tail -1 $SCAN_DIR/all_attachments.log 2>/dev/null" 2>/dev/null)
    echo "  $PROGRESS_LINE"
else
    # Check if completed
    COMPLETED=$(ssh $DGX_HOST "grep 'EXTRACTION COMPLETE' $SCAN_DIR/all_attachments.log 2>/dev/null" 2>/dev/null)
    if [ -n "$COMPLETED" ]; then
        echo "  Status: ✅ HOTOVO"
        ssh $DGX_HOST "grep -E '^\s+\.' $SCAN_DIR/all_attachments.log 2>/dev/null | head -10" 2>/dev/null
        TOTAL_ATT=$(ssh $DGX_HOST "grep 'Total attachments extracted:' $SCAN_DIR/all_attachments.log 2>/dev/null | awk '{print \$NF}'" 2>/dev/null)
        echo ""
        echo "  📦 Celkem příloh: $TOTAL_ATT"
    else
        echo "  Status: ⏸️ Nespuštěno"
    fi
fi
echo ""

# Get disk usage
echo "================================================================================"
echo "💾 DISK USAGE"
echo "================================================================================"
echo ""
DISK_USAGE=$(ssh $DGX_HOST "du -sh $SCAN_DIR 2>/dev/null" 2>/dev/null | awk '{print $1}')
echo "  Scan folder: $DISK_USAGE"
ALL_ATT_SIZE=$(ssh $DGX_HOST "du -sh $SCAN_DIR/all_attachments 2>/dev/null" 2>/dev/null | awk '{print $1}')
echo "  All attachments: $ALL_ATT_SIZE"
echo ""

# System resources
echo "================================================================================"
echo "🖥️  SYSTEM RESOURCES (DGX)"
echo "================================================================================"
echo ""

# Memory
ssh $DGX_HOST "free -h | head -2" 2>/dev/null
echo ""

# Ollama status
OLLAMA_RUNNING=$(ssh $DGX_HOST "pgrep -x ollama" 2>/dev/null)
if [ -n "$OLLAMA_RUNNING" ]; then
    echo "  Ollama: ✅ běží (PID: $OLLAMA_RUNNING)"
else
    echo "  Ollama: ❌ neběží"
fi

# Python processes
echo ""
echo "  Python procesy:"
ssh $DGX_HOST "ps aux | grep 'production_scan_parallel.py' | grep -v grep | awk '{printf \"    PID %s: CPU %.1f%% MEM %.0f MB\n\", \$2, \$3, \$6/1024}'" 2>/dev/null

echo ""
echo "================================================================================"
echo "⏱️  Aktualizováno: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================================================"
echo ""
echo "Pro sledování: watch -n 30 ~/maj-document-recognition/monitor_dgx_parallel_scan.sh"
echo ""
