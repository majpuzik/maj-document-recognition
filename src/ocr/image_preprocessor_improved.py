"""
IMPROVED Image preprocessing for better OCR results
"""

import cv2
import logging
import numpy as np
from PIL import Image, ImageEnhance


class ImprovedImagePreprocessor:
    """Improved image preprocessing for better OCR accuracy"""

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.preprocess_config = config.get("ocr", {}).get("preprocessing", {})

    def preprocess(self, image_path: str) -> str:
        """
        Apply improved preprocessing pipeline

        Returns:
            Path to preprocessed image
        """
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                self.logger.error(f"Could not read image: {image_path}")
                return image_path

            self.logger.info(f"Original image shape: {img.shape}")

            # Apply preprocessing steps
            img = self._resize_if_needed(img)
            img = self._convert_to_grayscale(img)
            img = self._remove_noise(img)
            img = self._correct_skew(img)
            img = self._adaptive_thresholding(img)
            img = self._morphological_operations(img)
            img = self._enhance_contrast(img)

            # Save preprocessed image
            output_path = image_path.replace(".", "_preprocessed.")
            cv2.imwrite(output_path, img)

            self.logger.info(f"Preprocessed image saved: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Preprocessing error: {e}", exc_info=True)
            return image_path

    def _resize_if_needed(self, img):
        """Resize image if too small or too large"""
        height, width = img.shape[:2]

        # If too small, upscale
        if height < 800 or width < 800:
            scale = max(800 / height, 800 / width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            self.logger.info(f"Upscaled to {new_width}x{new_height}")

        # If too large, downscale
        elif height > 4000 or width > 4000:
            scale = min(4000 / height, 4000 / width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
            self.logger.info(f"Downscaled to {new_width}x{new_height}")

        return img

    def _convert_to_grayscale(self, img):
        """Convert to grayscale if not already"""
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self.logger.debug("Converted to grayscale")
        return img

    def _remove_noise(self, img):
        """Remove noise using multiple methods"""
        # Gaussian blur
        img = cv2.GaussianBlur(img, (3, 3), 0)

        # Bilateral filter (preserves edges)
        img = cv2.bilateralFilter(img, 9, 75, 75)

        self.logger.debug("Noise removed")
        return img

    def _correct_skew(self, img):
        """Detect and correct skew/rotation"""
        try:
            # Detect edges
            edges = cv2.Canny(img, 50, 150, apertureSize=3)

            # Detect lines using Hough transform
            lines = cv2.HoughLines(edges, 1, np.pi/180, 200)

            if lines is not None and len(lines) > 0:
                # Calculate average angle
                angles = []
                for line in lines[:20]:  # Use first 20 lines
                    rho, theta = line[0]
                    angle = (theta * 180 / np.pi) - 90
                    angles.append(angle)

                median_angle = np.median(angles)

                # Only rotate if skew is significant
                if abs(median_angle) > 0.5:
                    # Rotate image
                    (h, w) = img.shape[:2]
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                    img = cv2.warpAffine(img, M, (w, h),
                                        flags=cv2.INTER_CUBIC,
                                        borderMode=cv2.BORDER_REPLICATE)
                    self.logger.info(f"Corrected skew: {median_angle:.2f} degrees")

        except Exception as e:
            self.logger.debug(f"Skew correction failed: {e}")

        return img

    def _adaptive_thresholding(self, img):
        """Apply adaptive thresholding for better binarization"""
        # Use adaptive threshold instead of simple threshold
        # This works better for images with varying lighting
        img = cv2.adaptiveThreshold(
            img,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,  # Block size
            2    # Constant subtracted from mean
        )

        self.logger.debug("Applied adaptive thresholding")
        return img

    def _morphological_operations(self, img):
        """Apply morphological operations to clean up"""
        # Remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
        img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)

        self.logger.debug("Applied morphological operations")
        return img

    def _enhance_contrast(self, img):
        """Enhance contrast using CLAHE"""
        try:
            # CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = clahe.apply(img)

            self.logger.debug("Enhanced contrast with CLAHE")
        except Exception as e:
            self.logger.debug(f"Contrast enhancement failed: {e}")

        return img

    def preprocess_pil(self, pil_image: Image.Image) -> Image.Image:
        """Preprocess PIL Image object"""
        # Convert PIL to OpenCV
        img_array = np.array(pil_image)

        # Convert RGB to BGR for OpenCV
        if len(img_array.shape) == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Apply preprocessing
        temp_path = "/tmp/temp_preprocessing.png"
        cv2.imwrite(temp_path, img_array)

        preprocessed_path = self.preprocess(temp_path)

        # Read back as PIL
        return Image.open(preprocessed_path)
