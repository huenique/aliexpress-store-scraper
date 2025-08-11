#!/usr/bin/env python3
"""
Batch Seller Processor
Processes each product in the JSON file and extracts seller information using enhanced_cli.py
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


class BatchSellerProcessor:
    def __init__(self, input_file: str, cookie: Optional[str] = None):
        self.input_file = input_file
        self.cookie = cookie
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
        """Check if token has expired"""
        return "FAIL_SYS_TOKEN_EXOIRED::令牌过期" in stderr or "令牌过期" in stderr

    def _prompt_for_new_cookie(self):
        """Prompt user for new cookie string"""
        print("\n" + "=" * 80)
        print("🔴 TOKEN EXPIRED - COOKIE UPDATE REQUIRED")
        print("=" * 80)
        print("The current cookie has expired. Please provide a new cookie string.")
        print(
            "You can get this from your browser's developer tools (F12 > Application > Cookies)"
        )
        print("\nPaste the new cookie string below:")
        print("-" * 40)

        new_cookie = input().strip()

        if not new_cookie:
            print("❌ No cookie provided. Exiting...")
            sys.exit(1)

        self.cookie = new_cookie
        print("✅ Cookie updated successfully!")
        print("-" * 80)
        return new_cookie

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

    def process_all(self) -> None:
        """Process all products"""
        products: List[Dict[str, Any]] = self._load_products()
        if not products:
            return

        total = len(products)
        successful = 0
        failed = 0
        token_expired_count = 0

        print(f"\n🚀 Starting batch processing of {total} products...")
        print(f"📊 Progress will be streamed to: {self.output_csv}")
        print("-" * 60)

        for i, product in enumerate(products, 1):
            product_id: str = product.get("Product ID", "")

            if not product_id:
                print(f"⚠️  [{i}/{total}] Skipping product with missing ID")
                continue

            # Run CLI command with retry logic for token expiration
            max_retries = 2
            retry_count = 0

            while retry_count < max_retries:
                result = self._run_cli_command(product_id, self.cookie)

                # Check for token expiration
                if result["returncode"] != 0 and self._check_token_expired(
                    result["stderr"]
                ):
                    token_expired_count += 1
                    print(
                        f"🔴 [{i}/{total}] Token expired for Product ID: {product_id}"
                    )

                    if retry_count < max_retries - 1:
                        self._prompt_for_new_cookie()
                        retry_count += 1
                        continue
                    else:
                        print(
                            f"❌ [{i}/{total}] Max retries reached for Product ID: {product_id}"
                        )
                        break

                # Process result
                if result["returncode"] == 0:
                    # Parse seller data from output
                    seller_data = self._parse_cli_output(result["stdout"])

                    if seller_data:
                        combined_data = {**product, **seller_data}
                        self.results.append(combined_data)
                        self._append_to_csv(product, seller_data, "Success")
                        successful += 1
                        print(
                            f"✅ [{i}/{total}] Success: {product_id} - {product.get('Title', '')[:50]}..."
                        )
                    else:
                        self.failed_products.append(
                            {
                                "product": product,
                                "error": "Could not parse seller data from output",
                                "output": result["stdout"],
                                "stderr": result["stderr"],
                            }
                        )
                        self._append_to_csv(product, None, "Parse Error")
                        failed += 1
                        print(f"⚠️  [{i}/{total}] Parse Error: {product_id}")
                else:
                    # Command failed
                    self.failed_products.append(
                        {
                            "product": product,
                            "error": result["stderr"],
                            "output": result["stdout"],
                            "returncode": result["returncode"],
                        }
                    )
                    self._append_to_csv(product, None, "CLI Error")
                    failed += 1
                    print(
                        f"❌ [{i}/{total}] Failed: {product_id} - {result['stderr'][:100]}..."
                    )

                break  # Exit retry loop if not token expiration

            # Small delay between requests
            time.sleep(1)

        # Save final results
        self._save_results()

        # Print summary
        print("\n" + "=" * 60)
        print("🎯 BATCH PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total Products: {total}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"🔴 Token Expired: {token_expired_count}")
        print(f"📈 Success Rate: {(successful / total) * 100:.1f}%")
        print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch process products for seller extraction"
    )
    parser.add_argument("input_file", help="Input JSON file with products")
    parser.add_argument("--cookie", help="Cookie string for authentication")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"❌ Input file not found: {args.input_file}")
        sys.exit(1)

    processor = BatchSellerProcessor(args.input_file, args.cookie)
    processor.process_all()


if __name__ == "__main__":
    main()
