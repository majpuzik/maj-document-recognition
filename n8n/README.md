# n8n Integration for MAJ-Document-Recognition

## Overview

n8n workflow pro automatickou klasifikaci emailů a import do Paperless-NGX.

## Workflow

```
IMAP (Get Emails) → API /classify → Route by Type → Paperless Upload → Set Custom Fields
```

## Setup

### 1. Import Workflow

1. Open n8n (http://192.168.10.35:5678)
2. Go to Workflows → Import from File
3. Select `maj_document_recognition_workflow.json`

### 2. Configure Credentials

**IMAP:**
- Host: your mail server
- Port: 993 (SSL)
- User: your email
- Password: app password

**Paperless Token:**
- Replace `YOUR_PAPERLESS_TOKEN` with actual token from Paperless settings

### 3. Configure API URL

Default API: `http://192.168.10.35:8765/api/classify`

If running on different machine, update the HTTP Request node.

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/classify` | POST | Classify document type |
| `/api/documents/post_document/` | POST | Upload to Paperless |
| `/api/documents/{id}/` | PATCH | Set custom fields |

## Classification Response

```json
{
  "doc_type": "invoice",
  "confidence": 0.85,
  "extracted_fields": {
    "doc_typ": "invoice",
    "protistrana_nazev": "ABC s.r.o.",
    "protistrana_ico": "12345678",
    "castka_celkem": 15000,
    "mena": "CZK",
    "ai_summary": "Faktura za služby"
  },
  "model": "qwen2.5:32b"
}
```

## Document Types

| Type | Czech Name | Tag |
|------|------------|-----|
| invoice | Faktura | finance |
| order | Objednávka | obchod |
| contract | Smlouva | smlouvy |
| marketing | Marketing | marketing |
| correspondence | Korespondence | komunikace |
| system_notification | Systémová notifikace | system |
| it_notes | IT poznámky | it |
| project_notes | Projektové poznámky | projekty |

## Custom Fields (31)

All 31 custom fields are automatically created in Paperless:

1. doc_typ
2. protistrana_nazev
3. protistrana_ico
4. protistrana_typ
5. castka_celkem
6. datum_dokumentu
7. cislo_dokumentu
8. mena
9. stav_platby
10. datum_splatnosti
11. kategorie
12. email_from
13. email_to
14. email_subject
15. od_osoba
16. od_osoba_role
17. od_firma
18. pro_osoba
19. pro_osoba_role
20. pro_firma
21. predmet
22. ai_summary
23. ai_keywords
24. ai_popis
25. typ_sluzby
26. nazev_sluzby
27. predmet_typ
28. predmet_nazev
29. polozky_text
30. polozky_json
31. perioda

## Trigger Options

### Manual
Run workflow manually from n8n UI.

### Schedule
Add Schedule Trigger node:
- Every 5 minutes
- Hourly
- Daily at specific time

### Webhook
Add Webhook Trigger to receive external triggers:
```
POST http://192.168.10.35:5678/webhook/maj-classify
```

## Full Pipeline Integration

```
┌────────────────────────────────────────────────────────┐
│                    n8n WORKFLOW                         │
├────────────────────────────────────────────────────────┤
│                                                         │
│  [IMAP Trigger]                                        │
│       │                                                 │
│       ▼                                                 │
│  [HTTP Request: POST /api/classify]                    │
│       │                                                 │
│       ▼                                                 │
│  [Switch by doc_type]                                  │
│       │                                                 │
│       ├─── invoice ───┐                                │
│       ├─── contract ──┤                                │
│       ├─── marketing ─┼──▶ [Set Tags/Type]            │
│       ├─── other ─────┤                                │
│       │               │                                 │
│       ▼               ▼                                 │
│  [HTTP Request: POST /api/documents/post_document/]    │
│       │                                                 │
│       ▼                                                 │
│  [HTTP Request: PATCH /api/documents/{id}/]            │
│  (Set 31 custom fields)                                │
│                                                         │
└────────────────────────────────────────────────────────┘
```

## Troubleshooting

### API Not Responding
```bash
# Check API server
curl http://192.168.10.35:8765/api/health

# Start API server
python /Volumes/ACASIS/apps/maj-document-recognition/api/server.py --port 8765
```

### Paperless Connection Failed
```bash
# Check Paperless
curl http://192.168.10.85:8777/api/documents/?page_size=1 \
  -H "Authorization: Token YOUR_TOKEN"
```

### Custom Fields Not Created
```bash
# Run Phase 5 with --test to create fields
python email_extractor/phase5_import.py --test
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.2.0 | 2025-12-17 | Force classification, no "other" |
| 1.1.0 | 2025-12-17 | System notification detection |
| 1.0.0 | 2025-12-16 | Initial release |
