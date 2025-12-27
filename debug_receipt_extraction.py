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
Debug receipt extraction to find the extra item
"""

import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
from data_extractors import create_extractor

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

SAMPLE_RECEIPT = """
====================================
      BENZINA - ČS a.s.
    IČO: 45534306
    DIČ: CZ45534306
====================================

Datum: 20.11.2024  14:35
Paragon: 85674321

Položky:
------------------------------------
Natural 95         45,5 l   36,90  1.679,95
Mytí auta Premium   1 ks   150,00    150,00
Káva grande         1 ks    65,00     65,00
------------------------------------

Celkem:                            1.894,95 Kč

DPH 21%:                             329,64 Kč
DPH 15%:                               0,00 Kč

====================================
EET - Elektronická evidence tržeb
FIK: a1b2c3d4-e5f6-7890-abcd-1234567890ab
BKP: 12345678-90ABCDEF-12345678-90AB-12345678
====================================

Děkujeme za nákup!
"""

print("="*80)
print("DEBUG: Receipt Extraction")
print("="*80)

extractor = create_extractor('receipt')
result = extractor.extract(SAMPLE_RECEIPT)

print("\n" + "="*80)
print("RESULT:")
print("="*80)
print(f"Items found: {len(result.get('items', []))}")
print(f"Confidence: {result.get('extraction_confidence', 0)}%")

if result.get('items'):
    print("\nItems extracted:")
    for i, item in enumerate(result['items'], 1):
        print(f"  {i}. {item.get('description', 'N/A')} - {item.get('quantity', 0)} {item.get('unit', '')} - {item.get('total', 0)} Kč")
else:
    print("\n⚠️  NO ITEMS EXTRACTED!")

print("\n" + "="*80)
print("AI CONSENSUS (should be 3 items):")
print("="*80)
print("  1. Natural 95 - 45.5 l - 1679.95 Kč")
print("  2. Mytí auta Premium - 1 ks - 150.00 Kč")
print("  3. Káva grande - 1 ks - 65.00 Kč")

if len(result.get('items', [])) == 4:
    print("\n⚠️  EXTRA ITEM DETECTED!")
    print("Extra item might be:")
    all_items = result['items']
    for i, item in enumerate(all_items, 1):
        desc = item.get('description', '')
        if 'celkem' in desc.lower() or 'total' in desc.lower() or 'dph' in desc.lower():
            print(f"  → Item #{i}: '{desc}' (likely not a real item)")
