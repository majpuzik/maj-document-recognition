# 📋 Implementace rozpoznávání Objednávky a Dodacího listu

**Datum:** 2025-11-06
**Verze:** v2.1
**Autor:** MAJ + Claude Code

---

## 🎯 Co bylo přidáno

### ✅ Nové typy dokumentů:

1. **🛒 objednavka** (Purchase Order / Bestellung)
2. **📦 dodaci_list** (Delivery Note / Lieferschein)

---

## 📊 Klíčové vlastnosti dokumentů

### 🛒 OBJEDNÁVKA (Purchase Order)

**Směr:** Odchozí (my → dodavatel)
**Účel:** Objednání zboží/služeb

**Povinné prvky:**
- ✅ Číslo objednávky (PO Number, Bestellnummer)
- ✅ Datum objednávky
- ✅ Dodavatel
- ✅ Seznam položek + množství
- ✅ **CENY** (jednotková i celková)
- ✅ Dodací termín

**Klíčová slova (multilingvální):**
- **CZ:** objednávka, číslo objednávky, obj. číslo, dodací termín
- **DE:** Bestellung, Bestellnummer, Liefertermin
- **EN:** purchase order, PO number, delivery date

**Rozlišení od faktury:**
- ❌ Obvykle BEZ daňových údajů (DIČ může být, ale není povinné)
- ❌ BEZ bankovních údajů
- ❌ BEZ data splatnosti
- ✅ MÁ termín dodání (ne splatnosti!)

---

### 📦 DODACÍ LIST (Delivery Note)

**Směr:** Příchozí (dodavatel → my)
**Účel:** Potvrzení dodávky zboží

**Povinné prvky:**
- ✅ Číslo dodacího listu (DL Number, Lieferscheinnummer)
- ✅ Datum dodání/expedice
- ✅ Odkaz na objednávku
- ✅ Seznam dodaného zboží
- ✅ **HMOTNOST balíku** (kg)
- ✅ **POČET balíků**
- ❌ **OBVYKLE BEZ CEN!**

**Klíčová slova (multilingvální):**
- **CZ:** dodací list, číslo DL, expedováno, hmotnost, počet balíků
- **DE:** Lieferschein, Lieferscheinnummer, Gewicht, Pakete
- **EN:** delivery note, packing slip, shipped, weight, packages

**Rozlišení od faktury:**
- ❌ BEZ cen (hlavní rozdíl!)
- ❌ BEZ DPH
- ❌ BEZ bankovních údajů
- ✅ MÁ informace o zásilce (hmotnost, balíky)

---

## 🔧 Implementované změny

### 1. Classifier Prompt (`src/ai/classifier_improved.py:37-95`)

**Přidáno do kategorií:**
```python
- objednavka: Objednávka, purchase order, Bestellung (číslo objednávky, položky, ceny, dodací termín)
- dodaci_list: Dodací list, delivery note, Lieferschein (bez cen!, číslo DL, hmotnost, počet balíků)
```

**Přidány příklady (few-shot learning):**

**Příklad 6 - Objednávka:**
```
Text: "Objednávka č. PO-2024-156, Dodavatel: ACME s.r.o.,
       Datum objednání: 15.3.2024, Položka: Šroub M6,
       Množství: 1000 ks, Cena za kus: 2 Kč, Celkem: 2000 Kč,
       Dodací termín: 30.3.2024"
→ TYP: objednavka
→ CONFIDENCE: 0.93
```

**Příklad 7 - Dodací list:**
```
Text: "Dodací list č. DL-8765, Datum expedice: 28.3.2024,
       Odkaz na objednávku: PO-2024-156, Počet balíků: 2,
       Hmotnost celkem: 15 kg, Příjemce: Naše firma s.r.o.,
       Dodáno: 1000 ks šroubů M6"
→ TYP: dodaci_list
→ CONFIDENCE: 0.91
```

**Přidáno rozlišení:**
```
DŮLEŽITÉ ROZLIŠENÍ:
- OBJEDNÁVKA obsahuje CENY a termín dodání (my objednáváme)
- DODACÍ LIST často BEZ CEN, má hmotnost/počet balíků (dodavatel dodává)
- FAKTURA obsahuje ceny + DPH + bankovní údaje (dodavatel účtuje)
```

---

### 2. Whitelist kontrola (`src/ai/classifier_improved.py:338-379`)

**Implementovaná logika:**

```python
# 1. Kontrola whitelist senderu
if is_whitelist:
    whitelist_boost = 0.15  # +15% confidence pro důvěryhodné senderы

    # 2. Přísná kontrola pro objednávky
    if best_type == "objednavka":
        has_order_number = check_keywords([
            "objednávka", "číslo obj", "purchase order", "bestellung"
        ])
        if not has_order_number:
            whitelist_boost = 0.05  # Snížený boost!
            logger.warning("⚠️ Whitelist sender but missing order number!")

    # 3. Přísná kontrola pro dodací listy
    elif best_type == "dodaci_list":
        has_delivery_number = check_keywords([
            "dodací list", "delivery note", "lieferschein"
        ])
        has_shipping_info = check_keywords([
            "hmotnost", "kg", "balík", "gewicht", "package"
        ])
        if not (has_delivery_number or has_shipping_info):
            whitelist_boost = 0.05  # Snížený boost!
            logger.warning("⚠️ Whitelist sender but missing delivery info!")
```

**Účel:**
- ✅ Důvěryhodní dodavatelé dostávají +15% boost
- ⚠️ Ale POUZE pokud dokument má správnou strukturu!
- 🛡️ Ochrana proti podvodu (fake objednávky/dodací listy)

---

### 3. Keywords v config (`config/config.yaml:79-105`)

**Objednávka keywords:**
```yaml
objednavka:
  - "objednávka"
  - "objednávk"
  - "číslo objednávky"
  - "obj. číslo"
  - "obj.č"
  - "purchase order"
  - "bestellung"
  - "bestellnummer"
  - "po number"
  - "dodací termín"
  - "delivery date"
  - "liefertermin"
```

**Dodací list keywords:**
```yaml
dodaci_list:
  - "dodací list"
  - "dodací l"
  - "číslo dl"
  - "dl č"
  - "delivery note"
  - "lieferschein"
  - "packing slip"
  - "expedováno"
  - "hmotnost"
  - "počet balíků"
  - "gewicht"
  - "pakete"
  - "shipped"
```

---

### 4. Classification types (`config/config.yaml:51-63`)

**Aktualizovaný seznam typů:**
```yaml
types:
  - "faktura"
  - "stvrzenka"
  - "objednavka"        # ← NOVÉ!
  - "dodaci_list"       # ← NOVÉ!
  - "bankovni_vypis"
  - "vyzva_k_platbe"
  - "oznameni_o_zaplaceni"
  - "oznameni_o_nezaplaceni"
  - "soudni_dokument"
  - "reklama"
  - "obchodni_korespondence"
  - "jine"
```

---

## 📋 Rozhodovací tabulka

| Vlastnost              | Objednávka | Dodací list | Faktura |
|------------------------|------------|-------------|---------|
| **Obsahuje ceny**      | ✅ Ano     | ❌ Ne       | ✅ Ano  |
| **Obsahuje DPH**       | ⚠️ Někdy   | ❌ Ne       | ✅ Ano  |
| **Číslo objednávky**   | ✅ Ano     | ✅ Ref      | ✅ Ref  |
| **Číslo faktury**      | ❌ Ne      | ❌ Ne       | ✅ Ano  |
| **Hmotnost balíku**    | ❌ Ne      | ✅ Ano      | ❌ Ne   |
| **Počet balíků**       | ❌ Ne      | ✅ Ano      | ❌ Ne   |
| **Dodací termín**      | ✅ Ano     | ❌ Ne       | ❌ Ne   |
| **Datum splatnosti**   | ❌ Ne      | ❌ Ne       | ✅ Ano  |
| **Bankovní údaje**     | ❌ Ne      | ❌ Ne       | ✅ Ano  |

---

## 🔍 Detekční logika

### Algoritmus rozpoznání:

```
1. Keyword matching (quick scan):
   - Hledá klíčová slova z config.yaml
   - Confidence: 0.5-0.85 based on počet matches

2. AI classification (Ollama):
   - Few-shot learning s příklady
   - Rozlišení CENY vs BEZ CEN
   - Confidence: 0.0-1.0

3. Whitelist boost (pokud je sender známý):
   - +15% confidence pro důvěryhodné
   - +5% pokud chybí povinné prvky (warning!)

4. Ensemble voting:
   - Weighted average z všech metod
   - Agreement bonus (více metod = vyšší confidence)
```

---

## 🎯 Příklady použití

### Správně rozpoznaná objednávka:
```
Sender: dodavatel@acme.cz (whitelist)
Text: "Objednávka č. 2024-001, ACME s.r.o.,
       Položka: Šrouby M6, 1000 ks × 2 Kč = 2000 Kč,
       Dodací termín: 30.3.2024"

Výsledek:
  Type: objednavka
  Confidence: 0.93 + 0.15 (whitelist) = 0.98 (98%)
  ✅ Whitelist sender + correct format
```

### Správně rozpoznaný dodací list:
```
Sender: doprava@acme.cz (whitelist)
Text: "Dodací list DL-8765, expedováno 28.3.2024,
       Počet balíků: 2, Hmotnost: 15 kg,
       Odkaz: Obj. 2024-001"

Výsledek:
  Type: dodaci_list
  Confidence: 0.91 + 0.15 (whitelist) = 0.96 (96%)
  ✅ Whitelist sender + correct format
```

### Podezřelá objednávka (missing info):
```
Sender: dodavatel@acme.cz (whitelist)
Text: "Toto je naše objednávka na zboží.
       Prosím dodejte co nejdříve."

Výsledek:
  Type: objednavka
  Confidence: 0.65 + 0.05 (reduced whitelist) = 0.70 (70%)
  ⚠️ Whitelist sender but missing order number!
```

---

## ⚠️ Ochrana před podvodem

### Implementované kontroly:

1. **Kontrola čísla objednávky:**
   - Pokud je typ `objednavka` ale chybí číslo → PODEZŘELÉ
   - Whitelist boost snížen z 15% na 5%

2. **Kontrola dodacích údajů:**
   - Pokud je typ `dodaci_list` ale chybí hmotnost/balíky → PODEZŘELÉ
   - Whitelist boost snížen z 15% na 5%

3. **Log warnings:**
   - Všechny podezřelé případy jsou logovány
   - Lze filtrovat: `grep "⚠️" logs/*.log`

---

## 📊 Změny v souborech

### Upravené soubory:

1. **`src/ai/classifier_improved.py`**
   - Přidány kategorie (řádky 40-41)
   - Přidány příklady (řádky 78-91)
   - Přidána whitelist kontrola (řádky 338-379)
   - Přidán import BlacklistWhitelist (řádky 32-34)

2. **`config/config.yaml`**
   - Přidány typy (řádky 54-55)
   - Přidány keywords pro objednavka (řádky 79-91)
   - Přidány keywords pro dodaci_list (řádky 92-105)

3. **Nově vytvořené:**
   - `OBJEDNAVKA_DODACI_LIST_IMPLEMENTACE.md` (tento soubor)

---

## ✅ Testování

### Manuální test:

```bash
cd ~/maj-document-recognition
source venv/bin/activate

# Test objednávky
echo "Objednávka č. PO-2024-001, Dodavatel: ACME, Cena: 2000 Kč" > /tmp/test_objednavka.txt
python -c "
from src.ai.classifier_improved import ImprovedAIClassifier
from src.database.db_manager import DatabaseManager
import yaml

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

db = DatabaseManager(config)
clf = ImprovedAIClassifier(config, db)

with open('/tmp/test_objednavka.txt') as f:
    text = f.read()

result = clf.classify(text, {'sender': 'test@example.com'})
print(f\"Type: {result['type']}, Confidence: {result['confidence']:.2%}\")
"

# Test dodacího listu
echo "Dodací list č. DL-001, Hmotnost: 15 kg, Počet balíků: 2" > /tmp/test_dodaci.txt
python -c "
from src.ai.classifier_improved import ImprovedAIClassifier
from src.database.db_manager import DatabaseManager
import yaml

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

db = DatabaseManager(config)
clf = ImprovedAIClassifier(config, db)

with open('/tmp/test_dodaci.txt') as f:
    text = f.read()

result = clf.classify(text, {'sender': 'test@example.com'})
print(f\"Type: {result['type']}, Confidence: {result['confidence']:.2%}\")
"
```

---

## 📞 Support

**Issues:** Pokud najdeš chybu v rozpoznávání:
1. Zkontroluj log: `tail -100 logs/*.log | grep "objednavka\|dodaci_list"`
2. Zkontroluj whitelist: `python -c "from src.integrations.blacklist_whitelist import BlacklistWhitelist; import yaml; bw = BlacklistWhitelist(yaml.safe_load(open('config/config.yaml'))); print(bw.is_whitelisted('sender@example.com'))"`

**Future improvements:**
- [ ] Extrakce čísla objednávky do metadata
- [ ] Extrakce dodacího termínu
- [ ] Automatické párování objednávka → dodací list → faktura
- [ ] Detekce duplicitních objednávek

---

**Made with ❤️ by MAJ + Claude Code**
**Version 2.1 - Released 2025-11-06**
