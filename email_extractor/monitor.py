#!/usr/bin/env python3
"""
NAS5 Docker Apps Collection
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
Real-time Progress Monitor
==========================
Displays live progress of all processing instances.

Features:
- Multi-instance progress tracking
- Real-time CPU/RAM display
- Document type statistics
- Success/failure rates
- ETA calculation

┌─────────────────────────────────────────────────────────────────────┐
│ FÁZE 1: DOCLING                              [████████░░] 80%      │
│ ─────────────────────────────────────────────────────────────────── │
│ Mac Mini:  3,200/32,000  CPU: 72%  RAM: 65%    [████░] 10%         │
│ MacBook:   2,800/32,000  CPU: 68%  RAM: 58%    [███░░] 8.7%        │
│ DGX:       2,500/31,133  CPU: 45%  RAM: 44%    [███░░] 8.0%        │
│ ─────────────────────────────────────────────────────────────────── │
│ Úspěšné: 7,234  Selhané: 1,266  Celkem: 8,500                      │
│ Faktury: 234  Smlouvy: 45  Účtenky: 89  Jiné: 6866                 │
│ ETA: 2h 34m                                                         │
└─────────────────────────────────────────────────────────────────────┘

Author: Claude Code
Date: 2025-12-15
"""

import os
import sys
import json
import time
import curses
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import psutil
import argparse


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class InstanceStatus:
    """Status of a single processing instance"""
    instance_id: int
    machine: str
    processed: int
    total: int
    success: int
    failed: int
    cpu_percent: float
    ram_percent: float
    last_update: str
    is_running: bool = True
    by_type: Dict[str, int] = None

    @property
    def progress_percent(self) -> float:
        return (self.processed / max(1, self.total)) * 100

    @property
    def success_rate(self) -> float:
        return (self.success / max(1, self.processed)) * 100


@dataclass
class GlobalStats:
    """Global statistics across all instances"""
    total_emails: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    by_type: Dict[str, int] = None
    start_time: datetime = None
    instances: List[InstanceStatus] = None


# ============================================================================
# STATS COLLECTOR
# ============================================================================

class StatsCollector:
    """Collects statistics from all instances"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.results_dir = output_dir / "phase1_results"

    def collect(self) -> GlobalStats:
        """Collect stats from all instance files"""
        stats = GlobalStats(
            by_type={},
            instances=[]
        )

        # Read all instance stats files
        for stats_file in self.output_dir.glob("phase1_stats_*.json"):
            try:
                with open(stats_file) as f:
                    data = json.load(f)

                instance = InstanceStatus(
                    instance_id=data.get("instance_id", 0),
                    machine=self._detect_machine(data),
                    processed=data.get("processed", 0),
                    total=data.get("total", 0),
                    success=data.get("success", 0),
                    failed=data.get("failed", 0),
                    cpu_percent=0,  # Will be updated from status file
                    ram_percent=0,
                    last_update=data.get("end_time") or data.get("start_time", ""),
                    by_type=data.get("by_type", {})
                )

                # Check if running
                instance.is_running = data.get("end_time") is None

                stats.instances.append(instance)

                # Aggregate
                stats.total_emails += instance.total
                stats.processed += instance.processed
                stats.success += instance.success
                stats.failed += instance.failed

                # Merge by_type
                for doc_type, count in instance.by_type.items():
                    stats.by_type[doc_type] = stats.by_type.get(doc_type, 0) + count

                # Track start time
                if data.get("start_time"):
                    st = datetime.fromisoformat(data["start_time"].replace("Z", "+00:00"))
                    if stats.start_time is None or st < stats.start_time:
                        stats.start_time = st

            except Exception as e:
                continue

        # Read resource status from instance status files
        for status_file in self.output_dir.glob("instance_*.json"):
            try:
                with open(status_file) as f:
                    data = json.load(f)

                instance_id = data.get("instance_id")
                for inst in stats.instances:
                    if inst.instance_id == instance_id:
                        inst.cpu_percent = data.get("cpu_percent", 0)
                        inst.ram_percent = data.get("ram_percent", 0)
                        break
            except:
                continue

        return stats

    def _detect_machine(self, data: Dict) -> str:
        """Detect machine from data"""
        # Try to detect from venv path or other hints
        start_idx = data.get("start_idx", 0)
        end_idx = data.get("end_idx", 0)

        # Based on distribution plan
        if end_idx <= 32000:
            return "Mac Mini"
        elif end_idx <= 64000:
            return "MacBook"
        else:
            return "DGX"


# ============================================================================
# TERMINAL UI
# ============================================================================

class TerminalMonitor:
    """Terminal-based monitoring UI"""

    def __init__(self, output_dir: Path):
        self.collector = StatsCollector(output_dir)
        self.output_dir = output_dir

    def run_simple(self, interval: float = 2.0):
        """Simple non-curses monitoring"""
        print("\n" + "=" * 70)
        print("PHASE 1 MONITOR - Press Ctrl+C to stop")
        print("=" * 70)

        try:
            while True:
                stats = self.collector.collect()
                self._print_simple(stats)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nMonitor stopped")

    def _print_simple(self, stats: GlobalStats):
        """Print simple stats to terminal"""
        # Clear screen
        os.system('clear' if os.name == 'posix' else 'cls')

        print("\n" + "=" * 70)
        print("PHASE 1: DOCLING EXTRACTION")
        print("=" * 70)

        # Progress bar
        progress = (stats.processed / max(1, stats.total_emails)) * 100
        bar_len = 40
        filled = int(bar_len * progress / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\nProgress: [{bar}] {progress:.1f}%")

        # Global stats
        success_rate = (stats.success / max(1, stats.processed)) * 100
        print(f"\nTotal: {stats.total_emails:,}  Processed: {stats.processed:,}")
        print(f"Success: {stats.success:,} ({success_rate:.1f}%)  Failed: {stats.failed:,}")

        # ETA
        if stats.start_time and stats.processed > 0:
            elapsed = datetime.now() - stats.start_time.replace(tzinfo=None)
            rate = stats.processed / max(1, elapsed.total_seconds())
            remaining = (stats.total_emails - stats.processed) / max(0.1, rate)
            eta = timedelta(seconds=int(remaining))
            print(f"ETA: {eta}")

        # Instances
        print("\n" + "-" * 70)
        print("INSTANCES")
        print("-" * 70)

        for inst in sorted(stats.instances, key=lambda x: x.instance_id):
            bar_len = 20
            filled = int(bar_len * inst.progress_percent / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            status = "🟢" if inst.is_running else "⚪"

            print(f"{status} [{inst.instance_id:2d}] {inst.machine:10s}: "
                  f"{inst.processed:6,}/{inst.total:6,} [{bar}] {inst.progress_percent:5.1f}% "
                  f"| CPU:{inst.cpu_percent:3.0f}% RAM:{inst.ram_percent:3.0f}%")

        # Document types
        print("\n" + "-" * 70)
        print("DOCUMENT TYPES")
        print("-" * 70)

        if stats.by_type:
            sorted_types = sorted(stats.by_type.items(), key=lambda x: -x[1])
            for doc_type, count in sorted_types[:8]:
                pct = (count / max(1, stats.success)) * 100
                print(f"  {doc_type:20s}: {count:6,} ({pct:5.1f}%)")

        print("\n" + "=" * 70)
        print(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

    def run_curses(self, interval: float = 2.0):
        """Run with curses UI"""
        try:
            curses.wrapper(lambda stdscr: self._curses_main(stdscr, interval))
        except curses.error:
            # Fallback to simple mode if curses fails
            self.run_simple(interval)

    def _curses_main(self, stdscr, interval: float):
        """Main curses loop"""
        curses.curs_set(0)  # Hide cursor
        stdscr.timeout(int(interval * 1000))

        # Colors
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)

        while True:
            stats = self.collector.collect()
            self._draw_curses(stdscr, stats)

            # Wait for input or timeout
            key = stdscr.getch()
            if key == ord('q') or key == ord('Q'):
                break

    def _draw_curses(self, stdscr, stats: GlobalStats):
        """Draw curses UI"""
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Title
        title = "PHASE 1: DOCLING EXTRACTION"
        stdscr.addstr(0, (width - len(title)) // 2, title, curses.A_BOLD | curses.color_pair(4))

        # Progress bar
        progress = (stats.processed / max(1, stats.total_emails)) * 100
        bar_width = min(50, width - 20)
        filled = int(bar_width * progress / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        stdscr.addstr(2, 2, f"Progress: [{bar}] {progress:.1f}%")

        # Stats
        success_rate = (stats.success / max(1, stats.processed)) * 100
        stdscr.addstr(4, 2, f"Total: {stats.total_emails:,}  Processed: {stats.processed:,}")
        stdscr.addstr(5, 2, f"Success: {stats.success:,} ({success_rate:.1f}%)  Failed: {stats.failed:,}")

        # ETA
        if stats.start_time and stats.processed > 0:
            elapsed = datetime.now() - stats.start_time.replace(tzinfo=None)
            rate = stats.processed / max(1, elapsed.total_seconds())
            remaining = (stats.total_emails - stats.processed) / max(0.1, rate)
            eta = timedelta(seconds=int(remaining))
            stdscr.addstr(6, 2, f"ETA: {eta}")

        # Instances
        stdscr.addstr(8, 2, "─" * (width - 4))
        stdscr.addstr(9, 2, "INSTANCES", curses.A_BOLD)

        row = 10
        for inst in sorted(stats.instances, key=lambda x: x.instance_id):
            if row >= height - 5:
                break

            bar_len = 15
            filled = int(bar_len * inst.progress_percent / 100)
            bar = "█" * filled + "░" * (bar_len - filled)

            # Color based on status
            color = curses.color_pair(1) if inst.is_running else curses.color_pair(2)

            line = f"[{inst.instance_id:2d}] {inst.machine:8s}: {inst.processed:5,}/{inst.total:5,} [{bar}] {inst.progress_percent:5.1f}%"
            stdscr.addstr(row, 2, line, color)

            # Resource usage
            cpu_color = curses.color_pair(1) if inst.cpu_percent < 70 else curses.color_pair(2) if inst.cpu_percent < 85 else curses.color_pair(3)
            ram_color = curses.color_pair(1) if inst.ram_percent < 70 else curses.color_pair(2) if inst.ram_percent < 85 else curses.color_pair(3)

            stdscr.addstr(row, 60, f"CPU:", curses.A_DIM)
            stdscr.addstr(row, 64, f"{inst.cpu_percent:3.0f}%", cpu_color)
            stdscr.addstr(row, 70, f"RAM:", curses.A_DIM)
            stdscr.addstr(row, 74, f"{inst.ram_percent:3.0f}%", ram_color)

            row += 1

        # Document types
        row += 1
        stdscr.addstr(row, 2, "─" * (width - 4))
        row += 1
        stdscr.addstr(row, 2, "TYPES:", curses.A_BOLD)

        if stats.by_type:
            col = 10
            for doc_type, count in sorted(stats.by_type.items(), key=lambda x: -x[1])[:6]:
                text = f"{doc_type}: {count:,}"
                if col + len(text) < width - 2:
                    stdscr.addstr(row, col, text)
                    col += len(text) + 3

        # Footer
        stdscr.addstr(height - 2, 2, "─" * (width - 4))
        stdscr.addstr(height - 1, 2, f"Press 'q' to quit | Updated: {datetime.now().strftime('%H:%M:%S')}")

        stdscr.refresh()


# ============================================================================
# JSON REPORTER
# ============================================================================

class JSONReporter:
    """Outputs stats as JSON for external tools"""

    def __init__(self, output_dir: Path):
        self.collector = StatsCollector(output_dir)

    def report(self) -> Dict:
        """Generate JSON report"""
        stats = self.collector.collect()

        return {
            "timestamp": datetime.now().isoformat(),
            "phase": 1,
            "total_emails": stats.total_emails,
            "processed": stats.processed,
            "success": stats.success,
            "failed": stats.failed,
            "success_rate": (stats.success / max(1, stats.processed)) * 100,
            "progress_percent": (stats.processed / max(1, stats.total_emails)) * 100,
            "by_type": stats.by_type,
            "instances": [
                {
                    "id": inst.instance_id,
                    "machine": inst.machine,
                    "processed": inst.processed,
                    "total": inst.total,
                    "progress": inst.progress_percent,
                    "cpu": inst.cpu_percent,
                    "ram": inst.ram_percent,
                    "running": inst.is_running
                }
                for inst in (stats.instances or [])
            ]
        }


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Phase 1 Progress Monitor')
    parser.add_argument('--output-dir', type=str,
                        default='/Volumes/ACASIS/apps/maj-document-recognition/phase1_output',
                        help='Output directory to monitor')
    parser.add_argument('--interval', type=float, default=2.0,
                        help='Update interval in seconds')
    parser.add_argument('--json', action='store_true',
                        help='Output JSON instead of TUI')
    parser.add_argument('--simple', action='store_true',
                        help='Use simple output (no curses)')

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}")
        print("Creating directory...")
        output_dir.mkdir(parents=True, exist_ok=True)

    if args.json:
        reporter = JSONReporter(output_dir)
        print(json.dumps(reporter.report(), indent=2))
    else:
        monitor = TerminalMonitor(output_dir)
        if args.simple:
            monitor.run_simple(args.interval)
        else:
            monitor.run_curses(args.interval)


if __name__ == "__main__":
    main()
