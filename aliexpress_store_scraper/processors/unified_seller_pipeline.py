#!/usr/bin/env python3
"""
Unified Seller Information Pipeline
==================================

A comprehensive pipeline that combines store credential scraping with OCR-based
seller information extraction from business license images.

This pipeline:
1. Scrapes store credentials and business license images from AliExpress
2. Uses OCR to extract seller contact information (address, email, phone) from the images
3. Combines both data sources into a unified seller profile

Pipeline Flow:
    JSON file with Store IDs → Store Credential Scraping → OCR Processing → Unified Results

Features:
- Handles JSON files with "Store ID" fields
- Scrapes certificate images from credential pages
- OCR extraction of contact information
- Unified data structure combining all seller information
- Progress tracking and error handling
- Configurable processing parameters

Usage:
    from unified_seller_pipeline import UnifiedSellerPipeline

    pipeline = UnifiedSellerPipeline()
    results = await pipeline.process_stores_from_json("nike_products.json")

    # Results contain both credential data and extracted contact info
    for result in results:
        print(f"Store: {result['store_id']}")
        print(f"Credentials: {result['credentials']}")
        print(f"Contact Info: {result['contact_info']}")

Author: AI Assistant
Date: August 2025
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from aliexpress_store_scraper.processors.business_license_processor import (
    BusinessLicenseProcessor,
    ContactInfo,
    ProcessingResult,
)
from aliexpress_store_scraper.processors.store_credentials_network_scraper import (
    StoreCredentialsNetworkScraper,
)
from aliexpress_store_scraper.utils.logger import ScraperLogger


class UnifiedSellerPipeline:
    """
    Unified pipeline for comprehensive seller information extraction.

    Combines store credential scraping with OCR-based contact information
    extraction to create complete seller profiles.
    """

    def __init__(
        self,
        max_workers: int = 4,
        enable_ocr_preprocessing: bool = True,
        captcha_retry_limit: int = 3,
        use_proxy: bool = False,
    ):
        """
        Initialize the unified pipeline.

        Args:
            max_workers: Maximum number of parallel workers for processing
            enable_ocr_preprocessing: Whether to enable image preprocessing for OCR
            captcha_retry_limit: Maximum number of CAPTCHA retry attempts
            use_proxy: Whether to use Oxylabs proxy configuration from environment
        """
        self.max_workers = max_workers
        self.enable_ocr_preprocessing = enable_ocr_preprocessing
        self.captcha_retry_limit = captcha_retry_limit
        self.use_proxy = use_proxy

        self.logger = ScraperLogger("UnifiedSellerPipeline")

        # Initialize sub-processors
        self.credentials_scraper = StoreCredentialsNetworkScraper(
            max_retries=captcha_retry_limit, use_proxy=use_proxy
        )
        self.ocr_processor = BusinessLicenseProcessor(
            max_workers=max_workers,
            enable_preprocessing=enable_ocr_preprocessing,
        )

        self.logger.info("✅ Unified Seller Pipeline initialized")

    def load_store_ids_from_json(self, json_file: str) -> List[str]:
        """
        Load store IDs from JSON file.

        Args:
            json_file: Path to JSON file containing "Store ID" fields

        Returns:
            List of unique store IDs
        """
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            store_ids = []

            # Handle both list and dict formats
            items = data if isinstance(data, list) else [data]

            for item in items:
                if isinstance(item, dict) and "Store ID" in item:
                    store_id = item["Store ID"]
                    if store_id and str(store_id).strip():
                        store_ids.append(str(store_id).strip())
                elif isinstance(item, list):
                    # Handle nested lists
                    for subitem in item:
                        if isinstance(subitem, dict) and "Store ID" in subitem:
                            store_id = subitem["Store ID"]
                            if store_id and str(store_id).strip():
                                store_ids.append(str(store_id).strip())

            # Remove duplicates and None values
            unique_store_ids = list(set(sid for sid in store_ids if sid))

            self.logger.info(
                f"📋 Loaded {len(unique_store_ids)} unique store IDs from {json_file}"
            )
            return unique_store_ids

        except Exception as e:
            self.logger.error(f"❌ Failed to load store IDs from {json_file}: {e}")
            raise

    async def scrape_store_credentials(self, store_ids: List[str]) -> Dict[str, Any]:
        """
        Scrape store credentials and business license images.

        Args:
            store_ids: List of store IDs to scrape

        Returns:
            Dictionary containing scraping results
        """
        self.logger.info(f"🔍 Starting credential scraping for {len(store_ids)} stores")

        try:
            # The scraper returns a list of results, we need to wrap it in a dict format
            results_list = await self.credentials_scraper.scrape_store_credentials(
                store_ids
            )

            # Transform to expected format
            results = {
                "results": [],
                "metadata": {
                    "total_requested": len(store_ids),
                    "timestamp": time.time(),
                },
            }

            for result in results_list:
                # Transform result format to match expected structure
                is_successful = result.get("status") == "success"
                transformed_result = {
                    "store_id": result.get("store_id", "unknown"),
                    "status": "success" if is_successful else "error",
                    "processing_time": result.get("processing_time", 0),
                }

                if is_successful:
                    transformed_result.update(
                        {
                            "api_data": result.get("network_data", {}),
                            "images": result.get("images", {}),
                        }
                    )
                else:
                    transformed_result["error"] = result.get("error", "Unknown error")
                    # Still include images if they were captured, even on credential parsing failure
                    if result.get("images"):
                        transformed_result["images"] = result.get("images", {})

                results["results"].append(transformed_result)

            successful_stores = sum(
                1 for result in results["results"] if result.get("status") == "success"
            )

            self.logger.info(
                f"✅ Credential scraping completed: {successful_stores}/{len(store_ids)} stores successful"
            )

            return results

        except Exception as e:
            self.logger.error(f"❌ Credential scraping failed: {e}")
            raise

    async def extract_contact_information(
        self, credentials_results: Dict[str, Any]
    ) -> List[ProcessingResult]:
        """
        Extract contact information from business license images using OCR.

        Args:
            credentials_results: Results from store credential scraping

        Returns:
            List of OCR processing results with contact information
        """
        # Extract images from credentials results
        images_data = []

        for result in credentials_results.get("results", []):
            store_id = result.get("store_id", "unknown")

            # Check both successful and failed results for images
            # Sometimes images are captured even if credential parsing fails
            images = result.get("images", {})

            # If no images in the result, check if images were captured during scraping
            # Look for any image data in the result structure
            if not images and hasattr(result, "get"):
                # Check for alternative image storage locations
                for key, value in result.items():
                    if isinstance(value, dict) and "base64" in value:
                        images[key] = value

            if not images:
                # Skip if no images found at all
                continue

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

        if not images_data:
            self.logger.warning("⚠️ No images found for OCR processing")
            return []

        self.logger.info(f"📷 Processing {len(images_data)} images with OCR")

        def progress_callback(
            completed: int, total: int, result: ProcessingResult
        ) -> None:
            if completed % max(1, total // 5) == 0 or completed == total:
                self.logger.info(
                    f"📊 OCR Progress: {completed}/{total} ({completed / total * 100:.1f}%)"
                )

        ocr_results = await self.ocr_processor.process_images_batch(
            images_data, progress_callback=progress_callback
        )

        successful_ocr = sum(
            1
            for result in ocr_results
            if result.status == "success"
            and result.contact_info
            and (
                result.contact_info.emails
                or result.contact_info.phone_numbers
                or result.contact_info.addresses
            )
        )

        self.logger.info(
            f"✅ OCR processing completed: {successful_ocr}/{len(images_data)} images with contact info extracted"
        )

        return ocr_results

    def merge_seller_data(
        self, credentials_results: Dict[str, Any], ocr_results: List[ProcessingResult]
    ) -> List[Dict[str, Any]]:
        """
        Merge credential scraping results with OCR contact information.

        Args:
            credentials_results: Results from credential scraping
            ocr_results: Results from OCR processing

        Returns:
            List of unified seller profiles
        """
        # Create mapping of store_id to OCR results
        ocr_by_store = {}
        for ocr_result in ocr_results:
            if ocr_result.status == "success" and "_" in ocr_result.image_id:
                store_id = ocr_result.image_id.split("_")[0]
                if store_id not in ocr_by_store:
                    ocr_by_store[store_id] = []
                ocr_by_store[store_id].append(ocr_result)

        unified_results = []

        for credentials_result in credentials_results.get("results", []):
            store_id = credentials_result.get("store_id", "unknown")

            # Base seller profile from credentials
            seller_profile = {
                "store_id": store_id,
                "processing_timestamp": time.time(),
                "credentials": {
                    "status": credentials_result.get("status"),
                    "api_data": credentials_result.get("api_data", {}),
                    "images": credentials_result.get("images", {}),
                    "processing_time": credentials_result.get("processing_time", 0),
                },
                "contact_info": {
                    "extraction_successful": False,
                    "total_contact_points": 0,
                    "emails": [],
                    "phone_numbers": [],
                    "addresses": [],
                    "company_names": [],
                    "registration_numbers": [],
                    "confidence_scores": [],
                    "sources": [],
                },
                "summary": {
                    "has_credentials": credentials_result.get("status") == "success",
                    "has_contact_info": False,
                    "total_images_processed": 0,
                    "successful_ocr_extractions": 0,
                },
            }

            # Add OCR contact information if available
            if store_id in ocr_by_store:
                store_ocr_results = ocr_by_store[store_id]
                seller_profile["summary"]["total_images_processed"] = len(
                    store_ocr_results
                )

                successful_extractions = 0
                all_emails = set()
                all_phones = set()
                all_addresses = set()
                all_companies = set()
                all_registrations = set()
                all_confidence_scores = []

                for ocr_result in store_ocr_results:
                    if ocr_result.contact_info:
                        contact = ocr_result.contact_info

                        # Check if any contact info was found
                        has_contact = bool(
                            contact.emails or contact.phone_numbers or contact.addresses
                        )

                        if has_contact:
                            successful_extractions += 1

                            # Collect all contact information
                            all_emails.update(contact.emails)
                            all_phones.update(contact.phone_numbers)
                            all_addresses.update(contact.addresses)

                            if contact.company_name:
                                all_companies.add(contact.company_name)
                            if contact.registration_number:
                                all_registrations.add(contact.registration_number)

                            all_confidence_scores.append(contact.confidence_score)

                            # Track source image
                            seller_profile["contact_info"]["sources"].append(
                                {
                                    "image_id": ocr_result.image_id,
                                    "confidence": contact.confidence_score,
                                    "contacts_found": {
                                        "emails": len(contact.emails),
                                        "phones": len(contact.phone_numbers),
                                        "addresses": len(contact.addresses),
                                    },
                                }
                            )

                # Populate unified contact information
                seller_profile["contact_info"].update(
                    {
                        "extraction_successful": successful_extractions > 0,
                        "total_contact_points": len(all_emails)
                        + len(all_phones)
                        + len(all_addresses),
                        "emails": sorted(list(all_emails)),
                        "phone_numbers": sorted(list(all_phones)),
                        "addresses": sorted(list(all_addresses)),
                        "company_names": sorted(list(all_companies)),
                        "registration_numbers": sorted(list(all_registrations)),
                        "confidence_scores": all_confidence_scores,
                        "average_confidence": sum(all_confidence_scores)
                        / len(all_confidence_scores)
                        if all_confidence_scores
                        else 0.0,
                    }
                )

                seller_profile["summary"].update(
                    {
                        "has_contact_info": successful_extractions > 0,
                        "successful_ocr_extractions": successful_extractions,
                    }
                )

            unified_results.append(seller_profile)

        self.logger.info(f"🔗 Merged data for {len(unified_results)} stores")
        return unified_results

    async def process_stores_from_json(
        self,
        json_file: str,
        save_intermediate_results: bool = True,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process stores from JSON file through the complete pipeline.

        Args:
            json_file: Path to JSON file containing "Store ID" fields
            save_intermediate_results: Whether to save intermediate results
            output_dir: Directory to save results (defaults to current directory)

        Returns:
            Dictionary containing complete pipeline results
        """
        start_time = time.time()

        if output_dir is None:
            output_dir = Path.cwd()
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"🚀 Starting unified seller pipeline for {json_file}")

        try:
            # Step 1: Load store IDs
            store_ids = self.load_store_ids_from_json(json_file)

            if not store_ids:
                raise ValueError("No store IDs found in JSON file")

            # Step 2: Scrape store credentials
            self.logger.info("📋 Phase 1: Scraping store credentials...")
            credentials_results = await self.scrape_store_credentials(store_ids)

            if save_intermediate_results:
                credentials_file = output_dir / "credentials_results.json"
                with open(credentials_file, "w", encoding="utf-8") as f:
                    json.dump(credentials_results, f, indent=2, ensure_ascii=False)
                self.logger.info(
                    f"💾 Intermediate credentials saved to {credentials_file}"
                )

            # Step 3: Extract contact information using OCR
            self.logger.info("📋 Phase 2: Extracting contact information with OCR...")
            ocr_results = await self.extract_contact_information(credentials_results)

            if save_intermediate_results:
                # Convert OCR results to JSON-serializable format
                ocr_json_results = []
                for result in ocr_results:
                    json_result = {
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
                    ocr_json_results.append(json_result)

                ocr_file = output_dir / "ocr_results.json"
                with open(ocr_file, "w", encoding="utf-8") as f:
                    json.dump(ocr_json_results, f, indent=2, ensure_ascii=False)
                self.logger.info(f"💾 Intermediate OCR results saved to {ocr_file}")

            # Step 4: Merge data into unified seller profiles
            self.logger.info("📋 Phase 3: Merging data into unified profiles...")
            unified_results = self.merge_seller_data(credentials_results, ocr_results)

            # Calculate final statistics
            total_time = time.time() - start_time

            final_results = {
                "pipeline_metadata": {
                    "input_file": str(json_file),
                    "total_stores_processed": len(store_ids),
                    "processing_time_seconds": total_time,
                    "pipeline_phases": [
                        "Store credential scraping",
                        "OCR contact extraction",
                        "Data merging",
                    ],
                    "timestamp": time.time(),
                },
                "summary": {
                    "stores_with_credentials": sum(
                        1
                        for result in unified_results
                        if result["summary"]["has_credentials"]
                    ),
                    "stores_with_contact_info": sum(
                        1
                        for result in unified_results
                        if result["summary"]["has_contact_info"]
                    ),
                    "total_contact_points": sum(
                        result["contact_info"]["total_contact_points"]
                        for result in unified_results
                    ),
                    "total_emails_found": sum(
                        len(result["contact_info"]["emails"])
                        for result in unified_results
                    ),
                    "total_phones_found": sum(
                        len(result["contact_info"]["phone_numbers"])
                        for result in unified_results
                    ),
                    "total_addresses_found": sum(
                        len(result["contact_info"]["addresses"])
                        for result in unified_results
                    ),
                },
                "results": unified_results,
            }

            self.logger.info(
                f"✅ Pipeline completed in {total_time:.1f}s - "
                f"{final_results['summary']['stores_with_credentials']} stores with credentials, "
                f"{final_results['summary']['stores_with_contact_info']} with contact info"
            )

            return final_results

        except Exception as e:
            self.logger.error(f"❌ Pipeline failed: {e}")
            raise

    async def process_stores_from_list(
        self,
        store_ids: List[str],
        save_intermediate_results: bool = True,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process stores from a list of store IDs through the complete pipeline.

        Args:
            store_ids: List of store IDs to process
            save_intermediate_results: Whether to save intermediate results
            output_dir: Directory to save results

        Returns:
            Dictionary containing complete pipeline results
        """
        start_time = time.time()

        if output_dir is None:
            output_dir = Path.cwd()
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            f"🚀 Starting unified seller pipeline for {len(store_ids)} store IDs"
        )

        try:
            # Process through the pipeline (similar to JSON version but skip loading step)

            # Step 1: Scrape store credentials
            self.logger.info("📋 Phase 1: Scraping store credentials...")
            credentials_results = await self.scrape_store_credentials(store_ids)

            if save_intermediate_results:
                credentials_file = output_dir / "credentials_results.json"
                with open(credentials_file, "w", encoding="utf-8") as f:
                    json.dump(credentials_results, f, indent=2, ensure_ascii=False)
                self.logger.info(
                    f"💾 Intermediate credentials saved to {credentials_file}"
                )

            # Step 2: Extract contact information using OCR
            self.logger.info("📋 Phase 2: Extracting contact information with OCR...")
            ocr_results = await self.extract_contact_information(credentials_results)

            if save_intermediate_results:
                # Convert OCR results to JSON-serializable format
                ocr_json_results = []
                for result in ocr_results:
                    json_result = {
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
                    ocr_json_results.append(json_result)

                ocr_file = output_dir / "ocr_results.json"
                with open(ocr_file, "w", encoding="utf-8") as f:
                    json.dump(ocr_json_results, f, indent=2, ensure_ascii=False)
                self.logger.info(f"💾 Intermediate OCR results saved to {ocr_file}")

            # Step 3: Merge data into unified seller profiles
            self.logger.info("📋 Phase 3: Merging data into unified profiles...")
            unified_results = self.merge_seller_data(credentials_results, ocr_results)

            # Calculate final statistics
            total_time = time.time() - start_time

            final_results = {
                "pipeline_metadata": {
                    "total_stores_processed": len(store_ids),
                    "processing_time_seconds": total_time,
                    "pipeline_phases": [
                        "Store credential scraping",
                        "OCR contact extraction",
                        "Data merging",
                    ],
                    "timestamp": time.time(),
                },
                "summary": {
                    "stores_with_credentials": sum(
                        1
                        for result in unified_results
                        if result["summary"]["has_credentials"]
                    ),
                    "stores_with_contact_info": sum(
                        1
                        for result in unified_results
                        if result["summary"]["has_contact_info"]
                    ),
                    "total_contact_points": sum(
                        result["contact_info"]["total_contact_points"]
                        for result in unified_results
                    ),
                    "total_emails_found": sum(
                        len(result["contact_info"]["emails"])
                        for result in unified_results
                    ),
                    "total_phones_found": sum(
                        len(result["contact_info"]["phone_numbers"])
                        for result in unified_results
                    ),
                    "total_addresses_found": sum(
                        len(result["contact_info"]["addresses"])
                        for result in unified_results
                    ),
                },
                "results": unified_results,
            }

            self.logger.info(
                f"✅ Pipeline completed in {total_time:.1f}s - "
                f"{final_results['summary']['stores_with_credentials']} stores with credentials, "
                f"{final_results['summary']['stores_with_contact_info']} with contact info"
            )

            return final_results

        except Exception as e:
            self.logger.error(f"❌ Pipeline failed: {e}")
            raise

    def print_pipeline_results(self, results: Dict[str, Any]):
        """
        Print formatted pipeline results.

        Args:
            results: Results from the pipeline processing
        """
        print("\n" + "=" * 80)
        print("🏪 UNIFIED SELLER INFORMATION PIPELINE RESULTS")
        print("=" * 80)

        metadata = results.get("pipeline_metadata", {})
        summary = results.get("summary", {})

        # Pipeline summary
        print(f"\n📊 PIPELINE SUMMARY")
        print("-" * 25)
        if "input_file" in metadata:
            print(f"Input file: {metadata['input_file']}")
        print(f"Total stores processed: {metadata.get('total_stores_processed', 0)}")
        print(
            f"Processing time: {metadata.get('processing_time_seconds', 0):.1f} seconds"
        )
        print(f"Stores with credentials: {summary.get('stores_with_credentials', 0)}")
        print(f"Stores with contact info: {summary.get('stores_with_contact_info', 0)}")
        print(f"Total contact points found: {summary.get('total_contact_points', 0)}")

        # Detailed breakdown
        print(f"\n📞 CONTACT INFORMATION BREAKDOWN")
        print("-" * 35)
        print(f"📧 Emails found: {summary.get('total_emails_found', 0)}")
        print(f"📞 Phone numbers found: {summary.get('total_phones_found', 0)}")
        print(f"📍 Addresses found: {summary.get('total_addresses_found', 0)}")

        # Individual store results
        store_results = results.get("results", [])
        stores_with_data = [
            result
            for result in store_results
            if result["summary"]["has_credentials"]
            or result["summary"]["has_contact_info"]
        ]

        if stores_with_data:
            print(f"\n🏪 STORE DETAILS ({len(stores_with_data)} with data)")
            print("-" * 30)

            for result in stores_with_data[:10]:  # Show first 10 stores
                store_id = result["store_id"]
                has_creds = result["summary"]["has_credentials"]
                has_contact = result["summary"]["has_contact_info"]

                print(f"\n🏪 Store ID: {store_id}")
                print(f"  📋 Credentials: {'✅' if has_creds else '❌'}")
                print(f"  📞 Contact Info: {'✅' if has_contact else '❌'}")

                if has_contact:
                    contact_info = result["contact_info"]
                    if contact_info["emails"]:
                        print(
                            f"    📧 Emails: {', '.join(contact_info['emails'][:3])}{'...' if len(contact_info['emails']) > 3 else ''}"
                        )
                    if contact_info["phone_numbers"]:
                        print(
                            f"    📞 Phones: {', '.join(contact_info['phone_numbers'][:2])}{'...' if len(contact_info['phone_numbers']) > 2 else ''}"
                        )
                    if contact_info["addresses"]:
                        print(
                            f"    📍 Address: {contact_info['addresses'][0][:50]}{'...' if len(contact_info['addresses'][0]) > 50 else ''}"
                        )
                    if contact_info["average_confidence"] > 0:
                        print(
                            f"    📊 Confidence: {contact_info['average_confidence']:.2f}"
                        )

            if len(stores_with_data) > 10:
                print(f"\n... and {len(stores_with_data) - 10} more stores with data")

        else:
            print("\n⚠️ No stores have both credentials and contact information")
            print("This could be due to:")
            print("  • CAPTCHA challenges during scraping")
            print("  • Poor image quality for OCR processing")
            print("  • Images don't contain readable contact information")

        print(f"\n✅ Pipeline processing completed successfully!")
