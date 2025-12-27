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
Advanced GUI for MAJ-EMAIL-DOCU-AI-LOAD
========================================
Rozšířené GUI s:
- Real-time CPU/RAM/GPU/Disk monitoring
- Automatické pozastavení při přetížení s UI notifikací
- Dynamický výpočet možných instancí dle zatížení
- Panel AI serverů v síti s checkboxy pro výběr
- Live progress tracking

Author: Claude Code
Date: 2025-12-16
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, timedelta
import subprocess
import threading
import json
import sys
import os
from pathlib import Path
from typing import Dict

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from advanced_resource_manager import (
    AdvancedResourceManager, ResourceLimits, FullResourceStatus, AIServer
)

# ============================================================================
# CONFIGURATION
# ============================================================================

PAPERLESS_CONFIGS = {
    "Production (192.168.10.200:8020)": {
        "url": "http://192.168.10.200:8020",
        "api_token": "d06a165d1a496a09ea8b5e70e3a0554702f20f53"
    },
    "Development (192.168.10.85:8777)": {
        "url": "http://192.168.10.85:8777",
        "api_token": "0c1072a02c43c50d109a0300f090a361fc1eb775"
    }
}

# Paperless DB locations - network presets for Finder sidebar
PAPERLESS_DB_PRESETS = [
    {
        "name": "NAS5 - Paperless Docker",
        "path": "/Volumes/homes/admin/paperless-ngx/data",
        "smb_url": "smb://192.168.10.35/homes/admin/paperless-ngx/data",
        "description": "Synology NAS5 - hlavní Paperless instance"
    },
    {
        "name": "NAS5 - Production DB",
        "path": "/Volumes/docker/paperless/data",
        "smb_url": "smb://192.168.10.35/docker/paperless/data",
        "description": "Produkční Paperless databáze"
    },
    {
        "name": "Mac Mini - Local Dev",
        "path": "/Users/m.a.j.puzik/paperless-ngx/data",
        "smb_url": None,
        "description": "Lokální vývojová instance"
    },
    {
        "name": "ACASIS - Backup DB",
        "path": "/Volumes/ACASIS/paperless-backup/data",
        "smb_url": None,
        "description": "Záložní Paperless databáze na ACASIS"
    },
    {
        "name": "Ubuntu VM - Test",
        "path": "/Volumes/ubuntu-share/paperless/data",
        "smb_url": "smb://192.168.64.3/paperless/data",
        "description": "Testovací VM instance"
    },
    {
        "name": "DGX - AI Processing",
        "path": "/Volumes/dgx-share/paperless/data",
        "smb_url": "smb://192.168.10.130/paperless/data",
        "description": "DGX AI server Paperless"
    },
]

KNOWN_AI_SERVERS = [
    {"host": "localhost", "port": 11434, "name": "Local Ollama"},
    {"host": "192.168.10.130", "port": 11434, "name": "DGX H100"},
    {"host": "192.168.10.131", "port": 11434, "name": "Mac Mini M4"},
]


# ============================================================================
# RESOURCE MONITOR WIDGET
# ============================================================================

class ResourceMonitorWidget(ttk.Frame):
    """Widget pro zobrazení systémových zdrojů"""

    def __init__(self, parent):
        super().__init__(parent)

        self.configure(padding=5)

        # Title
        title = ttk.Label(self, text="System Resources", font=('Helvetica', 11, 'bold'))
        title.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 5))

        # CPU
        ttk.Label(self, text="CPU:", width=6).grid(row=1, column=0, sticky='w')
        self.cpu_bar = ttk.Progressbar(self, length=120, mode='determinate')
        self.cpu_bar.grid(row=1, column=1, padx=5)
        self.cpu_label = ttk.Label(self, text="0%", width=6)
        self.cpu_label.grid(row=1, column=2)

        # RAM
        ttk.Label(self, text="RAM:", width=6).grid(row=2, column=0, sticky='w')
        self.ram_bar = ttk.Progressbar(self, length=120, mode='determinate')
        self.ram_bar.grid(row=2, column=1, padx=5)
        self.ram_label = ttk.Label(self, text="0%", width=6)
        self.ram_label.grid(row=2, column=2)

        # GPU
        ttk.Label(self, text="GPU:", width=6).grid(row=3, column=0, sticky='w')
        self.gpu_bar = ttk.Progressbar(self, length=120, mode='determinate')
        self.gpu_bar.grid(row=3, column=1, padx=5)
        self.gpu_label = ttk.Label(self, text="N/A", width=6)
        self.gpu_label.grid(row=3, column=2)

        # Disk
        ttk.Label(self, text="Disk:", width=6).grid(row=4, column=0, sticky='w')
        self.disk_bar = ttk.Progressbar(self, length=120, mode='determinate')
        self.disk_bar.grid(row=4, column=1, padx=5)
        self.disk_label = ttk.Label(self, text="0 GB", width=8)
        self.disk_label.grid(row=4, column=2)

        # Instances
        ttk.Separator(self, orient='horizontal').grid(row=5, column=0, columnspan=4, sticky='ew', pady=5)

        ttk.Label(self, text="Doporučené instance:").grid(row=6, column=0, columnspan=2, sticky='w')
        self.instances_label = ttk.Label(self, text="0 / 0", font=('Helvetica', 11, 'bold'))
        self.instances_label.grid(row=6, column=2, columnspan=2, sticky='w')

        # Status indicator
        self.status_frame = ttk.Frame(self)
        self.status_frame.grid(row=7, column=0, columnspan=4, sticky='ew', pady=5)

        self.status_indicator = tk.Canvas(self.status_frame, width=20, height=20, highlightthickness=0)
        self.status_indicator.pack(side='left')
        self.status_circle = self.status_indicator.create_oval(2, 2, 18, 18, fill='green')

        self.status_text = ttk.Label(self.status_frame, text="OK - Ready", foreground='green')
        self.status_text.pack(side='left', padx=5)

    def update(self, status: FullResourceStatus):
        """Aktualizuj zobrazení"""
        # CPU
        self.cpu_bar['value'] = status.cpu_percent
        self.cpu_label.config(text=f"{status.cpu_percent:.0f}%")
        self._color_bar(self.cpu_bar, status.cpu_percent)

        # RAM
        self.ram_bar['value'] = status.ram_percent
        self.ram_label.config(text=f"{status.ram_percent:.0f}%")
        self._color_bar(self.ram_bar, status.ram_percent)

        # GPU
        if status.gpu and status.gpu.available:
            self.gpu_bar['value'] = status.gpu.utilization_percent
            self.gpu_label.config(text=f"{status.gpu.utilization_percent:.0f}%")
            self._color_bar(self.gpu_bar, status.gpu.utilization_percent)
        else:
            self.gpu_bar['value'] = 0
            self.gpu_label.config(text="N/A")

        # Disk
        if status.disks:
            disk = status.disks[0]
            self.disk_bar['value'] = disk.percent
            self.disk_label.config(text=f"{disk.free_gb:.0f} GB")
            self._color_bar(self.disk_bar, disk.percent)

        # Instances
        self.instances_label.config(
            text=f"{status.recommended_instances} / {status.max_safe_instances}"
        )

        # Status
        if status.is_throttled:
            self.status_indicator.itemconfig(self.status_circle, fill='red')
            self.status_text.config(
                text=f"THROTTLED: {status.throttle_reason[:40]}",
                foreground='red'
            )
        else:
            self.status_indicator.itemconfig(self.status_circle, fill='green')
            self.status_text.config(text="OK - Ready", foreground='green')

    def _color_bar(self, bar: ttk.Progressbar, value: float):
        """Obarvi progress bar podle hodnoty"""
        style = ttk.Style()
        if value < 70:
            style.configure("green.Horizontal.TProgressbar", background='green')
            bar.configure(style="green.Horizontal.TProgressbar")
        elif value < 85:
            style.configure("yellow.Horizontal.TProgressbar", background='orange')
            bar.configure(style="yellow.Horizontal.TProgressbar")
        else:
            style.configure("red.Horizontal.TProgressbar", background='red')
            bar.configure(style="red.Horizontal.TProgressbar")


# ============================================================================
# AI SERVER PANEL
# ============================================================================

class AIServerPanel(ttk.LabelFrame):
    """Panel pro výběr AI serverů v síti"""

    def __init__(self, parent, resource_manager: AdvancedResourceManager):
        super().__init__(parent, text=" AI Servers in Network ", padding=10)

        self.resource_manager = resource_manager
        self.server_vars: Dict[str, tk.BooleanVar] = {}
        self.server_widgets: Dict[str, Dict] = {}

        # Header row
        header_frame = ttk.Frame(self)
        header_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(header_frame, text="Server", width=20, font=('Helvetica', 10, 'bold')).pack(side='left')
        ttk.Label(header_frame, text="Status", width=10, font=('Helvetica', 10, 'bold')).pack(side='left')
        ttk.Label(header_frame, text="Models", width=20, font=('Helvetica', 10, 'bold')).pack(side='left')
        ttk.Label(header_frame, text="Use", width=5, font=('Helvetica', 10, 'bold')).pack(side='left')

        # Scrollable server list
        self.server_frame = ttk.Frame(self)
        self.server_frame.pack(fill='both', expand=True)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', pady=5)

        self.discover_btn = tk.Button(
            btn_frame, text="Discover Servers",
            command=self.discover_servers,
            bg='#2196f3', fg='white', font=('Helvetica', 10)
        )
        self.discover_btn.pack(side='left', padx=5)

        self.select_all_btn = tk.Button(
            btn_frame, text="Select All",
            command=lambda: self._set_all(True),
            bg='#4caf50', fg='white', font=('Helvetica', 10)
        )
        self.select_all_btn.pack(side='left', padx=5)

        self.deselect_all_btn = tk.Button(
            btn_frame, text="Deselect All",
            command=lambda: self._set_all(False),
            bg='#f44336', fg='white', font=('Helvetica', 10)
        )
        self.deselect_all_btn.pack(side='left', padx=5)

        # Status label
        self.status_label = ttk.Label(self, text="Click 'Discover Servers' to scan network")
        self.status_label.pack(anchor='w')

    def discover_servers(self):
        """Objevuj servery v síti"""
        self.discover_btn.config(state='disabled', text='Scanning...')
        self.status_label.config(text="Scanning network...")

        def scan():
            servers = self.resource_manager.discover_ai_servers()
            self.after(0, lambda: self._update_server_list(servers))

        threading.Thread(target=scan, daemon=True).start()

    def _update_server_list(self, servers: list):
        """Aktualizuj seznam serverů"""
        # Clear old widgets
        for widget in self.server_frame.winfo_children():
            widget.destroy()
        self.server_vars.clear()
        self.server_widgets.clear()

        # Add servers
        for i, server in enumerate(servers):
            row = ttk.Frame(self.server_frame)
            row.pack(fill='x', pady=2)

            key = f"{server.host}:{server.port}"

            # Name
            name_label = ttk.Label(row, text=f"{server.name}", width=20)
            name_label.pack(side='left')

            # Status indicator
            status_canvas = tk.Canvas(row, width=20, height=20, highlightthickness=0)
            status_canvas.pack(side='left')
            color = 'green' if server.is_reachable else 'red'
            circle = status_canvas.create_oval(4, 4, 16, 16, fill=color)

            status_text = "ONLINE" if server.is_reachable else "OFFLINE"
            ttk.Label(row, text=status_text, width=8).pack(side='left')

            # Models
            models_text = ", ".join(server.models[:2])
            if len(server.models) > 2:
                models_text += f" +{len(server.models)-2}"
            ttk.Label(row, text=models_text[:20], width=20).pack(side='left')

            # Checkbox
            var = tk.BooleanVar(value=server.is_reachable)
            self.server_vars[key] = var
            cb = ttk.Checkbutton(
                row, variable=var,
                command=lambda k=key: self._on_toggle(k),
                state='normal' if server.is_reachable else 'disabled'
            )
            cb.pack(side='left')

            self.server_widgets[key] = {
                'row': row,
                'status_canvas': status_canvas,
                'circle': circle,
                'var': var
            }

        self.discover_btn.config(state='normal', text='Discover Servers')
        online = sum(1 for s in servers if s.is_reachable)
        self.status_label.config(text=f"Found {len(servers)} servers ({online} online)")

    def _on_toggle(self, key: str):
        """Handler pro toggle checkboxu"""
        host, port = key.split(':')
        enabled = self.server_vars[key].get()
        self.resource_manager.set_ai_server_enabled(host, int(port), enabled)

    def _set_all(self, enabled: bool):
        """Nastav všechny checkboxy"""
        for key, var in self.server_vars.items():
            host, port = key.split(':')
            server = self.resource_manager.ai_discovery.servers.get(key)
            if server and server.is_reachable:
                var.set(enabled)
                self.resource_manager.set_ai_server_enabled(host, int(port), enabled)

    def get_enabled_servers(self) -> list:
        """Vrať povolené servery"""
        return self.resource_manager.get_enabled_ai_servers()


# ============================================================================
# PAPERLESS DB PANEL
# ============================================================================

class PaperlessDBPanel(ttk.LabelFrame):
    """Panel pro výběr Paperless databáze z různých síťových lokací"""

    def __init__(self, parent):
        super().__init__(parent, text=" Paperless Database Location ", padding=10)

        self.selected_path = tk.StringVar(value="")
        self.selected_preset = tk.StringVar(value="")

        # Preset dropdown
        preset_frame = ttk.Frame(self)
        preset_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(preset_frame, text="Předvolba:").pack(side='left')

        preset_names = ["-- Vyberte lokaci --"] + [p["name"] for p in PAPERLESS_DB_PRESETS]
        self.preset_combo = ttk.Combobox(
            preset_frame,
            values=preset_names,
            textvariable=self.selected_preset,
            state='readonly',
            width=30
        )
        self.preset_combo.current(0)
        self.preset_combo.pack(side='left', padx=10)
        self.preset_combo.bind('<<ComboboxSelected>>', self._on_preset_selected)

        # Mount button (for SMB shares)
        self.mount_btn = tk.Button(
            preset_frame, text="📁 Mount",
            command=self._mount_selected,
            bg='#ff9800', fg='white', font=('Helvetica', 10),
            state='disabled'
        )
        self.mount_btn.pack(side='left', padx=5)

        # Description
        self.desc_label = ttk.Label(self, text="", foreground='#888888', font=('Helvetica', 9))
        self.desc_label.pack(anchor='w', pady=(0, 5))

        # Current path display
        path_frame = ttk.Frame(self)
        path_frame.pack(fill='x', pady=5)

        ttk.Label(path_frame, text="Cesta:").pack(side='left')
        self.path_entry = ttk.Entry(path_frame, textvariable=self.selected_path, width=45)
        self.path_entry.pack(side='left', padx=5, fill='x', expand=True)

        # Browse button
        self.browse_btn = tk.Button(
            path_frame, text="📂 Finder",
            command=self._browse_finder,
            bg='#2196f3', fg='white', font=('Helvetica', 10)
        )
        self.browse_btn.pack(side='left', padx=5)

        # Status and test connection
        status_frame = ttk.Frame(self)
        status_frame.pack(fill='x', pady=5)

        self.status_indicator = tk.Canvas(status_frame, width=20, height=20, highlightthickness=0)
        self.status_indicator.pack(side='left')
        self.status_circle = self.status_indicator.create_oval(2, 2, 18, 18, fill='gray')

        self.status_text = ttk.Label(status_frame, text="Nevybráno", foreground='gray')
        self.status_text.pack(side='left', padx=5)

        self.test_btn = tk.Button(
            status_frame, text="Test Connection",
            command=self._test_connection,
            bg='#4caf50', fg='white', font=('Helvetica', 10)
        )
        self.test_btn.pack(side='right')

        # Quick mount all button
        mount_all_frame = ttk.Frame(self)
        mount_all_frame.pack(fill='x', pady=(10, 0))

        self.mount_all_btn = tk.Button(
            mount_all_frame, text="🔗 Mount All Network Shares",
            command=self._mount_all_shares,
            bg='#9c27b0', fg='white', font=('Helvetica', 10)
        )
        self.mount_all_btn.pack(side='left')

        ttk.Label(
            mount_all_frame,
            text="(Připojí všechny SMB sdílení do Finderu)",
            foreground='#888888',
            font=('Helvetica', 9)
        ).pack(side='left', padx=10)

    def _on_preset_selected(self, event=None):
        """Handler pro výběr předvolby"""
        selection = self.selected_preset.get()
        if selection == "-- Vyberte lokaci --":
            self.selected_path.set("")
            self.desc_label.config(text="")
            self.mount_btn.config(state='disabled')
            return

        # Find selected preset
        for preset in PAPERLESS_DB_PRESETS:
            if preset["name"] == selection:
                self.selected_path.set(preset["path"])
                self.desc_label.config(text=preset["description"])

                # Enable mount button if SMB URL exists
                if preset.get("smb_url"):
                    self.mount_btn.config(state='normal')
                else:
                    self.mount_btn.config(state='disabled')

                # Auto-check path
                self._check_path_status()
                break

    def _browse_finder(self):
        """Otevře Finder dialog pro výběr složky"""
        # Set initial directory based on current selection or default
        initial_dir = self.selected_path.get() or "/Volumes"

        # Finder presets - add favorite locations
        # Note: macOS doesn't directly support sidebar presets in filedialog,
        # but we start in /Volumes which shows all mounted shares

        folder = filedialog.askdirectory(
            title="Vyberte Paperless data složku",
            initialdir=initial_dir,
            mustexist=True
        )

        if folder:
            self.selected_path.set(folder)
            self.selected_preset.set("-- Vlastní cesta --")
            self._check_path_status()

    def _mount_selected(self):
        """Připojí vybraný SMB share"""
        selection = self.selected_preset.get()

        for preset in PAPERLESS_DB_PRESETS:
            if preset["name"] == selection and preset.get("smb_url"):
                smb_url = preset["smb_url"]
                self._mount_smb(smb_url, preset["name"])
                break

    def _mount_smb(self, smb_url: str, name: str):
        """Připojí SMB share pomocí AppleScript"""
        self.mount_btn.config(state='disabled', text='Mounting...')

        def do_mount():
            try:
                # Use osascript to mount SMB share
                script = f'''
                tell application "Finder"
                    try
                        mount volume "{smb_url}"
                    end try
                end tell
                '''
                result = subprocess.run(
                    ['osascript', '-e', script],
                    capture_output=True, text=True, timeout=30
                )

                # Wait a bit for mount
                import time
                time.sleep(2)

                self.after(0, lambda: self._on_mount_complete(name, result.returncode == 0))
            except Exception as e:
                self.after(0, lambda: self._on_mount_complete(name, False, str(e)))

        threading.Thread(target=do_mount, daemon=True).start()

    def _on_mount_complete(self, name: str, success: bool, error: str = ""):
        """Callback po dokončení mount"""
        self.mount_btn.config(state='normal', text='📁 Mount')

        if success:
            self._check_path_status()
            messagebox.showinfo("Mount", f"Share '{name}' připojen úspěšně!")
        else:
            messagebox.showerror("Mount Error", f"Nepodařilo se připojit share.\n{error}")

    def _mount_all_shares(self):
        """Připojí všechny SMB shares"""
        self.mount_all_btn.config(state='disabled', text='Mounting all...')

        def do_mount_all():
            mounted = []
            failed = []

            for preset in PAPERLESS_DB_PRESETS:
                smb_url = preset.get("smb_url")
                if smb_url:
                    try:
                        script = f'''
                        tell application "Finder"
                            try
                                mount volume "{smb_url}"
                            end try
                        end tell
                        '''
                        subprocess.run(['osascript', '-e', script], capture_output=True, timeout=15)
                        mounted.append(preset["name"])
                    except:
                        failed.append(preset["name"])

            import time
            time.sleep(2)
            self.after(0, lambda: self._on_mount_all_complete(mounted, failed))

        threading.Thread(target=do_mount_all, daemon=True).start()

    def _on_mount_all_complete(self, mounted: list, failed: list):
        """Callback po mount všech shares"""
        self.mount_all_btn.config(state='normal', text='🔗 Mount All Network Shares')

        msg = f"Připojeno: {len(mounted)} shares\n"
        if mounted:
            msg += "\n".join(f"  ✓ {m}" for m in mounted)
        if failed:
            msg += f"\n\nNepodařilo se: {len(failed)}\n"
            msg += "\n".join(f"  ✗ {f}" for f in failed)

        messagebox.showinfo("Mount All", msg)
        self._check_path_status()

    def _check_path_status(self):
        """Zkontroluj status aktuální cesty"""
        path = self.selected_path.get()

        if not path:
            self._set_status('gray', 'Nevybráno')
            return

        if os.path.exists(path):
            # Check if it's a valid Paperless data directory
            db_file = os.path.join(path, "db.sqlite3")
            media_dir = os.path.join(path, "media")

            if os.path.exists(db_file):
                self._set_status('green', 'OK - Paperless DB nalezena')
            elif os.path.isdir(path):
                self._set_status('orange', 'Složka existuje, DB nenalezena')
            else:
                self._set_status('orange', 'Cesta existuje')
        else:
            self._set_status('red', 'Cesta neexistuje (nepřipojeno?)')

    def _set_status(self, color: str, text: str):
        """Nastav status indicator"""
        self.status_indicator.itemconfig(self.status_circle, fill=color)
        self.status_text.config(text=text, foreground=color if color != 'gray' else '#888888')

    def _test_connection(self):
        """Test připojení k Paperless databázi"""
        path = self.selected_path.get()

        if not path:
            messagebox.showwarning("Test", "Nejprve vyberte cestu k databázi.")
            return

        self.test_btn.config(state='disabled', text='Testing...')

        def do_test():
            results = {
                'path_exists': os.path.exists(path),
                'is_dir': os.path.isdir(path) if os.path.exists(path) else False,
                'db_exists': False,
                'db_size': 0,
                'media_exists': False,
                'media_count': 0,
            }

            if results['is_dir']:
                db_file = os.path.join(path, "db.sqlite3")
                results['db_exists'] = os.path.exists(db_file)
                if results['db_exists']:
                    results['db_size'] = os.path.getsize(db_file) / (1024*1024)  # MB

                media_dir = os.path.join(path, "media", "documents")
                results['media_exists'] = os.path.isdir(media_dir)
                if results['media_exists']:
                    try:
                        results['media_count'] = len(os.listdir(media_dir))
                    except:
                        pass

            self.after(0, lambda: self._show_test_results(results))

        threading.Thread(target=do_test, daemon=True).start()

    def _show_test_results(self, results: dict):
        """Zobraz výsledky testu"""
        self.test_btn.config(state='normal', text='Test Connection')

        msg = "Test Paperless databáze:\n\n"
        msg += f"✓ Cesta existuje\n" if results['path_exists'] else "✗ Cesta neexistuje\n"

        if results['is_dir']:
            msg += f"✓ Je adresář\n"

            if results['db_exists']:
                msg += f"✓ db.sqlite3 nalezena ({results['db_size']:.1f} MB)\n"
            else:
                msg += f"✗ db.sqlite3 nenalezena\n"

            if results['media_exists']:
                msg += f"✓ Media složka ({results['media_count']} dokumentů)\n"
            else:
                msg += f"✗ Media složka nenalezena\n"

        if results['db_exists']:
            self._set_status('green', 'OK - Paperless DB nalezena')
            messagebox.showinfo("Test OK", msg)
        else:
            self._set_status('red', 'DB nenalezena')
            messagebox.showwarning("Test Failed", msg)

    def get_selected_path(self) -> str:
        """Vrať vybranou cestu"""
        return self.selected_path.get()

    def get_db_path(self) -> str:
        """Vrať cestu k SQLite databázi"""
        base = self.selected_path.get()
        if base:
            return os.path.join(base, "db.sqlite3")
        return ""


# ============================================================================
# MAIN GUI
# ============================================================================

class AdvancedLauncherGUI:
    """Rozšířené GUI s monitoringem a AI server discovery"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MAJ Email/Document AI Loader - Advanced")
        self.root.geometry("900x800")
        self.root.configure(bg='#1e1e1e')

        # Resource manager
        self.resource_manager = AdvancedResourceManager(
            limits=ResourceLimits(
                max_cpu_percent=85.0,
                max_ram_percent=85.0,
                max_gpu_percent=90.0,
                min_disk_free_gb=10.0
            ),
            status_callback=self._on_status_update,
            throttle_callback=self._on_throttle_change,
            disk_paths=["/", "/Volumes/ACASIS"]
        )

        self.setup_styles()
        self.create_widgets()

        # Start monitoring
        self.resource_manager.start_monitoring(interval=2.0)

        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#1e1e1e')
        style.configure('TLabel', background='#1e1e1e', foreground='#ffffff', font=('Helvetica', 11))
        style.configure('TLabelframe', background='#1e1e1e', foreground='#ffffff')
        style.configure('TLabelframe.Label', background='#1e1e1e', foreground='#4fc3f7', font=('Helvetica', 11, 'bold'))
        style.configure('Title.TLabel', font=('Helvetica', 16, 'bold'), foreground='#4fc3f7')
        style.configure('TButton', font=('Helvetica', 11), padding=10)
        style.configure('TRadiobutton', background='#1e1e1e', foreground='#ffffff', font=('Helvetica', 11))
        style.configure('TCheckbutton', background='#1e1e1e', foreground='#ffffff', font=('Helvetica', 11))
        style.configure('TNotebook', background='#1e1e1e')
        style.configure('TNotebook.Tab', background='#2d2d2d', foreground='#ffffff', padding=[10, 5])

    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill='both', expand=True)

        # Left panel - Resource monitor + AI servers
        left_panel = ttk.Frame(main_frame, width=300)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)

        # Resource monitor widget
        self.resource_widget = ResourceMonitorWidget(left_panel)
        self.resource_widget.pack(fill='x', pady=(0, 10))

        # AI Server panel
        self.ai_panel = AIServerPanel(left_panel, self.resource_manager)
        self.ai_panel.pack(fill='both', expand=True)

        # Right panel - Notebook with tabs
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side='right', fill='both', expand=True)

        # Title
        title = ttk.Label(right_panel, text="MAJ Email/Document AI Loader", style='Title.TLabel')
        title.pack(pady=10)

        # Notebook
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill='both', expand=True)

        # Tab 1: Processing
        self._create_processing_tab()

        # Tab 2: Settings (Paperless DB)
        self._create_settings_tab()

        # Tab 3: Monitoring
        self._create_monitoring_tab()

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, font=('Helvetica', 10), foreground='#888888')
        status_bar.pack(side='bottom', fill='x', pady=5, padx=10)

        # Throttle warning banner (hidden by default)
        self.throttle_banner = tk.Frame(self.root, bg='#f44336', height=30)
        self.throttle_label = tk.Label(
            self.throttle_banner,
            text="SYSTEM OVERLOADED - Processing paused",
            bg='#f44336', fg='white', font=('Helvetica', 11, 'bold')
        )
        self.throttle_label.pack(pady=5)
        # Banner is not packed by default

    def _create_processing_tab(self):
        """Záložka zpracování"""
        process_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(process_frame, text="  Processing  ")

        # Source selection
        source_frame = ttk.LabelFrame(process_frame, text=" Data Source ", padding=10)
        source_frame.pack(fill='x', pady=5)

        self.source_var = tk.StringVar(value="emails")
        ttk.Radiobutton(source_frame, text="Emails (Thunderbird)", variable=self.source_var, value="emails").pack(anchor='w')
        ttk.Radiobutton(source_frame, text="Documents (OneDrive/ACASIS)", variable=self.source_var, value="documents").pack(anchor='w')
        ttk.Radiobutton(source_frame, text="Both", variable=self.source_var, value="both").pack(anchor='w')

        # Limit options
        limit_frame = ttk.LabelFrame(process_frame, text=" Limits ", padding=10)
        limit_frame.pack(fill='x', pady=5)

        count_row = ttk.Frame(limit_frame)
        count_row.pack(fill='x', pady=2)
        self.use_count = tk.BooleanVar(value=False)
        ttk.Checkbutton(count_row, text="Limit count:", variable=self.use_count).pack(side='left')
        self.count_entry = ttk.Entry(count_row, width=10)
        self.count_entry.insert(0, "1000")
        self.count_entry.pack(side='left', padx=10)

        # Auto-instances option
        auto_row = ttk.Frame(limit_frame)
        auto_row.pack(fill='x', pady=2)
        self.auto_instances = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            auto_row,
            text="Auto-calculate instances based on system load",
            variable=self.auto_instances
        ).pack(side='left')

        # Manual instances
        manual_row = ttk.Frame(limit_frame)
        manual_row.pack(fill='x', pady=2)
        ttk.Label(manual_row, text="Manual instances:").pack(side='left')
        self.manual_instances = ttk.Entry(manual_row, width=5)
        self.manual_instances.insert(0, "5")
        self.manual_instances.pack(side='left', padx=10)

        # Phases
        phase_frame = ttk.LabelFrame(process_frame, text=" Phases ", padding=10)
        phase_frame.pack(fill='x', pady=5)

        self.phase1 = tk.BooleanVar(value=True)
        self.phase2 = tk.BooleanVar(value=True)
        self.phase3 = tk.BooleanVar(value=False)
        self.phase5 = tk.BooleanVar(value=True)

        phases_row = ttk.Frame(phase_frame)
        phases_row.pack(fill='x')
        ttk.Checkbutton(phases_row, text="Phase 1: Docling", variable=self.phase1).pack(side='left', padx=5)
        ttk.Checkbutton(phases_row, text="Phase 2: LLM", variable=self.phase2).pack(side='left', padx=5)
        ttk.Checkbutton(phases_row, text="Phase 3: GPT-4", variable=self.phase3).pack(side='left', padx=5)
        ttk.Checkbutton(phases_row, text="Phase 5: Import", variable=self.phase5).pack(side='left', padx=5)

        # Buttons
        btn_frame = ttk.Frame(process_frame)
        btn_frame.pack(fill='x', pady=15)

        self.start_btn = tk.Button(
            btn_frame, text="START",
            command=self.start_processing,
            bg='#4caf50', fg='white', font=('Helvetica', 12, 'bold'),
            width=12, height=2
        )
        self.start_btn.pack(side='left', padx=5)

        self.stop_btn = tk.Button(
            btn_frame, text="STOP",
            command=self.stop_processing,
            bg='#f44336', fg='white', font=('Helvetica', 12, 'bold'),
            width=12, height=2,
            state='disabled'
        )
        self.stop_btn.pack(side='left', padx=5)

    def _create_settings_tab(self):
        """Záložka nastavení - Paperless DB a další"""
        settings_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(settings_frame, text="  Settings  ")

        # Paperless DB Panel
        self.paperless_panel = PaperlessDBPanel(settings_frame)
        self.paperless_panel.pack(fill='x', pady=5)

        # Paperless API Configuration
        api_frame = ttk.LabelFrame(settings_frame, text=" Paperless API ", padding=10)
        api_frame.pack(fill='x', pady=10)

        # API selection dropdown
        api_row = ttk.Frame(api_frame)
        api_row.pack(fill='x', pady=2)

        ttk.Label(api_row, text="API Instance:").pack(side='left')
        self.api_var = tk.StringVar(value=list(PAPERLESS_CONFIGS.keys())[0])
        api_combo = ttk.Combobox(
            api_row,
            values=list(PAPERLESS_CONFIGS.keys()),
            textvariable=self.api_var,
            state='readonly',
            width=35
        )
        api_combo.pack(side='left', padx=10)

        # Test API button
        test_api_btn = tk.Button(
            api_row, text="Test API",
            command=self._test_paperless_api,
            bg='#4caf50', fg='white', font=('Helvetica', 10)
        )
        test_api_btn.pack(side='left', padx=5)

        # Custom API URL
        custom_row = ttk.Frame(api_frame)
        custom_row.pack(fill='x', pady=5)

        self.use_custom_api = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            custom_row,
            text="Vlastní API URL:",
            variable=self.use_custom_api
        ).pack(side='left')

        self.custom_api_url = ttk.Entry(custom_row, width=40)
        self.custom_api_url.insert(0, "http://192.168.10.x:8000")
        self.custom_api_url.pack(side='left', padx=5)

        # API Token
        token_row = ttk.Frame(api_frame)
        token_row.pack(fill='x', pady=2)

        ttk.Label(token_row, text="API Token:").pack(side='left')
        self.custom_token = ttk.Entry(token_row, width=50, show='*')
        self.custom_token.pack(side='left', padx=10)

        show_token = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            token_row,
            text="Zobrazit",
            variable=show_token,
            command=lambda: self.custom_token.config(show='' if show_token.get() else '*')
        ).pack(side='left')

        # Output settings
        output_frame = ttk.LabelFrame(settings_frame, text=" Output Settings ", padding=10)
        output_frame.pack(fill='x', pady=10)

        # Output directory
        out_row = ttk.Frame(output_frame)
        out_row.pack(fill='x', pady=2)

        ttk.Label(out_row, text="Output Directory:").pack(side='left')
        self.output_dir = ttk.Entry(out_row, width=45)
        self.output_dir.insert(0, "/Volumes/ACASIS/apps/maj-document-recognition/phase1_output")
        self.output_dir.pack(side='left', padx=5)

        tk.Button(
            out_row, text="📂",
            command=lambda: self._browse_output_dir(),
            bg='#2196f3', fg='white'
        ).pack(side='left')

        # ISDOC generation
        isdoc_row = ttk.Frame(output_frame)
        isdoc_row.pack(fill='x', pady=2)

        self.generate_isdoc = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            isdoc_row,
            text="Generovat ISDOC XML pro účetní dokumenty",
            variable=self.generate_isdoc
        ).pack(side='left')

        # CDB Logging
        cdb_row = ttk.Frame(output_frame)
        cdb_row.pack(fill='x', pady=2)

        self.enable_cdb = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            cdb_row,
            text="Logovat do CDB (almquist.db)",
            variable=self.enable_cdb
        ).pack(side='left')

    def _browse_output_dir(self):
        """Vybere output adresář"""
        folder = filedialog.askdirectory(
            title="Vyberte output adresář",
            initialdir=self.output_dir.get()
        )
        if folder:
            self.output_dir.delete(0, tk.END)
            self.output_dir.insert(0, folder)

    def _test_paperless_api(self):
        """Test Paperless API připojení"""
        import requests

        if self.use_custom_api.get():
            url = self.custom_api_url.get()
            token = self.custom_token.get()
        else:
            config = PAPERLESS_CONFIGS.get(self.api_var.get(), {})
            url = config.get("url", "")
            token = config.get("api_token", "")

        if not url:
            messagebox.showwarning("Test", "URL není nastavena")
            return

        def do_test():
            try:
                headers = {"Authorization": f"Token {token}"}
                response = requests.get(f"{url}/api/documents/", headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    count = data.get("count", 0)
                    self.root.after(0, lambda: messagebox.showinfo(
                        "API OK",
                        f"Připojení úspěšné!\n\nDokumentů: {count}\nURL: {url}"
                    ))
                else:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "API Error",
                        f"HTTP {response.status_code}\n{response.text[:200]}"
                    ))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("API Error", str(e)))

        threading.Thread(target=do_test, daemon=True).start()

    def _create_monitoring_tab(self):
        """Záložka monitoringu"""
        monitor_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(monitor_frame, text="  Monitoring  ")

        # Log output
        log_frame = ttk.LabelFrame(monitor_frame, text=" Processing Log ", padding=10)
        log_frame.pack(fill='both', expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=20,
            bg='#161b22', fg='#c9d1d9', font=('Monaco', 9)
        )
        self.log_text.pack(fill='both', expand=True)
        self.log_text.insert('1.0', "Ready to start processing...\n")

    def _on_status_update(self, status: FullResourceStatus):
        """Callback při aktualizaci statusu"""
        self.root.after(0, lambda: self.resource_widget.update(status))

    def _on_throttle_change(self, is_throttled: bool, reason: str):
        """Callback při změně throttle stavu"""
        def update():
            if is_throttled:
                self.throttle_banner.pack(side='top', fill='x', before=self.root.winfo_children()[0])
                self.throttle_label.config(text=f"SYSTEM OVERLOADED: {reason}")
                self.log_text.insert('end', f"\nWARNING: Processing paused - {reason}\n")
                self.log_text.see('end')
            else:
                self.throttle_banner.pack_forget()
                self.log_text.insert('end', "\nINFO: Resources recovered, resuming...\n")
                self.log_text.see('end')

        self.root.after(0, update)

    def start_processing(self):
        """Spusť zpracování"""
        # Get configuration
        enabled_servers = self.ai_panel.get_enabled_servers()
        if not enabled_servers:
            messagebox.showwarning("Warning", "No AI servers selected!")
            return

        # Get instance count
        if self.auto_instances.get():
            status = self.resource_manager.get_full_status()
            instances = status.recommended_instances
        else:
            instances = int(self.manual_instances.get())

        self.log_text.insert('end', f"\n{'='*50}\n")
        self.log_text.insert('end', f"Starting processing at {datetime.now().strftime('%H:%M:%S')}\n")
        self.log_text.insert('end', f"Instances: {instances}\n")
        self.log_text.insert('end', f"Servers: {', '.join(s.name for s in enabled_servers)}\n")
        self.log_text.insert('end', f"{'='*50}\n")
        self.log_text.see('end')

        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_var.set("Processing...")

        # TODO: Launch actual processing

    def stop_processing(self):
        """Zastav zpracování"""
        self.log_text.insert('end', f"\nStopping processing at {datetime.now().strftime('%H:%M:%S')}\n")
        self.log_text.see('end')

        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_var.set("Stopped")

        # TODO: Stop actual processing

    def _on_close(self):
        """Handler pro zavření okna"""
        self.resource_manager.stop_monitoring()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    app = AdvancedLauncherGUI()
    app.run()
