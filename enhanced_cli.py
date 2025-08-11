#!/usr/bin/env python3
"""
Enhanced AliExpress CLI Scraper with Cookie Automation
=====================================================

Command-line interface for the AliExpress product scraper with automated cookie generation.
Can extract product data with or without manual cookies using Playwright automation.

Usage:
    python enhanced_cli.py <product_url>  # Automated cookies
    python enhanced_cli.py <product_url> --cookie "manual_cookie"  # Manual cookies
    python enhanced_cli.py --help

Features:
- ✅ Automated cookie generation using Playwright
- ✅ Session caching (1-minute default validity)
- ✅ Manual cookie override option
- ✅ Batch processing support
- ✅ JSON and text output formats
- ✅ Verbose debugging mode
- ✅ Automatic retry with fresh cookies

Examples:
    python enhanced_cli.py "https://www.aliexpress.us/item/3256809096800275.html"
    python enhanced_cli.py --product-id 3256809096800275
    python enhanced_cli.py -u "https://aliexpress.com/item/123.html" --json
    python enhanced_cli.py --batch "id1,id2,id3" --verbose
    python enhanced_cli.py --test-automation  # Test the automation system
"""

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional

from enhanced_aliexpress_client import EnhancedAliExpressClient


def extract_product_id_from_url(url: str) -> Optional[str]:
    """
    Extract product ID from various AliExpress URL formats.

    Supported formats:
    - https://www.aliexpress.us/item/3256809096800275.html
    - https://www.aliexpress.com/item/3256809096800275.html
    - https://aliexpress.us/item/3256809096800275.html
    - aliexpress.com/item/3256809096800275.html
    - 3256809096800275 (direct product ID)
    """
    # If it's already just a product ID
    if url.isdigit():
        return url

    # Try to extract from URL
    patterns = [
        r"/item/(\d+)\.html",  # Standard format
        r"/item/(\d+)",  # Without .html
        r"item/(\d+)",  # Without leading slash
        r"/(\d+)\.html",  # Just ID with .html
        r"(\d{13,})",  # Long product ID pattern (13+ digits)
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def parse_batch_products(batch_string: str) -> List[str]:
    """
    Parse batch product IDs from various formats.

    Supported formats:
    - "id1,id2,id3"
    - "id1, id2, id3"
    - "id1\nid2\nid3"
    - "url1,url2,url3"
    """
    # Split by comma or newline
    items = re.split(r"[,\n]", batch_string)

    product_ids: List[str] = []
    for item in items:
        item = item.strip()
        if item:
            product_id = extract_product_id_from_url(item)
            if product_id:
                product_ids.append(product_id)
            else:
                print(f"⚠️ Could not extract product ID from: {item}", file=sys.stderr)

    return product_ids


def format_output_text(product_data: Dict[str, Any], verbose: bool = False) -> str:
    """Format product data as human-readable text."""
    if not product_data.get("success"):
        return f"❌ Error: {product_data.get('error', 'Unknown error')}"

    output: List[str] = []
    output.append("🎯 PRODUCT INFORMATION")
    output.append("=" * 50)
    output.append(f"📝 Title: {product_data['title']}")
    output.append(f"🆔 Product ID: {product_data['product_id']}")

    if product_data.get("price"):
        price = product_data["price"]
        output.append(
            f"💰 Price: {price['sale_price']} (was {price['original_price']} {price['currency']})"
        )

    if product_data.get("rating"):
        rating = product_data["rating"]
        output.append(f"⭐ Rating: {rating['score']} stars ({rating['total_sold']})")

    if product_data.get("store"):
        store = product_data["store"]
        output.append(
            f"🏪 Store: {store['name']} ({store['rating']}/100, {store['positive_rate']} positive)"
        )
        if verbose:
            output.append(f"    Country: {store['country']}")
            output.append(f"    Open since: {store['open_time']}")

    if product_data.get("shipping"):
        shipping = product_data["shipping"]
        output.append(
            f"🚚 Shipping: {shipping['delivery_days_min']}-{shipping['delivery_days_max']} days"
        )
        output.append(
            f"    Cost: {shipping['shipping_cost']} from {shipping['ship_from']} via {shipping['carrier']}"
        )

    if product_data.get("sku_options") and verbose:
        output.append(f"🎨 Available Options:")
        for option in product_data["sku_options"]:
            values = ", ".join(option["values"][:5])
            if len(option["values"]) > 5:
                values += f" (+ {len(option['values']) - 5} more)"
            output.append(f"    {option['name']}: {values}")

    output.append(f"🖼️ Images: {len(product_data.get('images', []))} available")

    if verbose:
        output.append(
            f"📊 Data sections available: {len(product_data.get('available_sections', []))}"
        )
        output.append(f"🔍 API Trace ID: {product_data.get('api_trace_id', 'N/A')}")

        # Show automation info
        if product_data.get("automation_used"):
            output.append("🤖 Automation info:")
            output.append(f"    Used automated cookies: Yes")
            output.append(
                f"    Cookies from cache: {product_data.get('cookies_from_cache', 'N/A')}"
            )
            if product_data.get("retry_attempted"):
                output.append("    Retry with fresh cookies: Yes")

    return "\n".join(output)


def format_batch_output_text(
    batch_results: Dict[str, Any], verbose: bool = False
) -> str:
    """Format batch processing results as human-readable text."""
    output: List[str] = []

    # Summary
    output.append("📊 BATCH PROCESSING RESULTS")
    output.append("=" * 50)
    output.append(f"Total requested: {batch_results['total_requested']}")
    output.append(f"Successful: {batch_results['successful']} ✅")
    output.append(f"Failed: {batch_results['failed_count']} ❌")
    output.append(
        f"Success rate: {(batch_results['successful'] / batch_results['total_requested'] * 100):.1f}%"
    )

    if batch_results.get("automation_used"):
        output.append("🤖 Used automated cookie generation")

    output.append("")

    # Successful products
    if batch_results["products"]:
        output.append("✅ SUCCESSFUL PRODUCTS:")
        output.append("-" * 25)
        for product_id, product_data in batch_results["products"].items():
            title = product_data.get("title", "N/A")[:50]
            price = product_data.get("price", {}).get("sale_price", "N/A")
            output.append(f"🎯 {product_id}: {title}... | Price: {price}")

    # Failed products
    if batch_results["failed"]:
        output.append("")
        output.append("❌ FAILED PRODUCTS:")
        output.append("-" * 18)
        for product_id, error_data in batch_results["failed"].items():
            error = error_data.get("error", "Unknown error")[:60]
            output.append(f"💥 {product_id}: {error}...")

    return "\n".join(output)


def format_output_json(data: Dict[str, Any], pretty: bool = True) -> str:
    """Format data as JSON."""
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    else:
        return json.dumps(data, ensure_ascii=False)


def handle_test_automation(
    client: EnhancedAliExpressClient, verbose: bool = False
) -> None:
    """Handle the automation testing command."""
    print("🧪 Testing Enhanced AliExpress Client Automation")
    print("=" * 52)
    print()

    test_results = client.test_automation()

    if verbose or not test_results["overall_success"]:
        print("📋 Detailed Test Results:")
        print(json.dumps(test_results, indent=2))

    if test_results["overall_success"]:
        print("🎉 All automation tests passed! System is ready for use.")
        sys.exit(0)
    else:
        print("⚠️ Some automation tests failed. See details above.")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced AliExpress Product Scraper CLI with Cookie Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fully automated (no cookies needed!)
  %(prog)s "https://www.aliexpress.us/item/3256809096800275.html"
  %(prog)s --product-id 3256809096800275

  # With manual cookies (bypass automation)
  %(prog)s "https://aliexpress.us/item/123.html" --cookie "your_cookie_here"
  
  # Batch processing
  %(prog)s --batch "3256809096800275,1234567890123,9876543210987"
  
  # JSON output
  %(prog)s -u "https://aliexpress.com/item/123.html" --json
  
  # Test automation system
  %(prog)s --test-automation

Cookie automation:
  - First run: Opens headless browser to collect cookies
  - Subsequent runs: Uses cached cookies (1-minute validity)
  - Automatic retry with fresh cookies on failure
  - Manual cookie override always available

Manual cookie format example:
  "_m_h5_tk=token_here_1234567890; other=cookies; ..."
        """,
    )

    # Main input methods
    parser.add_argument("url", nargs="?", help="AliExpress product URL or product ID")
    parser.add_argument(
        "-u",
        "--url",
        "--product-url",
        dest="product_url",
        help="AliExpress product URL or product ID",
    )
    parser.add_argument(
        "-p", "--product-id", help="Direct product ID (alternative to URL)"
    )
    parser.add_argument(
        "--batch",
        help="Comma-separated list of product IDs or URLs for batch processing",
    )

    # Cookie options
    parser.add_argument(
        "-c",
        "--cookie",
        dest="cookie_string",
        help="Manual cookie string (bypasses automation)",
    )
    parser.add_argument(
        "--force-fresh-cookies",
        action="store_true",
        help="Force generation of fresh cookies (ignore cache)",
    )
    parser.add_argument(
        "--cache-minutes",
        type=int,
        default=1,
        help="Cookie cache validity in minutes (default: 1)",
    )

    # Output options
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "--pretty-json",
        action="store_true",
        help="Output in pretty-printed JSON format",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed information"
    )
    parser.add_argument("--raw", action="store_true", help="Output raw API response")

    # Automation options
    parser.add_argument(
        "--test-automation",
        action="store_true",
        help="Test the cookie automation system",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window during automation (for debugging)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=1.0,
        help="Delay between batch requests in seconds (default: 1.0)",
    )

    # Parse arguments
    args = parser.parse_args()

    # Initialize enhanced client
    client = EnhancedAliExpressClient(
        cookie_cache_minutes=args.cache_minutes,
        auto_retry=True,
        headless_browser=not args.no_headless,
    )

    # Handle test automation
    if args.test_automation:
        handle_test_automation(client, args.verbose)
        return

    # Handle batch processing
    if args.batch:
        product_ids = parse_batch_products(args.batch)
        if not product_ids:
            print(
                "❌ Error: No valid product IDs found in batch input", file=sys.stderr
            )
            sys.exit(1)

        if args.verbose:
            print(
                f"🔍 Processing {len(product_ids)} products in batch mode",
                file=sys.stderr,
            )
            print(
                f"🍪 Cookie automation: {'Manual' if args.cookie_string else 'Automated'}",
                file=sys.stderr,
            )
            print("🚀 Starting batch processing...", file=sys.stderr)
            print(file=sys.stderr)

        try:
            batch_results = client.batch_get_products(
                product_ids,
                delay_seconds=args.batch_delay,
                manual_cookies=args.cookie_string,
            )

            # Output results
            if args.raw or args.json or args.pretty_json:
                print(format_output_json(batch_results, pretty=True))
            else:
                print(format_batch_output_text(batch_results, verbose=args.verbose))

            # Exit with appropriate code
            sys.exit(0 if batch_results["success"] else 1)

        except Exception as e:
            print(f"❌ Batch processing error: {e}", file=sys.stderr)
            if args.verbose:
                import traceback

                traceback.print_exc()
            sys.exit(1)

    # Single product processing
    product_input = args.url or args.product_url or args.product_id
    if not product_input:
        parser.error(
            "Please provide a product URL/ID or use --batch for multiple products"
        )

    # Extract product ID
    product_id = extract_product_id_from_url(product_input)
    if not product_id:
        print(
            f"❌ Error: Could not extract product ID from: {product_input}",
            file=sys.stderr,
        )
        print("Supported formats:", file=sys.stderr)
        print(
            "  - https://www.aliexpress.us/item/3256809096800275.html", file=sys.stderr
        )
        print("  - https://aliexpress.com/item/3256809096800275.html", file=sys.stderr)
        print("  - 3256809096800275 (direct product ID)", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"🔍 Extracted product ID: {product_id}", file=sys.stderr)
        if args.cookie_string:
            print(
                f"🍪 Using manual cookie ({len(args.cookie_string)} chars)",
                file=sys.stderr,
            )
        else:
            print("🤖 Using automated cookie generation", file=sys.stderr)
        print("🚀 Fetching product data...", file=sys.stderr)
        print(file=sys.stderr)

    try:
        # Get product data with enhanced client
        if args.force_fresh_cookies and not args.cookie_string:
            # Force fresh cookies by clearing cache first
            client.cookie_generator.clear_cache()

        product_data = client.get_product(product_id, args.cookie_string)

        # Output results
        if args.raw:
            print(format_output_json(product_data, pretty=True))
        elif args.json or args.pretty_json:
            print(format_output_json(product_data, pretty=True))
        else:
            print(format_output_text(product_data, verbose=args.verbose))

        # Show automation status in verbose mode
        if args.verbose and not args.cookie_string:
            print(file=sys.stderr)
            print("🤖 Automation Status:", file=sys.stderr)
            status = client.get_automation_status()
            for key, value in status.items():
                if key != "timestamp":
                    print(f"   {key}: {value}", file=sys.stderr)

        # Exit with appropriate code
        if product_data.get("success"):
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
