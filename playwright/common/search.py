# playwright/common/search.py
"""
Playwright search utilities - only custom logic, uses Playwright's built-in methods.
"""

import time
import random
import logging
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


def _natural_typing(element, text: str, use_fast: bool = False):
    """Type text naturally with random delays"""
    filtered = ''.join(c for c in text if ord(c) <= 0xFFFF)
    delay = 0.02 if use_fast else 0.05
    for ch in filtered:
        element.type(ch, delay=random.uniform(delay, delay * 3))


def _has_search_results(page: Page) -> bool:
    """Check if search results page has any results"""
    try:
        video_links = page.locator("a[href*='/watch?v=']").count()
        channel_links = page.locator("a[href*='/@']").count()
        return video_links > 0 or channel_links > 0
    except:
        return False


class DesktopSearch:
    @staticmethod
    def perform_search(page: Page, instance_id: int, search_query: str, use_fast_typing: bool = False, video_id: str = None) -> bool:
        """Open desktop YouTube, type query, press Enter"""
        try:
            logger.info(f"Instance {instance_id}: Performing desktop search...")
            
            page.goto("https://www.youtube.com")
            page.wait_for_selector("input[name='search_query']", timeout=20000)
            
            # Wait for page stability
            time.sleep(2)
            
            # Handle cookies if present
            try:
                accept_btn = page.locator("button:has-text('Accept all')")
                if accept_btn.count() > 0 and accept_btn.first.is_visible():
                    accept_btn.first.click()
                    time.sleep(1)
            except:
                pass
            
            time.sleep(random.uniform(1, 2.5))
            
            search_box = page.locator("input[name='search_query']").first
            search_box.click()
            time.sleep(random.uniform(0.3, 0.8))
            search_box.fill("")
            
            # Type search query
            _natural_typing(search_box, search_query, use_fast=use_fast_typing)
            time.sleep(random.uniform(0.5, 1))
            search_box.press("Enter")
            
            # Wait for results
            time.sleep(3)
            
            if _has_search_results(page):
                logger.info(f"Instance {instance_id}: Desktop search successful")
                return True
            
            # Fallback to video ID search
            if video_id:
                logger.info(f"Instance {instance_id}: Falling back to video ID: {video_id}")
                search_box = page.locator("input[name='search_query']").first
                search_box.click()
                search_box.fill("")
                _natural_typing(search_box, video_id, use_fast=True)
                time.sleep(random.uniform(0.5, 1))
                search_box.press("Enter")
                time.sleep(3)
                
                if _has_search_results(page):
                    logger.info(f"Instance {instance_id}: Video ID search successful")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Instance {instance_id}: Desktop search error - {e}")
            return False


class MobileSearch:
    @staticmethod
    def perform_search(page: Page, instance_id: int, search_query: str, use_fast_typing: bool = False, video_id: str = None) -> bool:
        """Open mobile YouTube, click search button, type query, submit"""
        try:
            logger.info(f"Instance {instance_id}: Performing mobile search...")
            
            page.goto("https://m.youtube.com")
            time.sleep(2)
            
            # Handle cookies if present
            try:
                accept_btn = page.locator("button:has-text('Accept all')")
                if accept_btn.count() > 0 and accept_btn.first.is_visible():
                    accept_btn.first.click()
                    time.sleep(1)
            except:
                pass
            
            time.sleep(random.uniform(1, 2.5))
            
            # Click search button
            search_btn = page.locator("button[aria-label='Search']")
            if search_btn.count() == 0:
                search_btn = page.locator(".search-icon")
            if search_btn.count() == 0:
                search_btn = page.locator("ytm-searchbox button")
            
            if search_btn.count() > 0:
                search_btn.first.click()
            else:
                logger.error(f"Instance {instance_id}: Could not find search button")
                return False
            
            time.sleep(random.uniform(1, 1.5))
            
            # Find search input
            search_box = page.locator("input[name='search_query']")
            if search_box.count() == 0:
                search_box = page.locator("input[placeholder='Search YouTube']")
            if search_box.count() == 0:
                search_box = page.locator("ytm-searchbox input")
            
            if search_box.count() == 0:
                logger.error(f"Instance {instance_id}: Could not find search input")
                return False
            
            search_box.first.click()
            time.sleep(random.uniform(0.5, 1))
            search_box.first.fill("")
            
            # Type search query
            _natural_typing(search_box.first, search_query, use_fast=use_fast_typing)
            time.sleep(random.uniform(0.5, 1))
            search_box.first.press("Enter")
            
            # Wait for results
            time.sleep(3)
            
            if _has_search_results(page):
                logger.info(f"Instance {instance_id}: Mobile search successful")
                return True
            
            # Fallback to video ID search
            if video_id:
                logger.info(f"Instance {instance_id}: Falling back to video ID: {video_id}")
                search_box = page.locator("input[name='search_query']")
                if search_box.count() == 0:
                    search_box = page.locator("input[placeholder='Search YouTube']")
                
                if search_box.count() > 0:
                    search_box.first.click()
                    search_box.first.fill("")
                    _natural_typing(search_box.first, video_id, use_fast=True)
                    time.sleep(random.uniform(0.5, 1))
                    search_box.first.press("Enter")
                    time.sleep(3)
                    
                    if _has_search_results(page):
                        logger.info(f"Instance {instance_id}: Mobile video ID search successful")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Instance {instance_id}: Mobile search error - {e}")
            return False