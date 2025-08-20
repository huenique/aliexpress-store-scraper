#!/usr/bin/env python3
"""
Core Seller Fields Extractor - AliExpress
=========================================

Simple seller information extraction focused on the 6 core available fields
from the mtop.aliexpress.pdp.pc.query API response.

Core Available Fields (6/12):
1. ✅ Seller Name - from SHOP_CARD_PC.storeName
2. ✅ Seller Profile Picture - from SHOP_CARD_PC.logo
3. ✅ Seller Profile URL - from SHOP_CARD_PC.storeHomePage
4. ✅ Seller Rating - from SHOP_CARD_PC.sellerScore
5. ✅ Total Reviews - from SHOP_CARD_PC.sellerTotalNum
6. ✅ Country - from SHOP_CARD_PC.sellerInfo.countryCompleteName

Usage:
    from core_seller_extractor import CoreSellerExtractor

    extractor = CoreSellerExtractor()
    seller_data = extractor.extract_core_seller_fields(api_response)

    # Returns only the 6 available fields with clean data
    print(seller_data)

Author: Core Seller Fields Module
Date: August 2025
"""

from typing import Any, Dict, List


class CoreSellerExtractor:
    """
    Simple extractor focusing on the 6 core seller fields available in AliExpress API.

    This class extracts only the confirmed available seller fields, providing
    clean, reliable data without N/A values or missing field placeholders.
    """

    def __init__(self):
        """Initialize the core seller extractor."""

        # The 6 core available fields from mtop API
        self.core_fields = {
            "seller_name": "SHOP_CARD_PC.storeName",
            "seller_profile_picture": "SHOP_CARD_PC.logo",
            "seller_profile_url": "SHOP_CARD_PC.sellerInfo.storeURL",
            "seller_rating": "SHOP_CARD_PC.benefitInfoList[store rating]",
            "total_reviews": "SHOP_CARD_PC.sellerTotalNum",
            "country": "SHOP_CARD_PC.sellerInfo.countryCompleteName",
        }

    def extract_core_seller_fields(
        self, api_response: Dict[str, Any], include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Extract the 6 core seller fields from API response.

        Args:
            api_response: Complete API response from mtop.aliexpress.pdp.pc.query
            include_metadata: Whether to include extraction metadata

        Returns:
            Dictionary with the 6 core seller fields (no N/A values)
        """
        if not self._validate_api_response(api_response):
            return self._create_error_response("Invalid API response format")

        try:
            result_data = api_response.get("data", {}).get("data", {}).get("result", {})
            shop_card_data = result_data.get("SHOP_CARD_PC", {})
            seller_info = shop_card_data.get("sellerInfo", {})

            # Extract the 6 core fields
            core_data: Dict[str, Any] = {}

            # 1. Seller Name
            seller_name = shop_card_data.get("storeName")
            if seller_name:
                core_data["seller_name"] = seller_name

            # 2. Seller Profile Picture
            profile_picture = shop_card_data.get("logo")
            if profile_picture:
                core_data["seller_profile_picture"] = profile_picture

            # 3. Seller Profile URL - Use storeURL from mtop API response and format it properly
            store_url = shop_card_data.get("sellerInfo", {}).get("storeURL")
            if store_url:
                # Format the URL properly (add https: if it starts with //)
                if store_url.startswith("//"):
                    core_data["seller_profile_url"] = "https:" + store_url
                else:
                    core_data["seller_profile_url"] = store_url

            # 4. Seller Rating - Extract from benefitInfoList where title is "store rating"
            benefit_info_list: List[Dict[str, Any]] = shop_card_data.get(
                "benefitInfoList", []
            )
            rating: Any = None
            for benefit in benefit_info_list:
                if benefit and benefit.get("title") == "store rating":
                    rating = benefit.get("value")
                    break

            if rating:
                # Convert to numeric if possible for easier processing
                try:
                    core_data["seller_rating"] = float(rating)
                except (ValueError, TypeError):
                    core_data["seller_rating"] = rating

            # 5. Total Reviews
            total_reviews = shop_card_data.get("sellerTotalNum")
            if total_reviews:
                # Convert to numeric if possible
                try:
                    core_data["total_reviews"] = int(total_reviews)
                except (ValueError, TypeError):
                    core_data["total_reviews"] = total_reviews

            # 6. Country
            country = seller_info.get("countryCompleteName")
            if country:
                core_data["country"] = country

            # Add metadata if requested
            if include_metadata:
                core_data["extraction_metadata"] = {
                    "extraction_success": True,
                    "fields_extracted": len(core_data),
                    "total_available_core_fields": 6,
                    "extraction_rate": f"{len(core_data) / 6 * 100:.1f}%",
                    "api_source": "mtop.aliexpress.pdp.pc.query",
                    "extracted_fields": list(core_data.keys()),
                }

            return core_data

        except Exception as e:
            return self._create_error_response(f"Extraction failed: {str(e)}")

    def extract_seller_summary(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract a clean seller summary with just the essential information.

        Args:
            api_response: Complete API response from mtop.aliexpress.pdp.pc.query

        Returns:
            Dictionary with essential seller information in a clean format
        """
        core_data = self.extract_core_seller_fields(
            api_response, include_metadata=False
        )

        if not core_data:
            return {"error": "No seller data could be extracted"}

        # Create a clean summary
        summary: Dict[str, Any] = {
            "seller_info": {},
            "contact_info": {},
            "reputation": {},
            "available_fields": len(core_data),
        }

        # Organize fields by category
        if "seller_name" in core_data:
            summary["seller_info"]["name"] = core_data["seller_name"]

        if "country" in core_data:
            summary["contact_info"]["country"] = core_data["country"]

        if "seller_profile_url" in core_data:
            summary["contact_info"]["store_url"] = core_data["seller_profile_url"]

        if "seller_profile_picture" in core_data:
            summary["seller_info"]["profile_picture"] = core_data[
                "seller_profile_picture"
            ]

        if "seller_rating" in core_data:
            summary["reputation"]["rating"] = core_data["seller_rating"]

        if "total_reviews" in core_data:
            summary["reputation"]["total_interactions"] = core_data["total_reviews"]

        return summary

    def get_field_mapping(self) -> Dict[str, str]:
        """
        Get the mapping of field names to their API source paths.

        Returns:
            Dictionary mapping field names to API paths
        """
        return self.core_fields.copy()

    def validate_extraction_quality(
        self, extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate the quality of extracted seller data.

        Args:
            extracted_data: Result from extract_core_seller_fields()

        Returns:
            Dictionary with quality assessment
        """
        if not extracted_data or "extraction_metadata" not in extracted_data:
            return {"quality": "Poor", "reason": "No extraction metadata available"}

        metadata = extracted_data["extraction_metadata"]
        fields_extracted = metadata.get("fields_extracted", 0)

        # Assess quality based on how many core fields were successfully extracted
        if fields_extracted >= 5:
            quality = "Excellent"
            message = f"Extracted {fields_extracted}/6 core fields"
        elif fields_extracted >= 4:
            quality = "Good"
            message = f"Extracted {fields_extracted}/6 core fields"
        elif fields_extracted >= 2:
            quality = "Fair"
            message = f"Extracted {fields_extracted}/6 core fields"
        else:
            quality = "Poor"
            message = f"Only extracted {fields_extracted}/6 core fields"

        return {
            "quality": quality,
            "message": message,
            "extraction_rate": metadata.get("extraction_rate", "0%"),
            "missing_fields": [
                field
                for field in self.core_fields.keys()
                if field not in extracted_data
            ],
            "recommendation": "Use all available fields for best seller profiling"
            if quality in ["Excellent", "Good"]
            else "Consider alternative data sources for missing fields",
        }

    def _validate_api_response(self, api_response: Dict[str, Any]) -> bool:
        """Validate that the API response has the expected structure."""
        try:
            result = api_response.get("data", {}).get("data", {}).get("result", {})
            return "SHOP_CARD_PC" in result
        except (AttributeError, TypeError):
            return False

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create a standardized error response."""
        return {
            "extraction_success": False,
            "error": error_message,
            "extraction_metadata": {
                "fields_extracted": 0,
                "total_available_core_fields": 6,
                "extraction_rate": "0%",
            },
        }


def demo_core_extraction():
    """Demonstrate core seller field extraction with sample data."""

    print("🎯 Core Seller Fields Demo")
    print("=" * 30)
    print()

    # Sample API response structure (from actual API analysis)
    sample_response: Dict[str, Any] = {
        "data": {
            "data": {
                "result": {
                    "SHOP_CARD_PC": {
                        "storeName": "TechGadgets Pro Store",
                        "logo": "https://ae-pic-a1.aliexpress-media.com/kf/example.png",
                        "storeURL": "https://m.aliexpress.com/store/storeHome.htm?sellerAdminSeq=123456789",
                        "sellerTotalNum": "1247",
                        "benefitInfoList": [
                            {"title": "# sold in 180 days ", "value": "100+"},
                            {"title": "positive reviews", "value": "100.0%"},
                            {"title": "store rating", "value": "4.5"},
                            {"title": "Communication", "value": "4.7"},
                        ],
                        "sellerInfo": {
                            "countryCompleteName": "United States",
                            "storeURL": "//www.aliexpress.com/store/1104278284",
                        },
                    }
                }
            }
        }
    }

    # Initialize extractor and extract data
    extractor = CoreSellerExtractor()

    print("🔍 Extracting core seller fields...")
    core_data = extractor.extract_core_seller_fields(sample_response)

    print(f"✅ Extraction completed!")
    print(
        f"Fields extracted: {core_data.get('extraction_metadata', {}).get('fields_extracted', 0)}/6"
    )
    print()

    print("📊 CORE SELLER DATA")
    print("-" * 25)
    for field, value in core_data.items():
        if field != "extraction_metadata":
            display_field = field.replace("_", " ").title()
            # Truncate long URLs for display
            display_value = str(value)
            if len(display_value) > 60:
                display_value = display_value[:57] + "..."
            print(f"  {display_field}: {display_value}")

    print()
    print("📝 SELLER SUMMARY")
    print("-" * 20)
    summary = extractor.extract_seller_summary(sample_response)

    if "seller_info" in summary:
        print("👤 Seller Info:")
        for key, value in summary["seller_info"].items():
            print(f"  • {key.title()}: {value}")

    if "contact_info" in summary:
        print("📍 Contact Info:")
        for key, value in summary["contact_info"].items():
            if key == "store_url" and len(str(value)) > 50:
                value = str(value)[:47] + "..."
            print(f"  • {key.replace('_', ' ').title()}: {value}")

    if "reputation" in summary:
        print("⭐ Reputation:")
        for key, value in summary["reputation"].items():
            print(f"  • {key.replace('_', ' ').title()}: {value}")

    print()

    # Quality assessment
    quality = extractor.validate_extraction_quality(core_data)
    print("🏆 EXTRACTION QUALITY")
    print("-" * 25)
    print(f"Quality: {quality['quality']}")
    print(f"Message: {quality['message']}")
    print(f"Rate: {quality['extraction_rate']}")
    print(f"Recommendation: {quality['recommendation']}")

    if quality.get("missing_fields"):
        print(f"Missing: {', '.join(quality['missing_fields'])}")

    print()
    print("💡 USAGE EXAMPLE")
    print("-" * 20)
    print("from core_seller_extractor import CoreSellerExtractor")
    print("extractor = CoreSellerExtractor()")
    print("seller_data = extractor.extract_core_seller_fields(api_response)")
    print("summary = extractor.extract_seller_summary(api_response)")


if __name__ == "__main__":
    demo_core_extraction()
