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
            if 'pot=' not in original_href:
                separator = '&' if '?' in original_href else '?'
                new_href = f"{original_href}{separator}pot={po_token}"
                driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", video_link)
                logger.info(f"Instance {instance_id}: Injected PO token into video link href before click")
        
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
        time.sleep(0.5)
        channel_link = None
        
        if is_mobile:
            # Wait for the channel renderer to be present
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "ytm-compact-channel-renderer"))
                )
                logger.info(f"Instance {instance_id}: Channel renderer found")
            except Exception as e:
                logger.warning(f"Instance {instance_id}: Channel renderer not found: {e}")
            
            # Try multiple selectors
            selectors = [
                f"a[href='/@{channel_name}']",
                "ytm-compact-channel-renderer a",
                f"//ytm-compact-channel-renderer//a[contains(@href, '/@{channel_name}')]",
                "//a[contains(@href, '/channel/')]"
            ]
            
            for sel in selectors:
                try:
                    if sel.startswith("//"):
                        elements = driver.find_elements(By.XPATH, sel)
                        if elements:
                            channel_link = elements[0]
                            logger.info(f"Instance {instance_id}: Found via XPath")
                            break
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, sel)
                        if elements:
                            channel_link = elements[0]
                            logger.info(f"Instance {instance_id}: Found via CSS: {sel}")
                            break
                except:
                    continue
            
            if not channel_link:
                try:
                    handle_xpath = f"//span[contains(text(), '@{channel_name}')]/ancestor::a"
                    channel_link = driver.find_element(By.XPATH, handle_xpath)
                    logger.info(f"Instance {instance_id}: Found via handle text")
                except:
                    pass
        else:
            # Desktop selectors
            selectors = [
                f"a[href='/@{channel_name}']",
                f"//a[contains(@href, '/@{channel_name}')]",
                "ytd-channel-renderer a#main-link",
                f"//ytd-channel-name//yt-formatted-string[contains(text(), '{channel_name}')]/ancestor::a"
            ]
            
            for sel in selectors:
                try:
                    if sel.startswith("//"):
                        elements = driver.find_elements(By.XPATH, sel)
                        if elements:
                            channel_link = elements[0]
                            logger.info(f"Instance {instance_id}: Found via XPath")
                            break
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, sel)
                        if elements:
                            channel_link = elements[0]
                            logger.info(f"Instance {instance_id}: Found via CSS: {sel}")
                            break
                except:
                    continue
        
        if not channel_link:
            logger.error(f"Instance {instance_id}: Channel result not found for {channel_name}")
            return False
        
        # Human-like click with navigation verification
        return human_click(driver, channel_link, instance_id, element_type=f"channel result ({channel_name})")
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error in find_and_click_channel_result - {e}")
        return False

# ---------- Channel internal search (search within a channel page) ----------
def channel_internal_search(driver, instance_id, video_id, is_mobile=False):
    """
    On the channel page, use the "Search" tab (mobile) or search button (desktop),
    then type video ID and click the result.
    Uses human-like click with navigation verification.
    """
    try:
        if is_mobile:
            # ==================== MOBILE CHANNEL SEARCH ====================
            # Step 1: Click the Search tab
            search_tab = None
            try:
                WebDriverWait(driver, 5).until(
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
                        search_tab = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, sel))
                        )
                    else:
                        search_tab = WebDriverWait(driver, 5).until(
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
            
            driver.execute_script("arguments[0].click();", search_tab)
            logger.info(f"Instance {instance_id}: Clicked Search tab")
            time.sleep(1)
            
            # Step 2: Find the search input box
            search_box = None
            input_selectors = [
                "input.YtmChannelSearchBoxRendererInput",
                "input[placeholder='Search channel']",
                "input[name='query']",
                "input[placeholder='Search']"
            ]
            
            for sel in input_selectors:
                try:
                    search_box = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    if search_box:
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
            
            # Step 3: Type video ID and submit
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", search_box)
            time.sleep(random.uniform(0.2, 0.5))
            search_box.click()
            search_box.clear()
            _natural_typing(search_box, video_id, use_fast=False)
            time.sleep(random.uniform(0.3, 0.6))
            search_box.send_keys(Keys.ENTER)
            logger.info(f"Instance {instance_id}: Search submitted")
            
            # Step 4: Wait for and click video result
            time.sleep(2)
            
            video_link = None
            link_selectors = [
                f"a[href*='{video_id}']",
                "ytd-video-renderer a#thumbnail",
                "ytm-compact-video-renderer a"
            ]
            
            for sel in link_selectors:
                try:
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
                logger.warning(f"Instance {instance_id}: Video not found in search results")
                return False
            
            # Human-like click with navigation verification
            return human_click(driver, video_link, instance_id, element_type=f"channel video result (ID: {video_id[:8]})")
            
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
                        search_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, sel))
                        )
                    else:
                        search_btn = WebDriverWait(driver, 5).until(
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
            
            driver.execute_script("arguments[0].click();", search_btn)
            logger.info(f"Instance {instance_id}: Clicked channel search button")
            time.sleep(1)
            
            # Step 2: Find search input box
            search_box = None
            input_selectors = [
                "input[name='query']",
                "tp-yt-paper-input input",
                "input[placeholder='Search']",
                "ytd-searchbox input"
            ]
            
            for sel in input_selectors:
                try:
                    search_box = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    if search_box:
                        logger.info(f"Instance {instance_id}: Found search input with {sel}")
                        break
                except:
                    continue
            
            if not search_box:
                logger.error(f"Instance {instance_id}: Could not find search input on desktop")
                return False
            
            # Step 3: Type video ID and submit
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", search_box)
            time.sleep(random.uniform(0.2, 0.5))
            search_box.click()
            search_box.clear()
            _natural_typing(search_box, video_id, use_fast=False)
            time.sleep(random.uniform(0.3, 0.6))
            search_box.send_keys(Keys.ENTER)
            logger.info(f"Instance {instance_id}: Search submitted")
            
            # Step 4: Wait for results
            time.sleep(2.5)
            logger.info(f"Instance {instance_id}: After search, URL: {driver.current_url}")
            
            # Step 5: Find video link
            video_link = None
            link_selectors = [
                f"ytd-video-renderer a[href*='{video_id}']",
                "ytd-video-renderer a#thumbnail",
                f"a[href*='{video_id}']",
                "a[href*='/watch?v=']"
            ]
            
            for sel in link_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elements:
                        href = el.get_attribute('href')
                        if href and video_id in href:
                            video_link = el
                            logger.info(f"Instance {instance_id}: Found video link with {sel}")
                            break
                    if video_link:
                        break
                except Exception as e:
                    logger.debug(f"Selector {sel} error: {e}")
            
            if not video_link:
                # Try XPath fallback
                try:
                    video_link = driver.find_element(By.XPATH, f"//a[contains(@href, '{video_id}')]")
                    logger.info(f"Instance {instance_id}: Found video link via XPath")
                except:
                    pass
            
            if not video_link:
                logger.error(f"Instance {instance_id}: Video not found in desktop channel search results")
                all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/watch?v=']")
                logger.info(f"Instance {instance_id}: Found {len(all_links)} video links on page")
                return False
            
            # Human-like click with navigation verification
            return human_click(driver, video_link, instance_id, element_type=f"desktop channel video result (ID: {video_id[:8]})")
            
    except Exception as e:
        logger.error(f"Instance {instance_id}: Channel internal search error - {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False