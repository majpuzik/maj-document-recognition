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
Automatic Ollama Server Discovery
"""

import socket
import subprocess
import json
import logging
from typing import List, Dict
import concurrent.futures
import requests

logger = logging.getLogger(__name__)


class OllamaServerDiscovery:
    """
    Auto-discover Ollama servers in network

    Methods:
    - Network scan (nmap/manual)
    - Health check (API ping)
    - Model availability check
    - Server ranking by capabilities
    """

    def __init__(self, network_range: str = "192.168.10.0/24"):
        self.network_range = network_range
        self.ollama_port = 11434
        self.timeout = 5

    def discover_servers(self, required_model: str = None) -> List[Dict]:
        """
        Discover all Ollama servers in network

        Returns:
            List of server info dicts
        """
        servers = []

        # Always add localhost
        localhost = self._check_server("localhost")
        if localhost:
            servers.append(localhost)

        # Scan network
        network_servers = self._scan_network()
        servers.extend(network_servers)

        # Filter by required model
        if required_model:
            servers = [s for s in servers if required_model in s.get('models', [])]

        # Rank by capabilities
        servers = self._rank_servers(servers)

        return servers

    def _scan_network(self) -> List[Dict]:
        """Scan network for Ollama servers"""

        # Try nmap first (fast)
        try:
            return self._nmap_scan()
        except:
            logger.warning("nmap not available, using manual scan")
            return self._manual_scan()

    def _nmap_scan(self) -> List[Dict]:
        """Fast scan using nmap"""
        logger.info(f"🔍 Scanning {self.network_range} for Ollama servers...")

        result = subprocess.run(
            ["nmap", "-p", str(self.ollama_port), self.network_range, "--open", "-T4"],
            capture_output=True,
            text=True,
            timeout=30
        )

        servers = []
        lines = result.stdout.split('\n')

        for i, line in enumerate(lines):
            if f'{self.ollama_port}/tcp open' in line:
                # Get IP from previous lines
                for j in range(i-1, max(i-5, 0), -1):
                    if 'Nmap scan report' in lines[j]:
                        # Extract IP
                        parts = lines[j].split()
                        ip = parts[-1].strip('()')
                        if not ip or ip == 'for':
                            ip = parts[-2]

                        # Skip localhost (already added)
                        if ip in ['localhost', '127.0.0.1']:
                            continue

                        server = self._check_server(ip)
                        if server:
                            servers.append(server)
                        break

        logger.info(f"✅ Found {len(servers)} network servers via nmap")
        return servers

    def _manual_scan(self) -> List[Dict]:
        """Manual scan (slower but no dependencies)"""
        logger.info(f"🔍 Manual scanning {self.network_range}...")

        # Parse network range
        base_ip = '.'.join(self.network_range.split('.')[:3])
        servers = []

        # Scan common IPs in parallel
        common_ips = [f"{base_ip}.{i}" for i in [35, 79, 83, 100, 101, 102]]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self._check_server, ip): ip for ip in common_ips}

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    servers.append(result)

        logger.info(f"✅ Found {len(servers)} servers via manual scan")
        return servers

    def _check_server(self, host: str) -> Dict or None:
        """
        Check if server is running Ollama

        Returns server info or None
        """
        try:
            # Try to connect
            url = f"http://{host}:{self.ollama_port}/api/tags"
            response = requests.get(url, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                models = [m['name'] for m in data.get('models', [])]

                # Get server info
                info_url = f"http://{host}:{self.ollama_port}/api/version"
                try:
                    info_response = requests.get(info_url, timeout=2)
                    version = info_response.json().get('version', 'unknown')
                except:
                    version = 'unknown'

                return {
                    'host': host,
                    'url': f"http://{host}:{self.ollama_port}",
                    'models': models,
                    'model_count': len(models),
                    'version': version,
                    'reachable': True
                }

        except Exception as e:
            logger.debug(f"Server {host} not reachable: {e}")

        return None

    def _rank_servers(self, servers: List[Dict]) -> List[Dict]:
        """
        Rank servers by capabilities

        Ranking criteria:
        1. localhost first (lowest latency)
        2. Most models
        3. Alphabetical
        """
        def rank_key(server):
            # localhost always first
            if server['host'] == 'localhost':
                return (0, -server['model_count'], server['host'])
            else:
                return (1, -server['model_count'], server['host'])

        return sorted(servers, key=rank_key)

    def health_check(self, server: Dict) -> bool:
        """Check if server is healthy"""
        try:
            response = requests.get(f"{server['url']}/api/tags", timeout=3)
            return response.status_code == 200
        except:
            return False

    def check_model_availability(self, servers: List[Dict], model: str) -> List[Dict]:
        """Filter servers that have specific model"""
        available = []

        for server in servers:
            if model in server.get('models', []):
                available.append(server)

        return available


def main():
    """CLI for server discovery"""
    import argparse

    parser = argparse.ArgumentParser(description="Ollama Server Discovery")
    parser.add_argument('--network', default='192.168.10.0/24', help='Network range to scan')
    parser.add_argument('--model', help='Filter by required model')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--health', action='store_true', help='Check health of discovered servers')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    discovery = OllamaServerDiscovery(args.network)
    servers = discovery.discover_servers(args.model)

    if args.health:
        for server in servers:
            healthy = discovery.health_check(server)
            server['healthy'] = healthy

    if args.json:
        print(json.dumps(servers, indent=2))
    else:
        print(f"\n🌐 Discovered {len(servers)} Ollama server(s):\n")

        for i, server in enumerate(servers, 1):
            print(f"{i}. {server['url']}")
            print(f"   Models: {server['model_count']} ({', '.join(server['models'][:3])}...)")
            print(f"   Version: {server['version']}")

            if args.health:
                status = "✅ Healthy" if server.get('healthy') else "❌ Unhealthy"
                print(f"   Status: {status}")

            print()

        # Show recommended configuration
        if servers:
            print("💡 Recommended distributed_parallel_test.py config:\n")
            print("OLLAMA_SERVERS = [")
            for server in servers:
                print(f'    "{server["url"]}",')
            print("]")


if __name__ == "__main__":
    main()
