#!/usr/bin/env python3
"""
CLI for AliExpress Store Credentials Network Scraper
===================================================

Command-line interface for scraping store credentials by capturing
network requests and extracting base64 images directly from API responses.

Usage:
    # Scrape specific store IDs
    python store_credentials_network_cli.py --store-ids "123456,789012,345678"

    # Scrape from text file
    python store_credentials_network_cli.py --file store_ids.txt

    # Scrape from JSON file with 'Store ID' field
    python store_credentials_network_cli.py --json-file nike_100_final.json

    # Demo mode with fake IDs
    python store_credentials_network_cli.py --demo

    # Custom settings with session persistence
    python store_credentials_network_cli.py --store-ids "123456,789012" --timeout 20000 --delay 2.0 --cookies-file my_session.json

Author: Enhanced CLI for network request interception with session persistence
Date: August 2025
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from aliexpress_store_scraper.processors.store_credentials_network_scraper import (
    StoreCredentialsNetworkScraper,
)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AliExpress Store Credentials Network Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --store-ids "123456,789012,345678"
  %(prog)s --file store_ids.txt --timeout 20000
  %(prog)s --json-file nike_100_final.json --delay 2.0
  %(prog)s --demo --delay 2.0 --retries 3
  %(prog)s --store-ids "123456" --output my_results.json --no-headless
        """,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--store-ids", type=str, help="Comma-separated list of store IDs to scrape"
    )
    input_group.add_argument(
        "--file", type=str, help="File containing store IDs (one per line)"
    )
    input_group.add_argument(
        "--json-file",
        type=str,
        help="JSON file containing objects with 'Store ID' field",
    )
    input_group.add_argument(
        "--demo", action="store_true", help="Run demo mode with sample store IDs"
    )

    # Scraper configuration
    parser.add_argument(
        "--timeout",
        type=int,
        default=30000,
        help="Page load timeout in milliseconds (default: 30000)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Maximum retry attempts per store (default: 3)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in non-headless mode (visible)",
    )
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Use Oxylabs proxy (requires OXYLABS_* environment variables)",
    )

    # Session options
    parser.add_argument(
        "--cookies-file",
        type=str,
        default="aliexpress_session_cookies.json",
        help="Path to JSON file for storing session cookies (default: aliexpress_session_cookies.json)",
    )

    # Output options
    parser.add_argument(
        "--output",
        type=str,
        default="store_credentials_network_results.json",
        help="Output JSON file (default: store_credentials_network_results.json)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    return parser.parse_args()


def load_store_ids_from_file(file_path: str) -> List[str]:
    """
    Load store IDs from a text file.

    Args:
        file_path: Path to file containing store IDs

    Returns:
        List of store IDs

    Raises:
        SystemExit: If file cannot be read or is empty
    """
    try:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ Error: File '{file_path}' does not exist")
            sys.exit(1)

        store_ids: List[str] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):  # Skip empty lines and comments
                    store_ids.append(line)

        if not store_ids:
            print(f"❌ Error: No store IDs found in '{file_path}'")
            sys.exit(1)

        return store_ids

    except Exception as e:
        print(f"❌ Error reading file '{file_path}': {e}")
        sys.exit(1)


def load_store_ids_from_json(file_path: str) -> List[str]:
    """
    Load store IDs from a JSON file containing objects with 'Store ID' field.

    Args:
        file_path: Path to JSON file containing objects with 'Store ID' field

    Returns:
        List of store IDs

    Raises:
        SystemExit: If file cannot be read, is empty, or doesn't contain valid data
    """
    try:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ Error: File '{file_path}' does not exist")
            sys.exit(1)

        store_ids: List[str] = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle different JSON structures
        if isinstance(data, list):
            # Array of objects
            for item in data:
                if (
                    isinstance(item, dict)
                    and "Store ID" in item
                    and item["Store ID"] is not None
                ):
                    store_id = str(item["Store ID"]).strip()
                    if store_id and store_id != "None" and store_id not in store_ids:
                        store_ids.append(store_id)
        elif (
            isinstance(data, dict)
            and "Store ID" in data
            and data["Store ID"] is not None
        ):
            # Single object
            store_id = str(data["Store ID"]).strip()
            if store_id and store_id != "None":
                store_ids.append(store_id)
        else:
            print(
                f"❌ Error: JSON file '{file_path}' does not contain objects with 'Store ID' field"
            )
            print(
                "   Expected format: array of objects with 'Store ID' field or single object with 'Store ID' field"
            )
            sys.exit(1)

        if not store_ids:
            print(f"❌ Error: No valid Store IDs found in '{file_path}'")
            sys.exit(1)

        # Remove duplicates while preserving order
        unique_store_ids = []
        seen = set()
        for store_id in store_ids:
            if store_id not in seen:
                unique_store_ids.append(store_id)
                seen.add(store_id)

        return unique_store_ids

    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in file '{file_path}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading JSON file '{file_path}': {e}")
        sys.exit(1)


def get_demo_store_ids() -> List[str]:
    """Get demo store IDs for testing."""
    return ["1234567890", "9876543210", "5555555555"]


def parse_store_ids(store_ids_str: str) -> List[str]:
    """
    Parse comma-separated store IDs string.

    Args:
        store_ids_str: Comma-separated store IDs

    Returns:
        List of store IDs
    """
    store_ids = [sid.strip() for sid in store_ids_str.split(",")]
    store_ids = [sid for sid in store_ids if sid]  # Remove empty strings
    return store_ids


def print_progress(current: int, total: int, store_id: str) -> None:
    """Print progress information."""
    percentage = (current / total) * 100
    print(
        f"📊 Progress: {current}/{total} ({percentage:.1f}%) - Processing store {store_id}"
    )


def print_results_summary(results: List[Dict[str, Any]]) -> None:
    """Print summary of scraping results."""
    total = len(results)
    successful = sum(1 for r in results if r.get("status") == "success")
    failed = total - successful

    total_api_calls = sum(len(r.get("network_data", {})) for r in results)
    total_images = sum(len(r.get("images", {})) for r in results)

    print(f"\n🎯 Network Scraping Summary:")
    print(f"   📋 Total stores: {total}")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print(f"   🌐 API calls captured: {total_api_calls}")
    print(f"   🖼️  Images extracted: {total_images}")

    if successful > 0:
        avg_apis = total_api_calls / successful if successful > 0 else 0
        avg_images = total_images / successful if successful > 0 else 0
        print(f"   📈 Avg API calls per successful store: {avg_apis:.1f}")
        print(f"   📈 Avg images per successful store: {avg_images:.1f}")

    print(f"   📊 Success rate: {(successful / total) * 100:.1f}%")

    # Show failed stores
    failed_stores = [r["store_id"] for r in results if r.get("status") != "success"]
    if failed_stores:
        print(f"   ⚠️  Failed stores: {', '.join(failed_stores)}")


async def main():
    """Main CLI function."""
    args = parse_arguments()

    # Determine store IDs to scrape
    if args.demo:
        store_ids = get_demo_store_ids()
        print("🧪 Running in demo mode with sample store IDs")
    elif args.file:
        store_ids = load_store_ids_from_file(args.file)
        print(f"📁 Loaded {len(store_ids)} store IDs from '{args.file}'")
    elif args.json_file:
        store_ids = load_store_ids_from_json(args.json_file)
        print(f"📄 Loaded {len(store_ids)} store IDs from JSON file '{args.json_file}'")
    else:
        store_ids = parse_store_ids(args.store_ids)
        print(f"📝 Parsed {len(store_ids)} store IDs from command line")

    if not store_ids:
        print("❌ Error: No store IDs provided")
        sys.exit(1)

    print(f"🎯 Store IDs to process: {', '.join(store_ids)}")

    # Validate arguments
    if args.timeout < 1000:
        print("❌ Error: Timeout must be at least 1000ms")
        sys.exit(1)

    if args.delay < 0:
        print("❌ Error: Delay cannot be negative")
        sys.exit(1)

    if args.retries < 1:
        print("❌ Error: Retries must be at least 1")
        sys.exit(1)

    # Create scraper
    scraper = StoreCredentialsNetworkScraper(
        headless=not args.no_headless,
        timeout=args.timeout,
        delay_between_requests=args.delay,
        max_retries=args.retries,
        use_proxy=args.proxy,
        cookies_file=args.cookies_file,
    )

    print(f"\n🚀 Starting network scraping with configuration:")
    print(f"   🌐 Headless mode: {not args.no_headless}")
    print(f"   ⏱️  Timeout: {args.timeout}ms")
    print(f"   ⏰ Delay between requests: {args.delay}s")
    print(f"   🔄 Max retries: {args.retries}")
    print(f"   🌐 Using proxy: {args.proxy}")
    print(f"   🍪 Cookies file: {args.cookies_file}")
    print(f"   📝 Output file: {args.output}")

    # Progress callback
    progress_callback = None if args.quiet else print_progress

    # Start scraping
    start_time = time.time()

    try:
        results = await scraper.scrape_store_credentials(
            store_ids, progress_callback=progress_callback
        )

        # Save results
        scraper.save_results(results, args.output)

        # Print summary
        if not args.quiet:
            print_results_summary(results)

            elapsed_time = time.time() - start_time
            print(f"\n⏱️  Total execution time: {elapsed_time:.2f} seconds")
            print(f"💾 Results saved to: {args.output}")

        # Exit with appropriate code
        successful = sum(1 for r in results if r.get("status") == "success")
        if successful == 0:
            print("\n❌ No stores were successfully scraped")
            sys.exit(1)
        elif successful < len(store_ids):
            print(f"\n⚠️  Some stores failed ({successful}/{len(store_ids)} successful)")
            sys.exit(2)
        else:
            print(f"\n🎉 All stores scraped successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
