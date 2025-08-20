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
- populate-sellers: Populate seller data for products in JSON file
- unified-pipeline: Complete seller info pipeline (credentials + OCR contact extraction)
- brand-to-seller: Complete pipeline from brand scan to seller contact info
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
    network_parser.add_argument("--store-ids", help="Comma-separated store IDs")
    network_parser.add_argument(
        "--file", help="File containing store IDs (one per line)"
    )
    network_parser.add_argument(
        "--json-file", help="JSON file containing objects with 'Store ID' field"
    )
    network_parser.add_argument("--output", help="Output file path")

    # Unified seller pipeline
    unified_parser = subparsers.add_parser(
        "unified-pipeline",
        help="Complete seller info pipeline (credentials + OCR contact extraction)",
    )
    unified_input_group = unified_parser.add_mutually_exclusive_group(required=True)
    unified_input_group.add_argument(
        "--json-file", help="JSON file containing 'Store ID' fields"
    )
    unified_input_group.add_argument(
        "--store-ids", help="Comma-separated store IDs to process directly"
    )
    unified_parser.add_argument("--output", help="Output JSON file path")
    unified_parser.add_argument("--output-dir", help="Directory for output files")
    unified_parser.add_argument(
        "--workers", type=int, default=4, help="Maximum parallel workers"
    )
    unified_parser.add_argument(
        "--captcha-retries", type=int, default=3, help="Maximum CAPTCHA retry attempts"
    )
    unified_parser.add_argument(
        "--no-ocr-preprocessing",
        action="store_true",
        help="Disable OCR image preprocessing",
    )
    unified_parser.add_argument(
        "--no-intermediate-files",
        action="store_true",
        help="Don't save intermediate results",
    )
    unified_parser.add_argument(
        "--proxy",
        action="store_true",
        help="Use Oxylabs proxy (requires OXYLABS_* environment variables)",
    )
    unified_parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )
    unified_parser.add_argument(
        "--quiet", action="store_true", help="Suppress progress output"
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

    # Brand-to-seller complete pipeline
    brand_parser = subparsers.add_parser(
        "brand-to-seller",
        help="Complete pipeline: brand scan → seller info → contact extraction",
    )
    brand_parser.add_argument(
        "brand_scan_file",
        help="Brand scan JSON file (e.g., nike_100.json) with Product URLs",
    )
    brand_parser.add_argument(
        "--output",
        help="Output file for complete results (default: <input>_seller_contact_info.json)",
    )
    brand_parser.add_argument(
        "--proxy",
        action="store_true",
        help="Use proxy for requests (requires OXYLABS_* environment variables)",
    )
    brand_parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between requests during seller population (default: 2.0)",
    )
    brand_parser.add_argument(
        "--retry-delay",
        type=float,
        default=3.0,
        help="Delay between retry attempts (default: 3.0)",
    )
    brand_parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts for failed seller extractions (default: 3)",
    )
    brand_parser.add_argument("--cookie", help="Manual cookie string for API requests")
    brand_parser.add_argument(
        "--no-intermediates",
        action="store_true",
        help="Don't save intermediate results (seller data, credentials, OCR)",
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
        import asyncio

        from aliexpress_store_scraper.cli.store_credentials_network_cli import (
            main as network_main,
        )

        # Reconstruct sys.argv for the network CLI
        sys.argv = ["store_credentials_network_cli.py"]
        if args.store_ids:
            sys.argv.extend(["--store-ids", args.store_ids])
        if args.file:
            sys.argv.extend(["--file", args.file])
        if args.json_file:
            sys.argv.extend(["--json-file", args.json_file])
        if args.output:
            sys.argv.extend(["--output", args.output])
        asyncio.run(network_main())

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

    elif args.command == "brand-to-seller":
        import asyncio

        from aliexpress_store_scraper.processors.brand_to_seller_pipeline import (
            main as brand_main,
        )

        # Reconstruct sys.argv for the brand-to-seller pipeline
        sys.argv = ["brand_to_seller_pipeline.py", args.brand_scan_file]
        if args.output:
            sys.argv.extend(["--output", args.output])
        if args.proxy:
            sys.argv.append("--proxy")
        if args.delay:
            sys.argv.extend(["--delay", str(args.delay)])
        if args.retry_delay:
            sys.argv.extend(["--retry-delay", str(args.retry_delay)])
        if args.max_retries:
            sys.argv.extend(["--max-retries", str(args.max_retries)])
        if args.cookie:
            sys.argv.extend(["--cookie", args.cookie])
        if args.no_intermediates:
            sys.argv.append("--no-intermediates")
        asyncio.run(brand_main())

    elif args.command == "unified-pipeline":
        import asyncio

        from aliexpress_store_scraper.cli.unified_pipeline import main as unified_main

        # Reconstruct sys.argv for the unified pipeline CLI
        sys.argv = ["unified_pipeline.py"]
        if args.json_file:
            sys.argv.extend(["--json-file", args.json_file])
        if args.store_ids:
            sys.argv.extend(["--store-ids", args.store_ids])
        if args.output:
            sys.argv.extend(["--output", args.output])
        if args.output_dir:
            sys.argv.extend(["--output-dir", args.output_dir])
        if args.workers:
            sys.argv.extend(["--workers", str(args.workers)])
        if args.captcha_retries:
            sys.argv.extend(["--captcha-retries", str(args.captcha_retries)])
        if args.no_ocr_preprocessing:
            sys.argv.append("--no-ocr-preprocessing")
        if args.no_intermediate_files:
            sys.argv.append("--no-intermediate-files")
        if args.proxy:
            sys.argv.append("--proxy")
        if args.verbose:
            sys.argv.append("--verbose")
        if args.quiet:
            sys.argv.append("--quiet")
        asyncio.run(unified_main())

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
