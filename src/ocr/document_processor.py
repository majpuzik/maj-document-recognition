"""
Document preprocessing and OCR processing
"""

import logging
from typing import Dict

import cv2
import numpy as np
from PIL import Image

from .text_extractor import TextExtractor


class DocumentProcessor:
    """Process documents with OCR and preprocessing"""

    def __init__(self, config: dict):
        """
        Initialize DocumentProcessor

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.ocr_config = config.get("ocr", {})
        self.preprocessing_config = self.ocr_config.get("preprocessing", {})
        self.text_extractor = TextExtractor(config)

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR results

        Args:
            image: PIL Image object

        Returns:
            Preprocessed PIL Image
        """
        if not self.preprocessing_config.get("enabled", True):
            return image

        try:
            # Convert PIL to OpenCV
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            # Grayscale conversion
            if self.preprocessing_config.get("grayscale", True):
                self.logger.debug("Converting to grayscale")
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

            # Denoising
            if self.preprocessing_config.get("denoise", True):
                self.logger.debug("Applying denoising")
                cv_image = cv2.fastNlMeansDenoising(cv_image)

            # Contrast enhancement
            if self.preprocessing_config.get("contrast_enhancement", True):
                self.logger.debug("Enhancing contrast")
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                cv_image = clahe.apply(cv_image)

            # Deskew
            if self.preprocessing_config.get("deskew", True):
                self.logger.debug("Deskewing image")
                cv_image = self._deskew_image(cv_image)

            # Convert back to PIL
            if len(cv_image.shape) == 2:  # Grayscale
                preprocessed = Image.fromarray(cv_image)
            else:
                preprocessed = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))

            return preprocessed

        except Exception as e:
            self.logger.warning(f"Error in preprocessing, using original image: {e}")
            return image

    def _deskew_image(self, image: np.ndarray) -> np.ndarray:
        """
        Deskew (straighten) image

        Args:
            image: OpenCV image array

        Returns:
            Deskewed image array
        """
        try:
            # Calculate skew angle
            coords = np.column_stack(np.where(image > 0))
            angle = cv2.minAreaRect(coords)[-1]

            # Correct angle
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            # Rotate image
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                image,
                M,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

            return rotated

        except Exception as e:
            self.logger.warning(f"Deskewing failed: {e}")
            return image

    def process_document(self, file_path: str) -> Dict[str, any]:
        """
        Process document with OCR

        Args:
            file_path: Path to document file

        Returns:
            Dictionary with OCR results and metadata
        """
        self.logger.info(f"Processing document: {file_path}")

        try:
            # Extract text
            result = self.text_extractor.extract(file_path)

            if not result.get("success"):
                return result

            # Check confidence threshold
            threshold = self.ocr_config.get("confidence_threshold", 60)
            if result.get("confidence", 0) < threshold:
                self.logger.warning(
                    f"OCR confidence ({result.get('confidence'):.1f}%) below threshold ({threshold}%)"
                )

            # Add metadata
            result["metadata"] = {
                "file_path": file_path,
                "page_count": result.get("page_count", 1),
                "format": result.get("format", "unknown"),
                "preprocessing_enabled": self.preprocessing_config.get("enabled", True),
            }

            return result

        except Exception as e:
            self.logger.error(f"Error processing document: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0,
            }

    def batch_process(self, file_paths: list) -> list:
        """
        Process multiple documents

        Args:
            file_paths: List of file paths

        Returns:
            List of OCR results
        """
        results = []

        for file_path in file_paths:
            result = self.process_document(file_path)
            results.append(result)

        return results
