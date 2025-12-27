# Kompletní Analýza - Production Scan V2 (FIXED)
## Cíl: Dosažení 100% přesnosti

**Generated**: 2025-12-03 19:55:26
**Scan date**: 2025-12-03T09:27:50.089133
**Max emails**: 10000

---

## 1. EXECUTIVE SUMMARY

### Klíčové metriky:
- **Celkem emailů**: 10,000
- **Emails s PDFs**: 157
- **PDFs extrahováno**: 224
- **Dokumentů klasifikováno**: 221
- **Položek extrahováno**: 110
- **AI validováno**: 110
- **Perfect consensus**: 88

### Porovnání PŘED vs. PO opravě:
```
Metrika                 PŘED    PO      Změna
─────────────────────────────────────────────
Documents extracted     0       110      +110
AI validated            0       110      +110
Perfect consensus       0       88      +88
```

### Success Rates:
- **Classification rate**: 98.7%
- **Extraction rate**: 49.8% (of classified)
- **AI validation rate**: 100.0% (of extracted)
- **Perfect consensus rate**: 80.0% (of validated)

---

## 2. DETAILNÍ BREAKDOWN PO TYPU DOKUMENTU


### INVOICE
- **Klasifikováno**: 112
- **Extrahováno**: 97
- **AI validováno**: 97
- **Perfect consensus**: 76
- **Success rate**: 86.6%

### PARKING_TICKET
- **Klasifikováno**: 28
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### CAR_SERVICE
- **Klasifikováno**: 19
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### ORDER
- **Klasifikováno**: 15
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### UNKNOWN
- **Klasifikováno**: 12
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### RECEIPT
- **Klasifikováno**: 11
- **Extrahováno**: 11
- **AI validováno**: 11
- **Perfect consensus**: 10
- **Success rate**: 100.0%

### CAR_WASH
- **Klasifikováno**: 7
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### CONTRACT
- **Klasifikováno**: 5
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### BANK_STATEMENT
- **Klasifikováno**: 5
- **Extrahováno**: 2
- **AI validováno**: 2
- **Perfect consensus**: 2
- **Success rate**: 40.0%

### GLASS_WORK
- **Klasifikováno**: 3
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### PROFORMA
- **Klasifikováno**: 2
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### DELIVERY_NOTE
- **Klasifikováno**: 1
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%

### PAYMENT_DOCUMENT
- **Klasifikováno**: 1
- **Extrahováno**: 0
- **AI validováno**: 0
- **Perfect consensus**: 0
- **Success rate**: 0.0%


---

## 3. ANALÝZA NEÚSPĚCHŮ

### 3.1 Dokumenty bez extrakce (items_extracted = 0)
**Počet**: 111
**Procento**: 49.6%

**Top 10 cases**:
1. 002350_=?utf-8?q?V=C5=A1eobecn=C3=A9_obchodn=C3=AD_podm=C3=ADnky.pdf?= - CONTRACT
2. 002372_Receipt-2184-3689.pdf - INVOICE
3. 002419_=?utf-8?q?utf-8''Milan_Pu=C5=BE=C3=ADk_v=C3=BDm=C4=9Bna_komponent=C5=AF_f?= =?utf-8?q?ve.pdf?= - CAR_SERVICE
4. 002441_Obchodni podminky.pdf - INVOICE
5. 002445_56921-Monthly-report-4-1-2025.pdf - UNKNOWN
6. 002447_=?utf-8?q?=C5=A0kolen=C3=AD_na_m=C3=ADru_pro_dodavatele.pdf?= - PARKING_TICKET
7. 002447_kurzy-otidea-dodavatele.pdf - PARKING_TICKET
8. 002452_oznameni_o_zmene_smluvnich_podminek-2025-05-05-.pdf - CAR_WASH
9. 002453_oznameni_o_zmene_smluvnich_podminek-2025-05-05-.pdf - CAR_WASH
10. 002454_Obchodni podminky.pdf - INVOICE


### 3.2 OCR selhání
**Počet**: 3
**Procento**: 1.3%

**Top 10 cases**:
1. 008638_Pojisteni_majetku_227533843_186992056.pdf - Insufficient text extracted
2. 008640_Pojisteni_majetku_224957305_186736356.pdf - Insufficient text extracted
3. 008961_measurement_report.pdf - Insufficient text extracted


### 3.3 AI Consensus selhání
- **No consensus (<50%)**: 0
- **Partial consensus (50-99%)**: 22

---

## 4. VÝKONNOSTNÍ ANALÝZA

### 4.1 Processing Time
- **Průměr**: 181.3s
- **Medián**: 128.4s
- **Min**: 0.0s
- **Max**: 1613.1s

### 4.2 Pomalé dokumenty (>100s): 116
- 000898_Invoice_2981894232.PDF - 379s - INVOICE
- 001559_proforma-faktura-z150.pdf - 449s - INVOICE
- 001682_992025400807.pdf - 571s - INVOICE
- 001687_992025400807.pdf - 405s - INVOICE
- 002002_992025400807.pdf - 333s - INVOICE
- 002046_home-assistant-cloud-invoice-2025-05-17.pdf - 132s - INVOICE
- 002261_Invoice-C93DFB42-0007.pdf - 134s - INVOICE
- 002261_Receipt-2311-4012-7052.pdf - 133s - INVOICE
- 002268_Faktura-2025-05-14-121455825.pdf - 194s - INVOICE
- 002361_Invoice-92EBA450-4479.pdf - 149s - INVOICE


---

## 5. DATOVÁ KVALITA

### 5.1 OCR Confidence Distribution
- 0-20%: 3 dokumentů
- 61-80%: 18 dokumentů
- 81-100%: 203 dokumentů


### 5.2 Text Length Distribution
- 100-1000: 61 dokumentů
- 1000-5000: 89 dokumentů
- <100: 3 dokumentů
- >5000: 71 dokumentů


### 5.3 Language Detection
- Czech: 209 dokumentů
- Multi-language, Czech: 10 dokumentů
- error: 3 dokumentů
- Multi-language, English, Czech: 1 dokumentů
- German, Czech: 1 dokumentů


---

## 6. CESTA K 100% - QUICK WINS


### Priority 1: Fix parking ticket false positives
- **Impact**: +23 documents (estimated)
- **Implementation**: Add negative patterns for N26 Support, Training materials, Medical docs
- **Effort**: Low (2 hours)

### Priority 1: Improve OCR preprocessing
- **Impact**: +3 documents
- **Implementation**: Image enhancement, deskew, noise reduction
- **Effort**: Medium (4 hours)

### Priority 2: Enhanced table extraction
- **Impact**: +111 documents
- **Implementation**: Better row detection, multi-column support
- **Effort**: High (8 hours)


---

## 7. METRIKY PRO SLEDOVÁNÍ

### Current Baseline:
```
Classification accuracy:    98.7%
Extraction success rate:    49.8%
AI consensus rate:          100.0%
Perfect consensus rate:     80.0%
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

**Status**: ❌ CRITICAL ISSUES

**Hlavní poznatky**:
1. Bug fix successful - extrakce nyní funguje (110 vs 0 před)
2. AI consensus validation works - 110 dokumentů validováno
3. 3 quick wins identified for improvement

**Next immediate steps**:
1. Fix parking ticket false positives (Low (2 hours))
2. Improve OCR preprocessing (Medium (4 hours))
3. Enhanced table extraction (High (8 hours))


**Estimated time to 95%+ accuracy**: 1-2 days

---

*Auto-generated by analyze_results.py*
