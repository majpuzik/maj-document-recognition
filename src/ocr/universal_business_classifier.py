#!/usr/bin/env python3
"""
Universal Business Document Classifier
Recognizes ALL types of business documents, not just invoices

Supported document types:
- Faktury (invoices)
- Účtenky (receipts)
- Bankovní výpisy (bank statements)
- Smlouvy (contracts)
- Objednávky (orders)
- Dodací listy (delivery notes)
- Daňové doklady (tax documents)
- Parkovací lístky (parking tickets)
- Doklady o platbě (payment documents)
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

class DocumentType(Enum):
    """Typy obchodních dokumentů"""
    INVOICE = "faktura"
    RECEIPT = "účtenka"
    BANK_STATEMENT = "bankovní_výpis"
    CONTRACT = "smlouva"
    ORDER = "objednávka"
    DELIVERY_NOTE = "dodací_list"
    TAX_DOCUMENT = "daňový_doklad"
    PARKING_TICKET = "parkovací_lístek"
    PAYMENT_DOCUMENT = "doklad_o_platbě"
    PURCHASE_ORDER = "nákupní_objednávka"
    PROFORMA = "proforma"
    CREDIT_NOTE = "dobropis"
    DEBIT_NOTE = "vrubopis"
    GAS_RECEIPT = "účtenka_čerpací_stanice"
    CAR_WASH = "mytí_auta"
    CAR_SERVICE = "autoservis"
    GLASS_WORK = "sklenářství"
    # NEW CATEGORIES
    MEDICAL_REPORT = "lékařská_zpráva"
    PERSONAL_ID = "osobní_doklad"
    INSURANCE = "pojištění"
    MARKETING = "reklama"
    POWER_OF_ATTORNEY = "plná_moc"
    DECLARATION = "čestné_prohlášení"
    UNKNOWN = "neznámý"

@dataclass
class DocumentPattern:
    """Pattern pro detekci typu dokumentu"""
    keywords: List[str]
    required_fields: List[str]
    bonus_patterns: List[str]
    negative_patterns: List[str]
    base_score: int

class UniversalBusinessClassifier:
    """Univerzální klasifikátor obchodních dokumentů"""

    def __init__(self):
        self.patterns = self._init_patterns()

    def _init_patterns(self) -> Dict[DocumentType, DocumentPattern]:
        """Inicializace vzorů pro všechny typy dokumentů"""
        return {
            # FAKTURY (včetně hotelových účtů)
            DocumentType.INVOICE: DocumentPattern(
                keywords=[
                    r'\bFAKTURA\b', r'\bINVOICE\b', r'\bFACTUUR\b', r'\bRACHNUNG\b',
                    r'\bDaňový doklad\b', r'\bDAŇOVÝ DOKLAD\b',
                    r'\bVariabilní symbol\b', r'\bČíslo faktury\b', r'\bFakturujeme vám\b',
                    # Hotelové faktury
                    r'\bFOLIO\b', r'\bHOTEL\s+INVOICE\b', r'\bGUEST\s+FOLIO\b',
                    r'Accommodation', r'Room\s+No', r'VAT\s+Detail'
                ],
                required_fields=[r'DIČ|IČ DPH|VAT', r'IČO|IČ|VAT\s+-\s+\(\d+%\)', r'DPH|VAT|MWST'],
                bonus_patterns=[
                    r'Datum splatnosti', r'Datum vystavení', r'IBAN',
                    r'Konstantní symbol', r'Specifický symbol',
                    # Hotelové
                    r'Arrival', r'Departure', r'Room\s+Rate', r'Reservation\s+No',
                    r'Total\s+gross', r'Balance\s+to\s+pay', r'Credit\s+Card'
                ],
                negative_patterns=[r'PARKOVNÉ', r'ÚČTENKA\s+Z\s+EET'],
                base_score=100
            ),

            # ÚČTENKY (obecné)
            DocumentType.RECEIPT: DocumentPattern(
                keywords=[
                    r'\bÚČTENKA\b', r'\bRECEIPT\b', r'\bBELEG\b', r'\bBON\b',
                    r'Daňový doklad\s+-\s+účtenka', r'Doklad o prodeji'
                ],
                required_fields=[r'DIČ|IČ DPH', r'Celkem|Total|Gesamt'],
                bonus_patterns=[
                    r'EET|FIK', r'BKP', r'PKP', r'Datum a čas',
                    r'Pokladna', r'Paragon', r'Číslo účtenky'
                ],
                negative_patterns=[],
                base_score=80
            ),

            # ÚČTENKY ČERPACÍ STANICE
            DocumentType.GAS_RECEIPT: DocumentPattern(
                keywords=[
                    r'\bBENZÍN\b', r'\bNAFTA\b', r'\bPETROL\b', r'\bDIESEL\b', r'\bGAS\b',
                    r'Natural\s+95', r'Natural\s+98', r'LPG', r'CNG',
                    r'Čerpací stanice', r'Benzinová pumpa', r'OMV', r'Shell', r'Benzina'
                ],
                required_fields=[r'\d+[.,]\d+\s*l', r'\d+[.,]\d+\s*Kč'],
                bonus_patterns=[
                    r'Litr', r'l/100km', r'Cena za litr', r'Stáčí', r'Točna',
                    r'Výdej PHM', r'Prodej PHM'
                ],
                negative_patterns=[],
                base_score=90
            ),

            # MYTÍ AUTA
            DocumentType.CAR_WASH: DocumentPattern(
                keywords=[
                    r'\bMYTÍ\b', r'\bCAR\s+WASH\b', r'\bWASCH\b',
                    r'Čištění vozu', r'Čistírna', r'Mytí vozidla'
                ],
                required_fields=[r'\d+[.,]\d+\s*Kč'],
                bonus_patterns=[
                    r'Exteriér', r'Interiér', r'Kompletní mytí', r'Program'
                ],
                negative_patterns=[],
                base_score=85
            ),

            # AUTOSERVIS
            DocumentType.CAR_SERVICE: DocumentPattern(
                keywords=[
                    r'\bSERVIS\b', r'\bOPRAVA\b', r'\bÚDRŽBA\b', r'\bSERVICE\b',
                    r'Výměna oleje', r'Pneuservis', r'Autoopravna', r'Autoservis',
                    r'Výměna kol', r'Pneumatik'
                ],
                required_fields=[r'IČO|IČ', r'\d+[.,]\d+\s*Kč'],
                bonus_patterns=[
                    r'SPZ', r'VIN', r'Stav tachometru', r'Značka vozu', r'Model'
                ],
                negative_patterns=[],
                base_score=85
            ),

            # SKLENÁŘSTVÍ
            DocumentType.GLASS_WORK: DocumentPattern(
                keywords=[
                    r'\bSKLENÁŘSTVÍ\b', r'\bSKLO\b', r'\bGLAS\b', r'\bGLASS\b',
                    r'Zasklení', r'Skleněný', r'Výroba skel'
                ],
                required_fields=[r'IČO|IČ', r'\d+[.,]\d+\s*Kč'],
                bonus_patterns=[
                    r'mm', r'tloušťka', r'rozměr', r'm2', r'cm2'
                ],
                negative_patterns=[],
                base_score=85
            ),

            # BANKOVNÍ VÝPISY
            DocumentType.BANK_STATEMENT: DocumentPattern(
                keywords=[
                    r'\bVÝPIS\s+Z\s+ÚČTU\b', r'\bBANK\s+STATEMENT\b', r'\bKONTOAUSZUG\b',
                    r'Zůstatek na účtu', r'Počáteční stav', r'Konečný stav',
                    r'Příchozí platby', r'Odchozí platby'
                ],
                required_fields=[r'Číslo účtu|Account number', r'\d{10}/\d{4}'],
                bonus_patterns=[
                    r'IBAN', r'Majitel účtu', r'Období výpisu',
                    r'VS|Variabilní symbol', r'KS|Konstantní symbol'
                ],
                negative_patterns=[],
                base_score=95
            ),

            # SMLOUVY
            DocumentType.CONTRACT: DocumentPattern(
                keywords=[
                    r'\bSMLOUVA\b', r'\bCONTRACT\b', r'\bVERTRAG\b',
                    r'Kupní smlouva', r'Nájemní smlouva', r'Smlouva o dílo',
                    r'Uzavřeli', r'Smluvní strany', r'Předmět smlouvy'
                ],
                required_fields=[r'Smluvní\s+strana', r'Podpis'],
                bonus_patterns=[
                    r'Článek', r'§', r'Odstavec', r'Příloha',
                    r'Práva a povinnosti', r'Platnost smlouvy'
                ],
                negative_patterns=[],
                base_score=90
            ),

            # DODACÍ LISTY
            DocumentType.DELIVERY_NOTE: DocumentPattern(
                keywords=[
                    r'\bDODACÍ\s+LIST\b', r'\bDELIVERY\s+NOTE\b', r'\bLIEFERSCHEIN\b',
                    r'Dodávka zboží', r'Přeprava', r'Expedice'
                ],
                required_fields=[r'IČO|IČ', r'Číslo\s+dodacího\s+listu'],
                bonus_patterns=[
                    r'Počet kusů', r'Balíky', r'Váha', r'Přepravce',
                    r'Datum expedice', r'Převzal'
                ],
                negative_patterns=[],
                base_score=85
            ),

            # OBJEDNÁVKY
            DocumentType.ORDER: DocumentPattern(
                keywords=[
                    r'\bOBJEDNÁVKA\b', r'\bORDER\b', r'\bBESTELLUNG\b',
                    r'Objednáváme', r'Objednávací číslo'
                ],
                required_fields=[r'IČO|IČ', r'Množství|Počet'],
                bonus_patterns=[
                    r'Dodací termín', r'Odběratel', r'Dodavatel',
                    r'Jednotková cena'
                ],
                negative_patterns=[],
                base_score=80
            ),

            # PARKOVACÍ LÍSTKY
            DocumentType.PARKING_TICKET: DocumentPattern(
                keywords=[
                    r'\bPARKOVNÉ\b', r'\bPARKING\s+TICKET\b', r'\bPARKEN\b',
                    r'Parkovací lístek', r'Parkoviště',
                    r'Parkovací automat', r'Parkovací zóna'
                ],
                required_fields=[r'Vjezd|Výjezd|Doba parkování', r'\d{2}:\d{2}'],
                bonus_patterns=[
                    r'SPZ', r'RZ', r'Zóna', r'Automat', r'Zaplaceno'
                ],
                negative_patterns=[
                    r'\bPLNÁ\s+MOC\b', r'\bZMOCNĚNÍ\b', r'\bINVOICE\b', r'\bFAKTURA\b',
                    r'\bHOTEL\b', r'\bACCOMMODATION\b', r'\bRoom\s+No\b',
                    r'\bCOPILOT\b', r'\bMICROSOFT\b', r'\bWORD\b', r'\bEXCEL\b'
                ],
                base_score=85
            ),

            # DOKLADY O PLATBĚ
            DocumentType.PAYMENT_DOCUMENT: DocumentPattern(
                keywords=[
                    r'\bDOKLAD\s+O\s+PLATBĚ\b', r'\bPAYMENT\s+RECEIPT\b',
                    r'Potvrzení o platbě', r'Platební doklad',
                    r'Úhrada', r'Zaplaceno'
                ],
                required_fields=[r'\d+[.,]\d+\s*Kč', r'Datum\s+platby|Datum\s+úhrady'],
                bonus_patterns=[
                    r'Způsob platby', r'Hotově|Kartou|Převodem',
                    r'Variabilní symbol'
                ],
                negative_patterns=[],
                base_score=75
            ),

            # PROFORMA
            DocumentType.PROFORMA: DocumentPattern(
                keywords=[
                    r'\bPROFORMA\b', r'\bZÁLOHOVÁ\s+FAKTURA\b',
                    r'Proforma invoice'
                ],
                required_fields=[r'IČO|IČ', r'DIČ|IČ DPH'],
                bonus_patterns=[r'Záloha', r'Platba předem', r'Advance payment'],
                negative_patterns=[],
                base_score=90
            ),

            # DOBROPIS
            DocumentType.CREDIT_NOTE: DocumentPattern(
                keywords=[
                    r'\bDOBROPIS\b', r'\bCREDIT\s+NOTE\b', r'\bGUTSCHRIFT\b',
                    r'Opravný daňový doklad'
                ],
                required_fields=[r'IČO|IČ', r'DIČ|IČ DPH'],
                bonus_patterns=[r'K\s+faktuře\s+č\.', r'Storno', r'Korekce'],
                negative_patterns=[],
                base_score=85
            ),

            # LÉKAŘSKÁ ZPRÁVA
            DocumentType.MEDICAL_REPORT: DocumentPattern(
                keywords=[
                    r'\bLÉKAŘSKÝ\s+POSUDEK\b', r'\bLÉKAŘSKÁ\s+ZPRÁVA\b',
                    r'\bNÁLEZ\b', r'\bVYŠETŘENÍ\b', r'\bDIAGNÓZA\b',
                    r'\bZDRAVOTNÍ\s+ZPŮSOBILOST\b', r'\bZDRAVOTNÍ\s+STAV\b',
                    r'Posudek\s+o\s+zdravotní', r'zdravotnich\s+sluzeb',
                    r'\bPACIENT\b', r'\bOŠETŘUJÍCÍ\s+LÉKAŘ\b',
                    r'Ambulantní', r'Hospitalizace', r'Poliklinika',
                    r'\bEKG\b', r'\bRTG\b', r'\bCT\b', r'\bMRI\b', r'\bUSG\b',
                    r'Kardiolog', r'Ortoped', r'Neurolog', r'Praktický\s+lékař'
                ],
                required_fields=[r'rodné\s+číslo|r\.č\.|datum\s+narození', r'jméno|pacient'],
                bonus_patterns=[
                    r'Anamnéza', r'Terapie', r'Doporučení', r'Kontrola',
                    r'Předepsané léky', r'Pracovní neschopnost', r'Diagnóza',
                    r'Zdravotní pojišťovna', r'IČP', r'Kód diagnózy',
                    r'způsobilý|nezpůsobilý', r'schopen|neschopen'
                ],
                negative_patterns=[r'\bFAKTURA\b', r'\bÚČTENKA\b', r'\bDPH\b'],
                base_score=95
            ),

            # OSOBNÍ DOKLADY (řidičák, občanka, pas)
            DocumentType.PERSONAL_ID: DocumentPattern(
                keywords=[
                    r'\bŘIDIČSKÝ\s+PRŮKAZ\b', r'\bŘIDIČÁK\b', r'\bFÜHRERSCHEIN\b',
                    r'\bOBČANSKÝ\s+PRŮKAZ\b', r'\bOBČANKA\b', r'\bPERSONALAUSWEIS\b',
                    r'\bPAS\b', r'\bCESTOVNÍ\s+DOKLAD\b', r'\bREISEPASS\b',
                    r'DRIVING\s+LICENCE', r'IDENTITY\s+CARD', r'PASSPORT',
                    r'Skupina\s+vozidel', r'Platnost\s+do', r'Vydán\s+dne',
                    r'Místo\s+narození', r'Státní\s+občanství'
                ],
                required_fields=[r'rodné\s+číslo|r\.č\.|datum\s+narození', r'jméno|příjmení'],
                bonus_patterns=[
                    r'Skupina\s+[ABCDE]', r'Kód\s+95', r'Podpis\s+držitele',
                    r'Číslo\s+dokladu', r'Vydávající\s+úřad', r'Trvalý\s+pobyt',
                    r'Fotografická\s+podoba', r'Biometrický'
                ],
                negative_patterns=[r'\bFAKTURA\b', r'\bÚČTENKA\b', r'\bDPH\b'],
                base_score=90
            ),

            # POJIŠTĚNÍ
            DocumentType.INSURANCE: DocumentPattern(
                keywords=[
                    r'\bPOJIŠTĚNÍ\b', r'\bPOJISTKA\b', r'\bPOJISTNÁ\s+SMLOUVA\b',
                    r'\bINSURANCE\b', r'\bVERSICHERUNG\b',
                    r'Pojistné\s+plnění', r'Pojistná\s+událost', r'Pojistné\s+podmínky',
                    r'ALLIANZ', r'GENERALI', r'KOOPERATIVA', r'ČPP', r'ČSOB\s+Pojišťovna',
                    r'UNIQA', r'DIRECT', r'AXA', r'MetLife'
                ],
                required_fields=[r'Číslo\s+pojistky|Číslo\s+smlouvy', r'Pojistník|Pojištěný'],
                bonus_patterns=[
                    r'Pojistné', r'Spoluúčast', r'Pojistná\s+částka',
                    r'Územní\s+platnost', r'Pojištěné\s+riziko',
                    r'Havarijní\s+pojištění', r'Povinné\s+ručení', r'Životní\s+pojištění'
                ],
                negative_patterns=[],
                base_score=90
            ),

            # REKLAMA / MARKETING
            DocumentType.MARKETING: DocumentPattern(
                keywords=[
                    r'\bSLEVA\b', r'\bAKCE\b', r'\bVÝPRODEJ\b', r'\bZDARMA\b',
                    r'\bNEWSLETTER\b', r'\bODHLÁSIT\b', r'\bUNSUBSCRIBE\b',
                    r'Limitovaná\s+nabídka', r'Exkluzivní\s+nabídka',
                    r'BLACK\s+FRIDAY', r'CYBER\s+MONDAY',
                    r'\bRABATT\b', r'\bDISCOUNT\b', r'\bOFFER\b', r'\bSALE\b',
                    r'Nenechte\s+si\s+ujít', r'Pouze\s+dnes', r'Jen\s+teď'
                ],
                required_fields=[],
                bonus_patterns=[
                    r'\d+%\s*sleva', r'\d+%\s*off', r'Klikněte\s+zde',
                    r'Objednat\s+nyní', r'Koupit\s+teď', r'Call\s+to\s+action',
                    r'Přihlásit\s+k\s+odběru', r'Sledujte\s+nás'
                ],
                negative_patterns=[r'\bFAKTURA\b', r'\bÚČTENKA\b', r'\bDPH\b', r'IČO'],
                base_score=80
            ),

            # PLNÁ MOC
            DocumentType.POWER_OF_ATTORNEY: DocumentPattern(
                keywords=[
                    r'\bPLNÁ\s+MOC\b', r'\bPLNA\s+MOC\b', r'\bPINA\s+MOC\b',  # OCR varianty
                    r'\bZMOCNĚNÍ\b', r'\bZPLNOMOCNĚNÍ\b',
                    r'\bVOLLMACHT\b', r'\bPOWER\s+OF\s+ATTORNEY\b',
                    r'Zmocňuji', r'Zplnomocňuji', r'Zplnomocnuji', r'Zpinomochuji',  # OCR
                    r'Pověřuji', r'jednat\s+mým\s+jménem', r'zastupovat\s+mě',
                    r'daňového\s+poradce', r'daňový\s+poradce', r'datiov',  # OCR varianty
                    r'poplatník|Poplatnik'  # OCR varianty
                ],
                required_fields=[r'podpis|Podpis', r'jméno|Poplatnik|zmocnitel|zmocněnec'],
                bonus_patterns=[
                    r'Zmocnitel', r'Zmocněnec', r'Rozsah\s+zmocnění',
                    r'Ověřený\s+podpis', r'Úředně\s+ověřený',
                    r'Finanční\s+úřad', r'Finanéni\s+Gfad',  # OCR varianty
                    r'Územní\s+pracoviště', r'Uzemni\s+pracovi',  # OCR varianty
                    r'daňov', r'přiznání', r'přeplatek', r'r\.č\.', r'r\.\s*c\.',
                    r'seznam.*poradc'  # daňový poradce v seznamu
                ],
                negative_patterns=[r'\bPARKOVNÉ\b', r'\bPARKING\b'],
                base_score=95
            ),

            # ČESTNÉ PROHLÁŠENÍ
            DocumentType.DECLARATION: DocumentPattern(
                keywords=[
                    r'\bČESTNÉ\s+PROHLÁŠENÍ\b', r'\bPROHLÁŠENÍ\b',
                    r'\bEIDESSTATTLICHE\s+ERKLÄRUNG\b', r'\bDECLARATION\b',
                    r'Prohlašuji', r'Čestně\s+prohlašuji', r'Tímto\s+prohlašuji',
                    r'pod\s+sankcí\s+trestního\s+postihu'
                ],
                required_fields=[r'jméno|podepsaný', r'datum|dne'],
                bonus_patterns=[
                    r'Pravdivost', r'Pod\s+přísahou', r'Jsem\s+si\s+vědom',
                    r'Podpis', r'V\s+[A-Z][a-z]+,?\s+dne'
                ],
                negative_patterns=[],
                base_score=85
            )
        }

    def classify(self, text: str) -> Tuple[DocumentType, int, Dict]:
        """
        Klasifikuje obchodní dokument

        Returns:
            (DocumentType, confidence_score, details)
        """
        text_upper = text.upper()
        results = []

        for doc_type, pattern in self.patterns.items():
            score = 0
            matched_keywords = []
            matched_fields = []
            matched_bonuses = []

            # 1. Kontrola klíčových slov (base score)
            keyword_matches = 0
            for keyword in pattern.keywords:
                if re.search(keyword, text, re.IGNORECASE):
                    keyword_matches += 1
                    matched_keywords.append(keyword)

            if keyword_matches > 0:
                score += pattern.base_score

            # 2. Povinná pole (mandatory +50)
            required_match_count = 0
            for req_field in pattern.required_fields:
                if re.search(req_field, text, re.IGNORECASE):
                    required_match_count += 1
                    matched_fields.append(req_field)

            if len(pattern.required_fields) > 0:
                required_ratio = required_match_count / len(pattern.required_fields)
                score += int(required_ratio * 50)

            # 3. Bonusové vzory (+5 za každý)
            for bonus in pattern.bonus_patterns:
                if re.search(bonus, text, re.IGNORECASE):
                    score += 5
                    matched_bonuses.append(bonus)

            # 4. Negativní vzory (-50)
            has_negative = False
            for negative in pattern.negative_patterns:
                if re.search(negative, text, re.IGNORECASE):
                    score -= 50
                    has_negative = True

            # Uložit výsledek
            if score > 0:
                results.append({
                    'type': doc_type,
                    'score': score,
                    'keyword_count': keyword_matches,
                    'matched_keywords': matched_keywords[:3],
                    'matched_fields': matched_fields[:3],
                    'matched_bonuses': matched_bonuses[:3],
                    'has_negative': has_negative
                })

        # Seřadit podle skóre
        results.sort(key=lambda x: x['score'], reverse=True)

        if not results or results[0]['score'] < 50:
            return (DocumentType.UNKNOWN, 0, {
                'reason': 'No sufficient patterns matched',
                'text_length': len(text)
            })

        best = results[0]
        return (
            best['type'],
            min(200, best['score']),  # Cap at 200
            {
                'matched_keywords': best['matched_keywords'],
                'matched_fields': best['matched_fields'],
                'matched_bonuses': best['matched_bonuses'],
                'keyword_count': best['keyword_count'],
                'all_candidates': [
                    f"{r['type'].value}: {r['score']}"
                    for r in results[:3]
                ]
            }
        )

    def extract_metadata(self, text: str, doc_type: DocumentType) -> Dict:
        """Extrahuje metadata podle typu dokumentu"""
        metadata = {}

        # IČO
        ico_match = re.search(r'IČO?:?\s*(\d{8})', text, re.IGNORECASE)
        if ico_match:
            metadata['ico'] = ico_match.group(1)

        # DIČ
        dic_match = re.search(r'DIČ|IČ\s*DPH:?\s*(CZ\d{8,10}|\d{8,10})', text, re.IGNORECASE)
        if dic_match:
            metadata['dic'] = dic_match.group(1)

        # Částky
        amounts = re.findall(r'(\d+[.,]\d{2})\s*Kč', text)
        if amounts:
            metadata['amounts'] = amounts[:3]

        # Datum (český formát)
        dates = re.findall(r'\d{1,2}\.\s*\d{1,2}\.\s*\d{4}', text)
        if dates:
            metadata['dates'] = dates[:3]

        # SPZ (pro auto dokumenty)
        if doc_type in [DocumentType.GAS_RECEIPT, DocumentType.CAR_SERVICE, DocumentType.PARKING_TICKET]:
            spz_match = re.search(r'\b[0-9][A-Z]{1,2}\d{1,4}\b', text)
            if spz_match:
                metadata['spz'] = spz_match.group(0)

        # Litry (pro benzín)
        if doc_type == DocumentType.GAS_RECEIPT:
            liters = re.findall(r'(\d+[.,]\d+)\s*l', text, re.IGNORECASE)
            if liters:
                metadata['liters'] = liters[0]

        return metadata

def classify_document(text: str) -> Dict:
    """
    Klasifikuje dokument a vrátí kompletní výsledek

    Args:
        text: Extrahovaný text z dokumentu

    Returns:
        Dict s výsledky klasifikace
    """
    classifier = UniversalBusinessClassifier()
    doc_type, confidence, details = classifier.classify(text)
    metadata = classifier.extract_metadata(text, doc_type)

    return {
        'type': doc_type.value,
        'type_cz': doc_type.value,
        'confidence': confidence,
        'confidence_level': _get_confidence_level(confidence),
        'details': details,
        'metadata': metadata,
        'text_length': len(text)
    }

def _get_confidence_level(score: int) -> str:
    """Určí úroveň jistoty"""
    if score >= 150:
        return 'VERY_HIGH'
    elif score >= 100:
        return 'HIGH'
    elif score >= 70:
        return 'MEDIUM'
    else:
        return 'LOW'

if __name__ == "__main__":
    # Testy
    test_texts = {
        'faktura': '''
            FAKTURA č. 2024001
            IČO: 12345678
            DIČ: CZ12345678
            DPH 21%
            Celkem: 15000.00 Kč
            Datum splatnosti: 31.12.2024
        ''',
        'uctenka_benzin': '''
            ÚČTENKA
            Natural 95
            32.50 l
            Cena za litr: 35.90 Kč
            Celkem: 1166.75 Kč
            DIČ: CZ12345678
            25.10.2024 15:30
        ''',
        'parkovani': '''
            PARKOVNÉ
            SPZ: 1AB1234
            Vjezd: 10:30
            Výjezd: 14:45
            Doba parkování: 4h 15m
            Částka: 80.00 Kč
        '''
    }

    for name, text in test_texts.items():
        result = classify_document(text)
        print(f"\n{name.upper()}:")
        print(f"  Typ: {result['type']}")
        print(f"  Confidence: {result['confidence']}/200 ({result['confidence_level']})")
        print(f"  Metadata: {result['metadata']}")
