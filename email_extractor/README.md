# Email Extractor - Multi-Phase Pipeline

## Přehled

5-fázový systém pro extrakci a klasifikaci ~95k emailů z Thunderbirdu.

## Fáze

| Fáze | Nástroj | Stroje | Status |
|------|---------|--------|--------|
| 1 | Docling | Mac Mini, MacBook, DGX | ✅ Hotovo (53,357) |
| 2 | qwen2.5:32b | Mac Mini, MacBook, DGX | ✅ Hotovo (2,261) |
| 3 | GPT-4 | DGX | Čeká |
| 4 | Manuální review | - | Čeká |
| 5 | Paperless import | - | Čeká |

## Multi-Machine Architektura

```
┌─────────────────────────────────────────────────────────────┐
│                    SDÍLENÉ ÚLOŽIŠTĚ                         │
│            /Volumes/ACASIS (NFS/SSHFS mount)                │
├─────────────────────────────────────────────────────────────┤
│  phase1_output/                                             │
│  ├── phase1_results/     # 53,357 JSON výsledků             │
│  ├── phase2_results/     # 2,261 LLM výsledků               │
│  ├── phase2_locks/       # Atomické zámky (file-based)      │
│  ├── phase2_to_process.jsonl  # Input pro Phase 2           │
│  └── phase2_failed.jsonl      # Selhané emaily              │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────┴────┐          ┌────┴────┐          ┌────┴────┐
    │Mac Mini │          │ MacBook │          │   DGX   │
    │  M4 Pro │          │   Pro   │          │ A100x8  │
    └─────────┘          └─────────┘          └─────────┘
```

## Spuštění

### Phase 2 (Multi-machine)
```bash
# Na každém stroji - automatická koordinace
python3 email_extractor/phase2_llm.py

# Stroje se poznají podle hostname:
# - spark* → DGX paths
# - macbook/mbp → MacBook paths
# - ostatní → Mac Mini paths (default)
```

## Locking Mechanismus

- **Atomické vytvoření**: `os.O_CREAT | os.O_EXCL`
- **Stale lock cleanup**: >10 minut → automatický reset
- **Format**: `{hostname}:{timestamp}`

## 38 Custom Fields

```python
CUSTOM_FIELDS = [
    # Základní (31)
    "doc_typ", "protistrana_nazev", "protistrana_ico", "protistrana_typ",
    "castka_celkem", "datum_dokumentu", "cislo_dokumentu", "mena",
    "stav_platby", "datum_splatnosti", "kategorie", "email_from",
    "email_to", "email_subject", "od_osoba", "od_osoba_role",
    "od_firma", "pro_osoba", "pro_osoba_role", "pro_firma",
    "predmet", "ai_summary", "ai_keywords", "ai_popis",
    "typ_sluzby", "nazev_sluzby", "predmet_typ", "predmet_nazev",
    "polozky_text", "polozky_json", "perioda",
    # Enhanced (7) - přidáno 2024-12-17
    "direction", "doc_subtype", "castka_zaklad", "castka_dph",
    "sazba_dph", "variabilni_symbol", "protistrana_dic"
]
```

## Paperless Instance

| Instance | Port | Token | Tagy |
|----------|------|-------|------|
| paperless-ngx | 8020 | e264c40b... | 74 |
| almquist | 8010 | 68800594... | 74 |
| paperless-rag | 8030 | (v kódu) | 74+ |

## Changelog

### 2024-12-17
- ✅ Multi-machine podpora v phase2_llm.py
- ✅ File-based locking s atomic create
- ✅ Hostname auto-detection (spark/macbook/default)
- ✅ Skip already processed
- ✅ Enhanced field extractor integrace
- ✅ 74 tagů na všech Paperless instancích
