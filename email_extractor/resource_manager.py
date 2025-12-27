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
Resource Manager - CPU/RAM Throttling
======================================
Manages system resources and automatically throttles processing
when CPU/RAM exceed configured limits.

Features:
- Real-time CPU/RAM monitoring
- Auto-pause when limits exceeded
- Auto-resume when resources free
- Process priority management
- Multi-instance coordination

Author: Claude Code
Date: 2025-12-15
"""

import os
import sys
import time
import json
import signal
import psutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from threading import Thread, Event
import subprocess


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ResourceLimits:
    """Resource limits configuration"""
    max_cpu_percent: float = 85.0
    max_ram_percent: float = 85.0
    check_interval: float = 2.0  # seconds
    cooldown_time: float = 10.0  # seconds to wait when over limit
    recovery_threshold: float = 75.0  # resume when below this


@dataclass
class ResourceStatus:
    """Current resource status"""
    timestamp: str
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    cpu_cores: int
    is_throttled: bool = False
    throttle_reason: str = ""


# ============================================================================
# RESOURCE MANAGER
# ============================================================================

class ResourceManager:
    """
    Manages system resources and throttles processing when limits exceeded.

    Usage:
        manager = ResourceManager(limits)

        # Check before heavy operation
        if manager.can_proceed():
            do_heavy_work()
        else:
            manager.wait_for_resources()

        # Or use context manager
        with manager.throttled():
            do_heavy_work()
    """

    def __init__(
        self,
        limits: ResourceLimits = None,
        logger: logging.Logger = None,
        status_file: Path = None
    ):
        self.limits = limits or ResourceLimits()
        self.logger = logger or logging.getLogger(__name__)
        self.status_file = status_file

        # State
        self._throttled = False
        self._throttle_reason = ""
        self._stop_event = Event()
        self._monitor_thread = None

        # Statistics
        self.stats = {
            "total_throttle_time": 0,
            "throttle_count": 0,
            "max_cpu_seen": 0,
            "max_ram_seen": 0,
            "checks": 0
        }

    def start_monitoring(self):
        """Start background monitoring thread"""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_event.clear()
            self._monitor_thread = Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            self.logger.info("Resource monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Resource monitoring stopped")

    def get_status(self) -> ResourceStatus:
        """Get current resource status"""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()

        status = ResourceStatus(
            timestamp=datetime.now().isoformat(),
            cpu_percent=cpu,
            ram_percent=ram.percent,
            ram_used_gb=ram.used / (1024**3),
            ram_total_gb=ram.total / (1024**3),
            cpu_cores=psutil.cpu_count(),
            is_throttled=self._throttled,
            throttle_reason=self._throttle_reason
        )

        # Update max seen values
        self.stats["max_cpu_seen"] = max(self.stats["max_cpu_seen"], cpu)
        self.stats["max_ram_seen"] = max(self.stats["max_ram_seen"], ram.percent)
        self.stats["checks"] += 1

        return status

    def can_proceed(self) -> bool:
        """Check if processing can proceed based on resource limits"""
        status = self.get_status()

        # Check CPU
        if status.cpu_percent > self.limits.max_cpu_percent:
            self._throttled = True
            self._throttle_reason = f"CPU {status.cpu_percent:.0f}% > {self.limits.max_cpu_percent}%"
            return False

        # Check RAM
        if status.ram_percent > self.limits.max_ram_percent:
            self._throttled = True
            self._throttle_reason = f"RAM {status.ram_percent:.0f}% > {self.limits.max_ram_percent}%"
            return False

        # Resources OK
        if self._throttled:
            # Check if we're below recovery threshold
            if (status.cpu_percent < self.limits.recovery_threshold and
                status.ram_percent < self.limits.recovery_threshold):
                self._throttled = False
                self._throttle_reason = ""
                self.logger.info("Resources recovered, resuming")

        return not self._throttled

    def wait_for_resources(self, timeout: float = None) -> bool:
        """
        Wait until resources are available.

        Args:
            timeout: Max seconds to wait (None = wait forever)

        Returns:
            True if resources available, False if timeout
        """
        start_time = time.time()
        wait_start = time.time()

        while not self.can_proceed():
            elapsed = time.time() - start_time

            if timeout and elapsed > timeout:
                self.logger.warning(f"Timeout waiting for resources after {elapsed:.0f}s")
                return False

            # Log status periodically
            if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                status = self.get_status()
                self.logger.info(
                    f"Waiting for resources... CPU: {status.cpu_percent:.0f}%, "
                    f"RAM: {status.ram_percent:.0f}% ({elapsed:.0f}s)"
                )

            time.sleep(self.limits.cooldown_time)

        # Record throttle time
        throttle_time = time.time() - wait_start
        if throttle_time > 1:
            self.stats["total_throttle_time"] += throttle_time
            self.stats["throttle_count"] += 1
            self.logger.info(f"Throttled for {throttle_time:.1f}s")

        return True

    def _monitor_loop(self):
        """Background monitoring loop"""
        while not self._stop_event.is_set():
            status = self.get_status()

            # Save status to file if configured
            if self.status_file:
                try:
                    with open(self.status_file, 'w') as f:
                        json.dump(asdict(status), f, indent=2)
                except Exception as e:
                    self.logger.warning(f"Failed to write status file: {e}")

            # Check for critical levels
            if status.ram_percent > 95:
                self.logger.error(f"CRITICAL: RAM at {status.ram_percent:.0f}%!")

            if status.cpu_percent > 95:
                self.logger.warning(f"High CPU: {status.cpu_percent:.0f}%")

            self._stop_event.wait(self.limits.check_interval)

    def throttled(self):
        """Context manager for throttled operations"""
        return ThrottledContext(self)

    def get_stats(self) -> Dict:
        """Get resource manager statistics"""
        return {
            **self.stats,
            "current_status": asdict(self.get_status())
        }


class ThrottledContext:
    """Context manager for resource-aware operations"""

    def __init__(self, manager: ResourceManager):
        self.manager = manager

    def __enter__(self):
        self.manager.wait_for_resources()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


# ============================================================================
# PROCESS COORDINATOR
# ============================================================================

class ProcessCoordinator:
    """
    Coordinates multiple processing instances on a single machine.
    Uses a shared status file to communicate between instances.
    """

    def __init__(
        self,
        instance_id: int,
        coord_dir: Path,
        limits: ResourceLimits = None,
        logger: logging.Logger = None
    ):
        self.instance_id = instance_id
        self.coord_dir = coord_dir
        self.coord_dir.mkdir(parents=True, exist_ok=True)

        self.limits = limits or ResourceLimits()
        self.logger = logger or logging.getLogger(__name__)

        self.status_file = coord_dir / f"instance_{instance_id}.json"
        self.manager = ResourceManager(limits, logger, self.status_file)

    def register(self):
        """Register this instance"""
        self._write_status("running")
        self.logger.info(f"Instance {self.instance_id} registered")

    def unregister(self):
        """Unregister this instance"""
        self._write_status("stopped")
        self.logger.info(f"Instance {self.instance_id} unregistered")

    def _write_status(self, state: str):
        """Write instance status"""
        status = {
            "instance_id": self.instance_id,
            "state": state,
            "pid": os.getpid(),
            "timestamp": datetime.now().isoformat(),
            **asdict(self.manager.get_status())
        }

        with open(self.status_file, 'w') as f:
            json.dump(status, f, indent=2)

    def get_active_instances(self) -> List[Dict]:
        """Get all active instances"""
        instances = []

        for status_file in self.coord_dir.glob("instance_*.json"):
            try:
                with open(status_file) as f:
                    data = json.load(f)

                # Check if process is still running
                pid = data.get("pid")
                if pid and psutil.pid_exists(pid):
                    instances.append(data)
            except Exception:
                continue

        return instances

    def should_start_new(self) -> bool:
        """Check if new instance should start based on resources"""
        status = self.manager.get_status()

        # Don't start if resources are high
        if status.cpu_percent > self.limits.recovery_threshold:
            return False
        if status.ram_percent > self.limits.recovery_threshold:
            return False

        return True

    def wait_and_proceed(self, timeout: float = None) -> bool:
        """Wait for resources and permission to proceed"""
        return self.manager.wait_for_resources(timeout)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_system_info() -> Dict:
    """Get detailed system information"""
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    return {
        "cpu": {
            "cores": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True),
            "frequency_mhz": cpu_freq.current if cpu_freq else None,
            "percent": psutil.cpu_percent(interval=0.1)
        },
        "memory": {
            "total_gb": mem.total / (1024**3),
            "available_gb": mem.available / (1024**3),
            "used_gb": mem.used / (1024**3),
            "percent": mem.percent
        },
        "disk": {
            "total_gb": disk.total / (1024**3),
            "free_gb": disk.free / (1024**3),
            "percent": disk.percent
        },
        "timestamp": datetime.now().isoformat()
    }


def kill_zombie_processes(pattern: str = None):
    """Kill zombie or hung processes matching pattern"""
    killed = 0

    for proc in psutil.process_iter(['pid', 'name', 'status', 'cmdline']):
        try:
            if proc.status() == psutil.STATUS_ZOMBIE:
                proc.kill()
                killed += 1
                continue

            if pattern and proc.cmdline():
                cmdline = " ".join(proc.cmdline())
                if pattern in cmdline:
                    # Check if process is hung (no CPU for long time)
                    cpu = proc.cpu_percent(interval=1)
                    if cpu == 0:
                        proc.kill()
                        killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return killed


# ============================================================================
# CLI
# ============================================================================

def main():
    """Monitor resources from command line"""
    import argparse

    parser = argparse.ArgumentParser(description='Resource Manager CLI')
    parser.add_argument('--watch', action='store_true', help='Watch resources continuously')
    parser.add_argument('--interval', type=float, default=2.0, help='Check interval in seconds')
    parser.add_argument('--max-cpu', type=float, default=85.0, help='Max CPU percent')
    parser.add_argument('--max-ram', type=float, default=85.0, help='Max RAM percent')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    limits = ResourceLimits(
        max_cpu_percent=args.max_cpu,
        max_ram_percent=args.max_ram,
        check_interval=args.interval
    )

    manager = ResourceManager(limits)

    if args.watch:
        print("\nResource Monitor (Ctrl+C to stop)")
        print("=" * 60)

        try:
            while True:
                status = manager.get_status()
                can_proceed = manager.can_proceed()

                # Color coding
                cpu_color = "\033[92m" if status.cpu_percent < 70 else "\033[93m" if status.cpu_percent < 85 else "\033[91m"
                ram_color = "\033[92m" if status.ram_percent < 70 else "\033[93m" if status.ram_percent < 85 else "\033[91m"
                reset = "\033[0m"

                print(f"\r{status.timestamp} | "
                      f"CPU: {cpu_color}{status.cpu_percent:5.1f}%{reset} | "
                      f"RAM: {ram_color}{status.ram_percent:5.1f}%{reset} "
                      f"({status.ram_used_gb:.1f}/{status.ram_total_gb:.1f} GB) | "
                      f"{'THROTTLED' if status.is_throttled else 'OK':10s}",
                      end="", flush=True)

                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\nStopped")
    else:
        # One-shot status
        info = get_system_info()
        print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
