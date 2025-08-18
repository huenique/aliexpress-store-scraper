#!/usr/bin/env python3
"""
Business License Image Processor
===============================

A comprehensive tool for extracting contact information from business license images
using OCR (Optical Character Recognition) and intelligent text pattern matching.

This module can be used both as a library and as a command-line tool.

Library Usage:
    from business_license_processor import BusinessLicenseProcessor

    processor = BusinessLicenseProcessor()

    # Process single image
    result = await processor.process_image(image_data)

    # Process multiple images in parallel
    results = await processor.process_images_batch(image_list)

    # Extract contact info from text
    contacts = processor.extract_contact_info(ocr_text)

CLI Usage:
    # Process from existing JSON results
    python business_license_processor.py --from-json store_results.json

    # Process individual image files
    python business_license_processor.py --images img1.jpg,img2.png

    # Custom settings
    python business_license_processor.py --from-json results.json --workers 8 --output contacts.json

Dependencies:
    pip install pillow pytesseract opencv-python-headless
    # Install Tesseract OCR: sudo apt-get install tesseract-ocr (Linux)

Author: AI Assistant
Date: August 2025
"""

import argparse
import asyncio
import base64
import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, cast

try:
    import cv2
    import numpy as np
    import pytesseract
    from PIL import Image

    has_ocr_deps = True
except ImportError:
    cv2 = None
    np = None
    Image = None
    pytesseract = None
    has_ocr_deps = False

HAS_OCR = has_ocr_deps

from logger import ScraperLogger


@dataclass
class ContactInfo:
    """Data class for extracted contact information"""

    emails: List[str] = field(default_factory=lambda: cast(List[str], []))
    phone_numbers: List[str] = field(default_factory=lambda: cast(List[str], []))
    addresses: List[str] = field(default_factory=lambda: cast(List[str], []))
    company_name: Optional[str] = None
    registration_number: Optional[str] = None
    raw_text: str = ""
    confidence_score: float = 0.0


@dataclass
class ProcessingResult:
    """Data class for image processing results"""

    image_id: str
    status: str
    contact_info: Optional[ContactInfo] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    timestamp: float = field(default_factory=time.time)


class BusinessLicenseProcessor:
    """
    Processes business license images to extract contact information
    using OCR and pattern matching techniques.
    """

    def __init__(
        self,
        max_workers: int = 4,
        tesseract_config: str = "--oem 3 --psm 6",
        enable_preprocessing: bool = True,
    ):
        """
        Initialize the business license processor.

        Args:
            max_workers: Maximum number of parallel workers for processing
            tesseract_config: Tesseract OCR configuration string
            enable_preprocessing: Whether to apply image preprocessing
        """
        self.logger = ScraperLogger("BusinessLicenseProcessor")
        self.max_workers = max_workers
        self.tesseract_config = tesseract_config
        self.enable_preprocessing = enable_preprocessing

        # Check if OCR dependencies are available
        if not HAS_OCR:
            self.logger.warning(
                "⚠️ OCR dependencies not installed. Install: pip install pillow pytesseract opencv-python-headless"
            )
            # Don't raise error, allow fallback functionality

        # Verify Tesseract is available if dependencies are installed
        if HAS_OCR and pytesseract:
            try:
                # Type ignore for pytesseract function that may not be in stub
                pytesseract.get_tesseract_version()  # type: ignore[attr-defined]
            except Exception as e:
                self.logger.error(f"❌ Tesseract not found: {e}")
                # Don't raise error in constructor, handle in methods

        # Email regex patterns (comprehensive)
        self.email_patterns = [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
            r"\b[\w\.-]+@[\w\.-]+\.[\w]+\b",
        ]

        # Phone number patterns (international formats)
        self.phone_patterns = [
            r"\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}",  # US/Canada
            r"\+?86[-.\s]?1[0-9]{10}",  # China mobile
            r"\+?86[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{7,8}",  # China landline
            r"\+?[0-9]{1,4}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}",  # International
            r"\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}",  # Standard format
            r"[0-9]{3}[-.\s]?[0-9]{4}[-.\s]?[0-9]{4}",  # Another common format
            r"Tel:?\s*[+]?[0-9\s\-\(\)]{7,15}",  # With Tel prefix
            r"Phone:?\s*[+]?[0-9\s\-\(\)]{7,15}",  # With Phone prefix
        ]

        # Address patterns (basic - can be enhanced)
        self.address_patterns = [
            r"\b\d+[\w\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Place|Pl|Court|Ct)\b",
            r"\b\d+[\w\s,.-]+(?:路|街|巷|号|楼|层|室)\b",  # Chinese address patterns
            r"Address:?\s*(.{10,100})",  # With Address prefix
            r"地址:?\s*(.{5,50})",  # Chinese address prefix
        ]

        # Business registration patterns
        self.registration_patterns = [
            r"Registration\s*(?:No|Number|#):?\s*([A-Z0-9]{8,20})",
            r"License\s*(?:No|Number|#):?\s*([A-Z0-9]{8,20})",
            r"统一社会信用代码:?\s*([A-Z0-9]{18})",  # Chinese unified credit code
            r"注册号:?\s*([A-Z0-9]{8,20})",  # Chinese registration number
        ]

        self.logger.info("✅ Business License Processor initialized")

    def _decode_base64_image(self, base64_data: str) -> Optional[Any]:
        """
        Decode base64 image data to PIL Image.

        Args:
            base64_data: Base64 encoded image string

        Returns:
            PIL Image object or None if decoding fails
        """
        if not HAS_OCR or not Image:
            self.logger.error("❌ PIL not available for image decoding")
            return None

        try:
            # Remove data URI prefix if present
            if base64_data.startswith("data:image/"):
                base64_data = base64_data.split(",", 1)[1]

            # Decode base64
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_bytes))

            return image

        except Exception as e:
            self.logger.error(f"❌ Failed to decode base64 image: {e}")
            return None

    def _load_image_from_path(self, image_path: Union[str, Path]) -> Optional[Any]:
        """
        Load image from file path.

        Args:
            image_path: Path to image file

        Returns:
            PIL Image object or None if loading fails
        """
        if not HAS_OCR or not Image:
            self.logger.error("❌ PIL not available for image loading")
            return None

        try:
            image_path = Path(image_path)
            if not image_path.exists():
                self.logger.error(f"❌ Image file not found: {image_path}")
                return None

            image = Image.open(image_path)
            return image

        except Exception as e:
            self.logger.error(f"❌ Failed to load image from {image_path}: {e}")
            return None

    def _preprocess_image(self, image: Any) -> Any:
        """
        Apply preprocessing to improve OCR accuracy for business documents.

        Args:
            image: Input PIL Image

        Returns:
            Preprocessed PIL Image
        """
        if not self.enable_preprocessing:
            return image

        if not HAS_OCR or not cv2 or not np or not Image:
            self.logger.warning("⚠️ OpenCV/NumPy not available - skipping preprocessing")
            return image

        try:
            # Convert to numpy array for OpenCV processing
            img_array = np.array(image)

            # Convert to grayscale if not already
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # For business documents, try minimal preprocessing
            # Sometimes less processing is better for clean documents

            # Resize image if too small (OCR works better on larger images)
            height, width = gray.shape
            if height < 800 or width < 800:
                scale_factor = max(800 / height, 800 / width)
                new_height = int(height * scale_factor)
                new_width = int(width * scale_factor)
                gray = cv2.resize(
                    gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC
                )
                self.logger.info(
                    f"📏 Resized image from {width}x{height} to {new_width}x{new_height}"
                )

            # Simple thresholding for business documents (often have good contrast)
            # Use Otsu's thresholding for automatic threshold selection
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Apply slight dilation to make text thicker/clearer
            kernel = np.ones((1, 1), np.uint8)
            processed = cv2.dilate(thresh, kernel, iterations=1)

            # Convert back to PIL Image
            processed_image = Image.fromarray(processed)

            return processed_image

        except Exception as e:
            self.logger.error(f"❌ Image preprocessing failed: {e}")
            return image

    def _extract_text_from_image(self, image: Any) -> str:
        """
        Extract text from image using OCR with multiple configuration attempts.

        Args:
            image: PIL Image object

        Returns:
            Extracted text as string
        """
        if not HAS_OCR or not pytesseract:
            self.logger.error("❌ Tesseract OCR not available")
            return ""

        try:
            # Preprocess image
            processed_image = self._preprocess_image(image)

            # Try multiple OCR configurations for better results
            configs = [
                "--oem 3 --psm 6",  # Default: uniform block of text
                "--oem 3 --psm 4",  # Single column of text
                "--oem 3 --psm 3",  # Fully automatic page segmentation
                "--oem 3 --psm 8",  # Single word
                "--oem 3 --psm 7",  # Single text line
                "--oem 3 --psm 11",  # Sparse text
                "--oem 3 --psm 12",  # Sparse text with OSD
            ]

            best_text: str = ""
            best_length: int = 0

            for config in configs:
                try:
                    # Type ignore for pytesseract function that may not be in stub
                    text = cast(
                        str,
                        pytesseract.image_to_string(  # type: ignore[attr-defined]
                            processed_image, config=config
                        ).strip(),
                    )
                    # Choose the result with the most content (heuristic for best extraction)
                    if len(text) > best_length:
                        best_text = text
                        best_length = len(text)
                        self.logger.info(
                            f"🔍 Better OCR result with config '{config}': {len(text)} chars"
                        )
                except Exception as e:
                    self.logger.warning(f"⚠️ OCR config '{config}' failed: {e}")
                    continue

            # Also try without preprocessing in case it's making things worse
            if best_length < 50:  # If we got very little text, try raw image
                try:
                    # Type ignore for pytesseract function that may not be in stub
                    raw_text = cast(
                        str,
                        pytesseract.image_to_string(  # type: ignore[attr-defined]
                            image, config="--oem 3 --psm 6"
                        ).strip(),
                    )
                    if len(raw_text) > best_length:
                        best_text = raw_text
                        best_length = len(raw_text)
                        self.logger.info(
                            f"🔍 Raw image OCR performed better: {len(raw_text)} chars"
                        )
                except Exception as e:
                    self.logger.warning(f"⚠️ Raw OCR failed: {e}")

            self.logger.info(
                f"🎯 Final OCR result: {len(best_text)} characters extracted"
            )
            if best_text:
                # Log first 200 chars for debugging
                preview = best_text[:200].replace("\n", "\\n")
                self.logger.info(f"📝 OCR Preview: {preview}...")

            return best_text

        except Exception as e:
            self.logger.error(f"❌ OCR extraction failed: {e}")
            return ""

    def extract_contact_info(self, text: str) -> ContactInfo:
        """
        Extract contact information from OCR text using pattern matching.

        Args:
            text: OCR extracted text

        Returns:
            ContactInfo object with extracted information
        """
        contact_info = ContactInfo(raw_text=text)

        # Extract emails
        for pattern in self.email_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            contact_info.emails.extend(matches)

        # Remove duplicates and clean
        contact_info.emails = list(set(email.strip() for email in contact_info.emails))

        # Extract phone numbers
        for pattern in self.phone_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            contact_info.phone_numbers.extend(matches)

        # Clean and deduplicate phone numbers
        cleaned_phones: List[str] = []
        for phone in contact_info.phone_numbers:
            # Remove common prefixes and clean
            cleaned = re.sub(r"^(Tel:?|Phone:?)\s*", "", phone, flags=re.IGNORECASE)
            cleaned = re.sub(r"[^\d+\-\(\)\s]", "", cleaned).strip()
            if len(cleaned) >= 7:  # Minimum phone length
                cleaned_phones.append(cleaned)

        contact_info.phone_numbers = list(set(cleaned_phones))

        # Extract addresses
        for pattern in self.address_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if isinstance(matches[0], tuple) if matches else False:
                # Handle patterns with groups - use cast to ensure proper typing
                address_matches = cast(
                    List[str],
                    [
                        match[0] if isinstance(match, tuple) else match
                        for match in matches
                    ],
                )
                contact_info.addresses.extend(address_matches)
            else:
                contact_info.addresses.extend(cast(List[str], matches))

        # Clean addresses
        contact_info.addresses = [
            addr.strip() for addr in contact_info.addresses if len(addr.strip()) > 5
        ]
        contact_info.addresses = list(set(contact_info.addresses))

        # Try to extract company name (heuristic approach)
        lines = text.split("\n")
        for line in lines[:5]:  # Check first few lines
            line = line.strip()
            if len(line) > 3 and len(line) < 100:
                # Look for company indicators
                if any(
                    keyword in line.lower()
                    for keyword in [
                        "company",
                        "corp",
                        "inc",
                        "ltd",
                        "llc",
                        "公司",
                        "有限",
                    ]
                ):
                    contact_info.company_name = line
                    break

        # Extract registration numbers
        for pattern in self.registration_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                contact_info.registration_number = matches[0]
                break

        # Calculate confidence score based on information found
        score = 0.0
        if contact_info.emails:
            score += 0.3
        if contact_info.phone_numbers:
            score += 0.3
        if contact_info.addresses:
            score += 0.2
        if contact_info.company_name:
            score += 0.1
        if contact_info.registration_number:
            score += 0.1

        contact_info.confidence_score = min(score, 1.0)

        return contact_info

    def _process_single_image(self, image_data: Dict[str, Any]) -> ProcessingResult:
        """
        Process a single image (synchronous function for thread execution).

        Args:
            image_data: Dictionary containing image information

        Returns:
            ProcessingResult object
        """
        start_time = time.time()
        image_id = image_data.get("id", "unknown")

        try:
            # Load image based on data type
            image = None

            if "base64" in image_data:
                image = self._decode_base64_image(image_data["base64"])
            elif "path" in image_data:
                image = self._load_image_from_path(image_data["path"])
            elif "data_uri" in image_data:
                image = self._decode_base64_image(image_data["data_uri"])
            else:
                return ProcessingResult(
                    image_id=image_id,
                    status="error",
                    error="No valid image data provided",
                )

            if image is None:
                return ProcessingResult(
                    image_id=image_id, status="error", error="Failed to load image"
                )

            # Extract text using OCR
            text = self._extract_text_from_image(image)

            if not text.strip():
                return ProcessingResult(
                    image_id=image_id,
                    status="warning",
                    contact_info=ContactInfo(raw_text=""),
                    error="No text extracted from image",
                    processing_time=time.time() - start_time,
                )

            # Extract contact information
            contact_info = self.extract_contact_info(text)

            return ProcessingResult(
                image_id=image_id,
                status="success",
                contact_info=contact_info,
                processing_time=time.time() - start_time,
            )

        except Exception as e:
            return ProcessingResult(
                image_id=image_id,
                status="error",
                error=str(e),
                processing_time=time.time() - start_time,
            )

    async def process_image(self, image_data: Dict[str, Any]) -> ProcessingResult:
        """
        Process a single image asynchronously.

        Args:
            image_data: Dictionary containing image information
                      - For base64: {'id': str, 'base64': str} or {'id': str, 'data_uri': str}
                      - For file: {'id': str, 'path': str}

        Returns:
            ProcessingResult object
        """
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor, self._process_single_image, image_data
            )

        return result

    async def process_images_batch(
        self,
        images_data: List[Dict[str, Any]],
        progress_callback: Optional[
            Callable[[int, int, ProcessingResult], None]
        ] = None,
    ) -> List[ProcessingResult]:
        """
        Process multiple images in parallel.

        Args:
            images_data: List of image data dictionaries
            progress_callback: Optional callback function for progress updates

        Returns:
            List of ProcessingResult objects
        """
        if not images_data:
            self.logger.warning("⚠️ No images provided for processing")
            return []

        self.logger.info(
            f"🔄 Starting parallel processing of {len(images_data)} images"
        )
        start_time = time.time()

        # Process images in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            loop = asyncio.get_event_loop()

            # Create tasks for all images
            tasks = [
                loop.run_in_executor(executor, self._process_single_image, image_data)
                for image_data in images_data
            ]

            # Process tasks and track progress
            results: List[ProcessingResult] = []
            completed = 0

            for task in asyncio.as_completed(tasks):
                result = await task
                results.append(result)
                completed += 1

                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed, len(images_data), result)

                # Log progress
                if completed % max(1, len(images_data) // 10) == 0 or completed == len(
                    images_data
                ):
                    self.logger.info(
                        f"📊 Progress: {completed}/{len(images_data)} images processed"
                    )

        total_time = time.time() - start_time
        success_count = sum(1 for r in results if r.status == "success")

        self.logger.info(f"✅ Batch processing completed in {total_time:.2f}s")
        self.logger.info(
            f"📈 Success rate: {success_count}/{len(results)} ({success_count / len(results) * 100:.1f}%)"
        )

        return results

    def get_processing_summary(self, results: List[ProcessingResult]) -> Dict[str, Any]:
        """
        Generate a summary of processing results.

        Args:
            results: List of ProcessingResult objects

        Returns:
            Summary dictionary with statistics
        """
        if not results:
            return {"total_images": 0, "message": "No results to analyze"}

        total_images = len(results)
        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "error")
        warnings = sum(1 for r in results if r.status == "warning")

        # Count extracted information
        total_emails = sum(
            len(r.contact_info.emails) if r.contact_info else 0 for r in results
        )
        total_phones = sum(
            len(r.contact_info.phone_numbers) if r.contact_info else 0 for r in results
        )
        total_addresses = sum(
            len(r.contact_info.addresses) if r.contact_info else 0 for r in results
        )

        # Calculate average confidence
        confidence_scores = [
            r.contact_info.confidence_score
            for r in results
            if r.contact_info and r.status == "success"
        ]
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 0.0
        )

        # Calculate average processing time
        avg_processing_time = sum(r.processing_time for r in results) / total_images

        return {
            "total_images": total_images,
            "successful": successful,
            "failed": failed,
            "warnings": warnings,
            "success_rate": f"{successful / total_images * 100:.1f}%",
            "total_emails_extracted": total_emails,
            "total_phones_extracted": total_phones,
            "total_addresses_extracted": total_addresses,
            "average_confidence_score": f"{avg_confidence:.2f}",
            "average_processing_time": f"{avg_processing_time:.2f}s",
            "images_with_contact_info": sum(
                1
                for r in results
                if r.contact_info
                and (
                    r.contact_info.emails
                    or r.contact_info.phone_numbers
                    or r.contact_info.addresses
                )
            ),
        }

    def export_results_to_dict(self, results: List[ProcessingResult]) -> Dict[str, Any]:
        """
        Export processing results to a serializable dictionary.

        Args:
            results: List of ProcessingResult objects

        Returns:
            Dictionary containing all results and summary
        """
        exported_results: List[Dict[str, Any]] = []

        for result in results:
            result_dict: Dict[str, Any] = {
                "image_id": result.image_id,
                "status": result.status,
                "processing_time": result.processing_time,
                "timestamp": result.timestamp,
                "error": result.error,
            }

            if result.contact_info:
                result_dict["contact_info"] = {
                    "emails": result.contact_info.emails,
                    "phone_numbers": result.contact_info.phone_numbers,
                    "addresses": result.contact_info.addresses,
                    "company_name": result.contact_info.company_name,
                    "registration_number": result.contact_info.registration_number,
                    "confidence_score": result.contact_info.confidence_score,
                    "raw_text_length": len(result.contact_info.raw_text),
                }

            exported_results.append(result_dict)

        return {
            "results": exported_results,
            "summary": self.get_processing_summary(results),
            "processing_metadata": {
                "processor_version": "1.0.0",
                "max_workers": self.max_workers,
                "tesseract_config": self.tesseract_config,
                "preprocessing_enabled": self.enable_preprocessing,
                "total_processing_time": sum(r.processing_time for r in results),
            },
        }


# Convenience functions for easy usage
async def process_business_license_images(
    images_data: List[Dict[str, Any]], max_workers: int = 4
) -> List[ProcessingResult]:
    """
    Convenience function to process business license images.

    Args:
        images_data: List of image data dictionaries
        max_workers: Maximum number of parallel workers

    Returns:
        List of ProcessingResult objects
    """
    processor = BusinessLicenseProcessor(max_workers=max_workers)
    return await processor.process_images_batch(images_data)


def extract_contact_from_text(text: str) -> ContactInfo:
    """
    Convenience function to extract contact info from text.

    Args:
        text: Text to analyze

    Returns:
        ContactInfo object
    """
    processor = BusinessLicenseProcessor()
    return processor.extract_contact_info(text)


# =============================================================================
# CLI INTERFACE
# =============================================================================


class BusinessLicenseCLI:
    """Command-line interface for the Business License Processor"""

    def __init__(self):
        self.logger = ScraperLogger("BusinessLicenseCLI")

    def load_json_data(self, json_file: str) -> Dict[str, Any]:
        """Load data from JSON file"""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load JSON file {json_file}: {e}")
            raise

    def extract_images_from_json(
        self, json_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract image data from JSON results for processing"""
        images_data: List[Dict[str, Any]] = []

        results = json_data.get("results", [])
        for result in results:
            if result.get("status") != "success":
                continue

            store_id = result.get("store_id", "unknown")
            images = result.get("images", {})

            for image_key, image_data in images.items():
                if "base64" not in image_data:
                    continue

                images_data.append(
                    {
                        "id": f"{store_id}_{image_key}",
                        "store_id": store_id,
                        "base64": image_data["base64"],
                        "format": image_data.get("format", "unknown"),
                    }
                )

        return images_data

    def prepare_image_files(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """Prepare image files for processing"""
        images_data: List[Dict[str, Any]] = []

        for i, image_path in enumerate(image_paths):
            path = Path(image_path)
            if not path.exists():
                self.logger.warning(f"Image file not found: {image_path}")
                continue

            images_data.append(
                {
                    "id": f"file_{i + 1}_{path.stem}",
                    "path": str(path.absolute()),
                    "filename": path.name,
                }
            )

        return images_data

    async def process_from_json(
        self, json_file: str, max_workers: int = 4
    ) -> Dict[str, Any]:
        """Process images from JSON file"""
        self.logger.info(f"Loading results from {json_file}")

        json_data = self.load_json_data(json_file)
        images_data = self.extract_images_from_json(json_data)

        if not images_data:
            print("⚠️ No images found in JSON data")
            return {"results": [], "summary": {"error": "No images found"}}

        print(f"📊 Found {len(images_data)} images to process\n")

        processor = BusinessLicenseProcessor(max_workers=max_workers)

        def progress_callback(
            completed: int, total: int, result: ProcessingResult
        ) -> None:
            if completed % max(1, total // 10) == 0 or completed == total:
                print(
                    f"📊 Progress: {completed}/{total} ({completed / total * 100:.1f}%)"
                )

        results = await processor.process_images_batch(
            images_data, progress_callback=progress_callback
        )
        return {"results": results, "original_data": json_data}

    async def process_image_files(
        self, image_paths: List[str], max_workers: int = 4
    ) -> Dict[str, Any]:
        """Process individual image files"""
        images_data = self.prepare_image_files(image_paths)

        if not images_data:
            return {"results": [], "summary": {"error": "No valid images found"}}

        print(f"📊 Found {len(images_data)} images to process\n")

        processor = BusinessLicenseProcessor(max_workers=max_workers)

        def progress_callback(
            completed: int, total: int, result: ProcessingResult
        ) -> None:
            print(
                f"📊 Processing: {completed}/{total} ({completed / total * 100:.1f}%)"
            )

        results = await processor.process_images_batch(
            images_data, progress_callback=progress_callback
        )
        return {"results": results}

    def print_results(self, results: Dict[str, Any]):
        """Print formatted results"""
        print("\n" + "=" * 60)
        print("🏢 BUSINESS LICENSE PROCESSING RESULTS")
        print("=" * 60)

        processing_results = results.get("results", [])

        if not processing_results:
            print("❌ No results to display")
            return

        # Count successful extractions
        successful_extractions = 0
        total_contacts_found = 0

        print(f"\n📊 PROCESSING SUMMARY")
        print("-" * 25)
        print(f"Total images processed: {len(processing_results)}")

        # Show contact information found
        for result in processing_results:
            if result.status == "success" and result.contact_info:
                contact = result.contact_info
                if contact.emails or contact.phone_numbers or contact.addresses:
                    successful_extractions += 1
                    total_contacts_found += (
                        len(contact.emails)
                        + len(contact.phone_numbers)
                        + len(contact.addresses)
                    )

        print(f"Successful extractions: {successful_extractions}")
        print(f"Total contact points: {total_contacts_found}")
        print(
            f"Success rate: {successful_extractions / len(processing_results) * 100:.1f}%"
        )

        if successful_extractions > 0:
            print(f"\n📞 CONTACT INFORMATION FOUND")
            print("-" * 35)

            for result in processing_results:
                if result.status == "success" and result.contact_info:
                    contact = result.contact_info
                    if contact.emails or contact.phone_numbers or contact.addresses:
                        print(f"\n🖼️ Image: {result.image_id}")

                        if contact.company_name:
                            print(f"  🏢 Company: {contact.company_name}")

                        if contact.emails:
                            print(f"  📧 Emails: {', '.join(contact.emails)}")

                        if contact.phone_numbers:
                            print(f"  📞 Phones: {', '.join(contact.phone_numbers)}")

                        if contact.addresses:
                            print(f"  📍 Addresses:")
                            for addr in contact.addresses:
                                print(f"     • {addr}")

                        if contact.registration_number:
                            print(f"  🆔 Registration: {contact.registration_number}")

                        print(f"  📊 Confidence: {contact.confidence_score:.2f}")
        else:
            print("\n⚠️ No contact information was extracted")
            print("This could be due to:")
            print("  • Poor image quality or OCR recognition issues")
            print("  • Text not in recognized format")
            print("  • Images don't contain readable contact information")

    def save_results(self, results: Dict[str, Any], output_file: str):
        """Save results to JSON file"""
        try:
            # Convert results to JSON-serializable format
            json_results: Dict[str, Any] = {
                "summary": {
                    "total_processed": len(results.get("results", [])),
                    "successful_extractions": sum(
                        1
                        for r in results.get("results", [])
                        if r.status == "success"
                        and r.contact_info
                        and (
                            r.contact_info.emails
                            or r.contact_info.phone_numbers
                            or r.contact_info.addresses
                        )
                    ),
                    "processing_timestamp": time.time(),
                },
                "results": [],
            }

            results_list = results.get("results", [])
            for result in results_list:
                json_result: Dict[str, Any] = {
                    "image_id": result.image_id,
                    "status": result.status,
                    "processing_time": result.processing_time,
                    "error": result.error,
                }

                if result.contact_info:
                    json_result["contact_info"] = {
                        "emails": result.contact_info.emails,
                        "phone_numbers": result.contact_info.phone_numbers,
                        "addresses": result.contact_info.addresses,
                        "company_name": result.contact_info.company_name,
                        "registration_number": result.contact_info.registration_number,
                        "confidence_score": result.contact_info.confidence_score,
                    }

                json_results["results"].append(json_result)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(json_results, f, indent=2, ensure_ascii=False)

            print(f"💾 Results saved to: {output_file}")

        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")


async def main():
    """Main CLI function"""

    # Check OCR dependencies first
    if not HAS_OCR:
        print("❌ OCR dependencies not available.")
        print("Install with:")
        print("  pip install pillow pytesseract opencv-python-headless")
        print("  # Install Tesseract: sudo apt-get install tesseract-ocr (Linux)")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Extract contact information from business license images using OCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --from-json store_results.json
  %(prog)s --images img1.jpg,img2.png --workers 8
  %(prog)s --from-json results.json --output contacts.json --workers 4
        """,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--from-json", type=str, help="Process images from existing JSON results file"
    )
    input_group.add_argument(
        "--images", type=str, help="Comma-separated list of image file paths to process"
    )

    # Processing options
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Maximum number of parallel workers (default: 4)",
    )
    parser.add_argument("--output", type=str, help="Output JSON file path (optional)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Initialize CLI
    cli = BusinessLicenseCLI()

    print("🏢 Business License Processor")
    print("=" * 35)

    try:
        results = None

        if args.from_json:
            results = await cli.process_from_json(args.from_json, args.workers)
        elif args.images:
            image_paths = [p.strip() for p in args.images.split(",")]
            results = await cli.process_image_files(image_paths, args.workers)

        if results:
            cli.print_results(results)

            if args.output:
                cli.save_results(results, args.output)

            print(f"\n✅ Processing completed successfully!")
        else:
            print("❌ No results obtained")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


# =============================================================================
# LIBRARY FUNCTIONS (for easy importing)
# =============================================================================


def extract_contact_info_from_text(text: str) -> ContactInfo:
    """
    Convenience function to extract contact info from text.

    Args:
        text: Text to analyze for contact information

    Returns:
        ContactInfo object with extracted information
    """
    processor = BusinessLicenseProcessor()
    return processor.extract_contact_info(text)


async def process_single_image(image_data: Dict[str, Any]) -> ProcessingResult:
    """
    Convenience function to process a single image.

    Args:
        image_data: Dictionary containing image information

    Returns:
        ProcessingResult object
    """
    processor = BusinessLicenseProcessor()
    return await processor.process_image(image_data)


async def process_multiple_images(
    images_data: List[Dict[str, Any]],
    max_workers: int = 4,
    progress_callback: Optional[Callable[[int, int, ProcessingResult], None]] = None,
) -> List[ProcessingResult]:
    """
    Convenience function to process multiple images in parallel.

    Args:
        images_data: List of image data dictionaries
        max_workers: Maximum parallel workers
        progress_callback: Optional progress callback function

    Returns:
        List of ProcessingResult objects
    """
    processor = BusinessLicenseProcessor(max_workers=max_workers)
    return await processor.process_images_batch(images_data, progress_callback)


if __name__ == "__main__":
    asyncio.run(main())
