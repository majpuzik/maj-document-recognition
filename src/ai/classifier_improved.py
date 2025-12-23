"""
IMPROVED AI-based document classification
"""

import logging
import re
from typing import Dict, List, Optional

import requests

from .ml_model import MLModel
from .reklamni_filtr import ReklamniFiltr
from .soudni_filtr import SoudniFiltr


class ImprovedAIClassifier:
    """Improved AI-powered document classifier with better prompts and models"""

    def __init__(self, config: dict, db_manager=None):
        self.config = config
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.ai_config = config.get("ai", {})
        self.ollama_config = self.ai_config.get("ollama", {})
        self.classification_config = config.get("classification", {})

        # Initialize sub-classifiers
        self.ml_model = MLModel(config, db_manager) if self.ai_config.get("ml_model", {}).get("enabled") else None
        self.reklamni_filtr = ReklamniFiltr(config)
        self.soudni_filtr = SoudniFiltr(config)

        # Import BlacklistWhitelist for sender verification
        from ..integrations.blacklist_whitelist import BlacklistWhitelist
        self.blacklist_whitelist = BlacklistWhitelist(config)

    def _build_improved_prompt(self, text: str, metadata: Dict = None) -> str:
        """Build improved prompt with examples (few-shot learning)"""

        prompt = """Jsi expert na klasifikaci českých, německých a anglických obchodních dokumentů.

DOSTUPNÉ KATEGORIE:
- faktura: Daňový doklad, invoice, Rechnung (obsahuje částky, DIČ, IČO, datum zdanitelného plnění)
- stvrzenka: Pokladní doklad, receipt, paragon (bez DIČ, jednoduchý účet)
- objednavka: Objednávka, purchase order, Bestellung (číslo objednávky, položky, ceny, dodací termín)
- dodaci_list: Dodací list, delivery note, Lieferschein (bez cen!, číslo DL, hmotnost, počet balíků)
- bankovni_vypis: Výpis z účtu, bank statement (transakce, zůstatek)
- vyzva_k_platbe: Payment request, Zahlungsaufforderung (výzva zaplatit fakturu)
- oznameni_o_zaplaceni: Payment confirmation (potvrzení platby)
- oznameni_o_nezaplaceni: Unpaid notice (upomínka)
- soudni_dokument: Soudní dokumenty (rozsudek, usnesení, předvolání)
- reklama: Newslettery, marketing, slevy
- obchodni_korespondence: Běžná korespondence (dopisy, emaily)
- jine: Ostatní

PŘÍKLADY KLASIFIKACE:

Příklad 1:
Text: "Faktura č. 2024001, IČO: 12345678, DIČ: CZ12345678, Datum zdanitelného plnění: 15.3.2024, Celková částka: 5 000 Kč včetně DPH"
→ TYP: faktura
→ CONFIDENCE: 0.95

Příklad 2:
Text: "Paragon, Tesco, Nákup: 15.3.2024, Celkem: 250 Kč"
→ TYP: stvrzenka
→ CONFIDENCE: 0.90

Příklad 3:
Text: "Výpis z účtu 123456/0100, Zůstatek: 50 000 Kč, Transakce za únor 2024"
→ TYP: bankovni_vypis
→ CONFIDENCE: 0.92

Příklad 4:
Text: "Upomínka č. 1 k faktuře 2024001. Lhůta splatnosti již uplynula. Prosíme o úhradu 5 000 Kč"
→ TYP: vyzva_k_platbe
→ CONFIDENCE: 0.88

Příklad 5:
Text: "Rozsudek Okresního soudu v Praze, sp. zn. 15C 123/2024, ve věci žaloby..."
→ TYP: soudni_dokument
→ CONFIDENCE: 0.98

Příklad 6:
Text: "Objednávka č. PO-2024-156, Dodavatel: ACME s.r.o., Datum objednání: 15.3.2024, Položka: Šroub M6, Množství: 1000 ks, Cena za kus: 2 Kč, Celkem: 2000 Kč, Dodací termín: 30.3.2024"
→ TYP: objednavka
→ CONFIDENCE: 0.93

Příklad 7:
Text: "Dodací list č. DL-8765, Datum expedice: 28.3.2024, Odkaz na objednávku: PO-2024-156, Počet balíků: 2, Hmotnost celkem: 15 kg, Příjemce: Naše firma s.r.o., Dodáno: 1000 ks šroubů M6"
→ TYP: dodaci_list
→ CONFIDENCE: 0.91

DŮLEŽITÉ ROZLIŠENÍ:
- OBJEDNÁVKA obsahuje CENY a termín dodání (my objednáváme)
- DODACÍ LIST často BEZ CEN, má hmotnost/počet balíků (dodavatel dodává)
- FAKTURA obsahuje ceny + DPH + bankovní údaje (dodavatel účtuje)

NYNÍ KLASIFIKUJ TENTO DOKUMENT:

{}

ODPOVĚZ PŘESNĚ V TOMTO FORMÁTU:
TYP: [název kategorie]
CONFIDENCE: [číslo 0.0 až 1.0]
REASONING: [stručné zdůvodnění 1-2 věty]"""

        return prompt.format(text[:3000])  # Increased from 2000 to 3000 chars

    def classify_with_ollama(self, text: str, metadata: Dict = None) -> Dict[str, any]:
        """Classify document using Ollama LLM with improved model"""
        if not self.ollama_config.get("enabled", False):
            return {"success": False, "error": "Ollama not enabled"}

        try:
            url = f"{self.ollama_config.get('base_url')}/api/generate"

            # Use better model (qwen2.5:7b is better than llama3.2:3b)
            model = self.ollama_config.get("model", "qwen2.5:7b")

            # Build improved prompt
            prompt = self._build_improved_prompt(text, metadata)

            # Make request with lower temperature for more consistent results
            response = requests.post(
                url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "temperature": 0.05,  # Lower temperature = more deterministic
                    "stream": False,
                },
                timeout=self.ollama_config.get("timeout", 60),  # Increased timeout
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Ollama API error: {response.status_code}",
                }

            result = response.json()
            classification = self._parse_ollama_response(result.get("response", ""))

            return {
                "success": True,
                "type": classification.get("type"),
                "confidence": classification.get("confidence", 0.5),
                "reasoning": classification.get("reasoning", ""),
            }

        except Exception as e:
            self.logger.error(f"Ollama classification error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _parse_ollama_response(self, response: str) -> Dict[str, any]:
        """Parse Ollama response with better error handling"""
        result = {
            "type": "jine",
            "confidence": 0.5,
            "reasoning": "",
        }

        # Extract type
        type_match = re.search(r"TYP:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
        if type_match:
            extracted_type = type_match.group(1).strip().lower()
            # Clean up common issues
            extracted_type = extracted_type.replace("**", "").replace("*", "")
            result["type"] = extracted_type

        # Extract confidence - FIX: Clamp to 0.0-1.0
        conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", response, re.IGNORECASE)
        if conf_match:
            try:
                confidence = float(conf_match.group(1))
                # FIX: Ensure confidence is between 0.0 and 1.0
                result["confidence"] = max(0.0, min(1.0, confidence))
            except ValueError:
                pass

        # Extract reasoning
        reasoning_match = re.search(r"REASONING:\s*(.+?)(?:\n\n|$)", response, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1).strip()

        return result

    def classify_with_keywords(self, text: str) -> Dict[str, any]:
        """Enhanced keyword matching with better scoring"""
        text_lower = text.lower()
        keywords_config = self.classification_config.get("keywords", {})

        scores = {}
        matches = {}

        # Calculate scores for each type
        for doc_type, keywords in keywords_config.items():
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    matched_keywords.append(keyword)

            if matched_keywords:
                scores[doc_type] = len(matched_keywords)
                matches[doc_type] = matched_keywords

        if not scores:
            return {
                "success": True,
                "type": "jine",
                "confidence": 0.2,
                "method": "keywords",
            }

        # Get best match
        best_type = max(scores, key=scores.get)
        max_score = scores[best_type]

        # Better confidence calculation
        # Give higher confidence if multiple keywords match
        if max_score >= 3:
            confidence = 0.85
        elif max_score == 2:
            confidence = 0.70
        else:
            confidence = 0.50

        return {
            "success": True,
            "type": best_type,
            "confidence": confidence,
            "method": "keywords",
            "scores": scores,
            "matched_keywords": matches.get(best_type, []),
        }

    def classify(self, text: str, metadata: Dict = None) -> Dict[str, any]:
        """
        Classify document using ensemble approach with improved voting
        """
        self.logger.info("Starting improved document classification")

        # Early detection for special cases
        # Check for ads first
        ad_result = self.reklamni_filtr.is_advertisement(text)
        if ad_result.get("is_ad") and ad_result.get("confidence", 0) > 0.8:
            return {
                "type": "reklama",
                "confidence": ad_result.get("confidence", 0.9),
                "method": "reklamni_filtr",
                "metadata": metadata or {},
            }

        # Check for legal documents
        legal_result = self.soudni_filtr.is_legal_document(text)
        if legal_result.get("is_legal") and legal_result.get("confidence", 0) > 0.8:
            return {
                "type": "soudni_dokument",
                "confidence": legal_result.get("confidence", 0.9),
                "method": "soudni_filtr",
                "metadata": metadata or {},
            }

        results = []

        # 1. Keyword matching (fast baseline)
        keyword_result = self.classify_with_keywords(text)
        if keyword_result.get("success"):
            results.append({
                "type": keyword_result.get("type"),
                "confidence": keyword_result.get("confidence", 0),
                "method": "keywords",
                "weight": 1.0,
            })
            self.logger.info(f"Keywords: {keyword_result.get('type')} ({keyword_result.get('confidence'):.2f})")

        # 2. Ollama AI (most accurate)
        if self.ollama_config.get("enabled", False):
            ollama_result = self.classify_with_ollama(text, metadata)
            if ollama_result.get("success"):
                results.append({
                    "type": ollama_result.get("type"),
                    "confidence": ollama_result.get("confidence", 0),
                    "method": "ollama",
                    "reasoning": ollama_result.get("reasoning", ""),
                    "weight": 2.0,  # Higher weight for AI
                })
                self.logger.info(f"AI: {ollama_result.get('type')} ({ollama_result.get('confidence'):.2f}) - {ollama_result.get('reasoning', '')[:50]}")

        # 3. ML model (if available and trained)
        if self.ml_model:
            ml_result = self.ml_model.predict(text)
            if ml_result.get("success"):
                results.append({
                    "type": ml_result.get("type"),
                    "confidence": ml_result.get("confidence", 0),
                    "method": "ml_model",
                    "weight": 1.5,
                })
                self.logger.info(f"ML: {ml_result.get('type')} ({ml_result.get('confidence'):.2f})")

        # Weighted voting ensemble
        if not results:
            return {
                "type": "jine",
                "confidence": 0.3,
                "method": "default",
                "metadata": metadata or {},
            }

        # Calculate weighted scores
        type_scores = {}
        for result in results:
            doc_type = result.get("type", "jine")
            confidence = result.get("confidence", 0)
            weight = result.get("weight", 1.0)

            weighted_score = confidence * weight

            if doc_type not in type_scores:
                type_scores[doc_type] = []
            type_scores[doc_type].append(weighted_score)

        # Get best type by average weighted score
        best_type = None
        best_score = 0

        for doc_type, scores in type_scores.items():
            avg_score = sum(scores) / len(scores)
            if avg_score > best_score:
                best_score = avg_score
                best_type = doc_type

        # Calculate final confidence
        # If multiple methods agree, boost confidence
        agreement_count = len(type_scores.get(best_type, []))
        final_confidence = min(best_score * (1.0 + 0.1 * (agreement_count - 1)), 1.0)

        # WHITELIST KONTROLA - důležité pro objednávky a dodací listy!
        sender = metadata.get("sender", "") if metadata else ""
        whitelist_boost = 0.0
        is_whitelist = False

        if sender and self.blacklist_whitelist:
            is_whitelist = self.blacklist_whitelist.is_whitelisted(sender)

            if is_whitelist:
                # Sender je důvěryhodný → boost confidence
                whitelist_boost = 0.15

                # Přísná kontrola pro objednávky a dodací listy
                if best_type in ["objednavka", "dodaci_list"]:
                    text_lower = text.lower()

                    # Objednávka: zkontroluj číslo objednávky
                    if best_type == "objednavka":
                        has_order_number = any(kw in text_lower for kw in [
                            "objednávka", "objednávk", "číslo obj", "obj. č", "obj.č",
                            "bestellung", "bestellnummer", "purchase order", "po number", "po #"
                        ])
                        if not has_order_number:
                            self.logger.warning(f"⚠️ Whitelist sender but missing order number!")
                            whitelist_boost = 0.05  # Menší boost pokud chybí číslo

                    # Dodací list: zkontroluj číslo DL a hmotnost/balíky
                    elif best_type == "dodaci_list":
                        has_delivery_number = any(kw in text_lower for kw in [
                            "dodací list", "dodací l", "číslo dl", "dl č", "dl.č",
                            "lieferschein", "lieferscheinnummer", "delivery note", "packing slip"
                        ])
                        has_shipping_info = any(kw in text_lower for kw in [
                            "hmotnost", "váha", "kg", "balík", "balíků", "kol",
                            "gewicht", "pakete", "weight", "package"
                        ])
                        if not (has_delivery_number or has_shipping_info):
                            self.logger.warning(f"⚠️ Whitelist sender but missing delivery info!")
                            whitelist_boost = 0.05

                final_confidence = min(final_confidence + whitelist_boost, 1.0)
                self.logger.info(f"✅ Whitelist sender boost: +{whitelist_boost:.0%} → {final_confidence:.2%}")

        self.logger.info(f"Final: {best_type} ({final_confidence:.2f}) from {len(results)} methods")

        return {
            "type": best_type or "jine",
            "confidence": final_confidence,
            "method": "ensemble",
            "metadata": metadata or {},
            "details": {
                "methods_used": [r.get("method") for r in results],
                "agreement_count": agreement_count,
                "whitelist_sender": is_whitelist,
                "whitelist_boost": whitelist_boost,
            }
        }
