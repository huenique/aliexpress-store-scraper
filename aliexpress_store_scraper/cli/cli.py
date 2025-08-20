#!/usr/bin/env python3
"""
AliExpress CLI Scraper
=====================

Command-line interface for the AliExpress product scraper.
Extract product data by providing a product URL and cookie.

Usage:
    python cli.py <product_url> <cookie>
    python cli.py --help

Examples:
    python cli.py "https://www.aliexpress.us/item/3256809096800275.html" "cookie_string"
    python cli.py --product-id 3256809096800275 --cookie "cookie_string"
    python cli.py -u "https://aliexpress.com/item/123.html" -c "cookie" --json
    python cli.py --url "https://aliexpress.com/item/123.html" --cookie "cookie" --verbose
"""

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional

from aliexpress_store_scraper.clients.aliexpress_client import AliExpressClient


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

    return "\n".join(output)


def format_output_json(product_data: Dict[str, Any], pretty: bool = True) -> str:
    """Format product data as JSON."""
    if pretty:
        return json.dumps(product_data, indent=2, ensure_ascii=False)
    else:
        return json.dumps(product_data, ensure_ascii=False)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AliExpress Product Scraper CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://www.aliexpress.us/item/3256809096800275.html" "your_cookie_here"
  %(prog)s --product-id 3256809096800275 --cookie "your_cookie_here"
  %(prog)s -u "https://aliexpress.com/item/123.html" -c "cookie" --json
  %(prog)s --url "https://aliexpress.com/item/123.html" --cookie "cookie" --verbose

Cookie format example:
  "_m_h5_tk=token_here_1234567890; other=cookies; ..."

To get a fresh cookie:
  1. Go to www.aliexpress.us in your browser
  2. Open DevTools (F12) → Network tab
  3. Refresh the page and find any request
  4. Copy the entire 'Cookie' header value
        """,
    )

    # Positional arguments (for quick usage)
    parser.add_argument("url", nargs="?", help="AliExpress product URL or product ID")
    parser.add_argument("cookie", nargs="?", help="Cookie string from your browser")

    # Named arguments (more explicit)
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
        "-c", "--cookie", dest="cookie_string", help="Cookie string from your browser"
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

    # Parse arguments
    args = parser.parse_args()

    # Determine product URL/ID
    product_input = args.url or args.product_url or args.product_id
    if not product_input:
        parser.error("Please provide a product URL or ID")

    # Determine cookie
    cookie = args.cookie or args.cookie_string
    if not cookie:
        parser.error("Please provide a cookie string")

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
        print(f"🍪 Cookie length: {len(cookie)} characters", file=sys.stderr)
        print("🚀 Fetching product data...", file=sys.stderr)
        print(file=sys.stderr)

    try:
        # Initialize client and fetch data
        client = AliExpressClient()
        product_data = client.get_product(product_id, cookie)

        # Output results
        if args.raw:
            print(json.dumps(product_data, indent=2, ensure_ascii=False))
        elif args.json or args.pretty_json:
            print(format_output_json(product_data, pretty=True))
        else:
            print(format_output_text(product_data, verbose=args.verbose))

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
