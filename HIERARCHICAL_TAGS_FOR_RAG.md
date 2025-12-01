# 🏗️ Hierarchická struktura tagů pro RAG systém

## 📋 Požadavky pro RAG
Pro efektivní RAG (Retrieval-Augmented Generation) potřebujeme:
1. **Hierarchickou strukturu** (4 úrovně)
2. **Konzistentní naming** (jednotné pojmenování)
3. **Všechny metadata** jako samostatné tagy
4. **Vztahy mezi tagy** (parent-child)

---

## 🌳 4-úrovňová hierarchie tagů

```
ÚROVEŇ 1: DODAVATEL (Supplier/Provider)
    └── ÚROVEŇ 2: DRUH (Category/Type)
        └── ÚROVEŇ 3: PODSKUPINA (Subcategory)
            └── ÚROVEŇ 4: TYP (Specific Type)
```

---

## 📊 ÚROVEŇ 1: DODAVATEL (Supplier Tags)

### Formát: `supplier:{název}`
### Barva: 🔵 #3498DB (modrá)

```python
SUPPLIERS = {
    # AI Services
    'supplier:Anthropic': 'Anthropic (Claude AI)',
    'supplier:OpenAI': 'OpenAI (ChatGPT, GPT-4)',
    'supplier:Google': 'Google (Gemini, Workspace, Cloud)',
    'supplier:Groq': 'Groq (Fast AI inference)',
    'supplier:Perplexity': 'Perplexity AI',
    'supplier:Together-AI': 'Together AI',

    # Cloud Storage
    'supplier:Dropbox': 'Dropbox',
    'supplier:Google-Drive': 'Google Drive',
    'supplier:OneDrive': 'Microsoft OneDrive',
    'supplier:iCloud': 'Apple iCloud',

    # Dev Tools
    'supplier:GitHub': 'GitHub',
    'supplier:GitLab': 'GitLab',
    'supplier:Vercel': 'Vercel',
    'supplier:Render': 'Render',

    # Media/Creative
    'supplier:ElevenLabs': 'ElevenLabs (AI Voice)',
    'supplier:Luma-AI': 'Luma AI (Video)',
    'supplier:Suno': 'Suno (AI Music)',
    'supplier:Meshy': 'Meshy (3D AI)',

    # Email/Communication
    'supplier:Gmail': 'Gmail',
    'supplier:Proton': 'ProtonMail',
    'supplier:Slack': 'Slack',

    # Other
    'supplier:N8N': 'N8N Automation',
    'supplier:Paperspace': 'Paperspace GPU',
    'supplier:RunPod': 'RunPod GPU'
    # ... všichni z databáze services
}
```

**Celkem: ~30 dodavatelů**

---

## 📁 ÚROVEŇ 2: DRUH (Category Tags)

### Formát: `cat:{druh}`
### Barva: 🟣 #9B59B6 (fialová)

```python
CATEGORIES = {
    # Hlavní kategorie
    'cat:document': 'Dokument',
    'cat:email': 'Email',
    'cat:notification': 'Notifikace',
    'cat:communication': 'Komunikace',
    'cat:financial': 'Finanční dokument',
    'cat:legal': 'Právní dokument',
    'cat:marketing': 'Marketing',
    'cat:technical': 'Technická dokumentace'
}
```

**Celkem: 8 kategorií**

---

## 📑 ÚROVEŇ 3: PODSKUPINA (Subcategory Tags)

### Formát: `sub:{podskupina}`
### Barva: 🟠 #F39C12 (oranžová)

```python
SUBCATEGORIES = {
    # Finanční podskupiny
    'sub:faktura': 'Faktura',
    'sub:dobropis': 'Dobropis',
    'sub:objednavka': 'Objednávka',
    'sub:nabidka': 'Nabídka',
    'sub:uctenka': 'Účtenka',
    'sub:vypis': 'Bankovní výpis',
    'sub:vyzva-k-platbe': 'Výzva k platbě',
    'sub:potvrzeni-platby': 'Potvrzení platby',

    # Email podskupiny
    'sub:newsletter': 'Newsletter',
    'sub:upozorneni': 'Upozornění',
    'sub:promo': 'Propagace',
    'sub:pozvanka': 'Pozvánka',

    # Právní podskupiny
    'sub:smlouva': 'Smlouva',
    'sub:rozhodnuti': 'Rozhodnutí',
    'sub:predvolani': 'Předvolání',

    # Technické podskupiny
    'sub:api-docs': 'API dokumentace',
    'sub:changelog': 'Changelog',
    'sub:release-notes': 'Release notes'
}
```

**Celkem: ~20 podskupin**

---

## 🎯 ÚROVEŇ 4: TYP (Specific Type Tags)

### Formát: `type:{typ}`
### Barva: 🟢 #27AE60 (zelená)

```python
SPECIFIC_TYPES = {
    # Typy faktur
    'type:faktura-dodavatelska': 'Dodavatelská faktura',
    'type:faktura-odberatelska': 'Odběratelská faktura',
    'type:faktura-zalohova': 'Zálohová faktura',
    'type:faktura-proforma': 'Proforma faktura',
    'type:faktura-opravna': 'Opravná faktura',

    # Typy smluv
    'type:smlouva-najemni': 'Nájemní smlouva',
    'type:smlouva-kupni': 'Kupní smlouva',
    'type:smlouva-o-dilo': 'Smlouva o dílo',
    'type:smlouva-licencni': 'Licenční smlouva',

    # Typy newsletterů
    'type:newsletter-weekly': 'Týdenní newsletter',
    'type:newsletter-monthly': 'Měsíční newsletter',
    'type:newsletter-promo': 'Propagační newsletter',

    # Typy notifikací
    'type:notif-system': 'Systémová notifikace',
    'type:notif-security': 'Bezpečnostní upozornění',
    'type:notif-update': 'Update notifikace',
    'type:notif-billing': 'Billing notifikace'
}
```

**Celkem: ~30 specifických typů**

---

## 🔗 METADATA TAGY (Cross-cutting Tags)

### Formát: `meta:{metadata}`
### Barva: ⚪ #95A5A6 (šedá)

```python
METADATA_TAGS = {
    # Stav zpracování
    'meta:ai-classified': 'Klasifikováno AI',
    'meta:manual-review': 'Potřebuje ruční kontrolu',
    'meta:verified': 'Ověřeno',
    'meta:archived': 'Archivováno',

    # Kvalita klasifikace
    'meta:high-confidence': 'Vysoká jistota (>80%)',
    'meta:medium-confidence': 'Střední jistota (50-80%)',
    'meta:low-confidence': 'Nízká jistota (<50%)',

    # Vlastnosti dokumentu
    'meta:has-attachment': 'Má přílohu',
    'meta:has-pdf': 'Má PDF',
    'meta:has-unsubscribe': 'Má odhlašovací link',
    'meta:recurring': 'Opakující se',
    'meta:urgent': 'Urgentní',

    # Zdroj
    'meta:source-email': 'Zdroj: Email',
    'meta:source-scan': 'Zdroj: Scan',
    'meta:source-upload': 'Zdroj: Upload',

    # Jazyk
    'meta:lang-cs': 'Čeština',
    'meta:lang-en': 'Angličtina',
    'meta:lang-de': 'Němčina',

    # Stav platby
    'meta:paid': 'Zaplaceno',
    'meta:unpaid': 'Nezaplaceno',
    'meta:overdue': 'Po splatnosti'
}
```

**Celkem: ~20 metadata tagů**

---

## 📐 PŘÍKLAD: Kompletní tagování faktury od OpenAI

### Dokument:
```
From: billing@openai.com
Subject: Invoice #INV-2024-001234 for November 2024
Date: 2024-11-30
Amount: $150.00
Body: Your monthly invoice for ChatGPT Plus API usage...
Attachment: invoice_nov_2024.pdf
```

### Všechny aplikované tagy:

```yaml
# ÚROVEŇ 1: DODAVATEL
- supplier:OpenAI

# ÚROVEŇ 2: DRUH
- cat:financial

# ÚROVEŇ 3: PODSKUPINA
- sub:faktura

# ÚROVEŇ 4: TYP
- type:faktura-dodavatelska

# METADATA
- meta:ai-classified
- meta:high-confidence
- meta:has-pdf
- meta:recurring
- meta:source-email
- meta:lang-en
- meta:unpaid

# DODATEČNÉ KONTEXTOVÉ TAGY
- period:2024-11
- amount-range:100-500
- currency:USD
```

**Celkem: 13 tagů na jeden dokument**

---

## 📊 ÚPLNÝ SOUHRN VŠECH TAGŮ

| Kategorie | Počet | Prefix | Barva |
|-----------|-------|--------|-------|
| **Dodavatelé** | ~30 | `supplier:` | 🔵 #3498DB |
| **Druhy** | 8 | `cat:` | 🟣 #9B59B6 |
| **Podskupiny** | ~20 | `sub:` | 🟠 #F39C12 |
| **Typy** | ~30 | `type:` | 🟢 #27AE60 |
| **Metadata** | ~20 | `meta:` | ⚪ #95A5A6 |
| **Období** | 60 | `period:` | 🔵 #2980B9 |
| **Částky** | 10 | `amount-range:` | 🟢 #16A085 |
| **Měny** | 5 | `currency:` | 🟡 #F1C40F |
| **━━━━━━━** | **━━━** | **━━━━━━━━** | **━━━━━━** |
| **CELKEM** | **~183 tagů** | | |

---

## 🎯 VÝHODY PRO RAG SYSTÉM

### 1. Přesné vyhledávání
```python
# Najdi všechny dodavatelské faktury od OpenAI z listopadu 2024
tags = [
    "supplier:OpenAI",
    "cat:financial",
    "sub:faktura",
    "type:faktura-dodavatelska",
    "period:2024-11"
]
```

### 2. Hierarchické dotazy
```python
# Najdi všechny finanční dokumenty
tags = ["cat:financial"]  # Vrátí faktury, výpisy, potvrzení...

# Najdi všechny faktury
tags = ["sub:faktura"]  # Vrátí všechny typy faktur

# Najdi konkrétní typ
tags = ["type:faktura-dodavatelska"]  # Jen dodavatelské faktury
```

### 3. Kombinované filtry
```python
# Najdi nezaplacené faktury s vysokou jistotou od AI dodavatelů
tags = [
    "cat:financial",
    "sub:faktura",
    "meta:unpaid",
    "meta:high-confidence",
    "supplier:OpenAI OR supplier:Anthropic OR supplier:Google"
]
```

### 4. Agregace pro RAG context
```python
# RAG může agregovat kontext:
# "Uživatel se ptá na náklady za AI služby v roce 2024"

query_tags = {
    "suppliers": ["supplier:OpenAI", "supplier:Anthropic", "supplier:Google"],
    "category": "cat:financial",
    "subcategory": "sub:faktura",
    "periods": ["period:2024-01", "period:2024-02", ..., "period:2024-12"],
    "metadata": ["meta:paid", "meta:unpaid"]
}

# RAG vrátí všechny relevantní faktury
# a může spočítat celkové náklady
```

---

## 🔄 AUTOMATICKÉ GENEROVÁNÍ TAGŮ

### Logika pro AI klasifikátor:

```python
def generate_hierarchical_tags(email, classification):
    tags = []

    # 1. DODAVATEL (povinný)
    supplier = identify_supplier(email['from'], email['body'])
    if supplier:
        tags.append(f"supplier:{supplier}")

    # 2. DRUH (povinný)
    category = classify_category(email, classification)
    tags.append(f"cat:{category}")

    # 3. PODSKUPINA (pokud aplikovatelné)
    subcategory = classify_subcategory(email, classification, category)
    if subcategory:
        tags.append(f"sub:{subcategory}")

    # 4. TYP (pokud aplikovatelné)
    specific_type = classify_specific_type(email, subcategory)
    if specific_type:
        tags.append(f"type:{specific_type}")

    # 5. METADATA (vždy)
    metadata = extract_metadata(email, classification)
    tags.extend([f"meta:{m}" for m in metadata])

    # 6. DODATEČNÉ KONTEXTOVÉ TAGY
    tags.extend(extract_contextual_tags(email))

    return tags
```

---

## ✅ VÝSTUPNÍ FORMÁT PRO PAPERLESS-NGX

```json
{
  "title": "Invoice OpenAI November 2024",
  "document_type": 1,  // ID pro "Invoice"
  "correspondent": 5,  // ID pro "OpenAI"
  "created": "2024-11-30",
  "tags": [
    // IDs tagů v Paperless (po vytvoření)
    12,  // supplier:OpenAI
    34,  // cat:financial
    56,  // sub:faktura
    78,  // type:faktura-dodavatelska
    90,  // meta:ai-classified
    91,  // meta:high-confidence
    92,  // meta:has-pdf
    93,  // meta:recurring
    94,  // period:2024-11
    95,  // amount-range:100-500
    96,  // currency:USD
    97,  // meta:unpaid
    98   // meta:lang-en
  ],
  "custom_fields": [
    {"field": 1, "value": "150.00"},      // Částka
    {"field": 2, "value": "USD"},         // Měna
    {"field": 3, "value": "2024-11-30"},  // Datum splatnosti
    {"field": 4, "value": "INV-2024-001234"}  // Číslo faktury
  ]
}
```

---

## 🚀 IMPLEMENTACE

Po schválení vytvořím:

1. **`tag_generator.py`** - Generuje všechny tagy hierarchicky
2. **`tag_validator.py`** - Validuje správnost hierarchie
3. **`classify_for_paperless_v2.py`** - Hlavní klasifikační skript
4. **`export_to_rag.py`** - Export do RAG-ready formátu

---

**Toto je perfektní struktura pro RAG! Čekám na schválení! 🎯**
