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
Advanced Resource Manager with GPU, Disk, and Network AI Discovery
===================================================================
Rozšířený resource manager s podporou:
- CPU/RAM monitoring s auto-throttling
- GPU monitoring (nvidia-smi pro CUDA, ioreg pro Apple Metal)
- Disk space monitoring
- Auto-pause s UI callback notifikací
- Dynamický výpočet možných instancí dle zatížení
- Network AI server discovery (Ollama instances)

Author: Claude Code
Date: 2025-12-16
"""

import os
import sys
import time
import json
import socket
import subprocess
import psutil
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict, field
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ResourceLimits:
    """Limity pro throttling"""
    max_cpu_percent: float = 85.0
    max_ram_percent: float = 85.0
    max_gpu_percent: float = 90.0
    min_disk_free_gb: float = 10.0
    check_interval: float = 2.0
    cooldown_time: float = 10.0
    recovery_threshold: float = 75.0


@dataclass
class GPUStatus:
    """Status GPU"""
    available: bool = False
    name: str = ""
    memory_used_mb: float = 0
    memory_total_mb: float = 0
    memory_percent: float = 0
    utilization_percent: float = 0
    temperature_c: float = 0
    gpu_type: str = ""  # "nvidia" or "apple_metal"


@dataclass
class DiskStatus:
    """Status disku"""
    path: str = "/"
    total_gb: float = 0
    used_gb: float = 0
    free_gb: float = 0
    percent: float = 0


@dataclass
class AIServer:
    """AI server v síti"""
    host: str = ""
    port: int = 11434
    name: str = ""
    is_reachable: bool = False
    models: List[str] = field(default_factory=list)
    gpu_status: Optional[GPUStatus] = None
    cpu_percent: float = 0
    ram_percent: float = 0
    last_check: str = ""
    enabled: bool = True  # Pro GUI checkbox


@dataclass
class FullResourceStatus:
    """Kompletní status všech zdrojů"""
    timestamp: str = ""
    hostname: str = ""

    # CPU/RAM
    cpu_percent: float = 0
    cpu_cores: int = 0
    ram_percent: float = 0
    ram_used_gb: float = 0
    ram_total_gb: float = 0

    # GPU
    gpu: Optional[GPUStatus] = None

    # Disk
    disks: List[DiskStatus] = field(default_factory=list)

    # Throttling
    is_throttled: bool = False
    throttle_reason: str = ""
    throttle_sources: List[str] = field(default_factory=list)

    # Instance calculation
    recommended_instances: int = 0
    max_safe_instances: int = 0


# ============================================================================
# GPU MONITORING
# ============================================================================

class GPUMonitor:
    """Monitor GPU - podporuje NVIDIA i Apple Metal"""

    def __init__(self):
        self.gpu_type = self._detect_gpu_type()

    def _detect_gpu_type(self) -> str:
        """Detekuj typ GPU"""
        # Check for NVIDIA
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return "nvidia"
        except:
            pass

        # Check for Apple Metal (macOS)
        if sys.platform == "darwin":
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType", "-json"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    if "SPDisplaysDataType" in data:
                        return "apple_metal"
            except:
                pass

        return "none"

    def get_status(self) -> GPUStatus:
        """Získej status GPU"""
        if self.gpu_type == "nvidia":
            return self._get_nvidia_status()
        elif self.gpu_type == "apple_metal":
            return self._get_apple_metal_status()
        else:
            return GPUStatus(available=False)

    def _get_nvidia_status(self) -> GPUStatus:
        """Status NVIDIA GPU pomocí nvidia-smi"""
        try:
            result = subprocess.run([
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits"
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 5:
                    mem_used = float(parts[1])
                    mem_total = float(parts[2])
                    return GPUStatus(
                        available=True,
                        name=parts[0],
                        memory_used_mb=mem_used,
                        memory_total_mb=mem_total,
                        memory_percent=(mem_used / mem_total * 100) if mem_total > 0 else 0,
                        utilization_percent=float(parts[3]),
                        temperature_c=float(parts[4]),
                        gpu_type="nvidia"
                    )
        except Exception as e:
            logging.warning(f"nvidia-smi error: {e}")

        return GPUStatus(available=False, gpu_type="nvidia")

    def _get_apple_metal_status(self) -> GPUStatus:
        """Status Apple Metal GPU pomocí ioreg"""
        try:
            # Get GPU name
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True, text=True, timeout=10
            )

            gpu_name = "Apple GPU"
            if result.returncode == 0:
                data = json.loads(result.stdout)
                displays = data.get("SPDisplaysDataType", [])
                if displays:
                    gpu_name = displays[0].get("sppci_model", "Apple GPU")

            # Get memory pressure using vm_stat
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True, timeout=5
            )

            # Estimate GPU memory from unified memory (Apple Silicon)
            mem = psutil.virtual_memory()
            # Apple GPU shares system memory - estimate 30-50% available for GPU
            estimated_gpu_mem = mem.total / (1024**2) * 0.4  # 40% of system RAM

            # Get GPU utilization via powermetrics (requires sudo) or estimate
            gpu_util = 0
            try:
                # Try Activity Monitor's GPU history
                result = subprocess.run(
                    ["ioreg", "-r", "-c", "IOAccelerator", "-d", "1"],
                    capture_output=True, text=True, timeout=5
                )
                if "PerformanceStatistics" in result.stdout:
                    # Parse utilization if available
                    import re
                    match = re.search(r'"Device Utilization %"\s*=\s*(\d+)', result.stdout)
                    if match:
                        gpu_util = int(match.group(1))
            except:
                pass

            return GPUStatus(
                available=True,
                name=gpu_name,
                memory_used_mb=mem.used / (1024**2) * 0.3,  # Estimate
                memory_total_mb=estimated_gpu_mem,
                memory_percent=mem.percent * 0.8,  # Rough correlation
                utilization_percent=gpu_util,
                temperature_c=0,  # Not easily available
                gpu_type="apple_metal"
            )

        except Exception as e:
            logging.warning(f"Apple Metal status error: {e}")

        return GPUStatus(available=False, gpu_type="apple_metal")


# ============================================================================
# NETWORK AI SERVER DISCOVERY
# ============================================================================

class AIServerDiscovery:
    """Automatické hledání AI serverů v síti"""

    # Known AI server configurations
    KNOWN_SERVERS = [
        {"host": "localhost", "port": 11434, "name": "Local Ollama"},
        {"host": "192.168.10.130", "port": 11434, "name": "DGX H100"},
        {"host": "192.168.10.131", "port": 11434, "name": "Mac Mini M4"},
        {"host": "192.168.10.132", "port": 11434, "name": "MacBook Pro M3"},
        {"host": "192.168.10.35", "port": 11434, "name": "NAS5"},
    ]

    def __init__(self, custom_servers: List[Dict] = None):
        self.servers: Dict[str, AIServer] = {}
        self.known_servers = self.KNOWN_SERVERS + (custom_servers or [])

    def discover(self, timeout: float = 2.0) -> List[AIServer]:
        """Objevuj AI servery v síti"""
        discovered = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(self._check_server, srv, timeout): srv
                for srv in self.known_servers
            }

            for future in as_completed(futures, timeout=timeout * 2):
                try:
                    server = future.result()
                    if server:
                        discovered.append(server)
                        self.servers[f"{server.host}:{server.port}"] = server
                except:
                    pass

        return discovered

    def _check_server(self, server_config: Dict, timeout: float) -> Optional[AIServer]:
        """Zkontroluj jeden server"""
        host = server_config["host"]
        port = server_config["port"]
        name = server_config.get("name", f"{host}:{port}")

        try:
            import requests

            # Check if Ollama is running
            resp = requests.get(
                f"http://{host}:{port}/api/tags",
                timeout=timeout
            )

            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]

                server = AIServer(
                    host=host,
                    port=port,
                    name=name,
                    is_reachable=True,
                    models=models,
                    last_check=datetime.now().isoformat(),
                    enabled=True
                )

                # Try to get system stats
                try:
                    if host in ["localhost", "127.0.0.1"]:
                        server.cpu_percent = psutil.cpu_percent(interval=0.1)
                        server.ram_percent = psutil.virtual_memory().percent
                except:
                    pass

                return server

        except Exception as e:
            logging.debug(f"Server {host}:{port} not reachable: {e}")

        return None

    def get_enabled_servers(self) -> List[AIServer]:
        """Vrať pouze povolené servery"""
        return [s for s in self.servers.values() if s.enabled and s.is_reachable]

    def set_server_enabled(self, host: str, port: int, enabled: bool):
        """Nastav zda je server povolen"""
        key = f"{host}:{port}"
        if key in self.servers:
            self.servers[key].enabled = enabled


# ============================================================================
# ADVANCED RESOURCE MANAGER
# ============================================================================

class AdvancedResourceManager:
    """
    Pokročilý resource manager s:
    - CPU/RAM/GPU/Disk monitoring
    - Auto-throttling
    - UI callback notifikace
    - Dynamic instance calculator
    - Network AI server discovery
    """

    def __init__(
        self,
        limits: ResourceLimits = None,
        logger: logging.Logger = None,
        status_callback: Callable[[FullResourceStatus], None] = None,
        throttle_callback: Callable[[bool, str], None] = None,
        disk_paths: List[str] = None
    ):
        self.limits = limits or ResourceLimits()
        self.logger = logger or logging.getLogger(__name__)
        self.status_callback = status_callback
        self.throttle_callback = throttle_callback
        self.disk_paths = disk_paths or ["/", "/Volumes/ACASIS"]

        # Components
        self.gpu_monitor = GPUMonitor()
        self.ai_discovery = AIServerDiscovery()

        # State
        self._throttled = False
        self._throttle_reasons = []
        self._stop_event = threading.Event()
        self._monitor_thread = None

        # Stats
        self.stats = {
            "total_throttle_time": 0,
            "throttle_count": 0,
            "checks": 0
        }

    def start_monitoring(self, interval: float = None):
        """Spusť background monitoring"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        interval = interval or self.limits.check_interval
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
        self.logger.info("Advanced resource monitoring started")

    def stop_monitoring(self):
        """Zastav monitoring"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Advanced resource monitoring stopped")

    def _monitor_loop(self, interval: float):
        """Hlavní monitoring loop"""
        while not self._stop_event.is_set():
            try:
                status = self.get_full_status()

                # Check throttling
                old_throttled = self._throttled
                self._check_throttle(status)

                # Callback if status changed
                if self.status_callback:
                    self.status_callback(status)

                # Throttle callback if state changed
                if self.throttle_callback and old_throttled != self._throttled:
                    self.throttle_callback(
                        self._throttled,
                        "; ".join(self._throttle_reasons)
                    )

            except Exception as e:
                self.logger.error(f"Monitor error: {e}")

            self._stop_event.wait(interval)

    def get_full_status(self) -> FullResourceStatus:
        """Získej kompletní status všech zdrojů"""
        # CPU/RAM
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()

        # GPU
        gpu_status = self.gpu_monitor.get_status()

        # Disks
        disk_statuses = []
        for path in self.disk_paths:
            try:
                if os.path.exists(path):
                    usage = psutil.disk_usage(path)
                    disk_statuses.append(DiskStatus(
                        path=path,
                        total_gb=usage.total / (1024**3),
                        used_gb=usage.used / (1024**3),
                        free_gb=usage.free / (1024**3),
                        percent=usage.percent
                    ))
            except:
                pass

        # Calculate recommended instances
        recommended, max_safe = self._calculate_instances(cpu, mem.percent, gpu_status)

        status = FullResourceStatus(
            timestamp=datetime.now().isoformat(),
            hostname=socket.gethostname(),
            cpu_percent=cpu,
            cpu_cores=psutil.cpu_count(),
            ram_percent=mem.percent,
            ram_used_gb=mem.used / (1024**3),
            ram_total_gb=mem.total / (1024**3),
            gpu=gpu_status,
            disks=disk_statuses,
            is_throttled=self._throttled,
            throttle_reason="; ".join(self._throttle_reasons),
            throttle_sources=list(self._throttle_reasons),
            recommended_instances=recommended,
            max_safe_instances=max_safe
        )

        self.stats["checks"] += 1
        return status

    def _check_throttle(self, status: FullResourceStatus):
        """Zkontroluj zda je třeba throttlovat"""
        reasons = []

        # CPU check
        if status.cpu_percent > self.limits.max_cpu_percent:
            reasons.append(f"CPU {status.cpu_percent:.0f}% > {self.limits.max_cpu_percent}%")

        # RAM check
        if status.ram_percent > self.limits.max_ram_percent:
            reasons.append(f"RAM {status.ram_percent:.0f}% > {self.limits.max_ram_percent}%")

        # GPU check
        if status.gpu and status.gpu.available:
            if status.gpu.utilization_percent > self.limits.max_gpu_percent:
                reasons.append(f"GPU {status.gpu.utilization_percent:.0f}% > {self.limits.max_gpu_percent}%")
            if status.gpu.memory_percent > self.limits.max_gpu_percent:
                reasons.append(f"GPU MEM {status.gpu.memory_percent:.0f}% > {self.limits.max_gpu_percent}%")

        # Disk check
        for disk in status.disks:
            if disk.free_gb < self.limits.min_disk_free_gb:
                reasons.append(f"DISK {disk.path} only {disk.free_gb:.1f}GB free < {self.limits.min_disk_free_gb}GB")

        # Update throttle state
        if reasons:
            if not self._throttled:
                self._throttled = True
                self.stats["throttle_count"] += 1
                self.logger.warning(f"THROTTLED: {'; '.join(reasons)}")
            self._throttle_reasons = reasons
        else:
            # Recovery check
            if self._throttled:
                if (status.cpu_percent < self.limits.recovery_threshold and
                    status.ram_percent < self.limits.recovery_threshold):
                    self._throttled = False
                    self._throttle_reasons = []
                    self.logger.info("Resources recovered, resuming")

    def _calculate_instances(
        self,
        cpu_percent: float,
        ram_percent: float,
        gpu: GPUStatus
    ) -> Tuple[int, int]:
        """
        Dynamicky vypočítej doporučený počet instancí.

        Returns:
            (recommended, max_safe) - doporučený a maximální bezpečný počet
        """
        cpu_cores = psutil.cpu_count()
        ram_gb = psutil.virtual_memory().total / (1024**3)

        # Base capacity (1 instance per 2 cores, 4GB RAM)
        cpu_capacity = cpu_cores // 2
        ram_capacity = int(ram_gb // 4)
        base_capacity = min(cpu_capacity, ram_capacity)

        # Adjust for current usage
        cpu_available = (100 - cpu_percent) / 100
        ram_available = (100 - ram_percent) / 100

        # Scale based on availability
        recommended = int(base_capacity * min(cpu_available, ram_available) * 0.8)
        max_safe = int(base_capacity * min(cpu_available, ram_available))

        # Minimum 1, maximum based on cores
        recommended = max(1, min(recommended, cpu_cores))
        max_safe = max(1, min(max_safe, cpu_cores))

        # Adjust for GPU if available
        if gpu and gpu.available:
            gpu_available = (100 - gpu.utilization_percent) / 100
            recommended = int(recommended * gpu_available)

        return recommended, max_safe

    def can_proceed(self) -> bool:
        """Může proces pokračovat?"""
        status = self.get_full_status()
        return not status.is_throttled

    def wait_for_resources(self, timeout: float = None) -> bool:
        """Počkej na dostupné zdroje"""
        start_time = time.time()

        while not self.can_proceed():
            if timeout and (time.time() - start_time) > timeout:
                return False
            time.sleep(self.limits.cooldown_time)

        return True

    def discover_ai_servers(self) -> List[AIServer]:
        """Objevuj AI servery v síti"""
        return self.ai_discovery.discover()

    def get_ai_servers(self) -> List[AIServer]:
        """Vrať všechny nalezené AI servery"""
        return list(self.ai_discovery.servers.values())

    def set_ai_server_enabled(self, host: str, port: int, enabled: bool):
        """Povol/zakaz AI server"""
        self.ai_discovery.set_server_enabled(host, port, enabled)

    def get_enabled_ai_servers(self) -> List[AIServer]:
        """Vrať povolené AI servery"""
        return self.ai_discovery.get_enabled_servers()


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI pro testování"""
    import argparse

    parser = argparse.ArgumentParser(description='Advanced Resource Manager')
    parser.add_argument('--watch', action='store_true', help='Continuous monitoring')
    parser.add_argument('--discover', action='store_true', help='Discover AI servers')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--interval', type=float, default=2.0, help='Check interval')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    manager = AdvancedResourceManager()

    if args.discover:
        print("Discovering AI servers...")
        servers = manager.discover_ai_servers()

        if args.json:
            print(json.dumps([asdict(s) for s in servers], indent=2, default=str))
        else:
            print(f"\nFound {len(servers)} AI servers:\n")
            for s in servers:
                status = "ONLINE" if s.is_reachable else "OFFLINE"
                models = ", ".join(s.models[:3]) + ("..." if len(s.models) > 3 else "")
                print(f"  [{status}] {s.name} ({s.host}:{s.port})")
                print(f"          Models: {models}")
                print()
        return

    if args.watch:
        print("\nAdvanced Resource Monitor (Ctrl+C to stop)")
        print("=" * 70)

        def status_callback(status: FullResourceStatus):
            # Color codes
            red = "\033[91m"
            yellow = "\033[93m"
            green = "\033[92m"
            reset = "\033[0m"

            cpu_c = green if status.cpu_percent < 70 else yellow if status.cpu_percent < 85 else red
            ram_c = green if status.ram_percent < 70 else yellow if status.ram_percent < 85 else red

            line = (
                f"\r{datetime.now().strftime('%H:%M:%S')} | "
                f"CPU: {cpu_c}{status.cpu_percent:5.1f}%{reset} | "
                f"RAM: {ram_c}{status.ram_percent:5.1f}%{reset} | "
            )

            if status.gpu and status.gpu.available:
                gpu_c = green if status.gpu.utilization_percent < 70 else yellow if status.gpu.utilization_percent < 85 else red
                line += f"GPU: {gpu_c}{status.gpu.utilization_percent:5.1f}%{reset} | "

            for disk in status.disks[:1]:
                disk_c = green if disk.free_gb > 50 else yellow if disk.free_gb > 10 else red
                line += f"Disk: {disk_c}{disk.free_gb:5.1f}GB{reset} | "

            line += f"Inst: {status.recommended_instances}/{status.max_safe_instances} | "

            if status.is_throttled:
                line += f"{red}THROTTLED{reset}"
            else:
                line += f"{green}OK{reset}"

            print(line + " " * 10, end="", flush=True)

        manager.status_callback = status_callback
        manager.start_monitoring(args.interval)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopped")
            manager.stop_monitoring()
    else:
        status = manager.get_full_status()
        if args.json:
            print(json.dumps(asdict(status), indent=2, default=str))
        else:
            print(f"\n{'='*60}")
            print(f"SYSTEM STATUS: {status.hostname}")
            print(f"{'='*60}")
            print(f"CPU: {status.cpu_percent:.1f}% ({status.cpu_cores} cores)")
            print(f"RAM: {status.ram_percent:.1f}% ({status.ram_used_gb:.1f}/{status.ram_total_gb:.1f} GB)")

            if status.gpu and status.gpu.available:
                print(f"\nGPU: {status.gpu.name}")
                print(f"  Utilization: {status.gpu.utilization_percent:.1f}%")
                print(f"  Memory: {status.gpu.memory_percent:.1f}% ({status.gpu.memory_used_mb:.0f}/{status.gpu.memory_total_mb:.0f} MB)")
                if status.gpu.temperature_c > 0:
                    print(f"  Temperature: {status.gpu.temperature_c:.0f}C")

            print(f"\nDISKS:")
            for disk in status.disks:
                print(f"  {disk.path}: {disk.free_gb:.1f}GB free ({disk.percent:.1f}% used)")

            print(f"\nRECOMMENDED INSTANCES: {status.recommended_instances}")
            print(f"MAX SAFE INSTANCES: {status.max_safe_instances}")

            if status.is_throttled:
                print(f"\nWARNING: THROTTLED - {status.throttle_reason}")


if __name__ == "__main__":
    main()
