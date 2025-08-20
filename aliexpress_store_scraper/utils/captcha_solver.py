#!/usr/bin/env python3
"""
AliExpress Advanced Captcha Solver
Based on proven French implementation with enhanced slider solving
"""

import asyncio
import random

from playwright.async_api import Page

from aliexpress_store_scraper.utils.logger import ScraperLogger


class AdvancedCaptchaSolver:
    """Advanced CAPTCHA solver with robust slider detection and solving"""

    def __init__(self, page: Page):
        self.page = page
        self.logger = ScraperLogger("AdvancedCaptchaSolver")

    async def detect_and_solve_captcha(self) -> bool:
        """Detect and solve AliExpress slider captchas automatically"""
        try:
            # Wait for captcha to load
            await asyncio.sleep(2)

            # Check if captcha is present
            captcha_present = await self.page.evaluate("""
                () => {
                    // Look for AliExpress specific captcha elements
                    const captchaSelectors = [
                        '.nc_iconfont.btn_slide',
                        '.btn_slide',
                        '[class*="nc_iconfont"]',
                        '[class*="btn_slide"]',
                        'span[data-nc-lang="SLIDE"]',
                        '.nc-lang-cnt',
                        '[class*="captcha"]',
                        '[class*="slider"]',
                        '[class*="verify"]',
                        '[class*="puzzle"]',
                        'iframe[src*="captcha"]',
                        '.nc_wrapper',
                        '.nc_scale',
                        '.nc_scale_text'
                    ];
                    
                    for (const selector of captchaSelectors) {
                        if (document.querySelector(selector)) {
                            return true;
                        }
                    }
                    
                    // Check inside iframes
                    const iframes = document.querySelectorAll('iframe');
                    for (const iframe of iframes) {
                        try {
                            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                            for (const selector of captchaSelectors) {
                                if (iframeDoc.querySelector(selector)) {
                                    return true;
                                }
                            }
                        } catch (e) {
                            // Ignore iframe access errors
                        }
                    }
                    
                    return false;
                }
            """)

            if not captcha_present:
                self.logger.info("✅ No captcha detected")
                return True

            self.logger.info("🛡️ Captcha detected! Attempting automatic resolution...")

            # Wait for complete loading
            await asyncio.sleep(3)

            # Try to solve with multiple methods
            success = await self.solve_slide_captcha()

            if not success:
                self.logger.info("🔄 Trying with maximum distance...")
                success = await self.solve_captcha_with_max_distance()

            if success:
                self.logger.success("✅ Captcha solved successfully!")
                await asyncio.sleep(2)
                return True
            else:
                self.logger.error("❌ Failed to solve captcha automatically")
                return False

        except Exception as e:
            self.logger.error(f"⚠️ Error during captcha detection: {str(e)}")
            return False

    async def solve_slide_captcha(self) -> bool:
        """Solve slider captcha with robust approach"""
        try:
            # Get detailed captcha information
            captcha_info = await self.page.evaluate("""
                () => {
                    // First try main page
                    let slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                document.querySelector('.btn_slide') ||
                                document.querySelector('[class*="nc_iconfont"]') ||
                                document.querySelector('[class*="btn_slide"]');
                    
                    let container = null;
                    
                    // If not found in main page, check iframes
                    if (!slider) {
                        const iframes = document.querySelectorAll('iframe');
                        for (const iframe of iframes) {
                            try {
                                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                                if (iframeDoc) {
                                    slider = iframeDoc.querySelector('.nc_iconfont.btn_slide') ||
                                            iframeDoc.querySelector('.btn_slide') ||
                                            iframeDoc.querySelector('[class*="nc_iconfont"]') ||
                                            iframeDoc.querySelector('[class*="btn_slide"]') ||
                                            iframeDoc.querySelector('.nc-container .nc-btn') ||
                                            iframeDoc.querySelector('.slidetounlock') ||
                                            iframeDoc.querySelector('[class*="slide"]') ||
                                            iframeDoc.querySelector('.captcha-slider');
                                    
                                    if (slider) {
                                        // Get iframe position to adjust coordinates
                                        const iframeRect = iframe.getBoundingClientRect();
                                        const sliderRect = slider.getBoundingClientRect();
                                        
                                        // Find container in iframe
                                        container = slider.closest('.nc-container') ||
                                                  slider.closest('.nc_scale') ||
                                                  slider.closest('[class*="slider"]') ||
                                                  slider.closest('.captcha-container') ||
                                                  slider.parentElement;
                                        
                                        const containerRect = container ? container.getBoundingClientRect() : sliderRect;
                                        
                                        return {
                                            sliderLeft: iframeRect.left + sliderRect.left,
                                            sliderTop: iframeRect.top + sliderRect.top,
                                            sliderWidth: sliderRect.width,
                                            sliderHeight: sliderRect.height,
                                            containerLeft: iframeRect.left + containerRect.left,
                                            containerWidth: containerRect.width,
                                            currentLeft: parseFloat(slider.style.left || '0'),
                                            isInIframe: true,
                                            iframe: iframe
                                        };
                                    }
                                }
                            } catch (e) {
                                // Ignore iframe access errors
                                console.log('Iframe access error:', e);
                            }
                        }
                    }
                    
                    if (!slider) {
                        return null;
                    }
                    
                    // Find captcha container in main page
                    container = slider.closest('[class*="nc_scale"]') || 
                              slider.closest('[class*="slider"]') ||
                              slider.parentElement;
                    
                    const sliderRect = slider.getBoundingClientRect();
                    const containerRect = container ? container.getBoundingClientRect() : sliderRect;
                    
                    return {
                        sliderLeft: sliderRect.left,
                        sliderTop: sliderRect.top,
                        sliderWidth: sliderRect.width,
                        sliderHeight: sliderRect.height,
                        containerLeft: containerRect.left,
                        containerWidth: containerRect.width,
                        currentLeft: parseFloat(slider.style.left || '0'),
                        isInIframe: false
                    };
                }
            """)

            if not captcha_info:
                self.logger.error("❌ Slider information not found")
                return False

            self.logger.info(
                f"🎯 Slider found: position=({captcha_info['sliderLeft']:.0f}, {captcha_info['sliderTop']:.0f}), width={captcha_info['sliderWidth']:.0f}"
            )
            self.logger.info(
                f"📏 Container: width={captcha_info['containerWidth']:.0f}"
            )

            # Calculate slide distance (go completely to the end)
            slide_distance = (
                captcha_info["containerWidth"] * 1.0
            )  # 100% - go completely to the end

            # Start position (center of slider)
            start_x = captcha_info["sliderLeft"] + captcha_info["sliderWidth"] / 2
            start_y = captcha_info["sliderTop"] + captcha_info["sliderHeight"] / 2

            # End position
            end_x = start_x + slide_distance

            self.logger.info(
                f"🖱️ Sliding from ({start_x:.0f}, {start_y:.0f}) to ({end_x:.0f}, {start_y:.0f}) - Distance: {slide_distance:.0f}px"
            )

            # Perform sliding with natural approach
            await self.page.mouse.move(start_x, start_y)
            await asyncio.sleep(0.2)

            # Press mouse button
            await self.page.mouse.down()
            await asyncio.sleep(0.1)

            # Progressive sliding with acceleration/deceleration
            steps = 25
            for i in range(1, steps + 1):
                progress = i / steps

                # Natural acceleration curve (slow start, fast middle, slow end)
                if progress < 0.3:
                    ease = progress * progress * 2.5  # Acceleration
                elif progress > 0.7:
                    ease = 1 - (1 - progress) * (1 - progress) * 2.5  # Deceleration
                else:
                    ease = progress  # Constant speed

                current_x = start_x + slide_distance * ease
                current_y = start_y + random.uniform(-1, 1)  # Slight vertical variation

                await self.page.mouse.move(current_x, current_y)
                await asyncio.sleep(random.uniform(0.015, 0.025))

            # Release mouse button
            await self.page.mouse.up()
            await asyncio.sleep(1.5)

            # Check if captcha was solved
            captcha_solved = await self.page.evaluate("""
                () => {
                    const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                  document.querySelector('.btn_slide') ||
                                  document.querySelector('[class*="nc_iconfont"]') ||
                                  document.querySelector('[class*="btn_slide"]');
                    
                    if (slider) {
                        const style = window.getComputedStyle(slider);
                        const left = parseFloat(style.left);
                        
                        // If slider moved significantly
                        if (left > 10) {
                            return true;
                        }
                        
                        // Check if text changed
                        const slideText = document.querySelector('.nc-lang-cnt');
                        if (slideText && !slideText.textContent.includes('verifier')) {
                            return true;
                        }
                        
                        // Check if captcha disappeared
                        const captchaContainer = document.querySelector('[class*="nc_scale"]') ||
                                               document.querySelector('[class*="captcha"]') ||
                                               document.querySelector('[class*="slider"]');
                        if (!captchaContainer || captchaContainer.style.display === 'none') {
                            return true;
                        }
                        
                        // Check if products are visible (success indicator)
                        const productLinks = document.querySelectorAll('a[href*="item"]');
                        if (productLinks.length > 0) {
                            return true;
                        }
                    }
                    
                    return false;
                }
            """)

            if captcha_solved:
                self.logger.success("✅ Sliding successful!")
                return True
            else:
                self.logger.warning("❌ Sliding failed, trying improved approach...")
                return await self.retry_slide_captcha_improved()

        except Exception as e:
            self.logger.error(f"⚠️ Error solving captcha: {str(e)}")
            return False

    async def retry_slide_captcha_improved(self) -> bool:
        """Retry with different approach"""
        try:
            self.logger.info("🔄 Retry with JavaScript approach...")

            # Use more direct JavaScript approach
            success = await self.page.evaluate("""
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
                    
                    const containerWidth = container.offsetWidth || container.clientWidth;
                    const targetLeft = containerWidth * 0.98;  // 98% for retry
                    
                    // Simulate movement by changing style
                    slider.style.left = targetLeft + 'px';
                    
                    // Trigger necessary events
                    const rect = slider.getBoundingClientRect();
                    
                    // Mousedown
                    const downEvent = new MouseEvent('mousedown', {
                        clientX: rect.x + 5,
                        clientY: rect.y + rect.height / 2,
                        bubbles: true,
                        cancelable: true
                    });
                    slider.dispatchEvent(downEvent);
                    
                    // Wait then trigger mouseup
                    setTimeout(() => {
                        const upEvent = new MouseEvent('mouseup', {
                            clientX: rect.x + targetLeft,
                            clientY: rect.y + rect.height / 2,
                            bubbles: true,
                            cancelable: true
                        });
                        document.dispatchEvent(upEvent);
                    }, 500);
                    
                    return true;
                }
            """)

            if success:
                await asyncio.sleep(2)

                # Check again
                captcha_solved = await self.page.evaluate("""
                    () => {
                        const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                      document.querySelector('.btn_slide') ||
                                      document.querySelector('[class*="nc_iconfont"]') ||
                                      document.querySelector('[class*="btn_slide"]');
                        
                        if (slider) {
                            const style = window.getComputedStyle(slider);
                            const left = parseFloat(style.left);
                            return left > 10;
                        }
                        
                        return false;
                    }
                """)

                if captcha_solved:
                    return True
                else:
                    # Third attempt: slide completely to the end
                    self.logger.info("🔄 Third attempt: complete sliding...")
                    return await self.final_slide_attempt()

            return False

        except Exception as e:
            self.logger.error(f"⚠️ Error during retry: {str(e)}")
            return False

    async def final_slide_attempt(self) -> bool:
        """Final attempt: slide completely to the end"""
        try:
            # Slide completely to the end
            success = await self.page.evaluate("""
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
                    
                    const containerWidth = container.offsetWidth || container.clientWidth;
                    const targetLeft = containerWidth;  // 100% - go completely to the end
                    
                    // Simulate movement by changing style
                    slider.style.left = targetLeft + 'px';
                    
                    // Trigger necessary events
                    const rect = slider.getBoundingClientRect();
                    
                    // Mousedown
                    const downEvent = new MouseEvent('mousedown', {
                        clientX: rect.x + 5,
                        clientY: rect.y + rect.height / 2,
                        bubbles: true,
                        cancelable: true
                    });
                    slider.dispatchEvent(downEvent);
                    
                    // Wait then trigger mouseup
                    setTimeout(() => {
                        const upEvent = new MouseEvent('mouseup', {
                            clientX: rect.x + targetLeft,
                            clientY: rect.y + rect.height / 2,
                            bubbles: true,
                            cancelable: true
                        });
                        document.dispatchEvent(upEvent);
                    }, 500);
                    
                    return true;
                }
            """)

            if success:
                await asyncio.sleep(2)

                # Check again
                captcha_solved = await self.page.evaluate("""
                    () => {
                        const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                      document.querySelector('.btn_slide') ||
                                      document.querySelector('[class*="nc_iconfont"]') ||
                                      document.querySelector('[class*="btn_slide"]');
                        
                        if (slider) {
                            const style = window.getComputedStyle(slider);
                            const left = parseFloat(style.left);
                            return left > 10;
                        }
                        
                        return false;
                    }
                """)

                return captcha_solved

            return False

        except Exception as e:
            self.logger.error(f"⚠️ Error during final attempt: {str(e)}")
            return False

    async def solve_captcha_with_max_distance(self) -> bool:
        """Solve captcha by sliding with maximum distance"""
        try:
            self.logger.info("🎯 Trying with maximum distance...")

            # Get slider information with iframe support
            slider_info = await self.page.evaluate("""
                () => {
                    // First try main page
                    let slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                document.querySelector('.btn_slide') ||
                                document.querySelector('[class*="nc_iconfont"]') ||
                                document.querySelector('[class*="btn_slide"]');
                    
                    let container = null;
                    
                    // If not found in main page, check iframes
                    if (!slider) {
                        const iframes = document.querySelectorAll('iframe');
                        for (const iframe of iframes) {
                            try {
                                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                                if (iframeDoc) {
                                    slider = iframeDoc.querySelector('.nc_iconfont.btn_slide') ||
                                            iframeDoc.querySelector('.btn_slide') ||
                                            iframeDoc.querySelector('[class*="nc_iconfont"]') ||
                                            iframeDoc.querySelector('[class*="btn_slide"]') ||
                                            iframeDoc.querySelector('.nc-container .nc-btn') ||
                                            iframeDoc.querySelector('.slidetounlock') ||
                                            iframeDoc.querySelector('[class*="slide"]') ||
                                            iframeDoc.querySelector('.captcha-slider');
                                    
                                    if (slider) {
                                        // Get iframe position to adjust coordinates
                                        const iframeRect = iframe.getBoundingClientRect();
                                        const sliderRect = slider.getBoundingClientRect();
                                        
                                        container = slider.closest('.nc-container') ||
                                                  slider.closest('.nc_scale') ||
                                                  slider.closest('[class*="slider"]') ||
                                                  slider.closest('.captcha-container') ||
                                                  slider.parentElement;
                                        
                                        const containerRect = container ? container.getBoundingClientRect() : sliderRect;
                                        
                                        return {
                                            sliderLeft: iframeRect.left + sliderRect.left,
                                            sliderTop: iframeRect.top + sliderRect.top,
                                            sliderWidth: sliderRect.width,
                                            sliderHeight: sliderRect.height,
                                            containerLeft: iframeRect.left + containerRect.left,
                                            containerWidth: containerRect.width,
                                            isInIframe: true
                                        };
                                    }
                                }
                            } catch (e) {
                                // Ignore iframe access errors
                            }
                        }
                    }
                    
                    if (!slider) {
                        return null;
                    }
                    
                    container = slider.closest('[class*="nc_scale"]') || 
                              slider.closest('[class*="slider"]') ||
                              slider.parentElement;
                    
                    const sliderRect = slider.getBoundingClientRect();
                    const containerRect = container ? container.getBoundingClientRect() : sliderRect;
                    
                    return {
                        sliderLeft: sliderRect.left,
                        sliderTop: sliderRect.top,
                        sliderWidth: sliderRect.width,
                        sliderHeight: sliderRect.height,
                        containerLeft: containerRect.left,
                        containerWidth: containerRect.width,
                        isInIframe: false
                    };
                }
            """)

            if not slider_info:
                return False

            # Start position (center of slider)
            start_x = slider_info["sliderLeft"] + slider_info["sliderWidth"] / 2
            start_y = slider_info["sliderTop"] + slider_info["sliderHeight"] / 2

            # End position (completely to the right of container)
            end_x = (
                slider_info["containerLeft"] + slider_info["containerWidth"] + 50
            )  # 50px extra to be sure

            self.logger.info(
                f"🖱️ Maximum slide from ({start_x:.0f}, {start_y:.0f}) to ({end_x:.0f}, {start_y:.0f})"
            )

            # Perform sliding with Playwright
            await self.page.mouse.move(start_x, start_y)
            await asyncio.sleep(0.2)

            # Press button
            await self.page.mouse.down()
            await asyncio.sleep(0.1)

            # Progressive sliding to the end
            steps = 30
            for i in range(1, steps + 1):
                progress = i / steps
                current_x = start_x + (end_x - start_x) * progress
                current_y = start_y + random.uniform(-2, 2)  # Slight variation

                await self.page.mouse.move(current_x, current_y)
                await asyncio.sleep(random.uniform(0.02, 0.03))

            # Release button
            await self.page.mouse.up()
            await asyncio.sleep(2)

            # Check if captcha was solved
            captcha_solved = await self.page.evaluate("""
                () => {
                    // Check if captcha disappeared
                    const captchaContainer = document.querySelector('[class*="nc_scale"]') ||
                                           document.querySelector('[class*="captcha"]') ||
                                           document.querySelector('[class*="slider"]');
                    
                    if (!captchaContainer || captchaContainer.style.display === 'none') {
                        return true;
                    }
                    
                    // Check if products are visible
                    const productLinks = document.querySelectorAll('a[href*="item"]');
                    if (productLinks.length > 0) {
                        return true;
                    }
                    
                    // Check if slider moved
                    const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                  document.querySelector('.btn_slide') ||
                                  document.querySelector('[class*="nc_iconfont"]') ||
                                  document.querySelector('[class*="btn_slide"]');
                    
                    if (slider) {
                        const style = window.getComputedStyle(slider);
                        const left = parseFloat(style.left);
                        if (left > 50) {  // If slider moved significantly
                            return true;
                        }
                    }
                    
                    return false;
                }
            """)

            return captcha_solved

        except Exception as e:
            self.logger.error(f"⚠️ Error during maximum distance attempt: {str(e)}")
            return False
