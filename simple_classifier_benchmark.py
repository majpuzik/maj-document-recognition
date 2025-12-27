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
Jednoduchý benchmark srovnání klasifikátorů
Testuje 4 různé přístupy na stejných datech
"""

import json
import time
import sys
from pathlib import Path

# Load test data
test_data_file = Path(__file__).parent / 'test_emails_dec2024.json'
with open(test_data_file, 'r', encoding='utf-8') as f:
    test_emails = json.load(f)

print("=" * 70)
print("🔬 BENCHMARK KLASIFIKÁTORŮ DOKUMENTŮ")
print("=" * 70)
print(f"\n📊 Testovací dataset: {len(test_emails)} emailů od 1.12.2024")

# Test každého klasifikátoru samostatně
results = {}

# ============================================================================
# TEST 1: CZ Receipt Intelligence (cz_receipt_intelligence.py)
# ============================================================================
print("\n" + "=" * 70)
print("TEST 1: CZ Receipt Intelligence")
print("=" * 70)

try:
    sys.path.insert(0, str(Path.home() / "apps" / "maj-subscriptions-local"))
    from cz_receipt_intelligence import extract_receipt_info, classify_receipt_type

    start_time = time.time()
    classifications = []
    errors = 0

    for email in test_emails:
        try:
            # Simuluj zpracování emailu jako účtenky
            text = f"{email['subject']} {email['body'][:500]}"
            receipt_type = classify_receipt_type(text)
            classifications.append({
                'subject': email['subject'][:50],
                'classification': receipt_type,
                'confidence': 0.8  # placeholder
            })
        except Exception as e:
            errors += 1
            classifications.append({'subject': email['subject'][:50], 'error': str(e)})

    elapsed = time.time() - start_time
    results['cz_receipt_intelligence'] = {
        'name': 'CZ Receipt Intelligence',
        'total': len(test_emails),
        'processed': len(classifications),
        'errors': errors,
        'time': elapsed,
        'speed': len(test_emails) / elapsed,
        'classifications': classifications
    }

    print(f"✅ Hotovo: {len(test_emails)} emailů za {elapsed:.1f}s ({len(test_emails)/elapsed:.1f} email/s)")
    print(f"⚠️  Chyby: {errors}")

except Exception as e:
    print(f"❌ Selhalo: {e}")
    results['cz_receipt_intelligence'] = {'error': str(e)}

# ============================================================================
# TEST 2: Document Recognition (document_processor.py + classifier.py)
# ============================================================================
print("\n" + "=" * 70)
print("TEST 2: Document Processor + Classifier")
print("=" * 70)

try:
    sys.path.insert(0, str(Path.home() / "maj-document-recognition" / "src"))
    from ai.classifier import EmailClassifier

    classifier = EmailClassifier()

    start_time = time.time()
    classifications = []
    errors = 0

    for email in test_emails:
        try:
            result = classifier.classify(
                subject=email['subject'],
                sender=email['from'],
                body=email['body'][:1000]
            )
            classifications.append({
                'subject': email['subject'][:50],
                'classification': result.get('category', 'unknown'),
                'confidence': result.get('confidence', 0)
            })
        except Exception as e:
            errors += 1
            classifications.append({'subject': email['subject'][:50], 'error': str(e)})

    elapsed = time.time() - start_time
    results['document_processor'] = {
        'name': 'Document Processor',
        'total': len(test_emails),
        'processed': len(classifications),
        'errors': errors,
        'time': elapsed,
        'speed': len(test_emails) / elapsed,
        'classifications': classifications
    }

    print(f"✅ Hotovo: {len(test_emails)} emailů za {elapsed:.1f}s ({len(test_emails)/elapsed:.1f} email/s)")
    print(f"⚠️  Chyby: {errors}")

except Exception as e:
    print(f"❌ Selhalo: {e}")
    results['document_processor'] = {'error': str(e)}

# ============================================================================
# TEST 3: Ollama Document Classifier
# ============================================================================
print("\n" + "=" * 70)
print("TEST 3: Ollama Document Classifier (AI-powered)")
print("=" * 70)

try:
    sys.path.insert(0, str(Path.home() / "apps" / "maj-subscriptions-local"))
    from ollama_document_classifier import OllamaDocumentClassifier

    ollama_classifier = OllamaDocumentClassifier()

    start_time = time.time()
    classifications = []
    errors = 0

    # Testuj jen první 50 emailů (Ollama je pomalá)
    test_subset = test_emails[:50]

    for email in test_subset:
        try:
            result = ollama_classifier.classify_document(
                text=email['body'][:2000],
                metadata={
                    'subject': email['subject'],
                    'sender': email['from']
                }
            )
            classifications.append({
                'subject': email['subject'][:50],
                'classification': result.get('document_type', 'unknown'),
                'confidence': result.get('confidence', 0)
            })
        except Exception as e:
            errors += 1
            classifications.append({'subject': email['subject'][:50], 'error': str(e)})

    elapsed = time.time() - start_time
    results['ollama_classifier'] = {
        'name': 'Ollama AI Classifier',
        'total': len(test_subset),
        'processed': len(classifications),
        'errors': errors,
        'time': elapsed,
        'speed': len(test_subset) / elapsed if elapsed > 0 else 0,
        'classifications': classifications,
        'note': 'Tested on first 50 emails only (AI slower)'
    }

    print(f"✅ Hotovo: {len(test_subset)} emailů za {elapsed:.1f}s ({len(test_subset)/elapsed:.1f} email/s)")
    print(f"⚠️  Chyby: {errors}")
    print(f"ℹ️  Poznámka: Testováno jen 50 emailů (AI je pomalejší)")

except Exception as e:
    print(f"❌ Selhalo: {e}")
    results['ollama_classifier'] = {'error': str(e)}

# ============================================================================
# TEST 4: Legal Document Identifier
# ============================================================================
print("\n" + "=" * 70)
print("TEST 4: Legal Document Identifier")
print("=" * 70)

try:
    sys.path.insert(0, str(Path.home() / "apps" / "maj-subscriptions-local"))

    # Pokus se načíst legal_doc_identifier
    legal_doc_path = Path.home() / "apps" / "maj-subscriptions-local" / "legal_doc_identifier.py"
    if not legal_doc_path.exists():
        # Try backup location
        legal_doc_path = Path.home() / "maj-document-recognition" / "legal_doc_identifier.py"

    if legal_doc_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("legal_doc_identifier", legal_doc_path)
        legal_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legal_module)

        start_time = time.time()
        classifications = []
        errors = 0

        for email in test_emails:
            try:
                text = f"{email['subject']}\\n{email['body'][:1000]}"
                result = legal_module.classify_document(text)
                classifications.append({
                    'subject': email['subject'][:50],
                    'classification': result.get('type', 'not_legal'),
                    'confidence': result.get('confidence', 0)
                })
            except Exception as e:
                errors += 1
                classifications.append({'subject': email['subject'][:50], 'error': str(e)})

        elapsed = time.time() - start_time
        results['legal_identifier'] = {
            'name': 'Legal Document Identifier',
            'total': len(test_emails),
            'processed': len(classifications),
            'errors': errors,
            'time': elapsed,
            'speed': len(test_emails) / elapsed,
            'classifications': classifications
        }

        print(f"✅ Hotovo: {len(test_emails)} emailů za {elapsed:.1f}s ({len(test_emails)/elapsed:.1f} email/s)")
        print(f"⚠️  Chyby: {errors}")
    else:
        print("⚠️  Skipped: legal_doc_identifier.py not found")
        results['legal_identifier'] = {'skipped': 'file not found'}

except Exception as e:
    print(f"❌ Selhalo: {e}")
    results['legal_identifier'] = {'error': str(e)}

# ============================================================================
# VÝSLEDKY
# ============================================================================
print("\n" + "=" * 70)
print("📊 SROVNÁNÍ VÝSLEDKŮ")
print("=" * 70)

# Filtruj platné výsledky
valid_results = {k: v for k, v in results.items() if 'error' not in v and 'skipped' not in v}

if valid_results:
    # Seřaď podle rychlosti
    sorted_results = sorted(valid_results.items(), key=lambda x: x[1].get('speed', 0), reverse=True)

    print(f"\n{'Klasifikátor':<30} {'Rychlost':>15} {'Chyby':>10} {'Čas':>10}")
    print("-" * 70)

    for name, result in sorted_results:
        speed = f"{result['speed']:.2f} email/s"
        errors = f"{result['errors']}/{result['total']}"
        elapsed = f"{result['time']:.1f}s"
        display_name = result['name'][:28]

        print(f"{display_name:<30} {speed:>15} {errors:>10} {elapsed:>10}")

    # Vítěz
    winner_name, winner = sorted_results[0]
    print("\n" + "=" * 70)
    print(f"🏆 VÍTĚZ: {winner['name']}")
    print(f"   Rychlost: {winner['speed']:.2f} emailů/s")
    print(f"   Chybovost: {winner['errors']}/{winner['total']} ({100*winner['errors']/winner['total']:.1f}%)")
    print(f"   Celkový čas: {winner['time']:.1f}s")
    print("=" * 70)

    # Ulož výsledky
    output_file = Path(__file__).parent / 'benchmark_results_simple.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Výsledky uloženy: {output_file}")

else:
    print("\n❌ Žádné platné výsledky k porovnání!")

print("\n✅ Benchmark dokončen!")
