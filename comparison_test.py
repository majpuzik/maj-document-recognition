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
Comparison test: Old vs Improved classifier
"""

import sys
from pathlib import Path
import yaml
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.ai.classifier import AIClassifier
from src.ai.classifier_improved import ImprovedAIClassifier
from src.database.db_manager import DatabaseManager

# Test texts with expected classifications
TEST_CASES = [
    {
        "name": "Faktura CZ",
        "text": """
        FAKTURA č. 2024001
        Dodavatel: ABC s.r.o.
        IČO: 12345678
        DIČ: CZ12345678

        Odběratel: XYZ a.s.

        Položka: Služby IT
        Cena bez DPH: 10 000 Kč
        DPH 21%: 2 100 Kč
        Celkem: 12 100 Kč

        Datum zdanitelného plnění: 15.3.2024
        Datum splatnosti: 30.3.2024
        """,
        "expected": "faktura"
    },
    {
        "name": "Paragon",
        "text": """
        TESCO
        Paragon

        Rohlíky     15 Kč
        Mléko       25 Kč
        Máslo       45 Kč

        Celkem:     85 Kč

        15.3.2024 14:35
        """,
        "expected": "stvrzenka"
    },
    {
        "name": "Bankovní výpis",
        "text": """
        Česká spořitelna, a.s.
        VÝPIS Z ÚČTU

        Číslo účtu: 123456789/0800
        Období: 1.3.2024 - 31.3.2024

        Počáteční zůstatek: 50 000 Kč
        Příjmy: 15 000 Kč
        Výdaje: 8 500 Kč
        Konečný zůstatek: 56 500 Kč

        Transakce:
        15.3. Příjem - Mzda: 15 000 Kč
        20.3. Platba - Nájem: 8 500 Kč
        """,
        "expected": "bankovni_vypis"
    },
    {
        "name": "Upomínka",
        "text": """
        UPOMÍNKA č. 1

        K faktuře: 2024001
        Datum splatnosti: 30.3.2024

        Vážený zákazníku,

        lhůta splatnosti faktury č. 2024001 již uplynula.
        Dlužná částka: 12 100 Kč

        Prosíme o urgentní úhradu.
        """,
        "expected": "vyzva_k_platbe"
    },
    {
        "name": "Invoice EN",
        "text": """
        INVOICE #INV-2024-001

        From: Tech Solutions Inc.
        VAT: GB123456789

        To: Client Corp.

        Item: Software License
        Amount: $1,000.00
        VAT 20%: $200.00
        Total: $1,200.00

        Due date: March 30, 2024
        """,
        "expected": "faktura"
    },
    {
        "name": "Rechnung DE",
        "text": """
        RECHNUNG Nr. 2024-001

        Lieferant: Deutsche Firma GmbH
        USt-IdNr.: DE123456789

        Kunde: Österreich KG

        Leistung: Beratung
        Nettobetrag: 1.000,00 EUR
        MwSt 19%: 190,00 EUR
        Gesamtbetrag: 1.190,00 EUR

        Leistungsdatum: 15.03.2024
        Zahlbar bis: 30.03.2024
        """,
        "expected": "faktura"
    },
]

def load_config():
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def test_classifier(classifier, test_cases, name="Classifier"):
    """Test a classifier on all test cases"""
    print(f"\n{'='*80}")
    print(f"Testing: {name}")
    print(f"{'='*80}")

    results = {
        "correct": 0,
        "incorrect": 0,
        "total_confidence": 0,
        "details": []
    }

    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {test['name']}")
        print(f"Expected: {test['expected']}")

        start = time.time()
        result = classifier.classify(test['text'])
        duration = time.time() - start

        predicted = result.get('type', 'jine')
        confidence = result.get('confidence', 0)

        is_correct = (predicted == test['expected'])
        status = "✓" if is_correct else "✗"

        print(f"{status} Predicted: {predicted} (confidence: {confidence:.2%}) [{duration:.1f}s]")

        if is_correct:
            results["correct"] += 1
        else:
            results["incorrect"] += 1

        results["total_confidence"] += confidence
        results["details"].append({
            "name": test['name'],
            "expected": test['expected'],
            "predicted": predicted,
            "confidence": confidence,
            "correct": is_correct,
            "duration": duration
        })

    # Summary
    total = len(test_cases)
    accuracy = results["correct"] / total * 100
    avg_confidence = results["total_confidence"] / total

    print(f"\n{'='*80}")
    print(f"SUMMARY - {name}")
    print(f"{'='*80}")
    print(f"Accuracy: {results['correct']}/{total} = {accuracy:.1f}%")
    print(f"Average confidence: {avg_confidence:.2%}")
    print(f"Incorrect: {results['incorrect']}")

    return results

def main():
    print("="*80)
    print("CLASSIFIER COMPARISON TEST")
    print("="*80)

    config = load_config()

    # Change model to qwen2.5:7b for improved classifier
    config_improved = config.copy()
    config_improved['ai']['ollama']['model'] = 'qwen2.5:7b'

    db = DatabaseManager(config)

    print("\n🔵 Initializing classifiers...")

    # OLD classifier
    old_classifier = AIClassifier(config, db)

    # NEW improved classifier
    new_classifier = ImprovedAIClassifier(config_improved, db)

    # Test OLD
    old_results = test_classifier(old_classifier, TEST_CASES, "OLD Classifier (llama3.2:3b)")

    # Test NEW
    new_results = test_classifier(new_classifier, TEST_CASES, "IMPROVED Classifier (qwen2.5:7b)")

    # Final comparison
    print(f"\n{'='*80}")
    print("FINAL COMPARISON")
    print(f"{'='*80}")

    old_accuracy = old_results["correct"] / len(TEST_CASES) * 100
    new_accuracy = new_results["correct"] / len(TEST_CASES) * 100
    improvement = new_accuracy - old_accuracy

    old_conf = old_results["total_confidence"] / len(TEST_CASES)
    new_conf = new_results["total_confidence"] / len(TEST_CASES)
    conf_improvement = (new_conf - old_conf) * 100

    print(f"\nAccuracy:")
    print(f"  OLD: {old_accuracy:.1f}%")
    print(f"  NEW: {new_accuracy:.1f}%")
    print(f"  {'🔺' if improvement > 0 else '🔻'} Improvement: {improvement:+.1f}%")

    print(f"\nAverage Confidence:")
    print(f"  OLD: {old_conf:.2%}")
    print(f"  NEW: {new_conf:.2%}")
    print(f"  {'🔺' if conf_improvement > 0 else '🔻'} Improvement: {conf_improvement:+.1f}pp")

    print(f"\n{'='*80}")

    # Detailed comparison
    print(f"\nDetailed Comparison:")
    print(f"{'Test':<20} {'Expected':<15} {'Old':<15} {'New':<15} {'Status'}")
    print(f"{'-'*80}")

    for i, test in enumerate(TEST_CASES):
        old_pred = old_results['details'][i]['predicted']
        new_pred = new_results['details'][i]['predicted']
        expected = test['expected']

        old_ok = "✓" if old_pred == expected else "✗"
        new_ok = "✓" if new_pred == expected else "✗"

        if old_pred != expected and new_pred == expected:
            status = "🔺 FIXED"
        elif old_pred == expected and new_pred != expected:
            status = "🔻 BROKEN"
        elif old_pred == expected and new_pred == expected:
            status = "✓ OK"
        else:
            status = "✗ Still wrong"

        print(f"{test['name']:<20} {expected:<15} {old_pred:<12}{old_ok}  {new_pred:<12}{new_ok}  {status}")

if __name__ == "__main__":
    main()
