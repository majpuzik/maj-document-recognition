# 📋 Plán integrace Universal Business Classifier → Paperless-NGX

## 🎯 Cíl
Klasifikovat **5 let emailů** (2020-2025) pomocí **Universal Business Classifier** a exportovat do **Paperless-NGX** kompatibilního formátu.

---

## 📊 Fáze 1: Analýza dat

### 1.1 Databázová struktura
```sql
-- Zkontrolovat strukturu email_evidence
PRAGMA table_info(email_evidence);

-- Zjistit rozsah dat
SELECT
    MIN(email_date) as nejstarsi,
    MAX(email_date) as nejnovejsi,
    COUNT(*) as celkem
FROM email_evidence;

-- Počet emailů za rok
SELECT
    strftime('%Y', email_date) as rok,
    COUNT(*) as pocet
FROM email_evidence
WHERE email_date >= '2020-01-01'
GROUP BY rok
ORDER BY rok;
```

**Očekávaný output:**
- Celkem: ~3000-5000 emailů
- Rozsah: 2020-2025
- Distribution: ~600-1000 emailů/rok

### 1.2 Datové pole potřebné z databáze
```python
required_fields = {
    'id': 'INTEGER',                      # Unikátní ID
    'email_subject': 'TEXT',              # Předmět
    'email_from': 'TEXT',                 # Odesílatel
    'email_to': 'TEXT',                   # Příjemce
    'email_date': 'TIMESTAMP',            # Datum
    'email_body_compact': 'TEXT',         # Tělo (kratší)
    'email_body_full': 'TEXT',            # Tělo (úplné)
    'attachments_count': 'INTEGER',       # Počet příloh
    'has_pdf': 'BOOLEAN',                 # Má PDF?
    'service_id': 'INTEGER'               # FK na services
}
```

---

## 📦 Fáze 2: Paperless-NGX API Specifikace

### 2.1 Povinná pole pro Paperless-NGX API
```json
{
  "title": "Email Subject - 2024-12-01",
  "document_type": 1,           // ID typu dokumentu
  "correspondent": 2,           // ID odesílatele
  "tags": [3, 4, 5],           // IDs tagů
  "created": "2024-12-01",     // Datum vytvoření
  "content": "Email body text...",
  "custom_fields": [
    {
      "field": 1,              // Custom field ID
      "value": "subscription"
    }
  ]
}
```

### 2.2 Tagy systém (podle PAPERLESS_TAGS_README.md)

#### Classification Type Tags (6):
```python
CLASSIFICATION_TAGS = {
    'email:subscription': {'color': '#FF6B6B', 'description': 'Předplatné'},
    'email:marketing': {'color': '#FFA500', 'description': 'Marketing'},
    'email:notification': {'color': '#4ECDC4', 'description': 'Notifikace'},
    'email:transactional': {'color': '#95E1D3', 'description': 'Transakce'},
    'email:personal': {'color': '#9B59B6', 'description': 'Osobní'},
    'email:spam': {'color': '#95A5A6', 'description': 'Spam'}
}
```

#### Service Tags (dynamické z databáze):
```python
# Automaticky z tabulky 'services'
service_tags = {
    f'service:{service_name}': {
        'color': '#3498DB',
        'description': f'Emails from {service_name}'
    }
}
```

#### Special Tags (5):
```python
SPECIAL_TAGS = {
    'ai:classified': {'color': '#27AE60'},
    'ai:high-confidence': {'color': '#2ECC71'},
    'ai:low-confidence': {'color': '#E74C3C'},
    'has:unsubscribe': {'color': '#F39C12'},
    'recurring': {'color': '#9B59B6'}
}
```

### 2.3 Document Types mapping
```python
DOCUMENT_TYPE_MAPPING = {
    # Universal Business Classifier → Paperless
    'invoice': 'Invoice',
    'receipt': 'Receipt',
    'statement': 'Bank Statement',
    'contract': 'Contract',
    'correspondence': 'Business Correspondence',
    'notification': 'Notification',
    'marketing': 'Marketing Material',
    'legal': 'Legal Document',
    'other': 'Email'  # default
}
```

---

## 🔧 Fáze 3: Implementace

### 3.1 Architektura skriptu

```
classify_for_paperless.py
├── DatabaseExtractor
│   ├── extract_emails(since_date='2020-01-01')
│   ├── batch_iterator(batch_size=500)
│   └── save_progress(last_id)
│
├── UniversalClassifier
│   ├── classify_batch(emails)
│   ├── extract_features(email)
│   └── calculate_confidence(result)
│
├── PaperlessFormatter
│   ├── format_document(email, classification)
│   ├── create_tags(classification)
│   ├── map_document_type(type)
│   └── generate_custom_fields(email)
│
├── PaperlessExporter
│   ├── test_connection()
│   ├── create_missing_tags()
│   ├── create_missing_correspondents()
│   └── export_batch(documents)
│
└── ProgressTracker
    ├── save_state(current_id, stats)
    ├── load_state()
    └── generate_report()
```

### 3.2 Klíčové komponenty

#### 3.2.1 DatabaseExtractor
```python
def extract_emails(since_date='2020-01-01', batch_size=500):
    """
    Vytáhne emaily z databáze po dávkách

    Returns:
        Generator[List[Dict]]: Dávky emailů
    """
    query = """
    SELECT
        id,
        email_subject,
        email_from,
        email_to,
        email_date,
        email_body_compact,
        email_body_full,
        attachments_count,
        has_pdf,
        service_id
    FROM email_evidence
    WHERE email_date >= ?
    ORDER BY email_date ASC
    """

    # Yield po dávkách pro memory efficiency
    offset = 0
    while True:
        batch = fetch_batch(query, since_date, batch_size, offset)
        if not batch:
            break
        yield batch
        offset += batch_size
```

#### 3.2.2 PaperlessFormatter
```python
def format_for_paperless(email: Dict, classification: Dict) -> Dict:
    """
    Formátuje email do Paperless-NGX API formátu

    Args:
        email: Raw email data z databáze
        classification: Output z Universal Business Classifier

    Returns:
        Dict: Paperless-NGX kompatibilní dokument
    """
    return {
        # Povinná pole
        'title': f"{email['email_subject'][:100]} - {email['email_date'][:10]}",
        'created': email['email_date'][:10],  # YYYY-MM-DD
        'content': email['email_body_compact'] or email['email_body_full'],

        # Metadata
        'document_type': get_document_type_id(
            DOCUMENT_TYPE_MAPPING.get(
                classification.get('document_type', 'other')
            )
        ),

        'correspondent': get_correspondent_id(
            extract_sender_name(email['email_from'])
        ),

        # Tagy
        'tags': generate_tag_ids(email, classification),

        # Custom fields
        'custom_fields': [
            {'field': FIELD_ID_CLASSIFICATION, 'value': classification.get('type')},
            {'field': FIELD_ID_CONFIDENCE, 'value': str(classification.get('confidence', 0))},
            {'field': FIELD_ID_SOURCE, 'value': 'email_evidence'},
            {'field': FIELD_ID_ORIGINAL_ID, 'value': str(email['id'])}
        ]
    }
```

#### 3.2.3 Tag Generation Logic
```python
def generate_tag_ids(email: Dict, classification: Dict) -> List[int]:
    """
    Generuje seznam tag IDs pro email

    Logic:
    1. Classification type tag (vždy 1)
    2. Service tag (pokud service_id exists)
    3. Confidence tag (based on score)
    4. Special tags (unsubscribe link, recurring, etc.)
    """
    tags = []

    # 1. Classification type
    doc_type = classification.get('document_type', 'other')
    classification_tag = CLASSIFICATION_TAG_MAP.get(doc_type, 'email:notification')
    tags.append(get_or_create_tag(classification_tag))

    # 2. Service tag
    if email.get('service_id'):
        service_name = get_service_name(email['service_id'])
        tags.append(get_or_create_tag(f'service:{service_name}'))

    # 3. Confidence tag
    confidence = classification.get('confidence', 0)
    if confidence > 0.8:
        tags.append(get_or_create_tag('ai:high-confidence'))
    elif confidence < 0.5:
        tags.append(get_or_create_tag('ai:low-confidence'))

    # 4. Special tags
    tags.append(get_or_create_tag('ai:classified'))

    if has_unsubscribe_link(email['email_body_compact']):
        tags.append(get_or_create_tag('has:unsubscribe'))

    return tags
```

---

## 🚀 Fáze 4: Spuštění

### 4.1 Test Run (100 emailů)
```bash
python3 classify_for_paperless.py \
    --since-date 2024-01-01 \
    --limit 100 \
    --output test_output.jsonl \
    --dry-run
```

**Očekávaný output:**
```
✅ Načteno 100 emailů
✅ Klasifikováno: 100/100
✅ Validace: 100/100 passed
📊 Typy dokumentů:
   - email:notification: 45
   - email:marketing: 30
   - email:transactional: 15
   - email:subscription: 10
💾 Output: test_output.jsonl (valid Paperless format)
```

### 4.2 Full Run (5 let)
```bash
python3 classify_for_paperless.py \
    --since-date 2020-01-01 \
    --batch-size 500 \
    --output paperless_export_5years.jsonl \
    --parallel 4 \
    --resume \
    2>&1 | tee paperless_export.log
```

**Features:**
- ✅ Batch processing (500 emailů najednou)
- ✅ Parallel classification (4 workers)
- ✅ Resume capability (pokračuje po pádu)
- ✅ Progress tracking (každých 100 emailů)
- ✅ Error handling (skip invalid, log errors)

---

## 📈 Fáze 5: Validace & Export

### 5.1 Validace výstupu
```python
def validate_paperless_json(data: Dict) -> bool:
    """
    Validuje JSON proti Paperless-NGX API schema
    """
    required_fields = ['title', 'created', 'content']

    for field in required_fields:
        if field not in data or not data[field]:
            return False

    # Validace date formátu
    if not re.match(r'\d{4}-\d{2}-\d{2}', data['created']):
        return False

    # Validace IDs
    if 'document_type' in data and not isinstance(data['document_type'], int):
        return False

    if 'tags' in data and not isinstance(data['tags'], list):
        return False

    return True
```

### 5.2 Summary Report
```
========================================
📊 KLASIFIKACE DOKONČENA
========================================
Celkem zpracováno: 4,532 emailů
Období: 2020-01-01 až 2025-11-30
Doba běhu: 45 minut

📈 STATISTIKY:
----------------------------------------
Classification Types:
  email:notification    1,834 (40.5%)
  email:marketing       1,360 (30.0%)
  email:transactional     680 (15.0%)
  email:subscription      453 (10.0%)
  email:personal          205 ( 4.5%)

Services (top 10):
  Google                  456
  LinkedIn                324
  GitHub                  234
  Dropbox                 189
  ...

Confidence:
  High (>80%):          3,625 (80.0%)
  Medium (50-80%):        680 (15.0%)
  Low (<50%):             227 ( 5.0%)

⚠️  CHYBY:
  Invalid emails:          12
  Classification fails:     3
  Skipped (duplicates):     8

✅ VÝSTUP:
  Format: Paperless-NGX JSONL
  File: paperless_export_5years.jsonl
  Size: 125 MB
  Valid entries: 4,509/4,532 (99.5%)

🏷️  TAGY VYTVOŘENY:
  Classification tags: 6
  Service tags: 47
  Special tags: 5
  Total: 58

========================================
```

---

## 📝 Fáze 6: Import do Paperless-NGX

### 6.1 Vytvoření tagů
```bash
python3 create_paperless_tags.py
```

### 6.2 Import dokumentů
```bash
# Pomocí Paperless API
python3 import_to_paperless.py \
    --input paperless_export_5years.jsonl \
    --batch-size 50 \
    --workers 4
```

**nebo**

```bash
# Pomocí Paperless consume directory
cp paperless_export_5years.jsonl /path/to/paperless/consume/
```

---

## ✅ Úspěšná kritéria

1. ✅ Všechny emaily od 2020-01-01 klasifikovány
2. ✅ Výstup validní proti Paperless-NGX API schema
3. ✅ Všechny povinné tagy vytvořeny
4. ✅ < 5% chybovost
5. ✅ Resume capability funguje
6. ✅ Import do Paperless úspěšný

---

## 🎯 Další kroky po schválení

Po schválení tohoto plánu:

1. Implementuji `classify_for_paperless.py`
2. Test run na 100 emailech
3. Validace výstupu
4. Full run na 5 letech
5. Import do Paperless-NGX
6. Výsledný report

**Čekám na tvé schválení! 🚀**
