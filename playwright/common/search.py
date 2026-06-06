# playwright/common/search.py
"""
Playwright search utilities for YouTube Automation.
Performs search on desktop or mobile YouTube.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DesktopSearch:
    """Search on www.youtube.com (desktop layout)."""

    @staticmethod
    def perform_search(page, search_query: str, use_fast_typing: bool = False) -> bool:
        """
        Open desktop YouTube, type query, press Enter.
        
        Args:
            page: Playwright page object
            search_query: Text to search for
            use_fast_typing: Type faster (for retries)
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Desktop search for: {search_query[:40]}...")
            
            page.goto("https://www.youtube.com", wait_until='domcontentloaded')
            time.sleep(1.5)
            
            # Handle cookies if present
            try:
                accept_btn = page.query_selector('button:has-text("Accept all"), button:has-text("Accept"), button:has-text("I agree"), button:has-text("Got it")')
                if accept_btn and accept_btn.is_visible():
                    accept_btn.click()
                    time.sleep(0.5)
            except:
                pass
            
            # Find search box - multiple selectors for robustness
            search_box = None
            selectors = [
                'input[name="search_query"]',
                'input#search',
                'ytd-searchbox input',
                'input[aria-label="Search"]'
            ]
            
            for selector in selectors:
                try:
                    search_box = page.query_selector(selector)
                    if search_box and search_box.is_visible():
                        logger.info(f"Desktop search box found with selector: {selector}")
                        break
                except:
                    continue
            
            if not search_box:
                logger.error("Desktop search box not found")
                return False
            
            search_box.click()
            time.sleep(0.3)
            search_box.fill("")
            
            # Type with natural delay
            delay = 0.02 if use_fast_typing else 0.05
            for char in search_query:
                search_box.type(char, delay=delay)
                time.sleep(0.01)
            
            time.sleep(0.5)
            search_box.press("Enter")
            
            # Wait for results to load
            page.wait_for_load_state('networkidle', timeout=15000)
            time.sleep(1.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Desktop search error: {e}")
            return False


class MobileSearch:
    """Search on m.youtube.com (mobile layout)."""

    @staticmethod
    def perform_search(page, search_query: str, use_fast_typing: bool = False) -> bool:
        """
        Open mobile YouTube, click search button, type query, submit.
        
        Args:
            page: Playwright page object
            search_query: Text to search for
            use_fast_typing: Type faster (for retries)
        
        Returns:
            True if successful
        """
        try:
            logger.info(f"Mobile search for: {search_query[:40]}...")
            
            page.goto("https://m.youtube.com", wait_until='domcontentloaded')
            time.sleep(1.5)
            
            # Handle cookies if present
            try:
                accept_btn = page.query_selector('button:has-text("Accept all"), button:has-text("Accept"), button:has-text("I agree")')
                if accept_btn and accept_btn.is_visible():
                    accept_btn.click()
                    time.sleep(0.5)
            except:
                pass
            
            # Click search button - multiple selectors
            search_btn = None
            btn_selectors = [
                'button[aria-label="Search"]',
                '.ytSearchboxComponentSearchButton',
                'yt-icon-button#search-icon',
                '.mobile-topbar-header-content button:first-child'
            ]
            
            for selector in btn_selectors:
                try:
                    search_btn = page.query_selector(selector)
                    if search_btn and search_btn.is_visible():
                        logger.info(f"Mobile search button found with selector: {selector}")
                        break
                except:
                    continue
            
            if not search_btn:
                # Try to find any button with search in aria-label
                try:
                    search_btn = page.query_selector('button[aria-label*="Search"]')
                except:
                    pass
            
            if not search_btn:
                logger.error("Mobile search button not found")
                return False
            
            search_btn.click()
            time.sleep(1.5)
            
            # Find search input - multiple selectors
            search_box = None
            input_selectors = [
                'input[name="search_query"]',
                'input.ytSearchboxComponentInput',
                'input[placeholder="Search YouTube"]',
                'input[placeholder="Search"]'
            ]
            
            for selector in input_selectors:
                try:
                    search_box = page.query_selector(selector)
                    if search_box and search_box.is_visible():
                        logger.info(f"Mobile search input found with selector: {selector}")
                        break
                except:
                    continue
            
            if not search_box:
                logger.error("Mobile search input not found")
                return False
            
            search_box.click()
            time.sleep(0.3)
            search_box.fill("")
            
            # Type with natural delay
            delay = 0.02 if use_fast_typing else 0.05
            for char in search_query:
                search_box.type(char, delay=delay)
                time.sleep(0.01)
            
            time.sleep(0.5)
            search_box.press("Enter")
            
            # Wait for results
            page.wait_for_load_state('networkidle', timeout=15000)
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Mobile search error: {e}")
            return False