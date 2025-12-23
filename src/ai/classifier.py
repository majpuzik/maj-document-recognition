"""
AI-based document classification using Ollama and ML models
"""

import logging
import re
from typing import Dict, List, Optional

import requests

from .ml_model import MLModel
from .reklamni_filtr import ReklamniFiltr
from .soudni_filtr import SoudniFiltr


class AIClassifier:
    """AI-powered document classifier"""

    def __init__(self, config: dict, db_manager=None):
        """
        Initialize AIClassifier

        Args:
            config: Application configuration dictionary
            db_manager: Database manager instance
        """
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

    def classify_with_ollama(self, text: str, metadata: Dict = None) -> Dict[str, any]:
        """
        Classify document using Ollama LLM

        Args:
            text: Document text
            metadata: Additional metadata

        Returns:
            Classification result dictionary
        """
        if not self.ollama_config.get("enabled", False):
            return {"success": False, "error": "Ollama not enabled"}

        try:
            url = f"{self.ollama_config.get('base_url')}/api/generate"

            # Build prompt
            prompt = self._build_ollama_prompt(text, metadata)

            # Make request
            response = requests.post(
                url,
                json={
                    "model": self.ollama_config.get("model", "llama3.2:3b"),
                    "prompt": prompt,
                    "temperature": self.ollama_config.get("temperature", 0.1),
                    "stream": False,
                },
                timeout=self.ollama_config.get("timeout", 30),
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

    def _build_ollama_prompt(self, text: str, metadata: Dict = None) -> str:
        """Build prompt for Ollama"""
        types = self.classification_config.get("types", [])
        types_str = ", ".join(types)

        prompt = f"""Analyzuj následující text dokumentu a urči jeho typ.

Možné typy dokumentů: {types_str}

Text dokumentu:
{text[:2000]}  # Limit to 2000 chars

Odpověz ve formátu:
TYP: [název typu]
CONFIDENCE: [0.0-1.0]
REASONING: [krátké zdůvodnění]
"""
        return prompt

    def _parse_ollama_response(self, response: str) -> Dict[str, any]:
        """Parse Ollama response"""
        result = {
            "type": "jine",
            "confidence": 0.5,
            "reasoning": "",
        }

        # Extract type
        type_match = re.search(r"TYP:\s*(.+)", response, re.IGNORECASE)
        if type_match:
            result["type"] = type_match.group(1).strip().lower()

        # Extract confidence
        conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", response, re.IGNORECASE)
        if conf_match:
            try:
                result["confidence"] = float(conf_match.group(1))
            except ValueError:
                pass

        # Extract reasoning
        reasoning_match = re.search(r"REASONING:\s*(.+)", response, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1).strip()

        return result

    def classify_with_keywords(self, text: str) -> Dict[str, any]:
        """
        Classify document using keyword matching

        Args:
            text: Document text

        Returns:
            Classification result dictionary
        """
        text_lower = text.lower()
        keywords_config = self.classification_config.get("keywords", {})

        scores = {}

        # Calculate scores for each type
        for doc_type, keywords in keywords_config.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text_lower)
            if score > 0:
                scores[doc_type] = score

        if not scores:
            return {
                "success": True,
                "type": "jine",
                "confidence": 0.3,
                "method": "keywords",
            }

        # Get best match
        best_type = max(scores, key=scores.get)
        max_score = scores[best_type]

        # Calculate confidence (normalize by number of keywords)
        total_keywords = len(keywords_config.get(best_type, []))
        confidence = min(max_score / total_keywords, 1.0) if total_keywords > 0 else 0.3

        return {
            "success": True,
            "type": best_type,
            "confidence": confidence,
            "method": "keywords",
            "scores": scores,
        }

    def classify(self, text: str, metadata: Dict = None) -> Dict[str, any]:
        """
        Classify document using all available methods

        Args:
            text: Document text
            metadata: Additional metadata

        Returns:
            Classification result dictionary
        """
        self.logger.info("Starting document classification")

        results = []

        # Check for ads
        ad_result = self.reklamni_filtr.is_advertisement(text)
        if ad_result.get("is_ad"):
            return {
                "type": "reklama",
                "confidence": ad_result.get("confidence", 0.9),
                "method": "reklamni_filtr",
                "metadata": ad_result,
            }

        # Check for legal documents
        legal_result = self.soudni_filtr.is_legal_document(text)
        if legal_result.get("is_legal"):
            return {
                "type": "soudni_dokument",
                "confidence": legal_result.get("confidence", 0.9),
                "method": "soudni_filtr",
                "metadata": legal_result,
            }

        # Try ML model
        if self.ml_model:
            ml_result = self.ml_model.predict(text)
            if ml_result.get("success"):
                results.append({
                    "type": ml_result.get("type"),
                    "confidence": ml_result.get("confidence", 0),
                    "method": "ml_model",
                })

        # Try Ollama
        if self.ollama_config.get("enabled", False):
            ollama_result = self.classify_with_ollama(text, metadata)
            if ollama_result.get("success"):
                results.append({
                    "type": ollama_result.get("type"),
                    "confidence": ollama_result.get("confidence", 0),
                    "method": "ollama",
                    "reasoning": ollama_result.get("reasoning", ""),
                })

        # Try keyword matching
        keyword_result = self.classify_with_keywords(text)
        if keyword_result.get("success"):
            results.append({
                "type": keyword_result.get("type"),
                "confidence": keyword_result.get("confidence", 0),
                "method": "keywords",
            })

        # Combine results (weighted voting)
        if not results:
            return {
                "type": "jine",
                "confidence": 0.1,
                "method": "fallback",
            }

        # Weight by method confidence and reliability
        weights = {
            "ml_model": 1.5,
            "ollama": 1.3,
            "keywords": 1.0,
        }

        type_scores = {}
        for result in results:
            doc_type = result["type"]
            weight = weights.get(result["method"], 1.0)
            score = result["confidence"] * weight

            if doc_type not in type_scores:
                type_scores[doc_type] = []
            type_scores[doc_type].append(score)

        # Calculate final scores (average)
        final_scores = {
            doc_type: sum(scores) / len(scores)
            for doc_type, scores in type_scores.items()
        }

        # Get best classification
        best_type = max(final_scores, key=final_scores.get)
        best_confidence = final_scores[best_type]

        self.logger.info(f"Classification result: {best_type} (confidence: {best_confidence:.2%})")

        return {
            "type": best_type,
            "confidence": best_confidence,
            "method": "ensemble",
            "individual_results": results,
            "metadata": metadata or {},
        }
