#!/usr/bin/env python3
"""
Unified Seller Pipeline CLI
==========================

Command-line interface for the unified seller information pipeline.
Combines store credential scraping with OCR-based contact extraction.

Usage Examples:
    # Process from JSON file with Store IDs
    python -m aliexpress_store_scraper.cli.unified_pipeline --json-file nike_products.json

    # Process specific store IDs directly
    python -m aliexpress_store_scraper.cli.unified_pipeline --store-ids 1104067221,1104783588

    # Custom configuration
    python -m aliexpress_store_scraper.cli.unified_pipeline \
        --json-file products.json \
        --output unified_results.json \
        --workers 8 \
        --captcha-retries 5 \
        --no-intermediate-files

Author: AI Assistant  
Date: August 2025
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List

from aliexpress_store_scraper.processors.unified_seller_pipeline import (
    UnifiedSellerPipeline,
)
from aliexpress_store_scraper.utils.logger import ScraperLogger


async def main():
    """Main CLI function for the unified seller pipeline."""

    parser = argparse.ArgumentParser(
        description="Unified seller information pipeline - combines store credential scraping with OCR contact extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --json-file nike_products.json
  %(prog)s --store-ids 1104067221,1104783588,1104096355
  %(prog)s --json-file products.json --output results.json --workers 8
  %(prog)s --json-file products.json --no-intermediate-files --output-dir results/
        """,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--json-file",
        type=str,
        help="JSON file containing 'Store ID' fields to process",
    )
    input_group.add_argument(
        "--store-ids",
        type=str,
        help="Comma-separated list of store IDs to process directly",
    )

    # Output options
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path (default: unified_results.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory for output files (default: current directory)",
    )

    # Processing options
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Maximum number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--captcha-retries",
        type=int,
        default=3,
        help="Maximum CAPTCHA retry attempts (default: 3)",
    )
    parser.add_argument(
        "--no-ocr-preprocessing",
        action="store_true",
        help="Disable OCR image preprocessing",
    )
    parser.add_argument(
        "--no-intermediate-files",
        action="store_true",
        help="Don't save intermediate results files",
    )
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Use Oxylabs proxy (requires OXYLABS_* environment variables)",
    )

    # Display options
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    # Set up output paths
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_file = args.output or "unified_results.json"
    if not Path(output_file).is_absolute():
        output_file = output_dir / output_file

    # Initialize logger
    logger = ScraperLogger("UnifiedPipelineCLI")

    if not args.quiet:
        print("🏪 Unified Seller Information Pipeline")
        print("=" * 45)
        print()

    try:
        # Initialize pipeline
        pipeline = UnifiedSellerPipeline(
            max_workers=args.workers,
            enable_ocr_preprocessing=not args.no_ocr_preprocessing,
            captcha_retry_limit=args.captcha_retries,
            use_proxy=args.proxy,
        )

        start_time = time.time()
        results = None

        # Process based on input type
        if args.json_file:
            if not args.quiet:
                print(f"📋 Processing stores from JSON file: {args.json_file}")

            results = await pipeline.process_stores_from_json(
                json_file=args.json_file,
                save_intermediate_results=not args.no_intermediate_files,
                output_dir=str(output_dir),
            )

        elif args.store_ids:
            store_ids = [
                sid.strip() for sid in args.store_ids.split(",") if sid.strip()
            ]

            if not args.quiet:
                print(f"📋 Processing {len(store_ids)} store IDs directly")

            results = await pipeline.process_stores_from_list(
                store_ids=store_ids,
                save_intermediate_results=not args.no_intermediate_files,
                output_dir=str(output_dir),
            )

        if not results:
            print("❌ No results obtained from pipeline")
            sys.exit(1)

        # Save final results
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            if not args.quiet:
                print(f"\n💾 Final results saved to: {output_file}")

        except Exception as e:
            logger.error(f"Failed to save results to {output_file}: {e}")
            sys.exit(1)

        # Display results summary
        if not args.quiet:
            pipeline.print_pipeline_results(results)

        # Display final stats
        total_time = time.time() - start_time
        summary = results.get("summary", {})

        if not args.quiet:
            print(f"\n🎯 FINAL SUMMARY")
            print("-" * 20)
            print(f"⏱️  Total processing time: {total_time:.1f} seconds")
            print(
                f"🏪 Stores processed: {results.get('pipeline_metadata', {}).get('total_stores_processed', 0)}"
            )
            print(f"📋 With credentials: {summary.get('stores_with_credentials', 0)}")
            print(f"📞 With contact info: {summary.get('stores_with_contact_info', 0)}")
            print(f"📊 Total contact points: {summary.get('total_contact_points', 0)}")
            print(f"💾 Results saved to: {output_file}")

        # Success/failure indication
        stores_processed = results.get("pipeline_metadata", {}).get(
            "total_stores_processed", 0
        )
        stores_with_data = summary.get("stores_with_credentials", 0)

        if stores_with_data == 0:
            print("\n⚠️  WARNING: No stores successfully processed")
            sys.exit(1)
        elif stores_with_data < stores_processed * 0.5:
            print(
                f"\n⚠️  WARNING: Low success rate ({stores_with_data}/{stores_processed})"
            )
            print("Consider checking CAPTCHA handling or network connectivity")

        print(f"\n✅ Pipeline completed successfully!")

    except KeyboardInterrupt:
        print("\n🛑 Pipeline interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def process_json_file(json_file: str, **kwargs) -> dict:
    """
    Convenience function for processing JSON file synchronously.

    Args:
        json_file: Path to JSON file with Store IDs
        **kwargs: Additional arguments for pipeline configuration

    Returns:
        Pipeline results dictionary
    """
    pipeline = UnifiedSellerPipeline(**kwargs)
    return asyncio.run(pipeline.process_stores_from_json(json_file))


def process_store_ids(store_ids: List[str], **kwargs) -> dict:
    """
    Convenience function for processing store IDs synchronously.

    Args:
        store_ids: List of store IDs to process
        **kwargs: Additional arguments for pipeline configuration

    Returns:
        Pipeline results dictionary
    """
    pipeline = UnifiedSellerPipeline(**kwargs)
    return asyncio.run(pipeline.process_stores_from_list(store_ids))


if __name__ == "__main__":
    asyncio.run(main())
