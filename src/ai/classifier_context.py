#!/usr/bin/env python3
"""
** The project "maj-document-recognition-v2/src" is a document matching system that automates the pr
"""

"""
Context-Aware AI Classifier
Learns from previous classifications and improves over time
"""

import logging
import json
from typing import Dict, List
from collections import Counter, defaultdict
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class ContextAwareClassifier:
    """
    AI Classifier with context learning

    Features:
    - Learns from sender patterns
    - Tracks classification history
    - Suggests corrections for low confidence
    - Adaptive confidence thresholds per type
    """

    def __init__(self, config: dict, db_manager):
        self.config = config
        self.db = db_manager
        self.cache = {}
        self._load_context()

    def _load_context(self):
        """Load historical context from database"""
        try:
            # Get sender patterns
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            # Sender → Type mapping
            cursor.execute("""
                SELECT
                    json_extract(metadata, '$.sender') as sender,
                    document_type,
                    COUNT(*) as count
                FROM documents
                WHERE json_extract(metadata, '$.sender') IS NOT NULL
                GROUP BY sender, document_type
                HAVING count >= 3
            """)

            self.sender_patterns = defaultdict(Counter)
            for row in cursor.fetchall():
                sender, doc_type, count = row
                self.sender_patterns[sender][doc_type] = count

            # Subject patterns
            cursor.execute("""
                SELECT
                    json_extract(metadata, '$.subject') as subject,
                    document_type,
                    COUNT(*) as count
                FROM documents
                WHERE json_extract(metadata, '$.subject') IS NOT NULL
                GROUP BY subject, document_type
                HAVING count >= 2
            """)

            self.subject_patterns = defaultdict(Counter)
            for row in cursor.fetchall():
                subject, doc_type, count = row
                if subject:
                    self.subject_patterns[subject][doc_type] = count

            # Type-specific confidence thresholds
            cursor.execute("""
                SELECT
                    document_type,
                    AVG(ai_confidence) as avg_conf,
                    MIN(ai_confidence) as min_conf,
                    COUNT(*) as count
                FROM documents
                GROUP BY document_type
                HAVING count >= 5
            """)

            self.type_thresholds = {}
            for row in cursor.fetchall():
                doc_type, avg_conf, min_conf, count = row
                # Set threshold at avg - 10%
                self.type_thresholds[doc_type] = max(avg_conf - 0.1, 0.5)

            conn.close()

            logger.info(f"📚 Loaded context: {len(self.sender_patterns)} senders, {len(self.subject_patterns)} subjects")

        except Exception as e:
            logger.warning(f"Could not load context: {e}")
            self.sender_patterns = defaultdict(Counter)
            self.subject_patterns = defaultdict(Counter)
            self.type_thresholds = {}

    def classify_with_context(self, text: str, metadata: Dict, base_classification: Dict) -> Dict:
        """
        Enhance classification with context

        Args:
            text: OCR text
            metadata: Document metadata (sender, subject, etc.)
            base_classification: Initial classification from AI

        Returns:
            Enhanced classification with context boost
        """
        doc_type = base_classification.get('type')
        confidence = base_classification.get('confidence', 0)

        # Context boosts
        sender_boost = self._check_sender_context(metadata.get('sender'), doc_type)
        subject_boost = self._check_subject_context(metadata.get('subject'), doc_type)
        threshold_check = self._check_confidence_threshold(doc_type, confidence)

        # Apply boosts
        total_boost = sender_boost + subject_boost
        enhanced_confidence = min(confidence + total_boost, 1.0)

        # Check if we should suggest alternative
        alternative = None
        if confidence < 0.7:
            alternative = self._suggest_alternative(metadata)

        result = {
            **base_classification,
            'confidence': enhanced_confidence,
            'context_applied': True,
            'sender_boost': sender_boost,
            'subject_boost': subject_boost,
            'below_threshold': not threshold_check,
            'suggested_alternative': alternative
        }

        if total_boost > 0:
            logger.info(f"🎯 Context boost: +{total_boost:.0%} ({doc_type})")

        if alternative:
            logger.warning(f"💡 Suggested alternative: {alternative['type']} ({alternative['confidence']:.0%})")

        return result

    def _check_sender_context(self, sender: str, doc_type: str) -> float:
        """Check if sender historically sends this type"""
        if not sender or sender not in self.sender_patterns:
            return 0.0

        patterns = self.sender_patterns[sender]
        total = sum(patterns.values())

        if doc_type in patterns:
            # Boost proportional to how often sender sends this type
            ratio = patterns[doc_type] / total
            if ratio > 0.8:  # >80% of emails from this sender are this type
                return 0.15  # +15% confidence
            elif ratio > 0.5:
                return 0.10  # +10%
            elif ratio > 0.3:
                return 0.05  # +5%

        return 0.0

    def _check_subject_context(self, subject: str, doc_type: str) -> float:
        """Check if subject line hints at type"""
        if not subject:
            return 0.0

        # Check exact match
        if subject in self.subject_patterns:
            patterns = self.subject_patterns[subject]
            if doc_type in patterns and patterns[doc_type] >= 2:
                return 0.10  # +10% for known subject

        # Check partial matches (keywords)
        keywords_by_type = {
            'faktura': ['faktura', 'invoice', 'rechnung'],
            'stvrzenka': ['receipt', 'stvrzenka', 'pokladní'],
            'vyzva_k_platbe': ['upomínka', 'reminder', 'zaplatit'],
            'reklama': ['newsletter', 'akce', 'sleva', 'sale'],
        }

        subject_lower = subject.lower()
        for kw in keywords_by_type.get(doc_type, []):
            if kw in subject_lower:
                return 0.05  # +5% for keyword match

        return 0.0

    def _check_confidence_threshold(self, doc_type: str, confidence: float) -> bool:
        """Check if confidence is above learned threshold for this type"""
        if doc_type not in self.type_thresholds:
            return confidence >= 0.6  # Default threshold

        return confidence >= self.type_thresholds[doc_type]

    def _suggest_alternative(self, metadata: Dict) -> Dict or None:
        """Suggest alternative classification based on sender/subject"""
        sender = metadata.get('sender')

        if sender and sender in self.sender_patterns:
            # Most common type from this sender
            patterns = self.sender_patterns[sender]
            most_common = patterns.most_common(1)[0]

            return {
                'type': most_common[0],
                'confidence': most_common[1] / sum(patterns.values()),
                'reason': f'Sender typically sends {most_common[0]}'
            }

        return None

    def get_learning_stats(self) -> Dict:
        """Get statistics about learned context"""
        return {
            'known_senders': len(self.sender_patterns),
            'known_subjects': len(self.subject_patterns),
            'type_thresholds': dict(self.type_thresholds),
            'top_senders': [
                {
                    'sender': sender,
                    'types': dict(patterns)
                }
                for sender, patterns in list(self.sender_patterns.items())[:10]
            ]
        }

    def retrain(self):
        """Reload context from database (after new data)"""
        logger.info("🔄 Retraining context classifier...")
        self._load_context()
        logger.info("✅ Context retrained")


class MetaLearningClassifier:
    """
    Meta-learning: learns which classification method works best for which document type

    Tracks:
    - AI accuracy per type
    - Keyword accuracy per type
    - ML model accuracy per type
    - Optimal ensemble weights
    """

    def __init__(self, db_path: str = "data/documents.db"):
        self.db_path = db_path
        self._load_performance_stats()

    def _load_performance_stats(self):
        """Load historical performance of each method"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get ground truth (manually verified) documents
        cursor.execute("""
            SELECT
                document_type,
                ai_confidence,
                COUNT(*) as count
            FROM documents
            WHERE ai_confidence >= 0.9  -- High confidence = likely correct
            GROUP BY document_type
        """)

        self.method_performance = defaultdict(lambda: {'ai': 0, 'keywords': 0, 'ml': 0})

        for row in cursor.fetchall():
            doc_type, avg_conf, count = row
            # For now, assume AI is primary
            self.method_performance[doc_type]['ai'] = avg_conf

        conn.close()

    def get_optimal_weights(self, doc_type: str) -> Dict[str, float]:
        """
        Get optimal ensemble weights for this document type

        Returns:
            {'ai': 0.7, 'keywords': 0.2, 'ml': 0.1}
        """
        if doc_type not in self.method_performance:
            # Default weights
            return {'ai': 0.7, 'keywords': 0.2, 'ml': 0.1}

        # TODO: Implement actual meta-learning
        # For now, return based on historical AI performance
        ai_perf = self.method_performance[doc_type]['ai']

        if ai_perf > 0.95:
            return {'ai': 0.9, 'keywords': 0.05, 'ml': 0.05}
        elif ai_perf > 0.85:
            return {'ai': 0.7, 'keywords': 0.2, 'ml': 0.1}
        else:
            return {'ai': 0.5, 'keywords': 0.3, 'ml': 0.2}


def main():
    """Test context classifier"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from src.database.db_manager import DatabaseManager

    config = {'database': {'db_path': 'data/documents.db'}}
    db = DatabaseManager(config)

    classifier = ContextAwareClassifier(config, db)
    stats = classifier.get_learning_stats()

    print("\n📚 Context Learning Statistics:\n")
    print(f"Known senders: {stats['known_senders']}")
    print(f"Known subjects: {stats['known_subjects']}")

    print(f"\n🎯 Type-specific thresholds:")
    for doc_type, threshold in stats['type_thresholds'].items():
        print(f"  {doc_type:<25} {threshold:.0%}")

    print(f"\n👥 Top senders:")
    for sender_info in stats['top_senders'][:5]:
        print(f"\n  {sender_info['sender']}")
        for doc_type, count in sender_info['types'].items():
            print(f"    {doc_type:<20} {count:>3}×")


if __name__ == "__main__":
    main()
