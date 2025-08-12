#!/usr/bin/env python3
"""
Atomic Batch Seller Processor
Processes products in atomic batches where all products in a batch succeed or fail together.
Uses ThreadPoolExecutor for concurrent processing with proper error handling.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class AtomicBatchSellerProcessor:
    def __init__(
        self,
        input_file: str,
        cookie: Optional[str] = None,
        batch_size: int = 10,
        max_workers: int = 5,
    ):
        self.input_file = input_file
        self.cookie = cookie
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.results: List[Dict[str, Any]] = []
        self.failed_products: List[Dict[str, Any]] = []

        # Create output files with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_json = f"seller_data_{timestamp}.json"
        self.output_csv = f"seller_data_{timestamp}.csv"
        self.failed_json = f"failed_products_{timestamp}.json"

        # CSV headers matching Seller_rows.csv structure
        self.csv_headers: List[str] = [
            "seller_uuid",
            "seller_name",
            "profile_photo_url",
            "seller_profile_url",
            "seller_rating",
            "total_reviews",
            "contact_methods",
            "email_address",
            "phone_number",
            "physical_address",
            "verification_status",
            "seller_status",
            "enforcement_status",
            "map_compliance_status",
            "associated_listings",
            "date_added",
            "last_updated",
            "blacklisted",
            "counterfeiter",
            "priority_seller",
            "seller_note",
            "seller_id",
            "admin_priority_seller",
            "known_counterfeiter",
            "seller_admin_stage",
            "seller_investigation",
            "seller_stage",
            "seller_state",
        ]

        # Initialize CSV file
        self._init_csv_file()

    def _init_csv_file(self):
        """Initialize CSV file with headers"""
        with open(self.output_csv, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.csv_headers)

    def _load_products(self) -> List[Dict[str, Any]]:
        """Load products from JSON file"""
        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                products = json.load(f)
            print(f"✅ Loaded {len(products)} products from {self.input_file}")
            return products
        except Exception as e:
            print(f"❌ Error loading products: {e}")
            return []

    def _run_cli_command(
        self, product_id: str, cookie: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run enhanced_cli.py for a single product"""
        cmd: List[str] = [
            "uv",
            "run",
            "python",
            "enhanced_cli.py",
            "--product-id",
            product_id,
            "--seller-json",
        ]

        if cookie:
            cmd.extend(["--cookie", cookie])

        try:
            print(f"🔄 Processing Product ID: {product_id}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
            )

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Command timed out after 60 seconds",
                "returncode": -1,
            }
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "returncode": -1}

    def _parse_cli_output(self, output: str) -> Optional[Dict[str, Any]]:
        """Parse JSON output from CLI command"""
        try:
            output = output.strip()
            if output.startswith("{") and output.endswith("}"):
                return json.loads(output)

            # Look for JSON block in the stdout
            lines = output.split("\n")
            json_lines = []
            in_json_block = False

            for line in lines:
                line = line.strip()
                if line.startswith("{"):
                    in_json_block = True
                    json_lines = [line]
                elif in_json_block:
                    json_lines.append(line)
                    if line.endswith("}"):
                        json_str = "\n".join(json_lines)
                        return json.loads(json_str)

            return None
        except Exception as e:
            print(f"🔍 JSON Parse Debug - Error: {e}")
            print(f"🔍 JSON Parse Debug - Output: {output[:200]}...")
            return None

    def _check_token_expired(self, stderr: str) -> bool:
        """Check if the error indicates token expiration"""
        token_indicators = [
            "token expired",
            "authentication failed",
            "invalid token",
            "403",
            "unauthorized",
            "CSRF verification failed",
            "cookie expired",
            "login required",
        ]
        stderr_lower = stderr.lower()
        return any(indicator in stderr_lower for indicator in token_indicators)

    def _check_validation_error(self, stderr: str) -> bool:
        """Check if error indicates validation failure"""
        validation_indicators = [
            "validation error",
            "invalid product id",
            "product not found",
            "page not found",
            "404",
        ]
        stderr_lower = stderr.lower()
        return any(indicator in stderr_lower for indicator in validation_indicators)

    def _prompt_for_new_cookie(self):
        """Prompt user for new cookie when token expires"""
        print("\n" + "=" * 60)
        print("🍪 COOKIE UPDATE REQUIRED")
        print("=" * 60)
        print("The current authentication token has expired.")
        print("Please provide a new cookie to continue processing.")
        print("-" * 60)

        while True:
            try:
                new_cookie = input("Enter new cookie (or 'q' to quit): ").strip()

                if new_cookie.lower() == "q":
                    print("❌ Processing aborted by user.")
                    sys.exit(0)

                if new_cookie:
                    self.cookie = new_cookie
                    print("✅ Cookie updated successfully!")
                    break
                else:
                    print("⚠️  Please enter a valid cookie.")

            except KeyboardInterrupt:
                print("\n❌ Processing aborted by user.")
                sys.exit(0)

    def _process_single_product_atomic(
        self, product: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """Process a single product atomically. Returns (result, error)"""
        product_id: str = product.get("Product ID", "")

        if not product_id:
            return product, "Missing Product ID"

        # Run CLI command
        result = self._run_cli_command(product_id, self.cookie)

        # Check for critical errors that should fail the batch
        if result["returncode"] != 0:
            stderr = result["stderr"]

            # Token expiration - critical error
            if self._check_token_expired(stderr):
                return product, f"TOKEN_EXPIRED: {stderr}"

            # Validation errors - critical error
            if self._check_validation_error(stderr):
                return product, f"VALIDATION_ERROR: {stderr}"

            # Other errors - critical error
            return product, f"CLI_ERROR: {stderr}"

        # Parse seller data from successful output
        seller_data = self._parse_cli_output(result["stdout"])

        if seller_data:
            combined_data = {**product, **seller_data}
            return combined_data, None
        else:
            return product, "PARSE_ERROR: Could not parse seller data"

    def _process_atomic_batch(
        self, batch: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
        """Process a batch of products atomically"""
        batch_results: list[Dict[str, Any]] = []
        batch_errors: list[Dict[str, Any]] = []
        critical_error = None

        print(f"🔄 Processing atomic batch of {len(batch)} products...")

        with ThreadPoolExecutor(
            max_workers=min(self.max_workers, len(batch))
        ) as executor:
            # Submit all products in the batch
            future_to_product = {
                executor.submit(self._process_single_product_atomic, product): product
                for product in batch
            }

            # Collect results
            for future in as_completed(future_to_product):
                product = future_to_product[future]

                try:
                    result, error = future.result()

                    if error:
                        # Check for critical errors that should fail the entire batch
                        if error.startswith(("TOKEN_EXPIRED", "VALIDATION_ERROR")):
                            critical_error = error
                            batch_errors.append({"product": product, "error": error})
                        else:
                            batch_errors.append({"product": product, "error": error})
                    else:
                        batch_results.append(result)

                except Exception as e:
                    error_msg = f"EXCEPTION: {str(e)}"
                    critical_error = error_msg
                    batch_errors.append({"product": product, "error": error_msg})

        # Atomic behavior: if any product failed, entire batch fails
        if batch_errors:
            return (
                [],
                batch
                + [
                    error["product"]
                    for error in batch_errors
                    if error["product"] not in batch
                ],
                critical_error,
            )

        return batch_results, [], None

    def _process_and_save_batch_results(self, batch_results: List[Dict[str, Any]]):
        """Process and save successful batch results to CSV"""
        for result in batch_results:
            # Extract original product and seller data
            product_data: dict[str, Any] = {}
            seller_data: dict[str, Any] = {}

            # Separate product fields from seller fields based on known product fields
            product_fields = {
                "Product ID",
                "Title",
                "Sale Price",
                "Original Price",
                "Discount (%)",
                "Currency",
                "Rating",
                "Orders Count",
                "Store Name",
                "Store ID",
                "Store URL",
                "Product URL",
                "Image URL",
                "Brand",
            }

            for key, value in result.items():
                if key in product_fields:
                    product_data[key] = value
                else:
                    seller_data[key] = value

            # Append to CSV with seller data if available
            if seller_data:
                self._append_to_csv(product_data, seller_data, "Success")
            else:
                self._append_to_csv(product_data, None, "No Seller Data")

            # Add to results
            self.results.append(result)

    def _append_to_csv(
        self,
        product_data: Dict[str, Any],
        seller_data: Optional[Dict[str, Any]] = None,
        status: str = "Success",
    ) -> None:
        """Append a row to the CSV file using Seller_rows.csv structure"""
        if seller_data:
            # Use seller data directly since it matches the CSV structure
            row = [
                seller_data.get("seller_uuid", "null"),
                seller_data.get("seller_name", "null"),
                seller_data.get("profile_photo_url", "null"),
                seller_data.get("seller_profile_url", "null"),
                seller_data.get("seller_rating", "null"),
                seller_data.get("total_reviews", "null"),
                seller_data.get("contact_methods", "[]"),
                seller_data.get("email_address", "null"),
                seller_data.get("phone_number", "null"),
                seller_data.get("physical_address", "null"),
                seller_data.get("verification_status", "null"),
                seller_data.get("seller_status", "null"),
                seller_data.get("enforcement_status", "null"),
                seller_data.get("map_compliance_status", "null"),
                seller_data.get("associated_listings", "null"),
                seller_data.get("date_added", "null"),
                seller_data.get("last_updated", "null"),
                seller_data.get("blacklisted", "null"),
                seller_data.get("counterfeiter", "null"),
                seller_data.get("priority_seller", "null"),
                seller_data.get("seller_note", "null"),
                seller_data.get("seller_id", "null"),
                seller_data.get("admin_priority_seller", "null"),
                seller_data.get("known_counterfeiter", "null"),
                seller_data.get("seller_admin_stage", "null"),
                seller_data.get("seller_investigation", "null"),
                seller_data.get("seller_stage", "null"),
                seller_data.get("seller_state", "null"),
            ]
        else:
            # Fill with nulls if no seller data
            row = ["null"] * len(self.csv_headers)

        with open(self.output_csv, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(row)

    def _save_results(self):
        """Save results to JSON files"""
        # Save successful results
        with open(self.output_json, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        # Save failed products
        with open(self.failed_json, "w", encoding="utf-8") as f:
            json.dump(self.failed_products, f, indent=2, ensure_ascii=False)

        print(f"\n📁 Results saved to:")
        print(f"   • Success: {self.output_json} ({len(self.results)} products)")
        print(f"   • CSV: {self.output_csv}")
        print(f"   • Failed: {self.failed_json} ({len(self.failed_products)} products)")

    def process_all_atomic(self) -> None:
        """Process all products using atomic batch processing"""
        products: List[Dict[str, Any]] = self._load_products()
        if not products:
            return

        total = len(products)
        successful = 0
        failed = 0
        total_batches = (total + self.batch_size - 1) // self.batch_size

        print(f"\n🚀 Starting atomic batch processing of {total} products...")
        print(
            f"� Processing in batches of {self.batch_size} with {self.max_workers} workers"
        )
        print(f"�📊 Total batches: {total_batches}")
        print(f"📈 Progress will be streamed to: {self.output_csv}")
        print("-" * 60)

        # Process products in atomic batches
        for batch_idx in range(0, total, self.batch_size):
            batch_num = (batch_idx // self.batch_size) + 1
            batch = products[batch_idx : batch_idx + self.batch_size]

            print(f"\n📦 Batch {batch_num}/{total_batches} ({len(batch)} products)")
            print("-" * 40)

            # Process the atomic batch
            batch_results, batch_failures, critical_error = self._process_atomic_batch(
                batch
            )

            # If batch failed, retry up to 3 times before prompting for new cookie
            if batch_failures:
                retry_count = 0
                max_retries = 3

                # Check if this is a token expiration error that should prompt immediately
                token_expired = critical_error and "TOKEN_EXPIRED" in critical_error

                print(f"❌ Batch {batch_num} failed - {critical_error}")

                if token_expired:
                    print(
                        f"❌ Batch {batch_num} failed - token expired, prompting for new cookie"
                    )
                else:
                    print(f"❌ Batch {batch_num} failed - attempting retries")

                    # Retry logic for non-token errors
                    while retry_count < max_retries and batch_failures:
                        retry_count += 1
                        print(
                            f"🔄 Retry {retry_count}/{max_retries} for batch {batch_num}"
                        )
                        time.sleep(2)  # Brief delay before retry

                        batch_results, batch_failures, critical_error = (
                            self._process_atomic_batch(batch)
                        )

                        if not batch_failures:
                            print(
                                f"✅ Batch {batch_num} succeeded on retry {retry_count}!"
                            )
                            break
                        elif critical_error and "TOKEN_EXPIRED" in critical_error:
                            print(
                                f"❌ Token expired on retry {retry_count}, will prompt for new cookie"
                            )
                            token_expired = True
                            break
                        else:
                            print(
                                f"❌ Retry {retry_count} failed for batch {batch_num}"
                            )

                # If still failed after retries or token expired, prompt for action
                if batch_failures and (retry_count >= max_retries or token_expired):
                    if token_expired:
                        print(f"🍪 Token expired for batch {batch_num}")
                    else:
                        print(
                            f"❌ Batch {batch_num} failed after {max_retries} retries"
                        )

                    # Prompt for action
                    while True:
                        action = input(
                            f"\nBatch {batch_num} failed:\nChoose action:\n1. Update cookie and retry batch {batch_num}\n2. Skip batch {batch_num}\n3. Stop processing\nEnter choice (1/2/3): "
                        ).strip()

                        if action == "1":
                            self._prompt_for_new_cookie()
                            print(f"🔄 Retrying batch {batch_num} with new cookie...")
                            batch_results, batch_failures, critical_error = (
                                self._process_atomic_batch(batch)
                            )
                            if not batch_failures:
                                print(
                                    f"✅ Batch {batch_num} succeeded with new cookie!"
                                )
                                break
                            else:
                                print(
                                    f"❌ Batch {batch_num} still failed - try a different cookie or skip"
                                )
                                continue
                        elif action == "2":
                            print(f"⏩ Skipping batch {batch_num}")
                            batch_results = []
                            batch_failures = batch
                            break
                        elif action == "3":
                            print("🛑 Stopping processing")
                            self._save_results()
                            return
                        else:
                            print("⚠️  Invalid choice. Please enter 1, 2, or 3.")

            # Process successful results
            if batch_results:
                self._process_and_save_batch_results(batch_results)
                successful += len(batch_results)
                print(
                    f"✅ Batch {batch_num} completed successfully: {len(batch_results)} products"
                )

            # Process failed results
            if batch_failures:
                for failed_product in batch_failures:
                    self.failed_products.append(
                        {
                            "product": failed_product,
                            "error": "Batch failed atomically",
                            "batch_num": batch_num,
                            "critical_error": critical_error,
                        }
                    )
                failed += len(batch_failures)
                print(
                    f"❌ Batch {batch_num} failed atomically: {len(batch_failures)} products"
                )

            # Small delay between batches
            if batch_num < total_batches:
                time.sleep(2)

        # Save final results
        self._save_results()

        # Print summary
        print("\n" + "=" * 60)
        print("🎯 ATOMIC BATCH PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total Products: {total}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"� Total Batches: {total_batches}")
        print(f"📈 Success Rate: {(successful / total) * 100:.1f}%")
        print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atomic batch process products for seller extraction"
    )
    parser.add_argument("input_file", help="Input JSON file with products")
    parser.add_argument("--cookie", help="Cookie string for authentication")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of products to process in each atomic batch (default: 10)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Maximum number of concurrent workers per batch (default: 5)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"❌ Input file not found: {args.input_file}")
        sys.exit(1)

    processor = AtomicBatchSellerProcessor(
        args.input_file,
        args.cookie,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
    )
    processor.process_all_atomic()


if __name__ == "__main__":
    main()
