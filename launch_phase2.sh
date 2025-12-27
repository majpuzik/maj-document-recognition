#!/bin/bash
#
# Launch Phase 2: LLM Hierarchical Processing
# ============================================
# Launches AIVoter hierarchical processing for failed Phase 1 documents.
# Uses: czech-finance-speed (7.6B) → qwen2.5:14b → qwen2.5:32b
#
# Runs on Mac Mini + MacBook (NOT DGX - to keep GPU free for other tasks)
#
# Distribution:
#   - Mac Mini M4:  3 instances
#   - MacBook Pro:  5 instances
#
# Usage:
#   ./launch_phase2.sh mac_mini    # Launch Mac Mini instances
#   ./launch_phase2.sh macbook     # Launch MacBook instances
#   ./launch_phase2.sh all         # Launch for current machine
#   ./launch_phase2.sh status      # Check status
#   ./launch_phase2.sh stop        # Stop all instances
#

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACTOR_DIR="$SCRIPT_DIR/email_extractor"
PHASE2_SCRIPT="$EXTRACTOR_DIR/phase2_hierarchical.py"

# Input file (failed from Phase 1)
INPUT_FILE="$SCRIPT_DIR/phase1_output/phase2_to_process.jsonl"

# Output directory
OUTPUT_DIR="$SCRIPT_DIR/phase1_output"

# PID file directory
PID_DIR="$OUTPUT_DIR/pids_phase2"

# Log directory
LOG_DIR="$OUTPUT_DIR/logs_phase2"

# ============================================================================
# MACHINE CONFIGURATIONS
# ============================================================================

get_machine_config() {
    local machine=$1

    case $machine in
        mac_mini)
            # 3 instances, Ollama on localhost
            echo "3 800 /Users/m.a.j.puzik/.venvs/docling"
            ;;
        macbook)
            # 5 instances, Ollama on localhost
            echo "5 500 "
            ;;
        *)
            echo ""
            ;;
    esac
}

# ============================================================================
# FUNCTIONS
# ============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
    exit 1
}

detect_machine() {
    local hostname=$(hostname)

    if [[ "$hostname" == *"MacBook"* ]] || [[ "$hostname" == *"macbook"* ]]; then
        echo "macbook"
    else
        echo "mac_mini"
    fi
}

get_python() {
    local venv=$1

    if [[ -n "$venv" && -f "$venv/bin/python" ]]; then
        echo "$venv/bin/python"
    else
        echo "python3"
    fi
}

count_input() {
    if [[ -f "$INPUT_FILE" ]]; then
        wc -l < "$INPUT_FILE" | tr -d ' '
    else
        echo "0"
    fi
}

launch_instances() {
    local machine=$1

    # Check input file
    if [[ ! -f "$INPUT_FILE" ]]; then
        error "Input file not found: $INPUT_FILE"
    fi

    local total_items=$(count_input)
    if [[ "$total_items" -eq 0 ]]; then
        error "Input file is empty"
    fi

    log "Total items to process: $total_items"

    # Get config
    local config=$(get_machine_config $machine)
    if [[ -z "$config" ]]; then
        error "Unknown machine: $machine (Phase 2 only runs on mac_mini or macbook)"
    fi

    # Parse config
    local num_instances=$(echo $config | awk '{print $1}')
    local per_instance=$(echo $config | awk '{print $2}')
    local venv=$(echo $config | awk '{print $3}')

    local python=$(get_python "$venv")

    log "Launching $num_instances instances for $machine"
    log "Items per instance: ~$per_instance"
    log "Python: $python"

    # Create directories
    mkdir -p "$PID_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$OUTPUT_DIR/phase2_results"

    local start=0
    for ((i=0; i<num_instances; i++)); do
        local limit=$per_instance

        # Adjust limit for remaining items
        local remaining=$((total_items - start))
        if [[ $remaining -lt $limit ]]; then
            limit=$remaining
        fi

        if [[ $limit -le 0 ]]; then
            log "No more items to process, stopping at instance $i"
            break
        fi

        local instance_id="${machine}_phase2_${i}"
        local log_file="$LOG_DIR/${instance_id}.log"
        local pid_file="$PID_DIR/${instance_id}.pid"

        log "Starting instance $instance_id: start=$start, limit=$limit"

        # Launch in background
        nohup $python "$PHASE2_SCRIPT" \
            --start $start \
            --limit $limit \
            > "$log_file" 2>&1 &

        local pid=$!
        echo $pid > "$pid_file"

        log "  PID: $pid"

        start=$((start + limit))

        # Small delay between launches (let Ollama warm up)
        sleep 3
    done

    log "All instances launched for $machine"
}

stop_instances() {
    local machine=${1:-"all"}

    log "Stopping Phase 2 instances for: $machine"

    if [[ "$machine" == "all" ]]; then
        for pid_file in "$PID_DIR"/*.pid; do
            if [[ -f "$pid_file" ]]; then
                local pid=$(cat "$pid_file")
                if ps -p $pid > /dev/null 2>&1; then
                    log "Killing PID $pid"
                    kill $pid 2>/dev/null || true
                fi
                rm -f "$pid_file"
            fi
        done
    else
        for pid_file in "$PID_DIR"/${machine}_phase2_*.pid; do
            if [[ -f "$pid_file" ]]; then
                local pid=$(cat "$pid_file")
                if ps -p $pid > /dev/null 2>&1; then
                    log "Killing PID $pid"
                    kill $pid 2>/dev/null || true
                fi
                rm -f "$pid_file"
            fi
        done
    fi

    log "Instances stopped"
}

show_status() {
    log "Phase 2 Status"
    echo "=============================================="

    local total_items=$(count_input)
    echo "Input items: $total_items"
    echo ""

    local total_running=0

    for machine in mac_mini macbook; do
        echo "$machine:"
        echo "----------------------------------------------"

        local machine_running=0

        for pid_file in "$PID_DIR"/${machine}_phase2_*.pid; do
            if [[ -f "$pid_file" ]]; then
                local instance=$(basename "$pid_file" .pid)
                local pid=$(cat "$pid_file")

                if ps -p $pid > /dev/null 2>&1; then
                    echo "  $instance: RUNNING (PID $pid)"
                    machine_running=$((machine_running + 1))
                    total_running=$((total_running + 1))
                else
                    echo "  $instance: STOPPED"
                fi
            fi
        done

        if [[ $machine_running -eq 0 ]]; then
            echo "  No running instances"
        fi
        echo ""
    done

    echo "=============================================="
    echo "Total running: $total_running"

    # Check results
    if [[ -d "$OUTPUT_DIR/phase2_results" ]]; then
        local results_count=$(ls -1 "$OUTPUT_DIR/phase2_results"/*.json 2>/dev/null | wc -l | tr -d ' ')
        echo "Results: $results_count"
    fi

    # Check failed
    if [[ -f "$OUTPUT_DIR/phase2_failed.jsonl" ]]; then
        local failed_count=$(wc -l < "$OUTPUT_DIR/phase2_failed.jsonl" | tr -d ' ')
        echo "Failed: $failed_count"
    fi

    # Check escalated to 32B
    local escalated=$(grep -l "escalated_to_32b.*true" "$OUTPUT_DIR/phase2_results"/*.json 2>/dev/null | wc -l | tr -d ' ')
    echo "Escalated to 32B: $escalated"
}

check_ollama() {
    log "Checking Ollama models..."

    if ! command -v ollama &> /dev/null; then
        error "Ollama not found. Please install it first."
    fi

    local models_needed=("czech-finance-speed" "qwen2.5:14b" "qwen2.5:32b")

    for model in "${models_needed[@]}"; do
        if ollama list | grep -q "$model"; then
            log "  ✓ $model"
        else
            log "  ✗ $model NOT FOUND - pulling..."
            ollama pull "$model"
        fi
    done
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    local command=${1:-"status"}
    shift || true

    case $command in
        mac_mini|macbook)
            check_ollama
            launch_instances "$command"
            ;;

        all)
            check_ollama
            local machine=$(detect_machine)
            log "Detected machine: $machine"
            launch_instances "$machine"
            ;;

        stop)
            stop_instances "${1:-all}"
            ;;

        status)
            show_status
            ;;

        check)
            check_ollama
            ;;

        help|--help|-h)
            echo "Usage: $0 <command>"
            echo ""
            echo "Commands:"
            echo "  mac_mini   Launch Mac Mini instances (3 instances)"
            echo "  macbook    Launch MacBook instances (5 instances)"
            echo "  all        Launch for current machine"
            echo "  stop       Stop all instances"
            echo "  status     Show status"
            echo "  check      Check Ollama models"
            ;;

        *)
            error "Unknown command: $command. Use --help for usage."
            ;;
    esac
}

main "$@"
