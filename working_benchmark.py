#!/usr/bin/env python3
"""
Funkční benchmark srovnání klasifikátorů
Testuje skutečné funkce na reálných datech
"""

import json
import time
import sys
from pathlib import Path

# Load test data
test_data_file = Path.home() / 'maj-document-recognition' / 'test_emails_dec2024.json'
with open(test_data_file, 'r', encoding='utf-8') as f:
    test_emails = json.load(f)

print("=" * 70)
print("🔬 BENCHMARK KLASIFIKÁTORŮ DOKUMENTŮ (Reálný)")
print("=" * 70)
print(f"\n📊 Testovací dataset: {len(test_emails)} emailů od 1.12.2024\n")

# Add paths
sys.path.insert(0, str(Path.home() / "apps" / "maj-subscriptions-local"))

results = {}

# ============================================================================
# TEST 1: Universal Business Classifier
# ============================================================================
print("=" * 70)
print("TEST 1: Universal Business Classifier")
print("=" * 70)

try:
    from universal_business_classifier import UniversalBusinessClassifier

    classifier = UniversalBusinessClassifier()

    start_time = time.time()
    classifications = []
    errors = 0

    for email in test_emails:
        try:
            text = f"{email['subject']}\n{email['body'][:2000]}"
            result = classifier.classify(text)
            classifications.append({
                'subject': email['subject'][:50],
                'type': result.document_type.value if hasattr(result, 'document_type') else 'unknown',
                'confidence': result.confidence if hasattr(result, 'confidence') else 0.0
            })
        except Exception as e:
            errors += 1

    elapsed = time.time() - start_time
    results['universal_business'] = {
        'name': 'Universal Business Classifier',
        'total': len(test_emails),
        'processed': len(test_emails) - errors,
        'errors': errors,
        'time': elapsed,
        'speed': len(test_emails) / elapsed,
        'success_rate': (len(test_emails) - errors) / len(test_emails) * 100
    }

    print(f"✅ Hotovo: {len(test_emails)} emailů za {elapsed:.1f}s ({len(test_emails)/elapsed:.1f} email/s)")
    print(f"📊 Úspěšnost: {results['universal_business']['success_rate']:.1f}%")
    print(f"⚠️  Chyby: {errors}")

except Exception as e:
    print(f"❌ Selhalo: {e}")
    results['universal_business'] = {'error': str(e)}

# ============================================================================
# TEST 2: Reklamní Filtr (Marketing Email Detector)
# ============================================================================
print("\n" + "=" * 70)
print("TEST 2: Reklamní Filtr (Marketing Detector)")
print("=" * 70)

try:
    from reklamni_filtr import ReklamniFiltr

    filtr = ReklamniFiltr()

    start_time = time.time()
    classifications = []
    marketing_count = 0
    errors = 0

    for email in test_emails:
        try:
            is_marketing = filtr.je_reklamni(
                subject=email['subject'],
                sender=email['from'],
                body=email['body'][:1000]
            )

            if is_marketing:
                marketing_count += 1

            classifications.append({
                'subject': email['subject'][:50],
                'is_marketing': is_marketing
            })
        except Exception as e:
            errors += 1

    elapsed = time.time() - start_time
    results['reklamni_filtr'] = {
        'name': 'Reklamní Filtr',
        'total': len(test_emails),
        'processed': len(test_emails) - errors,
        'errors': errors,
        'marketing_found': marketing_count,
        'time': elapsed,
        'speed': len(test_emails) / elapsed,
        'success_rate': (len(test_emails) - errors) / len(test_emails) * 100
    }

    print(f"✅ Hotovo: {len(test_emails)} emailů za {elapsed:.1f}s ({len(test_emails)/elapsed:.1f} email/s)")
    print(f"📊 Úspěšnost: {results['reklamni_filtr']['success_rate']:.1f}%")
    print(f"📧 Reklamních emailů: {marketing_count}/{len(test_emails)} ({100*marketing_count/len(test_emails):.1f}%)")
    print(f"⚠️  Chyby: {errors}")

except Exception as e:
    print(f"❌ Selhalo: {e}")
    results['reklamni_filtr'] = {'error': str(e)}

# ============================================================================
# TEST 3: Soudní Filtr (Legal Document Detector)
# ============================================================================
print("\n" + "=" * 70)
print("TEST 3: Soudní Filtr (Legal Document Detector)")
print("=" * 70)

try:
    from soudni_filtr import SoudniFiltr

    filtr = SoudniFiltr()

    start_time = time.time()
    classifications = []
    legal_count = 0
    errors = 0

    for email in test_emails:
        try:
            text = f"{email['subject']}\n{email['body'][:2000]}"
            is_legal = filtr.je_soudni(text)

            if is_legal:
                legal_count += 1

            classifications.append({
                'subject': email['subject'][:50],
                'is_legal': is_legal
            })
        except Exception as e:
            errors += 1

    elapsed = time.time() - start_time
    results['soudni_filtr'] = {
        'name': 'Soudní Filtr',
        'total': len(test_emails),
        'processed': len(test_emails) - errors,
        'errors': errors,
        'legal_found': legal_count,
        'time': elapsed,
        'speed': len(test_emails) / elapsed,
        'success_rate': (len(test_emails) - errors) / len(test_emails) * 100
    }

    print(f"✅ Hotovo: {len(test_emails)} emailů za {elapsed:.1f}s ({len(test_emails)/elapsed:.1f} email/s)")
    print(f"📊 Úspěšnost: {results['soudni_filtr']['success_rate']:.1f}%")
    print(f"⚖️  Soudních dokumentů: {legal_count}/{len(test_emails)} ({100*legal_count/len(test_emails):.1f}%)")
    print(f"⚠️  Chyby: {errors}")

except Exception as e:
    print(f"❌ Selhalo: {e}")
    results['soudni_filtr'] = {'error': str(e)}

# ============================================================================
# TEST 4: CZ Receipt Intelligence
# ============================================================================
print("\n" + "=" * 70)
print("TEST 4: CZ Receipt Intelligence")
print("=" * 70)

try:
    import cz_receipt_intelligence as cz_receipt

    start_time = time.time()
    classifications = []
    receipts_found = 0
    errors = 0

    for email in test_emails:
        try:
            text = f"{email['subject']}\n{email['body'][:2000]}"

            # Zkontroluj jestli obsahuje typické znaky účtenky
            has_ico = cz_receipt.RE_ICO.search(text)
            has_dic = cz_receipt.RE_DIC.search(text)
            has_amount = cz_receipt.RE_AMOUNT.search(text)
            has_eet = cz_receipt.RE_EET_FIK.search(text) or cz_receipt.RE_EET_BKP.search(text)

            is_receipt = bool(has_ico or has_dic or has_eet) and bool(has_amount)

            if is_receipt:
                receipts_found += 1

            classifications.append({
                'subject': email['subject'][:50],
                'is_receipt': is_receipt,
                'has_ico': bool(has_ico),
                'has_dic': bool(has_dic),
                'has_amount': bool(has_amount),
                'has_eet': bool(has_eet)
            })
        except Exception as e:
            errors += 1

    elapsed = time.time() - start_time
    results['cz_receipt'] = {
        'name': 'CZ Receipt Intelligence',
        'total': len(test_emails),
        'processed': len(test_emails) - errors,
        'errors': errors,
        'receipts_found': receipts_found,
        'time': elapsed,
        'speed': len(test_emails) / elapsed,
        'success_rate': (len(test_emails) - errors) / len(test_emails) * 100
    }

    print(f"✅ Hotovo: {len(test_emails)} emailů za {elapsed:.1f}s ({len(test_emails)/elapsed:.1f} email/s)")
    print(f"📊 Úspěšnost: {results['cz_receipt']['success_rate']:.1f}%")
    print(f"🧾 Účtenek nalezeno: {receipts_found}/{len(test_emails)} ({100*receipts_found/len(test_emails):.1f}%)")
    print(f"⚠️  Chyby: {errors}")

except Exception as e:
    print(f"❌ Selhalo: {e}")
    results['cz_receipt'] = {'error': str(e)}

# ============================================================================
# VÝSLEDKY
# ============================================================================
print("\n" + "=" * 70)
print("📊 SROVNÁNÍ VÝSLEDKŮ")
print("=" * 70)

# Filtruj platné výsledky
valid_results = [(k, v) for k, v in results.items() if 'error' not in v]

if valid_results:
    # Seřaď podle úspěšnosti
    sorted_results = sorted(valid_results, key=lambda x: x[1].get('success_rate', 0), reverse=True)

    print(f"\n{'Klasifikátor':<30} {'Rychlost':>15} {'Úspěšnost':>12} {'Chyby':>10}")
    print("-" * 70)

    for name, result in sorted_results:
        speed = f"{result['speed']:.2f} email/s"
        success = f"{result['success_rate']:.1f}%"
        errors = f"{result['errors']}/{result['total']}"
        display_name = result['name'][:28]

        print(f"{display_name:<30} {speed:>15} {success:>12} {errors:>10}")

    # Vítěz
    winner_name, winner = sorted_results[0]
    print("\n" + "=" * 70)
    print(f"🏆 VÍTĚZ: {winner['name']}")
    print(f"   Rychlost: {winner['speed']:.2f} emailů/s")
    print(f"   Úspěšnost: {winner['success_rate']:.1f}%")
    print(f"   Chybovost: {winner['errors']}/{winner['total']} ({100*winner['errors']/winner['total']:.1f}%)")
    print(f"   Celkový čas: {winner['time']:.1f}s")
    print("=" * 70)

    # Statistiky
    print("\n📈 DETAILNÍ STATISTIKY:")
    print("-" * 70)

    for name, result in sorted_results:
        print(f"\n{result['name']}:")
        if 'marketing_found' in result:
            print(f"  📧 Reklamních emailů: {result['marketing_found']}")
        if 'legal_found' in result:
            print(f"  ⚖️  Soudních dokumentů: {result['legal_found']}")
        if 'receipts_found' in result:
            print(f"  🧾 Účtenek: {result['receipts_found']}")

    # Ulož výsledky
    output_file = Path.home() / 'maj-document-recognition' / 'benchmark_results_working.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Výsledky uloženy: {output_file}")

else:
    print("\n❌ Žádné platné výsledky k porovnání!")

print("\n✅ Benchmark dokončen!")
