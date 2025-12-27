# Correspondent Normalization for Paperless-NGX

## Overview

This module provides correspondent name normalization to prevent duplicates in Paperless-NGX.

## Problem

Without normalization, the same sender can create multiple correspondent entries:
- "Adobe" vs "adobe systems" vs "ADOBE Inc."
- "Google" vs "Google Alerts"
- "Alza.cz" vs "alza.cz" vs "ALZA.CZ a.s."

## Solution

### Normalization Rules

1. **Case normalization** - Convert to lowercase for comparison
2. **Legal suffix removal** - Remove Inc., s.r.o., GmbH, a.s., Ltd., etc.
3. **Service suffix removal** - Remove Newsletter, Alerts, News, etc.
4. **Domain suffix removal** - Remove .cz, .com, .de, etc.
5. **Unicode normalization** - Remove emojis and special characters
6. **Email format handling** - Extract name from "Name <email>" format

### Files

- `correspondent_normalizer.py` - Core normalization functions
- `merge_correspondents.py` - Script to merge existing duplicates
- `parallel_upload_stuck.py` - Upload script with normalization

## Usage

### Normalize a name (for comparison)

```python
from correspondent_normalizer import normalize_correspondent

# All these return "adobe"
normalize_correspondent("Adobe")
normalize_correspondent("adobe systems")
normalize_correspondent("ADOBE Inc.")
```

### Get best display name

```python
from correspondent_normalizer import get_best_correspondent_name

# Uses known mappings or cleans up the name
get_best_correspondent_name("adobe systems")  # Returns "Adobe"
get_best_correspondent_name("ALZA.CZ a.s.")   # Returns "Alza.cz"
```

### Merge existing duplicates

```bash
# Dry run - see what would be merged
python merge_correspondents.py --dry-run --min-docs 5

# Execute merge
python merge_correspondents.py --execute --min-docs 5 --output results.json
```

## Configuration

### Paperless DGX

- **URL**: `http://192.168.10.200:8020`
- **Token**: `155c91425631202132bb769241ad7d3196428df0`
- **User**: `admin`

### Known Mappings

The `KNOWN_MAPPINGS` dict in `correspondent_normalizer.py` contains manual overrides:

```python
KNOWN_MAPPINGS = {
    'adobe': 'Adobe',
    'google': 'Google',
    'alza': 'Alza.cz',
    'booking': 'Booking.com',
    # ...
}
```

## Results (2025-12-17)

Initial merge:
- **1715 correspondents** analyzed
- **62 duplicate groups** found
- **70 correspondents** merged
- **243 documents** reassigned

Remaining after merge: **1645 unique correspondents**

## Adding New Mappings

Edit `correspondent_normalizer.py`:

```python
KNOWN_MAPPINGS = {
    # Add new mappings here
    'new_normalized': 'Display Name',
}
```

## Testing

```bash
python correspondent_normalizer.py
```

This runs test cases showing normalization results.

---

## CDB Logging

All maintenance actions are logged to CDB:
- **Location:** `/home/puzik/almquist-central-log/almquist.db`
- **Table:** `maintenance_log`

```sql
SELECT * FROM maintenance_log
WHERE category = 'paperless-correspondents'
ORDER BY timestamp DESC;
```

## Memory Graph

Information is also stored in Claude's memory graph:
- **Paperless-DGX** - service configuration
- **Correspondent-Normalizer** - normalization tool
- **Correspondent-Merge-Script** - merge tool
- **Paperless-Upload-Script** - upload tool

---

## Maintenance Schedule

Run merge script periodically to catch new duplicates:

```bash
# Weekly check (dry-run)
python3 merge_correspondents.py --dry-run --min-docs 2

# If duplicates found, execute
python3 merge_correspondents.py --execute --min-docs 2 --output /tmp/merge_$(date +%Y%m%d).json
```
