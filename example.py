#!/usr/bin/env python3
"""
Example usage of the AliExpress client
=====================================

Shows how to use the reverse engineered AliExpress client to fetch product data.
"""

import json

from aliexpress_client import AliExpressClient


def basic_example():
    """Basic example of using the AliExpress client."""

    print("📦 AliExpress Client - Basic Example")
    print("=" * 40)

    # Initialize client (commented out to avoid unused variable warning)
    # client = AliExpressClient()

    # Example product ID
    product_id = "3256809096800275"

    # You need to provide a fresh cookie from your browser
    # Replace this with your actual cookie from AliExpress
    # cookie_string = "your_fresh_cookie_here"

    print(f"🎯 Product ID: {product_id}")
    print("🔗 URL: https://www.aliexpress.us/item/3256809096800275.html")
    print()
    print("⚠️  To use this example, you need a fresh cookie:")
    print("   1. Go to https://www.aliexpress.us")
    print("   2. Open DevTools (F12) → Network tab")
    print("   3. Refresh page, find any request")
    print("   4. Copy the entire 'Cookie' header value")
    print("   5. Replace 'your_fresh_cookie_here' with your real cookie")
    print()

    # Uncomment and use real cookie to test
    # client = AliExpressClient()
    # cookie_string = "your_fresh_cookie_here"
    # try:
    #     result = client.get_product(product_id, cookie_string)
    #
    #     if result['success']:
    #         print("✅ Success! Product data retrieved:")
    #         client.print_product_summary(result)
    #     else:
    #         print(f"❌ Error: {result['error']}")
    #
    # except Exception as e:
    #     print(f"❌ Exception: {e}")


def advanced_example():
    """Advanced example showing data extraction."""

    print("🚀 Advanced Example - Data Processing")
    print("=" * 40)

    client = AliExpressClient()

    # Example with actual working cookie (replace with fresh one)
    working_cookie = (
        "_m_h5_tk=998976f5bda3f9183f14daa31cbc84be_1754918131358; "
        "_m_h5_tk_enc=09a3caf1680838650ed4db88004911eb; "
        "# ... rest of your fresh cookie ..."
    )

    product_id = "3256809096800275"

    try:
        print(f"🔄 Fetching product {product_id}...")
        result = client.get_product(product_id, working_cookie)

        if result["success"]:
            print("✅ Data retrieved successfully!")

            # Extract specific data
            title = result.get("title", "N/A")
            price = result.get("price", {}).get("sale_price", "N/A")
            rating = result.get("rating", {}).get("score", "N/A")

            print(f"📝 Title: {title}")
            print(f"💰 Price: {price}")
            print(f"⭐ Rating: {rating}")

            # Save to JSON file
            with open("product_data.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("💾 Data saved to product_data.json")

        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
            if "EXPIRED" in str(result.get("error", "")):
                print("🔄 Cookie expired - get a fresh one from your browser")

    except Exception as e:
        print(f"❌ Exception: {e}")


def cli_recommendation():
    """Show how to use the CLI tool instead."""

    print("💡 Recommended: Use the CLI Tool")
    print("=" * 40)
    print("For easier usage, try the command-line interface:")
    print()
    print("# Basic usage")
    print('python cli.py "product_url" "your_cookie"')
    print()
    print("# JSON output")
    print('python cli.py --product-id 3256809096800275 --cookie "cookie" --json')
    print()
    print("# Verbose details")
    print('python cli.py -p 3256809096800275 -c "cookie" --verbose')
    print()
    print("# Get help")
    print("python cli.py --help")
    print()
    print("📖 See CLI_README.md for comprehensive documentation")


def show_capabilities():
    """Show what the client can extract."""

    print("🎯 What Can Be Extracted")
    print("=" * 40)
    print("✅ Complete product data:")
    print("   • Title, description, product ID")
    print("   • Pricing: sale price, original price, discounts")
    print("   • Ratings: star rating, total sales, reviews")
    print("   • Store: name, rating, location, seller history")
    print("   • Shipping: delivery times, costs, carriers")
    print("   • Variants: colors, sizes, configurations")
    print("   • Images: product photos, gallery")
    print("   • Technical: API trace IDs, timestamps")
    print()
    print("🔐 Technical Details:")
    print("   • Reverse engineered from AliExpress JavaScript")
    print("   • Uses real MTOP API endpoints")
    print("   • Proper MD5 signature generation")
    print("   • Cookie-based authentication")
    print("   • JSONP response parsing")


if __name__ == "__main__":
    basic_example()
    print("\n" + "=" * 60 + "\n")
    advanced_example()
    print("\n" + "=" * 60 + "\n")
    cli_recommendation()
    print("\n" + "=" * 60 + "\n")
    show_capabilities()

    print("\n🎉 AliExpress Client Ready! 🎉")
    print("🏆 100% Reverse Engineered Success!")
