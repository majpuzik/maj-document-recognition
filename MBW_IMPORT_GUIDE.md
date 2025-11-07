# 📁 MBW Dokumenty → Paperless-NGX Import Guide

Kompletní návod pro import dokumentů z Dropbox MBW složky do Paperless-NGX s možností selekce.

## 🎯 Přehled procesu

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  1. ZPRACOVÁNÍ  │────▶│  2. SELEKCE      │────▶│  3. IMPORT          │
│  OCR + AI       │     │  Filtry + výběr  │     │  → Paperless-NGX    │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
process_mbw_        →   interactive_        →    import_to_
documents.py            selector.py               paperless.py
```

## 📦 Co potřebuješ

1. ✅ Dokumenty v `~/Dropbox/MBW`
2. ✅ Běžící Paperless-NGX (localhost:8000)
3. ✅ API token pro Paperless
4. ✅ Ollama běží (localhost:11434)

## 🚀 Krok 1: Zpracování dokumentů

Načte všechny dokumenty z MBW složky, provede OCR a AI klasifikaci.

```bash
cd ~/maj-document-recognition
source venv/bin/activate

# Zpracovat všechny dokumenty
python process_mbw_documents.py

# Nebo s vlastními parametry
python process_mbw_documents.py \
    --source ~/Dropbox/MBW \
    --output data/mbw_processed.json \
    --config config/config.yaml
```

### Výstup:
- **data/mbw_processed.json** - JSON se všemi zpracovanými dokumenty
- **SQLite DB** - Uloženo v databázi pro pozdější použití

### Co se děje:
1. Najde všechny PDF, JPG, PNG v MBW složce
2. Pro každý dokument:
   - OCR (tesseract) - extrakce textu
   - AI klasifikace (ollama) - rozpoznání typu
   - Uložení do DB
   - Příprava tagů pro Paperless

## 🎯 Krok 2: Interaktivní selekce

Vybereš které dokumenty chceš importovat do Paperless.

```bash
python interactive_selector.py

# Nebo s vlastním výsledkovým souborem
python interactive_selector.py --results data/mbw_processed.json
```

### Možnosti selekce:

#### 📋 Základní operace:
- **[t]** - Toggle výběr konkrétního dokumentu (zadej číslo)
- **[a]** - Vybrat všechny (filtrované)
- **[d]** - Zrušit výběr všech

#### 🔍 Filtry:
- **[f]** - Otevřít menu filtrů

Dostupné filtry:
1. **Typ dokumentu** - faktura, objednavka, dodaci_list, atd.
2. **Min confidence** - např. 0.7 = pouze dokumenty s min 70% jistotou
3. **Max confidence** - např. 0.9 = pouze dokumenty do 90% jistoty
4. **Datum od** - formát YYYY-MM-DD
5. **Datum do** - formát YYYY-MM-DD
6. **Pouze vybrané** - zobrazit pouze zaškrtnuté

#### 📄 Navigace:
- **[n]** - Další stránka
- **[p]** - Předchozí stránka
- **[g]** - Jít na konkrétní stránku

#### 💾 Export:
- **[e]** - Exportovat vybrané dokumenty do JSON pro import

### Příklad workflow:

```
1. Otevřeš menu filtrů [f]
2. Vybereš typ dokumentu [1] → faktura
3. Nastavíš min confidence [2] → 0.8
4. Vrátíš se zpět [b]
5. Vidíš pouze faktury s min 80% jistotou
6. Vybereš všechny [a]
7. Exportuješ [e] → data/paperless_import.json
```

### Výstup:
- **data/paperless_import.json** - JSON s vybranými dokumenty pro import

## 📤 Krok 3: Import do Paperless-NGX

Nahraje vybrané dokumenty do Paperless-NGX.

```bash
# DRY RUN - pouze simulace (doporučeno první)
python import_to_paperless.py --dry-run

# Reálný import
python import_to_paperless.py

# S vlastními parametry
python import_to_paperless.py \
    --export data/paperless_import.json \
    --config config/config.yaml
```

### Co se děje:
1. Načte JSON s vybranými dokumenty
2. Pro každý dokument:
   - Zkontroluje duplikáty (checksum)
   - Vytvoří tagy (pokud neexistují)
   - Vytvoří correspondent (pokud neexistuje)
   - Vytvoří document_type (pokud neexistuje)
   - Nahraje dokument s metadaty

### Výstup:
- Dokumenty nahrány do Paperless-NGX
- Automaticky vytvořené tagy/typy/correspondent
- Souhrn: úspěšné, duplikáty, chyby

## ⚙️ Konfigurace Paperless-NGX

V `config/config.yaml`:

```yaml
paperless:
  enabled: true
  url: "http://localhost:8000"
  api_token: "tvůj-api-token-zde"
  verify_ssl: true
  timeout: 30

  # Automatické vytváření
  auto_create_tags: true
  auto_create_correspondents: true
  auto_create_document_types: true

  # Kontrola duplikátů
  check_duplicates: true
  duplicate_check_method: "checksum"  # checksum, title, content
```

### Jak získat API token:

1. Otevři Paperless-NGX: http://localhost:8000
2. Přihlaš se
3. Jdi do Settings → API Keys
4. Vytvoř nový token
5. Zkopíruj do config.yaml

## 📊 Příklady použití

### Příklad 1: Import všech faktur s vysokou jistotou

```bash
# 1. Zpracuj dokumenty
python process_mbw_documents.py

# 2. Interaktivní selekce
python interactive_selector.py

# V selectoru:
[f]  # Filtry
[1]  # Typ dokumentu
[1]  # faktura
[2]  # Min confidence
0.85
[b]  # Zpět
[a]  # Vybrat všechny
[e]  # Export
data/faktury_import.json

# 3. Import
python import_to_paperless.py --export data/faktury_import.json
```

### Příklad 2: Import dokumentů z ledna 2025

```bash
# V selectoru:
[f]  # Filtry
[4]  # Datum od
2025-01-01
[5]  # Datum do
2025-01-31
[b]  # Zpět
[a]  # Vybrat všechny
[e]  # Export

# Import
python import_to_paperless.py
```

### Příklad 3: Manuální výběr 10 dokumentů

```bash
# V selectoru:
[t] 5   # Vyber dokument #5
[t] 12  # Vyber dokument #12
[t] 23  # Vyber dokument #23
...
[e]  # Export jen vybraných
```

## 🔍 Rozpoznané typy dokumentů

Systém rozpoznává tyto typy (+ nově přidané v2.1):

1. **faktura** - Faktury (invoice, Rechnung)
2. **stvrzenka** - Stvrzenky, paragony
3. **objednavka** ⭐ NOVÉ! - Purchase Order, Bestellung
4. **dodaci_list** ⭐ NOVÉ! - Delivery Note, Lieferschein
5. **bankovni_vypis** - Bank statements
6. **vyzva_k_platbe** - Payment requests
7. **oznameni_o_zaplaceni** - Payment confirmations
8. **soudni_dokument** - Legal documents
9. **reklama** - Marketing/newsletters
10. **obchodni_korespondence** - Business correspondence
11. **jine** - Other

## 📈 Automaticky generované tagy

Pro každý dokument se vytvoří:

- **MBW** - základní tag (všechny dokumenty z MBW)
- **[typ_dokumentu]** - faktura, objednavka, atd.
- **high_confidence** - pokud confidence ≥ 90%
- **low_confidence** - pokud confidence < 70%

## ⚠️ Troubleshooting

### Chyba: "Ollama not available"

```bash
# Zkontroluj jestli Ollama běží
curl http://localhost:11434/api/tags

# Spusť Ollama pokud neběží
ollama serve
```

### Chyba: "Cannot connect to Paperless-NGX"

```bash
# Zkontroluj jestli Paperless běží
curl http://localhost:8000/api/documents/?page_size=1

# Zkontroluj API token v config.yaml
```

### Chyba: "OCR failed"

```bash
# Zkontroluj Tesseract
tesseract --version

# Nainstaluj pokud chybí
brew install tesseract tesseract-lang
```

### Příliš nízká confidence

- Zkontroluj kvalitu OCR (text extraction)
- Pro obrázky (JPG) může být OCR horší než u PDF
- Použij filtry pro zobrazení problematických dokumentů:
  - Min confidence: 0.0
  - Max confidence: 0.7

## 📂 Struktura souborů

```
maj-document-recognition/
├── process_mbw_documents.py      # Krok 1: Zpracování
├── interactive_selector.py       # Krok 2: Selekce
├── import_to_paperless.py        # Krok 3: Import
├── MBW_IMPORT_GUIDE.md           # Tento návod
│
├── data/
│   ├── mbw_processed.json        # Zpracované dokumenty (krok 1)
│   ├── paperless_import.json     # Vybrané k importu (krok 2)
│   └── documents.db              # SQLite databáze
│
├── config/
│   └── config.yaml               # Konfigurace
│
└── src/
    ├── ocr/                      # OCR moduly
    ├── ai/                       # AI klasifikace
    ├── integrations/             # Paperless API
    └── database/                 # DB manager
```

## 🎯 Quick Start (všechno najednou)

```bash
cd ~/maj-document-recognition
source venv/bin/activate

# 1. Zpracuj všechny dokumenty
python process_mbw_documents.py

# 2. Interaktivní selekce (vyber co chceš)
python interactive_selector.py

# 3. Nejprve dry run (test)
python import_to_paperless.py --dry-run

# 4. Reálný import pokud vypadá OK
python import_to_paperless.py
```

## 💡 Tipy

1. **Vždy použij --dry-run první** - uvidíš co se stane bez změn
2. **Filtruj podle confidence** - dokumenty s nízkou jistotou zkontroluj ručně
3. **Zkontroluj duplikáty** - systém je automaticky přeskočí
4. **Použij tagy** - všechny dokumenty mají tag "MBW" pro snadné filtrování
5. **Zkontroluj DB** - všechno je uloženo v SQLite i když import selže

---

**Made with ❤️ by MAJ + Claude Code**
**Version 2.1 - Released 2025-11-06**
