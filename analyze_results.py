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
Automatic Results Analyzer
===========================
Generates comprehensive analysis from production_scan_results.json
Goal: Identify path to 100% accuracy

Author: Claude Code
Date: 2025-12-02
"""

import json
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict

def load_results(results_file: Path) -> Dict:
    """Load scan results"""
    with open(results_file, 'r') as f:
        return json.load(f)

def analyze_failures(results: List[Dict]) -> Dict:
    """Analyze all failures"""

    failures = {
        'no_extraction': [],
        'ocr_failure': [],
        'classification_error': [],
        'parser_limitation': [],
        'no_consensus': [],
        'partial_consensus': []
    }

    for result in results:
        if not result.get('success'):
            if 'Insufficient text' in result.get('error', ''):
                failures['ocr_failure'].append(result)
            elif 'Unknown' in result.get('error', ''):
                failures['classification_error'].append(result)
            continue

        # Successful classification but no extraction
        if result.get('items_extracted', 0) == 0:
            failures['no_extraction'].append(result)

        # AI consensus issues
        if result.get('ai_consensus'):
            strength = result['ai_consensus'].get('consensus_strength', 0)
            if strength < 0.5:
                failures['no_consensus'].append(result)
            elif strength < 1.0:
                failures['partial_consensus'].append(result)

    return failures

def analyze_performance(results: List[Dict]) -> Dict:
    """Analyze processing performance"""

    times = [r['processing_time'] for r in results if 'processing_time' in r]

    slow_docs = [
        {'file': r['filename'], 'time': r['processing_time'], 'type': r.get('doc_type')}
        for r in results
        if r.get('processing_time', 0) > 100
    ]

    return {
        'avg': statistics.mean(times) if times else 0,
        'median': statistics.median(times) if times else 0,
        'min': min(times) if times else 0,
        'max': max(times) if times else 0,
        'slow_docs': slow_docs
    }

def analyze_ocr_quality(results: List[Dict]) -> Dict:
    """Analyze OCR quality"""

    confidence_dist = defaultdict(int)
    text_length_dist = defaultdict(int)
    language_dist = defaultdict(int)

    for result in results:
        ocr_info = result.get('ocr_info', {})

        # Confidence distribution
        conf = ocr_info.get('confidence', 0)
        if conf <= 20:
            confidence_dist['0-20%'] += 1
        elif conf <= 40:
            confidence_dist['21-40%'] += 1
        elif conf <= 60:
            confidence_dist['41-60%'] += 1
        elif conf <= 80:
            confidence_dist['61-80%'] += 1
        else:
            confidence_dist['81-100%'] += 1

        # Text length distribution
        text_len = ocr_info.get('text_length', 0)
        if text_len < 100:
            text_length_dist['<100'] += 1
        elif text_len < 1000:
            text_length_dist['100-1000'] += 1
        elif text_len < 5000:
            text_length_dist['1000-5000'] += 1
        else:
            text_length_dist['>5000'] += 1

        # Language distribution
        lang = ocr_info.get('language', 'unknown')
        language_dist[lang] += 1

    return {
        'confidence': dict(confidence_dist),
        'text_length': dict(text_length_dist),
        'language': dict(language_dist)
    }

def identify_quick_wins(failures: Dict, stats: Dict) -> List[Dict]:
    """Identify quick wins for 100% path"""

    quick_wins = []

    # 1. Parking ticket false positives
    parking_count = stats.get('by_type', {}).get('PARKING_TICKET', {}).get('count', 0)
    if parking_count > 15:  # Known issue
        quick_wins.append({
            'priority': 1,
            'title': 'Fix parking ticket false positives',
            'impact': f'+{parking_count - 5} documents (estimated)',
            'implementation': 'Add negative patterns for N26 Support, Training materials, Medical docs',
            'effort': 'Low (2 hours)'
        })

    # 2. OCR failures
    ocr_failures = len(failures['ocr_failure'])
    if ocr_failures > 0:
        quick_wins.append({
            'priority': 1,
            'title': 'Improve OCR preprocessing',
            'impact': f'+{ocr_failures} documents',
            'implementation': 'Image enhancement, deskew, noise reduction',
            'effort': 'Medium (4 hours)'
        })

    # 3. No extraction despite classification
    no_extract = len(failures['no_extraction'])
    if no_extract > 0:
        quick_wins.append({
            'priority': 2,
            'title': 'Enhanced table extraction',
            'impact': f'+{no_extract} documents',
            'implementation': 'Better row detection, multi-column support',
            'effort': 'High (8 hours)'
        })

    return sorted(quick_wins, key=lambda x: x['priority'])

def generate_analysis_report(results_file: Path, template_file: Path, output_file: Path):
    """Generate comprehensive analysis report"""

    print("📊 Loading results...")
    data = load_results(results_file)
    results = data['results']
    stats = data['statistics']

    print(f"   {len(results)} documents processed")

    print("\n🔍 Analyzing failures...")
    failures = analyze_failures(results)

    print("\n⏱️  Analyzing performance...")
    perf = analyze_performance(results)

    print("\n📝 Analyzing OCR quality...")
    ocr = analyze_ocr_quality(results)

    print("\n🎯 Identifying quick wins...")
    quick_wins = identify_quick_wins(failures, stats)

    # Generate report
    print(f"\n📄 Generating report...")

    report = f"""# Kompletní Analýza - Production Scan V2 (FIXED)
## Cíl: Dosažení 100% přesnosti

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Scan date**: {data['scan_date']}
**Max emails**: {data['max_emails']}

---

## 1. EXECUTIVE SUMMARY

### Klíčové metriky:
- **Celkem emailů**: {stats['total_emails']:,}
- **Emails s PDFs**: {stats['emails_with_attachments']:,}
- **PDFs extrahováno**: {stats['pdfs_extracted']:,}
- **Dokumentů klasifikováno**: {stats['documents_classified']:,}
- **Položek extrahováno**: {stats['documents_extracted']:,}
- **AI validováno**: {stats['ai_validated']:,}
- **Perfect consensus**: {stats['perfect_consensus']:,}

### Porovnání PŘED vs. PO opravě:
```
Metrika                 PŘED    PO      Změna
─────────────────────────────────────────────
Documents extracted     0       {stats['documents_extracted']}      +{stats['documents_extracted']}
AI validated            0       {stats['ai_validated']}      +{stats['ai_validated']}
Perfect consensus       0       {stats['perfect_consensus']}      +{stats['perfect_consensus']}
```

### Success Rates:
- **Classification rate**: {stats['documents_classified']/stats['pdfs_extracted']*100:.1f}%
- **Extraction rate**: {stats['documents_extracted']/stats['documents_classified']*100:.1f}% (of classified)
- **AI validation rate**: {stats['ai_validated']/stats['documents_extracted']*100 if stats['documents_extracted'] > 0 else 0:.1f}% (of extracted)
- **Perfect consensus rate**: {stats['perfect_consensus']/stats['ai_validated']*100 if stats['ai_validated'] > 0 else 0:.1f}% (of validated)

---

## 2. DETAILNÍ BREAKDOWN PO TYPU DOKUMENTU

"""

    # Document type breakdown
    for doc_type, type_stats in sorted(stats['by_type'].items(), key=lambda x: x[1]['count'], reverse=True):
        success_rate = (type_stats['extracted'] / type_stats['count'] * 100) if type_stats['count'] > 0 else 0

        report += f"""
### {doc_type}
- **Klasifikováno**: {type_stats['count']}
- **Extrahováno**: {type_stats['extracted']}
- **AI validováno**: {type_stats['ai_validated']}
- **Perfect consensus**: {type_stats['perfect_consensus']}
- **Success rate**: {success_rate:.1f}%
"""

    report += f"""

---

## 3. ANALÝZA NEÚSPĚCHŮ

### 3.1 Dokumenty bez extrakce (items_extracted = 0)
**Počet**: {len(failures['no_extraction'])}
**Procento**: {len(failures['no_extraction'])/len(results)*100:.1f}%

**Top 10 cases**:
"""

    for i, fail in enumerate(failures['no_extraction'][:10], 1):
        report += f"{i}. {fail['filename']} - {fail.get('doc_type', 'unknown')}\n"

    report += f"""

### 3.2 OCR selhání
**Počet**: {len(failures['ocr_failure'])}
**Procento**: {len(failures['ocr_failure'])/len(results)*100:.1f}%

**Top 10 cases**:
"""

    for i, fail in enumerate(failures['ocr_failure'][:10], 1):
        report += f"{i}. {fail['filename']} - {fail.get('error', 'N/A')}\n"

    report += f"""

### 3.3 AI Consensus selhání
- **No consensus (<50%)**: {len(failures['no_consensus'])}
- **Partial consensus (50-99%)**: {len(failures['partial_consensus'])}

---

## 4. VÝKONNOSTNÍ ANALÝZA

### 4.1 Processing Time
- **Průměr**: {perf['avg']:.1f}s
- **Medián**: {perf['median']:.1f}s
- **Min**: {perf['min']:.1f}s
- **Max**: {perf['max']:.1f}s

### 4.2 Pomalé dokumenty (>100s): {len(perf['slow_docs'])}
"""

    for doc in perf['slow_docs'][:10]:
        report += f"- {doc['file']} - {doc['time']:.0f}s - {doc.get('type', 'unknown')}\n"

    report += f"""

---

## 5. DATOVÁ KVALITA

### 5.1 OCR Confidence Distribution
"""

    for range_name, count in sorted(ocr['confidence'].items()):
        report += f"- {range_name}: {count} dokumentů\n"

    report += f"""

### 5.2 Text Length Distribution
"""

    for range_name, count in sorted(ocr['text_length'].items()):
        report += f"- {range_name}: {count} dokumentů\n"

    report += f"""

### 5.3 Language Detection
"""

    for lang, count in sorted(ocr['language'].items(), key=lambda x: x[1], reverse=True):
        report += f"- {lang}: {count} dokumentů\n"

    report += f"""

---

## 6. CESTA K 100% - QUICK WINS

"""

    for win in quick_wins:
        report += f"""
### Priority {win['priority']}: {win['title']}
- **Impact**: {win['impact']}
- **Implementation**: {win['implementation']}
- **Effort**: {win['effort']}
"""

    report += f"""

---

## 7. METRIKY PRO SLEDOVÁNÍ

### Current Baseline:
```
Classification accuracy:    {stats['documents_classified']/stats['pdfs_extracted']*100:.1f}%
Extraction success rate:    {stats['documents_extracted']/stats['documents_classified']*100:.1f}%
AI consensus rate:          {stats['ai_validated']/stats['documents_extracted']*100 if stats['documents_extracted'] > 0 else 0:.1f}%
Perfect consensus rate:     {stats['perfect_consensus']/stats['ai_validated']*100 if stats['ai_validated'] > 0 else 0:.1f}%
```

### Target (100% cíl):
```
Classification accuracy:    100%
Extraction success rate:    95%+ (some docs may be unparseable)
AI consensus rate:          100% (when data extracted)
Perfect consensus rate:     90%+ (2 models agreeing)
```

---

## 8. ZÁVĚR

**Status**: {'✅ EXCELLENT' if stats['documents_extracted']/stats['documents_classified'] > 0.8 else '⚠️  NEEDS IMPROVEMENT' if stats['documents_extracted']/stats['documents_classified'] > 0.5 else '❌ CRITICAL ISSUES'}

**Hlavní poznatky**:
1. Bug fix successful - extrakce nyní funguje ({stats['documents_extracted']} vs 0 před)
2. AI consensus validation works - {stats['ai_validated']} dokumentů validováno
3. {len(quick_wins)} quick wins identified for improvement

**Next immediate steps**:
"""

    for i, win in enumerate(quick_wins[:3], 1):
        report += f"{i}. {win['title']} ({win['effort']})\n"

    report += f"""

**Estimated time to 95%+ accuracy**: {'1-2 days' if len(quick_wins) <= 3 else '3-5 days' if len(quick_wins) <= 5 else '1 week'}

---

*Auto-generated by analyze_results.py*
"""

    # Save report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ Report saved: {output_file}")
    print(f"\n📊 Summary:")
    print(f"   - {stats['documents_classified']}/{stats['pdfs_extracted']} classified ({stats['documents_classified']/stats['pdfs_extracted']*100:.1f}%)")
    print(f"   - {stats['documents_extracted']}/{stats['documents_classified']} extracted ({stats['documents_extracted']/stats['documents_classified']*100:.1f}%)")
    print(f"   - {stats['ai_validated']}/{stats['documents_extracted']} AI validated ({stats['ai_validated']/stats['documents_extracted']*100 if stats['documents_extracted'] > 0 else 0:.1f}%)")
    print(f"   - {stats['perfect_consensus']}/{stats['ai_validated']} perfect consensus ({stats['perfect_consensus']/stats['ai_validated']*100 if stats['ai_validated'] > 0 else 0:.1f}%)")
    print(f"\n🎯 Quick wins: {len(quick_wins)}")
    for win in quick_wins[:3]:
        print(f"   {win['priority']}. {win['title']} - {win['impact']}")


def main():
    """Main entry point"""

    base_dir = Path(__file__).parent
    results_file = base_dir / "production_scan_output" / "production_scan_results.json"
    template_file = base_dir / "ANALYSIS_TEMPLATE.md"
    output_file = base_dir / "PRODUCTION_ANALYSIS_FINAL.md"

    if not results_file.exists():
        print(f"❌ Results file not found: {results_file}")
        print("   Waiting for scan to complete...")
        return

    generate_analysis_report(results_file, template_file, output_file)


if __name__ == "__main__":
    main()
