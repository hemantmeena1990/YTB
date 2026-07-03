#!/usr/bin/env python3
"""
YouTube Automation - GOOGLE SEARCH ENTRY MODE (COMPLETELY FIXED)
Simulates coming from Google Search (highest trust traffic source)

FIXES APPLIED:
1. Uses platform redirect URL format (https://www.google.com/url?q=)
2. CTRL+Click to open in new tab - preserves Google referrer
3. PO token injected AFTER Google redirect completes
4. &udm=7 parameter to force classic search (avoid AI Mode)
5. Extract YouTube URL from Google redirect wrapper
6. Token verification logging after navigation
7. Stale element recovery for correction links
8. Human-like typing, delays, scrolling preserved
"""

import sys
import os
import json
import random
import shutil
import time
import logging
import importlib.util
import unicodedata
import traceback
from urllib.parse import urlparse, parse_qs, quote_plus
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# ========== ABSOLUTE PATH SETUP ==========
_script_path = Path(__file__).resolve()
PROJECT_ROOT = _script_path.parent.parent.parent
COMMON_ROOT = PROJECT_ROOT / "common"
SELENIUM_COMMON_ROOT = PROJECT_ROOT / "selenium" / "common"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(COMMON_ROOT))
sys.path.insert(0, str(SELENIUM_COMMON_ROOT))


def _load_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ========== IMPORTS ==========

# PO Token
_po_token_path = COMMON_ROOT / "po_token.py"
_po_token_module = _load_module_from_file("po_token", _po_token_path)
get_po_token = _po_token_module.get_po_token
add_po_token_to_url = _po_token_module.add_po_token_to_url
set_po_logger = _po_token_module.set_logger
set_po_token_source = _po_token_module.set_po_token_source

# Human Behavior
_human_behavior_path = COMMON_ROOT / "human_behavior.py"
_human_behavior_module = _load_module_from_file("human_behavior", _human_behavior_path)
watch_with_human_behavior = _human_behavior_module.watch_with_human_behavior
click_suggested_video = _human_behavior_module.click_suggested_video
ensure_video_playback = _human_behavior_module.ensure_video_playback
handle_all_popups = _human_behavior_module.handle_all_popups
attempt_video_playback_with_retry = _human_behavior_module.attempt_video_playback_with_retry
is_video_playing = _human_behavior_module.is_video_playing
simulate_mouse_wheel = _human_behavior_module.simulate_mouse_wheel
human_delay = _human_behavior_module.human_delay

# Human Click
_humanclick_path = COMMON_ROOT / "humanclick.py"
_humanclick_module = _load_module_from_file("humanclick", _humanclick_path)
human_click = _humanclick_module.human_click

# PO Driver
_po_driver_path = SELENIUM_COMMON_ROOT / "po_driver.py"
_po_driver_module = _load_module_from_file("po_driver", _po_driver_path)
create_driver_with_po_token = _po_driver_module.create_driver_with_po_token
set_driver_logger = _po_driver_module.set_logger
apply_fingerprint_overrides = _po_driver_module.apply_fingerprint_overrides

# Utils
_utils_path = SELENIUM_COMMON_ROOT / "utils.py"
_utils_module = _load_module_from_file("utils", _utils_path)
handle_cookies = _utils_module.handle_cookies
get_variable_watch_time = _utils_module.get_variable_watch_time
wait_for_page_load = _utils_module.wait_for_page_load
wait_for_url_change = _utils_module.wait_for_url_change
is_login_page = _utils_module.is_login_page
get_random_resolution = _utils_module.get_random_resolution

# ========== LOGGING ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTGoogleSearch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTGoogleSearch")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(log_filename, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

try:
    set_po_logger(logger)
except:
    pass
try:
    set_driver_logger(logger)
except:
    pass

logger.info(f"YTGoogleSearch.py started - PID: {os.getpid()}")
logger.info(f"Project root: {PROJECT_ROOT}")


# ========== HELPER FUNCTIONS ==========

def sanitize_text(text):
    """Remove emoji and non-BMP characters for ChromeDriver compatibility"""
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if ord(c) <= 0xFFFF)
    text = ' '.join(text.split())
    return text


def fetch_video_title_from_url(video_url):
    """Fetch video title using yt-dlp and sanitize it"""
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = info.get('title', '')
            return sanitize_text(title)
    except Exception as e:
        logger.debug(f"Could not fetch title: {e}")
        return ""


def extract_youtube_url_from_google_result(href: str) -> str:
    """
    Extract actual YouTube URL from Google's redirect wrapper.
    
    Google result href formats:
    - Direct: https://www.youtube.com/watch?v=ABC123
    - Redirect: https://www.google.com/url?q=https://www.youtube.com/watch?v=ABC123&sa=...
    
    Returns:
        Extracted YouTube URL, or original href if not a Google redirect
    """
    if not href:
        return None
    
    # Already a direct YouTube URL
    if "youtube.com/watch" in href and "google.com" not in href:
        return href
    
    # Handle Google redirect URLs
    if "google.com/url" in href:
        parsed = urlparse(href)
        query_params = parse_qs(parsed.query)
        
        if "q" in query_params:
            q_value = query_params["q"][0]
            if "youtube.com/watch" in q_value:
                return q_value
    
    return href


def build_google_redirect_url(video_url: str) -> str:
    """
    Build a proper Google redirect URL for the video.
    This is the format: https://www.google.com/url?q={encoded_url}
    """
    encoded_url = quote_plus(video_url)
    return f"https://www.google.com/url?q={encoded_url}"


def force_classic_google_search(driver, search_query, instance_id):
    """
    Navigate directly to Google with &udm=7 to force classic search results.
    This avoids Google's AI Mode which breaks result parsing.
    """
    encoded_query = quote_plus(search_query)
    search_url = f"https://www.google.com/search?q={encoded_query}&udm=7"
    
    logger.info(f"Instance {instance_id}: Forcing classic Google search with udm=7")
    logger.info(f"Instance {instance_id}: Search URL: {search_url[:100]}...")
    
    driver.get(search_url)
    wait_for_page_load(driver, 15)
    time.sleep(2)
    
    # Check if AI Mode still appears (defensive)
    if "AI Mode" in driver.page_source or "generative" in driver.page_source.lower():
        logger.warning(f"Instance {instance_id}: AI Mode detected, retrying...")
        driver.get(f"https://www.google.com/search?q={encoded_query}&udm=7&source=hp")
        time.sleep(2)
    
    return True


def _click_videos_tab(driver, instance_id):
    """Find and click the Videos tab on Google results page"""
    try:
        videos_tab_selectors = [
            "//span[text()='Videos']/ancestor::a",
            "a[href*='&tbm=vid']",
            "//a[contains(@href, 'tbm=vid')]",
            "div[role='tab'] span.R1QWuf",
            "//div[@role='tab']//span[text()='Videos']",
        ]
        
        for selector in videos_tab_selectors:
            try:
                if selector.startswith("//"):
                    elem = driver.find_element(By.XPATH, selector)
                else:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                if elem and elem.is_displayed():
                    if elem.tag_name == "span":
                        elem = driver.find_element(By.XPATH, "//span[text()='Videos']/ancestor::a")
                    logger.info(f"Instance {instance_id}: Found Videos tab with selector: {selector[:50]}")
                    return elem
            except:
                continue
        return None
    except Exception as e:
        logger.debug(f"Error finding Videos tab: {e}")
        return None


def _click_all_tab(driver, instance_id):
    """Find and click the All tab on Google results page"""
    try:
        all_tab_selectors = [
            "//span[text()='All']/ancestor::a",
            "a[href*='&tbm=']",
            "div[role='tab'] span.R1QWuf",
            "//div[@role='tab']//span[text()='All']",
        ]
        
        for selector in all_tab_selectors:
            try:
                if selector.startswith("//"):
                    elem = driver.find_element(By.XPATH, selector)
                else:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                if elem and elem.is_displayed() and 'All' in elem.text:
                    if elem.tag_name == "span":
                        elem = driver.find_element(By.XPATH, "//span[text()='All']/ancestor::a")
                    logger.info(f"Instance {instance_id}: Found All tab with selector: {selector[:50]}")
                    return elem
            except:
                continue
        return None
    except Exception as e:
        logger.debug(f"Error finding All tab: {e}")
        return None


def _find_and_click_video_by_id(driver, instance_id, video_id, po_token):
    """
    Find video by exact ID on Google results page.
    
    CRITICAL: CTRL+Click preserves Google referrer
              PO token injected AFTER Google redirect completes
    """
    try:
        time.sleep(1)
        
        # Find the video element
        elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='youtube.com/watch']")
        video_element = None
        
        for elem in elements:
            href = elem.get_attribute('href')
            if href and (f'/watch?v={video_id}' in href or f'watch?v={video_id}' in href):
                video_element = elem
                logger.info(f"Instance {instance_id}: Found video link for ID: {video_id}")
                break
        
        if not video_element:
            return False
        
        # Store current window handles before click
        original_handles = driver.window_handles
        original_handle_count = len(original_handles)
        
        logger.info(f"Instance {instance_id}: CTRL+Click to open in new tab (preserves Google referrer)")
        
        # CRITICAL: CTRL+Click to open in new tab
        # This preserves Google as the referrer
        ActionChains(driver) \
            .key_down(Keys.CONTROL) \
            .click(video_element) \
            .key_up(Keys.CONTROL) \
            .perform()
        
        # Wait for new tab to open
        timeout = 10
        start_time = time.time()
        while len(driver.window_handles) <= original_handle_count:
            if time.time() - start_time > timeout:
                raise Exception("New tab did not open")
            time.sleep(0.5)
        
        # Find and switch to new tab
        new_handle = None
        for handle in driver.window_handles:
            if handle not in original_handles:
                new_handle = handle
                break
        
        if new_handle:
            driver.switch_to.window(new_handle)
            logger.info(f"Instance {instance_id}: Switched to new tab")
            
            # Wait for Google redirect to complete
            wait_for_page_load(driver, 15)
            time.sleep(2)
            
            # ✅ RE-APPLY FINGERPRINT AFTER NEW TAB
            if cfg:
                use_undetected = getattr(cfg, 'use_undetected', False)
                apply_fingerprint_overrides(driver, cfg, instance_id, is_undetected=use_undetected)
                logger.info(f"Instance {instance_id}: 🔄 Fingerprint re-applied in new tab")
            
            # Get final URL after redirect
            current_url = driver.current_url
            logger.info(f"Instance {instance_id}: Final URL after redirect: {current_url[:150]}")
            
            # CRITICAL: Inject PO token AFTER redirect (not before)
            if po_token and 'youtube.com/watch' in current_url:
                if 'pot=' not in current_url:
                    separator = '&' if '?' in current_url else '?'
                    final_url = f"{current_url}{separator}pot={po_token}"
                    logger.info(f"Instance {instance_id}: Injecting PO token after redirect")
                    driver.get(final_url)
                    time.sleep(1)
                    
                    # Verify token was preserved (check for pot= parameter)
                    current_url_after = driver.current_url
                    if 'pot=' in current_url_after:
                        logger.info(f"Instance {instance_id}: ✅ PO TOKEN VERIFIED (pot= parameter present)")
                        # Extract and log first few chars of token
                        import re
                        match = re.search(r'pot=([^&]+)', current_url_after)
                        if match:
                            token_preview = match.group(1)[:30]
                            logger.info(f"Instance {instance_id}: Token preview: {token_preview}...")
                    else:
                        logger.warning(f"Instance {instance_id}: ⚠️ PO TOKEN MISSING from URL!")
                else:
                    logger.info(f"Instance {instance_id}: PO token already present")
            else:
                logger.info(f"Instance {instance_id}: No PO token to inject (po_token={po_token is not None})")
            
            # Close original Google tab (optional)
            try:
                driver.switch_to.window(original_handles[0])
                driver.close()
                driver.switch_to.window(new_handle)
            except:
                pass
            
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error in _find_and_click_video_by_id: {e}")
        return False


def _find_and_click_video_by_id_redirect(driver, instance_id, video_id, po_token):
    """
    Alternative method: Navigate directly via Google redirect URL.
    This simulates coming from Google Search by using the actual redirect format.
    """
    try:
        # Build the Google redirect URL
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        redirect_url = f"https://www.google.com/url?q={quote_plus(watch_url)}"
        
        # Add PO token to the final URL (will be injected after redirect)
        logger.info(f"Instance {instance_id}: Using Google redirect method")
        logger.info(f"Instance {instance_id}: Redirect URL: {redirect_url[:150]}...")
        
        # Navigate to Google redirect URL
        driver.get(redirect_url)
        wait_for_page_load(driver, 15)
        time.sleep(2)
        
        # After redirect, we should be on YouTube
        current_url = driver.current_url
        logger.info(f"Instance {instance_id}: After redirect: {current_url[:150]}")
        
        # Inject PO token if needed
        if po_token and 'youtube.com/watch' in current_url:
            if 'pot=' not in current_url:
                separator = '&' if '?' in current_url else '?'
                final_url = f"{current_url}{separator}pot={po_token}"
                logger.info(f"Instance {instance_id}: Injecting PO token")
                driver.get(final_url)
                time.sleep(1)
                
                if 'pot=' in driver.current_url:
                    logger.info(f"Instance {instance_id}: ✅ PO TOKEN VERIFIED")
                else:
                    logger.warning(f"Instance {instance_id}: ⚠️ PO TOKEN MISSING")
        
        return True
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Redirect method failed: {e}")
        return False


# ========== GOOGLE SEARCH NAVIGATION ==========

def simulate_google_search_entry(driver, instance_id, video_title, video_id, po_token, is_mobile, cfg=None):
    """
    Simulate coming from Google Search.
    Three-tier fallback with CTRL+Click to preserve referrer.
    
    Tier 1: Full title search with udm=7
    Tier 2: Videos tab search
    Tier 3: Video ID only search with correction handling
    """
    try:
        # Sanitize the search query
        search_query = sanitize_text(video_title) if video_title else video_id
        if not search_query:
            search_query = "youtube video"
        
        if len(search_query) < 5 and search_query == video_id:
            search_query = f"{video_id} youtube"
        
        logger.info(f"Instance {instance_id}: Simulating Google Search entry")
        logger.info(f"Instance {instance_id}: Target video ID: {video_id}")
        logger.info(f"Instance {instance_id}: Search query: {search_query[:80]}")
        
        # ========== TIER 1: Full title search with udm=7 ==========
        logger.info(f"Instance {instance_id}: TIER 1 - Searching with full title")
        
        force_classic_google_search(driver, search_query, instance_id)
        
        # Accept cookies if present
        try:
            accept_btn = driver.find_element(By.XPATH, "//button[contains(., 'Accept') or contains(., 'I agree') or contains(., 'Accept all')]")
            human_click(driver, accept_btn, instance_id, "Google cookie accept")
            time.sleep(1)
        except:
            pass
        
        # Human-like scrolling
        simulate_mouse_wheel(driver, random.randint(200, 400))
        time.sleep(1)
        
        # Find and open video (CTRL+Click preserves referrer)
        clicked = _find_and_click_video_by_id(driver, instance_id, video_id, po_token, cfg)
        if clicked:
            logger.info(f"Instance {instance_id}: TIER 1 succeeded")
            return True
        
        # ========== TIER 2: Click Videos tab ==========
        logger.info(f"Instance {instance_id}: TIER 2 - Switching to Videos tab")
        
        try:
            videos_tab = _click_videos_tab(driver, instance_id)
            
            if videos_tab:
                human_click(driver, videos_tab, instance_id, "Google Videos tab")
                logger.info(f"Instance {instance_id}: Clicked Videos tab")
                time.sleep(2)
                simulate_mouse_wheel(driver, 400)
                time.sleep(1)
                
                clicked = _find_and_click_video_by_id(driver, instance_id, video_id, po_token, cfg=None)
                if clicked:
                    logger.info(f"Instance {instance_id}: TIER 2 succeeded")
                    return True
            else:
                logger.warning(f"Instance {instance_id}: Could not find Videos tab")
                
        except Exception as e:
            logger.warning(f"Instance {instance_id}: Error switching to Videos tab: {e}")
        
        # ========== TIER 3: Search by video ID only with correction handling ==========
        logger.info(f"Instance {instance_id}: TIER 3 - Simplified search by video ID")
        
        try:
            # Step 1: Click "All" tab to reset
            all_tab = _click_all_tab(driver, instance_id)
            if all_tab:
                human_click(driver, all_tab, instance_id, "All tab")
                logger.info(f"Instance {instance_id}: Clicked All tab")
                time.sleep(2)
                wait_for_page_load(driver, 10)
            
            # Step 2: Search by video ID with udm=7
            encoded_id = quote_plus(video_id)
            driver.get(f"https://www.google.com/search?q={encoded_id}&udm=7")
            wait_for_page_load(driver, 15)
            time.sleep(2)
            
            # Step 3: Handle correction link if present
            try:
                correction_selectors = [
                    f"//a[text()='{video_id}']",
                    "//a[contains(text(), 'Showing results for')]",
                    "//a[contains(@href, '/search?q=') and contains(text(), 'did you mean')]",
                    "//a[contains(@href, '/search?q=')]//b"
                ]
                
                for selector in correction_selectors:
                    try:
                        if selector.startswith("//"):
                            correction_link = driver.find_element(By.XPATH, selector)
                        else:
                            correction_link = driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if correction_link and correction_link.is_displayed():
                            logger.info(f"Instance {instance_id}: Found correction link, clicking...")
                            human_click(driver, correction_link, instance_id, "Correction link")
                            time.sleep(2)
                            wait_for_page_load(driver, 10)
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Correction link handling: {e}")
            
            # Step 4: Find and open video
            simulate_mouse_wheel(driver, 300)
            time.sleep(1)
            
            clicked = _find_and_click_video_by_id(driver, instance_id, video_id, po_token, cfg)
            if clicked:
                logger.info(f"Instance {instance_id}: TIER 3 succeeded")
                return True
            else:
                logger.warning(f"Instance {instance_id}: Video not found after TIER 3")
                
        except Exception as e:
            logger.error(f"Instance {instance_id}: TIER 3 failed - {e}")
        
        # ========== ALL TIERS FAILED - Try redirect method ==========
        logger.info(f"Instance {instance_id}: All tiers failed, trying Google redirect method")
        return _find_and_click_video_by_id_redirect(driver, instance_id, video_id, po_token)
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Google Search simulation failed - {e}")
        logger.error(traceback.format_exc())
        return False


# ========== CONFIGURATION ==========
@dataclass
class SessionConfig:
    instance_id: int
    url: str
    video_id: str
    video_title: str
    min_watch_time: int
    max_watch_time: int
    suggested_min: int
    suggested_max: int
    suggested_chance: float
    headless: bool
    user_agent: str
    is_mobile: bool
    cycles: int = 1
    po_token: str = None
    visitor_id: str = None
    po_token_source: str = "external"
    proxy: str = None
    proxy_mode: str = "none"
    num_instances: int = 1
    current_proxy: str = None
    cycle_number: int = 1
    redirect_url: str = None
    traffic_source: str = "google_search"
    
    # ========== ✅ ADD THESE MISSING FIELDS ==========
    automation_version: str = "selenium"
    use_undetected: bool = False
    referer: str = None
    chrome_args: list = None
    # ===============================================
    
    # ========== ✅ ADD FINGERPRINT FIELDS ==========
    platform: str = "Win32"
    screen_width: int = 1920
    screen_height: int = 1080
    viewport_width: int = 1920
    viewport_height: int = 950
    plugins_length: int = 5
    device_category: str = "desktop"
    vendor: str = "Google Inc."
    connection: dict = None
    language: str = "en-US"
    force_mobile: bool = False
    fingerprint_type: str = "desktop"
    # ===============================================


# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        logger.info(f"Instance {cfg.instance_id}: ========== Starting Google Search Mode ==========")
        logger.info(f"Instance {cfg.instance_id}: Video ID: {cfg.video_id}")
        logger.info(f"Instance {cfg.instance_id}: Video title: {cfg.video_title[:80] if cfg.video_title else 'N/A'}")
        logger.info(f"Instance {cfg.instance_id}: PO token source: {cfg.po_token_source}")
        logger.info(f"Instance {cfg.instance_id}: Proxy: {cfg.proxy if cfg.proxy else 'none'}")
        logger.info(f"Instance {cfg.instance_id}: Cycles: {cfg.cycles}")
        
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_google_cache")
        
        cycles_done = 0
        total_cycles = cfg.cycles
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: --- Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'} ---")
            
            search_success = simulate_google_search_entry(
                driver, 
                cfg.instance_id, 
                cfg.video_title, 
                cfg.video_id, 
                cfg.po_token, 
                cfg.is_mobile,
                cfg
            )
            
            if not search_success:
                logger.error(f"Instance {cfg.instance_id}: Video not found, aborting cycle")
                cycles_done += 1
                continue
            
            wait_for_page_load(driver, 30)
            time.sleep(random.uniform(2, 4))
            
            if is_login_page(driver):
                logger.warning(f"Instance {cfg.instance_id}: Login page detected, aborting")
                return
            
            handle_cookies(driver, cfg.instance_id)
            handle_all_popups(driver, cfg.instance_id)
            
            if is_video_playing(driver):
                logger.info(f"Instance {cfg.instance_id}: Video already playing")
                playback_success = True
            else:
                logger.info(f"Instance {cfg.instance_id}: Starting playback...")
                playback_success = attempt_video_playback_with_retry(
                    driver, cfg.instance_id, cfg.is_mobile, is_suggested=False, max_retries=3
                )
            
            if playback_success:
                main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
                logger.info(f"Instance {cfg.instance_id}: Watching main for {main_watch}s")
                watch_with_human_behavior(driver, main_watch, cfg.is_mobile)
            else:
                logger.warning(f"Instance {cfg.instance_id}: Playback failed, skipping watch")
            
            if random.random() < cfg.suggested_chance:
                logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
                if click_suggested_video(driver, cfg.is_mobile):
                    time.sleep(2)
                    wait_for_page_load(driver, 20)
                    handle_cookies(driver, cfg.instance_id)
                    
                    suggested_playback = attempt_video_playback_with_retry(
                        driver, cfg.instance_id, cfg.is_mobile, is_suggested=True, max_retries=2
                    )
                    
                    if suggested_playback:
                        suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                        logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
                        watch_with_human_behavior(driver, suggested_watch, cfg.is_mobile)
                    else:
                        logger.warning(f"Instance {cfg.instance_id}: Suggested playback failed")
                else:
                    logger.warning(f"Instance {cfg.instance_id}: Could not load suggested video")
            
            cycles_done += 1
            
            if total_cycles == 0 or cycles_done < total_cycles:
                pause_duration = random.uniform(5, 15)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause_duration:.1f}s")
                time.sleep(pause_duration)
                driver.get("https://www.google.com")
                time.sleep(2)
        
        logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycles")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error - {e}")
        logger.error(traceback.format_exc())
    finally:
        if driver:
            try:
                driver.quit()
                logger.info(f"Instance {cfg.instance_id}: Driver closed")
            except:
                pass
        if profile_dir and os.path.exists(profile_dir):
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
                logger.info(f"Instance {cfg.instance_id}: Profile deleted")
            except:
                pass


# ========== MAIN ==========

def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTGoogleSearch.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    logger.info(f"Loading config from: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    logger.info(f"Starting YTGoogleSearch with {len(instances)} instance(s)")
    processes = []
    
    for d in instances:
        video_id = d.get("video_id", "")
        po_token = None
        visitor_id = None
        po_token_source = d.get("po_token_source", "external")
        set_po_token_source(po_token_source)
        
        if video_id:
            po_token, visitor_id = get_po_token(video_id, d.get("instance_id", 0))
            if po_token:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: PO token received")
            else:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: No token")
        
        video_title = d.get("video_title", "")
        if not video_title and video_id:
            video_title = fetch_video_title_from_url(d.get("url", ""))
            if not video_title:
                video_title = video_id
        
        assigned_proxy = d.get("proxy", None)
        redirect_url = d.get("redirect_url", None)
        
        cfg = SessionConfig(
            instance_id=d.get("instance_id", 0),
            url=d.get("url", ""),
            video_id=video_id,
            video_title=video_title,
            min_watch_time=d.get("min_watch_time", 15),
            max_watch_time=d.get("max_watch_time", 30),
            suggested_min=d.get("suggested_min", 15),
            suggested_max=d.get("suggested_max", 35),
            suggested_chance=d.get("suggested_chance", 0.4),
            headless=d.get("headless", False),
            user_agent=d.get("user_agent", ""),
            is_mobile=d.get("is_mobile", False),
            cycles=d.get("cycles", 1),
            po_token=po_token,
            visitor_id=visitor_id,
            po_token_source=po_token_source,
            proxy=assigned_proxy,
            proxy_mode=d.get("proxy_mode", "none"),
            num_instances=d.get("num_instances", 1),
            current_proxy=assigned_proxy,
            cycle_number=d.get("cycle_number", 1),
            redirect_url=redirect_url,
            traffic_source=d.get("traffic_source", "google_search"),
            # ========== ✅ ADD FINGERPRINT FIELDS ==========
            platform=d.get("platform", "Win32"),
            screen_width=d.get("screen_width", 1920),
            screen_height=d.get("screen_height", 1080),
            viewport_width=d.get("viewport_width", 1920),
            viewport_height=d.get("viewport_height", 950),
            plugins_length=d.get("plugins_length", 5),
            device_category=d.get("device_category", "desktop"),
            vendor=d.get("vendor", "Google Inc."),
            connection=d.get("connection", None),
            language=d.get("language", "en-US"),
            force_mobile=d.get("force_mobile", False),
            fingerprint_type=d.get("fingerprint_type", "desktop"),
            automation_version=d.get("automation_version", "selenium"),
            use_undetected=d.get("use_undetected", False),
            referer=d.get("referer", None),
            chrome_args=d.get("chrome_args", None)
            # ===============================================
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        logger.info(f"Instance {cfg.instance_id} started in process {p.pid}")
        time.sleep(random.uniform(1, 3))
    
    for p in processes:
        p.join()
        logger.info(f"Process {p.pid} completed")
    
    logger.info("All Google Search sessions finished")


if __name__ == "__main__":
    main()