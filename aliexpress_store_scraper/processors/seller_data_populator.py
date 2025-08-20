#!/usr/bin/env python3
"""
Seller Data Populator Module
============================

This module reads a JSON file with product data, extracts seller information
for each product using their Product URLs, and updates the JSON with the
seller data to replace null values.

Features:
- Initial seller data population
- Optional retry for failed products
- Automated and manual cookie support
- Progress tracking and detailed reporting
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from aliexpress_store_scraper.clients.enhanced_aliexpress_client import (
    EnhancedAliExpressClient,
)
from aliexpress_store_scraper.processors.core_seller_extractor import (
    CoreSellerExtractor,
)


def extract_product_id_from_url(url: str) -> Optional[str]:
    """Extract product ID from AliExpress URL."""
    import re

    if url.isdigit():
        return url

    patterns = [
        r"/item/(\d+)\.html",
        r"/item/(\d+)",
        r"item/(\d+)",
        r"/(\d+)\.html",
        r"(\d{13,})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def get_seller_data_for_product(
    product_url: str,
    client: EnhancedAliExpressClient,
    extractor: CoreSellerExtractor,
    manual_cookie: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get seller data for a single product.

    Returns:
        Dict with seller data or error information
    """
    try:
        # Extract product ID from URL
        product_id = extract_product_id_from_url(product_url)
        if not product_id:
            return {"error": f"Could not extract product ID from URL: {product_url}"}

        print(f"🔍 Processing Product ID: {product_id}")

        # Get API response
        if manual_cookie:
            api_result = client.call_api(
                cookie_string=manual_cookie,
                api="mtop.aliexpress.pdp.pc.query",
                data={
                    "productId": product_id,
                    "_lang": "en_US",
                    "_currency": "USD",
                    "country": "US",
                    "province": "922878890000000000",
                    "city": "922878897869000000",
                    "channel": "",
                    "pdp_ext_f": "",
                    "pdpNPI": "",
                    "sourceType": "",
                    "clientType": "pc",
                    "ext": json.dumps(
                        {
                            "foreverRandomToken": "1b30c08e93b84668bac6ea9a4e750a45",
                            "site": "usa",
                            "crawler": False,
                            "x-m-biz-bx-region": "",
                            "signedIn": True,
                            "host": "www.aliexpress.us",
                        }
                    ),
                },
            )
        else:
            # Use automated cookies
            product_result = client.get_product_with_auto_cookies(product_id)
            if not product_result.get("success"):
                return {
                    "error": f"Failed to get product: {product_result.get('error')}"
                }

            # Get fresh cookies and make API call
            cookie_result = client._get_valid_cookies()
            if not cookie_result["success"]:
                return {"error": f"Failed to get cookies: {cookie_result.get('error')}"}

            api_result = client.call_api(
                cookie_string=cookie_result["cookies"],
                api="mtop.aliexpress.pdp.pc.query",
                data={
                    "productId": product_id,
                    "_lang": "en_US",
                    "_currency": "USD",
                    "country": "US",
                    "province": "922878890000000000",
                    "city": "922878897869000000",
                    "channel": "",
                    "pdp_ext_f": "",
                    "pdpNPI": "",
                    "sourceType": "",
                    "clientType": "pc",
                    "ext": json.dumps(
                        {
                            "foreverRandomToken": "1b30c08e93b84668bac6ea9a4e750a45",
                            "site": "usa",
                            "crawler": False,
                            "x-m-biz-bx-region": "",
                            "signedIn": True,
                            "host": "www.aliexpress.us",
                        }
                    ),
                },
            )

        if not api_result.get("success"):
            return {"error": f"API call failed: {api_result.get('error')}"}

        # Extract seller data
        seller_data = extractor.extract_core_seller_fields(api_result)

        if seller_data.get("extraction_metadata", {}).get("extraction_success"):
            return {
                "success": True,
                "seller_data": seller_data,
                "product_id": product_id,
            }
        else:
            return {"error": "Failed to extract seller data from API response"}

    except Exception as e:
        return {"error": f"Exception occurred: {str(e)}"}


def update_product_with_seller_data(
    product: Dict[str, Any], seller_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update a product dictionary with seller data.

    Args:
        product: Original product dictionary
        seller_data: Extracted seller data

    Returns:
        Updated product dictionary
    """
    updated_product = product.copy()

    # Map seller data to product fields
    if "seller_name" in seller_data:
        updated_product["Store Name"] = seller_data["seller_name"]

    if "seller_profile_url" in seller_data:
        updated_product["Store URL"] = seller_data["seller_profile_url"]

        # Try to extract Store ID from URL
        import re

        store_id_match = re.search(
            r"sellerAdminSeq=([A-Z0-9]+)", seller_data["seller_profile_url"]
        )
        if store_id_match:
            updated_product["Store ID"] = store_id_match.group(1)
        else:
            # Try alternative patterns
            store_id_match = re.search(
                r"store/(\d+)", seller_data["seller_profile_url"]
            )
            if store_id_match:
                updated_product["Store ID"] = store_id_match.group(1)

    return updated_product


def is_seller_data_missing(product: Dict[str, Any]) -> bool:
    """
    Check if a product is missing seller data.

    Returns True if Store Name is null, empty, missing, or "null" string
    """
    store_name = product.get("Store Name")

    # Check for various "empty" conditions
    return (
        store_name is None
        or store_name == "null"
        or store_name == ""
        or (isinstance(store_name, str) and store_name.strip() == "")
    )


def find_failed_products(products: List[Dict[str, Any]]) -> List[int]:
    """
    Find indices of products that need retry.

    Returns list of indices where seller data is missing
    """
    failed_indices = []
    for i, product in enumerate(products):
        if is_seller_data_missing(product):
            failed_indices.append(i)
    return failed_indices


def populate_initial_seller_data(
    products: List[Dict[str, Any]],
    client: EnhancedAliExpressClient,
    extractor: CoreSellerExtractor,
    manual_cookie: Optional[str] = None,
    delay: float = 1.0,
) -> tuple[List[Dict[str, Any]], int, int]:
    """
    Populate seller data for all products.

    Returns:
        (updated_products, success_count, error_count)
    """
    updated_products = []
    success_count = 0
    error_count = 0

    for i, product in enumerate(products, 1):
        product_url = product.get("Product URL")
        product_id = product.get("Product ID")

        print(f"[{i}/{len(products)}] Processing: {product_id}")

        if not product_url:
            print(f"  ⚠️  No Product URL found, skipping")
            updated_products.append(product)
            error_count += 1
            continue

        # Check if seller data is already populated
        if (
            product.get("Store Name")
            and product.get("Store Name") != "null"
            and product.get("Store Name") is not None
        ):
            print(f"  ✅ Seller data already exists, skipping")
            updated_products.append(product)
            success_count += 1
            continue

        # Get seller data
        result = get_seller_data_for_product(
            product_url, client, extractor, manual_cookie
        )

        if result.get("success"):
            # Update product with seller data
            updated_product = update_product_with_seller_data(
                product, result["seller_data"]
            )
            updated_products.append(updated_product)
            success_count += 1

            store_name = result["seller_data"].get("seller_name", "Unknown")
            print(f"  ✅ Success: {store_name}")
        else:
            # Keep original product if extraction failed
            updated_products.append(product)
            error_count += 1
            print(f"  ❌ Error: {result.get('error', 'Unknown error')}")

        # Add delay between requests to be respectful
        if i < len(products):  # Don't delay after the last item
            time.sleep(delay)

    return updated_products, success_count, error_count


def retry_failed_seller_data(
    products: List[Dict[str, Any]],
    client: EnhancedAliExpressClient,
    extractor: CoreSellerExtractor,
    manual_cookie: Optional[str] = None,
    delay: float = 2.0,
    max_retries: int = 3,
) -> tuple[List[Dict[str, Any]], int, int]:
    """
    Retry seller data extraction for failed products.

    Returns:
        (updated_products, success_count, error_count)
    """
    failed_indices = find_failed_products(products)

    if not failed_indices:
        print("🎉 Great! All products already have seller data - nothing to retry")
        return products, 0, 0

    print(f"🔍 Found {len(failed_indices)} products needing retry:")
    for i, idx in enumerate(failed_indices[:5]):  # Show first 5
        product = products[idx]
        print(
            f"  [{idx + 1}] {product.get('Product ID', 'Unknown')} - {product.get('Title', 'Unknown')[:50]}..."
        )

    if len(failed_indices) > 5:
        print(f"  ... and {len(failed_indices) - 5} more")

    print()
    print("🚀 Starting retry process...")
    print("-" * 50)

    success_count = 0
    error_count = 0
    updated_products = products.copy()

    for i, failed_idx in enumerate(failed_indices, 1):
        product = products[failed_idx]
        product_url = product.get("Product URL")
        product_id = product.get("Product ID")

        print(f"[{i}/{len(failed_indices)}] Retrying: {product_id}")

        if not product_url:
            print(f"  ⚠️  No Product URL found, skipping")
            error_count += 1
            continue

        # Retry with multiple attempts
        retry_success = False
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"  🔄 Retry attempt {attempt + 1}/{max_retries}")
                time.sleep(delay * 2)  # Longer delay for retries

            # Get seller data
            result = get_seller_data_for_product(
                product_url, client, extractor, manual_cookie
            )

            if result.get("success"):
                # Update product with seller data
                updated_product = update_product_with_seller_data(
                    product, result["seller_data"]
                )
                updated_products[failed_idx] = updated_product
                success_count += 1

                store_name = result["seller_data"].get("seller_name", "Unknown")
                print(f"  ✅ Success: {store_name}")
                retry_success = True
                break
            else:
                error_msg = result.get("error", "Unknown error")
                if "RGV587_ERROR" in error_msg or "FAIL_SYS_USER_VALIDATE" in error_msg:
                    print(f"  ⚠️  Rate limited, will retry...")
                    continue
                else:
                    print(f"  ❌ Error: {error_msg}")
                    break

        if not retry_success:
            error_count += 1
            print(f"  ❌ Failed after {max_retries} attempts")

        # Add delay between products
        if i < len(failed_indices):
            time.sleep(delay)

    return updated_products, success_count, error_count


def main():
    """Main function for seller data population pipeline."""
    parser = argparse.ArgumentParser(
        description="Populate seller data for products in JSON file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s products.json
  %(prog)s products.json --output products_with_sellers.json
  %(prog)s products.json --retry --delay 3.0
  %(prog)s products.json --cookie "your_cookie_here"
  %(prog)s products.json --retry --max-retries 5
        """,
    )

    parser.add_argument("input_file", help="JSON file with product data")
    parser.add_argument(
        "--output", "-o", help="Output file (default: <input_file>_with_sellers.json)"
    )
    parser.add_argument(
        "--cookie",
        "-c",
        help="Manual cookie string (optional, uses automated cookies if not provided)",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Enable retry for failed products after initial population",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="Delay between retry requests in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts per product (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making requests",
    )

    args = parser.parse_args()

    input_file = args.input_file
    output_file = args.output or f"{Path(input_file).stem}_with_sellers.json"

    # Check if input file exists
    if not Path(input_file).exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)

    print(f"📁 Input file: {input_file}")
    print(f"📁 Output file: {output_file}")
    print(f"⏱️  Delay between requests: {args.delay}s")
    if args.retry:
        print(
            f"🔄 Retry enabled (delay: {args.retry_delay}s, max attempts: {args.max_retries})"
        )
    if args.cookie:
        print("🍪 Using manual cookie")
    else:
        print("🤖 Using automated cookies")
    print()

    # Load JSON data
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            products = json.load(f)
        print(f"✅ Loaded {len(products)} products from {input_file}")
    except Exception as e:
        print(f"❌ Error loading JSON file: {e}")
        sys.exit(1)

    if args.dry_run:
        missing_count = len(find_failed_products(products))
        print(f"🏃 Dry run mode - would process {len(products)} products")
        print(f"Products needing seller data: {missing_count}")
        if args.retry:
            print("Would retry failed products after initial population")
        return

    # Initialize clients
    client = EnhancedAliExpressClient()
    extractor = CoreSellerExtractor()

    # Phase 1: Initial population
    print("🚀 Phase 1: Initial seller data extraction...")
    print("=" * 50)

    updated_products, initial_success, initial_errors = populate_initial_seller_data(
        products, client, extractor, args.cookie, args.delay
    )

    print()
    print("📊 INITIAL RESULTS SUMMARY")
    print("-" * 30)
    print(f"Total products: {len(products)}")
    print(f"Successful extractions: {initial_success}")
    print(f"Failed extractions: {initial_errors}")
    print(f"Success rate: {initial_success / len(products) * 100:.1f}%")

    # Phase 2: Retry if enabled
    retry_success = 0
    retry_errors = 0

    if args.retry:
        print()
        print("🔄 Phase 2: Retry failed extractions...")
        print("=" * 40)

        updated_products, retry_success, retry_errors = retry_failed_seller_data(
            updated_products,
            client,
            extractor,
            args.cookie,
            args.retry_delay,
            args.max_retries,
        )

        if retry_success > 0 or retry_errors > 0:
            print()
            print("📊 RETRY RESULTS SUMMARY")
            print("-" * 25)
            print(f"Products attempted: {retry_success + retry_errors}")
            print(f"Successful retries: {retry_success}")
            print(f"Still failed: {retry_errors}")
            if retry_success + retry_errors > 0:
                print(
                    f"Retry success rate: {retry_success / (retry_success + retry_errors) * 100:.1f}%"
                )

    # Final summary
    total_success = initial_success + retry_success
    total_errors = (
        initial_errors + retry_errors - retry_success
    )  # Subtract retry_success to avoid double counting

    print()
    print("🎯 FINAL RESULTS SUMMARY")
    print("=" * 25)
    print(f"Total products: {len(products)}")
    print(f"Products with seller data: {total_success}")
    print(f"Products still missing data: {total_errors}")
    print(f"Overall completion: {total_success / len(products) * 100:.1f}%")

    # Save updated JSON
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(updated_products, f, indent=2, ensure_ascii=False)
        print(f"✅ Updated data saved to: {output_file}")

        if total_success > initial_success:
            print(
                f"🎉 Successfully populated seller data for {total_success} products!"
            )
            if args.retry and retry_success > 0:
                print(f"   Including {retry_success} recovered through retry process")

        if total_errors > 0:
            print(f"⚠️  {total_errors} products still need seller data")

    except Exception as e:
        print(f"❌ Error saving output file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
