#!/usr/bin/env python3
"""
AliExpress Cookie Generator with Captcha Solving
===============================================

Automated cookie generation using Playwright for AliExpress scraping with
integrated captcha solving capabilities.

Features:
- Headless browser automation to collect necessary cookies
- Session data caching with custom timestamp validation
- Automatic cookie refresh when expired
- Bot challenge bypass with captcha solving
- Minimizes browser automation overhead

Author: Enhanced for AliExpress scraping with captcha solving
Date: August 2025
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

# Import captcha solver if available
try:
    from captcha_solver import AliExpressCaptchaSolver, CaptchaSolverIntegration # type: ignore
    captcha_solver_available = True
except ImportError:
    captcha_solver_available = False


class CookieGenerator:
    """
    Automated cookie generator for AliExpress using Playwright.

    This class handles the automation of cookie collection from AliExpress
    using a headless browser, with intelligent caching to minimize browser usage.
    """

    def __init__(
        self,
        cache_file: str = "session_cache.json",
        cache_validity_minutes: int = 1,
        headless: bool = True,
        base_url: str = "https://www.aliexpress.us",
    ):
        """
        Initialize the cookie generator.

        Args:
            cache_file: Path to store cached session data
            cache_validity_minutes: How long cached cookies remain valid (default: 1 minute)
            headless: Whether to run browser in headless mode
            base_url: Base URL for AliExpress (default: US site)
        """
        self.cache_file = Path(cache_file)
        self.cache_validity_seconds = cache_validity_minutes * 60
        self.headless = headless
        self.base_url = base_url.rstrip("/")

        # Browser configuration
        self.browser_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
        ]

        self.user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

    def _load_cached_session(self) -> Optional[Dict[str, Any]]:
        """
        Load cached session data if it exists and is still valid.

        Returns:
            Cached session data or None if cache is invalid/missing
        """
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Check if cache is still valid
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

    def _extract_cookies_from_context(self, context: BrowserContext) -> str:
        """
        Extract cookies from browser context and format them as a cookie string.

        Args:
            context: Playwright browser context

        Returns:
            Formatted cookie string for HTTP headers
        """
        cookies = context.cookies()

        # Format cookies as header string
        cookie_pairs: list[str] = []
        for cookie in cookies:
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            if name and value:
                cookie_pairs.append(f"{name}={value}")

        return "; ".join(cookie_pairs)

    def _wait_for_essential_cookies(self, page: Page, timeout: int = 30) -> bool:
        """
        Wait for essential cookies to be set by the page.

        Args:
            page: Playwright page object
            timeout: Maximum wait time in seconds

        Returns:
            True if essential cookies are found, False otherwise
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            cookies = page.context.cookies()
            cookie_names = [
                cookie.get("name", "") for cookie in cookies if cookie.get("name")
            ]

            # Check for essential AliExpress cookies
            essential_cookies = ["_m_h5_tk", "_m_h5_tk_enc"]
            has_essential = any(name in cookie_names for name in essential_cookies)

            if has_essential:
                print("✅ Essential cookies detected")
                return True

            # Wait a bit before checking again
            time.sleep(1)

        print("⚠️ Timeout waiting for essential cookies")
        return False

    def _setup_browser_context(self, browser: Browser) -> BrowserContext:
        """
        Set up browser context with proper configuration.

        Args:
            browser: Playwright browser instance

        Returns:
            Configured browser context
        """
        context = browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            # Add some realistic browser features
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        # Add some stealth features
        context.add_init_script("""
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
    
    def _detect_captcha_challenge(self, page: Page) -> bool:
        """
        Detect if a captcha challenge is present on the page.
        
        Args:
            page: Playwright page object
            
        Returns:
            True if captcha challenge is detected
        """
        try:
            # Check for common captcha indicators
            captcha_selectors = [
                '.nc_iconfont.btn_slide',
                '.btn_slide',
                '[class*="nc_iconfont"]',
                '[class*="btn_slide"]',
                'span[data-nc-lang="SLIDE"]',
                '.nc-lang-cnt',
                '[class*="captcha"]',
                '[class*="slider"]',
                '[class*="verify"]',
                '.nc_wrapper',
                '.nc_scale',
                '.nc_scale_text'
            ]
            
            for selector in captcha_selectors:
                if page.locator(selector).count() > 0:
                    print(f"🤖 Captcha challenge detected: {selector}")
                    return True
            
            # Check page content for captcha indicators
            page_content = page.content()
            captcha_keywords = [
                "captcha", "slider", "verify", "challenge", 
                "unusual traffic", "security check", "bot"
            ]
            
            content_lower = page_content.lower()
            for keyword in captcha_keywords:
                if keyword in content_lower:
                    print(f"🤖 Captcha keyword detected: {keyword}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Error detecting captcha: {e}")
            return False
    
    def _solve_captcha_challenge(self, page: Page, max_attempts: int = 3) -> bool:
        """
        Solve captcha challenge using the integrated captcha solver.
        
        Args:
            page: Playwright page object
            max_attempts: Maximum attempts to solve the captcha
            
        Returns:
            True if captcha was solved successfully
        """
        if not captcha_solver_available:
            print("⚠️ Captcha solver not available - cannot solve challenge")
            return False
        
        print(f"🔄 Attempting to solve captcha challenge...")
        
        try:
            # Use JavaScript to solve the slider captcha
            for attempt in range(max_attempts):
                print(f"🎯 Captcha solving attempt {attempt + 1}/{max_attempts}")
                
                # Check if captcha is still present
                if not self._detect_captcha_challenge(page):
                    print("✅ Captcha already solved!")
                    return True
                
                # Try to solve the slider captcha
                success = page.evaluate("""
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
                        const rect = slider.getBoundingClientRect();
                        const startX = rect.x + rect.width / 2;
                        const startY = rect.y + rect.height / 2;
                        const endX = startX + targetLeft;
                        
                        // Dispatch mouse down event
                        const downEvent = new MouseEvent('mousedown', {
                            clientX: startX,
                            clientY: startY,
                            bubbles: true,
                            cancelable: true
                        });
                        slider.dispatchEvent(downEvent);
                        
                        // Move slider
                        slider.style.left = targetLeft + 'px';
                        
                        // Dispatch mouse up event
                        setTimeout(() => {
                            const upEvent = new MouseEvent('mouseup', {
                                clientX: endX,
                                clientY: startY,
                                bubbles: true,
                                cancelable: true
                            });
                            document.dispatchEvent(upEvent);
                        }, 200);
                        
                        return true;
                    }
                """)
                
                if success:
                    print("🎯 Slider moved, waiting for validation...")
                    time.sleep(3)  # Wait for validation
                    
                    # Check if captcha was solved
                    if not self._detect_captcha_challenge(page):
                        print("✅ Captcha solved successfully!")
                        return True
                    else:
                        print("❌ Captcha still present after solving attempt")
                else:
                    print("❌ Failed to move slider")
                
                # Wait before next attempt
                if attempt < max_attempts - 1:
                    time.sleep(2)
            
            print(f"❌ Failed to solve captcha after {max_attempts} attempts")
            return False
            
        except Exception as e:
            print(f"❌ Error solving captcha: {e}")
            return False

    def generate_fresh_cookies(self, wait_time: int = 5) -> Dict[str, Any]:
        """
        Generate fresh cookies by visiting AliExpress with Playwright.

        Args:
            wait_time: Time to wait on page for cookies to be set (seconds)

        Returns:
            Dictionary with cookies and session metadata
        """
        print(f"🚀 Starting browser to collect fresh cookies...")

        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=self.headless, args=self.browser_args)

            try:
                context = self._setup_browser_context(browser)
                page = context.new_page()

                # Navigate to AliExpress
                print(f"📍 Navigating to {self.base_url}")
                response = page.goto(
                    self.base_url, wait_until="networkidle", timeout=30000
                )

                if response and response.status >= 400:
                    print(f"⚠️ HTTP {response.status} response from AliExpress")

                # Wait for the page to load and cookies to be set
                print(f"⏳ Waiting {wait_time}s for cookies to be set...")
                time.sleep(wait_time)

                # Check for captcha challenge and solve if needed
                if self._detect_captcha_challenge(page):
                    print("🤖 Bot challenge detected, attempting to solve...")
                    captcha_solved = self._solve_captcha_challenge(page)
                    
                    if captcha_solved:
                        print("✅ Bot challenge solved, waiting for page to settle...")
                        time.sleep(3)  # Allow page to settle after solving
                    else:
                        print("⚠️ Could not solve bot challenge, proceeding with available cookies...")

                # Try to wait for essential cookies
                self._wait_for_essential_cookies(page, timeout=15)

                # Extract cookies
                cookie_string = self._extract_cookies_from_context(context)
                cookies_count = len(context.cookies())

                print(f"🍪 Collected {cookies_count} cookies")

                # Prepare result with enhanced metadata
                result: Dict[str, Any] = {
                    "success": True,
                    "cookies": cookie_string,
                    "cookies_count": cookies_count,
                    "user_agent": self.user_agent,
                    "timestamp": time.time(),
                    "url": self.base_url,
                    "captcha_encountered": self._detect_captcha_challenge(page),
                    "session_id": f"session_{int(time.time())}"  # Custom session identifier
                }

                # Save to cache with enhanced metadata
                self._save_session_cache(
                    cookie_string,
                    {
                        "cookies_count": cookies_count, 
                        "url": self.base_url,
                        "captcha_encountered": result["captcha_encountered"],
                        "session_id": result["session_id"]
                    }
                )

                return result

            except Exception as e:
                print(f"❌ Failed to generate cookies: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "cookies": "",
                    "timestamp": time.time(),
                }
            finally:
                browser.close()

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
            print(f"🔍 Session cookies invalid: missing {validation['missing_essential']}")
            return True
        
        return False
    
    def refresh_session_if_expired(self) -> Dict[str, Any]:
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
                "timestamp": current_session.get("timestamp"),
                "user_agent": current_session.get("user_agent", self.user_agent)
            }
            # Add other fields from current session safely
            for key in ["cookies_count", "url", "session_id", "captcha_encountered"]:
                if key in current_session:
                    result[key] = current_session[key]
            return result
        
        # Session expired or invalid, generate fresh cookies
        print("🔄 Session expired, generating fresh cookies...")
        fresh_result = self.generate_fresh_cookies()
        
        if fresh_result["success"]:
            fresh_result["refreshed"] = True
            fresh_result["from_cache"] = False
            return fresh_result
        else:
            return {
                "success": False,
                "error": fresh_result.get("error", "Unknown error"),
                "refreshed": False,
                "cookies": ""
            }

    def get_valid_cookies(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get valid cookies, using cache if available or generating fresh ones.
        Uses the enhanced session management with custom timestamp validation.

        Args:
            force_refresh: Force generation of fresh cookies, ignoring cache

        Returns:
            Dictionary with cookies and session metadata
        """
        if force_refresh:
            # Force refresh by clearing cache and generating fresh cookies
            print("🔄 Force refresh requested, generating fresh cookies...")
            result = self.generate_fresh_cookies()
            result["from_cache"] = False
            return result
        
        # Use enhanced session management with expiration checking
        return self.refresh_session_if_expired()

    def validate_cookies(self, cookie_string: str) -> Dict[str, Any]:
        """
        Validate if cookies contain essential tokens for AliExpress API.

        Args:
            cookie_string: Cookie string to validate

        Returns:
            Validation result with details
        """
        cookies_dict: Dict[str, str] = {}

        # Parse cookie string
        for cookie in cookie_string.split("; "):
            if "=" in cookie:
                key, value = cookie.split("=", 1)
                cookies_dict[key] = value

        # Check for essential cookies
        essential_cookies = ["_m_h5_tk", "_m_h5_tk_enc"]
        found_essential: list[str] = []
        missing_essential: list[str] = []

        for cookie_name in essential_cookies:
            if cookie_name in cookies_dict:
                found_essential.append(cookie_name)
            else:
                missing_essential.append(cookie_name)

        is_valid = len(missing_essential) == 0

        return {
            "valid": is_valid,
            "total_cookies": len(cookies_dict),
            "found_essential": found_essential,
            "missing_essential": missing_essential,
            "has_auth_token": "_m_h5_tk" in cookies_dict,
        }

    def get_session_status(self) -> Dict[str, Any]:
        """
        Get current session status information.
        
        Returns:
            Dictionary with session status details
        """
        current_session = self._load_cached_session()
        
        if not current_session:
            return {
                "has_session": False,
                "expired": True,
                "details": "No session file found"
            }
        
        is_expired = self.is_session_expired(current_session)
        
        return {
            "has_session": True,
            "expired": is_expired,
            "timestamp": current_session.get("timestamp", 0),
            "age_seconds": time.time() - current_session.get("timestamp", 0),
            "session_id": current_session.get("session_id"),
            "captcha_encountered": current_session.get("captcha_encountered", False),
            "cookies_count": current_session.get("cookies_count", 0),
            "details": f"Session {'expired' if is_expired else 'valid'}"
        }

    def clear_cache(self) -> bool:
        """
        Clear the session cache file.

        Returns:
            True if cache was cleared successfully
        """
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                print(f"🗑️ Cache cleared: {self.cache_file}")
                return True
            else:
                print("ℹ️ No cache file to clear")
                return True
        except Exception as e:
            print(f"❌ Failed to clear cache: {e}")
            return False


def main():
    """Example usage of the cookie generator."""

    print("🍪 AliExpress Cookie Generator")
    print("=" * 32)
    print("Automated cookie collection with Playwright")
    print()

    # Initialize generator
    generator = CookieGenerator(
        cache_validity_minutes=1,  # 1-minute cache
        headless=True,  # Set to False to see browser
    )

    # Get valid cookies (uses cache if available)
    print("📋 Getting valid cookies...")
    result = generator.get_valid_cookies()

    if result["success"]:
        cookies = result["cookies"]
        from_cache = result.get("from_cache", False)

        print(f"✅ {'Cached' if from_cache else 'Fresh'} cookies obtained!")
        print(f"🍪 Cookie string length: {len(cookies)} chars")

        # Validate cookies
        validation = generator.validate_cookies(cookies)
        print(f"🔍 Validation: {'✅ Valid' if validation['valid'] else '❌ Invalid'}")
        print(f"   Total cookies: {validation['total_cookies']}")
        print(f"   Essential found: {validation['found_essential']}")
        if validation["missing_essential"]:
            print(f"   Missing: {validation['missing_essential']}")

        # Show first 100 chars of cookies for demo
        print(f"🎯 Sample: {cookies[:100]}...")

    else:
        print(f"❌ Failed to get cookies: {result.get('error')}")

    print()
    print("🎉 Cookie generator ready for integration!")


if __name__ == "__main__":
    main()
