# selenium/common/search.py
"""
Reusable search utilities for YouTube automation.
Only performs the search (opens homepage, types query, submits).
Result clicking is handled by common.find.
All clicks now use human-like behavior.
"""

import time
import random
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import human_click
from common.humanclick import human_click

logger = logging.getLogger(__name__)


def _natural_typing(element, text, use_fast=False):
    """Type text naturally with random delays."""
    filtered = ''.join(c for c in text if ord(c) <= 0xFFFF)
    delay = 0.02 if use_fast else 0.05
    for ch in filtered:
        element.send_keys(ch)
        time.sleep(random.uniform(delay, delay * 3))


def _wait_for_page_load(driver, timeout=25):
    """Wait for page to load completely."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            if driver.execute_script("return document.readyState;") == "complete":
                return True
        except:
            pass
        time.sleep(0.3)
    return False


def _wait_for_search_box(driver, timeout=20):
    """Wait for search box to be present and ready."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.NAME, "search_query"))
        )
        return True
    except:
        return False


def _handle_cookies(driver, instance_id):
    """Handle cookie consent popups using human_click."""
    cookie_xpaths = [
        "//button[contains(., 'Accept all')]",
        "//button[contains(., 'I agree')]",
        "//button[contains(@aria-label, 'Accept')]",
        "//button[contains(., 'Accept')]",
        "//button[contains(., 'Got it')]"
    ]
    for xpath in cookie_xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for elem in elements:
                if elem.is_displayed() and elem.is_enabled():
                    human_click(driver, elem, instance_id, "cookie accept button")
                    time.sleep(1)
                    return True
        except:
            continue
    return False


def _human_delay(min_sec=0.3, max_sec=1.5):
    """Random human-like delay."""
    time.sleep(random.uniform(min_sec, max_sec))


def _has_search_results(driver):
    """
    Check if search results page has any results.
    Works for both video searches AND channel searches.
    """
    try:
        # Check for video links (for video searches)
        video_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/watch?v=']")
        
        # Check for channel links (for channel searches)
        channel_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/@']")
        
        # Check for any result containers (fallback)
        result_containers = driver.find_elements(By.CSS_SELECTOR, "ytd-item-section-renderer, ytm-section-list-renderer")
        
        # Return True if ANY type of result is found
        return len(video_links) > 0 or len(channel_links) > 0 or len(result_containers) > 0
    except:
        return False


class DesktopSearch:
    @staticmethod
    def perform_search(driver, instance_id, search_query, use_fast_typing=False, video_id=None):
        """
        Open desktop YouTube, type query, press Enter.
        If title search fails, falls back to video ID search.
        """
        try:
            logger.info(f"Instance {instance_id}: Performing desktop search...")
            
            driver.get("https://www.youtube.com")
            
            # Wait for search box to be ready (timeout 20 seconds)
            if not _wait_for_search_box(driver, timeout=20):
                logger.error(f"Instance {instance_id}: Search box not found after 20 seconds")
                return False
            
            _wait_for_page_load(driver, 20)
            _handle_cookies(driver, instance_id)
            _human_delay(1, 2.5)

            search_box = driver.find_element(By.NAME, "search_query")
            human_click(driver, search_box, instance_id, "desktop search box")
            _human_delay(0.3, 0.8)
            search_box.clear()
            
            # Try title search first
            _natural_typing(search_box, search_query, use_fast=use_fast_typing)
            _human_delay(0.5, 1)
            search_box.send_keys(Keys.ENTER)
            
            # Wait for results with timeout
            _wait_for_page_load(driver, 20)
            _human_delay(1.5, 3)
            
            # Check if we got results
            if _has_search_results(driver):
                logger.info(f"Instance {instance_id}: Desktop title search successful")
                return True
                
            # If title search failed and we have video_id, fallback to video ID search
            if video_id:
                logger.info(f"Instance {instance_id}: Title search failed, falling back to video ID: {video_id}")
                
                # Clear and search by video ID
                search_box = driver.find_element(By.NAME, "search_query")
                human_click(driver, search_box, instance_id, "desktop search box (fallback)")
                search_box.clear()
                _natural_typing(search_box, video_id, use_fast=True)
                _human_delay(0.5, 1)
                search_box.send_keys(Keys.ENTER)
                _wait_for_page_load(driver, 20)
                _human_delay(1.5, 3)
                
                if _has_search_results(driver):
                    logger.info(f"Instance {instance_id}: Desktop video ID search successful")
                    return True
                else:
                    logger.warning(f"Instance {instance_id}: Video ID search also returned no results")
                    return False
            else:
                logger.warning(f"Instance {instance_id}: Title search failed and no video_id provided")
                return False
                
        except Exception as e:
            logger.error(f"Instance {instance_id}: Desktop perform_search error - {e}")
            return False


class MobileSearch:
    @staticmethod
    def perform_search(driver, instance_id, search_query, use_fast_typing=False, video_id=None):
        """
        Open mobile YouTube, click search button, type query, submit.
        If title search fails, falls back to video ID search.
        """
        try:
            logger.info(f"Instance {instance_id}: Performing mobile search...")
            
            driver.get("https://m.youtube.com")
            _wait_for_page_load(driver, 20)
            _handle_cookies(driver, instance_id)
            _human_delay(1, 2.5)

            # Click search button using human_click
            search_btn = None
            selectors = [
                ".mobile-topbar-header-content button:first-child",
                "button.ytSearchboxComponentSearchButton",
                "button[aria-label='Search']",
                "//button[@aria-label='Search']",
                ".search-icon",
                "ytm-searchbox button"
            ]
            
            for sel in selectors:
                try:
                    if sel.startswith("//"):
                        search_btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, sel))
                        )
                    else:
                        search_btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                        )
                    if search_btn:
                        break
                except:
                    continue
                    
            if not search_btn:
                logger.error(f"Instance {instance_id}: Could not find mobile search button")
                return False
                
            human_click(driver, search_btn, instance_id, "mobile search button")
            _human_delay(1, 1.5)

            # Find search input box
            search_box = None
            input_selectors = [
                "input[name='search_query']",
                "input.ytSearchboxComponentInput",
                "input[placeholder='Search YouTube']",
                "ytm-searchbox input",
                "input.search-box"
            ]
            
            for sel in input_selectors:
                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    if search_box:
                        break
                except:
                    continue
                    
            if not search_box:
                logger.error(f"Instance {instance_id}: Could not find mobile search box")
                return False

            # Re-fetch search box to avoid stale reference
            try:
                search_box = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='search_query']"))
                )
            except:
                search_box = driver.find_element(By.CSS_SELECTOR, "input[name='search_query']")
            human_click(driver, search_box, instance_id, "mobile search input")
            _human_delay(0.5, 1)
            search_box.clear()
            
            # Try title search first
            _natural_typing(search_box, search_query, use_fast=use_fast_typing)
            _human_delay(0.5, 1)
            search_box.send_keys(Keys.ENTER)
            _wait_for_page_load(driver, 20)
            _human_delay(1.5, 3)
            
            # Check if we got results
            if _has_search_results(driver):
                logger.info(f"Instance {instance_id}: Mobile title search successful")
                return True
                
            # If title search failed and we have video_id, fallback to video ID search
            if video_id:
                logger.info(f"Instance {instance_id}: Title search failed, falling back to video ID: {video_id}")
                
                # Find search box again (page may have changed)
                try:
                    search_box = driver.find_element(By.CSS_SELECTOR, "input[name='search_query']")
                except:
                    try:
                        search_box = driver.find_element(By.CSS_SELECTOR, "input.ytSearchboxComponentInput")
                    except:
                        logger.error(f"Instance {instance_id}: Could not find search box for fallback")
                        return False
                
                human_click(driver, search_box, instance_id, "mobile search input (fallback)")
                search_box.clear()
                _natural_typing(search_box, video_id, use_fast=True)
                _human_delay(0.5, 1)
                search_box.send_keys(Keys.ENTER)
                _wait_for_page_load(driver, 20)
                _human_delay(1.5, 3)
                
                if _has_search_results(driver):
                    logger.info(f"Instance {instance_id}: Mobile video ID search successful")
                    return True
                else:
                    logger.warning(f"Instance {instance_id}: Mobile video ID search also returned no results")
                    return False
            else:
                logger.warning(f"Instance {instance_id}: Title search failed and no video_id provided")
                return False
                
        except Exception as e:
            logger.error(f"Instance {instance_id}: Mobile perform_search error - {e}")
            return False