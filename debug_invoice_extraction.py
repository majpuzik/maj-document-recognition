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
Debug script to see why invoice extraction is failing
"""

import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
from data_extractors import create_extractor

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

SAMPLE_INVOICE = """
FAKTURA č. 2024-0123
Datum vystavení: 15.11.2024
Datum splatnosti: 30.11.2024

Dodavatel:
OpenAI Ireland Ltd.
IČO: 12345678
DIČ: IE1234567V

Odběratel:
Martin Pužík
IČO: 87654321

Položky:
=======================================================
Č.  Popis                          Množství  Cena    DPH    Celkem
---  -------------------------      --------  ------  -----  --------
1.   ChatGPT Plus API - listopad   1 ks      150,00  21%    181,50
2.   Data storage 50GB             50 GB       2,00  21%    121,00
3.   Additional tokens 1M          1 ks       50,00  21%     60,50
=======================================================

Celkem bez DPH:               200,00 Kč
DPH 21%:                       42,00 Kč
Celkem k úhradě:              242,00 Kč

Způsob platby: Bankovní převod
VS: 2024001
"""

print("="*80)
print("DEBUG: Invoice Extraction")
print("="*80)

extractor = create_extractor('invoice')
result = extractor.extract(SAMPLE_INVOICE)

print("\n" + "="*80)
print("RESULT:")
print("="*80)
print(f"Line items found: {len(result.get('line_items', []))}")
print(f"Confidence: {result.get('extraction_confidence', 0)}%")

if result.get('line_items'):
    print("\nLine items:")
    for item in result['line_items']:
        print(f"  {item['line_number']}. {item['description']} - {item['total_gross']}")
else:
    print("\n⚠️  NO LINE ITEMS EXTRACTED!")

print("\nFull result:")
import json
print(json.dumps(result, indent=2, ensure_ascii=False))
