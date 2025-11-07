"""
Advertisement detection filter
"""

import logging
import re
from typing import Dict, List


class ReklamniFiltr:
    """Filter for detecting advertisement documents"""

    def __init__(self, config: dict):
        """
        Initialize ReklamniFiltr

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Advertisement keywords (multilingual)
        self.ad_keywords = [
            # Czech
            "sleva", "akce", "výprodej", "zdarma", "limitovaná nabídka",
            "exkluzivní", "bonus", "dárek", "soutěž", "vyhrajte",
            "newsletter", "odhláste", "odhlásit", "odběr",
            # German
            "rabatt", "angebot", "aktion", "kostenlos", "gratis",
            "gewinnspiel", "newsletter", "abmelden",
            # English
            "sale", "discount", "offer", "free", "limited time",
            "exclusive", "bonus", "gift", "contest", "win",
            "unsubscribe", "opt-out",
        ]

        # Structural patterns
        self.ad_patterns = [
            r"([\d]{1,3}%)\s+(sleva|rabatt|discount|off)",
            r"(black|cyber)\s+friday",
            r"flash\s+sale",
            r"limited\s+(time|offer)",
            r"act\s+now",
            r"don['\']t\s+miss",
            r"exkluzivn[íě]\s+nabídka",
        ]

    def is_advertisement(self, text: str) -> Dict[str, any]:
        """
        Check if document is an advertisement

        Args:
            text: Document text

        Returns:
            Dictionary with detection result
        """
        text_lower = text.lower()

        # Count keyword matches
        keyword_matches = sum(1 for keyword in self.ad_keywords if keyword in text_lower)

        # Count pattern matches
        pattern_matches = sum(
            1 for pattern in self.ad_patterns
            if re.search(pattern, text_lower)
        )

        # Calculate confidence
        total_score = keyword_matches * 0.6 + pattern_matches * 0.4
        max_score = len(self.ad_keywords) * 0.6 + len(self.ad_patterns) * 0.4

        # Normalize confidence
        confidence = min(total_score / 5.0, 1.0)  # Threshold at 5 matches

        is_ad = confidence > 0.5

        self.logger.debug(
            f"Ad detection: {is_ad} (confidence: {confidence:.2%}, "
            f"keywords: {keyword_matches}, patterns: {pattern_matches})"
        )

        return {
            "is_ad": is_ad,
            "confidence": confidence,
            "keyword_matches": keyword_matches,
            "pattern_matches": pattern_matches,
        }

    def extract_ad_features(self, text: str) -> Dict[str, any]:
        """
        Extract advertisement features from text

        Args:
            text: Document text

        Returns:
            Dictionary with extracted features
        """
        text_lower = text.lower()

        features = {
            "has_unsubscribe": any(
                word in text_lower
                for word in ["unsubscribe", "odhlásit", "abmelden"]
            ),
            "has_discount": any(
                word in text_lower
                for word in ["sleva", "rabatt", "discount", "sale"]
            ),
            "has_call_to_action": any(
                word in text_lower
                for word in ["klikněte", "click", "klicken", "objednat", "order"]
            ),
        }

        # Extract discount percentage
        discount_match = re.search(r"(\d{1,3})%", text)
        if discount_match:
            features["discount_percentage"] = int(discount_match.group(1))

        return features
