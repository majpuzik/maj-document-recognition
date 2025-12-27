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
GUI Monitor for MAJ-EMAIL-DOCU-AI-LOAD
======================================
Real-time monitoring of processing progress.

Zobrazuje:
- Odkud → Kam tečou data
- Kolik zbývá
- Odhadovaný čas
- Počet úspěšně zpracovaných
- Počet labelů
- Počet nezpracovaných → další fáze

Author: Claude Code
Date: 2025-12-16
"""
import tkinter as tk
from tkinter import ttk
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
import subprocess

class MonitorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("📊 MAJ Processing Monitor")
        self.root.geometry("900x700")
        self.root.configure(bg='#0d1117')

        self.running = True
        self.start_time = time.time()

        self.setup_styles()
        self.create_widgets()
        self.start_update_thread()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#0d1117')
        style.configure('TLabel', background='#0d1117', foreground='#c9d1d9', font=('Monaco', 10))
        style.configure('Title.TLabel', font=('Helvetica', 14, 'bold'), foreground='#58a6ff')
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'), foreground='#8b949e')
        style.configure('Success.TLabel', foreground='#3fb950')
        style.configure('Warning.TLabel', foreground='#d29922')
        style.configure('Error.TLabel', foreground='#f85149')
        style.configure('TProgressbar', troughcolor='#21262d', background='#238636')

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(title_frame, text="📊 MAJ Email/Document Processing Monitor",
                  style='Title.TLabel').pack(side='left')

        self.status_label = ttk.Label(title_frame, text="● RUNNING", style='Success.TLabel')
        self.status_label.pack(side='right')

        # === DATA FLOW ===
        flow_frame = ttk.LabelFrame(self.root, text=" 📂 Data Flow ", padding=10)
        flow_frame.pack(fill='x', padx=20, pady=5)

        self.flow_text = tk.Text(flow_frame, height=4, bg='#161b22', fg='#8b949e',
                                  font=('Monaco', 10), relief='flat')
        self.flow_text.pack(fill='x')
        self.flow_text.insert('1.0', """
  📧 Thunderbird ──rsync──▶ DGX:/home/puzik/thunderbird-emails/
  📄 OneDrive    ──rsync──▶ DGX:/home/puzik/almquist-rag-v3/documents/
  📄 Dropbox     ──rsync──▶ DGX:/home/puzik/almquist-rag-v3/documents/
  📄 ACASIS      ──rsync──▶ DGX:/home/puzik/almquist-rag-v3/documents/
""")
        self.flow_text.config(state='disabled')

        # === PHASE PROGRESS ===
        progress_frame = ttk.LabelFrame(self.root, text=" ⚙️ Phase Progress ", padding=10)
        progress_frame.pack(fill='both', expand=True, padx=20, pady=5)

        # Phase headers
        headers = ["Phase", "Status", "Progress", "Success", "Failed", "→Next", "ETA"]
        header_frame = ttk.Frame(progress_frame)
        header_frame.pack(fill='x')

        widths = [150, 80, 200, 80, 80, 80, 100]
        for i, (header, width) in enumerate(zip(headers, widths)):
            ttk.Label(header_frame, text=header, style='Header.TLabel',
                     width=width//8).pack(side='left', padx=2)

        # Phase rows
        self.phases = {}
        phase_configs = [
            ("phase1", "Phase 1: Docling", "#238636"),
            ("phase2", "Phase 2: LLM 32B", "#1f6feb"),
            ("phase3", "Phase 3: GPT-4", "#8957e5"),
            ("phase4", "Phase 4: Manual", "#d29922"),
            ("phase5", "Phase 5: Import", "#f85149"),
        ]

        for phase_id, phase_name, color in phase_configs:
            row = ttk.Frame(progress_frame)
            row.pack(fill='x', pady=3)

            phase_data = {
                "name": ttk.Label(row, text=phase_name, width=18),
                "status": ttk.Label(row, text="⏳ Waiting", width=10),
                "progress": ttk.Progressbar(row, length=180, mode='determinate'),
                "success": ttk.Label(row, text="0", width=10, style='Success.TLabel'),
                "failed": ttk.Label(row, text="0", width=10, style='Error.TLabel'),
                "next": ttk.Label(row, text="0", width=10, style='Warning.TLabel'),
                "eta": ttk.Label(row, text="--:--", width=12),
            }

            phase_data["name"].pack(side='left', padx=2)
            phase_data["status"].pack(side='left', padx=2)
            phase_data["progress"].pack(side='left', padx=2)
            phase_data["success"].pack(side='left', padx=2)
            phase_data["failed"].pack(side='left', padx=2)
            phase_data["next"].pack(side='left', padx=2)
            phase_data["eta"].pack(side='left', padx=2)

            self.phases[phase_id] = phase_data

        # === STATISTICS ===
        stats_frame = ttk.LabelFrame(self.root, text=" 📈 Statistics ", padding=10)
        stats_frame.pack(fill='x', padx=20, pady=5)

        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill='x')

        # Row 1
        self.total_docs = self.create_stat(stats_grid, "📄 Total Documents:", "0", 0, 0)
        self.processed = self.create_stat(stats_grid, "✅ Processed:", "0", 0, 1)
        self.success_rate = self.create_stat(stats_grid, "📊 Success Rate:", "0%", 0, 2)

        # Row 2
        self.labels_found = self.create_stat(stats_grid, "🏷️ Labels Found:", "0", 1, 0)
        self.isdoc_generated = self.create_stat(stats_grid, "📋 ISDOC Generated:", "0", 1, 1)
        self.elapsed_time = self.create_stat(stats_grid, "⏱️ Elapsed:", "00:00:00", 1, 2)

        # === LABEL BREAKDOWN ===
        labels_frame = ttk.LabelFrame(self.root, text=" 🏷️ Labels by Type ", padding=10)
        labels_frame.pack(fill='x', padx=20, pady=5)

        self.labels_text = tk.Text(labels_frame, height=3, bg='#161b22', fg='#8b949e',
                                   font=('Monaco', 9), relief='flat')
        self.labels_text.pack(fill='x')

        # === CONTROLS ===
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill='x', padx=20, pady=10)

        tk.Button(control_frame, text="🔄 Refresh", command=self.update_display,
                 bg='#238636', fg='white', font=('Helvetica', 10)).pack(side='left', padx=5)

        tk.Button(control_frame, text="⏸️ Pause All", command=self.pause_all,
                 bg='#d29922', fg='white', font=('Helvetica', 10)).pack(side='left', padx=5)

        tk.Button(control_frame, text="▶️ Resume All", command=self.resume_all,
                 bg='#1f6feb', fg='white', font=('Helvetica', 10)).pack(side='left', padx=5)

        tk.Button(control_frame, text="🛑 Stop All", command=self.stop_all,
                 bg='#f85149', fg='white', font=('Helvetica', 10)).pack(side='left', padx=5)

        tk.Button(control_frame, text="📋 Open Logs", command=self.open_logs,
                 bg='#8957e5', fg='white', font=('Helvetica', 10)).pack(side='right', padx=5)

    def create_stat(self, parent, label, value, row, col):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, padx=20, pady=5, sticky='w')
        ttk.Label(frame, text=label, style='Header.TLabel').pack(side='left')
        val_label = ttk.Label(frame, text=value, font=('Monaco', 11, 'bold'))
        val_label.pack(side='left', padx=5)
        return val_label

    def start_update_thread(self):
        def update_loop():
            while self.running:
                self.root.after(0, self.update_display)
                time.sleep(2)

        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()

    def update_display(self):
        """Update all displays with current data"""
        try:
            # Read status files
            base = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output")

            # Update elapsed time
            elapsed = int(time.time() - self.start_time)
            self.elapsed_time.config(text=str(timedelta(seconds=elapsed)))

            # Read phase stats
            stats_file = base / "current_stats.json"
            if stats_file.exists():
                with open(stats_file) as f:
                    stats = json.load(f)

                self.total_docs.config(text=f"{stats.get('total', 0):,}")
                self.processed.config(text=f"{stats.get('processed', 0):,}")

                total = stats.get('total', 1)
                processed = stats.get('processed', 0)
                rate = (processed / total * 100) if total > 0 else 0
                self.success_rate.config(text=f"{rate:.1f}%")

                self.labels_found.config(text=f"{stats.get('labels', 0):,}")
                self.isdoc_generated.config(text=f"{stats.get('isdoc', 0):,}")

                # Update phase progress
                for phase_id, phase_data in stats.get('phases', {}).items():
                    if phase_id in self.phases:
                        p = self.phases[phase_id]
                        p["status"].config(text=phase_data.get('status', 'Waiting'))
                        p["progress"]['value'] = phase_data.get('progress', 0)
                        p["success"].config(text=str(phase_data.get('success', 0)))
                        p["failed"].config(text=str(phase_data.get('failed', 0)))
                        p["next"].config(text=str(phase_data.get('to_next', 0)))
                        p["eta"].config(text=phase_data.get('eta', '--:--'))

                # Update labels breakdown
                labels = stats.get('labels_by_type', {})
                if labels:
                    self.labels_text.config(state='normal')
                    self.labels_text.delete('1.0', 'end')
                    label_str = "  ".join([f"{k}: {v}" for k, v in sorted(labels.items(), key=lambda x: -x[1])])
                    self.labels_text.insert('1.0', label_str)
                    self.labels_text.config(state='disabled')

        except Exception as e:
            pass  # Silently ignore read errors

    def pause_all(self):
        subprocess.run(["pkill", "-STOP", "-f", "phase[1-5]"])
        self.status_label.config(text="● PAUSED", style='Warning.TLabel')

    def resume_all(self):
        subprocess.run(["pkill", "-CONT", "-f", "phase[1-5]"])
        self.status_label.config(text="● RUNNING", style='Success.TLabel')

    def stop_all(self):
        subprocess.run(["pkill", "-f", "phase[1-5]"])
        self.status_label.config(text="● STOPPED", style='Error.TLabel')
        self.running = False

    def open_logs(self):
        log_dir = "/Volumes/ACASIS/apps/maj-document-recognition/phase1_output"
        subprocess.Popen(["open", log_dir])

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = MonitorGUI()
    app.run()
