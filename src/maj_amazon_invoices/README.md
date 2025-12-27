# MAJ Amazon Invoices

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Open Source](https://img.shields.io/badge/Open%20Source-100%25-green.svg)](https://opensource.org/)

**Parse Amazon Business CSV exports and generate professional PDF invoices.**

*[Česká verze níže / Czech version below](#czech-version)*

---

## Features

- **Multi-language CSV Parser** - Supports German, English, and Czech Amazon exports
- **PDF Invoice Generator** - Creates professional Amazon-style invoices
- **ISDOC Export** - Prepares data for Czech electronic invoices (ISDOC format)
- **Auto-detection** - Automatically detects language and delimiter (tab, comma, semicolon)
- **Clean API** - Simple high-level API with detailed error messages
- **100% Open Source** - MIT license, all dependencies are open source

## Installation

```bash
pip install reportlab
```

## Quick Start

```python
from maj_amazon_invoices import process_amazon_csv

# Process CSV and generate both PDF and ISDOC
response = process_amazon_csv(
    'bestellungen_von_2025.csv',
    output_dir='invoices/'
)

if response.success:
    print(f"Processed {response.stats.total_orders} orders")
    for result in response.results:
        print(f"  {result.order_number}: {result.pdf_path}")
```

## API Options

```python
from maj_amazon_invoices import process_amazon_csv

response = process_amazon_csv(
    csv_path='export.csv',
    output_dir='output/',
    output_format='both',      # 'pdf', 'isdoc', or 'both'
    language='bilingual',      # 'cs', 'bilingual', or 'original'
    row_start=1,               # Process from row 1 (optional)
    row_end=100,               # Process to row 100 (optional)
)
```

## Low-Level Usage

```python
from maj_amazon_invoices import parse_amazon_csv, generate_amazon_invoice_pdf

# Parse CSV
orders = parse_amazon_csv('bestellungen.csv')

# Generate PDF for each order
for order in orders:
    generate_amazon_invoice_pdf(order, f'invoices/{order.order_number}.pdf')
    print(f'{order.order_number}: {order.total_incl_vat} {order.currency}')
```

## Supported CSV Formats

### File Name Patterns
- `bestellungen_von_*.csv` / `bestellungen-von-*.csv` (German)
- `invoices_from_*.csv` / `invoices-from-*.csv` (English)
- `objednavky_od_*.csv` / `objednavky-od-*.csv` (Czech)

### Languages

| Language | Example Headers |
|----------|-----------------|
| German | Bestelldatum, Bestellnummer, Währung |
| English | Order Date, Order Number, Currency |
| Czech | Datum objednávky, Číslo objednávky, Měna |

## Output

### Generated PDF Contains
- Amazon Business branding (orange header)
- Order information (number, dates, currency)
- Seller / Buyer details with VAT IDs
- Item table (ASIN, description, quantity, price, VAT)
- Totals (subtotal, shipping, promotions, VAT, grand total)
- Payment information
- Bilingual labels (CZ/EN)

### ISDOC Data Structure
```python
{
    "doc_type": "FAKTURA",
    "number": "028-5217580-1995537",
    "issue_date": "2025-12-21",
    "currency": "EUR",
    "customer": {"name": "...", "dic": "CZ12345678"},
    "items": [...],
    "summary": {"total_gross": 54.70}
}
```

## Dependencies

| Package | License | Purpose |
|---------|---------|---------|
| reportlab | BSD | PDF generation |
| Python 3.8+ | PSF | Runtime |

**Fonts:** DejaVu Sans (Bitstream Vera License) - bundled, open source

## License

**MIT License** - Free to use, modify, and distribute.

---

<a name="czech-version"></a>
# Česká verze

## MAJ Amazon Invoices

**Parser pro Amazon Business CSV exporty s generováním profesionálních PDF faktur.**

## Funkce

- **Multi-language CSV Parser** - Podpora německých, anglických a českých exportů
- **PDF Generátor** - Vytváří profesionální faktury ve stylu Amazon
- **ISDOC Export** - Připravuje data pro české elektronické faktury
- **Auto-detekce** - Automaticky rozpozná jazyk a oddělovač
- **Čisté API** - Jednoduché API s podrobnými chybovými hláškami
- **100% Open Source** - MIT licence, všechny závislosti jsou open source

## Instalace

```bash
pip install reportlab
```

## Rychlý start

```python
from maj_amazon_invoices import process_amazon_csv

# Zpracování CSV a generování PDF i ISDOC
response = process_amazon_csv(
    'bestellungen_von_2025.csv',
    output_dir='faktury/'
)

if response.success:
    print(f"Zpracováno {response.stats.total_orders} objednávek")
    for result in response.results:
        print(f"  {result.order_number}: {result.pdf_path}")
```

## Parametry API

| Parametr | Hodnoty | Popis |
|----------|---------|-------|
| `output_format` | `pdf`, `isdoc`, `both` | Formát výstupu (výchozí: both) |
| `language` | `cs`, `bilingual`, `original` | Jazyk dokumentu (výchozí: bilingual) |
| `row_start` | číslo | První řádek ke zpracování |
| `row_end` | číslo | Poslední řádek ke zpracování |

## Nízkoúrovňové použití

```python
from maj_amazon_invoices import parse_amazon_csv, generate_amazon_invoice_pdf

# Parsování CSV
orders = parse_amazon_csv('bestellungen.csv')

# Generování PDF
for order in orders:
    generate_amazon_invoice_pdf(order, f'faktury/{order.order_number}.pdf')
```

## Integrace s účetním systémem

```python
from maj_amazon_invoices import parse_amazon_csv

orders = parse_amazon_csv('export.csv')
for order in orders:
    isdoc_data = order.to_isdoc_dict()
    # Použití s účetním systémem...
```

## Licence

**MIT License** - Volně k použití, úpravě a distribuci.

---

**Author:** MAJ Development
**Version:** 1.0.0
