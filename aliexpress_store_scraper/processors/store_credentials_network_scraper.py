#!/usr/bin/env python3
"""
AliExpress Store Credentials Network Scraper
==========================================

Enhanced scraper that captures network requests to extract base64 images
and certificate data directly from API responses, bypassing HTML parsing.

This approach is more efficient as it:
1. Captures the actual API calls that fetch business license images
2. Extracts base64 image data directly from responses
3. Avoids parsing large HTML documents
4. Gets structured JSON data from API endpoints

Usage:
    from store_credentials_network_scraper import StoreCredentialsNetworkScraper

    scraper = StoreCredentialsNetworkScraper()
    store_ids = ["123456", "789012"]
    results = scraper.scrape_store_credentials(store_ids)

Author: Enhanced for network request interception
Date: August 2025
"""

import asyncio
import json
import os
import re
import time
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Optional, cast

from dotenv import load_dotenv
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Request,
    Response,
    Route,
    async_playwright,
)

from aliexpress_store_scraper.utils.captcha_solver import AdvancedCaptchaSolver
from aliexpress_store_scraper.utils.logger import ScraperLogger


class StoreCredentialsNetworkScraper:
    """
    Enhanced scraper that captures network requests for AliExpress store credentials.

    This scraper intercepts API calls to extract certificate images and data directly
    from network responses, providing more efficient access to the underlying data.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        delay_between_requests: float = 1.0,
        max_retries: int = 3,
        user_agent: Optional[str] = None,
        use_proxy: bool = False,
        cookies_file: str = "aliexpress_session_cookies.json",
        max_captcha_attempts: int = 3,
    ):
        """
        Initialize the network scraper.

        Args:
            headless: Run browser in headless mode
            timeout: Page load timeout in milliseconds
            delay_between_requests: Delay between requests in seconds
            max_retries: Maximum number of retry attempts per store
            user_agent: Custom user agent string
            use_proxy: Whether to use Oxylabs proxy configuration from environment
            cookies_file: Path to JSON file for storing session cookies
            max_captcha_attempts: Maximum attempts to solve CAPTCHA before restarting browser
        """
        self.headless = headless
        self.timeout = timeout
        self.delay = delay_between_requests
        self.max_retries = max_retries
        self.use_proxy = use_proxy
        self.cookies_file = cookies_file
        self.max_captcha_attempts = max_captcha_attempts
        self.user_agent = user_agent or (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self.logger = ScraperLogger(module_name="StoreCredentialsNetworkScraper")

        # Track captured network data
        self.network_data: dict[str, Any] = {}
        self.certificate_apis: list[str] = []
        self.image_data: dict[str, Any] = {}

        # Session management
        self.captcha_failure_count = 0
        self.session_active = False

        # Browser instances (initialized in _setup_browser)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

        # Configure proxy if enabled
        self.proxy_config = None
        if self.use_proxy:
            self.proxy_config = self._get_oxylabs_proxy_config()

    def _get_oxylabs_proxy_config(self) -> Optional[dict[str, str]]:
        """Get Oxylabs proxy configuration from environment variables."""
        # Load environment variables from .env file
        load_dotenv()

        username = os.getenv("OXYLABS_USERNAME")
        password = os.getenv("OXYLABS_PASSWORD")
        endpoint = os.getenv("OXYLABS_ENDPOINT")

        if username and password and endpoint:
            proxy_config = {
                "server": f"http://{endpoint}",
                "username": username,
                "password": password,
            }
            self.logger.info(f"🌐 Configured Oxylabs proxy: {endpoint}")
            return proxy_config
        else:
            self.logger.warning(
                "⚠️  Oxylabs proxy credentials not found in environment variables"
            )
            self.logger.warning(
                "   Add OXYLABS_USERNAME, OXYLABS_PASSWORD, and OXYLABS_ENDPOINT to .env file"
            )
            return None

    def _load_cookies(self) -> Optional[list[dict[str, Any]]]:
        """
        Load cookies from JSON file.

        Returns:
            List of cookie dictionaries if file exists and is valid, None otherwise
        """
        cookies_path = Path(self.cookies_file)

        if not cookies_path.exists():
            self.logger.info(f"🍪 No existing cookies file found: {self.cookies_file}")
            return None

        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)

            # Validate the data structure
            if "cookies" not in data:
                self.logger.warning(
                    f"⚠️  Invalid cookies file format: {self.cookies_file}"
                )
                return None

            cookies_raw: list[dict[str, Any] | Any] | Any = data["cookies"]
            if not isinstance(cookies_raw, list):
                self.logger.warning(
                    f"⚠️  Invalid cookies format in: {self.cookies_file}"
                )
                return None

            cookies_raw = cast(list[dict[str, Any]], cookies_raw)

            # Check if cookies are not expired (optional validation)
            valid_cookies: list[dict[str, Any]] = []
            current_time = int(time.time())

            for cookie_item in cookies_raw:
                # Skip non-dictionary items
                if not isinstance(cookie_item, dict):
                    continue

                cookie_item = cast(dict[str, Any], cookie_item)

                # Type-cast the cookie to the proper type with type ignore for JSON parsing
                cookie: dict[str, Any] = {str(k): v for k, v in cookie_item.items()}

                # If no expires field or not expired, keep the cookie
                expires_value = cookie.get("expires", -1)

                # Handle both numeric and string expires values
                expires: int = -1

                if isinstance(expires_value, (int, float)):
                    expires = int(expires_value)
                elif isinstance(expires_value, str):
                    try:
                        expires = int(float(expires_value))
                    except (ValueError, TypeError):
                        expires = -1

                if expires == -1 or expires > current_time:
                    valid_cookies.append(cookie)
                else:
                    cookie_name_value = cookie.get("name", "unknown")
                    cookie_name = (
                        str(cookie_name_value)
                        if cookie_name_value is not None
                        else "unknown"
                    )
                    self.logger.debug(f"🗑️  Expired cookie removed: {cookie_name}")

            if valid_cookies:
                self.logger.info(
                    f"🍪 Loaded {len(valid_cookies)} valid cookies from {self.cookies_file}"
                )
                saved_at = data.get("saved_at", "unknown")
                self.logger.info(f"   📅 Last saved: {saved_at}")
                return valid_cookies
            else:
                self.logger.info(f"🍪 No valid cookies found in {self.cookies_file}")
                return None

        except json.JSONDecodeError:
            self.logger.warning(f"⚠️  Failed to parse cookies file: {self.cookies_file}")
            return None
        except Exception as e:
            self.logger.warning(
                f"⚠️  Error loading cookies from {self.cookies_file}: {e}"
            )
            return None

    def _save_cookies(self, cookies: list[dict[str, Any]]) -> None:
        """
        Save cookies to JSON file.

        Args:
            cookies: List of cookie dictionaries from browser context
        """
        if not cookies:
            self.logger.debug("🍪 No cookies to save")
            return

        try:
            cookies_data: dict[str, Any] = {
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "timestamp": int(time.time()),
                "cookies": cookies,
                "user_agent": self.user_agent,
                "proxy_used": self.proxy_config is not None,
            }

            cookies_path = Path(self.cookies_file)
            with open(cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"🍪 Saved {len(cookies)} cookies to {self.cookies_file}")
            self.logger.debug(f"   📁 File size: {cookies_path.stat().st_size} bytes")

        except Exception as e:
            self.logger.error(f"❌ Failed to save cookies to {self.cookies_file}: {e}")

    async def _load_cookies_to_context(self) -> None:
        """Load saved cookies into browser context if available."""
        cookies = self._load_cookies()
        if cookies and hasattr(self, "context"):
            try:
                # Convert our dict format to the format expected by Playwright
                valid_cookies: list[Any] = []
                for cookie in cookies:
                    # Ensure required fields are present
                    if "name" in cookie and "value" in cookie and "domain" in cookie:
                        # Create a properly typed cookie for Playwright
                        playwright_cookie: dict[str, Any] = {
                            "name": str(cookie["name"]),
                            "value": str(cookie["value"]),
                            "domain": str(cookie["domain"]),
                            "path": str(cookie.get("path", "/")),
                        }

                        # Add optional fields if present
                        expires_val = cookie.get("expires")
                        if expires_val and expires_val != -1:
                            playwright_cookie["expires"] = expires_val

                        http_only = cookie.get("httpOnly")
                        if http_only is not None:
                            playwright_cookie["httpOnly"] = http_only

                        secure = cookie.get("secure")
                        if secure is not None:
                            playwright_cookie["secure"] = secure

                        same_site = cookie.get("sameSite")
                        if same_site:
                            playwright_cookie["sameSite"] = same_site

                        valid_cookies.append(playwright_cookie)

                if valid_cookies:
                    if self.context is not None:
                        await self.context.add_cookies(valid_cookies)
                        self.logger.info(
                            f"🍪 Applied {len(valid_cookies)} cookies to browser context"
                        )
                    else:
                        self.logger.warning("⚠️  Browser context not available")
                else:
                    self.logger.warning("⚠️  No valid cookies found to apply")
            except Exception as e:
                self.logger.warning(f"⚠️  Failed to apply cookies to context: {e}")

    async def _save_cookies_from_context(self) -> None:
        """Save current cookies from browser context to file."""
        if hasattr(self, "context") and self.context is not None:
            try:
                browser_cookies = await self.context.cookies()
                if browser_cookies:
                    # Convert Playwright Cookie objects to simple dictionaries
                    cookie_dicts: list[dict[str, Any]] = []
                    for cookie in browser_cookies:
                        # Convert cookie object to dictionary safely
                        cookie_dict: dict[str, Any] = {
                            "name": cookie.get("name", ""),
                            "value": cookie.get("value", ""),
                            "domain": cookie.get("domain", ""),
                            "path": cookie.get("path", "/"),
                            "expires": cookie.get("expires", -1),
                            "httpOnly": cookie.get("httpOnly", False),
                            "secure": cookie.get("secure", False),
                            "sameSite": cookie.get("sameSite", "lax"),
                        }
                        cookie_dicts.append(cookie_dict)

                    self._save_cookies(cookie_dicts)
                else:
                    self.logger.debug("🍪 No cookies found in context to save")
            except Exception as e:
                self.logger.warning(f"⚠️  Failed to save cookies from context: {e}")

    def get_cookies_for_requests(self) -> dict[str, str]:
        """
        Get cookies in simple key-value format suitable for subsequent HTTP requests.

        Returns:
            Dictionary with cookie names as keys and values as strings
        """
        if not hasattr(self, "context"):
            self.logger.warning(
                "⚠️  Browser context not available for cookie extraction"
            )
            return {}

        try:
            import asyncio

            # Get cookies from browser context synchronously
            if self.context is None:
                self.logger.warning("⚠️  Browser context not available")
                return {}

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we can't use run()
                self.logger.warning(
                    "⚠️  Cannot extract cookies synchronously from async context"
                )
                return {}
            else:
                cookies = loop.run_until_complete(self.context.cookies())
        except Exception as e:
            self.logger.warning(f"⚠️  Failed to extract cookies for requests: {e}")
            return {}

        # Convert to simple key-value format
        cookies_dict: dict[str, str] = {}
        for cookie in cookies:
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            if name and value:
                cookies_dict[name] = value

        self.logger.info(f"🍪 Extracted {len(cookies_dict)} cookies for requests")
        return cookies_dict

    async def get_cookies_for_requests_async(self) -> dict[str, str]:
        """
        Get cookies in simple key-value format suitable for subsequent HTTP requests (async version).

        Returns:
            Dictionary with cookie names as keys and values as strings
        """
        if not hasattr(self, "context") or self.context is None:
            self.logger.warning(
                "⚠️  Browser context not available for cookie extraction"
            )
            return {}

        try:
            cookies = await self.context.cookies()
        except Exception as e:
            self.logger.warning(f"⚠️  Failed to extract cookies for requests: {e}")
            return {}

        # Convert to simple key-value format
        cookies_dict: dict[str, str] = {}
        for cookie in cookies:
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            if name and value:
                cookies_dict[name] = value

        self.logger.info(f"🍪 Extracted {len(cookies_dict)} cookies for requests")
        return cookies_dict

    async def _check_session_health(self) -> bool:
        """
        Check if current browser session is healthy and usable.

        Returns:
            bool: True if session is healthy, False otherwise
        """
        try:
            if (
                not hasattr(self, "context")
                or not self.context
                or not self.session_active
            ):
                return False

            # Try to create a new page to test session
            page = await self.context.new_page()
            await page.close()
            return True
        except Exception as e:
            self.logger.warning(f"Session health check failed: {e}")
            return False

    async def _restart_browser_session(self) -> None:
        """
        Restart the browser session and reset CAPTCHA counters.
        """
        self.logger.info("🔄 Restarting browser session due to CAPTCHA failures...")

        try:
            # Close current session
            if hasattr(self, "context") and self.context:
                await self.context.close()
            if hasattr(self, "browser") and self.browser:
                await self.browser.close()

            self.browser = None
            self.context = None
            self.session_active = False

            # Reset CAPTCHA counter
            self.captcha_failure_count = 0

            # Setup fresh browser session
            await self._setup_browser()
            self.session_active = True

            self.logger.success("✅ Browser session restarted successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to restart browser session: {e}")
            raise

    def _should_restart_session(self) -> bool:
        """
        Check if session should be restarted due to CAPTCHA failures.

        Returns:
            bool: True if session should be restarted
        """
        return self.captcha_failure_count >= self.max_captcha_attempts

    def _increment_captcha_failure(self) -> None:
        """
        Increment CAPTCHA failure counter and log current status.
        """
        self.captcha_failure_count += 1
        self.logger.warning(
            f"⚠️ CAPTCHA failure {self.captcha_failure_count}/{self.max_captcha_attempts}"
        )

        if self._should_restart_session():
            self.logger.warning(
                "🚨 Maximum CAPTCHA failures reached, session restart needed"
            )

    def _reset_captcha_counter(self) -> None:
        """
        Reset CAPTCHA failure counter after successful operation.
        """
        if self.captcha_failure_count > 0:
            self.logger.info(
                "✅ Resetting CAPTCHA failure counter after successful operation"
            )
            self.captcha_failure_count = 0

    def __enter__(self) -> "StoreCredentialsNetworkScraper":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Context manager exit with cleanup."""
        if hasattr(self, "playwright"):
            asyncio.run(self._cleanup())

    async def _cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            # Save cookies before closing browser
            await self._save_cookies_from_context()

            if hasattr(self, "browser") and self.browser:
                await self.browser.close()
            if hasattr(self, "playwright") and self.playwright:
                await self.playwright.stop()
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")

    async def _setup_browser(self) -> None:
        """Initialize Playwright browser with optimized settings."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-extensions",
                "--disable-plugins",
            ],
        )

        # Create browser context with additional blocking and proxy support
        context_options: dict[str, Any] = {
            "user_agent": self.user_agent,
            "viewport": {"width": 1920, "height": 1080},
            "ignore_https_errors": True,
        }

        # Add proxy configuration if available
        if self.proxy_config:
            context_options["proxy"] = self.proxy_config
            self.logger.info(f"🌐 Using proxy: {self.proxy_config['server']}")

        self.context = await self.browser.new_context(**context_options)

        # Load saved cookies into the context
        await self._load_cookies_to_context()

        self.logger.info("Browser initialized successfully")
        # Mark session as active after successful setup
        self.session_active = True

    async def _setup_request_interception(self, page: Page, store_id: str) -> None:
        """
        Set up request/response interception to capture certificate API calls.

        Args:
            page: Playwright page instance
            store_id: Current store ID being processed
        """

        async def handle_route(route: Route, request: Request) -> None:
            """Handle requests and decide whether to block or allow."""
            url = request.url.lower()
            method = request.method

            # Allow all resource types - no blocking!
            resource_type = request.resource_type
            self.logger.debug(f"✅ Allowing {resource_type}: {url[:100]}")

            # Allow and track API requests that might contain certificate data
            if self._is_certificate_api(url):
                self.logger.info(f"📡 Tracking certificate API: {method} {url}")
                await route.continue_()
                return

            # Allow all other requests (HTML, JS, XHR)
            await route.continue_()

        async def handle_response(response: Response) -> None:
            """Capture responses from certificate-related API calls."""
            url = response.url
            status = response.status

            if self._is_certificate_api(url) and status == 200:
                try:
                    # Capture the response data
                    content_type = response.headers.get("content-type", "")

                    if "application/json" in content_type:
                        json_data = await response.json()
                        self.logger.info(f"📋 Captured JSON response from: {url}")

                        # Store the API response
                        api_key = f"{store_id}_{self._get_api_type(url)}"
                        self.network_data[api_key] = {
                            "url": url,
                            "status": status,
                            "content_type": content_type,
                            "data": json_data,
                            "timestamp": time.time(),
                        }

                        # Check if this is the specific mtop.ae.merchant.shop.credential.get response
                        if self._is_credential_data_response(json_data, url):
                            self._extract_credential_data(json_data, store_id, url)

                        # Extract base64 images from the response
                        self._extract_images_from_json(json_data, store_id, url)

                    elif "text/" in content_type:
                        text_data = await response.text()
                        self.logger.info(f"📄 Captured text response from: {url}")

                        api_key = f"{store_id}_{self._get_api_type(url)}"
                        self.network_data[api_key] = {
                            "url": url,
                            "status": status,
                            "content_type": content_type,
                            "data": text_data,
                            "timestamp": time.time(),
                        }

                        # Try to parse JSONP responses
                        if self._is_credential_api(url):
                            jsonp_data = self._parse_jsonp_response(text_data)
                            if jsonp_data and self._is_credential_data_response(
                                jsonp_data, url
                            ):
                                self.logger.info(
                                    f"🎯 Found credential data in JSONP response!"
                                )
                                self.network_data[api_key]["parsed_jsonp"] = jsonp_data
                                self._extract_credential_data(jsonp_data, store_id, url)

                except Exception as e:
                    self.logger.warning(f"Error capturing response from {url}: {e}")

        # Set up the request interception
        await page.route("**/*", handle_route)

        # Set up response interception
        page.on("response", handle_response)

        self.logger.info("Request/response interception configured")

    def _is_certificate_api(self, url: str) -> bool:
        """
        Determine if a URL is likely a certificate/license API endpoint.

        Args:
            url: URL to check

        Returns:
            True if URL appears to be certificate-related API
        """
        # Patterns that might indicate certificate/license APIs
        certificate_patterns = [
            r"credential",
            r"certificate",
            r"license",
            r"business.*license",
            r"qualification",
            r"mtop.*credential",
            r"api.*credential",
            r"merchant.*shop.*credential",
            r"shop.*info",
            r"company.*info",
            r"store.*info",
            r"seller.*info",
        ]

        url_lower = url.lower()

        # Check if URL matches any certificate-related patterns
        for pattern in certificate_patterns:
            if re.search(pattern, url_lower):
                return True

        # Additional checks for AliExpress specific endpoints
        if "aliexpress.com" in url_lower and any(
            keyword in url_lower for keyword in ["mtop", "api", "h5", "ajax", "service"]
        ):
            return True

        return False

    def _get_api_type(self, url: str) -> str:
        """
        Classify the API type based on URL patterns.

        Args:
            url: API URL

        Returns:
            API type classification
        """
        url_lower = url.lower()

        if "credential" in url_lower:
            return "credential"
        elif "license" in url_lower:
            return "license"
        elif "certificate" in url_lower:
            return "certificate"
        elif "qualification" in url_lower:
            return "qualification"
        elif "shop" in url_lower or "store" in url_lower:
            return "shop_info"
        else:
            return "unknown"

    def _extract_images_from_json(
        self, json_data: dict[str, Any], store_id: str, source_url: str
    ) -> None:
        """
        Recursively extract base64 images from JSON response data.

        Args:
            json_data: JSON response data
            store_id: Current store ID
            source_url: URL where this data came from
        """

        def find_base64_images(
            obj: dict[str, Any] | list[Any] | str, path: str = ""
        ) -> None:
            """Recursively find base64 image strings in nested JSON."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    find_base64_images(value, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]"
                    find_base64_images(item, current_path)
            else:
                # obj is a str at this point due to the union type
                # Check if string looks like base64 image
                if self._is_base64_image(obj):
                    image_key = f"{store_id}_{path}_{int(time.time())}"
                    self.image_data[image_key] = {
                        "base64_data": obj,
                        "source_url": source_url,
                        "json_path": path,
                        "store_id": store_id,
                        "extracted_at": time.time(),
                    }
                    self.logger.info(f"🖼️  Extracted base64 image from: {path}")

        find_base64_images(json_data)

    def _is_credential_data_response(self, json_data: dict[str, Any], url: str) -> bool:
        """
        Check if this is the specific credential data response we're looking for.

        Expected format:
        {
            "api": "mtop.ae.merchant.shop.credential.get",
            "data": {
                "data": {
                    "url": "/9j/4AAQSkZJRgABAgAAAQABAAD...base64_data"
                }
            },
            "ret": ["SUCCESS::调用成功"],
            "v": "1.0"
        }

        Args:
            json_data: JSON response data
            url: Source URL

        Returns:
            True if this appears to be credential data response
        """
        try:
            # Check if this is an mtop credential API response
            if not (
                "mtop.ae.merchant.shop.credential.get" in url
                or json_data.get("api") == "mtop.ae.merchant.shop.credential.get"
            ):
                return False

            # Check for the expected structure
            data: dict[str, Any] = json_data.get("data", {})
            inner_data: dict[str, Any] = data.get("data", {})

            # Check if the url field contains what looks like base64 data
            url_data = inner_data["url"]
            if isinstance(url_data, str) and len(url_data) > 100:
                return True

            return False

        except Exception as e:
            self.logger.warning(f"Error checking credential data response: {e}")
            return False

    def _extract_credential_data(
        self, json_data: dict[str, Any], store_id: str, source_url: str
    ) -> None:
        """
        Extract credential data from the specific API response format.

        Args:
            json_data: JSON response with credential data
            store_id: Current store ID
            source_url: URL where this data came from
        """
        try:
            data_raw: dict[str, Any] | None = json_data.get("data")
            if not data_raw:
                self.logger.warning("No data found in JSON response")
                return

            inner_data_raw = data_raw.get("data")
            if not inner_data_raw:
                self.logger.warning("No inner data found in JSON response")
                return

            base64_data_raw = inner_data_raw["url"]
            if isinstance(base64_data_raw, str):
                base64_data = base64_data_raw

                if len(base64_data) > 100:
                    # This is likely the base64 certificate image
                    image_key = f"{store_id}_certificate_{int(time.time())}"
                    self.image_data[image_key] = {
                        "base64_data": base64_data,
                        "source_url": source_url,
                        "json_path": "data.data.url",
                        "store_id": store_id,
                        "api_name": json_data.get(
                            "api", "mtop.ae.merchant.shop.credential.get"
                        ),
                        "api_version": json_data.get("v", "unknown"),
                        "api_status": json_data.get("ret", []),
                        "extracted_at": time.time(),
                        "data_type": "certificate_image",
                    }

                    self.logger.info(
                        f"🏆 SUCCESS! Extracted certificate image for store {store_id}"
                    )
                    self.logger.info(
                        f"📏 Base64 data length: {len(base64_data)} characters"
                    )

                    # Try to determine image format from base64 data
                    image_format = self._detect_image_format(base64_data)
                    if image_format:
                        self.image_data[image_key]["image_format"] = image_format
                        self.logger.info(f"🖼️  Detected image format: {image_format}")

        except Exception as e:
            self.logger.error(f"Error extracting credential data: {e}")

    def _detect_image_format(self, base64_data: str) -> Optional[str]:
        """
        Try to detect the image format from base64 data.

        Args:
            base64_data: Base64 encoded image data

        Returns:
            Detected image format or None
        """
        try:
            # Check for data URL prefix
            if base64_data.startswith("data:image/"):
                format_match = re.match(r"data:image/([^;]+);base64,", base64_data)
                if format_match:
                    return format_match.group(1)

            # Try to decode the first few bytes to check magic numbers
            import base64

            try:
                # Remove data URL prefix if present
                if "base64," in base64_data:
                    base64_data = base64_data.split("base64,", 1)[1]

                # Decode first few bytes
                decoded = base64.b64decode(base64_data[:20])

                # Check common image magic numbers
                if decoded.startswith(b"\xff\xd8\xff"):
                    return "jpeg"
                elif decoded.startswith(b"\x89PNG\r\n\x1a\n"):
                    return "png"
                elif decoded.startswith(b"GIF87a") or decoded.startswith(b"GIF89a"):
                    return "gif"
                elif decoded.startswith(b"RIFF") and b"WEBP" in decoded:
                    return "webp"
                elif decoded.startswith(b"BM"):
                    return "bmp"

            except Exception:
                pass

        except Exception:
            pass

        return None

    def _is_credential_api(self, url: str) -> bool:
        """
        Check if URL is specifically the credential API endpoint.

        Args:
            url: URL to check

        Returns:
            True if this is the credential API
        """
        return "mtop.ae.merchant.shop.credential.get" in url.lower()

    def _parse_jsonp_response(self, text_data: str) -> Optional[dict[str, Any]]:
        """
        Parse JSONP response to extract JSON data.

        JSONP format: callback_name({json_data});

        Args:
            text_data: JSONP response text

        Returns:
            Parsed JSON data or None
        """
        try:
            # Remove JSONP wrapper
            # Look for pattern: callback_name({...});
            import re

            # Try to find JSON within JSONP wrapper
            jsonp_pattern = r"[a-zA-Z_][a-zA-Z0-9_]*\s*\(\s*({.*})\s*\)\s*;?"
            match = re.search(jsonp_pattern, text_data, re.DOTALL)

            if match:
                json_str = match.group(1)
                import json

                return json.loads(json_str)

            # If no JSONP wrapper found, try to parse as direct JSON
            if text_data.strip().startswith("{") and text_data.strip().endswith("}"):
                import json

                return json.loads(text_data)

        except Exception as e:
            self.logger.debug(f"Failed to parse JSONP response: {e}")

        return None

    def _is_base64_image(self, text: str) -> bool:
        """
        Check if a string appears to be a base64-encoded image.

        Args:
            text: String to check

        Returns:
            True if string appears to be base64 image
        """
        if len(text) < 100:
            return False

        # Check for data URL format
        if text.startswith("data:image/"):
            return True

        # Check for base64 patterns (basic heuristic)
        base64_pattern = r"^[A-Za-z0-9+/]{100,}={0,2}$"
        if re.match(base64_pattern, text) and len(text) > 1000:
            return True

        return False

    async def _scrape_single_store(self, store_id: str) -> dict[str, Any]:
        """
        Scrape a single store's credentials with network interception.

        Args:
            store_id: Store ID to scrape

        Returns:
            Dictionary containing scraped data and captured network requests
        """
        result: dict[str, Any] = {
            "store_id": store_id,
            "scraped_at": time.time(),
            "status": "error",
            "network_data": {},
            "images": {},
            "error": None,
        }

        try:
            # Ensure browser context is available
            if not self.context:
                raise RuntimeError("Browser context not initialized")

            page = await self.context.new_page()

            # Clear previous network data for this store
            store_network_keys = [
                k for k in self.network_data.keys() if k.startswith(store_id)
            ]
            for key in store_network_keys:
                del self.network_data[key]

            store_image_keys = [
                k for k in self.image_data.keys() if k.startswith(store_id)
            ]
            for key in store_image_keys:
                del self.image_data[key]

            # Set up network interception for this store
            await self._setup_request_interception(page, store_id)

            # Navigate to the store credentials page
            # Use HTTP when proxy is enabled to avoid HTTPS tunneling issues
            protocol = "http" if self.proxy_config else "https"
            url = f"{protocol}://shoprenderview.aliexpress.com/credential/showcredential.htm?storeNum={store_id}"

            self.logger.info(f"🔍 Navigating to store {store_id}: {url}")
            if self.proxy_config and protocol == "http":
                self.logger.info(
                    "   💡 Using HTTP to avoid proxy HTTPS tunneling issues"
                )

            response = await page.goto(
                url, wait_until="networkidle", timeout=self.timeout
            )

            # Wait a moment for potential redirects to CAPTCHA pages
            await page.wait_for_timeout(5000)

            # Check current URL for CAPTCHA redirect
            current_url = page.url
            self.logger.info(f"🔍 Current URL after navigation: {current_url}")

            # Check for CAPTCHA and solve if present
            captcha_detected = await self._detect_captcha(page)
            if captcha_detected:
                self.logger.info(
                    f"🤖 CAPTCHA detected for store {store_id}, attempting to solve..."
                )
                captcha_solved = await self._solve_captcha(page)
                if captcha_solved:
                    self.logger.success(f"✅ CAPTCHA solved for store {store_id}")
                    # Reset CAPTCHA counter on successful solve
                    self._reset_captcha_counter()

                    # Wait at least 10 seconds after CAPTCHA solve for API calls to trigger
                    self.logger.info(
                        "⏳ Waiting at least 10 seconds for post-CAPTCHA API calls..."
                    )
                    await page.wait_for_timeout(
                        12000
                    )  # Increased to 12 seconds to be safe

                    # Navigate back to the original URL if needed
                    if "punish" in page.url.lower():
                        self.logger.info(
                            "🔄 Navigating back to credentials page after CAPTCHA solve..."
                        )
                        response = await page.goto(
                            url, wait_until="networkidle", timeout=self.timeout
                        )

                        # Wait additional time for credential API calls after page reload
                        self.logger.info(
                            "⏳ Waiting for credential API calls after page reload..."
                        )
                        await page.wait_for_timeout(5000)  # Initial wait

                        # Actively wait for credential API response
                        api_captured = await self._wait_for_credential_api(
                            page, store_id, timeout=15000
                        )
                        if not api_captured:
                            self.logger.info(
                                "🔄 Trying to trigger API call by refreshing page..."
                            )
                            await page.reload(wait_until="networkidle")
                            await self._wait_for_credential_api(
                                page, store_id, timeout=10000
                            )
                else:
                    # CAPTCHA solve failed - increment failure counter
                    self._increment_captcha_failure()
                    self.logger.warning(
                        f"⚠️ Failed to solve CAPTCHA for store {store_id}"
                    )
            else:
                self.logger.info(f"ℹ️ No CAPTCHA detected for store {store_id}")

            # Wait for certificate images to render with dynamic CAPTCHA monitoring
            certificate_images = (
                await self._wait_for_certificate_images_with_captcha_monitoring(
                    page,
                    store_id,
                    max_wait=45,  # Increased from 30 to 45 seconds
                )
            )

            # Process found images and extract base64 data
            if certificate_images:
                for i, img_src in enumerate(certificate_images):
                    if img_src.startswith("data:image/"):
                        # Extract base64 data from data URI
                        try:
                            # Format: data:image/jpeg;base64,/9j/4AAQSkZJRgABA...
                            header, b64_data = img_src.split(",", 1)
                            image_format = header.split("/")[1].split(";")[
                                0
                            ]  # Extract format (jpeg, png, etc.)

                            image_key = f"{store_id}_certificate_{i + 1}"
                            self.image_data[image_key] = {
                                "format": image_format,
                                "base64": b64_data,
                                "data_uri": img_src,
                                "timestamp": time.time(),
                            }

                            self.logger.success(
                                f"✅ Extracted certificate {i + 1} - Format: {image_format.upper()}, Size: {len(b64_data)} chars"
                            )
                        except Exception as e:
                            self.logger.warning(
                                f"⚠️ Error processing image {i + 1}: {e}"
                            )

            if response and response.status == 200:
                result["url"] = url
                result["status"] = "success"
                result["status_code"] = response.status
                result["final_url"] = page.url

                # Wait a bit more for any additional API calls to complete
                await page.wait_for_timeout(3000)

                # Capture network data for this store
                store_network_data = {
                    k: v for k, v in self.network_data.items() if k.startswith(store_id)
                }

                store_image_data = {
                    k: v for k, v in self.image_data.items() if k.startswith(store_id)
                }

                result["network_data"] = store_network_data
                result["images"] = store_image_data
                result["network_requests_captured"] = len(store_network_data)
                result["images_extracted"] = len(store_image_data)

                self.logger.info(
                    f"✅ Store {store_id}: Captured {len(store_network_data)} API responses, "
                    f"extracted {len(store_image_data)} images"
                )

            else:
                status_code = response.status if response else 0
                result["error"] = f"HTTP {status_code}: Failed to load page"
                result["status_code"] = status_code

            # Don't close page - leave it open for manual inspection
            # await page.close()

        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"❌ Error scraping store {store_id}: {e}")

        return result

    async def scrape_store_credentials(
        self,
        store_ids: list[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[dict[str, Any]]:
        """
        Scrape credentials for multiple stores with network interception.

        Args:
            store_ids: list of store IDs to scrape
            progress_callback: Optional callback function for progress updates

        Returns:
            list of dictionaries containing scraped data and network captures
        """
        if not store_ids:
            self.logger.warning("No store IDs provided")
            return []

        await self._setup_browser()
        # Mark session as active after initial setup
        self.session_active = True
        results: list[dict[str, Any]] = []

        self.logger.info(f"🚀 Starting network scraping for {len(store_ids)} stores")
        self.logger.info(
            f"Configuration: timeout={self.timeout}ms, delay={self.delay}s, retries={self.max_retries}"
        )
        self.logger.info(
            f"Session management: max_captcha_attempts={self.max_captcha_attempts}"
        )

        for i, store_id in enumerate(store_ids):
            # Check if session needs restart due to CAPTCHA failures
            if self._should_restart_session():
                try:
                    await self._restart_browser_session()
                except Exception as e:
                    self.logger.error(f"❌ Failed to restart browser session: {e}")
                    # If restart fails, continue with current session
                    pass

            # Verify session health before processing store
            session_healthy = await self._check_session_health()
            if not session_healthy:
                self.logger.warning("⚠️ Session unhealthy, attempting to restart...")
                try:
                    await self._restart_browser_session()
                except Exception as e:
                    self.logger.error(f"❌ Failed to restart unhealthy session: {e}")
                    # Continue with potentially broken session

            if progress_callback:
                progress_callback(i + 1, len(store_ids), store_id)

            attempt = 1
            success = False
            result = {}

            while attempt <= self.max_retries and not success:
                try:
                    if attempt > 1:
                        self.logger.info(
                            f"🔄 Retry {attempt}/{self.max_retries} for store {store_id}"
                        )

                    result = await self._scrape_single_store(store_id)

                    if result["status"] == "success":
                        success = True
                        # Reset CAPTCHA counter on successful scraping
                        self._reset_captcha_counter()
                        # Save cookies after successful scraping to preserve session
                        await self._save_cookies_from_context()
                    else:
                        attempt += 1

                except Exception as e:
                    self.logger.error(
                        f"❌ Attempt {attempt} failed for store {store_id}: {e}"
                    )

                    # Even if the scraping failed, preserve any images that were captured
                    store_image_data = {
                        k: v
                        for k, v in self.image_data.items()
                        if k.startswith(store_id)
                    }
                    store_network_data = {
                        k: v
                        for k, v in self.network_data.items()
                        if k.startswith(store_id)
                    }

                    result: dict[str, Any] = {
                        "status": "error",
                        "error": f"Failed after {attempt} attempts: {str(e)}",
                        "scraped_at": time.time(),
                        "network_data": store_network_data,
                        "images": store_image_data,
                        "images_extracted": len(store_image_data),
                        "network_requests_captured": len(store_network_data),
                    }

                    # Log if we captured images despite the error
                    if store_image_data:
                        self.logger.info(
                            f"✅ Preserved {len(store_image_data)} images from failed attempt for store {store_id}"
                        )

                    attempt += 1

            if result:
                results.append(result)

            # Delay between requests (except for the last one)
            if i < len(store_ids) - 1 and self.delay > 0:
                await asyncio.sleep(self.delay)

        # Don't automatically close browser - leave it open for manual inspection
        self.logger.info("🔍 Browser left open for manual inspection")
        # await self._cleanup()

        success_count = sum(1 for r in results if r["status"] == "success")
        total_images = sum(len(r["images"]) for r in results)
        total_api_calls = sum(len(r["network_data"]) for r in results)

        self.logger.info(
            f"🎉 Network scraping completed: {success_count}/{len(store_ids)} successful, "
            f"{total_api_calls} API calls captured, {total_images} images extracted"
        )

        return results

    async def save_session_cookies(self) -> None:
        """Manually save current session cookies to file."""
        await self._save_cookies_from_context()

    def set_cookies_file(self, cookies_file: str) -> None:
        """
        Update the cookies file path.

        Args:
            cookies_file: Path to JSON file for storing session cookies
        """
        self.cookies_file = cookies_file
        self.logger.info(f"🍪 Cookies file set to: {cookies_file}")

    def save_results(
        self,
        results: list[dict[str, Any]],
        output_file: str = "store_credentials_network_results.json",
    ) -> None:
        """
        Save results to JSON file.

        Args:
            results: list of scraping results
            output_file: Output file path
        """
        try:
            output_path = Path(output_file)

            # Create summary statistics
            summary: dict[str, Any] = {
                "total_stores": len(results),
                "successful_stores": sum(
                    1 for r in results if r["status"] == "success"
                ),
                "total_api_calls_captured": sum(
                    len(r.get("network_data", {})) for r in results
                ),
                "total_images_extracted": sum(
                    len(r.get("images", {})) for r in results
                ),
                "scraping_completed_at": time.time(),
            }

            # Combine summary and results
            output_data: dict[str, Any] = {"summary": summary, "results": results}

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"💾 Results saved to: {output_path}")

        except Exception as e:
            self.logger.error(f"❌ Error saving results: {e}")

    async def _detect_captcha(self, page: Page) -> bool:
        """
        Detect if a CAPTCHA is present on the current page.

        Args:
            page: Playwright page instance

        Returns:
            True if CAPTCHA is detected, False otherwise
        """
        try:
            # First check URL for CAPTCHA/punishment indicators
            current_url = page.url
            if any(
                indicator in current_url.lower()
                for indicator in ["punish", "captcha", "verify", "challenge"]
            ):
                self.logger.info(f"🔍 CAPTCHA detected in URL: {current_url}")
                return True

            # Check page content for CAPTCHA indicators
            page_content = await page.content()
            if any(
                text in page_content.lower()
                for text in [
                    "unusual traffic",
                    "slide to verify",
                    "security verification",
                    "sorry, we have detected",
                    "click to feedback",
                ]
            ):
                self.logger.info("🔍 CAPTCHA detected in page content")
                return True

            # Debug: Log some page information
            self.logger.info(f"🔍 Debug - Current URL: {current_url}")
            self.logger.info(f"🔍 Debug - Page title: {await page.title()}")

            # Check for iframes (CAPTCHA might be in an iframe)
            iframes = await page.query_selector_all("iframe")
            self.logger.info(f"🔍 Debug - Found {len(iframes)} iframes")

            # Look for common CAPTCHA elements with expanded selectors
            captcha_selectors = [
                # More specific selectors based on AliExpress CAPTCHAs
                'iframe[src*="nocaptcha"]',
                'iframe[src*="captcha"]',
                'div[class*="nc-container"]',
                'div[class*="nc_wrapper"]',
                'div[class*="slider-wrap"]',
                '[class*="nc_scale"]',
                '[class*="slider"]',
                ".nc_iconfont.btn_slide",
                ".btn_slide",
                '[class*="captcha"]',
                '[id*="captcha"]',
                # Input elements for CAPTCHA
                'input[placeholder*="slide"]',
                'input[placeholder*="verify"]',
                # Common CAPTCHA containers
                ".captcha-container",
                ".verification-container",
                ".slider-container",
                # Generic patterns that might indicate CAPTCHA
                'div:has-text("Please slide to verify")',
                'div:has-text("slide to verify")',
                'div:has-text("unusual traffic")',
                # Button or clickable elements
                'button:has-text("slide")',
                'button:has-text("verify")',
            ]

            for selector in captcha_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        self.logger.info(
                            f"🔍 Found {len(elements)} elements matching: {selector}"
                        )
                        for i, element in enumerate(elements):
                            is_visible = await element.is_visible()
                            self.logger.info(f"🔍 Element {i}: visible={is_visible}")
                            if is_visible:
                                self.logger.info(f"🔍 CAPTCHA detected: {selector}")
                                return True
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue

            # If no elements found, dump page structure for debugging
            self.logger.info(
                "🔍 No CAPTCHA elements found, analyzing page structure..."
            )

            # Look for any elements containing key CAPTCHA words
            try:
                all_text_elements = await page.query_selector_all("*")
                captcha_words = ["slide", "verify", "captcha", "unusual", "traffic"]

                for element in all_text_elements[:50]:  # Check first 50 elements
                    try:
                        text_content = await element.text_content()
                        if text_content and any(
                            word in text_content.lower() for word in captcha_words
                        ):
                            tag_name = await element.evaluate("el => el.tagName")
                            class_name = await element.evaluate("el => el.className")
                            self.logger.info(
                                f"🔍 Found potential CAPTCHA text: '{text_content}' in <{tag_name}> class='{class_name}'"
                            )
                    except:
                        continue
            except Exception as e:
                self.logger.debug(f"Error analyzing page structure: {e}")

            return False

        except Exception as e:
            self.logger.warning(f"Error detecting CAPTCHA: {e}")
            return False

    async def _solve_captcha(self, page: Page) -> bool:
        """
        Attempt to solve detected CAPTCHA using the AliExpress CAPTCHA solver.

        Args:
            page: Playwright page instance

        Returns:
            True if CAPTCHA was solved successfully, False otherwise
        """
        try:
            # First check if CAPTCHA is in an iframe
            iframes = await page.query_selector_all(
                'iframe[src*="captcha"], iframe[src*="nocaptcha"]'
            )

            if iframes:
                self.logger.info(
                    f"🔍 Found {len(iframes)} CAPTCHA iframes, attempting iframe-based solving..."
                )

                for iframe in iframes:
                    try:
                        # Get iframe content frame
                        # Skip iframe-specific handling for now
                        # The AdvancedCaptchaSolver works on the main page context
                        continue
                    except Exception as e:
                        self.logger.debug(
                            f"Failed to solve CAPTCHA in iframe {iframe}: {e}"
                        )
                        continue

            # If iframe solving failed or no iframe found, try main page context
            self.logger.info("🔄 Trying CAPTCHA solving in main page context...")

            # Initialize CAPTCHA solver with the existing main page
            captcha_solver = AdvancedCaptchaSolver(page)

            # Try to solve slider CAPTCHA
            success = await captcha_solver.detect_and_solve_captcha()

            if success:
                self.logger.success("✅ CAPTCHA solved successfully!")
                return True

            self.logger.warning("⚠️ Failed to solve CAPTCHA")
            return False

        except Exception as e:
            self.logger.error(f"❌ Error solving CAPTCHA: {e}")
            return False

    async def _wait_for_credential_api(
        self, page: Page, store_id: str, timeout: int = 15000
    ) -> bool:
        """
        Wait for the credential API call to be made after CAPTCHA solving.

        Args:
            page: The Playwright page
            store_id: Store ID being processed
            timeout: Maximum time to wait in milliseconds

        Returns:
            True if credential API call was captured, False if timeout
        """
        start_time = time.time()
        initial_count = len(
            [k for k in self.network_data.keys() if store_id in k and "credential" in k]
        )

        while (time.time() - start_time) < (timeout / 1000):
            current_count = len(
                [
                    k
                    for k in self.network_data.keys()
                    if store_id in k and "credential" in k
                ]
            )

            # Check if we got new credential API data
            if current_count > initial_count:
                self.logger.success(
                    f"🎯 New credential API data captured for store {store_id}"
                )
                return True

            # Wait a bit before checking again
            await page.wait_for_timeout(1000)

        self.logger.warning(
            f"⏰ Timeout waiting for credential API call for store {store_id}"
        )
        return False

    async def _wait_for_certificate_images(
        self, page: Page, store_id: str, max_wait: int = 30
    ) -> list[str]:
        """
        Wait for certificate images to render on the page using exponential backoff.

        Args:
            page: The Playwright page
            store_id: Store ID being processed
            max_wait: Maximum time to wait in seconds

        Returns:
            list of base64 image sources found
        """
        self.logger.info(
            f"🖼️ Waiting for certificate images to render for store {store_id}..."
        )

        images_found: list[str] = []
        wait_time = 1  # Start with 1 second
        total_waited = 0

        while total_waited < max_wait:
            try:
                # Look for images with the specific class
                image_elements = await page.query_selector_all(
                    "img.viewer-move.viewer-transition"
                )

                # If specific class not found, try broader searches
                if not image_elements:
                    # Try other common certificate image selectors
                    selectors = [
                        'img[src*="base64"]',
                        'img[src^="data:image/"]',
                        "img.viewer-move",
                        "img.viewer-transition",
                        'img[alt*="license"]',
                        'img[alt*="certificate"]',
                        "#container img",
                        ".tab-content img",
                        'img[src*="credential"]',
                    ]

                    for selector in selectors:
                        image_elements = await page.query_selector_all(selector)
                        if image_elements:
                            self.logger.info(
                                f"🔍 Found {len(image_elements)} images with selector: {selector}"
                            )
                            break

                # Debug: Show all images on page for troubleshooting
                if (
                    not image_elements and total_waited < 5
                ):  # Only debug on first few attempts
                    all_images = await page.query_selector_all("img")
                    if all_images:
                        self.logger.info(
                            f"🔍 Debug: Found {len(all_images)} total images on page"
                        )
                        for i, img in enumerate(all_images[:5]):  # Show first 5
                            try:
                                src = await img.get_attribute("src")
                                class_name = await img.get_attribute("class")
                                alt = await img.get_attribute("alt")
                                self.logger.debug(
                                    f"  Image {i + 1}: src={src[:50] if src else 'None'}... class={class_name} alt={alt}"
                                )
                            except:
                                pass
                    else:
                        self.logger.debug("🔍 Debug: No images found on page at all")

                if image_elements:
                    self.logger.success(
                        f"🎯 Found {len(image_elements)} certificate images!"
                    )

                    for i, img_element in enumerate(image_elements):
                        try:
                            # Get the src attribute
                            src = await img_element.get_attribute("src")
                            if src and (
                                src.startswith("data:image/") or "base64" in src
                            ):
                                # Check if this is a real certificate image, not a placeholder
                                base64_data = src.split(",", 1)[1] if "," in src else ""
                                image_size = len(base64_data)

                                # Skip very small images (likely placeholders/icons)
                                if image_size < 5000:  # Less than ~3.7KB
                                    self.logger.debug(
                                        f"📋 Skipping small image {i + 1} (size: {image_size} chars): likely placeholder"
                                    )
                                    continue

                                images_found.append(src)
                                self.logger.info(
                                    f"📸 Captured certificate image {i + 1}: {src[:50]}... (size: {image_size} chars)"
                                )
                            elif src:
                                self.logger.info(
                                    f"🔗 Found image URL (not base64): {src[:50]}..."
                                )
                        except Exception as e:
                            self.logger.warning(
                                f"⚠️ Error extracting image {i + 1}: {e}"
                            )

                    if images_found:
                        return images_found
                else:
                    self.logger.debug(
                        f"⏳ No certificate images found yet, waiting {wait_time}s..."
                    )

                # Wait with exponential backoff
                await page.wait_for_timeout(wait_time * 1000)
                total_waited += wait_time
                wait_time = min(wait_time * 2, 8)  # Double wait time, max 8 seconds

            except Exception as e:
                self.logger.warning(f"⚠️ Error checking for images: {e}")
                await page.wait_for_timeout(2000)
                total_waited += 2

        self.logger.warning(
            f"⏰ Timeout waiting for certificate images for store {store_id}"
        )
        return images_found

    async def _wait_for_certificate_images_with_captcha_monitoring(
        self, page: Page, store_id: str, max_wait: int = 45
    ) -> list[str]:
        """
        Wait for certificate images while monitoring for dynamic CAPTCHA appearance.

        Args:
            page: The Playwright page
            store_id: Store ID being processed
            max_wait: Maximum time to wait in seconds

        Returns:
            list of base64 image sources found
        """
        self.logger.info(
            f"🖼️ Waiting for certificate images with CAPTCHA monitoring for store {store_id}..."
        )

        images_found: list[str] = []
        wait_time = 1  # Start with 1 second
        total_waited = 0
        last_captcha_check = 0

        while total_waited < max_wait:
            try:
                # Check for CAPTCHA every 10 seconds
                if total_waited - last_captcha_check >= 10:
                    self.logger.info("🔍 Checking for dynamically appearing CAPTCHA...")
                    captcha_detected = await self._detect_captcha(page)
                    if captcha_detected:
                        self.logger.info(
                            "🤖 Dynamic CAPTCHA detected! Attempting to solve..."
                        )
                        captcha_solved = await self._solve_captcha(page)
                        if captcha_solved:
                            self.logger.success("✅ Dynamic CAPTCHA solved!")
                            await page.wait_for_timeout(12000)  # Wait after solving
                        else:
                            self.logger.warning("⚠️ Failed to solve dynamic CAPTCHA")
                    last_captcha_check = total_waited

                # Look for images with the specific class
                image_elements = await page.query_selector_all(
                    "img.viewer-move.viewer-transition"
                )

                # If specific class not found, try broader searches
                if not image_elements:
                    # Try other common certificate image selectors
                    selectors = [
                        'img[src*="base64"]',
                        'img[src^="data:image/"]',
                        "img.viewer-move",
                        "img.viewer-transition",
                        'img[alt*="license"]',
                        'img[alt*="certificate"]',
                        "#container img",
                        ".tab-content img",
                        'img[src*="credential"]',
                    ]

                    for selector in selectors:
                        image_elements = await page.query_selector_all(selector)
                        if image_elements:
                            self.logger.info(
                                f"🔍 Found {len(image_elements)} images with selector: {selector}"
                            )
                            break

                # Debug: Show all images on page for troubleshooting
                if (
                    not image_elements and total_waited < 5
                ):  # Only debug on first few attempts
                    all_images = await page.query_selector_all("img")
                    if all_images:
                        self.logger.info(
                            f"🔍 Debug: Found {len(all_images)} total images on page"
                        )
                        for i, img in enumerate(all_images[:5]):  # Show first 5
                            try:
                                src = await img.get_attribute("src")
                                class_name = await img.get_attribute("class")
                                alt = await img.get_attribute("alt")
                                self.logger.debug(
                                    f"  Image {i + 1}: src={src[:50] if src else 'None'}... class={class_name} alt={alt}"
                                )
                            except:
                                pass
                    else:
                        self.logger.debug("🔍 Debug: No images found on page at all")

                if image_elements:
                    self.logger.success(
                        f"🎯 Found {len(image_elements)} certificate images!"
                    )

                    for i, img_element in enumerate(image_elements):
                        try:
                            # Get the src attribute
                            src = await img_element.get_attribute("src")
                            if src and (
                                src.startswith("data:image/") or "base64" in src
                            ):
                                # Check if this is a real certificate image, not a placeholder
                                base64_data = src.split(",", 1)[1] if "," in src else ""
                                image_size = len(base64_data)

                                # Skip very small images (likely placeholders/icons)
                                if image_size < 5000:  # Less than ~3.7KB
                                    self.logger.debug(
                                        f"📋 Skipping small image {i + 1} (size: {image_size} chars): likely placeholder"
                                    )
                                    continue

                                images_found.append(src)
                                self.logger.info(
                                    f"📸 Captured certificate image {i + 1}: {src[:50]}... (size: {image_size} chars)"
                                )
                            elif src:
                                self.logger.info(
                                    f"🔗 Found image URL (not base64): {src[:50]}..."
                                )
                        except Exception as e:
                            self.logger.warning(
                                f"⚠️ Error extracting image {i + 1}: {e}"
                            )

                    if images_found:
                        return images_found
                else:
                    self.logger.debug(
                        f"⏳ No certificate images found yet, waiting {wait_time}s..."
                    )

                # Wait with exponential backoff
                await page.wait_for_timeout(wait_time * 1000)
                total_waited += wait_time
                wait_time = min(wait_time * 2, 8)  # Double wait time, max 8 seconds

            except Exception as e:
                self.logger.warning(f"⚠️ Error checking for images: {e}")
                await page.wait_for_timeout(2000)
                total_waited += 2

        self.logger.warning(
            f"⏰ Timeout waiting for certificate images for store {store_id} with CAPTCHA monitoring"
        )
        return images_found


# Example usage
if __name__ == "__main__":

    async def main() -> None:
        scraper = StoreCredentialsNetworkScraper(
            timeout=15000, delay_between_requests=1.0, max_retries=2
        )

        # Demo store IDs
        demo_stores = ["1234567890", "9876543210", "5555555555"]

        def progress_callback(current: int, total: int, store_id: str) -> None:
            print(f"📊 Progress: {current}/{total} - Processing store {store_id}")

        results = await scraper.scrape_store_credentials(
            demo_stores, progress_callback=progress_callback
        )

        scraper.save_results(results)

        # Print summary
        success_count = sum(1 for r in results if r["status"] == "success")
        total_images = sum(len(r.get("images", {})) for r in results)
        total_apis = sum(len(r.get("network_data", {})) for r in results)

        print(f"\n🎯 Network Scraping Summary:")
        print(f"   Stores processed: {len(results)}")
        print(f"   Successful: {success_count}")
        print(f"   API calls captured: {total_apis}")
        print(f"   Images extracted: {total_images}")

    asyncio.run(main())
