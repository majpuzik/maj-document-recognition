#!/bin/bash
#
# Launch Phase 1: Docling Extraction
# ===================================
# Launches multiple parallel instances of phase1_docling.py
# across Mac Mini M4, MacBook Pro, and DGX.
#
# Distribution:
#   - Mac Mini M4:  0 - 32,000  (10 instances, 3,200 each)
#   - MacBook Pro: 32,000 - 64,000 (15 instances, 2,133 each)
#   - DGX:        64,000 - 95,133 (15 instances, 2,076 each)
#
# Total: 40 instances, ~95,133 emails
#
# Usage:
#   ./launch_phase1.sh mac_mini    # Launch Mac Mini instances
#   ./launch_phase1.sh macbook     # Launch MacBook instances
#   ./launch_phase1.sh dgx         # Launch DGX instances
#   ./launch_phase1.sh status      # Check status
#   ./launch_phase1.sh stop        # Stop all instances
#

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACTOR_DIR="$SCRIPT_DIR/email_extractor"
PHASE1_SCRIPT="$EXTRACTOR_DIR/phase1_docling.py"

# Email directory
EMAIL_DIR="/Volumes/ACASIS/parallel_scan_1124_1205/thunderbird-emails"

# Output directory
OUTPUT_DIR="/Volumes/ACASIS/apps/maj-document-recognition/phase1_output"

# Total emails (approximate)
TOTAL_EMAILS=95133

# PID file directory
PID_DIR="$OUTPUT_DIR/pids"

# Log directory
LOG_DIR="$OUTPUT_DIR/logs"

# ============================================================================
# MACHINE CONFIGURATIONS
# ============================================================================

get_machine_config() {
    local machine=$1

    case $machine in
        mac_mini)
            echo "0 32000 10 /Users/m.a.j.puzik/.venvs/docling"
            ;;
        macbook)
            echo "32000 64000 15 "
            ;;
        dgx)
            echo "64000 95133 15 /home/puzik/venv-docling"
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
    local os=$(uname -s)

    if [[ "$hostname" == *"MacBook"* ]] || [[ "$hostname" == *"macbook"* ]]; then
        echo "macbook"
    elif [[ "$hostname" == *"dgx"* ]] || [[ "$hostname" == *"Dell"* ]] || [[ "$os" == "Linux" ]]; then
        echo "dgx"
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

launch_instances() {
    local machine=$1

    # Get config
    local config=$(get_machine_config $machine)
    if [[ -z "$config" ]]; then
        error "Unknown machine: $machine"
    fi

    # Parse config
    local start=$(echo $config | awk '{print $1}')
    local end=$(echo $config | awk '{print $2}')
    local num_instances=$(echo $config | awk '{print $3}')
    local venv=$(echo $config | awk '{print $4}')

    local python=$(get_python "$venv")

    # Calculate emails per instance
    local total=$((end - start))
    local per_instance=$((total / num_instances))

    log "Launching $num_instances instances for $machine"
    log "Range: $start - $end ($total emails)"
    log "Python: $python"

    # Create directories
    mkdir -p "$PID_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$OUTPUT_DIR/phase1_results"

    local instance_start=$start
    for ((i=0; i<num_instances; i++)); do
        local instance_end=$((instance_start + per_instance))

        # Last instance gets remainder
        if [[ $i -eq $((num_instances - 1)) ]]; then
            instance_end=$end
        fi

        local instance_id="${machine}_${i}"
        local log_file="$LOG_DIR/${instance_id}.log"
        local pid_file="$PID_DIR/${instance_id}.pid"

        log "Starting instance $instance_id: $instance_start - $instance_end"

        # Launch in background
        nohup $python "$PHASE1_SCRIPT" \
            --machine "$machine" \
            --instance $i \
            --start $instance_start \
            --end $instance_end \
            --email-dir "$EMAIL_DIR" \
            --output-dir "$OUTPUT_DIR" \
            > "$log_file" 2>&1 &

        local pid=$!
        echo $pid > "$pid_file"

        log "  PID: $pid"

        instance_start=$instance_end

        # Small delay between launches
        sleep 1
    done

    log "All $num_instances instances launched for $machine"
}

stop_instances() {
    local machine=${1:-"all"}

    log "Stopping instances for: $machine"

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
        for pid_file in "$PID_DIR"/${machine}_*.pid; do
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
    log "Phase 1 Status"
    echo "=============================================="

    local total_running=0

    for machine in mac_mini macbook dgx; do
        echo ""
        echo "$machine:"
        echo "----------------------------------------------"

        local machine_running=0

        for pid_file in "$PID_DIR"/${machine}_*.pid; do
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
    done

    echo ""
    echo "=============================================="
    echo "Total running: $total_running"

    # Check stats files
    if [[ -d "$OUTPUT_DIR" ]]; then
        local stats_count=$(ls -1 "$OUTPUT_DIR"/phase1_stats_*.json 2>/dev/null | wc -l || echo "0")
        local results_count=$(ls -1 "$OUTPUT_DIR/phase1_results"/*.json 2>/dev/null | wc -l || echo "0")

        echo "Stats files: $stats_count"
        echo "Results: $results_count"
    fi
}

run_monitor() {
    local machine=$(detect_machine)
    local config=$(get_machine_config $machine)
    local venv=$(echo $config | awk '{print $4}')
    local python=$(get_python "$venv")

    $python "$EXTRACTOR_DIR/monitor.py" --output-dir "$OUTPUT_DIR" "$@"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    local command=${1:-"status"}
    shift || true

    case $command in
        mac_mini|macbook|dgx)
            launch_instances "$command"
            ;;

        all)
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

        monitor)
            run_monitor "$@"
            ;;

        help|--help|-h)
            echo "Usage: $0 <command>"
            echo ""
            echo "Commands:"
            echo "  mac_mini   Launch Mac Mini instances (0-32000, 10 instances)"
            echo "  macbook    Launch MacBook instances (32000-64000, 15 instances)"
            echo "  dgx        Launch DGX instances (64000-95133, 15 instances)"
            echo "  all        Launch for current machine"
            echo "  stop       Stop all instances"
            echo "  status     Show status"
            echo "  monitor    Run progress monitor"
            ;;

        *)
            error "Unknown command: $command. Use --help for usage."
            ;;
    esac
}

main "$@"
