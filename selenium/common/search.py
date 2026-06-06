# common/search.py
"""
Reusable search utilities for YouTube automation.
Only performs the search (opens homepage, types query, submits).
Result clicking is handled by common.find.
"""

import time
import random
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

def _natural_typing(element, text, use_fast=False):
    filtered = ''.join(c for c in text if ord(c) <= 0xFFFF)
    delay = 0.02 if use_fast else 0.05
    for ch in filtered:
        element.send_keys(ch)
        time.sleep(random.uniform(delay, delay * 3))

def _wait_for_page_load(driver, timeout=25):
    start = time.time()
    while time.time() - start < timeout:
        try:
            if driver.execute_script("return document.readyState;") == "complete":
                return True
        except:
            pass
        time.sleep(0.3)
    return False

def _handle_cookies(driver, instance_id):
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
                    driver.execute_script("arguments[0].click();", elem)
                    time.sleep(1)
                    return True
        except:
            continue
    return False

def _human_delay(min_sec=0.3, max_sec=1.5):
    time.sleep(random.uniform(min_sec, max_sec))

class DesktopSearch:
    @staticmethod
    def perform_search(driver, instance_id, search_query, use_fast_typing=False):
        """Open desktop YouTube, type query, press Enter. Returns True if successful."""
        try:
            driver.get("https://www.youtube.com")
            _wait_for_page_load(driver, 20)
            _handle_cookies(driver, instance_id)
            _human_delay(1, 2.5)

            search_box = driver.find_element(By.NAME, "search_query")
            search_box.click()
            _human_delay(0.3, 0.8)
            search_box.clear()
            _natural_typing(search_box, search_query, use_fast=use_fast_typing)
            _human_delay(0.5, 1)
            search_box.send_keys(Keys.ENTER)
            _wait_for_page_load(driver, 20)
            _human_delay(1.5, 3)
            return True
        except Exception as e:
            logger.error(f"Instance {instance_id}: Desktop perform_search error - {e}")
            return False

class MobileSearch:
    @staticmethod
    def perform_search(driver, instance_id, search_query, use_fast_typing=False):
        """Open mobile YouTube, click search button, type query, submit. Returns True if successful."""
        try:
            driver.get("https://m.youtube.com")
            _wait_for_page_load(driver, 20)
            _handle_cookies(driver, instance_id)
            _human_delay(1, 2.5)

            # Click search button
            search_btn = None
            selectors = [
                ".mobile-topbar-header-content button:first-child",
                "button.ytSearchboxComponentSearchButton",
                "button[aria-label='Search']",
                "//button[@aria-label='Search']"
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
            driver.execute_script("arguments[0].click();", search_btn)
            _human_delay(1, 1.5)

            # Find search input box
            search_box = None
            input_selectors = [
                "input[name='search_query']",
                "input.ytSearchboxComponentInput",
                "input[placeholder='Search YouTube']"
            ]
            for sel in input_selectors:
                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    if search_box:
                        break
                except:
                    continue
            if not search_box:
                logger.error(f"Instance {instance_id}: Could not find mobile search box")
                return False

            search_box.click()
            _human_delay(0.5, 1)
            search_box.clear()
            _natural_typing(search_box, search_query, use_fast=use_fast_typing)
            _human_delay(0.5, 1)
            search_box.send_keys(Keys.ENTER)
            _wait_for_page_load(driver, 20)
            _human_delay(1.5, 3)
            return True
        except Exception as e:
            logger.error(f"Instance {instance_id}: Mobile perform_search error - {e}")
            return False