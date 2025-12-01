#!/usr/bin/env python3
"""
Benchmark test pro srovnání všech email klasifikátorů
Testuje na Thunderbird emailech od 1.12.2024 do dnes
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import mailbox
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.util

# Přidej cesty k modulům
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path.home() / "apps" / "maj-subscriptions-local"))

# Najdi Thunderbird profil
def find_thunderbird_profile():
    """Najde Thunderbird profil"""
    thunderbird_base = Path.home() / "Library" / "Thunderbird" / "Profiles"
    if not thunderbird_base.exists():
        return None

    profiles = list(thunderbird_base.glob("*.default-release"))
    if not profiles:
        profiles = list(thunderbird_base.glob("*.default"))

    return profiles[0] if profiles else None

# Načti emaily z Thunderbird
def load_emails_from_thunderbird(start_date, end_date):
    """Načte emaily z Thunderbird v daném období"""
    profile = find_thunderbird_profile()
    if not profile:
        print("❌ Thunderbird profil nenalezen!")
        return []

    print(f"📂 Thunderbird profil: {profile}")

    # Najdi všechny .msf soubory (indexy mailboxů)
    mail_dir = profile / "Mail"
    emails = []

    for mbox_file in mail_dir.rglob("*"):
        # Přeskoč indexy a složky
        if mbox_file.suffix in ['.msf', '.dat'] or mbox_file.is_dir():
            continue

        # Přeskoč systémové složky
        if mbox_file.name in ['msgFilterRules.dat', 'filterlog.html']:
            continue

        try:
            mbox = mailbox.mbox(str(mbox_file))
            for msg in mbox:
                # Extrahuj datum
                date_str = msg.get('Date', '')
                if not date_str:
                    continue

                try:
                    from email.utils import parsedate_to_datetime
                    msg_date = parsedate_to_datetime(date_str)

                    # Filtruj podle data
                    if start_date <= msg_date <= end_date:
                        emails.append({
                            'subject': msg.get('Subject', ''),
                            'from': msg.get('From', ''),
                            'to': msg.get('To', ''),
                            'date': msg_date.isoformat(),
                            'body': get_email_body(msg),
                            'has_attachments': has_attachments(msg),
                            'source': str(mbox_file.name)
                        })
                except Exception as e:
                    continue

        except Exception as e:
            print(f"⚠️  Chyba při čtení {mbox_file.name}: {e}")
            continue

    return emails

def get_email_body(msg):
    """Extrahuj tělo emailu"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            body = str(msg.get_payload())

    return body[:5000]  # Limit na 5000 znaků

def has_attachments(msg):
    """Zkontroluj, zda email má přílohy"""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                return True
    return False

# Klasifikátory k testování
CLASSIFIERS = {
    'ollama_email_classifier': {
        'path': Path.home() / 'apps' / 'maj-subscriptions-local' / 'ollama_email_classifier.py',
        'function': 'classify_email'
    },
    'scan_emails_with_ollama': {
        'path': Path.home() / 'maj-document-recognition' / 'scan_emails_with_ollama.py',
        'function': 'scan_email'
    },
    'classifier_improved': {
        'path': Path.home() / 'maj-document-recognition' / 'src' / 'ai' / 'classifier_improved.py',
        'function': 'classify_email'
    },
    'ollama_classifier': {
        'path': Path.home() / 'maj-document-recognition' / 'src' / 'ai' / 'ollama_classifier.py',
        'function': 'classify'
    }
}

def load_classifier_module(classifier_name, classifier_info):
    """Dynamicky načte klasifikátor"""
    try:
        spec = importlib.util.spec_from_file_location(
            classifier_name,
            classifier_info['path']
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"❌ Nepodařilo se načíst {classifier_name}: {e}")
        return None

def run_classifier(classifier_name, emails):
    """Spustí jeden klasifikátor na všech emailech"""
    print(f"\n🔄 Spouštím {classifier_name}...")

    classifier_info = CLASSIFIERS[classifier_name]
    module = load_classifier_module(classifier_name, classifier_info)

    if not module:
        return {
            'classifier': classifier_name,
            'error': 'Failed to load module',
            'results': []
        }

    results = []
    start_time = time.time()

    for idx, email in enumerate(emails):
        try:
            # Pokus se zavolat klasifikační funkci
            func_name = classifier_info['function']
            if hasattr(module, func_name):
                func = getattr(module, func_name)
                result = func(email)
                results.append({
                    'email_idx': idx,
                    'subject': email['subject'][:50],
                    'classification': result
                })
            else:
                results.append({
                    'email_idx': idx,
                    'subject': email['subject'][:50],
                    'error': f'Function {func_name} not found'
                })
        except Exception as e:
            results.append({
                'email_idx': idx,
                'subject': email['subject'][:50],
                'error': str(e)
            })

        if (idx + 1) % 10 == 0:
            print(f"  {classifier_name}: {idx + 1}/{len(emails)} emailů zpracováno")

    elapsed = time.time() - start_time

    return {
        'classifier': classifier_name,
        'total_emails': len(emails),
        'processed': len(results),
        'errors': sum(1 for r in results if 'error' in r),
        'elapsed_time': elapsed,
        'emails_per_second': len(emails) / elapsed if elapsed > 0 else 0,
        'results': results
    }

def main():
    print("=" * 70)
    print("🔬 BENCHMARK TEST VŠECH EMAIL KLASIFIKÁTORŮ")
    print("=" * 70)

    # Datum range
    end_date = datetime.now()
    start_date = datetime(2024, 12, 1)

    print(f"\n📅 Testovací období: {start_date.date()} - {end_date.date()}")

    # Načti emaily
    print("\n📧 Načítám emaily z Thunderbird...")
    emails = load_emails_from_thunderbird(start_date, end_date)

    print(f"✅ Načteno {len(emails)} emailů")

    if len(emails) == 0:
        print("❌ Žádné emaily nenalezeny v daném období!")
        return

    # Ulož testovací dataset
    test_data_file = Path(__file__).parent / 'benchmark_test_emails.json'
    with open(test_data_file, 'w', encoding='utf-8') as f:
        json.dump(emails, f, indent=2, ensure_ascii=False)
    print(f"💾 Testovací data uložena: {test_data_file}")

    # Spusť všechny klasifikátory paralelně
    print("\n" + "=" * 70)
    print("🚀 Spouštím klasifikátory paralelně...")
    print("=" * 70)

    benchmark_results = []

    with ProcessPoolExecutor(max_workers=len(CLASSIFIERS)) as executor:
        futures = {
            executor.submit(run_classifier, name, emails): name
            for name in CLASSIFIERS.keys()
        }

        for future in as_completed(futures):
            classifier_name = futures[future]
            try:
                result = future.result()
                benchmark_results.append(result)
                print(f"✅ {classifier_name} dokončen")
            except Exception as e:
                print(f"❌ {classifier_name} selhal: {e}")
                benchmark_results.append({
                    'classifier': classifier_name,
                    'error': str(e)
                })

    # Vyhodnocení
    print("\n" + "=" * 70)
    print("📊 VÝSLEDKY BENCHMARKU")
    print("=" * 70)

    # Seřaď podle rychlosti
    valid_results = [r for r in benchmark_results if 'error' not in r or r.get('processed', 0) > 0]
    valid_results.sort(key=lambda x: x.get('elapsed_time', float('inf')))

    print(f"\n{'Klasifikátor':<30} {'Rychlost':>15} {'Chyby':>10} {'Čas':>10}")
    print("-" * 70)

    for result in valid_results:
        name = result['classifier']
        speed = f"{result.get('emails_per_second', 0):.2f} email/s"
        errors = f"{result.get('errors', 0)}/{result.get('total_emails', 0)}"
        elapsed = f"{result.get('elapsed_time', 0):.1f}s"

        print(f"{name:<30} {speed:>15} {errors:>10} {elapsed:>10}")

    # Ulož kompletní výsledky
    results_file = Path(__file__).parent / 'benchmark_results.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'email_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_emails': len(emails),
            'results': benchmark_results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Kompletní výsledky uloženy: {results_file}")

    # Vyber nejlepší
    if valid_results:
        best = valid_results[0]
        print("\n" + "=" * 70)
        print(f"🏆 VÍTĚZ: {best['classifier']}")
        print(f"   Rychlost: {best['emails_per_second']:.2f} emailů/s")
        print(f"   Chybovost: {best['errors']}/{best['total_emails']} ({100*best['errors']/best['total_emails']:.1f}%)")
        print(f"   Celkový čas: {best['elapsed_time']:.1f}s")
        print("=" * 70)

if __name__ == "__main__":
    main()
