# selenium/common/find.py
"""
Functions to find and click specific result types on YouTube search results page,
and to perform channel internal search.
All clicking now uses human-like behavior from humanclick module.
"""
import time
import random
import logging
import sys
from pathlib import Path

# Add parent paths to handle imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
COMMON_ROOT = PROJECT_ROOT / "common"

if str(COMMON_ROOT) not in sys.path:
    sys.path.insert(0, str(COMMON_ROOT))

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import the shared human click utility
try:
    from common.humanclick import human_click
except ImportError:
    # Fallback: try direct import
    from humanclick import human_click

# Import wait_for_page_load from utils (with fallback)
try:
    from common.utils import wait_for_page_load
except ImportError:
    # Fallback: simple version
    def wait_for_page_load(driver, timeout=25):
        start = time.time()
        while time.time() - start < timeout:
            try:
                if driver.execute_script("return document.readyState;") == "complete":
                    return True
            except:
                pass
            time.sleep(0.3)
        return False

logger = logging.getLogger(__name__)

# ---------- Helper for natural typing ----------
def _natural_typing(element, text, use_fast=False):
    filtered = ''.join(c for c in text if ord(c) <= 0xFFFF)
    delay = 0.02 if use_fast else 0.05
    for ch in filtered:
        element.send_keys(ch)
        time.sleep(random.uniform(delay, delay * 3))

# ---------- Find and click video result (general search) ----------

def find_and_click_video_result(driver, instance_id, video_id, is_mobile=False, po_token=None):
    """
    On the search results page, find the video link containing the given video ID and click it.
    If po_token is provided, injects it into the href BEFORE clicking.
    Uses human-like click with navigation verification.
    """
    try:
        if is_mobile:
            selectors = [
                f"//a[contains(@href, '{video_id}')]",
                "ytm-compact-video-renderer a",
                "a[href*='watch?v=']"
            ]
        else:
            selectors = [
                f"//a[contains(@href, '{video_id}')]",
                "ytd-video-renderer a#thumbnail"
            ]
        
        video_link = None
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    elements = driver.find_elements(By.XPATH, sel)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    href = el.get_attribute('href')
                    if href and video_id in href:
                        video_link = el
                        break
                if video_link:
                    break
            except:
                continue
        
        if not video_link:
            logger.warning(f"Instance {instance_id}: Video result not found for ID {video_id}")
            return False
        
        # Inject PO token into href BEFORE clicking (if provided)
        if po_token:
            original_href = video_link.get_attribute('href')
            if original_href and 'pot=' not in original_href:
                separator = '&' if '?' in original_href else '?'
                new_href = f"{original_href}{separator}pot={po_token}"
                driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", video_link)
                logger.info(f"Instance {instance_id}: Injected PO token into video link href before click")
                logger.info(f"Instance {instance_id}: Final href after injection: {new_href[:150]}")
                # Re-scroll after injection to ensure element is interactable
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", video_link)
                time.sleep(0.5)
            else:
                logger.info(f"Instance {instance_id}: PO token already present or href missing")
        else:
            logger.warning(f"Instance {instance_id}: No PO token available for injection")
        
        # Human-like click with navigation verification
        return human_click(driver, video_link, instance_id, element_type=f"video result (ID: {video_id[:8]})")
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error in find_and_click_video_result - {e}")
        return False
        
        
# ---------- Find and click channel result ----------
def find_and_click_channel_result(driver, instance_id, channel_name, is_mobile=False):
    """
    On the search results page, find the channel link and click it.
    Uses human-like click with navigation verification.
    """
    try:
        time.sleep(2)  # Increased wait time for results to load
        
        # Clean channel name (remove @ if present)
        clean_name = channel_name.lstrip('@')
        logger.info(f"Instance {instance_id}: Looking for channel: {clean_name}")
        
        channel_link = None
        
        if is_mobile:
            # Wait for the channel renderer to be present
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "ytm-compact-channel-renderer"))
                )
                logger.info(f"Instance {instance_id}: Channel renderer found")
            except Exception as e:
                logger.warning(f"Instance {instance_id}: Channel renderer not found: {e}")
            
            # Try multiple selectors
            selectors = [
                f"a[href*='/@{clean_name}']",
                f"a[href*='/{clean_name}']",
                "ytm-compact-channel-renderer a",
                f"//ytm-compact-channel-renderer//a[contains(@href, '/@{clean_name}')]",
                "//a[contains(@href, '/channel/')]",
                f"//span[contains(text(), '@{clean_name}')]/ancestor::a",
                f"//yt-formatted-string[contains(text(), '{clean_name}')]/ancestor::a"
            ]
            
            for sel in selectors:
                try:
                    if sel.startswith("//"):
                        elements = driver.find_elements(By.XPATH, sel)
                        if elements:
                            channel_link = elements[0]
                            logger.info(f"Instance {instance_id}: Found via XPath: {sel[:50]}")
                            break
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, sel)
                        for elem in elements:
                            if elem.is_displayed():
                                channel_link = elem
                                logger.info(f"Instance {instance_id}: Found via CSS: {sel[:50]}")
                                break
                        if channel_link:
                            break
                except Exception as e:
                    logger.debug(f"Selector error: {e}")
                    continue
        else:
            # Desktop selectors
            selectors = [
                f"a[href*='/@{clean_name}']",
                f"a[href*='/{clean_name}']",
                "ytd-channel-renderer a#main-link",
                f"//a[contains(@href, '/@{clean_name}')]",
                "//a[contains(@href, '/@')]",
                f"//ytd-channel-name//yt-formatted-string[contains(text(), '{clean_name}')]/ancestor::a",
                f"//div[@id='text-container']//a[contains(@href, '/@{clean_name}')]",
                "ytd-channel-renderer ytd-channel-name a"
            ]
            
            for sel in selectors:
                try:
                    if sel.startswith("//"):
                        elements = driver.find_elements(By.XPATH, sel)
                        if elements:
                            channel_link = elements[0]
                            logger.info(f"Instance {instance_id}: Found via XPath: {sel[:50]}")
                            break
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, sel)
                        for elem in elements:
                            if elem.is_displayed():
                                channel_link = elem
                                logger.info(f"Instance {instance_id}: Found via CSS: {sel[:50]}")
                                break
                        if channel_link:
                            break
                except Exception as e:
                    logger.debug(f"Selector error: {e}")
                    continue
        
        if not channel_link:
            # Debug: print all channel-like links on page
            try:
                all_links = driver.find_elements(By.TAG_NAME, "a")
                channel_links = []
                for link in all_links:
                    href = link.get_attribute('href')
                    if href and ('/@' in href or '/channel/' in href):
                        channel_links.append(href)
                logger.info(f"Instance {instance_id}: Found channel links on page: {channel_links[:5]}")
            except:
                pass
            logger.error(f"Instance {instance_id}: Channel result not found for {clean_name}")
            return False
        
        # Human-like click with navigation verification
        old_url = driver.current_url
        success = human_click(driver, channel_link, instance_id, f"channel result ({clean_name})")
        
        if success:
            logger.info(f"Instance {instance_id}: Successfully clicked channel result")
        else:
            logger.warning(f"Instance {instance_id}: Click may not have navigated")
        
        return success
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error in find_and_click_channel_result - {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
        
        
# ---------- Channel internal search (search within a channel page) ----------
def channel_internal_search(driver, instance_id, video_id, is_mobile=False, po_token=None, video_title=None):
    """
    On the channel page, first try to find video directly on the page.
    If not found, perform a search:
        TIER 1: Search by video title (if available)
        TIER 2: Search by video ID
    """
    try:
        logger.info(f"Instance {instance_id}: channel_internal_search called, po_token present: {po_token is not None}")
        
        # ========== FIRST: Try to find video directly on current page ==========
        logger.info(f"Instance {instance_id}: Checking if video is already visible on channel page...")
        
        video_link = None
        
        # Try to find video link on current page
        link_selectors = [
            f"a[href*='{video_id}']",
            f"a[href*='/watch?v={video_id}']",
            "ytd-video-renderer a#thumbnail",
            "ytm-compact-video-renderer a",
            "a[href*='/watch?v=']"
        ]
        
        for selector in link_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    href = elem.get_attribute('href')
                    if href and video_id in href:
                        video_link = elem
                        logger.info(f"Instance {instance_id}: Found video directly on page via: {selector}")
                        break
                if video_link:
                    break
            except:
                continue
        
        if video_link:
            # ========== INJECT PO TOKEN AND CLICK ==========
            if po_token:
                logger.info(f"Instance {instance_id}: *** DIRECT INJECTION - po_token exists ***")
                original_href = video_link.get_attribute('href')
                logger.info(f"Instance {instance_id}: PO token present, href before: {original_href[:100] if original_href else 'None'}")
                
                if original_href and 'pot=' not in original_href:
                    separator = '&' if '?' in original_href else '?'
                    new_href = f"{original_href}{separator}pot={po_token}"
                    driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", video_link)
                    logger.info(f"Instance {instance_id}: Injected PO token into directly visible video link")
                    logger.info(f"Instance {instance_id}: Final href after injection: {new_href[:150]}")
                    # Re-scroll after injection to ensure element is interactable
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", video_link)
                    time.sleep(0.5)
                else:
                    logger.info(f"Instance {instance_id}: PO token already present or href missing")
            else:
                logger.warning(f"Instance {instance_id}: No PO token available for injection")
            
            # Just before clicking, log the final href
            final_href = video_link.get_attribute('href')
            logger.info(f"Instance {instance_id}: FINAL HREF BEFORE CLICK: {final_href[:200]}")
            if 'pot=' in final_href:
                logger.info(f"Instance {instance_id}: *** TOKEN IN HREF BEFORE CLICK ***")
            else:
                logger.warning(f"Instance {instance_id}: *** NO TOKEN IN HREF BEFORE CLICK ***")
                
            # Click the video
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", video_link)
            time.sleep(1)
            return human_click(driver, video_link, instance_id, f"direct channel video result (ID: {video_id[:8]})")
        
        # ========== SECOND: Video not found, perform search ==========
        logger.info(f"Instance {instance_id}: Video not directly visible, performing channel search...")
        
        # ========== TIER 1: Search by video title (if available) ==========
        search_success = False
        
        if video_title:
            logger.info(f"Instance {instance_id}: TIER 1 - Searching by video title: {video_title[:50]}...")
            search_success = _perform_channel_search(driver, instance_id, video_title, is_mobile, po_token, video_id)
            if search_success:
                logger.info(f"Instance {instance_id}: TIER 1 succeeded - found video by title search")
        
        # ========== TIER 2: Search by video ID (fallback) ==========
        if not search_success:
            logger.info(f"Instance {instance_id}: TIER 2 - Searching by video ID: {video_id}")
            search_success = _perform_channel_search(driver, instance_id, video_id, is_mobile, po_token, video_id)
            if search_success:
                logger.info(f"Instance {instance_id}: TIER 2 succeeded - found video by ID search")
        
        if search_success:
            return True
        else:
            logger.error(f"Instance {instance_id}: Channel search failed with both title and ID")
            return False
            
    except Exception as e:
        logger.error(f"Instance {instance_id}: Channel internal search error - {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def _perform_channel_search(driver, instance_id, search_term, is_mobile, po_token, target_video_id):
    """
    Perform a search within the channel using the given search term.
    ALWAYS looks for the exact video ID in the href to click.
    Returns True if video with target_video_id is found and clicked.
    """
    try:
        if is_mobile:
            # ==================== MOBILE CHANNEL SEARCH ====================
            # Step 1: Click the Search tab
            search_tab = None
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "yt-tab-shape"))
                )
            except:
                pass
            
            tab_selectors = [
                "yt-tab-shape[tab-title='Search']",
                "//div[@role='tab' and text()='Search']"
            ]
            
            for sel in tab_selectors:
                try:
                    if sel.startswith("//"):
                        search_tab = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, sel))
                        )
                    else:
                        search_tab = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                        )
                    if search_tab:
                        logger.info(f"Instance {instance_id}: Found Search tab")
                        break
                except:
                    continue
            
            if not search_tab:
                logger.error(f"Instance {instance_id}: Could not find Search tab")
                return False
            
            # Click Search tab with human_click
            human_click(driver, search_tab, instance_id, "Search tab")
            logger.info(f"Instance {instance_id}: Clicked Search tab")
            time.sleep(2)
            
            # Step 2: Find the search input box (re-fetch after page change)
            search_box = None
            input_selectors = [
                "input.YtmChannelSearchBoxRendererInput",
                "input[placeholder='Search channel']",
                "input[name='query']",
                "input[placeholder='Search']"
            ]
            
            for sel in input_selectors:
                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    if search_box and search_box.is_displayed():
                        logger.info(f"Instance {instance_id}: Found search input with: {sel}")
                        break
                except:
                    continue
            
            if not search_box:
                try:
                    search_form = driver.find_element(By.CSS_SELECTOR, "form.YtmChannelSearchBoxRendererForm")
                    search_box = search_form.find_element(By.TAG_NAME, "input")
                    logger.info(f"Instance {instance_id}: Found search input via form")
                except:
                    pass
            
            if not search_box:
                logger.error(f"Instance {instance_id}: Could not find search input")
                return False
            
            # Re-fetch to ensure fresh reference
            try:
                search_box = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='query']"))
                )
            except:
                pass
            
            # Step 3: Type search term and submit
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", search_box)
            time.sleep(random.uniform(0.2, 0.5))
            human_click(driver, search_box, instance_id, "search input box")
            search_box.clear()
            _natural_typing(search_box, search_term, use_fast=False)
            time.sleep(random.uniform(0.3, 0.6))
            search_box.send_keys(Keys.ENTER)
            logger.info(f"Instance {instance_id}: Search submitted for: {search_term[:50]}...")
            
            # Step 4: Wait for video results
            time.sleep(4)
            time.sleep(2)  # Additional wait for results to load
            
            # Step 5: Find video by exact ID (ALWAYS use video_id)
            video_link = None
            all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/watch?v=']")
            
            for link in all_links:
                href = link.get_attribute('href')
                if href and target_video_id and f'/watch?v={target_video_id}' in href:
                    video_link = link
                    logger.info(f"Instance {instance_id}: Found exact video ID match: {target_video_id}")
                    break
            
            if not video_link:
                logger.warning(f"Instance {instance_id}: No video found with ID {target_video_id} in search results")
                return False
            
            # ========== PO TOKEN INJECTION FOR SEARCH RESULT ==========
            if po_token:
                logger.info(f"Instance {instance_id}: *** SEARCH RESULT INJECTION - po_token exists ***")
                original_href = video_link.get_attribute('href')
                logger.info(f"Instance {instance_id}: Original href: {original_href[:100] if original_href else 'None'}")
                if original_href and 'pot=' not in original_href:
                    separator = '&' if '?' in original_href else '?'
                    new_href = f"{original_href}{separator}pot={po_token}"
                    driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", video_link)
                    logger.info(f"Instance {instance_id}: Injected PO token into search result video link")
                    logger.info(f"Instance {instance_id}: New href: {new_href[:150]}")
                    # Re-scroll after injection to ensure element is interactable
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", video_link)
                    time.sleep(0.5)
                else:
                    logger.info(f"Instance {instance_id}: PO token already present or href missing")
            else:
                logger.warning(f"Instance {instance_id}: No PO token available for search result injection")
            
            #Just before clicking, log the final href
            final_href = video_link.get_attribute('href')
            logger.info(f"Instance {instance_id}: FINAL HREF BEFORE CLICK: {final_href[:200]}")
            if 'pot=' in final_href:
                logger.info(f"Instance {instance_id}: *** TOKEN IN HREF BEFORE CLICK ***")
            else:
                logger.warning(f"Instance {instance_id}: *** NO TOKEN IN HREF BEFORE CLICK ***")
                
            # Just before clicking, log the final href
            final_href = video_link.get_attribute('href')
            logger.info(f"Instance {instance_id}: FINAL HREF BEFORE CLICK: {final_href[:200]}")
            if 'pot=' in final_href:
                logger.info(f"Instance {instance_id}: *** TOKEN IN HREF BEFORE CLICK ***")
            else:
                logger.warning(f"Instance {instance_id}: *** NO TOKEN IN HREF BEFORE CLICK ***")
            
            # Human-like click with navigation verification
            return human_click(driver, video_link, instance_id, f"search result video (ID: {target_video_id})")
            
        else:
            # ==================== DESKTOP CHANNEL SEARCH ====================
            # Step 1: Click the search button in channel header
            search_btn = None
            btn_selectors = [
                "ytd-expandable-tab-renderer yt-icon-button#icon-button",
                "button[aria-label='Search']",
                "//button[@aria-label='Search']"
            ]
            
            for sel in btn_selectors:
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
                        logger.info(f"Instance {instance_id}: Found search button with {sel}")
                        break
                except:
                    continue
            
            if not search_btn:
                logger.error(f"Instance {instance_id}: Could not find search button on desktop")
                return False
            
            human_click(driver, search_btn, instance_id, "channel search button")
            logger.info(f"Instance {instance_id}: Clicked channel search button")
            time.sleep(2)
            
            # Step 2: Find search input box (re-fetch after page change)
            search_box = None
            input_selectors = [
                "input[name='query']",
                "tp-yt-paper-input input",
                "input[placeholder='Search']",
                "ytd-searchbox input"
            ]
            
            for sel in input_selectors:
                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    if search_box and search_box.is_displayed():
                        logger.info(f"Instance {instance_id}: Found search input with {sel}")
                        break
                except:
                    continue
            
            if not search_box:
                logger.error(f"Instance {instance_id}: Could not find search input on desktop")
                return False
            
            # Re-fetch to ensure fresh reference
            try:
                search_box = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='query']"))
                )
            except:
                pass
            
            # Step 3: Type search term and submit
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", search_box)
            time.sleep(random.uniform(0.2, 0.5))
            human_click(driver, search_box, instance_id, "search input box")
            search_box.clear()
            _natural_typing(search_box, search_term, use_fast=False)
            time.sleep(random.uniform(0.3, 0.6))
            search_box.send_keys(Keys.ENTER)
            logger.info(f"Instance {instance_id}: Search submitted for: {search_term[:50]}...")
            
            # Step 4: Wait for results
            time.sleep(4)
            time.sleep(2)  # Additional wait for results to load
            
            # Step 5: Find video by exact ID (ALWAYS use video_id)
            video_link = None
            all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/watch?v=']")
            
            for link in all_links:
                href = link.get_attribute('href')
                if href and target_video_id and f'/watch?v={target_video_id}' in href:
                    video_link = link
                    logger.info(f"Instance {instance_id}: Found exact video ID match: {target_video_id}")
                    break
            
            if not video_link:
                logger.error(f"Instance {instance_id}: No video found with ID {target_video_id} in search results")
                return False
            
            # ========== PO TOKEN INJECTION FOR SEARCH RESULT ==========
            if po_token:
                original_href = video_link.get_attribute('href')
                if original_href and 'pot=' not in original_href:
                    separator = '&' if '?' in original_href else '?'
                    new_href = f"{original_href}{separator}pot={po_token}"
                    driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", video_link)
                    logger.info(f"Instance {instance_id}: Injected PO token into search result video link")
                    # Re-scroll after injection to ensure element is interactable
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", video_link)
                    time.sleep(0.5)
            
            
            # Just before clicking, log the final href
            final_href = video_link.get_attribute('href')
            logger.info(f"Instance {instance_id}: FINAL HREF BEFORE CLICK: {final_href[:200]}")
            if 'pot=' in final_href:
                logger.info(f"Instance {instance_id}: *** TOKEN IN HREF BEFORE CLICK ***")
            else:
                logger.warning(f"Instance {instance_id}: *** NO TOKEN IN HREF BEFORE CLICK ***")
            
            # Human-like click with navigation verification
            return human_click(driver, video_link, instance_id, f"desktop search result video (ID: {target_video_id})")
            
    except Exception as e:
        logger.error(f"Instance {instance_id}: Channel search error for term '{search_term[:50]}': {e}")
        return False