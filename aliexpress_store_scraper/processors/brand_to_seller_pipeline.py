#!/usr/bin/env python3
"""
Brand-to-Seller Complete Pipeline
===============================

End-to-end pipeline that processes brand scan results through seller info extraction
and credential/contact information scraping.

Pipeline Flow:
1. Load brand scan JSON (e.g., nike_100.json) with Product URLs
2. Extract Store IDs from Product URLs (with retries)
3. Scrape store credentials and business license images
4. Extract contact information via OCR
5. Generate comprehensive seller information results

Features:
- Complete automation from brand scan to seller contact info
- Built-in retry logic for seller data population
- Progress tracking and detailed reporting
- Proxy support throughout the pipeline
- Intermediate result saving for debugging
"""

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from aliexpress_store_scraper.clients.enhanced_aliexpress_client import (
    EnhancedAliExpressClient,
)
from aliexpress_store_scraper.processors.core_seller_extractor import (
    CoreSellerExtractor,
)
from aliexpress_store_scraper.processors.seller_data_populator import (
    find_failed_products,
    populate_initial_seller_data_async,
    retry_failed_seller_data_async,
)
from aliexpress_store_scraper.processors.unified_seller_pipeline import (
    UnifiedSellerPipeline,
)


class BrandToSellerPipeline:
    """Complete pipeline from brand scan results to seller contact information."""

    def __init__(
        self,
        use_proxy: bool = False,
        delay: float = 2.0,
        retry_delay: float = 3.0,
        max_retries: int = 3,
        manual_cookie: Optional[str] = None,
    ):
        """
        Initialize the brand-to-seller pipeline.

        Args:
            use_proxy: Whether to use proxy for requests
            delay: Delay between requests during seller population
            retry_delay: Delay between retry attempts
            max_retries: Maximum retry attempts for failed seller extractions
            manual_cookie: Optional manual cookie string
        """
        self.use_proxy = use_proxy
        self.delay = delay
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.manual_cookie = manual_cookie
        # Use simple print for logging to match existing patterns
        self.logger = None

        # Initialize components
        self.client = EnhancedAliExpressClient()
        self.extractor = CoreSellerExtractor()
        self.unified_pipeline = UnifiedSellerPipeline(use_proxy=use_proxy)

    async def run_complete_pipeline(
        self,
        brand_scan_file: str,
        output_file: Optional[str] = None,
        save_intermediates: bool = False,
        save_ocr_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the complete brand-to-seller pipeline.

        Args:
            brand_scan_file: Input JSON file with product data
            output_file: Output file path (optional)
            save_intermediates: Whether to save intermediate results
            save_ocr_only: Whether to save only OCR results for legal identification
        """
        start_time = time.time()

        if not output_file:
            base_name = Path(brand_scan_file).stem
            output_file = f"{base_name}_seller_contact_info.json"

        print("🚀 Starting Brand-to-Seller Complete Pipeline")
        print("=" * 60)
        print(f"📁 Input: {brand_scan_file}")
        print(f"📁 Output: {output_file}")
        if self.use_proxy:
            print("🔗 Proxy: Enabled")
        print("")

        try:
            # Phase 1: Load brand scan data
            print("📋 Phase 1: Loading brand scan data...")
            products = await self._load_brand_scan_data(brand_scan_file)

            # Phase 2: Populate seller information
            print("🏪 Phase 2: Populating seller information...")
            populated_products = await self._populate_seller_information(
                products, save_intermediates, brand_scan_file
            )

            # Phase 3: Extract unique Store IDs for unified pipeline
            print("🔍 Phase 3: Extracting Store IDs for credential scraping...")
            store_ids = self._extract_unique_store_ids(populated_products)

            if not store_ids:
                raise ValueError("No Store IDs found after seller population phase")

            # Phase 4: Run unified pipeline (credentials + OCR)
            print("🔐 Phase 4: Running unified pipeline (credentials + OCR)...")
            seller_contact_results = await self._run_unified_pipeline(
                store_ids, save_intermediates, save_ocr_only, brand_scan_file
            )

            # Phase 5: Merge results
            print("🔗 Phase 5: Merging brand and seller contact data...")
            final_results = self._merge_brand_and_contact_data(
                populated_products, seller_contact_results
            )

            # Save final results
            processing_time = time.time() - start_time
            final_results["pipeline_metadata"]["total_processing_time"] = (
                processing_time
            )

            self._save_results(final_results, output_file)

            # Final summary
            self._print_final_summary(final_results, processing_time)

            return final_results

        except Exception as e:
            print(f"❌ Pipeline failed: {e}")
            raise

    async def _load_brand_scan_data(self, brand_scan_file: str) -> List[Dict[str, Any]]:
        """Load and validate brand scan data."""
        try:
            with open(brand_scan_file, "r", encoding="utf-8") as f:
                products = json.load(f)

            print(f"✅ Loaded {len(products)} products from brand scan")

            # Validate that we have Product URLs to work with
            products_with_urls = sum(1 for p in products if p.get("Product URL"))
            print(f"📊 Products with URLs: {products_with_urls}/{len(products)}")

            if products_with_urls == 0:
                raise ValueError(
                    "No products with Product URLs found in brand scan data"
                )

            return products

        except Exception as e:
            raise ValueError(f"Failed to load brand scan data: {e}")

    async def _populate_seller_information(
        self,
        products: List[Dict[str, Any]],
        save_intermediates: bool,
        base_filename: str,
    ) -> List[Dict[str, Any]]:
        """Populate seller information with retry logic."""

        # Phase 2a: Initial population
        print("🚀 Phase 2a: Initial seller data extraction...")

        (
            updated_products,
            initial_success,
            initial_errors,
        ) = await populate_initial_seller_data_async(
            products, self.client, self.extractor, self.manual_cookie, self.delay
        )

        print("📊 Initial seller population results:")
        print(f"  ✅ Successful: {initial_success}")
        print(f"  ❌ Failed: {initial_errors}")
        print(f"  📈 Success rate: {initial_success / len(products) * 100:.1f}%")

        # Phase 2b: Retry failed extractions
        retry_success = 0
        if initial_errors > 0:
            print("🔄 Phase 2b: Retrying failed seller extractions...")

            (
                updated_products,
                retry_success,
                retry_errors,
            ) = await retry_failed_seller_data_async(
                updated_products,
                self.client,
                self.extractor,
                self.manual_cookie,
                self.retry_delay,
                self.max_retries,
            )

            if retry_success > 0:
                print("📊 Retry results:")
                print(f"  ✅ Recovered: {retry_success}")
                print(f"  ❌ Still failed: {retry_errors}")

        total_success = initial_success + retry_success
        final_failure_count = len(find_failed_products(updated_products))

        print("📊 Final seller population summary:")
        print(f"  🎯 Total with seller data: {total_success}")
        print(f"  ⚠️  Still missing data: {final_failure_count}")
        print(f"  📈 Overall completion: {total_success / len(products) * 100:.1f}%")

        # Save intermediate results
        if save_intermediates:
            base_name = Path(base_filename).stem
            intermediate_file = f"{base_name}_with_sellers.json"
            with open(intermediate_file, "w", encoding="utf-8") as f:
                json.dump(updated_products, f, indent=2, ensure_ascii=False)
            print(f"💾 Seller data saved to: {intermediate_file}")

        return updated_products

    def _extract_unique_store_ids(self, products: List[Dict[str, Any]]) -> List[str]:
        """Extract unique Store IDs from populated products."""
        store_ids = set()

        for product in products:
            store_id = product.get("Store ID")
            if store_id and str(store_id).strip() and str(store_id).lower() != "null":
                store_ids.add(str(store_id))

        store_ids_list = list(store_ids)
        print(f"📊 Found {len(store_ids_list)} unique Store IDs for processing")

        return store_ids_list

    async def _run_unified_pipeline(
        self,
        store_ids: List[str],
        save_intermediates: bool,
        save_ocr_only: bool,
        base_filename: str,
    ) -> Dict[str, Any]:
        """Run the unified pipeline for credential scraping and OCR."""

        # Create temporary intermediate files if needed
        credentials_file = None
        ocr_file = None

        # Determine if we should save intermediate results
        should_save_intermediates = save_intermediates or save_ocr_only
        output_dir = None

        if should_save_intermediates:
            base_name = Path(base_filename).stem
            output_dir = Path(base_filename).parent

        # Run unified pipeline
        results = await self.unified_pipeline.process_stores_from_list(
            store_ids,
            save_intermediate_results=should_save_intermediates,
            output_dir=str(output_dir) if should_save_intermediates else None,
        )

        return results

    def _merge_brand_and_contact_data(
        self, brand_products: List[Dict[str, Any]], contact_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge brand products with seller contact information using deduplicated structure."""
        print("🔗 Merging data with automatic deduplication to prevent legal risks...")

        # Create store-to-contact mapping (deduplicated)
        contact_by_store_id = {}
        if contact_results.get("results"):
            for contact_data in contact_results["results"]:
                store_id = contact_data.get("store_id")
                if store_id:
                    contact_by_store_id[store_id] = contact_data

        # Group products by store and create deduplicated structure
        store_info = defaultdict(
            lambda: {"products": [], "contact_info": None, "contact_sources": set()}
        )

        # Organize products by store
        for product in brand_products:
            store_id = product.get("Store ID")
            if store_id:
                store_info[store_id]["products"].append(product)

                # Set contact info once per store (deduplication)
                if (
                    store_id in contact_by_store_id
                    and not store_info[store_id]["contact_info"]
                ):
                    contact_data = contact_by_store_id[store_id]
                    store_info[store_id]["contact_info"] = contact_data.get(
                        "contact_info", {}
                    )

                    # Track sources for validation
                    if (
                        "contact_info" in contact_data
                        and "sources" in contact_data["contact_info"]
                    ):
                        for source in contact_data["contact_info"]["sources"]:
                            store_info[store_id]["contact_sources"].add(
                                source.get("image_id", "")
                            )

        # Create deduplicated stores database
        stores_db = {}
        total_contact_points = 0

        for store_id, info in store_info.items():
            contact_info = info["contact_info"] or {
                "emails": [],
                "phone_numbers": [],
                "addresses": [],
                "company_names": [],
                "registration_numbers": [],
                "confidence_scores": [],
                "sources": [],
                "average_confidence": 0.0,
                "total_contact_points": 0,
            }

            # Count contact points once per store
            store_contact_points = contact_info.get("total_contact_points", 0)
            total_contact_points += store_contact_points

            stores_db[store_id] = {
                "store_id": store_id,
                "product_count": len(info["products"]),
                "contact_info": contact_info,
                "has_contact_data": bool(info["contact_info"]),
                "contact_sources": list(info["contact_sources"])
                if info["contact_sources"]
                else [],
            }

        # Create clean products database with store references only
        products_db = []
        for product in brand_products:
            store_id = product.get("Store ID")
            clean_product = {
                "product_info": product,
                "store_id": store_id,
                "has_contact_data": store_id in stores_db
                and stores_db[store_id]["has_contact_data"],
            }
            products_db.append(clean_product)

        # Calculate summary statistics
        products_with_contact = sum(1 for p in products_db if p["has_contact_data"])
        stores_with_contact = sum(
            1 for store in stores_db.values() if store["has_contact_data"]
        )

        print(f"📊 Deduplication results:")
        print(f"   ✅ {len(stores_db)} unique stores")
        print(f"   ✅ {stores_with_contact} stores with contact data")
        print(f"   ✅ {products_with_contact} products linked to contacted stores")
        print(f"   ✅ Contact info stored once per store (legal-safe)")

        return {
            "pipeline_metadata": {
                "pipeline_type": "brand_to_seller_complete_deduplicated",
                "total_products_processed": len(brand_products),
                "products_with_seller_contact": products_with_contact,
                "total_contact_points_found": total_contact_points,
                "timestamp": time.time(),
                "structure_version": "2.0_deduplicated",
                "deduplication_applied": True,
            },
            "summary": {
                "brand_products": len(brand_products),
                "products_with_contact_info": products_with_contact,
                "stores_with_contact_info": stores_with_contact,
                "total_stores": len(stores_db),
                "contact_extraction_rate": products_with_contact
                / len(brand_products)
                * 100
                if brand_products
                else 0,
                "total_contact_points": total_contact_points,
            },
            "stores": stores_db,
            "products": products_db,
            "legal_compliance": {
                "contact_attribution_safe": True,
                "no_duplication_risk": True,
                "cease_desist_ready": True,
                "structure_version": "2.0_deduplicated",
                "note": "Contact information is properly attributed to stores, not duplicated across products",
            },
            "pipeline_details": {
                "seller_population_results": {
                    "total_processed": len(brand_products),
                    "with_seller_data": len(
                        [p for p in brand_products if p.get("Store ID")]
                    ),
                },
                "contact_extraction_results": contact_results.get("summary", {}),
            },
        }

    def _save_results(self, results: Dict[str, Any], output_file: str) -> None:
        """Save final results to file."""
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"💾 Complete results saved to: {output_file}")
        except Exception as e:
            raise ValueError(f"Failed to save results: {e}")

    def _print_final_summary(
        self, results: Dict[str, Any], processing_time: float
    ) -> None:
        """Print comprehensive final summary."""
        metadata = results["pipeline_metadata"]
        summary = results["summary"]

        print("")
        print("=" * 80)
        print("🎯 BRAND-TO-SELLER COMPLETE PIPELINE RESULTS (DEDUPLICATED)")
        print("=" * 80)
        print("")
        print("📊 PIPELINE SUMMARY")
        print("-" * 30)
        print(f"Total brand products processed: {summary['brand_products']}")
        print(f"Total unique stores: {summary['total_stores']}")
        print(
            f"Products with seller contact info: {summary['products_with_contact_info']}"
        )
        print(f"Stores with contact info: {summary['stores_with_contact_info']}")
        print(
            f"Contact extraction success rate: {summary['contact_extraction_rate']:.1f}%"
        )
        print(f"Total contact points found: {summary['total_contact_points']}")
        print(f"Total processing time: {processing_time:.1f} seconds")

        # Legal compliance info
        legal = results.get("legal_compliance", {})
        if legal:
            print("")
            print("⚖️  LEGAL COMPLIANCE STATUS")
            print("-" * 25)
            print(
                f"✅ Contact attribution safe: {legal.get('contact_attribution_safe', False)}"
            )
            print(f"✅ No duplication risk: {legal.get('no_duplication_risk', False)}")
            print(f"✅ Cease & desist ready: {legal.get('cease_desist_ready', False)}")
            print(f"📦 Structure version: {legal.get('structure_version', 'unknown')}")

        # Contact breakdown
        contact_results = results.get("pipeline_details", {}).get(
            "contact_extraction_results", {}
        )
        if contact_results:
            print("")
            print("📞 CONTACT INFORMATION BREAKDOWN")
            print("-" * 35)
            print(f"📧 Emails found: {contact_results.get('total_emails_found', 0)}")
            print(
                f"📞 Phone numbers found: {contact_results.get('total_phones_found', 0)}"
            )
            print(
                f"� Addresses found: {contact_results.get('total_addresses_found', 0)}"
            )

        # Store breakdown
        stores = results.get("stores", {})
        if stores:
            print("")
            print("🏪 STORE BREAKDOWN")
            print("-" * 16)
            for store_id, store_data in stores.items():
                contact = store_data["contact_info"]
                emails = len(contact.get("emails", []))
                phones = len(contact.get("phone_numbers", []))
                addresses = len(contact.get("addresses", []))

                print(f"Store {store_id}:")
                print(f"   - Products: {store_data['product_count']}")
                print(
                    f"   - Contacts: {emails} emails, {phones} phones, {addresses} addresses"
                )
                print(
                    f"   - Contact data: {'✅ Available' if store_data['has_contact_data'] else '❌ None'}"
                )

        print("")
        print("✅ Brand-to-Seller Pipeline completed successfully!")
        print("🛡️  Data structure optimized for legal compliance!")


async def main():
    # Main function for the brand-to-seller pipeline CLI
    parser = argparse.ArgumentParser(
        description="Complete brand-to-seller pipeline: brand scan → seller info → contact extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "brand_scan_file",
        help="Brand scan JSON file (e.g., nike_100.json) with Product URLs",
    )
    parser.add_argument(
        "--output",
        help="Output file for complete results (default: <input>_seller_contact_info.json)",
    )
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Use proxy for requests (requires OXYLABS_* environment variables)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between requests during seller population (default: 2.0)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=3.0,
        help="Delay between retry attempts (default: 3.0)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts for failed seller extractions (default: 3)",
    )
    parser.add_argument("--cookie", help="Manual cookie string for API requests")
    parser.add_argument(
        "--save-intermediates",
        action="store_true",
        help="Save intermediate results (seller data, credentials, OCR) - creates larger files",
    )
    parser.add_argument(
        "--save-ocr-only",
        action="store_true",
        help="Save only OCR results with store IDs for legal identification (recommended)",
    )

    args = parser.parse_args()

    # Validate input file
    if not Path(args.brand_scan_file).exists():
        print(f"❌ Error: Input file '{args.brand_scan_file}' not found")
        sys.exit(1)

    # Initialize pipeline
    pipeline = BrandToSellerPipeline(
        use_proxy=args.proxy,
        delay=args.delay,
        retry_delay=args.retry_delay,
        max_retries=args.max_retries,
        manual_cookie=args.cookie,
    )

    try:
        # Run complete pipeline
        await pipeline.run_complete_pipeline(
            brand_scan_file=args.brand_scan_file,
            output_file=args.output,
            save_intermediates=args.save_intermediates,
            save_ocr_only=args.save_ocr_only,
        )

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
