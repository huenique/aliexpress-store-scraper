#!/usr/bin/env python3
"""
Core Seller Fields CLI
======================

Simple command-line tool to extract the 6 core seller fields from AliExpress products.

Available Fields:
1. ✅ Seller Name
2. ✅ Seller Profile Picture
3. ✅ Seller Profile URL
4. ✅ Seller Rating
5. ✅ Total Reviews
6. ✅ Country

Usage:
    python core_seller_cli.py <product_id> [--cookie "cookie_string"]
    python core_seller_cli.py --url "https://aliexpress.com/item/123.html"
    python core_seller_cli.py --demo

Examples:
    python core_seller_cli.py 3256809096800275
    python core_seller_cli.py --url "https://www.aliexpress.us/item/3256809096800275.html"
    python core_seller_cli.py 3256809096800275 --cookie "your_cookie_here"
    python core_seller_cli.py --demo  # Show sample extraction

Author: Core Seller CLI
Date: August 2025
"""

import argparse
import json
import re
import sys

from core_seller_extractor import CoreSellerExtractor
from enhanced_aliexpress_client import EnhancedAliExpressClient


def extract_product_id(url_or_id):
    """Extract product ID from URL or return if already an ID."""
    if url_or_id.isdigit():
        return url_or_id

    # Extract from various URL formats
    patterns = [
        r"/item/(\d+)\.html",
        r"/item/(\d+)",
        r"product/(\d+)",
        r"(\d{13,})",  # Long numeric ID
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return None


def get_seller_info(product_id, manual_cookie=None):
    """Get seller info using core fields extractor."""

    print(f"🔍 Extracting core seller fields for product: {product_id}")

    client = EnhancedAliExpressClient()
    extractor = CoreSellerExtractor()

    try:
        # Get API response
        if manual_cookie:
            print("🍪 Using manual cookie")
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
            print("🤖 Using automated cookies...")
            product_result = client.get_product_with_auto_cookies(product_id)
            if not product_result.get("success"):
                return {
                    "error": f"Failed to get product: {product_result.get('error')}"
                }

            # We need the raw API response, so make another call
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

        print("✅ API call successful")

        # Extract seller fields
        seller_data = extractor.extract_core_seller_fields(api_result)
        summary = extractor.extract_seller_summary(api_result)
        quality = extractor.validate_extraction_quality(seller_data)

        return {
            "success": True,
            "product_id": product_id,
            "seller_data": seller_data,
            "summary": summary,
            "quality": quality,
        }

    except Exception as e:
        return {"error": f"Extraction failed: {str(e)}"}


def print_results(result):
    """Print formatted results."""

    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return

    print("\n🎯 CORE SELLER FIELDS EXTRACTED")
    print("=" * 35)

    seller_data = result["seller_data"]
    quality = result["quality"]

    print(f"📦 Product ID: {result['product_id']}")
    print(f"🏆 Quality: {quality['quality']} ({quality['extraction_rate']})")
    print()

    # Print core fields
    print("👤 SELLER INFORMATION")
    print("-" * 25)

    field_labels = {
        "seller_name": "Name",
        "seller_profile_picture": "Profile Picture",
        "seller_profile_url": "Store URL",
        "seller_rating": "Rating",
        "total_reviews": "Total Reviews",
        "country": "Country",
    }

    for field, label in field_labels.items():
        if field in seller_data:
            value = seller_data[field]

            # Format specific fields
            if field == "seller_rating":
                value = f"{value}/100"
            elif field in ["seller_profile_picture", "seller_profile_url"]:
                if len(str(value)) > 70:
                    value = str(value)[:67] + "..."

            print(f"  {label:15}: {value}")

    # Show summary format
    print("\n📋 ORGANIZED SUMMARY")
    print("-" * 25)
    summary = result["summary"]

    for category, data in summary.items():
        if category != "available_fields" and isinstance(data, dict) and data:
            print(f"{category.replace('_', ' ').title()}:")
            for key, value in data.items():
                clean_key = key.replace("_", " ").title()
                clean_value = str(value)
                if len(clean_value) > 60:
                    clean_value = clean_value[:57] + "..."
                print(f"  • {clean_key}: {clean_value}")
            print()


def show_demo():
    """Show demo extraction with sample data."""

    print("🎭 CORE SELLER FIELDS DEMO")
    print("=" * 30)
    print()

    print("This tool extracts only the 6 confirmed available seller fields:")
    print("  ✅ Seller Name")
    print("  ✅ Seller Profile Picture")
    print("  ✅ Seller Profile URL")
    print("  ✅ Seller Rating")
    print("  ✅ Total Reviews")
    print("  ✅ Country")
    print()

    # Demo with sample data
    extractor = CoreSellerExtractor()

    sample_api = {
        "data": {
            "data": {
                "result": {
                    "SHOP_CARD_PC": {
                        "storeName": "TechWorld Store",
                        "logo": "https://ae-pic-a1.aliexpress-media.com/kf/demo.png",
                        "storeHomePage": "https://m.aliexpress.com/store/storeHome.htm?sellerAdminSeq=123456",
                        "sellerScore": "89",
                        "sellerTotalNum": "2156",
                        "sellerInfo": {"countryCompleteName": "China"},
                    }
                }
            }
        }
    }

    seller_data = extractor.extract_core_seller_fields(sample_api)
    summary = extractor.extract_seller_summary(sample_api)
    quality = extractor.validate_extraction_quality(seller_data)

    demo_result = {
        "success": True,
        "product_id": "DEMO",
        "seller_data": seller_data,
        "summary": summary,
        "quality": quality,
    }

    print_results(demo_result)

    print("\n💡 USAGE EXAMPLES")
    print("-" * 20)
    print("python core_seller_cli.py 3256809096800275")
    print("python core_seller_cli.py --url 'https://aliexpress.com/item/123.html'")
    print("python core_seller_cli.py 123456 --cookie 'your_cookie'")


def main():
    """Main CLI function."""

    parser = argparse.ArgumentParser(
        description="Extract core seller fields from AliExpress products",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 3256809096800275
  %(prog)s --url "https://www.aliexpress.us/item/123.html"
  %(prog)s 123456 --cookie "cookie_string"
  %(prog)s --demo
        """,
    )

    parser.add_argument("product_id", nargs="?", help="Product ID or URL")
    parser.add_argument("--url", help="Product URL")
    parser.add_argument("--cookie", help="Manual cookie string")
    parser.add_argument("--demo", action="store_true", help="Show demo extraction")

    args = parser.parse_args()

    # Handle demo mode
    if args.demo:
        show_demo()
        return

    # Get product ID
    product_input = args.url if args.url else args.product_id

    if not product_input:
        parser.print_help()
        sys.exit(1)

    product_id = extract_product_id(product_input)
    if not product_id:
        print(f"❌ Could not extract product ID from: {product_input}")
        sys.exit(1)

    # Extract seller info
    result = get_seller_info(product_id, args.cookie)
    print_results(result)


if __name__ == "__main__":
    main()
