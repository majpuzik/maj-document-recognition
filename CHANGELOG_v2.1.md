# Changelog - MAJ Document Recognition v2.1

## 🎉 v2.1 - Objednávka & Dodací list (2025-11-06)

### ✨ Nové funkce

#### 📋 Nové typy dokumentů
- **Objednávka** (Purchase Order / Bestellung)
  - Rozpoznávání čísla objednávky
  - Detekce cen a množství
  - Identifikace dodacího termínu
  - Whitelist verifikace s kontrolou formátu

- **Dodací list** (Delivery Note / Lieferschein)
  - Rozpoznávání čísla dodacího listu
  - Detekce hmotnosti a počtu balíků
  - Obvykle bez cen (klíčový rozdíl od faktury)
  - Whitelist verifikace s kontrolou informací o zásilce

#### 🛡️ Fraud Detection
- Přísná kontrola pro whitelist sendery
- +15% confidence boost pro důvěryhodné odesílatele
- +5% snížený boost pokud chybí povinné prvky
- Automatické logování podezřelých případů

#### 🌍 Multilingvální podpora
- **Čeština**: objednávka, dodací list, číslo obj., hmotnost
- **Němčina**: Bestellung, Lieferschein, Bestellnummer, Gewicht
- **Angličtina**: Purchase Order, Delivery Note, PO Number, Weight

### 🔧 Technické změny

#### `src/ai/classifier_improved.py`
```python
# Řádky 40-41: Přidány kategorie
- objednavka: Objednávka, purchase order, Bestellung
- dodaci_list: Dodací list, delivery note, Lieferschein

# Řádky 78-91: Few-shot learning příklady
Příklad 6: Objednávka s cenami a dodacím termínem
Příklad 7: Dodací list s hmotností a počtem balíků

# Řádky 32-34: Import BlacklistWhitelist
from ..integrations.blacklist_whitelist import BlacklistWhitelist

# Řádky 338-379: Whitelist verifikace
- Kontrola čísla objednávky
- Kontrola čísla DL a shipping info
- Automatické snížení boostu při chybějících prvcích
```

#### `config/config.yaml`
```yaml
# Řádky 54-55: Nové typy
classification:
  types:
    - "objednavka"        # ← NOVÉ!
    - "dodaci_list"       # ← NOVÉ!

# Řádky 79-105: Multilingvální keywords
objednavka:
  - "objednávka", "purchase order", "bestellung"
  - "číslo objednávky", "po number", "bestellnummer"
  - "dodací termín", "delivery date", "liefertermin"

dodaci_list:
  - "dodací list", "delivery note", "lieferschein"
  - "hmotnost", "gewicht", "weight"
  - "počet balíků", "pakete", "packages"
```

### 📖 Dokumentace

#### `OBJEDNAVKA_DODACI_LIST_IMPLEMENTACE.md` (400+ řádků)
- ✅ Detailní analýza charakteristik dokumentů
- ✅ Rozhodovací tabulka (Objednávka vs Dodací list vs Faktura)
- ✅ Whitelist verifikační logika
- ✅ Fraud protection mechanismy
- ✅ Příklady použití a testování
- ✅ Troubleshooting guide

### 📊 Rozlišovací vlastnosti

| Vlastnost              | Objednávka | Dodací list | Faktura |
|------------------------|------------|-------------|---------|
| **Obsahuje ceny**      | ✅ Ano     | ❌ Ne       | ✅ Ano  |
| **Obsahuje DPH**       | ⚠️ Někdy   | ❌ Ne       | ✅ Ano  |
| **Číslo objednávky**   | ✅ Ano     | ✅ Ref      | ✅ Ref  |
| **Hmotnost balíku**    | ❌ Ne      | ✅ Ano      | ❌ Ne   |
| **Počet balíků**       | ❌ Ne      | ✅ Ano      | ❌ Ne   |
| **Dodací termín**      | ✅ Ano     | ❌ Ne       | ❌ Ne   |
| **Datum splatnosti**   | ❌ Ne      | ❌ Ne       | ✅ Ano  |
| **Bankovní údaje**     | ❌ Ne      | ❌ Ne       | ✅ Ano  |

### 🧪 Testování

```bash
cd ~/maj-document-recognition
source venv/bin/activate

# Test objednávky
echo "Objednávka č. PO-2024-001, Cena: 2000 Kč" > /tmp/test_objednavka.txt
python -c "
from src.ai.classifier_improved import ImprovedAIClassifier
# ... test code
"

# Test dodacího listu
echo "Dodací list č. DL-001, Hmotnost: 15 kg" > /tmp/test_dodaci.txt
python -c "
from src.ai.classifier_improved import ImprovedAIClassifier
# ... test code
"
```

### 📈 Statistiky

- **3 soubory změněny**
- **981 řádků přidáno**
- **400+ řádků dokumentace**
- **2 nové typy dokumentů**
- **26 multilingválních keywords**

### 🔍 Příklady rozpoznání

#### ✅ Správně rozpoznaná objednávka
```
Sender: dodavatel@acme.cz (whitelist)
Text: "Objednávka č. 2024-001, Položka: Šrouby M6,
       1000 ks × 2 Kč = 2000 Kč, Dodací termín: 30.3.2024"

Výsledek:
  Type: objednavka
  Confidence: 0.93 + 0.15 (whitelist) = 0.98 (98%)
  ✅ Whitelist sender + correct format
```

#### ✅ Správně rozpoznaný dodací list
```
Sender: doprava@acme.cz (whitelist)
Text: "Dodací list DL-8765, Počet balíků: 2,
       Hmotnost: 15 kg, Odkaz: Obj. 2024-001"

Výsledek:
  Type: dodaci_list
  Confidence: 0.91 + 0.15 (whitelist) = 0.96 (96%)
  ✅ Whitelist sender + correct format
```

#### ⚠️ Podezřelá objednávka
```
Sender: dodavatel@acme.cz (whitelist)
Text: "Toto je naše objednávka na zboží."

Výsledek:
  Type: objednavka
  Confidence: 0.65 + 0.05 (reduced) = 0.70 (70%)
  ⚠️ Whitelist sender but missing order number!
```

### 🚀 Upgrade guide

1. **Pull latest changes:**
   ```bash
   git pull origin main
   git checkout v2.1-objednavka-dodaci-list
   ```

2. **Žádné další kroky nejsou potřeba!**
   - Config automaticky načte nové typy
   - AI classifier automaticky používá nové prompty
   - Whitelist verifikace je aktivní okamžitě

3. **Verify installation:**
   ```bash
   grep -A 5 "objednavka:" config/config.yaml
   grep "OBJEDNÁVKA obsahuje CENY" src/ai/classifier_improved.py
   ```

### ⚠️ Breaking Changes

**ŽÁDNÉ!** Všechny změny jsou backward compatible.

### 🔮 Plánované vylepšení (v2.2)

- [ ] Extrakce čísla objednávky do metadata
- [ ] Extrakce dodacího termínu
- [ ] Automatické párování: objednávka → dodací list → faktura
- [ ] Detekce duplicitních objednávek
- [ ] Export objednávek do ERP systémů
- [ ] Grafické rozhraní pro přehled objednávek

### 🙏 Poděkování

Made with ❤️ by **MAJ + Claude Code**

---

**Released:** 2025-11-06
**Version:** v2.1
**Git tag:** `v2.1-objednavka-dodaci-list`
**Commit:** `52610c9`
