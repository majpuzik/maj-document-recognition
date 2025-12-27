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
GUI Launcher for MAJ-EMAIL-DOCU-AI-LOAD
========================================
Vstupní GUI pro výběr zpracování emailů nebo dokumentů.
S možností omezení podle počtu nebo datumu.
+ Test Paperless DB pro kontrolu custom fields.

Používá existující src/integrations/paperless_api.py

Author: Claude Code
Date: 2025-12-16
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
import subprocess
import threading
import json
import sys
from pathlib import Path

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Paperless configurations
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

# 31 Required Custom Fields
REQUIRED_FIELDS = [
    "doc_typ", "protistrana_nazev", "protistrana_ico", "protistrana_typ",
    "castka_celkem", "datum_dokumentu", "cislo_dokumentu", "mena",
    "stav_platby", "datum_splatnosti", "kategorie", "email_from",
    "email_to", "email_subject", "od_osoba", "od_osoba_role",
    "od_firma", "pro_osoba", "pro_osoba_role", "pro_firma",
    "predmet", "ai_summary", "ai_keywords", "ai_popis",
    "typ_sluzby", "nazev_sluzby", "predmet_typ", "predmet_nazev",
    "polozky_text", "polozky_json", "perioda"
]

# Field types for auto-creation
FIELD_TYPES = {
    "castka_celkem": "float",
    "datum_dokumentu": "date",
    "datum_splatnosti": "date",
}


class LauncherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MAJ Email/Document AI Loader")
        self.root.geometry("700x700")
        self.root.configure(bg='#1e1e1e')

        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#1e1e1e')
        style.configure('TLabel', background='#1e1e1e', foreground='#ffffff', font=('Helvetica', 11))
        style.configure('Title.TLabel', font=('Helvetica', 16, 'bold'), foreground='#4fc3f7')
        style.configure('Subtitle.TLabel', font=('Helvetica', 12, 'bold'), foreground='#81c784')
        style.configure('TButton', font=('Helvetica', 11), padding=10)
        style.configure('TRadiobutton', background='#1e1e1e', foreground='#ffffff', font=('Helvetica', 11))
        style.configure('TCheckbutton', background='#1e1e1e', foreground='#ffffff', font=('Helvetica', 11))
        style.configure('TEntry', font=('Helvetica', 11))
        style.configure('TCombobox', font=('Helvetica', 11))

    def create_widgets(self):
        # Title
        title = ttk.Label(self.root, text="📧 MAJ Email/Document AI Loader", style='Title.TLabel')
        title.pack(pady=15)

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=5)

        # Tab 1: Processing
        self.create_processing_tab()

        # Tab 2: Paperless Analyzer
        self.create_analyzer_tab()

        # Status bar
        self.status_var = tk.StringVar(value="Připraveno ke spuštění...")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                               font=('Helvetica', 10), foreground='#888888')
        status_bar.pack(side='bottom', fill='x', pady=10)

    def create_processing_tab(self):
        """Create the main processing tab"""
        process_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(process_frame, text="  📥 Zpracování  ")

        # === SOURCE SELECTION ===
        source_frame = ttk.LabelFrame(process_frame, text=" 📂 Zdroj dat ", padding=10)
        source_frame.pack(fill='x', pady=5)

        self.source_var = tk.StringVar(value="emails")

        ttk.Radiobutton(source_frame, text="📧 Emaily (Thunderbird)",
                       variable=self.source_var, value="emails").pack(anchor='w', pady=2)
        ttk.Radiobutton(source_frame, text="📄 Dokumenty (OneDrive/Dropbox/ACASIS)",
                       variable=self.source_var, value="documents").pack(anchor='w', pady=2)
        ttk.Radiobutton(source_frame, text="📧📄 Obojí (emaily + dokumenty)",
                       variable=self.source_var, value="both").pack(anchor='w', pady=2)

        # === LIMIT OPTIONS ===
        limit_frame = ttk.LabelFrame(process_frame, text=" 🔢 Omezení zpracování ", padding=10)
        limit_frame.pack(fill='x', pady=5)

        # Count limit
        count_row = ttk.Frame(limit_frame)
        count_row.pack(fill='x', pady=3)

        self.use_count = tk.BooleanVar(value=False)
        ttk.Checkbutton(count_row, text="Omezit počet:", variable=self.use_count).pack(side='left')
        self.count_entry = ttk.Entry(count_row, width=10)
        self.count_entry.insert(0, "1000")
        self.count_entry.pack(side='left', padx=10)
        ttk.Label(count_row, text="dokumentů").pack(side='left')

        # Date range
        date_row = ttk.Frame(limit_frame)
        date_row.pack(fill='x', pady=3)

        self.use_date = tk.BooleanVar(value=False)
        ttk.Checkbutton(date_row, text="Omezit datem:", variable=self.use_date).pack(side='left')

        ttk.Label(date_row, text="Od:").pack(side='left', padx=(10, 5))
        self.date_from = ttk.Entry(date_row, width=12)
        self.date_from.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        self.date_from.pack(side='left')

        ttk.Label(date_row, text="Do:").pack(side='left', padx=(10, 5))
        self.date_to = ttk.Entry(date_row, width=12)
        self.date_to.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_to.pack(side='left')

        # === PHASE SELECTION ===
        phase_frame = ttk.LabelFrame(process_frame, text=" ⚙️ Fáze zpracování ", padding=10)
        phase_frame.pack(fill='x', pady=5)

        self.phase1 = tk.BooleanVar(value=True)
        self.phase2 = tk.BooleanVar(value=True)
        self.phase3 = tk.BooleanVar(value=True)
        self.phase4 = tk.BooleanVar(value=True)
        self.phase5 = tk.BooleanVar(value=True)

        phases_row1 = ttk.Frame(phase_frame)
        phases_row1.pack(fill='x')
        ttk.Checkbutton(phases_row1, text="Phase 1: Docling + ISDOC", variable=self.phase1).pack(side='left', padx=10)
        ttk.Checkbutton(phases_row1, text="Phase 2: LLM 32B + ISDOC", variable=self.phase2).pack(side='left', padx=10)

        phases_row2 = ttk.Frame(phase_frame)
        phases_row2.pack(fill='x', pady=3)
        ttk.Checkbutton(phases_row2, text="Phase 3: GPT-4", variable=self.phase3).pack(side='left', padx=10)
        ttk.Checkbutton(phases_row2, text="Phase 4: Manual", variable=self.phase4).pack(side='left', padx=10)
        ttk.Checkbutton(phases_row2, text="Phase 5: Import", variable=self.phase5).pack(side='left', padx=10)

        # === BUTTONS ===
        btn_frame = ttk.Frame(process_frame)
        btn_frame.pack(fill='x', pady=15)

        start_btn = tk.Button(btn_frame, text="▶️ SPUSTIT", command=self.start_processing,
                             bg='#4caf50', fg='white', font=('Helvetica', 12, 'bold'),
                             width=12, height=2)
        start_btn.pack(side='left', padx=5)

        monitor_btn = tk.Button(btn_frame, text="📊 MONITOR", command=self.open_monitor,
                               bg='#2196f3', fg='white', font=('Helvetica', 12, 'bold'),
                               width=12, height=2)
        monitor_btn.pack(side='left', padx=5)

        quit_btn = tk.Button(btn_frame, text="❌ KONEC", command=self.root.quit,
                            bg='#f44336', fg='white', font=('Helvetica', 12, 'bold'),
                            width=12, height=2)
        quit_btn.pack(side='right', padx=5)

    def create_analyzer_tab(self):
        """Create the Paperless analyzer tab"""
        analyzer_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(analyzer_frame, text="  🔍 Paperless Test  ")

        # === DB SELECTION ===
        db_frame = ttk.LabelFrame(analyzer_frame, text=" 📊 Paperless Instance ", padding=10)
        db_frame.pack(fill='x', pady=5)

        db_row = ttk.Frame(db_frame)
        db_row.pack(fill='x')

        ttk.Label(db_row, text="Vyberte databázi:").pack(side='left')
        self.paperless_var = tk.StringVar(value=list(PAPERLESS_CONFIGS.keys())[0])
        self.paperless_combo = ttk.Combobox(db_row, textvariable=self.paperless_var,
                                            values=list(PAPERLESS_CONFIGS.keys()),
                                            state='readonly', width=35)
        self.paperless_combo.pack(side='left', padx=10)

        test_conn_btn = tk.Button(db_row, text="🔗 Test", command=self.test_paperless_connection,
                                 bg='#607d8b', fg='white', font=('Helvetica', 10))
        test_conn_btn.pack(side='left', padx=5)

        # === ANALYSIS OPTIONS ===
        options_frame = ttk.LabelFrame(analyzer_frame, text=" ⚙️ Možnosti analýzy ", padding=10)
        options_frame.pack(fill='x', pady=5)

        opt_row = ttk.Frame(options_frame)
        opt_row.pack(fill='x')

        ttk.Label(opt_row, text="Max dokumentů (0=vše):").pack(side='left')
        self.max_docs_entry = ttk.Entry(opt_row, width=8)
        self.max_docs_entry.insert(0, "500")
        self.max_docs_entry.pack(side='left', padx=10)

        self.create_fields_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_row, text="Vytvořit chybějící fields",
                       variable=self.create_fields_var).pack(side='left', padx=20)

        # === ACTION BUTTONS ===
        action_frame = ttk.Frame(analyzer_frame)
        action_frame.pack(fill='x', pady=10)

        analyze_btn = tk.Button(action_frame, text="🔍 ANALYZOVAT",
                               command=self.run_analysis,
                               bg='#ff9800', fg='white', font=('Helvetica', 11, 'bold'),
                               width=15, height=2)
        analyze_btn.pack(side='left', padx=5)

        fix_all_btn = tk.Button(action_frame, text="🔧 OPRAVIT VŠE",
                               command=lambda: self.run_fix(fix_all=True),
                               bg='#4caf50', fg='white', font=('Helvetica', 11, 'bold'),
                               width=15, height=2)
        fix_all_btn.pack(side='left', padx=5)

        fix_selected_btn = tk.Button(action_frame, text="🔧 OPRAVIT VYBRANÉ",
                                    command=lambda: self.run_fix(fix_all=False),
                                    bg='#2196f3', fg='white', font=('Helvetica', 11, 'bold'),
                                    width=15, height=2)
        fix_selected_btn.pack(side='left', padx=5)

        # === RESULTS ===
        results_frame = ttk.LabelFrame(analyzer_frame, text=" 📋 Výsledky analýzy ", padding=10)
        results_frame.pack(fill='both', expand=True, pady=5)

        self.results_text = scrolledtext.ScrolledText(results_frame, height=15,
                                                      bg='#161b22', fg='#c9d1d9',
                                                      font=('Monaco', 9), relief='flat')
        self.results_text.pack(fill='both', expand=True)
        self.results_text.insert('1.0', "Klikněte 'ANALYZOVAT' pro spuštění testu...\n")

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(analyzer_frame, variable=self.progress_var,
                                            maximum=100, mode='determinate')
        self.progress_bar.pack(fill='x', pady=5)

    def test_paperless_connection(self):
        """Test connection to selected Paperless instance"""
        config_name = self.paperless_var.get()
        config = PAPERLESS_CONFIGS[config_name]

        self.status_var.set(f"Testuji připojení k {config_name}...")
        self.root.update()

        def test():
            try:
                import requests
                resp = requests.get(
                    f"{config['url']}/api/documents/?page_size=1",
                    headers={"Authorization": f"Token {config['api_token']}"},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    count = data.get("count", 0)
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Připojení OK",
                        f"✅ Úspěšně připojeno k {config_name}\n\nCelkem dokumentů: {count:,}"
                    ))
                    self.root.after(0, lambda: self.status_var.set(f"Připojeno: {count:,} dokumentů"))
                else:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Chyba",
                        f"❌ HTTP {resp.status_code}\n{resp.text[:200]}"
                    ))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Chyba připojení",
                    f"❌ {str(e)}"
                ))

        threading.Thread(target=test, daemon=True).start()

    def run_analysis(self):
        """Run the Paperless analysis using existing PaperlessAPI"""
        config_name = self.paperless_var.get()
        config = PAPERLESS_CONFIGS[config_name]
        max_docs = int(self.max_docs_entry.get() or 0)
        create_fields = self.create_fields_var.get()

        self.results_text.delete('1.0', 'end')
        self.results_text.insert('end', f"Analyzuji {config_name}...\n\n")
        self.progress_var.set(0)
        self.status_var.set("Analyzuji...")
        self.root.update()

        def analyze():
            try:
                # Import existing PaperlessAPI from src/integrations
                from src.integrations.paperless_api import PaperlessAPI

                # Create API instance with config
                api_config = {"paperless": config}
                api = PaperlessAPI(api_config)

                # Test connection
                if not api.test_connection():
                    self.root.after(0, lambda: self.append_result(f"❌ Připojení selhalo\n"))
                    return

                self.root.after(0, lambda: self.append_result(f"✅ Připojeno k {config['url']}\n"))

                # Progress callback
                def progress(current, total, message):
                    self.root.after(0, lambda: self.progress_var.set(current))
                    self.root.after(0, lambda: self.status_var.set(message))

                # Run analysis using extended method
                report = api.analyze_custom_fields(
                    required_fields=REQUIRED_FIELDS,
                    max_docs=max_docs,
                    progress_callback=progress
                )

                # Format results
                result_text = f"""
{'='*60}
PAPERLESS ANALYSIS REPORT
{'='*60}
URL: {report['paperless_url']}
Time: {report['timestamp']}

TOTAL DOCUMENTS: {report['total_documents']:,}
CUSTOM FIELDS IN PAPERLESS: {report['total_custom_fields']}
REQUIRED FIELDS: {len(REQUIRED_FIELDS)}
"""

                if report['missing_custom_fields']:
                    result_text += f"""
⚠️  MISSING CUSTOM FIELDS ({len(report['missing_custom_fields'])}):
"""
                    for field in report['missing_custom_fields']:
                        result_text += f"   - {field}\n"

                result_text += f"""
📊 DOCUMENTS BY COMPLETENESS:
"""
                for bucket, count in report['documents_by_completeness'].items():
                    pct = count / max(1, report['total_documents']) * 100
                    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                    result_text += f"   {bucket:8} {bar} {count:5} ({pct:.1f}%)\n"

                result_text += f"""
📋 FIELD FILL RATES (sorted):
"""
                sorted_fields = sorted(report['field_stats'].items(), key=lambda x: x[1]['fill_rate'])
                for field_name, stats in sorted_fields:
                    status = "✓" if stats['exists'] else "✗"
                    bar = "█" * int(stats['fill_rate'] / 5) + "░" * (20 - int(stats['fill_rate'] / 5))
                    result_text += f"   {status} {field_name:22} {bar} {stats['fill_rate']:5.1f}%\n"

                if report['incomplete_documents']:
                    result_text += f"""
⚠️  INCOMPLETE DOCUMENTS (top 20 of {len(report['incomplete_documents'])}):
"""
                    for doc in report['incomplete_documents'][:20]:
                        result_text += f"   [{doc['id']:5}] {doc['title'][:40]:40} {doc['completeness']:5.1f}%\n"

                result_text += f"""
{'='*60}
"""

                self.root.after(0, lambda: self.append_result(result_text))

                # Create missing fields if requested
                if create_fields and report['missing_custom_fields']:
                    self.root.after(0, lambda: self.append_result("\n🔧 Creating missing fields...\n"))
                    created = api.create_missing_custom_fields(
                        report['missing_custom_fields'],
                        FIELD_TYPES
                    )
                    self.root.after(0, lambda: self.append_result(f"   Created {len(created)} fields\n"))

                self.root.after(0, lambda: self.status_var.set("Analýza dokončena"))

                # Store report for fix operations
                self.last_report = report
                self.last_api = api

            except Exception as e:
                self.root.after(0, lambda: self.append_result(f"\n❌ Error: {str(e)}\n"))
                import traceback
                self.root.after(0, lambda: self.append_result(traceback.format_exc()))

        threading.Thread(target=analyze, daemon=True).start()

    def run_fix(self, fix_all: bool):
        """Run fix operation on documents"""
        if not hasattr(self, 'last_report') or not hasattr(self, 'last_api'):
            messagebox.showwarning("Upozornění", "Nejprve spusťte analýzu!")
            return

        incomplete = self.last_report.get('incomplete_documents', [])
        if not incomplete:
            messagebox.showinfo("Info", "Žádné neúplné dokumenty k opravě!")
            return

        if fix_all:
            msg = f"Opravit všech {len(incomplete)} neúplných dokumentů?"
        else:
            msg = "Opravit vybrané dokumenty? (funkce bude přidána)"

        if not messagebox.askyesno("Potvrdit opravu", msg):
            return

        self.append_result(f"\n🔧 Spouštím opravu...\n")
        self.status_var.set("Opravuji dokumenty...")

        # TODO: Implement actual fix logic
        # This would require re-processing documents with the extraction pipeline
        self.append_result("⚠️ Funkce opravy vyžaduje re-extrakci dat.\n")
        self.append_result("   Pro opravu spusťte: python3 email_extractor/phase6_reextract.py\n")

    def append_result(self, text: str):
        """Append text to results"""
        self.results_text.insert('end', text)
        self.results_text.see('end')

    def get_config(self):
        """Build configuration from GUI selections"""
        config = {
            "source": self.source_var.get(),
            "limit_count": int(self.count_entry.get()) if self.use_count.get() else None,
            "date_from": self.date_from.get() if self.use_date.get() else None,
            "date_to": self.date_to.get() if self.use_date.get() else None,
            "phases": {
                "phase1": self.phase1.get(),
                "phase2": self.phase2.get(),
                "phase3": self.phase3.get(),
                "phase4": self.phase4.get(),
                "phase5": self.phase5.get(),
            },
            "timestamp": datetime.now().isoformat()
        }
        return config

    def start_processing(self):
        """Start the processing pipeline"""
        config = self.get_config()

        # Save config
        config_path = Path("/Volumes/ACASIS/apps/maj-document-recognition/phase1_output/run_config.json")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        # Build command
        cmd = ["python3", "run_all_phases.py"]
        cmd.extend(["--source", config["source"]])

        if config["limit_count"]:
            cmd.extend(["--limit", str(config["limit_count"])])
        if config["date_from"]:
            cmd.extend(["--date-from", config["date_from"]])
        if config["date_to"]:
            cmd.extend(["--date-to", config["date_to"]])

        # Disable phases
        if not config["phases"]["phase1"]:
            cmd.append("--skip-phase1")
        if not config["phases"]["phase2"]:
            cmd.append("--skip-phase2")
        if not config["phases"]["phase3"]:
            cmd.append("--skip-phase3")
        if not config["phases"]["phase4"]:
            cmd.append("--skip-phase4")
        if not config["phases"]["phase5"]:
            cmd.append("--skip-phase5")

        self.status_var.set(f"Spouštím: {' '.join(cmd)}")

        # Start in background
        def run():
            subprocess.Popen(cmd, cwd="/Volumes/ACASIS/apps/maj-document-recognition")

        threading.Thread(target=run, daemon=True).start()

        # Open monitor
        self.open_monitor()

    def open_monitor(self):
        """Open the monitoring window"""
        subprocess.Popen(["python3", "email_extractor/gui_monitor.py"],
                        cwd="/Volumes/ACASIS/apps/maj-document-recognition")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = LauncherGUI()
    app.run()
