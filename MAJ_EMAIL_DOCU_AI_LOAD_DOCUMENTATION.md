# MAJ-EMAIL-DOCU-AI-LOAD: Kompletní Dokumentace

**Verze:** 1.1.0
**Datum:** 2025-12-16
**Autor:** Claude Code
**GitHub:** https://github.com/majpuzik/maj-email-docu-ai-load (private)
**CDB ID:** 6

---

## 1. PŘEHLED SYSTÉMU

### 1.1 Účel
Systém MAJ-EMAIL-DOCU-AI-LOAD slouží k automatizovanému zpracování emailů a dokumentů s následujícími cíli:
- Extrakce textu z emailů a PDF příloh
- AI klasifikace typu dokumentu
- Extrakce strukturovaných dat (31 custom fields)
- Generování ISDOC XML pro účetní dokumenty
- Import do Paperless-NGX s plnou metadatou

### 1.2 Architektura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         VSTUPNÍ DATA                                │
├─────────────────────────────────────────────────────────────────────┤
│  Thunderbird Emaily          │  Dokumenty (OneDrive/Dropbox/ACASIS) │
│  ~95,000 emailů              │  PDF, DOC, JPG, PNG                  │
│  /parallel_scan_1124_1205/   │  /ACASIS/Dokumenty/                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PHASE 1: DOCLING EXTRACTION                    │
│  40 paralelních procesů na 3 strojích                              │
│  ├── Mac Mini M4 (10 procesů)   - Docling + regex                  │
│  ├── MacBook Pro (15 procesů)   - Docling + regex                  │
│  └── DGX H100 (15 procesů)      - Docling + regex                  │
│                                                                     │
│  Výstup: phase1_results/*.json + isdoc_xml/*.xml                   │
│  Selhané: phase2_to_process.jsonl                                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: LLM HIERARCHICAL                        │
│  8 procesů (Mac Mini + MacBook, BEZ DGX)                           │
│                                                                     │
│  AIVoter Hierarchical:                                             │
│  ├── Level 1: czech-finance-speed (7.6B) - rychlý CZ specialist   │
│  ├── Level 2: qwen2.5:14b - validace                               │
│  └── Level 3: qwen2.5:32b - arbitr (pokud 1+2 nesouhlasí)         │
│                                                                     │
│  Výstup: phase2_results/*.json + isdoc_xml/*.xml                   │
│  Selhané: phase2_failed.jsonl                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PHASE 3: GPT-4 API                             │
│  Běží na DGX (OpenAI API klíč)                                     │
│  Pro nejtěžší případy kde lokální LLM selhaly                      │
│                                                                     │
│  Výstup: phase3_results/*.json                                     │
│  Selhané: phase3_failed.jsonl                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PHASE 4: MANUAL REVIEW                          │
│  Terminálové/webové UI pro manuální klasifikaci zbytků             │
│                                                                     │
│  Výstup: phase4_results/*.json                                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   PHASE 5: PAPERLESS IMPORT                         │
│  Import do Paperless-NGX (192.168.10.200:8020)                     │
│                                                                     │
│  ├── MD5 deduplikace                                               │
│  ├── Vytvoření tagů, korespondentů                                 │
│  ├── Nastavení 31 custom fields                                    │
│  └── Upload dokumentů + ISDOC                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         VÝSTUP                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Paperless-NGX           │  CDB SQLite Log                         │
│  http://192.168.10.200   │  /home/puzik/almquist-central-log/      │
│  :8020                   │  almquist.db                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. CHRONOLOGICKÝ PRŮBĚH ZPRACOVÁNÍ

### 2.1 Krok 1: Příprava dat

**Zdroj emailů:**
```
/Volumes/ACASIS/parallel_scan_1124_1205/thunderbird-emails/
├── 127.0.0.1/
│   ├── 2024-01-15_abc123_Subject_here/
│   │   ├── message.eml
│   │   └── attachment.pdf
│   └── ...
└── ...
```

**Formát složky:** `{YYYY-MM-DD}_{email_id}_{subject_sanitized}/`

### 2.2 Krok 2: Spuštění GUI Launcheru

```bash
cd /Volumes/ACASIS/apps/maj-document-recognition
python3 email_extractor/gui_launcher.py
```

**GUI nabízí:**
- Tab 1: Výběr zdroje (emaily/dokumenty/obojí)
- Tab 1: Omezení (počet, datum)
- Tab 1: Výběr fází (1-5)
- Tab 2: Test Paperless DB (31 custom fields)

### 2.3 Krok 3: Phase 1 - Docling Extraction

**Spuštění na všech strojích:**
```bash
# Mac Mini M4 (10 procesů, range 0-32000)
for i in {0..9}; do
  start=$((i * 3200))
  end=$(((i + 1) * 3200))
  python3 email_extractor/phase1_docling.py \
    --machine mac_mini --instance $i \
    --start $start --end $end &
done

# MacBook Pro (15 procesů, range 32000-64000)
for i in {0..14}; do
  start=$((32000 + i * 2133))
  end=$((32000 + (i + 1) * 2133))
  python3 email_extractor/phase1_docling.py \
    --machine macbook --instance $i \
    --start $start --end $end &
done

# DGX (15 procesů, range 64000-95133)
ssh dgx "cd /home/puzik/maj-document-recognition && \
  for i in {0..14}; do
    start=$((64000 + i * 2089))
    end=$((64000 + (i + 1) * 2089))
    python3 email_extractor/phase1_docling.py \
      --machine dgx --instance \$i \
      --start \$start --end \$end &
  done"
```

**Co Phase 1 dělá:**
1. Načte `message.eml` z každé složky
2. Parsuje email (from, to, subject, date, body)
3. Najde PDF přílohy ve složce
4. Pro každé PDF → Docling OCR extrakce
5. Spojí email_body + pdf_text
6. Klasifikuje typ dokumentu (regex patterns)
7. Extrahuje 31 custom fields pomocí `FieldExtractor`
8. Generuje ISDOC XML pro účetní dokumenty
9. Uloží výsledek nebo zapíše do failed

**Výstupní soubory:**
```
phase1_output/
├── phase1_results/
│   ├── {email_id}.json
│   └── ...
├── isdoc_xml/
│   ├── {email_id}.isdoc.xml
│   └── ...
├── phase1_failed_0.jsonl
├── phase1_failed_1.jsonl
├── ...
├── phase1_stats_0.json
├── phase1_stats_1.json
└── phase2_to_process.jsonl  (spojené selhané)
```

### 2.4 Krok 4: Phase 2 - LLM Hierarchical

**Spuštění (po dokončení Phase 1):**
```bash
# Mac Mini (3 procesy)
python3 email_extractor/phase2_hierarchical.py --start 0 --limit 800 &
python3 email_extractor/phase2_hierarchical.py --start 800 --limit 800 &
python3 email_extractor/phase2_hierarchical.py --start 1600 --limit 800 &

# MacBook Pro (5 procesů)
python3 email_extractor/phase2_hierarchical.py --start 2400 --limit 500 &
# ...
```

**AIVoter Hierarchical Mode:**
```python
# Level 1: Rychlý specialist
response1 = ollama.chat("czech-finance-speed", prompt)

# Level 2: Validace
response2 = ollama.chat("qwen2.5:14b", prompt)

# Level 3: Arbitr (pouze pokud 1 != 2)
if response1 != response2:
    response3 = ollama.chat("qwen2.5:32b", prompt)
    return majority_vote(response1, response2, response3)
else:
    return response1  # consensus
```

### 2.5 Krok 5: Phase 3 - GPT-4 API

**Spuštění na DGX:**
```bash
ssh dgx "cd /home/puzik/maj-document-recognition && \
  python3 email_extractor/phase3_gpt4.py"
```

**Používá OpenAI API pro nejtěžší případy.**

### 2.6 Krok 6: Phase 4 - Manual Review

```bash
python3 email_extractor/phase4_manual.py
```

**Zobrazí zbylé dokumenty uživateli pro manuální klasifikaci.**

### 2.7 Krok 7: Phase 5 - Paperless Import

```bash
python3 email_extractor/phase5_import.py
```

**Co Phase 5 dělá:**
1. Spojí výsledky ze všech fází
2. MD5 deduplikace
3. Pro každý dokument:
   - Najde/vytvoří tagy
   - Najde/vytvoří korespondenta
   - Nastaví 31 custom fields
   - Upload do Paperless

---

## 3. 31 CUSTOM FIELDS

| # | Field Name | Typ | Popis |
|---|------------|-----|-------|
| 1 | doc_typ | string | Typ dokumentu (faktura, smlouva, ...) |
| 2 | protistrana_nazev | string | Název protistrany |
| 3 | protistrana_ico | string | IČO protistrany |
| 4 | protistrana_typ | string | Typ (firma, OSVČ, FO) |
| 5 | castka_celkem | float | Celková částka |
| 6 | datum_dokumentu | date | Datum dokumentu |
| 7 | cislo_dokumentu | string | Číslo dokumentu |
| 8 | mena | string | Měna (CZK, EUR, USD) |
| 9 | stav_platby | string | Stav (zaplaceno, nezaplaceno) |
| 10 | datum_splatnosti | date | Datum splatnosti |
| 11 | kategorie | string | Kategorie dokumentu |
| 12 | email_from | string | Email odesílatele |
| 13 | email_to | string | Email příjemce |
| 14 | email_subject | string | Předmět emailu |
| 15 | od_osoba | string | Jméno odesílatele |
| 16 | od_osoba_role | string | Role odesílatele |
| 17 | od_firma | string | Firma odesílatele |
| 18 | pro_osoba | string | Jméno příjemce |
| 19 | pro_osoba_role | string | Role příjemce |
| 20 | pro_firma | string | Firma příjemce |
| 21 | predmet | string | Předmět/účel |
| 22 | ai_summary | string | AI souhrn |
| 23 | ai_keywords | string | AI klíčová slova |
| 24 | ai_popis | string | AI popis obsahu |
| 25 | typ_sluzby | string | Typ služby |
| 26 | nazev_sluzby | string | Název služby |
| 27 | predmet_typ | string | Typ předmětu |
| 28 | predmet_nazev | string | Název předmětu |
| 29 | polozky_text | string | Položky (text) |
| 30 | polozky_json | string | Položky (JSON) |
| 31 | perioda | string | Období |

---

## 4. ISDOC GENEROVÁNÍ

### 4.1 Kdy se generuje ISDOC

ISDOC XML se generuje automaticky pro tyto typy dokumentů:
- `invoice` (faktura)
- `receipt` (účtenka)
- `tax_document` (daňový doklad)
- `bank_statement` (bankovní výpis)

### 4.2 ISDOC Formát

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="http://isdoc.cz/namespace/2013" version="6.0.2">
  <DocumentType>1</DocumentType>
  <ID>{cislo_dokumentu}</ID>
  <IssueDate>{datum_dokumentu}</IssueDate>
  <AccountingSupplierParty>
    <Party>
      <PartyName><Name>{protistrana_nazev}</Name></PartyName>
      <PartyIdentification><ID>{protistrana_ico}</ID></PartyIdentification>
    </Party>
  </AccountingSupplierParty>
  <LegalMonetaryTotal>
    <TaxInclusiveAmount currencyID="{mena}">{castka_celkem}</TaxInclusiveAmount>
  </LegalMonetaryTotal>
</Invoice>
```

---

## 5. MONITORING

### 5.1 GUI Monitor

```bash
python3 email_extractor/gui_monitor.py
```

**Zobrazuje:**
- Data flow vizualizaci
- Progress per fáze
- Statistiky (success/failed/labels/ISDOC)
- Pause/Resume/Stop kontroly

### 5.2 CLI Monitor

```bash
python3 email_extractor/monitor.py --status
python3 email_extractor/monitor.py --check-resources
```

### 5.3 CDB Logging

```python
# Logging do SQLite na DGX
from email_extractor.cdb_logger import CDBLogger

logger = CDBLogger()
logger.log_run(
    phase="phase1",
    machine="mac_mini",
    instance=0,
    total=3200,
    success=3150,
    failed=50,
    stats={"isdoc_generated": 234}
)
```

**DB lokace:** `/home/puzik/almquist-central-log/almquist.db`

**Tabulka:** `email_extraction_runs`

---

## 6. STROJE A KAPACITY

| Stroj | CPU | RAM | GPU | Docling venv | Procesy |
|-------|-----|-----|-----|--------------|---------|
| Mac Mini M4 | 14 cores | 64GB | - | ~/.venvs/docling | 10 |
| MacBook Pro M3 | 16 cores | 128GB | - | system python | 15 |
| DGX H100 | 20 cores | 120GB | H100 | /home/puzik/venv-docling | 15 |

### 6.1 Resource Management (Basic)

```python
from email_extractor.resource_manager import ResourceManager

rm = ResourceManager(cpu_limit=85, ram_limit=85)
rm.start()  # Auto-throttling při překročení limitů
```

### 6.2 Advanced Resource Management (v1.1.0)

**Nový soubor:** `email_extractor/advanced_resource_manager.py`

```python
from email_extractor.advanced_resource_manager import (
    AdvancedResourceManager, ResourceLimits
)

manager = AdvancedResourceManager(
    limits=ResourceLimits(
        max_cpu_percent=85.0,
        max_ram_percent=85.0,
        max_gpu_percent=90.0,
        min_disk_free_gb=10.0
    ),
    status_callback=on_status_update,    # UI update callback
    throttle_callback=on_throttle_change, # Throttle notification
    disk_paths=["/", "/Volumes/ACASIS"]
)

manager.start_monitoring(interval=2.0)
```

**Funkce:**

| Feature | Popis |
|---------|-------|
| CPU monitoring | `psutil.cpu_percent()` |
| RAM monitoring | `psutil.virtual_memory()` |
| GPU monitoring | NVIDIA: `nvidia-smi`, Apple: `ioreg/system_profiler` |
| Disk monitoring | `psutil.disk_usage()` pro více cest |
| Auto-throttling | Pozastavení při překročení limitů |
| UI callback | `status_callback(FullResourceStatus)` |
| Throttle notification | `throttle_callback(is_throttled, reason)` |
| Dynamic instances | `_calculate_instances()` dle zatížení |

### 6.3 GPU Monitoring

```python
from email_extractor.advanced_resource_manager import GPUMonitor

gpu = GPUMonitor()
status = gpu.get_status()

# NVIDIA GPU
print(f"GPU: {status.name}")
print(f"Utilization: {status.utilization_percent}%")
print(f"Memory: {status.memory_used_mb}/{status.memory_total_mb} MB")
print(f"Temperature: {status.temperature_c}°C")

# Apple Metal GPU
print(f"GPU: {status.name}")  # "Apple M4 GPU"
print(f"Utilization: {status.utilization_percent}%")  # Odhad z ioreg
```

### 6.4 Dynamic Instance Calculator

```python
# Automatický výpočet doporučeného počtu instancí
status = manager.get_full_status()

print(f"Doporučené instance: {status.recommended_instances}")
print(f"Max bezpečné instance: {status.max_safe_instances}")

# Algoritmus:
# 1. Base capacity = min(CPU_cores/2, RAM_GB/4)
# 2. Scale by available resources (100 - current_usage)
# 3. Adjust for GPU if available
```

### 6.5 Network AI Server Discovery

```python
from email_extractor.advanced_resource_manager import AIServerDiscovery

discovery = AIServerDiscovery()
servers = discovery.discover(timeout=2.0)

for server in servers:
    print(f"{server.name} ({server.host}:{server.port})")
    print(f"  Status: {'ONLINE' if server.is_reachable else 'OFFLINE'}")
    print(f"  Models: {', '.join(server.models)}")
```

**Předdefinované servery:**
| Server | Host | Port | Popis |
|--------|------|------|-------|
| Local Ollama | localhost | 11434 | Lokální instance |
| DGX H100 | 192.168.10.130 | 11434 | GPU server |
| Mac Mini M4 | 192.168.10.131 | 11434 | Mac Mini |
| MacBook Pro | 192.168.10.132 | 11434 | MacBook |
| NAS5 | 192.168.10.35 | 11434 | NAS server |

### 6.6 Advanced GUI (v1.1.0)

**Nový soubor:** `email_extractor/gui_advanced.py`

```bash
python3 email_extractor/gui_advanced.py
```

**Komponenty:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  LEVÝ PANEL                   │  PRAVÝ PANEL                        │
├───────────────────────────────┼─────────────────────────────────────┤
│  ResourceMonitorWidget        │  Notebook Tabs                      │
│  ├── CPU: [████████░░] 78%    │  ├── Tab: Processing                │
│  ├── RAM: [██████░░░░] 62%    │  │   ├── Source selection           │
│  ├── GPU: [████░░░░░░] 45%    │  │   ├── Limit options              │
│  ├── Disk: 234 GB free        │  │   ├── Auto-instances checkbox    │
│  ├── Instance: 8/12           │  │   └── Phase checkboxes           │
│  └── Status: ● OK             │  │                                   │
│                               │  └── Tab: Monitoring                │
│  AIServerPanel                │      └── Log output                 │
│  ├── [✓] DGX H100    ONLINE   │                                     │
│  ├── [✓] Mac Mini    ONLINE   │  ┌─────────────────────────────────┐│
│  ├── [ ] MacBook     OFFLINE  │  │ THROTTLE BANNER (červený)       ││
│  └── [Discover] [All] [None]  │  │ SYSTEM OVERLOADED: CPU 92%      ││
│                               │  └─────────────────────────────────┘│
└───────────────────────────────┴─────────────────────────────────────┘
```

**UI Features:**
- Real-time progress bary pro CPU/RAM/GPU/Disk
- Barevné kódování (zelená < 70%, žlutá < 85%, červená ≥ 85%)
- Doporučený počet instancí dle zatížení
- Seznam AI serverů s checkboxy
- Červený banner při přetížení systému
- Auto-pause/resume při throttlingu

---

## 7. PAPERLESS KONFIGURACE

### 7.1 Instance

| Instance | URL | Token |
|----------|-----|-------|
| Production | http://192.168.10.200:8020 | d06a165d1a496a09ea8b5e70e3a0554702f20f53 |
| Development | http://192.168.10.85:8777 | 0c1072a02c43c50d109a0300f090a361fc1eb775 |

### 7.2 Test Custom Fields

```bash
# V GUI Launcher - Tab "Paperless Test"
# Nebo přímo:
python3 -c "
from src.integrations.paperless_api import PaperlessAPI
api = PaperlessAPI({'paperless': {
    'url': 'http://192.168.10.200:8020',
    'api_token': 'd06a165d1a496a09ea8b5e70e3a0554702f20f53'
}})
report = api.analyze_custom_fields(REQUIRED_FIELDS)
print(report)
"
```

---

## 8. n8n WORKFLOW

### 8.1 Import workflow

```bash
n8n import:workflow --input=n8n-workflow-maj-email-docu-ai-load.json
```

### 8.2 Workflow struktura

```
Trigger (6h + Manual)
    │
    ├─► Email Branch ──► Phase 1 ──► Phase 2 ──► Phase 3 ─┐
    │                                                       │
    └─► Document Branch ─────────────────────────────────┐ │
                                                          │ │
                                                          ▼ ▼
                                              Phase 4 Manual Review
                                                          │
                                                          ▼
                                              Phase 5 Paperless Import
                                                          │
                                                          ▼
                                                    CDB Logger
```

---

## 9. SEZNAM SKRIPTŮ

### 9.1 Hlavní skripty (email_extractor/)

| Skript | Účel |
|--------|------|
| `gui_launcher.py` | Vstupní GUI pro spuštění pipeline |
| `gui_monitor.py` | Real-time monitoring |
| `phase1_docling.py` | Masivní paralelní Docling extrakce |
| `phase2_hierarchical.py` | AIVoter hierarchical LLM |
| `phase3_gpt4.py` | GPT-4 API fallback |
| `phase5_import.py` | Paperless import |
| `phase6_fix_tags.py` | Oprava tagů |
| `field_extractor.py` | Extrakce 31 polí |
| `isdoc_generator.py` | ISDOC XML generátor |
| `cdb_logger.py` | SQLite logging |
| `monitor.py` | CLI monitoring |
| `resource_manager.py` | CPU/RAM throttling |
| `advanced_resource_manager.py` | **NEW** CPU/RAM/GPU/Disk + AI discovery |
| `gui_advanced.py` | **NEW** Rozšířené GUI s monitoringem |

### 9.2 Pomocné skripty

| Skript | Účel |
|--------|------|
| `ai_consensus_trainer.py` | AIVoter třída |
| `analyze_results.py` | Analýza výsledků skenování |
| `src/integrations/paperless_api.py` | Paperless API client |
| `src/integrations/llm_metadata_extractor.py` | ISDOC generátor |

### 9.3 Shell skripty

| Skript | Účel |
|--------|------|
| `launch_phase1.sh` | Spouštěč Phase 1 na všech strojích |
| `launch_parallel_scan.sh` | Paralelní skenování |
| `sync_dgx_to_acasis.sh` | Synchronizace DGX → ACASIS |

---

## 10. INSTALACE A ZÁVISLOSTI

### 10.1 Python závislosti

```bash
pip install docling requests aiohttp tqdm \
  tkinter pillow transformers torch \
  openai anthropic
```

### 10.2 Ollama modely

```bash
ollama pull czech-finance-speed
ollama pull qwen2.5:14b
ollama pull qwen2.5:32b
```

### 10.3 Venv setup

```bash
# Mac Mini
~/.venvs/docling/bin/python

# DGX
/home/puzik/venv-docling/bin/python
```

---

## 11. TROUBLESHOOTING

### 11.1 Phase 1 selhává

```bash
# Zkontrolujte Docling
python3 -c "from docling.document_converter import DocumentConverter; print('OK')"

# Zkontrolujte RAM
python3 email_extractor/monitor.py --check-resources
```

### 11.2 Phase 2 pomalá

```bash
# Zkontrolujte Ollama
ollama list
ollama ps

# Restartujte model
ollama stop qwen2.5:32b
ollama run qwen2.5:32b
```

### 11.3 Paperless import selhává

```bash
# Test připojení
curl -H "Authorization: Token d06a165d1a496a09ea8b5e70e3a0554702f20f53" \
  http://192.168.10.200:8020/api/documents/?page_size=1
```

---

## 12. CHANGELOG

### v1.1.0 (2025-12-16)
- **NEW** Advanced Resource Manager
  - GPU monitoring (NVIDIA nvidia-smi + Apple Metal ioreg)
  - Disk space monitoring s konfigurovatelným limitem
  - Auto-throttling s UI callback notifikacemi
  - Dynamic instance calculator dle zatížení
- **NEW** Network AI Server Discovery
  - Automatické hledání Ollama serverů v síti
  - Podpora vlastních serverů
  - Enable/disable per server
- **NEW** Advanced GUI (`gui_advanced.py`)
  - Real-time resource monitoring widget
  - AI server panel s checkboxy
  - Červený throttle banner při přetížení
  - Auto-instances checkbox
- GitHub repo: https://github.com/majpuzik/maj-email-docu-ai-load
- CDB project_id: 6

### v1.0.0 (2025-12-16)
- Initial release
- 5-phase pipeline implementace
- GUI launcher a monitor
- ISDOC generování pro účetní dokumenty
- 31 custom fields extrakce
- AIVoter hierarchical consensus
- CDB SQLite logging
- n8n workflow integrace

---

*Dokumentace generována automaticky*
*MAJ-EMAIL-DOCU-AI-LOAD © 2025*
