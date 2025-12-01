#!/usr/bin/env python3
"""
Test AI Consensus with 2 Local Ollama Models
=============================================
Production mode: qwen2.5:32b + czech-finance-speed:latest

Author: Claude Code
Date: 2025-12-01
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))

from ai_consensus_trainer import AIVoter

# Sample Czech invoice text
SAMPLE_CZECH_INVOICE = """
FAKTURA č. 2024-0456
Datum vystavení: 01.12.2024
Datum splatnosti: 15.12.2024

Dodavatel:
MyBrainWorks s.r.o.
IČO: 03981428
DIČ: CZ03981428

Odběratel:
Martin Pužík
IČO: 12345678

Položky:
=======================================================
Č.  Popis                          Množství  Cena    DPH    Celkem
---  -------------------------      --------  ------  -----  --------
1.   Leonardo AI služba - prosinec 1 ks      1500,00 21%    1815,00
2.   Data storage 100GB            100 GB      10,00 21%    1210,00
=======================================================

Celkem bez DPH:            2500,00 Kč
DPH 21%:                    525,00 Kč
Celkem k úhradě:           3025,00 Kč

Způsob platby: Bankovní převod
VS: 2024456
"""

def main():
    print("\n" + "=" * 80)
    print("🇨🇿 TEST: 2 LOCAL OLLAMA MODELS (Production Mode)")
    print("=" * 80)
    print("\nModels:")
    print("  1. qwen2.5:32b - General 32B model")
    print("  2. czech-finance-speed:latest - Czech financial specialist")
    print()

    # Initialize AIVoter in production mode (no external APIs)
    print("Initializing AIVoter (production mode)...")
    voter = AIVoter(use_external_apis=False)

    if len(voter.models) != 2:
        print(f"\n❌ ERROR: Expected 2 models, got {len(voter.models)}")
        print(f"   Models: {list(voter.models.keys())}")
        return

    print(f"✅ Initialized {len(voter.models)} models: {list(voter.models.keys())}\n")

    # Test AI voting on Czech invoice
    print("Testing AI consensus on Czech invoice...")
    print("-" * 80)

    consensus_result, voting_details = voter.vote(SAMPLE_CZECH_INVOICE, 'invoice')

    # Display results
    print("\n" + "=" * 80)
    print("📊 RESULTS")
    print("=" * 80)

    print(f"\n1. Item Counts per Model:")
    for model_name, count in voting_details['item_counts'].items():
        print(f"   {model_name}: {count} items")

    print(f"\n2. Consensus:")
    print(f"   Majority count: {voting_details['majority_count']} items")
    print(f"   Agreeing models: {', '.join(voting_details['agreeing_models'])}")
    print(f"   Consensus strength: {voting_details['consensus_strength']:.0%}")

    if voting_details['consensus_strength'] == 1.0:
        print("\n   ✅ PERFECT CONSENSUS (100%) - Both models agree!")
    elif voting_details['consensus_strength'] >= 0.5:
        print("\n   ⚠️  PARTIAL CONSENSUS - Models disagree")
    else:
        print("\n   ❌ NO CONSENSUS - Models completely disagree")

    print("\n3. Expected vs Actual:")
    print("   Expected items: 2 (Leonardo AI + Data storage)")
    print(f"   AI consensus: {voting_details['majority_count']} items")

    if voting_details['majority_count'] == 2:
        print("   ✅ CORRECT!")
    else:
        print(f"   ❌ MISMATCH (diff: {abs(2 - voting_details['majority_count'])} items)")

    print("\n" + "=" * 80)
    print("✅ Test complete!")
    print("=" * 80)

    # Test info
    print("\n💡 Benefits of 2 local Ollama models:")
    print("   ✅ Faster (no API network calls)")
    print("   ✅ Cheaper (no API costs)")
    print("   ✅ More accurate for Czech documents (specialist model)")
    print("   ✅ Fully local and private")
    print("   ✅ Czech-finance-speed trained specifically on Czech documents")


if __name__ == "__main__":
    main()
