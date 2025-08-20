#!/usr/bin/env python3
"""
Async AliExpress Cookie Generator with Captcha Solving
====================================================

Asynchronous cookie generation using Playwright for AliExpress scraping with
integrated captcha solving capabilities.

Features:
- Async headless browser automation to collect necessary cookies
- Session data caching with custom timestamp validation
- Automatic cookie refresh when expired
- Bot challenge bypass with captcha solving
- Compatible with AsyncIO event loops

Author: Enhanced for AliExpress scraping with captcha solving (Async version)
Date: August 2025
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


class AsyncCookieGenerator:
    """
    Asynchronous automated cookie generator for AliExpress using Playwright.

    This class handles the automation of cookie collection from AliExpress
    using a headless browser, with intelligent caching to minimize browser usage.
    """

    def __init__(
        self,
        cache_file: str = "session_cache.json",
        cache_validity_minutes: int = 1,
        headless: bool = True,
        base_url: str = "https://www.aliexpress.us/",
        proxy: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the cookie generator.

        Args:
            cache_file: Path to the session cache file
            cache_validity_minutes: Minutes before cache expires
            headless: Whether to run browser in headless mode
            base_url: Base URL for AliExpress
            proxy: Proxy configuration dict
        """
        self.cache_file = Path(cache_file)
        self.cache_validity_minutes = cache_validity_minutes
        self.cache_validity_seconds = cache_validity_minutes * 60
        self.headless = headless
        self.base_url = base_url
        self.proxy = proxy

        # Browser configuration
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        self.browser_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        # Essential cookies that must be present for valid session
        self.essential_cookies = [
            "aep_usuc_f",
            "_gcl_au",
            "ali_apache_id",
            "aep_common_f",
        ]

    def _load_cached_session(self) -> Optional[Dict[str, Any]]:
        """
        Load session data from cache file if it exists and is valid.

        Returns:
            Cached session data or None if cache is invalid/expired
        """
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            cached_time = cache_data.get("timestamp", 0)
            current_time = time.time()

            if current_time - cached_time < self.cache_validity_seconds:
                print(
                    f"✅ Using cached session (age: {int(current_time - cached_time)}s)"
                )
                return cache_data
            else:
                print(
                    f"⏰ Cache expired (age: {int(current_time - cached_time)}s), refreshing..."
                )
                return None

        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️ Invalid cache file: {e}")
            return None

    def _save_session_cache(
        self, cookies: str, additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save session data to cache file.

        Args:
            cookies: Cookie string to cache
            additional_data: Additional session data to store
        """
        cache_data: Dict[str, Any] = {
            "timestamp": time.time(),
            "cookies": cookies,
            "user_agent": self.user_agent,
            "base_url": self.base_url,
        }

        if additional_data:
            cache_data.update(additional_data)

        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
            print(f"💾 Session cached to {self.cache_file}")
        except Exception as e:
            print(f"⚠️ Failed to save cache: {e}")

    async def _extract_cookies_from_context(self, context: BrowserContext) -> str:
        """
        Extract cookies from browser context and format them as a cookie string.

        Args:
            context: Playwright browser context

        Returns:
            Formatted cookie string for HTTP headers
        """
        cookies = await context.cookies()
        cookie_pairs = []

        for cookie in cookies:
            cookie_pairs.append(f"{cookie['name']}={cookie['value']}")

        return "; ".join(cookie_pairs)

    async def _setup_browser_context(self, browser: Browser) -> BrowserContext:
        """
        Set up browser context with realistic settings to avoid detection.

        Args:
            browser: Playwright browser instance

        Returns:
            Configured browser context
        """
        context_options = {
            "user_agent": self.user_agent,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone_id": "America/New_York",
            # Add some realistic browser features
            "extra_http_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        }

        # Add proxy if configured
        if self.proxy:
            context_options["proxy"] = self.proxy

        context = await browser.new_context(**context_options)

        # Add some stealth features
        await context.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)

        return context

    async def _detect_captcha_challenge(self, page: Page) -> bool:
        """
        Detect if a captcha challenge is present on the page.

        Args:
            page: Playwright page object

        Returns:
            True if captcha challenge is detected
        """
        captcha_selectors = [
            ".nc_iconfont.btn_slide",
            ".btn_slide",
            '[class*="nc_iconfont"]',
            '[class*="btn_slide"]',
            '[class*="captcha"]',
            '[class*="verify"]',
            ".slidetounlock",
            "#nc_",
        ]

        for selector in captcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    print(f"🤖 Captcha challenge detected: {selector}")
                    return True
            except:
                continue

        return False

    async def _solve_captcha_challenge(self, page: Page, max_attempts: int = 3) -> bool:
        """
        Solve captcha challenge using JavaScript automation.

        Args:
            page: Playwright page object
            max_attempts: Maximum attempts to solve the captcha

        Returns:
            True if captcha was solved successfully
        """
        print(f"🔄 Attempting to solve captcha challenge...")

        try:
            # Use JavaScript to solve the slider captcha
            for attempt in range(max_attempts):
                print(f"🎯 Captcha solving attempt {attempt + 1}/{max_attempts}")

                # Check if captcha is still present
                if not await self._detect_captcha_challenge(page):
                    print("✅ Captcha already solved!")
                    return True

                # Try to solve the slider captcha
                success = await page.evaluate("""
                    () => {
                        const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                      document.querySelector('.btn_slide') ||
                                      document.querySelector('[class*="nc_iconfont"]') ||
                                      document.querySelector('[class*="btn_slide"]');
                        
                        if (!slider) {
                            return false;
                        }
                        
                        const container = slider.closest('[class*="nc_scale"]') || 
                                        slider.closest('[class*="slider"]') ||
                                        slider.parentElement;
                        
                        if (!container) {
                            return false;
                        }
                        
                        // Simulate slider movement
                        const containerWidth = container.offsetWidth || container.clientWidth;
                        const targetLeft = containerWidth * 0.9;  // 90% across
                        
                        // Create mouse events
                        const mouseDown = new MouseEvent('mousedown', {
                            bubbles: true,
                            cancelable: true,
                            clientX: slider.getBoundingClientRect().left + 10,
                            clientY: slider.getBoundingClientRect().top + 10
                        });
                        
                        const mouseMove = new MouseEvent('mousemove', {
                            bubbles: true,
                            cancelable: true,
                            clientX: slider.getBoundingClientRect().left + targetLeft,
                            clientY: slider.getBoundingClientRect().top + 10
                        });
                        
                        const mouseUp = new MouseEvent('mouseup', {
                            bubbles: true,
                            cancelable: true,
                            clientX: slider.getBoundingClientRect().left + targetLeft,
                            clientY: slider.getBoundingClientRect().top + 10
                        });
                        
                        // Execute the drag sequence
                        slider.dispatchEvent(mouseDown);
                        
                        // Simulate gradual movement
                        for (let i = 0; i <= 10; i++) {
                            const currentX = slider.getBoundingClientRect().left + (targetLeft * i / 10);
                            const moveEvent = new MouseEvent('mousemove', {
                                bubbles: true,
                                cancelable: true,
                                clientX: currentX,
                                clientY: slider.getBoundingClientRect().top + 10
                            });
                            slider.dispatchEvent(moveEvent);
                        }
                        
                        slider.dispatchEvent(mouseUp);
                        
                        return true;
                    }
                """)

                if success:
                    # Wait for potential verification
                    await asyncio.sleep(2)

                    # Check if solved
                    if not await self._detect_captcha_challenge(page):
                        print("✅ Captcha successfully solved!")
                        return True

                # Wait between attempts
                await asyncio.sleep(1)

            print(f"❌ Failed to solve captcha after {max_attempts} attempts")
            return False

        except Exception as e:
            print(f"❌ Error solving captcha: {e}")
            return False

    async def generate_fresh_cookies(self, wait_time: int = 5) -> Dict[str, Any]:
        """
        Generate fresh cookies by visiting AliExpress with Playwright.

        Args:
            wait_time: Time to wait on page for cookies to be set (seconds)

        Returns:
            Dictionary with cookies and session metadata
        """
        print(f"🚀 Starting browser to collect fresh cookies...")

        async with async_playwright() as p:
            # Launch browser
            launch_options = {"headless": self.headless, "args": self.browser_args}
            if self.proxy:
                # Proxy is set per context, not per browser
                pass

            browser = await p.chromium.launch(**launch_options)

            try:
                context = await self._setup_browser_context(browser)
                page = await context.new_page()

                # Navigate to AliExpress
                print(f"📍 Navigating to {self.base_url}")
                response = await page.goto(
                    self.base_url, wait_until="networkidle", timeout=30000
                )

                if response and response.status >= 400:
                    print(f"⚠️ HTTP {response.status} response from AliExpress")

                # Wait for the page to load and cookies to be set
                print(f"⏳ Waiting {wait_time}s for cookies to be set...")
                await asyncio.sleep(wait_time)

                # Check for captcha challenge and solve if needed
                if await self._detect_captcha_challenge(page):
                    print("🤖 Bot challenge detected, attempting to solve...")
                    captcha_solved = await self._solve_captcha_challenge(page)

                    if captcha_solved:
                        print("✅ Bot challenge solved, waiting for page to settle...")
                        await asyncio.sleep(3)  # Allow page to settle after solving
                    else:
                        print(
                            "⚠️ Could not solve bot challenge, proceeding with available cookies..."
                        )

                # Extract cookies from context
                cookie_string = await self._extract_cookies_from_context(context)
                cookies_list = await context.cookies()

                print(f"🍪 Collected {len(cookies_list)} cookies")

                # Prepare session data
                session_data = {
                    "success": True,
                    "cookies": cookie_string,
                    "user_agent": self.user_agent,
                    "timestamp": time.time(),
                    "url": self.base_url,
                }

                # Save to cache
                self._save_session_cache(cookie_string, session_data)

                return session_data

            except Exception as e:
                print(f"❌ Error generating cookies: {e}")
                return {
                    "success": False,
                    "cookies": "",
                    "error": str(e),
                    "timestamp": time.time(),
                }

            finally:
                await browser.close()

    def validate_cookies(self, cookies: str) -> Dict[str, Any]:
        """
        Validate that essential cookies are present in the cookie string.

        Args:
            cookies: Cookie string to validate

        Returns:
            Dictionary with validation results
        """
        if not cookies:
            return {
                "valid": False,
                "missing_essential": self.essential_cookies,
                "present_essential": [],
            }

        present_essential = []
        missing_essential = []

        for essential in self.essential_cookies:
            if f"{essential}=" in cookies:
                present_essential.append(essential)
            else:
                missing_essential.append(essential)

        is_valid = len(missing_essential) <= 2  # Allow some flexibility

        return {
            "valid": is_valid,
            "missing_essential": missing_essential,
            "present_essential": present_essential,
        }

    def is_session_expired(self, session_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if a session has expired based on custom timestamp validation.

        Args:
            session_data: Session data to check, or None to load from cache

        Returns:
            True if session is expired or invalid
        """
        if session_data is None:
            session_data = self._load_cached_session()

        if not session_data:
            return True

        # Check timestamp expiration
        cached_time = session_data.get("timestamp", 0)
        current_time = time.time()

        if current_time - cached_time >= self.cache_validity_seconds:
            print(f"⏰ Session expired (age: {int(current_time - cached_time)}s)")
            return True

        # Check if essential cookies are present
        cookies = session_data.get("cookies", "")
        validation = self.validate_cookies(cookies)

        if not validation["valid"]:
            print(
                f"🔍 Session cookies invalid: missing {validation['missing_essential']}"
            )
            return True

        return False

    async def refresh_session_if_expired(self) -> Dict[str, Any]:
        """
        Check session and refresh if expired, opening https://www.aliexpress.us/ as needed.

        Returns:
            Dictionary with session data and refresh status
        """
        # Load current session
        current_session = self._load_cached_session()

        if current_session and not self.is_session_expired(current_session):
            print("✅ Current session is still valid")
            result: Dict[str, Any] = {
                "success": True,
                "cookies": current_session["cookies"],
                "refreshed": False,
                "from_cache": True,
                "timestamp": current_session.get("timestamp", time.time()),
                "user_agent": current_session.get("user_agent", self.user_agent),
            }
            return result

        print("🔄 Session expired, generating fresh cookies...")

        # Generate fresh session
        fresh_session = await self.generate_fresh_cookies()

        if fresh_session.get("success"):
            print("✅ Fresh session generated successfully")
            result = {
                "success": True,
                "cookies": fresh_session["cookies"],
                "refreshed": True,
                "from_cache": False,
                "timestamp": fresh_session["timestamp"],
                "user_agent": fresh_session["user_agent"],
            }
        else:
            print("❌ Failed to generate fresh session")
            result = {
                "success": False,
                "cookies": "",
                "refreshed": True,
                "from_cache": False,
                "error": fresh_session.get("error", "Unknown error"),
                "timestamp": time.time(),
                "user_agent": self.user_agent,
            }

        return result

    async def get_valid_cookies(self) -> Dict[str, Any]:
        """
        Get valid cookies, refreshing if necessary.

        Returns:
            Dictionary with valid cookies and metadata
        """
        return await self.refresh_session_if_expired()
