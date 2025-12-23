"""
Legal document detection filter
"""

import logging
import re
from typing import Dict, List


class SoudniFiltr:
    """Filter for detecting legal/court documents"""

    def __init__(self, config: dict):
        """
        Initialize SoudniFiltr

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Legal keywords (Czech/German)
        self.legal_keywords = [
            # Czech
            "soud", "soudní", "justice", "rozsudek", "usnesení",
            "trestní", "občanský", "obžaloba", "žaloba", "žalobce",
            "žalovaný", "obviněný", "státní zástupce", "prokurátor",
            "policejní protokol", "vyšetřování",
            # German
            "gericht", "urteil", "beschluss", "klage", "kläger",
            "beklagter", "staatsanwalt", "polizei",
        ]

        # Legal reference patterns
        self.legal_patterns = [
            r"\§\s*\d+",  # Paragraph references (§123)
            r"\d+\s*[A-Z]+\s*\d+/\d{4}",  # Case numbers (12K 123/2023)
            r"[A-Z]{2,4}\s+\d+/\d{4}",  # Case references (KRPA 123/2023)
            r"JUDr\.",  # Legal title
            r"trestní\s+řízení",
            r"trestní\s+zákon",
            r"strafrecht",
            r"zivilrecht",
        ]

        # Court identifiers
        self.court_identifiers = [
            "okresní soud",
            "krajský soud",
            "vrchní soud",
            "nejvyšší soud",
            "ústavní soud",
            "amtsgericht",
            "landgericht",
            "oberlandesgericht",
        ]

    def is_legal_document(self, text: str) -> Dict[str, any]:
        """
        Check if document is a legal/court document

        Args:
            text: Document text

        Returns:
            Dictionary with detection result
        """
        text_lower = text.lower()

        # Count keyword matches
        keyword_matches = sum(
            1 for keyword in self.legal_keywords
            if keyword in text_lower
        )

        # Count pattern matches
        pattern_matches = sum(
            1 for pattern in self.legal_patterns
            if re.search(pattern, text, re.IGNORECASE)
        )

        # Check for court identifiers
        court_matches = sum(
            1 for court in self.court_identifiers
            if court in text_lower
        )

        # Calculate confidence
        # Court identifiers have higher weight
        total_score = keyword_matches * 0.4 + pattern_matches * 0.3 + court_matches * 0.3
        max_score = len(self.legal_keywords) * 0.4 + len(self.legal_patterns) * 0.3 + len(self.court_identifiers) * 0.3

        # Normalize confidence
        confidence = min(total_score / 3.0, 1.0)  # Threshold at 3 matches

        is_legal = confidence > 0.5 or court_matches > 0  # Court mention = high probability

        self.logger.debug(
            f"Legal detection: {is_legal} (confidence: {confidence:.2%}, "
            f"keywords: {keyword_matches}, patterns: {pattern_matches}, courts: {court_matches})"
        )

        return {
            "is_legal": is_legal,
            "confidence": confidence,
            "keyword_matches": keyword_matches,
            "pattern_matches": pattern_matches,
            "court_matches": court_matches,
        }

    def extract_legal_features(self, text: str) -> Dict[str, any]:
        """
        Extract legal document features

        Args:
            text: Document text

        Returns:
            Dictionary with extracted features
        """
        features = {}

        # Extract case number
        case_match = re.search(
            r"([A-Z]{2,4}\s+\d+/\d{4}|\d+\s*[A-Z]+\s*\d+/\d{4})",
            text,
        )
        if case_match:
            features["case_number"] = case_match.group(1)

        # Extract paragraph references
        paragraph_refs = re.findall(r"\§\s*\d+", text)
        if paragraph_refs:
            features["paragraph_references"] = paragraph_refs

        # Detect document type
        if "rozsudek" in text.lower() or "urteil" in text.lower():
            features["document_subtype"] = "rozsudek"
        elif "usnesení" in text.lower() or "beschluss" in text.lower():
            features["document_subtype"] = "usneseni"
        elif "protokol" in text.lower():
            features["document_subtype"] = "protokol"
        elif "předvolání" in text.lower() or "vorladung" in text.lower():
            features["document_subtype"] = "predvolani"

        return features
