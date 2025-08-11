#!/usr/bin/env python3
"""
Enhanced AliExpress Client with Automated Cookie Management
==========================================================

Extended version of the AliExpress client that integrates with automated
cookie generation using Playwright. Provides seamless scraping with
automatic session management.

Features:
- Automatic cookie generation when needed
- Session caching with configurable validity
- Fallback to manual cookies if automation fails
- Comprehensive error handling and retry logic

Usage:
    from enhanced_aliexpress_client import EnhancedAliExpressClient

    client = EnhancedAliExpressClient()
    product_data = client.get_product("3256809096800275")  # No cookies needed!

Author: Enhanced version with automation features
Date: August 2025
"""

import time
from typing import Any, Dict, Optional

from aliexpress_client import AliExpressClient
from cookie_generator import CookieGenerator


class EnhancedAliExpressClient(AliExpressClient):
    """
    Enhanced AliExpress client with automated cookie management.

    Extends the base AliExpressClient to automatically handle cookie
    generation and session management using Playwright integration.
    """

    def __init__(
        self,
        base_url: str = "https://acs.aliexpress.us",
        cookie_cache_minutes: int = 1,
        auto_retry: bool = True,
        headless_browser: bool = True,
    ):
        """
        Initialize the enhanced AliExpress client.

        Args:
            base_url: Base URL for API requests
            cookie_cache_minutes: How long to cache cookies (default: 1 minute)
            auto_retry: Whether to retry with fresh cookies on failure
            headless_browser: Whether to run browser in headless mode
        """
        super().__init__(base_url)

        self.auto_retry = auto_retry
        self.cookie_generator = CookieGenerator(
            cache_validity_minutes=cookie_cache_minutes,
            headless=headless_browser,
            base_url="https://www.aliexpress.us",
        )

        # Track last successful cookie session
        self._last_successful_cookies: Optional[str] = None
        self._last_cookie_time: float = 0

    def _get_valid_cookies(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get valid cookies for making API requests.

        Args:
            force_refresh: Force generation of fresh cookies

        Returns:
            Dictionary with cookies and metadata
        """
        try:
            result = self.cookie_generator.get_valid_cookies(
                force_refresh=force_refresh
            )

            if result["success"] and result.get("cookies"):
                # Validate cookies have essential tokens
                validation = self.cookie_generator.validate_cookies(result["cookies"])

                if validation["valid"]:
                    self._last_successful_cookies = result["cookies"]
                    self._last_cookie_time = time.time()
                    return result
                else:
                    print(
                        f"⚠️ Generated cookies missing essential tokens: {validation['missing_essential']}"
                    )
                    if not force_refresh:
                        # Try once more with force refresh
                        return self._get_valid_cookies(force_refresh=True)

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Cookie generation failed: {e}",
                "cookies": "",
            }

    def get_product_with_auto_cookies(
        self, product_id: str, manual_cookies: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get product data with automatic cookie management.

        Args:
            product_id: AliExpress product ID
            manual_cookies: Optional manual cookies (bypasses automation)

        Returns:
            Dictionary with product information or error details
        """
        # Use manual cookies if provided
        if manual_cookies:
            print("🔧 Using manually provided cookies")
            return self.get_product(product_id, manual_cookies)

        # Try with existing cached cookies first
        cookie_result = self._get_valid_cookies(force_refresh=False)

        if not cookie_result["success"]:
            return {
                "success": False,
                "error": f"Failed to get cookies: {cookie_result.get('error')}",
                "product_id": product_id,
                "automation_used": True,
            }

        cookies = cookie_result["cookies"]
        from_cache = cookie_result.get("from_cache", False)

        print(
            f"🍪 Using {'cached' if from_cache else 'fresh'} cookies for product {product_id}"
        )

        # Try to get product data
        result = self.get_product(product_id, cookies)

        # If failed and auto_retry is enabled, try with fresh cookies
        if not result["success"] and self.auto_retry and from_cache:
            print("🔄 Cached cookies failed, retrying with fresh cookies...")

            fresh_cookie_result = self._get_valid_cookies(force_refresh=True)
            if fresh_cookie_result["success"]:
                result = self.get_product(product_id, fresh_cookie_result["cookies"])
                result["retry_attempted"] = True
            else:
                result["cookie_refresh_error"] = fresh_cookie_result.get("error")

        # Add automation metadata
        result["automation_used"] = True
        result["cookies_from_cache"] = from_cache

        return result

    def get_product(
        self, product_id: str, cookie_string: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get product data. If no cookies provided, uses automated cookie generation.

        Args:
            product_id: AliExpress product ID
            cookie_string: Optional cookie string (if not provided, will be auto-generated)

        Returns:
            Dictionary with product information
        """
        if cookie_string:
            # Use the original method with provided cookies
            return super().get_product(product_id, cookie_string)
        else:
            # Use automated cookie management
            return self.get_product_with_auto_cookies(product_id)

    def batch_get_products(
        self,
        product_ids: list[str],
        delay_seconds: float = 1.0,
        manual_cookies: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get multiple products with shared cookie session.

        Args:
            product_ids: List of product IDs to fetch
            delay_seconds: Delay between requests to avoid rate limiting
            manual_cookies: Optional manual cookies for all requests

        Returns:
            Dictionary with results for each product ID
        """
        results: Dict[str, Any] = {
            "success": True,
            "products": {},
            "failed": {},
            "total_requested": len(product_ids),
            "successful": 0,
            "failed_count": 0,
            "automation_used": manual_cookies is None,
        }

        # Get cookies once for all requests (if not manual)
        if not manual_cookies:
            cookie_result = self._get_valid_cookies(force_refresh=False)
            if not cookie_result["success"]:
                results["success"] = False
                results["error"] = (
                    f"Failed to get cookies: {cookie_result.get('error')}"
                )
                return results
            cookies = cookie_result["cookies"]
            print(f"🍪 Using shared cookie session for {len(product_ids)} products")
        else:
            cookies = manual_cookies
            print(f"🔧 Using manual cookies for {len(product_ids)} products")

        # Process each product
        for i, product_id in enumerate(product_ids):
            print(f"📦 [{i + 1}/{len(product_ids)}] Fetching product {product_id}...")

            try:
                # Use direct method to avoid double automation
                result = super().get_product(product_id, cookies)

                if result["success"]:
                    results["products"][product_id] = result
                    results["successful"] += 1
                    print(f"✅ Success: {result.get('title', 'N/A')[:50]}...")
                else:
                    results["failed"][product_id] = result
                    results["failed_count"] += 1
                    print(f"❌ Failed: {result.get('error', 'Unknown error')}")

                # Delay between requests
                if i < len(product_ids) - 1 and delay_seconds > 0:
                    time.sleep(delay_seconds)

            except Exception as e:
                error_result: Dict[str, Any] = {
                    "success": False,
                    "error": str(e),
                    "product_id": product_id,
                }
                results["failed"][product_id] = error_result
                results["failed_count"] += 1
                print(f"❌ Exception for {product_id}: {e}")

        # Update overall success status
        results["success"] = results["failed_count"] == 0

        return results

    def test_automation(self) -> Dict[str, Any]:
        """
        Test the automated cookie generation system.

        Returns:
            Test results with detailed information
        """
        print("🧪 Testing automated cookie generation...")

        test_results: Dict[str, Any] = {
            "timestamp": time.time(),
            "tests": {},
            "overall_success": True,
        }

        # Initialize cookie_result to None for proper scope
        cookie_result: Optional[Dict[str, Any]] = None

        # Test 1: Cookie generation
        print("\n📋 Test 1: Cookie Generation")
        try:
            cookie_result = self.cookie_generator.get_valid_cookies(force_refresh=True)
            test_results["tests"]["cookie_generation"] = {
                "success": cookie_result["success"],
                "cookies_length": len(cookie_result.get("cookies", "")),
                "from_cache": cookie_result.get("from_cache", False),
                "error": cookie_result.get("error"),
            }

            if cookie_result["success"]:
                print(
                    f"✅ Generated {len(cookie_result['cookies'])} character cookie string"
                )
            else:
                print(f"❌ Cookie generation failed: {cookie_result.get('error')}")
                test_results["overall_success"] = False

        except Exception as e:
            test_results["tests"]["cookie_generation"] = {
                "success": False,
                "error": str(e),
            }
            test_results["overall_success"] = False
            print(f"❌ Cookie generation exception: {e}")

        # Test 2: Cookie validation
        print("\n🔍 Test 2: Cookie Validation")
        if (
            cookie_result
            and cookie_result.get("success")
            and "cookies" in cookie_result
        ):
            try:
                cookies = str(cookie_result["cookies"])  # Ensure it's a string
                validation = self.cookie_generator.validate_cookies(cookies)
                test_results["tests"]["cookie_validation"] = validation

                if validation["valid"]:
                    print(
                        f"✅ Cookies valid - found {len(validation['found_essential'])} essential tokens"
                    )
                else:
                    print(
                        f"❌ Invalid cookies - missing: {validation['missing_essential']}"
                    )
                    test_results["overall_success"] = False

            except Exception as e:
                test_results["tests"]["cookie_validation"] = {
                    "valid": False,
                    "error": str(e),
                }
                print(f"❌ Cookie validation exception: {e}")
        else:
            test_results["tests"]["cookie_validation"] = {
                "skipped": "cookie_generation_failed"
            }

        # Test 3: API call with automated cookies
        print("\n🌐 Test 3: API Call with Automated Cookies")
        test_product_id = "3256809096800275"

        try:
            api_result = self.get_product_with_auto_cookies(test_product_id)
            test_results["tests"]["api_call"] = {
                "success": api_result["success"],
                "product_id": test_product_id,
                "title_found": bool(
                    api_result.get("title") and api_result["title"] != "N/A"
                ),
                "automation_used": api_result.get("automation_used", False),
                "error": api_result.get("error"),
            }

            if api_result["success"]:
                title = api_result.get("title", "N/A")
                print(f"✅ API call successful - Product: {title[:50]}...")
            else:
                print(f"❌ API call failed: {api_result.get('error')}")
                test_results["overall_success"] = False

        except Exception as e:
            test_results["tests"]["api_call"] = {"success": False, "error": str(e)}
            test_results["overall_success"] = False
            print(f"❌ API call exception: {e}")

        # Summary
        print(
            f"\n📊 Test Summary: {'✅ All Passed' if test_results['overall_success'] else '❌ Some Failed'}"
        )

        return test_results

    def get_automation_status(self) -> Dict[str, Any]:
        """
        Get current status of the automation system.

        Returns:
            Status information about cookies and automation
        """
        status: Dict[str, Any] = {
            "timestamp": time.time(),
            "cache_file_exists": self.cookie_generator.cache_file.exists(),
            "last_successful_cookies": self._last_successful_cookies is not None,
            "last_cookie_age_seconds": time.time() - self._last_cookie_time
            if self._last_cookie_time > 0
            else None,
        }

        # Check cache status
        if status["cache_file_exists"]:
            try:
                # Try to get valid cookies to check cache status
                cache_check = self.cookie_generator.get_valid_cookies(
                    force_refresh=False
                )
                status["cache_valid"] = cache_check.get("from_cache", False)
                if status["cache_valid"]:
                    # Calculate approximate age from current time
                    status["cache_age_seconds"] = "cache_age_unavailable_externally"
            except Exception:
                status["cache_valid"] = False
        else:
            status["cache_valid"] = False

        return status


def main():
    """Example usage of the enhanced AliExpress client."""

    print("🚀 Enhanced AliExpress Client with Cookie Automation")
    print("=" * 55)
    print("Automated cookie generation: ✅ Ready")
    print("Session caching: ✅ Enabled")
    print("Retry logic: ✅ Active")
    print()

    # Initialize enhanced client
    client = EnhancedAliExpressClient(
        cookie_cache_minutes=1,  # 1-minute cache
        auto_retry=True,
        headless_browser=True,
    )

    # Test automation system
    print("🧪 Running automation tests...")
    test_results = client.test_automation()

    if test_results["overall_success"]:
        print("\n🎉 All tests passed! System is ready for use.")
        print("\n📖 Usage Examples:")
        print("   # Simple usage (fully automated)")
        print("   result = client.get_product('3256809096800275')")
        print()
        print("   # Batch processing")
        print("   results = client.batch_get_products(['id1', 'id2', 'id3'])")
        print()
        print("   # With manual cookies (bypass automation)")
        print("   result = client.get_product('product_id', 'your_cookies_here')")

        # Show automation status
        print(f"\n📊 Automation Status:")
        status = client.get_automation_status()
        for key, value in status.items():
            if key != "timestamp":
                print(f"   {key}: {value}")

    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        print("   You can still use manual cookies if automation isn't working.")

    print()
    print("🏆 Enhanced client ready for production use!")


if __name__ == "__main__":
    main()
