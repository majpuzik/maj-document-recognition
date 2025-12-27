# MAJ-EMAIL-DOCU-AI-LOAD Workflow

## Přehled
Automatizovaný pipeline pro extrakci, klasifikaci a import emailů a dokumentů do Paperless-NGX.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MAJ-EMAIL-DOCU-AI-LOAD                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐      ┌──────────────┐                                        │
│  │   TRIGGER    │      │   TRIGGER    │                                        │
│  │  (6h auto)   │      │  (manual)    │                                        │
│  └──────┬───────┘      └──────┬───────┘                                        │
│         │                     │                                                 │
│         └──────────┬──────────┘                                                 │
│                    ▼                                                            │
│         ┌──────────────────┐                                                    │
│         │  BRANCH ROUTER   │                                                    │
│         └────────┬─────────┘                                                    │
│                  │                                                              │
│     ┌────────────┴────────────┐                                                 │
│     ▼                         ▼                                                 │
│  ┌──────────────────┐   ┌──────────────────┐                                   │
│  │   BRANCH A       │   │   BRANCH B       │                                   │
│  │   EMAILY         │   │   DOKUMENTY      │                                   │
│  │   Thunderbird    │   │   OneDrive       │                                   │
│  │                  │   │   Dropbox        │                                   │
│  │   rsync → DGX    │   │   ACASIS         │                                   │
│  └────────┬─────────┘   │   rsync → DGX    │                                   │
│           │             │   + deduplicate  │                                   │
│           │             └────────┬─────────┘                                   │
│           └──────────┬───────────┘                                              │
│                      ▼                                                          │
│  ════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│                        PHASE 1: DOCLING                                         │
│                        ~40 procesů na 3 strojích                                │
│  ┌───────────────┬───────────────┬───────────────┐                             │
│  │  Mac Mini M4  │  MacBook Pro  │     DGX       │                             │
│  │  10 procesů   │  15 procesů   │  15 procesů   │                             │
│  │  0-32,000     │  32,000-64,000│  64,000-95k   │                             │
│  └───────┬───────┴───────┬───────┴───────┬───────┘                             │
│          │               │               │                                      │
│          └───────────────┼───────────────┘                                      │
│                          ▼                                                      │
│                   ┌──────────────┐                                              │
│                   │   SELHANÉ?   │──────No────────┐                             │
│                   └──────┬───────┘                │                             │
│                          │Yes                     │                             │
│                          ▼                        │                             │
│  ════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│                        PHASE 2: LLM 32B HIERARCHICAL                            │
│                        qwen2.5:7b → 14b → 32b                                   │
│                        BEZ DGX (jen Mac Mini + MacBook)                         │
│  ┌───────────────┬───────────────┐                                             │
│  │  Mac Mini M4  │  MacBook Pro  │                                             │
│  │  3 procesy    │  5 procesů    │                                             │
│  └───────┬───────┴───────┬───────┘                                             │
│          │               │                                                      │
│          └───────┬───────┘                                                      │
│                  ▼                                                              │
│           ┌──────────────┐                                                      │
│           │   SELHANÉ?   │──────No────────┐                                     │
│           └──────┬───────┘                │                                     │
│                  │Yes                     │                                     │
│                  ▼                        │                                     │
│  ════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│                        PHASE 3: GPT-4 API                                       │
│                        Na DGX (externí model)                                   │
│                        OpenAI API klíč                                          │
│  ┌───────────────┐                                                             │
│  │      DGX      │                                                             │
│  │   GPT-4o API  │                                                             │
│  └───────┬───────┘                                                             │
│          │                                                                      │
│          ▼                                                                      │
│   ┌──────────────┐                                                              │
│   │   SELHANÉ?   │──────No────────┐                                             │
│   └──────┬───────┘                │                                             │
│          │Yes                     │                                             │
│          ▼                        │                                             │
│  ════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│                        PHASE 4: MANUÁLNÍ REVIEW                                 │
│                        Zobrazit na monitoru                                     │
│                        Čekat na vstup uživatele                                 │
│  ┌───────────────┐                                                             │
│  │   Terminal UI │                                                             │
│  │   nebo Web UI │                                                             │
│  └───────┬───────┘                                                             │
│          │                                                                      │
│          └──────────────┬─────────────────┘                                     │
│                         ▼                                                       │
│  ════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│                        PHASE 5: PAPERLESS IMPORT                                │
│                        URL: 192.168.10.200:8020                                 │
│                        31 custom fields                                         │
│                        Kontrola duplicit (MD5)                                  │
│  ┌───────────────┐                                                             │
│  │   Paperless   │                                                             │
│  │   API Upload  │                                                             │
│  │   + Tags      │                                                             │
│  │   + Fields    │                                                             │
│  └───────┬───────┘                                                             │
│          │                                                                      │
│          ▼                                                                      │
│  ════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│                        PHASE 6: ISDOC GENERÁTOR                                 │
│                        Pro účetní dokumenty:                                    │
│                        invoice, receipt, tax_document                           │
│  ┌───────────────┐                                                             │
│  │ ISDOC XML Gen │                                                             │
│  └───────┬───────┘                                                             │
│          │                                                                      │
│          ▼                                                                      │
│  ┌───────────────┐                                                             │
│  │   CDB LOG     │                                                             │
│  │   SQLite DGX  │                                                             │
│  └───────────────┘                                                             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

                        MONITORING (běží paralelně)
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │ Resource Monitor│    │ Progress Monitor│    │   CDB Logger    │             │
│  │ CPU/RAM < 85%   │    │ každých 5 min   │    │ SQLite na DGX   │             │
│  │ Pause on exceed │    │ Stats všech fází│    │ Zápis každého   │             │
│  └─────────────────┘    └─────────────────┘    │ běhu            │             │
│                                                 └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Datové Toky

### Branch A: Emaily
```
Thunderbird (8TB-SSD)
    │
    │ rsync
    ▼
DGX: /home/puzik/thunderbird-emails/
    │
    │ Phase 1-4 processing
    ▼
DGX: /home/puzik/processing/phase1_results/
    │
    │ Phase 5 import
    ▼
Paperless: 192.168.10.200:8020
```

### Branch B: Dokumenty
```
OneDrive (MacBook)  ──┐
Dropbox (MacBook)   ──┼── rsync ──▶ DGX: /home/puzik/almquist-rag-v3/documents/
ACASIS (8TB-SSD)    ──┘                              │
                                                     │ deduplicate
                                                     ▼
                                    DGX: /home/puzik/processing/unique_docs.txt
                                                     │
                                                     │ Phase 1-4 processing
                                                     ▼
                                    DGX: /home/puzik/processing/phase1_results/
                                                     │
                                                     │ Phase 5 import
                                                     ▼
                                    Paperless: 192.168.10.200:8020
```

---

## 31 Custom Fields

| # | Field | Popis |
|---|-------|-------|
| 1 | doc_typ | Typ dokumentu (invoice, contract, ...) |
| 2 | protistrana_nazev | Název protistrany |
| 3 | protistrana_ico | IČO protistrany |
| 4 | protistrana_typ | Typ (firma, OSVČ, FO) |
| 5 | castka_celkem | Celková částka |
| 6 | datum_dokumentu | Datum dokumentu |
| 7 | cislo_dokumentu | Číslo dokumentu |
| 8 | mena | Měna (CZK, EUR, USD) |
| 9 | stav_platby | Stav platby |
| 10 | datum_splatnosti | Datum splatnosti |
| 11 | kategorie | Kategorie dokumentu |
| 12 | email_from | Email odesílatele |
| 13 | email_to | Email příjemce |
| 14 | email_subject | Předmět emailu |
| 15 | od_osoba | Jméno odesílatele |
| 16 | od_osoba_role | Role odesílatele |
| 17 | od_firma | Firma odesílatele |
| 18 | pro_osoba | Jméno příjemce |
| 19 | pro_osoba_role | Role příjemce |
| 20 | pro_firma | Firma příjemce |
| 21 | predmet | Předmět/účel |
| 22 | ai_summary | AI souhrn |
| 23 | ai_keywords | AI klíčová slova |
| 24 | ai_popis | AI popis obsahu |
| 25 | typ_sluzby | Typ služby |
| 26 | nazev_sluzby | Název služby |
| 27 | predmet_typ | Typ předmětu |
| 28 | predmet_nazev | Název předmětu |
| 29 | polozky_text | Položky (text) |
| 30 | polozky_json | Položky (JSON) |
| 31 | perioda | Období |

---

## Stroje a Kapacity

| Stroj | CPU | RAM | Role | Docling proc | LLM proc |
|-------|-----|-----|------|--------------|----------|
| Mac Mini M4 | 14 | 64GB | Primary | 10 | 3 |
| MacBook Pro | 16 | 128GB | Secondary | 15 | 5 |
| DGX | 20 | 120GB | Hub + GPT-4 | 15 | 0 (GPT-4 API) |
| Dell | - | - | Excluded | 0 | 0 |

---

## Modely AI

### Phase 1: Docling
- Lokální OCR + text extraction
- Bez AI inference
- ~140 procesů celkem

### Phase 2: LLM Hierarchical
```
qwen2.5:7b (rychlý)
    │
    │ Pokud 7B + 14B souhlasí → HOTOVO
    ▼
qwen2.5:14b (validace)
    │
    │ Pokud nesouhlasí → arbitr
    ▼
qwen2.5:32b (arbitr)
```

### Phase 3: GPT-4
- Model: gpt-4o
- API: OpenAI
- Lokace: DGX (.env)

---

## Spuštění

### Import do n8n
```bash
# 1. Otevři n8n
# 2. Import workflow
# 3. Nastav credentials pro SSH, Paperless API

# Nebo CLI:
n8n import:workflow --input=/Volumes/ACASIS/apps/maj-document-recognition/n8n-workflow-maj-email-docu-ai-load.json
```

### Manuální spuštění
```bash
# Celý pipeline
cd /Volumes/ACASIS/apps/maj-document-recognition
python3 run_all_phases.py

# Jednotlivé fáze
python3 email_extractor/phase1_docling.py
python3 email_extractor/phase2_hierarchical.py
python3 email_extractor/phase3_gpt4.py
python3 email_extractor/phase5_import.py
```

---

## Monitoring

### Real-time progress
```bash
python3 email_extractor/monitor.py --status
```

### CDB Log (SQLite)
```bash
sqlite3 /home/puzik/almquist-central-log/almquist.db \
  "SELECT * FROM email_extraction_runs ORDER BY start_time DESC LIMIT 10"
```

### Resource check
```bash
python3 email_extractor/monitor.py --check-resources
```

---

## Error Handling

| Fáze | Selhání | Akce |
|------|---------|------|
| Phase 1 | Docling error | → phase1_failed.jsonl → Phase 2 |
| Phase 2 | LLM timeout/error | → phase2_failed.jsonl → Phase 3 |
| Phase 3 | GPT-4 API error | → phase3_failed.jsonl → Phase 4 |
| Phase 4 | User skip | → Přeskočit, nezahrnout |
| Phase 5 | Duplicate | → Skip, log |
| Phase 5 | API error | → Retry 3x, then fail |

---

## Checkpoints

Po každé fázi se vytvoří checkpoint:
- `phase1_output/phase1_complete.marker`
- `phase1_output/phase2_complete.marker`
- `phase1_output/phase3_complete.marker`
- ...

Pro restart od konkrétní fáze:
```bash
python3 run_all_phases.py --start-phase 3
```
