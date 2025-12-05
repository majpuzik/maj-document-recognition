# Paperless-NGX Import System with LLM Metadata Extraction

Automatizovaný import dokumentů do Paperless-NGX s extrakcí metadat pomocí lokálního LLM (Ollama).

## Funkce

### Hierarchické typy dokumentů
```
Dokument
├── Faktura
│   ├── Došlá faktura
│   ├── Odeslaná faktura
│   ├── Zálohová faktura
│   └── Dobropis
├── Účtenka
│   ├── Pohonné hmoty
│   ├── Restaurace
│   ├── Nákupy
│   ├── Služby
│   ├── Doprava
│   └── Potvrzení platby (PayPal, platební brány)
├── IT zpráva
│   ├── Systémová notifikace (NAS, Docker, servery)
│   ├── Monitoring alert
│   ├── Backup report
│   └── Security alert
├── Bankovní výpis
│   ├── Běžný účet
│   ├── Spořící účet
│   └── Firemní účet
├── Smlouva
│   ├── Pracovní smlouva
│   ├── Nájemní smlouva
│   ├── Obchodní smlouva
│   └── Pojistná smlouva
├── Dopis
│   ├── Úřední dopis
│   ├── Obchodní korespondence
│   └── Osobní korespondence
├── Daňový doklad
│   ├── Daňové přiznání
│   ├── DPH přiznání
│   └── Daňový doklad
└── Právní dokument
    ├── Soudní rozhodnutí
    ├── Exekuce
    └── Plná moc
```

### Tagy / Labels
- **year:** 2020-2025
- **currency:** CZK, EUR, USD
- **status:** Zaplaceno, Nezaplaceno, Částečně zaplaceno, Storno
- **priority:** Důležité, Běžné, Archiv
- **source:** Email, Sken, Upload, Auto-import
- **vat:** S DPH, Bez DPH, Osvobozeno
- **payment_method:** Hotově, Převodem, Kartou, PayPal
- **kategorie:** Reklama, Newsletter, IT zpráva, Obchodní, Osobní, Upomínka

### Custom Fields (strukturovaná data pro RAG)
- invoice_number (string)
- total_amount (monetary)
- currency (string)
- vat_amount (monetary)
- due_date (date)
- issue_date (date)
- ico (string)
- dic (string)
- bank_account (string)
- variable_symbol (string)
- payment_status (string)

## Požadavky

- Docker & Docker Compose
- Ollama s modelem qwen2.5:14b
- Python 3.10+
- SQLite databáze se zdrojovými dokumenty

## Instalace

```bash
# Spustit Paperless-NGX
docker compose up -d

# Počkat na inicializaci (~30s)
docker ps --filter "name=paperless-ngx"

# Spustit import
python3 paperless_full_import.py --limit 100
```

## Konfigurace

### Docker Compose
- Port: 8011
- Login: admin / admin123
- OCR jazyky: eng+deu+ces
- Consumer polling: 30s
- Workers: 2

### Ollama
- Model: qwen2.5:14b
- URL: http://localhost:11434
- Temperature: 0.1 (konzistentní výsledky)

## Použití

### Import dokumentů
```bash
# Import 100 dokumentů (default)
python3 paperless_full_import.py

# Import specifického počtu
python3 paperless_full_import.py --limit 50

# Sledování průběhu
tail -f import_log.txt
```

### Přístup k API
```python
import requests

# Získat token
resp = requests.post("http://localhost:8011/api/token/",
    json={"username": "admin", "password": "admin123"})
token = resp.json()['token']

# Použít API
headers = {"Authorization": f"Token {token}"}
docs = requests.get("http://localhost:8011/api/documents/", headers=headers)
```

## Struktura projektu

```
paperless-ngx/
├── docker-compose.yml      # Konfigurace Docker
├── paperless_full_import.py # Hlavní import skript
├── export_50_acasis_docs.py # Export utility
├── README.md               # Tato dokumentace
├── data/                   # Paperless databáze
├── media/                  # Uložené dokumenty
├── consume/                # Složka pro auto-import
└── export/                 # Export složka
```

## LLM Metadata Extraction

Systém používá Ollama pro extrakci:
1. **Correspondent** - automatická detekce odesílatele/dodavatele
2. **Document Type** - klasifikace do hierarchie
3. **Tags** - rok, měna, stav platby, kategorie
4. **Custom Fields** - číslo faktury, částka, DPH, data, IČO/DIČ

### Příklad výstupu LLM
```json
{
  "correspondent": "Google Payment Ireland Ltd.",
  "document_type_path": "Dokument > Účtenka > Potvrzení platby",
  "tags": ["year:2024", "currency:CZK", "kategorie:Obchodní", "status:Zaplaceno"],
  "custom_fields": {
    "total_amount": 26.99,
    "currency": "CZK",
    "issue_date": "2024-05-09"
  }
}
```

## RAG Integration

Data jsou připravena pro RAG:
- Hierarchické typy dokumentů
- Strukturovaná metadata v custom fields
- Full-text OCR index
- REST API pro dotazování

## Verze

- **v1.0** (2025-12-05): Initial release s LLM extrakcí
- Přidány typy: IT zpráva, Potvrzení platby
- Přidány kategorie: Reklama, Newsletter, IT zpráva, Obchodní, Osobní, Upomínka
- Default import: 100 dokumentů

## Autor

Claude Code / m.a.j.puzik
