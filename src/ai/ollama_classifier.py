#!/usr/bin/env python3
"""
Ollama Email Classifier - Final Arbiter
Používá llama3.3:70b pro finální klasifikaci emailů
"""
import logging
import json
import subprocess
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class OllamaEmailClassifier:
    """
    Finální klasifikátor používající Ollama (llama3.3:70b)

    Tento klasifikátor má poslední slovo při rozhodování o typu dokumentu/emailu.
    """

    def __init__(self, model: str = "llama3.3:70b"):
        self.model = model

        # Kategorie dokumentů (stejné jako v hlavním klasifikátoru)
        self.categories = [
            "faktura",
            "objednavka",
            "dodaci_list",
            "stvrzenka",
            "bankovni_vypis",
            "smlouva",
            "oznameni_o_zaplaceni",
            "oznameni_o_nezaplaceni",
            "vyzva_k_platbe",
            "upominka",
            "soudni_dokument",
            "obchodni_korespondence",
            "reklama",
            "jine"
        ]

    def classify_email(self, subject: str, body: str, sender: str = "") -> Dict:
        """
        Klasifikuje email pomocí Ollama LLM

        Args:
            subject: Předmět emailu
            body: Tělo emailu (prvních 2000 znaků)
            sender: Odesílatel (optional)

        Returns:
            Dict s 'document_type' a 'confidence'
        """
        # Ořízni text, aby nebyl moc dlouhý
        body_preview = body[:2000] if len(body) > 2000 else body

        # Vytvoř prompt pro LLM
        prompt = self._create_classification_prompt(subject, body_preview, sender)

        try:
            # Zavolej Ollama
            result = self._call_ollama(prompt)

            # Parsuj odpověď
            classification = self._parse_response(result)

            logger.info(f"Ollama classified as: {classification['document_type']} ({classification['confidence']:.2f})")

            return classification

        except Exception as e:
            logger.error(f"Ollama classification failed: {e}")
            # Fallback
            return {
                'document_type': 'jine',
                'confidence': 0.1,
                'method': 'ollama_failed'
            }

    def _create_classification_prompt(self, subject: str, body: str, sender: str) -> str:
        """Vytvoří prompt pro klasifikaci"""

        categories_list = ", ".join(self.categories)

        prompt = f"""Analyzuj tento email a urči jeho typ. Odpověz POUZE ve formátu JSON bez dalšího textu.

DOSTUPNÉ KATEGORIE:
{categories_list}

EMAIL:
Od: {sender}
Předmět: {subject}
Tělo:
{body}

PRAVIDLA KLASIFIKACE:
- faktura: obsahuje číslo faktury, částku, datum splatnosti, DPH
- objednavka: obsahuje číslo objednávky, položky k dodání
- dodaci_list: potvrzení o dodání zboží/služeb
- stvrzenka: potvrzení o platbě (bez faktury)
- bankovni_vypis: výpis z bankovního účtu, transakce
- smlouva: smluvní podmínky, ujednání
- oznameni_o_zaplaceni: info že platba byla přijata
- oznameni_o_nezaplaceni: info že platba nebyla přijata
- vyzva_k_platbe: žádost o zaplacení (bez upomínky)
- upominka: urgence po splatnosti
- soudni_dokument: předvolání, rozsudek, soudní korespondence
- obchodni_korespondence: běžná business komunikace
- reklama: marketing, newsletter, nabídky
- jine: ostatní

ODPOVĚZ POUZE TÍMTO JSON (nic víc):
{{"document_type": "kategorie", "confidence": 0.95, "reasoning": "stručné zdůvodnění"}}"""

        return prompt

    def _call_ollama(self, prompt: str) -> str:
        """Zavolá Ollama API"""

        # Používáme subprocess pro volání ollama
        cmd = [
            "ollama",
            "run",
            self.model,
            prompt
        ]

        logger.debug(f"Calling Ollama with model: {self.model}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # 60 sekund timeout
        )

        if result.returncode != 0:
            raise Exception(f"Ollama failed: {result.stderr}")

        return result.stdout.strip()

    def _parse_response(self, response: str) -> Dict:
        """Parsuje JSON odpověď z LLM"""

        # LLM někdy přidá markdown ```json
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)

            doc_type = data.get('document_type', 'jine')
            confidence = float(data.get('confidence', 0.5))

            # Validace kategorie
            if doc_type not in self.categories:
                logger.warning(f"Invalid category from LLM: {doc_type}, using 'jine'")
                doc_type = 'jine'
                confidence = 0.3

            return {
                'document_type': doc_type,
                'confidence': confidence,
                'method': 'ollama_llm',
                'reasoning': data.get('reasoning', '')
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Response was: {response}")

            # Fallback - pokus se najít kategorii v textu
            for category in self.categories:
                if category in cleaned.lower():
                    return {
                        'document_type': category,
                        'confidence': 0.6,
                        'method': 'ollama_fallback'
                    }

            return {
                'document_type': 'jine',
                'confidence': 0.1,
                'method': 'ollama_parse_failed'
            }


def test_classifier():
    """Test Ollama classifieru"""

    classifier = OllamaEmailClassifier()

    # Test email 1 - faktura
    result1 = classifier.classify_email(
        subject="Faktura č. 2024001",
        body="""
        Dobrý den,

        zasíláme Vám fakturu č. 2024001 za služby.
        Částka k úhradě: 5000 Kč včetně DPH
        Datum splatnosti: 31.12.2024
        Variabilní symbol: 2024001

        S pozdravem
        """,
        sender="fakturace@firma.cz"
    )
    print(f"\nTest 1 (Faktura): {result1}")

    # Test email 2 - reklama
    result2 = classifier.classify_email(
        subject="🎁 Slevy až 50% - Black Friday!",
        body="""
        Nezmeškejte naši Black Friday akci!

        Slevy až 50% na všechny produkty!
        Akce platí pouze do konce týdne.

        Nakupujte nyní: www.eshop.cz
        """,
        sender="marketing@eshop.cz"
    )
    print(f"\nTest 2 (Reklama): {result2}")

    # Test email 3 - oznameni o zaplaceni
    result3 = classifier.classify_email(
        subject="Platba přijata",
        body="""
        Vaše platba byla úspěšně přijata.

        Částka: 2500 Kč
        Variabilní symbol: 123456
        Datum: 15.11.2024
        """,
        sender="payments@bank.cz"
    )
    print(f"\nTest 3 (Oznámení o zaplacení): {result3}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test_classifier()
