#!/bin/bash
# Production Scan Monitor - Real-time Statistics
# Monitors production_scan_10k.log and displays live stats

LOG_FILE="$HOME/maj-document-recognition/production_scan_10k.log"
REFRESH_INTERVAL=5  # seconds

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Function to extract stats from log
get_stats() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "Log file not found: $LOG_FILE"
        return 1
    fi

    # Email stats
    TOTAL_EMAILS=$(grep "Total emails:" "$LOG_FILE" | tail -1 | grep -o '[0-9]*' | head -1)
    EMAILS_WITH_PDFS=$(grep "Emails with PDFs:" "$LOG_FILE" | tail -1 | grep -o '[0-9]*' | head -1)
    PDFS_EXTRACTED=$(grep "Extracted.*PDF files" "$LOG_FILE" | tail -1 | grep -o '[0-9]*' | head -1)

    # Processing stats
    CURRENT_PDF=$(grep "^\[.*Processing:" "$LOG_FILE" | tail -1 | grep -o '^\[[0-9]*' | tr -d '[')
    TOTAL_PDFS=$(grep "^\[.*Processing:" "$LOG_FILE" | tail -1 | grep -o '/[0-9]*\]' | tr -d '/]')
    CURRENT_FILE=$(grep "^\[.*Processing:" "$LOG_FILE" | tail -1 | sed 's/.*Processing: //')

    # Classification stats
    INVOICES=$(grep -c "Type: invoice" "$LOG_FILE")
    RECEIPTS=$(grep -c "Type: receipt" "$LOG_FILE")
    BANK_STATEMENTS=$(grep -c "Type: bank_statement" "$LOG_FILE")
    UNKNOWN=$(grep -c "Type: unknown" "$LOG_FILE")
    FAILED=$(grep -c "❌ Failed:" "$LOG_FILE")

    # AI Consensus stats
    PERFECT_CONSENSUS=$(grep -c "Strength: 100%" "$LOG_FILE")
    PARTIAL_CONSENSUS=$(grep "Strength:" "$LOG_FILE" | grep -v "100%" | wc -l | tr -d ' ')

    # Items extracted
    TOTAL_ITEMS=$(grep "Items:" "$LOG_FILE" | grep -o '[0-9]*' | awk '{s+=$1} END {print s}')

    # Success rate
    if [ -n "$TOTAL_PDFS" ] && [ "$TOTAL_PDFS" -gt 0 ]; then
        PROCESSED=$((INVOICES + RECEIPTS + BANK_STATEMENTS + UNKNOWN + FAILED))
        SUCCESS_RATE=$((100 * (INVOICES + RECEIPTS + BANK_STATEMENTS) / TOTAL_PDFS))
    else
        PROCESSED=0
        SUCCESS_RATE=0
    fi

    # Average processing time
    AVG_TIME=$(grep "Time:" "$LOG_FILE" | grep -o '[0-9.]*s' | tr -d 's' | awk '{s+=$1; c++} END {if(c>0) printf "%.1f", s/c; else print "0"}')
}

# Main monitoring loop
clear
echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║     PRODUCTION EMAIL SCANNER V2 - REAL-TIME MONITOR          ║${NC}"
echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

while true; do
    get_stats

    # Clear previous stats (keep header)
    tput cup 4 0
    tput ed

    echo -e "${BOLD}${BLUE}📧 EMAIL SCANNING${NC}"
    echo -e "   Total emails scanned:     ${GREEN}${TOTAL_EMAILS:-0}${NC}"
    echo -e "   Emails with PDFs:         ${GREEN}${EMAILS_WITH_PDFS:-0}${NC}"
    echo -e "   PDFs extracted:           ${GREEN}${PDFS_EXTRACTED:-0}${NC}"
    echo ""

    echo -e "${BOLD}${BLUE}🔍 PDF PROCESSING${NC}"
    if [ -n "$CURRENT_PDF" ] && [ -n "$TOTAL_PDFS" ]; then
        PROGRESS=$((100 * CURRENT_PDF / TOTAL_PDFS))
        echo -e "   Progress:                 ${YELLOW}${CURRENT_PDF}/${TOTAL_PDFS}${NC} (${PROGRESS}%)"
        echo -e "   Current file:             ${CYAN}${CURRENT_FILE:0:50}${NC}"
    else
        echo -e "   Progress:                 ${YELLOW}Waiting...${NC}"
    fi
    echo -e "   Success rate:             ${GREEN}${SUCCESS_RATE}%${NC}"
    echo -e "   Avg processing time:      ${GREEN}${AVG_TIME}s${NC}"
    echo ""

    echo -e "${BOLD}${BLUE}📋 DOCUMENT CLASSIFICATION${NC}"
    echo -e "   Invoices:                 ${GREEN}${INVOICES:-0}${NC}"
    echo -e "   Receipts:                 ${GREEN}${RECEIPTS:-0}${NC}"
    echo -e "   Bank statements:          ${GREEN}${BANK_STATEMENTS:-0}${NC}"
    echo -e "   Unknown/Other:            ${YELLOW}${UNKNOWN:-0}${NC}"
    echo -e "   Failed:                   ${RED}${FAILED:-0}${NC}"
    echo ""

    echo -e "${BOLD}${BLUE}🗳️  AI CONSENSUS (2 Ollama Models)${NC}"
    echo -e "   Perfect consensus (100%): ${GREEN}${PERFECT_CONSENSUS:-0}${NC}"
    echo -e "   Partial consensus:        ${YELLOW}${PARTIAL_CONSENSUS:-0}${NC}"
    echo ""

    echo -e "${BOLD}${BLUE}📊 DATA EXTRACTION${NC}"
    echo -e "   Total items extracted:    ${GREEN}${TOTAL_ITEMS:-0}${NC}"
    echo ""

    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "Refreshing every ${REFRESH_INTERVAL}s... Press Ctrl+C to stop"
    echo -e "Log file: ${LOG_FILE}"

    sleep $REFRESH_INTERVAL
done
