# 🏷️ Příklady tagování emailů pro Paperless-NGX

## Příklad 1: Newsletter od GitHub

**Email:**
```
From: notifications@github.com
Subject: [GitHub] Weekly Digest for @majpuzik
Date: 2024-12-15
Body: Here's your weekly digest of repository activity...
```

**Vygenerované tagy:**
```
✅ email:notification      (hlavní typ)
✅ service:GitHub          (identifikovaná služba)
✅ ai:classified           (klasifikováno AI)
✅ ai:high-confidence      (confidence: 0.92)
✅ recurring               (opakující se týdenní email)
```

**Document Type:** `Email`

**Correspondent:** `GitHub`

---

## Příklad 2: Faktura od Anthropic Claude

**Email:**
```
From: billing@anthropic.com
Subject: Invoice for November 2024 - $150.00
Date: 2024-11-30
Body: Your invoice for Claude API usage is ready...
Attachments: invoice_nov_2024.pdf
```

**Vygenerované tagy:**
```
✅ email:transactional     (faktura)
✅ service:Anthropic Claude (identifikovaná služba)
✅ ai:classified           (klasifikováno AI)
✅ ai:high-confidence      (confidence: 0.95)
```

**Document Type:** `Invoice`

**Correspondent:** `Anthropic`

---

## Příklad 3: Reklamní email od Dropbox

**Email:**
```
From: marketing@dropbox.com
Subject: 🎉 Upgrade to Dropbox Plus - 50% OFF!
Date: 2024-12-10
Body: Don't miss this limited offer...
[Unsubscribe link at bottom]
```

**Vygenerované tagy:**
```
✅ email:marketing         (reklamní email)
✅ service:Dropbox         (identifikovaná služba)
✅ ai:classified           (klasifikováno AI)
✅ ai:high-confidence      (confidence: 0.88)
✅ has:unsubscribe         (má odhlašovací link)
```

**Document Type:** `Email`

**Correspondent:** `Dropbox`

---

## Příklad 4: Předplatné OpenAI

**Email:**
```
From: noreply@openai.com
Subject: Your ChatGPT Plus subscription has been renewed
Date: 2024-12-01
Body: Your monthly subscription to ChatGPT Plus for $20.00 has been renewed...
```

**Vygenerované tagy:**
```
✅ email:subscription      (předplatné)
✅ email:transactional     (platební transakce)
✅ service:OpenAI GPT      (identifikovaná služba)
✅ ai:classified           (klasifikováno AI)
✅ ai:high-confidence      (confidence: 0.94)
✅ recurring               (měsíční opakování)
```

**Document Type:** `Payment Confirmation`

**Correspondent:** `OpenAI`

---

## Příklad 5: Neznámý odesílatel (nízká confidence)

**Email:**
```
From: info@random-service.com
Subject: Important Update
Date: 2024-12-05
Body: We wanted to let you know...
```

**Vygenerované tagy:**
```
✅ email:notification      (best guess)
⚠️  ai:classified          (klasifikováno AI)
⚠️  ai:low-confidence      (confidence: 0.42)
```

**Document Type:** `Email`

**Correspondent:** `random-service.com`

---

## Příklad 6: Spam/Nevyžádaný email

**Email:**
```
From: winner@lottery-scam.com
Subject: YOU WON $1,000,000!!!
Date: 2024-12-12
Body: CONGRATULATIONS! Click here to claim...
```

**Vygenerované tagy:**
```
✅ email:spam              (spam)
✅ ai:classified           (klasifikováno AI)
✅ ai:high-confidence      (confidence: 0.97)
```

**Document Type:** `Email`

**Correspondent:** `lottery-scam.com`

---

## 🎨 Barevné kódování v Paperless-NGX

Po importu do Paperless-NGX uvidíš:

### Classification Types:
- 🔴 `email:subscription` - červená
- 🟠 `email:marketing` - oranžová
- 🔵 `email:notification` - tyrkysová
- 🟢 `email:transactional` - zelená
- 🟣 `email:personal` - fialová
- ⚪ `email:spam` - šedá

### Service Tags:
- 🔵 všechny service tagy - modrá

### Meta Tags:
- 🟢 `ai:classified`, `ai:high-confidence` - zelená
- 🔴 `ai:low-confidence` - červená
- 🟠 `has:unsubscribe` - oranžová
- 🟣 `recurring` - fialová

---

## 📊 Statistiky tagování (očekávané z 5 let)

Na základě testovacích dat (~4500 emailů):

| Tag | Očekávaný počet | % |
|-----|----------------|---|
| email:notification | ~1,800 | 40% |
| email:marketing | ~1,350 | 30% |
| email:transactional | ~675 | 15% |
| email:subscription | ~450 | 10% |
| email:personal | ~180 | 4% |
| email:spam | ~45 | 1% |
| | | |
| service:GitHub | ~450 | 10% |
| service:Google* | ~400 | 9% |
| service:Dropbox | ~300 | 7% |
| service:OpenAI GPT | ~250 | 6% |
| (ostatní služby) | ~2,000 | 44% |
| | | |
| ai:high-confidence | ~3,600 | 80% |
| ai:low-confidence | ~225 | 5% |
| has:unsubscribe | ~1,000 | 22% |
| recurring | ~800 | 18% |

---

## 🔍 Užitečné filtry v Paperless-NGX

### Najít všechny faktury s vysokou jistotou:
```
document_type:Invoice AND tags:ai:high-confidence
```

### GitHub notifikace:
```
tags:service:GitHub AND tags:email:notification
```

### Reklamní emaily s možností odhlášení:
```
tags:email:marketing AND tags:has:unsubscribe
```

### Předplatné od všech AI služeb:
```
tags:email:subscription AND
(tags:service:OpenAI GPT OR tags:service:Anthropic Claude OR tags:service:Google AI)
```

### Nízká jistota - potřebuje review:
```
tags:ai:low-confidence
```

### Opakující se platby:
```
tags:recurring AND tags:email:transactional
```

---

## ✅ Benefit strukturovaného tagování

1. **Rychlé vyhledávání** - najdi všechny faktury od konkrétní služby
2. **Automatizace** - nastavit pravidla v Paperless (např. auto-archivace marketingu)
3. **Reporting** - kolik platíš za AI služby měsíčně
4. **Audit** - které služby posílají nejvíc emailů
5. **Cleanup** - smazat všechny reklamní emaily najednou
6. **Quality control** - rychle najít emails s nízkou confidence pro ruční review

---

**Připraven vytvořit těchto 41 tagů a klasifikovat 5 let emailů! 🚀**
