#!/usr/bin/env python3
"""
Transform OCR Seller Results to CSV
==================================

Convert OCR-extracted seller contact information to CSV format that matches
the Seller_rows.csv structure.

This script takes OCR results JSON file (like ocr_results.json) and transforms
the seller contact information into CSV format compatible with Seller_rows.csv.

Usage:
    python transform_ocr_to_csv.py --ocr-results ocr_results.json --output sellers_from_ocr.csv
    python transform_ocr_to_csv.py --contact-info nike_100_seller_contact_info.json --output sellers_from_contact.csv

Features:
- Extracts email, phone, and address information from OCR results
- Maps to Seller_rows.csv column structure
- Generates unique seller UUIDs
- Sets appropriate default values for missing fields
- Handles both OCR results and contact info JSON formats
"""

import argparse
import csv
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {file_path}: {str(e)}")
        return {}


def get_csv_headers() -> List[str]:
    """Get the standard CSV headers matching Seller_rows.csv structure."""
    return [
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


def create_default_seller_row() -> Dict[str, Any]:
    """Create a seller row with default values."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    return {
        "seller_uuid": str(uuid.uuid4()),
        "seller_name": "null",
        "profile_photo_url": "null",
        "seller_profile_url": "null",
        "seller_rating": "null",
        "total_reviews": "null",
        "contact_methods": "[]",
        "email_address": "null",
        "phone_number": "null",
        "physical_address": "null",
        "verification_status": "Unverified",
        "seller_status": "New",
        "enforcement_status": "None",
        "map_compliance_status": "Compliant",
        "associated_listings": 0,
        "date_added": current_time,
        "last_updated": current_time,
        "blacklisted": "false",
        "counterfeiter": "false",
        "priority_seller": "false",
        "seller_note": "",
        "seller_id": "null",
        "admin_priority_seller": "false",
        "known_counterfeiter": "false",
        "seller_admin_stage": "NA",
        "seller_investigation": "NotStarted",
        "seller_stage": "NA",
        "seller_state": "Active",
    }


def transform_ocr_results_to_csv_rows(
    ocr_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Transform OCR results to CSV rows.

    Args:
        ocr_results: List of OCR result dictionaries

    Returns:
        List of CSV row dictionaries
    """
    csv_rows = []

    for result in ocr_results:
        if result.get("status") != "success":
            continue

        contact_info = result.get("contact_info", {})
        if not contact_info:
            continue

        # Extract store ID from image_id
        image_id = result.get("image_id", "")
        store_id = ""
        if "_" in image_id:
            store_id = image_id.split("_")[0]

        # Create base row with defaults
        row = create_default_seller_row()

        # Populate with OCR data
        row["seller_id"] = store_id if store_id else "null"
        row["seller_name"] = f"Store {store_id}" if store_id else "Unknown Store"

        # Extract contact information
        emails = contact_info.get("emails", [])
        phones = contact_info.get("phone_numbers", [])
        addresses = contact_info.get("addresses", [])

        # Populate contact fields
        if emails:
            row["email_address"] = emails[0]  # Use first email
            if len(emails) > 1:
                # Store additional emails in contact_methods
                contact_methods = [f"email:{email}" for email in emails[1:]]
                row["contact_methods"] = json.dumps(contact_methods)

        if phones:
            # Clean phone number (remove common formatting)
            phone = str(phones[0]).strip()
            row["phone_number"] = phone

        if addresses:
            # Use the most complete address (usually the longest)
            address = max(addresses, key=len) if addresses else ""
            row["physical_address"] = address.strip()

        # Set default verification status (always Unverified)
        confidence = contact_info.get("confidence_score", 0)
        row["verification_status"] = "Unverified"

        # Set default seller_note to empty string
        processing_time = result.get("processing_time", 0)
        row["seller_note"] = ""

        csv_rows.append(row)

    return csv_rows


def extract_stores_from_seller_data(
    seller_data: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Extract unique stores from seller population data.

    Args:
        seller_data: List of product entries with seller information

    Returns:
        Dictionary mapping store_id to store information
    """
    stores = {}

    for product in seller_data:
        if not isinstance(product, dict):
            continue

        store_id = product.get("Store ID")
        if not store_id:
            continue

        # Convert store_id to string for consistency
        store_id = str(store_id)

        if store_id not in stores:
            store_url = product.get("Store URL", "")
            if not store_url and store_id:
                store_url = f"https://www.aliexpress.com/store/{store_id}"

            stores[store_id] = {
                "store_id": store_id,
                "store_name": product.get("Store Name", "Unknown Store"),
                "store_url": store_url,
                "product_count": 0,
                "products": [],
            }

        # Track products for this store
        stores[store_id]["product_count"] += 1
        stores[store_id]["products"].append(
            {
                "product_id": product.get("Product ID"),
                "title": product.get("Title", "")[:50] + "..."
                if len(product.get("Title", "")) > 50
                else product.get("Title", ""),
                "price": product.get("Sale Price"),
            }
        )

    return stores


def merge_with_contact_info_data(
    stores_from_population: Dict[str, Dict[str, Any]], contact_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Merge store population data with contact information, avoiding duplicates.

    Args:
        stores_from_population: Stores extracted from seller population data
        contact_data: Contact information from OCR/pipeline results

    Returns:
        List of CSV row dictionaries
    """
    csv_rows = []
    stores_with_contact = contact_data.get("stores", {})

    # Process all unique stores
    all_store_ids = set(stores_from_population.keys()) | set(stores_with_contact.keys())

    for store_id in all_store_ids:
        # Create base row with defaults
        row = create_default_seller_row()

        # Basic store information (prefer population data for names/URLs)
        if store_id in stores_from_population:
            pop_store = stores_from_population[store_id]
            row["seller_id"] = store_id
            row["seller_name"] = pop_store["store_name"]
            row["seller_profile_url"] = pop_store["store_url"]
            row["associated_listings"] = pop_store["product_count"]

            # Create a note about products
            product_note = f"Products: {pop_store['product_count']}"
            if pop_store["products"]:
                sample_products = pop_store["products"][
                    :2
                ]  # Show up to 2 sample products
                product_list = ", ".join([p["title"] for p in sample_products])
                if pop_store["product_count"] > 2:
                    product_list += f" +{pop_store['product_count'] - 2} more"
                product_note += f" | Examples: {product_list}"
        else:
            # Store only found in contact data
            row["seller_id"] = store_id
            row["seller_name"] = f"Store {store_id}"
            row["seller_profile_url"] = f"https://www.aliexpress.com/store/{store_id}"
            product_note = "From contact extraction only"

        # Add contact information if available
        contact_note = ""
        if store_id in stores_with_contact:
            store_contact = stores_with_contact[store_id]
            contact_info = store_contact.get("contact_info", {})

            # Extract contact details
            emails = contact_info.get("emails", [])
            phones = contact_info.get("phone_numbers", [])
            addresses = contact_info.get("addresses", [])

            # Populate contact fields
            if emails:
                row["email_address"] = emails[0]
                if len(emails) > 1:
                    contact_methods = [f"email:{email}" for email in emails[1:]]
                    row["contact_methods"] = json.dumps(contact_methods)

            if phones:
                row["phone_number"] = str(phones[0]).strip()

            if addresses:
                row["physical_address"] = max(addresses, key=len).strip()

            # Set default verification status (always Unverified)
            avg_confidence = contact_info.get("average_confidence", 0)
            row["verification_status"] = "Unverified"

            # Contact extraction details
            contact_points = contact_info.get(
                "total_contact_points", len(emails) + len(phones) + len(addresses)
            )
            contact_note = (
                f" | Contact: confidence {avg_confidence}, points {contact_points}"
            )

            # Update product count from contact data if not from population
            if store_id not in stores_from_population:
                contact_product_count = store_contact.get("product_count", 0)
                row["associated_listings"] = contact_product_count

        # Set default seller_note to empty string
        row["seller_note"] = ""

        csv_rows.append(row)

    return csv_rows


def transform_contact_info_to_csv_rows(
    contact_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Transform seller contact info JSON to CSV rows (legacy function for compatibility).

    Args:
        contact_data: Seller contact info dictionary

    Returns:
        List of CSV row dictionaries
    """
    # Use the new merge function with empty population data
    return merge_with_contact_info_data({}, contact_data)


def transform_combined_data_to_csv_rows(
    seller_population_data: List[Dict[str, Any]], contact_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Transform combined seller population and contact info data to CSV rows.

    Args:
        seller_population_data: List of products with seller information
        contact_data: Seller contact info dictionary from OCR/pipeline results

    Returns:
        List of CSV row dictionaries
    """
    # Extract stores from population data
    stores_from_population = extract_stores_from_seller_data(seller_population_data)

    # Merge with contact information
    return merge_with_contact_info_data(stores_from_population, contact_data)
    """
    Transform seller contact info JSON to CSV rows.
    
    Args:
        contact_data: Seller contact info dictionary (from nike_100_seller_contact_info.json format)
        
    Returns:
        List of CSV row dictionaries
    """
    csv_rows = []

    stores = contact_data.get("stores", {})

    for store_id, store_data in stores.items():
        # Create base row with defaults
        row = create_default_seller_row()

        # Basic store information
        row["seller_id"] = store_id
        row["seller_name"] = f"Store {store_id}"

        # Contact information - extract from nested structure
        contact_info = store_data.get("contact_info", {})

        # Check if we have contact data
        has_contact_data = store_data.get("has_contact_data", False)
        if not has_contact_data:
            row["seller_note"] = ""
            csv_rows.append(row)
            continue

        # Extract contact details from the nested structure
        emails = contact_info.get("emails", [])
        phones = contact_info.get("phone_numbers", [])
        addresses = contact_info.get("addresses", [])

        # Also check if contact sources contain contact information
        contact_sources = store_data.get("contact_sources", [])

        # Try to extract from OCR-style results if embedded
        if not (emails or phones or addresses) and contact_sources:
            # Sometimes contact info is in contact_sources
            for source in contact_sources:
                if isinstance(source, dict):
                    if "emails" in source:
                        emails.extend(source["emails"])
                    if "phone_numbers" in source:
                        phones.extend(source["phone_numbers"])
                    if "addresses" in source:
                        addresses.extend(source["addresses"])

        # Populate contact fields
        if emails:
            row["email_address"] = emails[0]
            if len(emails) > 1:
                contact_methods = [f"email:{email}" for email in emails[1:]]
                row["contact_methods"] = json.dumps(contact_methods)

        if phones:
            row["phone_number"] = str(phones[0]).strip()

        if addresses:
            # Use the most complete address
            address = max(addresses, key=len) if addresses else ""
            row["physical_address"] = address.strip()

        # Set default verification status (always Unverified)
        avg_confidence = contact_info.get("average_confidence", 0)
        row["verification_status"] = "Unverified"

        # Add metadata
        product_count = store_data.get("product_count", 0)
        row["associated_listings"] = product_count

        contact_points = contact_info.get(
            "total_contact_points", len(emails) + len(phones) + len(addresses)
        )
        row["seller_note"] = ""

        csv_rows.append(row)

    return csv_rows


def write_csv_file(csv_rows: List[Dict[str, Any]], output_path: str) -> None:
    """Write CSV rows to file."""
    if not csv_rows:
        print("⚠️  No data to write to CSV")
        return

    headers = get_csv_headers()

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(csv_rows)

        print(f"✅ Successfully wrote {len(csv_rows)} rows to {output_path}")

    except Exception as e:
        print(f"❌ Error writing CSV file: {str(e)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Transform OCR seller results to CSV format"
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--ocr-results", help="Path to OCR results JSON file (e.g., ocr_results.json)"
    )
    input_group.add_argument(
        "--contact-info",
        help="Path to seller contact info JSON file (e.g., nike_100_seller_contact_info.json)",
    )
    input_group.add_argument(
        "--combined",
        nargs=2,
        metavar=("SELLER_DATA", "CONTACT_INFO"),
        help="Paths to seller population data and contact info files (e.g., --combined nike_100_with_sellers.json nike_100_seller_contact_info.json)",
    )

    parser.add_argument("--output", required=True, help="Output CSV file path")

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Determine input type and load data
    if args.ocr_results:
        print(f"📂 Loading OCR results from: {args.ocr_results}")
        data = load_json_file(args.ocr_results)

        if isinstance(data, list):
            csv_rows = transform_ocr_results_to_csv_rows(data)
            source_type = "OCR results"
        else:
            print("❌ OCR results file should contain a JSON array")
            return

    elif args.contact_info:
        print(f"📂 Loading seller contact info from: {args.contact_info}")
        data = load_json_file(args.contact_info)

        if isinstance(data, dict):
            csv_rows = transform_contact_info_to_csv_rows(data)
            source_type = "seller contact info"
        else:
            print("❌ Contact info file should contain a JSON object")
            return

    else:  # combined
        seller_data_path, contact_info_path = args.combined
        print(f"📂 Loading seller population data from: {seller_data_path}")
        print(f"📂 Loading contact info from: {contact_info_path}")

        seller_data = load_json_file(seller_data_path)
        contact_data = load_json_file(contact_info_path)

        if not isinstance(seller_data, list):
            print("❌ Seller population data file should contain a JSON array")
            return
        if not isinstance(contact_data, dict):
            print("❌ Contact info file should contain a JSON object")
            return

        csv_rows = transform_combined_data_to_csv_rows(seller_data, contact_data)
        source_type = "combined seller population + contact info"

    if args.verbose:
        print(f"\n📊 TRANSFORMATION SUMMARY")
        print("-" * 30)
        print(f"Source: {source_type}")
        print(f"Records transformed: {len(csv_rows)}")
        print(f"Output file: {args.output}")

        if csv_rows:
            # Count records with different types of contact info
            with_email = sum(
                1 for row in csv_rows if row.get("email_address") != "null"
            )
            with_phone = sum(1 for row in csv_rows if row.get("phone_number") != "null")
            with_address = sum(
                1 for row in csv_rows if row.get("physical_address") != "null"
            )

            print(f"\n📞 CONTACT INFO BREAKDOWN")
            print(f"Records with email: {with_email}")
            print(f"Records with phone: {with_phone}")
            print(f"Records with address: {with_address}")

            # Show verification status distribution
            verification_counts = {}
            for row in csv_rows:
                status = row.get("verification_status", "Unknown")
                verification_counts[status] = verification_counts.get(status, 0) + 1

            print(f"\n🔍 VERIFICATION STATUS")
            for status, count in verification_counts.items():
                print(f"{status}: {count} records")

            print(f"\n📋 Sample record:")
            sample = csv_rows[0]
            for key, value in sample.items():
                if (
                    value != "null"
                    and value != "[]"
                    and value is not False
                    and value != 0
                ):
                    print(f"   {key}: {value}")

    # Write to CSV
    write_csv_file(csv_rows, args.output)


if __name__ == "__main__":
    main()
