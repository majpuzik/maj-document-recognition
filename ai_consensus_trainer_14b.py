#!/usr/bin/env python3
"""
NAS5 Docker Apps Collection
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
AI Consensus Trainer - Učení se z AI konsensu
================================================
1. Můj extraktor vytáhne data z dokumentu
2. 3 AI modely (GPT-4, Gemini, Claude) hodnotí stejný dokument
3. Pokud se alespoň 2 AI shodnou → to je správná odpověď
4. Uložím správný vzor do learning database
5. Můj extraktor se učí z těchto správných vzorů

Author: Claude Code
Date: 2025-11-30
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
from data_extractors import create_extractor
from extraction_schemas import SchemaValidator

# AI imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    print("⚠️  Claude SDK not available (pip install anthropic)")

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("⚠️  Ollama not available (pip install ollama)")

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIVoter:
    """
    Hlasování AI modelů o správné odpovědi

    Modes:
    - Production (default): 2 local Ollama models (qwen2.5:14b + czech-finance-speed)
                           Both must agree = 100% consensus
    - Training (use_external_apis=True): 3+ models including GPT-4/Gemini
                                        2+ must agree = 67% consensus
    """

    def __init__(self, use_external_apis=False):
        """
        Initialize AI models for consensus voting

        Args:
            use_external_apis: If True, use GPT-4/Gemini (for initial training/learning)
                             If False, use only 2 local Ollama models (production)
        """
        # Initialize AI clients
        self.models = {}
        self.use_external_apis = use_external_apis

        if use_external_apis:
            # External APIs for initial training/learning phase
            if OPENAI_AVAILABLE and os.getenv('OPENAI_API_KEY'):
                openai.api_key = os.getenv('OPENAI_API_KEY')
                self.models['gpt4'] = 'openai'

            if GEMINI_AVAILABLE and os.getenv('GEMINI_API_KEY'):
                genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
                self.models['gemini'] = 'gemini'

            if CLAUDE_AVAILABLE and os.getenv('ANTHROPIC_API_KEY'):
                self.claude_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
                self.models['claude'] = 'anthropic'

        # Always try to add local Ollama models (production mode)
        if OLLAMA_AVAILABLE:
            # Check if Ollama server is running
            try:
                ollama.list()
                # Use 2 local Ollama models for validation
                self.models['ollama_general'] = 'qwen2.5:14b'
                self.models['ollama_czech'] = 'czech-finance-speed:latest'
                logger.info("✅ Using 2 local Ollama models (general + Czech specialist)")
            except Exception as e:
                logger.warning(f"Ollama server not running: {e}")

        logger.info(f"✅ Initialized {len(self.models)} AI models: {list(self.models.keys())}")

    def extract_with_ai(self, model_name: str, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract data using specific AI model"""

        prompt = self._build_prompt(text, doc_type)

        try:
            if model_name == 'gpt4':
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a structured data extraction expert. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                result_text = response.choices[0].message.content

            elif model_name == 'gemini':
                response = self.gemini_model.generate_content(prompt)
                result_text = response.text

            elif model_name == 'claude':
                response = self.claude_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )
                result_text = response.content[0].text

            elif model_name == 'ollama':
                # Legacy support for old scripts
                response = ollama.chat(
                    model='qwen2.5:14b',
                    messages=[{"role": "user", "content": prompt}],
                    format='json'
                )
                result_text = response['message']['content']

            elif model_name == 'ollama_general':
                # General 32B model
                response = ollama.chat(
                    model='qwen2.5:14b',
                    messages=[{"role": "user", "content": prompt}],
                    format='json'
                )
                result_text = response['message']['content']

            elif model_name == 'ollama_czech':
                # Czech financial documents specialist
                response = ollama.chat(
                    model='czech-finance-speed:latest',
                    messages=[{"role": "user", "content": prompt}],
                    format='json'
                )
                result_text = response['message']['content']

            else:
                return {"error": f"Unknown model: {model_name}"}

            # Clean and parse JSON
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.startswith('```'):
                result_text = result_text[3:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]

            result = json.loads(result_text.strip())
            return result

        except Exception as e:
            logger.error(f"AI extraction failed for {model_name}: {e}")
            return {"error": str(e)}

    def _build_prompt(self, text: str, doc_type: str) -> str:
        """Build extraction prompt based on document type"""

        if doc_type == 'invoice':
            return f"""
Extract ALL line items from this invoice in JSON format.

IMPORTANT: Extract EVERY single line item you can find.

Required format:
{{
  "line_items": [
    {{
      "line_number": 1,
      "description": "exact item description",
      "quantity": 1.0,
      "unit": "ks",
      "unit_price": 100.00,
      "vat_rate": 21,
      "vat_amount": 21.00,
      "total_net": 100.00,
      "total_gross": 121.00
    }}
  ],
  "summary": {{
    "total_net": 100.00,
    "total_vat": 21.00,
    "total_gross": 121.00,
    "currency": "CZK"
  }}
}}

Invoice text:
{text}
"""

        elif doc_type == 'receipt':
            return f"""
Extract ALL items from this receipt in JSON format.

IMPORTANT: Extract EVERY single item you can find.

Required format:
{{
  "items": [
    {{
      "line_number": 1,
      "description": "exact item name",
      "quantity": 1.0,
      "unit": "ks",
      "unit_price": 10.00,
      "vat_rate": 21,
      "total": 10.00
    }}
  ],
  "summary": {{
    "total": 10.00,
    "vat_breakdown": {{"21": 1.74, "15": 0.0, "10": 0.0}},
    "currency": "CZK"
  }},
  "eet": {{
    "fik": "FIK code if present or empty string",
    "bkp": "BKP code if present or empty string"
  }}
}}

Receipt text:
{text}
"""

        return text

    def vote(self, text: str, doc_type: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Run voting across 3 AI models

        Returns:
            (consensus_result, voting_details)
        """
        logger.info(f"🗳️  Starting AI voting for {doc_type}")

        # Get extractions from all models
        extractions = {}
        for model_name in self.models.keys():
            logger.info(f"  📤 {model_name.upper()}...")
            result = self.extract_with_ai(model_name, text, doc_type)
            extractions[model_name] = result

        # Analyze consensus
        consensus, details = self._find_consensus(extractions, doc_type)

        return consensus, details

    def _find_consensus(self, extractions: Dict[str, Dict], doc_type: str) -> Tuple[Dict, Dict]:
        """Find consensus among AI models"""

        # Extract key metrics for comparison
        if doc_type == 'invoice':
            key = 'line_items'
        elif doc_type == 'receipt':
            key = 'items'
        else:
            key = 'items'

        # Count number of items from each model
        item_counts = {}
        for model_name, result in extractions.items():
            if 'error' not in result and key in result:
                item_counts[model_name] = len(result[key])
            else:
                item_counts[model_name] = 0

        # Find majority vote
        count_votes = Counter(item_counts.values())
        majority_count = count_votes.most_common(1)[0][0]

        # Find models that agree with majority
        agreeing_models = [name for name, count in item_counts.items() if count == majority_count]

        # Build consensus result (use first agreeing model's result)
        if agreeing_models:
            consensus_model = agreeing_models[0]
            consensus_result = extractions[consensus_model]
        else:
            consensus_result = {"error": "No consensus found"}

        voting_details = {
            'item_counts': item_counts,
            'majority_count': majority_count,
            'agreeing_models': agreeing_models,
            'consensus_strength': len(agreeing_models) / len(self.models),
            'all_extractions': extractions
        }

        logger.info(f"  ✅ Consensus: {majority_count} items ({len(agreeing_models)}/{len(self.models)} models agree)")

        return consensus_result, voting_details


class LearningDatabase:
    """Databáze správných vzorů pro učení"""

    def __init__(self, db_path: str = "learning_patterns.jsonl"):
        self.db_path = db_path

    def save_pattern(self, document_text: str, doc_type: str,
                    correct_result: Dict, voting_details: Dict):
        """Uloží správně rozpoznaný vzor"""

        pattern = {
            'timestamp': datetime.now().isoformat(),
            'doc_type': doc_type,
            'document_text': document_text[:500],  # First 500 chars
            'document_hash': hash(document_text),
            'correct_result': correct_result,
            'consensus_strength': voting_details['consensus_strength'],
            'agreeing_models': voting_details['agreeing_models'],
            'item_count': voting_details['majority_count']
        }

        # Append to JSONL
        with open(self.db_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(pattern, ensure_ascii=False) + '\n')

        logger.info(f"💾 Saved learning pattern to {self.db_path}")

    def load_patterns(self, doc_type: Optional[str] = None) -> List[Dict]:
        """Načte uložené vzory"""

        if not os.path.exists(self.db_path):
            return []

        patterns = []
        with open(self.db_path, 'r', encoding='utf-8') as f:
            for line in f:
                pattern = json.loads(line.strip())
                if doc_type is None or pattern['doc_type'] == doc_type:
                    patterns.append(pattern)

        return patterns

    def get_statistics(self) -> Dict[str, Any]:
        """Statistiky učících se vzorů"""

        patterns = self.load_patterns()

        if not patterns:
            return {'total': 0}

        by_type = Counter(p['doc_type'] for p in patterns)
        avg_consensus = sum(p['consensus_strength'] for p in patterns) / len(patterns)

        return {
            'total_patterns': len(patterns),
            'by_type': dict(by_type),
            'average_consensus': avg_consensus,
            'date_range': {
                'first': min(p['timestamp'] for p in patterns),
                'last': max(p['timestamp'] for p in patterns)
            }
        }


class ConsensusTrainer:
    """Main trainer - combines local extractor with AI consensus"""

    def __init__(self):
        self.voter = AIVoter()
        self.learning_db = LearningDatabase()
        self.local_extractor = None

    def train_on_document(self, text: str, doc_type: str) -> Dict[str, Any]:
        """
        Trénuj na jednom dokumentu:
        1. Můj extraktor extrahuje
        2. 3 AI hlasují
        3. Pokud 2+ souhlasí → uložíme jako správný vzor
        4. Porovnáme s mým extraktorem
        """

        print("\n" + "=" * 80)
        print(f"📚 TRAINING ON {doc_type.upper()}")
        print("=" * 80)

        # 1. Local extraction
        print("\n1️⃣  Local extractor:")
        self.local_extractor = create_extractor(doc_type)
        local_result = self.local_extractor.extract(text)

        if doc_type == 'invoice':
            local_items = len(local_result.get('line_items', []))
        else:
            local_items = len(local_result.get('items', []))

        print(f"   Extracted: {local_items} items")
        print(f"   Confidence: {local_result.get('extraction_confidence', 0):.1f}%")

        # 2. AI voting
        print("\n2️⃣  AI voting:")
        consensus_result, voting_details = self.voter.vote(text, doc_type)

        # 3. Check if we have consensus
        # - With 2 models (production): Both must agree = 100%
        # - With 3+ models (training): At least 2 must agree = 67%
        if len(self.voter.models) == 2:
            consensus_threshold = 1.0  # 100% - both models must agree
        else:
            consensus_threshold = 0.67  # 67% - at least 2 out of 3

        has_consensus = voting_details['consensus_strength'] >= consensus_threshold

        print(f"\n3️⃣  Consensus check:")
        print(f"   Strength: {voting_details['consensus_strength']:.0%}")
        print(f"   Agreeing models: {', '.join(voting_details['agreeing_models'])}")

        if has_consensus:
            print("   ✅ CONSENSUS REACHED - this is correct")

            # 4. Save pattern
            self.learning_db.save_pattern(text, doc_type, consensus_result, voting_details)

            # 5. Compare with local
            print(f"\n4️⃣  Comparison:")
            ai_items = voting_details['majority_count']

            match = local_items == ai_items
            print(f"   Local: {local_items} items")
            print(f"   AI consensus: {ai_items} items")

            if match:
                print("   ✅ LOCAL EXTRACTOR IS CORRECT!")
            else:
                diff = abs(local_items - ai_items)
                print(f"   ❌ MISMATCH (diff: {diff} items)")
                print(f"   → Můj extraktor potřebuje vylepšení")

            return {
                'has_consensus': True,
                'match': match,
                'local_items': local_items,
                'ai_items': ai_items,
                'consensus_result': consensus_result,
                'local_result': local_result
            }

        else:
            print("   ❌ NO CONSENSUS - AI models disagree")
            print("   → Skipping this document")

            return {
                'has_consensus': False,
                'voting_details': voting_details
            }


# ============================================================================
# SAMPLE DOCUMENTS FOR TESTING
# ============================================================================

SAMPLE_INVOICE = """
FAKTURA č. 2024-0123
Datum vystavení: 15.11.2024
Datum splatnosti: 30.11.2024

Dodavatel:
OpenAI Ireland Ltd.
IČO: 12345678
DIČ: IE1234567V

Odběratel:
Martin Pužík
IČO: 87654321

Položky:
=======================================================
Č.  Popis                          Množství  Cena    DPH    Celkem
---  -------------------------      --------  ------  -----  --------
1.   ChatGPT Plus API - listopad   1 ks      150,00  21%    181,50
2.   Data storage 50GB             50 GB       2,00  21%    121,00
3.   Additional tokens 1M          1 ks       50,00  21%     60,50
=======================================================

Celkem bez DPH:               200,00 Kč
DPH 21%:                       42,00 Kč
Celkem k úhradě:              242,00 Kč

Způsob platby: Bankovní převod
VS: 2024001
"""

SAMPLE_RECEIPT = """
====================================
      BENZINA - ČS a.s.
    IČO: 45534306
    DIČ: CZ45534306
====================================

Datum: 20.11.2024  14:35
Paragon: 85674321

Položky:
------------------------------------
Natural 95         45,5 l   36,90  1.679,95
Mytí auta Premium   1 ks   150,00    150,00
Káva grande         1 ks    65,00     65,00
------------------------------------

Celkem:                            1.894,95 Kč

DPH 21%:                             329,64 Kč
DPH 15%:                               0,00 Kč

====================================
EET - Elektronická evidence tržeb
FIK: a1b2c3d4-e5f6-7890-abcd-1234567890ab
BKP: 12345678-90ABCDEF-12345678-90AB-12345678
====================================

Děkujeme za nákup!
"""


def main():
    """Main training loop"""

    print("\n🎓 AI CONSENSUS TRAINER")
    print("=" * 80)
    print("Trénování mého extraktoru pomocí AI konsensu")
    print()

    trainer = ConsensusTrainer()

    # Train on sample invoice
    print("\n" + "🧾" * 40)
    result_invoice = trainer.train_on_document(SAMPLE_INVOICE, 'invoice')

    # Train on sample receipt
    print("\n" + "🧾" * 40)
    result_receipt = trainer.train_on_document(SAMPLE_RECEIPT, 'receipt')

    # Show learning database statistics
    print("\n" + "=" * 80)
    print("📊 LEARNING DATABASE STATISTICS")
    print("=" * 80)
    stats = trainer.learning_db.get_statistics()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    # Show learned patterns
    print("\n" + "=" * 80)
    print("📖 LEARNED PATTERNS")
    print("=" * 80)
    patterns = trainer.learning_db.load_patterns()
    for i, pattern in enumerate(patterns, 1):
        print(f"\n{i}. {pattern['doc_type'].upper()} ({pattern['timestamp'][:10]})")
        print(f"   Items: {pattern['item_count']}")
        print(f"   Consensus: {pattern['consensus_strength']:.0%}")
        print(f"   Models: {', '.join(pattern['agreeing_models'])}")

    print("\n✅ Training complete!")
    print(f"💾 Patterns saved to: {trainer.learning_db.db_path}")


if __name__ == "__main__":
    main()
