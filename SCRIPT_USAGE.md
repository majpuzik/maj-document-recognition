# MAJ-EMAIL-DOCU-AI-LOAD: Script Usage

## Overview
Přehled všech skriptů a jejich použití v pipeline.

---

## GUI (Vstup)

### `email_extractor/gui_launcher.py`
**Účel:** Vstupní GUI pro výběr zpracování
**Použití:** `python3 email_extractor/gui_launcher.py`
**Funkce:**
- Výběr zdroje: Emaily / Dokumenty / Obojí
- Omezení počtu nebo datumem
- Výběr fází (1-5)
- Spuštění pipeline
- Otevření monitoru

### `email_extractor/gui_monitor.py`
**Účel:** Real-time monitoring běžících procesů
**Použití:** `python3 email_extractor/gui_monitor.py`
**Funkce:**
- Data flow vizualizace
- Progress per fáze
- Statistiky (success/failed/labels/ISDOC)
- Pause/Resume/Stop kontroly

---

## Phase 1: Docling Extraction

### `email_extractor/phase1_docling.py`
**Účel:** Masivně paralelní text extrakce pomocí Docling
**Spuštění:**
```bash
# Mac Mini (10 procesů, range 0-32000)
python3 email_extractor/phase1_docling.py --machine mac_mini --instance 0 --start 0 --end 3200
python3 email_extractor/phase1_docling.py --machine mac_mini --instance 1 --start 3200 --end 6400
# ... až instance 9

# MacBook Pro (15 procesů, range 32000-64000)
python3 email_extractor/phase1_docling.py --machine macbook --instance 0 --start 32000 --end 34133
# ... až instance 14

# DGX (15 procesů, range 64000-95133)
python3 email_extractor/phase1_docling.py --machine dgx --instance 0 --start 64000 --end 66089
# ... až instance 14
```
**Vstup:** `/Volumes/ACASIS/parallel_scan_1124_1205/thunderbird-emails/`
**Výstup:**
- `phase1_output/phase1_results/{email_id}.json`
- `phase1_output/phase1_failed_{instance}.jsonl`
- `phase1_output/phase1_stats_{instance}.json`
- `phase1_output/isdoc_xml/{email_id}.isdoc.xml` (pro účetní dokumenty)

**Interní komponenty:**
- `FieldExtractor` - regex extrakce 31 polí
- `DoclingExtractor` - PDF text extraction
- `EmailParser` - EML parsing
- `DocumentClassifier` - regex klasifikace typu
- `isdoc_generator.generate_isdoc_for_result()` - ISDOC generování

---

## Phase 2: LLM Hierarchical

### `email_extractor/phase2_hierarchical.py`
**Účel:** AI klasifikace selhaných z Phase 1
**Model:** `czech-finance-speed (7.6B) → qwen2.5:14b → qwen2.5:32b`
**Spuštění:**
```bash
# Mac Mini (3 procesy)
python3 email_extractor/phase2_hierarchical.py --start 0 --limit 800

# MacBook Pro (5 procesů)
python3 email_extractor/phase2_hierarchical.py --start 800 --limit 500
```
**Vstup:** `phase1_output/phase2_to_process.jsonl`
**Výstup:**
- `phase1_output/phase2_results/{email_id}.json`
- `phase1_output/phase2_failed.jsonl`
- `phase1_output/isdoc_xml/{email_id}.isdoc.xml` (pro účetní dokumenty)

**Závislosti:**
- `ai_consensus_trainer.py` → `AIVoter` třída
- `isdoc_generator.py` → ISDOC generování

---

## Phase 3: GPT-4 API

### `email_extractor/phase3_gpt4.py`
**Účel:** Zpracování zbytků pomocí GPT-4o
**Lokace:** DGX (OpenAI API klíč)
**Spuštění:**
```bash
ssh dgx "cd /home/puzik/maj-document-recognition && python3 email_extractor/phase3_gpt4.py"
```
**Vstup:** `phase2_failed.jsonl`
**Výstup:**
- `phase3_results/{email_id}.json`
- `phase3_failed.jsonl`

---

## Phase 4: Manual Review

### `email_extractor/phase4_manual.py`
**Účel:** Zobrazení zbylých dokumentů uživateli
**Spuštění:** `python3 email_extractor/phase4_manual.py`
**UI:** Terminálové nebo web rozhraní
**Vstup:** `phase3_failed.jsonl`
**Výstup:** `phase4_results/{email_id}.json`

---

## Phase 5: Paperless Import

### `email_extractor/phase5_import.py`
**Účel:** Import do Paperless-NGX
**Spuštění:** `python3 email_extractor/phase5_import.py`
**Paperless:** `http://192.168.10.200:8020`
**Funkce:**
- Spojí výsledky ze všech fází
- MD5 deduplikace
- Vytvoří/najde tagy, korespondenty
- Nastaví 31 custom fields
- Upload dokumentů

**Závislosti:**
- `src/integrations/paperless_api.py` - Paperless API client

---

## ISDOC Generation

### `email_extractor/isdoc_generator.py`
**Účel:** Wrapper pro generování ISDOC XML
**Volá se z:** Phase 1, Phase 2
**Typy:** `invoice`, `receipt`, `tax_document`, `bank_statement`
**Výstup:** `phase1_output/isdoc_xml/{email_id}.isdoc.xml`

**Závislosti:**
- `src/integrations/llm_metadata_extractor.py` → `ISDOCGenerator`, `ISDOCInvoiceData`

---

## Monitoring & Logging

### `email_extractor/monitor.py`
**Účel:** CLI progress monitor
**Spuštění:**
```bash
python3 email_extractor/monitor.py --status
python3 email_extractor/monitor.py --check-resources
```

### `email_extractor/cdb_logger.py`
**Účel:** SQLite logging na DGX
**DB:** `/home/puzik/almquist-central-log/almquist.db`
**Tabulka:** `email_extraction_runs`

### `email_extractor/resource_manager.py`
**Účel:** CPU/RAM throttling (85% limit)

---

## Orchestration

### `run_all_phases.py`
**Účel:** Hlavní orchestrátor všech fází
**Spuštění:**
```bash
# Celý pipeline
python3 run_all_phases.py

# Od konkrétní fáze
python3 run_all_phases.py --start-phase 3

# S limity
python3 run_all_phases.py --source emails --limit 1000 --date-from 2024-01-01
```

### `launch_phase1.sh`
**Účel:** Spouštěč Phase 1 na všech strojích
```bash
./launch_phase1.sh  # Spustí 40 procesů na 3 strojích
```

### `launch_phase2.sh`
**Účel:** Spouštěč Phase 2 (bez DGX)
```bash
./launch_phase2.sh  # Spustí 8 procesů na Mac Mini + MacBook
```

---

## Existující utility (použité)

| Soubor | Účel | Použito v |
|--------|------|-----------|
| `src/integrations/paperless_api.py` | Paperless API client | Phase 5 |
| `src/integrations/llm_metadata_extractor.py` | ISDOC generátor | isdoc_generator.py |
| `src/ocr/extraction_schemas.py` | Field definice | Phase 1 |
| `src/ai/ollama_classifier.py` | LLM klasifikace | - |
| `ai_consensus_trainer.py` | AIVoter hierarchical | Phase 2 |

---

## n8n Workflow

### `n8n-workflow-maj-email-docu-ai-load.json`
**Účel:** n8n workflow pro automatizaci
**Import:**
```bash
n8n import:workflow --input=n8n-workflow-maj-email-docu-ai-load.json
```
**Nodes:**
- Trigger (6h interval + manual)
- Branch Router (emails/documents)
- Rsync nodes
- Phase launchers
- Monitors
- CDB Logger

---

## Flow Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                              VSTUP                                        │
│                      gui_launcher.py                                      │
│           ┌─────────────────┴─────────────────┐                          │
│           ▼                                   ▼                          │
│    Emaily (Thunderbird)              Dokumenty (OneDrive/...)            │
│           │                                   │                          │
│           └─────────────┬─────────────────────┘                          │
│                         ▼                                                │
├───────────────────────────────────────────────────────────────────────────┤
│  PHASE 1: phase1_docling.py + isdoc_generator.py                         │
│    40 procesů na 3 strojích (Mac Mini, MacBook, DGX)                     │
│    Docling OCR + regex extrakce + ISDOC pro účetní                       │
│           │                                                              │
│    Success ──────────▶ phase1_results/*.json + isdoc_xml/*.xml          │
│    Failed ───────────▶ phase2_to_process.jsonl                          │
├───────────────────────────────────────────────────────────────────────────┤
│  PHASE 2: phase2_hierarchical.py + isdoc_generator.py                    │
│    8 procesů (Mac Mini + MacBook, BEZ DGX)                               │
│    AIVoter: 7B → 14B → 32B hierarchical consensus                        │
│           │                                                              │
│    Success ──────────▶ phase2_results/*.json + isdoc_xml/*.xml          │
│    Failed ───────────▶ phase2_failed.jsonl                              │
├───────────────────────────────────────────────────────────────────────────┤
│  PHASE 3: phase3_gpt4.py (na DGX)                                        │
│    GPT-4o API pro nejtěžší případy                                       │
│           │                                                              │
│    Success ──────────▶ phase3_results/*.json                            │
│    Failed ───────────▶ phase3_failed.jsonl                              │
├───────────────────────────────────────────────────────────────────────────┤
│  PHASE 4: phase4_manual.py                                               │
│    Manuální review zbytků                                                │
│           │                                                              │
│    Success ──────────▶ phase4_results/*.json                            │
├───────────────────────────────────────────────────────────────────────────┤
│  PHASE 5: phase5_import.py                                               │
│    Import do Paperless-NGX (192.168.10.200:8020)                         │
│    31 custom fields, tagy, korespondenti                                 │
│           │                                                              │
│           ▼                                                              │
│    Paperless-NGX + CDB Log (SQLite)                                      │
├───────────────────────────────────────────────────────────────────────────┤
│                          MONITORING                                       │
│           gui_monitor.py | monitor.py | cdb_logger.py                    │
└───────────────────────────────────────────────────────────────────────────┘
```
