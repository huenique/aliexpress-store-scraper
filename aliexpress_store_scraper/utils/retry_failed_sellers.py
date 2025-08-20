#!/usr/bin/env python3
"""
Retry Failed Seller Data Script
==============================

This script retries seller data extraction for products that failed in the initial run.
It only processes products where Store Name is null, empty, or missing.

Usage:
    python retry_failed_sellers.py <json_file> [options]

Examples:
    # Basic retry with automated cookies
    python retry_failed_sellers.py nike_100_with_sellers.json

    # Retry with manual cookie
    python retry_failed_sellers.py nike_100_with_sellers.json --cookie "your_cookie_here"

    # Retry with longer delays between requests
    python retry_failed_sellers.py nike_100_with_sellers.json --delay 3.0

    # Dry run to see which products would be retried
    python retry_failed_sellers.py nike_100_with_sellers.json --dry-run

    # Save to different output file
    python retry_failed_sellers.py nike_100_with_sellers.json --output nike_100_complete.json
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

        print(f"🔍 Retrying Product ID: {product_id}")

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


def main():
    """Main retry function."""
    parser = argparse.ArgumentParser(
        description="Retry seller data extraction for failed products",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s nike_100_with_sellers.json
  %(prog)s nike_100_with_sellers.json --cookie "your_cookie"
  %(prog)s nike_100_with_sellers.json --delay 2.0
  %(prog)s nike_100_with_sellers.json --dry-run
  %(prog)s nike_100_with_sellers.json --output nike_100_complete.json
        """,
    )

    parser.add_argument("input_file", help="JSON file with products to retry")
    parser.add_argument(
        "--output", "-o", help="Output file (default: <input_file>_retried.json)"
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
        default=2.0,
        help="Delay between requests in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which products would be retried without making requests",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts per product (default: 3)",
    )

    args = parser.parse_args()

    input_file = args.input_file
    output_file = args.output or f"{Path(input_file).stem}_retried.json"

    # Check if input file exists
    if not Path(input_file).exists():
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)

    print(f"📁 Input file: {input_file}")
    print(f"📁 Output file: {output_file}")
    print(f"⏱️  Delay between requests: {args.delay}s")
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

    # Find failed products
    failed_indices = find_failed_products(products)

    if not failed_indices:
        print("🎉 Great! All products already have seller data - nothing to retry")
        return

    print(f"🔍 Found {len(failed_indices)} products needing retry:")
    for i, idx in enumerate(failed_indices[:5]):  # Show first 5
        product = products[idx]
        print(
            f"  [{idx + 1}] {product.get('Product ID', 'Unknown')} - {product.get('Title', 'Unknown')[:50]}..."
        )

    if len(failed_indices) > 5:
        print(f"  ... and {len(failed_indices) - 5} more")

    print()

    if args.dry_run:
        print("🏃 Dry run mode - no requests will be made")
        print(f"Would retry {len(failed_indices)} products")
        return

    # Initialize clients
    client = EnhancedAliExpressClient()
    extractor = CoreSellerExtractor()

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
        for attempt in range(args.max_retries):
            if attempt > 0:
                print(f"  🔄 Retry attempt {attempt + 1}/{args.max_retries}")
                time.sleep(args.delay * 2)  # Longer delay for retries

            # Get seller data
            result = get_seller_data_for_product(
                product_url, client, extractor, args.cookie
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
            print(f"  ❌ Failed after {args.max_retries} attempts")

        # Add delay between products
        if i < len(failed_indices):
            time.sleep(args.delay)

    print()
    print("📊 RETRY RESULTS SUMMARY")
    print("-" * 25)
    print(f"Products attempted: {len(failed_indices)}")
    print(f"Successful retries: {success_count}")
    print(f"Still failed: {error_count}")
    print(f"Retry success rate: {success_count / len(failed_indices) * 100:.1f}%")

    # Calculate overall completion
    total_with_data = len(products) - len(failed_indices) + success_count
    print(
        f"Overall completion: {total_with_data}/{len(products)} ({total_with_data / len(products) * 100:.1f}%)"
    )

    # Save updated JSON
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(updated_products, f, indent=2, ensure_ascii=False)
        print(f"✅ Updated data saved to: {output_file}")

        if success_count > 0:
            print(
                f"🎉 Successfully recovered seller data for {success_count} additional products!"
            )

        if error_count > 0:
            print(f"⚠️  {error_count} products still need seller data")

    except Exception as e:
        print(f"❌ Error saving output file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
