"""
Machine Learning model for document classification (TF-IDF + Naive Bayes)
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


class MLModel:
    """Machine Learning classifier using TF-IDF and Naive Bayes"""

    def __init__(self, config: dict, db_manager=None):
        """
        Initialize MLModel

        Args:
            config: Application configuration dictionary
            db_manager: Database manager instance
        """
        self.config = config
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.ml_config = config.get("ai", {}).get("ml_model", {})

        self.model_path = Path("data/ml_model.pkl")
        self.model = None
        self.is_trained = False

        # Load existing model
        self._load_model()

    def _load_model(self) -> None:
        """Load trained model from disk"""
        if self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                self.is_trained = True
                self.logger.info("ML model loaded successfully")
            except Exception as e:
                self.logger.error(f"Error loading ML model: {e}")
                self.model = None
                self.is_trained = False
        else:
            self.logger.info("No existing ML model found")

    def _save_model(self) -> None:
        """Save trained model to disk"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump(self.model, f)
            self.logger.info("ML model saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving ML model: {e}")

    def train(self, texts: List[str], labels: List[str]) -> bool:
        """
        Train the model with labeled data

        Args:
            texts: List of document texts
            labels: List of document types (labels)

        Returns:
            True if training successful
        """
        if len(texts) != len(labels):
            self.logger.error("Texts and labels must have same length")
            return False

        min_samples = self.ml_config.get("min_training_samples", 10)
        if len(texts) < min_samples:
            self.logger.warning(f"Not enough training samples ({len(texts)} < {min_samples})")
            return False

        try:
            self.logger.info(f"Training ML model with {len(texts)} samples")

            # Create pipeline
            self.model = Pipeline([
                ("tfidf", TfidfVectorizer(
                    max_features=5000,
                    ngram_range=(1, 2),
                    min_df=2,
                    stop_words=None,  # Keep all words for multilingual support
                )),
                ("clf", MultinomialNB(alpha=0.1)),
            ])

            # Train
            self.model.fit(texts, labels)
            self.is_trained = True

            # Save model
            self._save_model()

            self.logger.info("ML model training completed")
            return True

        except Exception as e:
            self.logger.error(f"Error training ML model: {e}", exc_info=True)
            return False

    def predict(self, text: str) -> Dict[str, any]:
        """
        Predict document type

        Args:
            text: Document text

        Returns:
            Prediction result dictionary
        """
        if not self.is_trained or self.model is None:
            return {
                "success": False,
                "error": "Model not trained",
            }

        try:
            # Predict
            predicted_type = self.model.predict([text])[0]

            # Get probability
            probabilities = self.model.predict_proba([text])[0]
            confidence = float(np.max(probabilities))

            return {
                "success": True,
                "type": predicted_type,
                "confidence": confidence,
                "probabilities": dict(zip(self.model.classes_, probabilities)),
            }

        except Exception as e:
            self.logger.error(f"Error predicting with ML model: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def auto_train_from_db(self) -> bool:
        """
        Automatically train model from database

        Returns:
            True if training successful
        """
        if not self.ml_config.get("auto_train", False):
            return False

        if not self.db_manager:
            self.logger.warning("No database manager available for auto-training")
            return False

        try:
            # Get labeled documents from database
            documents = self.db_manager.get_labeled_documents()

            if not documents:
                self.logger.info("No labeled documents available for training")
                return False

            texts = [doc["ocr_text"] for doc in documents]
            labels = [doc["document_type"] for doc in documents]

            return self.train(texts, labels)

        except Exception as e:
            self.logger.error(f"Error in auto-training: {e}", exc_info=True)
            return False

    def should_retrain(self) -> bool:
        """
        Check if model should be retrained

        Returns:
            True if retraining recommended
        """
        if not self.db_manager:
            return False

        try:
            # Get count of new samples since last training
            new_samples = self.db_manager.get_new_samples_count()
            threshold = self.ml_config.get("retrain_threshold", 50)

            return new_samples >= threshold

        except Exception as e:
            self.logger.error(f"Error checking retrain status: {e}")
            return False
