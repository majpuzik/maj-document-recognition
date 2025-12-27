# Correspondent Deduplication Summary - 2025-12-17

## Problem

Paperless-NGX had 1,715 correspondents with many duplicates:
- "Adobe" vs "adobe systems" vs "ADOBE Inc."
- "Google" vs "Google Alerts"
- "Alza.cz" vs "alza.cz"
- "AUKRO s.r.o." vs "Aukro" vs "aukro.cz"
- And many more...

## Solution

### 1. Created Correspondent Normalizer (`correspondent_normalizer.py`)

Normalizes correspondent names by:
- Converting to lowercase
- Removing legal suffixes (Inc., s.r.o., GmbH, etc.)
- Removing service suffixes (Newsletter, Alerts, etc.)
- Removing domain extensions (.cz, .com, etc.)
- Cleaning emojis and special characters
- Extracting names from email formats

### 2. Created Merge Script (`merge_correspondents.py`)

Automatically merges duplicate correspondents:
- Finds duplicates based on normalized names
- Keeps correspondent with most documents
- Reassigns all documents to primary correspondent
- Deletes now-empty duplicate correspondents

### 3. Updated Upload Script (`parallel_upload_stuck.py`)

Fixed:
- Correct Paperless URL: `http://192.168.10.200:8020`
- Correct API token: `155c91425631202132bb769241ad7d3196428df0`
- Added correspondent normalization for new uploads
- Extracts sender name from email headers

## Results

### Before
- **1,715** correspondents
- **62** duplicate groups identified
- **833** documents affected by duplicates

### After
- **1,645** correspondents (70 merged)
- **0** duplicate groups
- **243** documents reassigned

### Key Merges

| Normalized | Merged | Docs | Primary |
|------------|--------|------|---------|
| aukro | 5 | 94 | Aukro |
| google | 2 | 74 | Google |
| hobynaradi | 2 | 67 | HobyNaradi.cz |
| tripadvisor | 2 | 48 | Tripadvisor |
| alza | 2 | 46 | Alza.cz |
| ulanzi | 2 | 36 | Ulanzi |
| allegro | 3 | 35 | Allegro |
| acdsee | 2 | 26 | ACDSee |
| tesla lighting | 5 | 24 | TESLA LIGHTING |
| booking | 2 | 22 | Booking.com |

## Files Created

```
/Volumes/ACASIS/apps/maj-document-recognition/email_extractor/
├── correspondent_normalizer.py    # Normalization functions
├── merge_correspondents.py        # Merge duplicate correspondents
├── parallel_upload_stuck.py       # Updated upload script
├── CORRESPONDENT_NORMALIZATION.md # Documentation
└── MERGE_SUMMARY_2025-12-17.md   # This file
```

## Usage

### Run another merge (if needed)

```bash
cd /Volumes/ACASIS/apps/maj-document-recognition/email_extractor

# Dry run
python3 merge_correspondents.py --dry-run --min-docs 3

# Execute
python3 merge_correspondents.py --execute --min-docs 3 --output results.json
```

### Test normalizer

```bash
python3 correspondent_normalizer.py
```

## Paperless Configuration

- **URL**: `http://192.168.10.200:8020`
- **Token**: `155c91425631202132bb769241ad7d3196428df0`
- **Admin User**: `admin`
- **Documents**: 90,848
- **Correspondents**: 1,645
