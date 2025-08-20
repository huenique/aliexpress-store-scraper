#!/usr/bin/env python3
"""
AliExpress Store Scraper CLI Entry Point
========================================

Main entry point for running the AliExpress Store Scraper as a module.
Use: python -m aliexpress_store_scraper [command] [options]

Available commands:
- product: Scrape product information
- enhanced: Use enhanced CLI with automated cookies
- seller: Extract seller/store information
- store-network: Scrape store credentials and network data
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="aliexpress_store_scraper",
        description="AliExpress Store Scraper - Extract product and store data from AliExpress",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Basic product scraper
    product_parser = subparsers.add_parser("product", help="Basic product scraper")
    product_parser.add_argument("url_or_id", help="Product URL or ID")
    product_parser.add_argument("--cookie", help="Cookie string for authentication")
    product_parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )
    product_parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )

    # Enhanced CLI with automation
    enhanced_parser = subparsers.add_parser(
        "enhanced", help="Enhanced CLI with automated cookies"
    )
    enhanced_parser.add_argument("url_or_id", help="Product URL or ID")
    enhanced_parser.add_argument("--cookie", help="Manual cookie override")
    enhanced_parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )
    enhanced_parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )
    enhanced_parser.add_argument("--batch", help="Comma-separated list of product IDs")
    enhanced_parser.add_argument(
        "--test-automation", action="store_true", help="Test the automation system"
    )

    # Seller/Store scraper
    seller_parser = subparsers.add_parser(
        "seller", help="Extract seller/store information"
    )
    seller_parser.add_argument("store_id", help="Store ID to extract")
    seller_parser.add_argument("--output", help="Output file path")
    seller_parser.add_argument(
        "--format", choices=["json", "csv"], default="json", help="Output format"
    )

    # Store network scraper
    network_parser = subparsers.add_parser(
        "store-network", help="Scrape store credentials and network data"
    )
    network_parser.add_argument("--store-ids", help="File containing store IDs")
    network_parser.add_argument("--output", help="Output file path")
    network_parser.add_argument(
        "--concurrent", type=int, default=5, help="Number of concurrent requests"
    )

    # Seller data populator
    populate_parser = subparsers.add_parser(
        "populate-sellers", help="Populate seller data for products in JSON file"
    )
    populate_parser.add_argument("input_file", help="JSON file with product data")
    populate_parser.add_argument(
        "--output", "-o", help="Output file (default: <input_file>_with_sellers.json)"
    )
    populate_parser.add_argument(
        "--cookie", "-c", help="Manual cookie string (optional)"
    )
    populate_parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.0,
        help="Delay between requests in seconds",
    )
    populate_parser.add_argument(
        "--retry", action="store_true", help="Enable retry for failed products"
    )
    populate_parser.add_argument(
        "--retry-delay", type=float, default=2.0, help="Delay between retry requests"
    )
    populate_parser.add_argument(
        "--max-retries", type=int, default=3, help="Maximum retry attempts per product"
    )
    populate_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed"
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if args.command == "product":
        from aliexpress_store_scraper.cli.cli import main as product_main

        # Reconstruct sys.argv for the product CLI
        sys.argv = ["cli.py", args.url_or_id]
        if args.cookie:
            sys.argv.append(args.cookie)
        if args.json:
            sys.argv.append("--json")
        if args.verbose:
            sys.argv.append("--verbose")
        product_main()

    elif args.command == "enhanced":
        from aliexpress_store_scraper.cli.enhanced_cli import main as enhanced_main

        # Reconstruct sys.argv for the enhanced CLI
        sys.argv = ["enhanced_cli.py", args.url_or_id]
        if args.cookie:
            sys.argv.extend(["--cookie", args.cookie])
        if args.json:
            sys.argv.append("--json")
        if args.verbose:
            sys.argv.append("--verbose")
        if args.batch:
            sys.argv.extend(["--batch", args.batch])
        if args.test_automation:
            sys.argv.append("--test-automation")
        enhanced_main()

    elif args.command == "seller":
        from aliexpress_store_scraper.cli.core_seller_cli import main as seller_main

        # Reconstruct sys.argv for the seller CLI
        sys.argv = ["core_seller_cli.py", args.store_id]
        if args.output:
            sys.argv.extend(["--output", args.output])
        if args.format:
            sys.argv.extend(["--format", args.format])
        seller_main()

    elif args.command == "store-network":
        from aliexpress_store_scraper.cli.store_credentials_network_cli import (
            main as network_main,
        )

        # Reconstruct sys.argv for the network CLI
        sys.argv = ["store_credentials_network_cli.py"]
        if args.store_ids:
            sys.argv.extend(["--store-ids", args.store_ids])
        if args.output:
            sys.argv.extend(["--output", args.output])
        if args.concurrent:
            sys.argv.extend(["--concurrent", str(args.concurrent)])
        network_main()

    elif args.command == "populate-sellers":
        from aliexpress_store_scraper.processors.seller_data_populator import (
            main as populate_main,
        )

        # Reconstruct sys.argv for the seller data populator
        sys.argv = ["seller_data_populator.py", args.input_file]
        if args.output:
            sys.argv.extend(["--output", args.output])
        if args.cookie:
            sys.argv.extend(["--cookie", args.cookie])
        if args.delay:
            sys.argv.extend(["--delay", str(args.delay)])
        if args.retry:
            sys.argv.append("--retry")
        if args.retry_delay:
            sys.argv.extend(["--retry-delay", str(args.retry_delay)])
        if args.max_retries:
            sys.argv.extend(["--max-retries", str(args.max_retries)])
        if args.dry_run:
            sys.argv.append("--dry-run")
        populate_main()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
