#!/usr/bin/env python3
"""
YouTube Automation - GOOGLE SEARCH ENTRY MODE
Simulates coming from Google Search (highest trust traffic source)
Searches Google for the video title, then clicks the YouTube result
Uses all common modules with retry logic, PO token injection, and human_click.
Three-tier fallback: Full title search → Videos tab → Video ID only search
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
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
start_video_with_audio_mute = _human_behavior_module.start_video_with_audio_mute
click_suggested_video = _human_behavior_module.click_suggested_video
ensure_video_playback = _human_behavior_module.ensure_video_playback
handle_all_popups = _human_behavior_module.handle_all_popups
attempt_video_playback_with_retry = _human_behavior_module.attempt_video_playback_with_retry
is_video_playing = _human_behavior_module.is_video_playing
simulate_mouse_wheel = _human_behavior_module.simulate_mouse_wheel

# Human Click
_humanclick_path = COMMON_ROOT / "humanclick.py"
_humanclick_module = _load_module_from_file("humanclick", _humanclick_path)
human_click = _humanclick_module.human_click

# PO Driver
_po_driver_path = SELENIUM_COMMON_ROOT / "po_driver.py"
_po_driver_module = _load_module_from_file("po_driver", _po_driver_path)
create_driver_with_po_token = _po_driver_module.create_driver_with_po_token
set_driver_logger = _po_driver_module.set_logger

# Utils
_utils_path = SELENIUM_COMMON_ROOT / "utils.py"
_utils_module = _load_module_from_file("utils", _utils_path)
handle_cookies = _utils_module.handle_cookies
get_variable_watch_time = _utils_module.get_variable_watch_time
wait_for_page_load = _utils_module.wait_for_page_load
wait_for_url_change = _utils_module.wait_for_url_change
is_login_page = _utils_module.is_login_page
human_delay = _utils_module.human_delay
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
    Helper function to find video by exact ID on Google results page.
    Uses direct navigation instead of clicking to preserve PO token.
    """
    try:
        time.sleep(1)
        
        elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='youtube.com/watch']")
        
        for elem in elements:
            href = elem.get_attribute('href')
            if href and (f'/watch?v={video_id}' in href or f'watch?v={video_id}' in href):
                logger.info(f"Instance {instance_id}: Found video link for ID: {video_id}")
                
                final_href = href
                if po_token and 'pot=' not in final_href:
                    separator = '&' if '?' in final_href else '?'
                    final_href = f"{final_href}{separator}pot={po_token}"
                    logger.info(f"Instance {instance_id}: Injected PO token into URL")
                    logger.info(f"Instance {instance_id}: Final URL: {final_href[:150]}")
                
                driver.get(final_href)
                logger.info(f"Instance {instance_id}: Navigated directly to video")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error in _find_and_click_video_by_id: {e}")
        return False


# ========== GOOGLE SEARCH NAVIGATION ==========

def simulate_google_search_entry(driver, instance_id, video_title, video_id, po_token, is_mobile):
    """
    Simulate coming from Google Search.
    Three-tier fallback:
    1. Search full title → look for exact video ID
    2. Click Videos tab → look for exact video ID
    3. Click "All" tab → search by video ID only → click correction link if needed
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
        
        # Go to Google
        driver.get("https://www.google.com")
        wait_for_page_load(driver, 10)
        
        # Accept cookies if present
        try:
            accept_btn = driver.find_element(By.XPATH, "//button[contains(., 'Accept') or contains(., 'I agree')]")
            human_click(driver, accept_btn, instance_id, "Google cookie accept")
            time.sleep(1)
        except:
            pass
        
        # Find search box
        search_box = driver.find_element(By.NAME, "q")
        human_delay(0.5, 1)
        
        # ========== TIER 1: Search full title ==========
        logger.info(f"Instance {instance_id}: TIER 1 - Searching with title: {search_query[:80]}")
        
        search_box.clear()
        for char in search_query[:60]:
            try:
                search_box.send_keys(char)
                time.sleep(random.uniform(0.08, 0.25))
            except:
                continue
        
        time.sleep(random.uniform(1, 2))
        search_box.send_keys(Keys.RETURN)
        
        wait_for_page_load(driver, 15)
        time.sleep(2)
        
        simulate_mouse_wheel(driver, 300)
        time.sleep(1)
        
        clicked = _find_and_click_video_by_id(driver, instance_id, video_id, po_token)
        if clicked:
            logger.info(f"Instance {instance_id}: TIER 1 succeeded - found video by ID")
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
                
                clicked = _find_and_click_video_by_id(driver, instance_id, video_id, po_token)
                if clicked:
                    logger.info(f"Instance {instance_id}: TIER 2 succeeded - found video by ID in Videos tab")
                    return True
            else:
                logger.warning(f"Instance {instance_id}: Could not find Videos tab")
                
        except Exception as e:
            logger.warning(f"Instance {instance_id}: Error switching to Videos tab: {e}")
        
        # ========== TIER 3: Click All tab, search by video ID, handle correction ==========
        logger.info(f"Instance {instance_id}: TIER 3 - Simplified search")
        
        try:
            # Step 1: Click "All" tab
            all_tab = _click_all_tab(driver, instance_id)
            if all_tab:
                human_click(driver, all_tab, instance_id, "All tab")
                logger.info(f"Instance {instance_id}: Clicked All tab")
                time.sleep(2)
                wait_for_page_load(driver, 10)
            
            # Step 2: Search by video ID only
            search_box = driver.find_element(By.NAME, "q")
            human_click(driver, search_box, instance_id, "search box")
            search_box.clear()
            
            for char in video_id:
                search_box.send_keys(char)
                time.sleep(random.uniform(0.08, 0.15))
            
            time.sleep(random.uniform(0.5, 1))
            search_box.send_keys(Keys.RETURN)
            
            wait_for_page_load(driver, 15)
            time.sleep(2)
            
            # Step 3: Check for correction link
            try:
                correction_link = driver.find_element(By.XPATH, f"//a[text()='{video_id}']")
                if correction_link and correction_link.is_displayed():
                    logger.info(f"Instance {instance_id}: Found correction link with text: {video_id}")
                    human_click(driver, correction_link, instance_id, "Correction link")
                    time.sleep(2)
                    wait_for_page_load(driver, 10)
            except:
                logger.debug(f"No correction link found with exact text: {video_id}")
            
            # Step 4: Find and navigate to video
            simulate_mouse_wheel(driver, 300)
            time.sleep(1)
            
            clicked = _find_and_click_video_by_id(driver, instance_id, video_id, po_token)
            if clicked:
                logger.info(f"Instance {instance_id}: TIER 3 succeeded - found video")
                return True
            else:
                logger.warning(f"Instance {instance_id}: Video not found after TIER 3")
                
        except Exception as e:
            logger.error(f"Instance {instance_id}: TIER 3 failed - {e}")
        
        # ========== ALL TIERS FAILED ==========
        logger.error(f"Instance {instance_id}: Video ID {video_id} not found after all 3 tiers")
        return False
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Google Search simulation failed - {e}")
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


# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        logger.info(f"Instance {cfg.instance_id}: Starting Google Search mode")
        logger.info(f"Instance {cfg.instance_id}: Video title: {cfg.video_title[:80] if cfg.video_title else 'N/A'}")
        logger.info(f"Instance {cfg.instance_id}: PO token source: {cfg.po_token_source}")
        logger.info(f"Instance {cfg.instance_id}: Proxy: {cfg.proxy if cfg.proxy else 'none'}")
        
        # Create driver
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_google_cache")
        
        cycles_done = 0
        total_cycles = cfg.cycles
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'}")
            
            # Step 1: Google Search and click result
            search_success = simulate_google_search_entry(
                driver, 
                cfg.instance_id, 
                cfg.video_title, 
                cfg.video_id, 
                cfg.po_token, 
                cfg.is_mobile
            )
            
            if not search_success:
                logger.error(f"Instance {cfg.instance_id}: Video not found in Google Search, aborting cycle")
                return
            
            # Step 2: Wait for video page to load
            wait_for_page_load(driver, 30)
            time.sleep(random.uniform(2, 4))
            
            if is_login_page(driver):
                logger.warning(f"Instance {cfg.instance_id}: Login page, aborting")
                return
            
            handle_cookies(driver, cfg.instance_id)
            
            # Step 3: Check if video is already playing
            if is_video_playing(driver):
                logger.info(f"Instance {cfg.instance_id}: Video already playing, skipping playback retry")
                playback_success = True
            else:
                logger.info(f"Instance {cfg.instance_id}: Video not playing, attempting to start...")
                playback_success = attempt_video_playback_with_retry(
                    driver, cfg.instance_id, cfg.is_mobile, is_suggested=False, max_retries=3
                )
            
            # Step 4: Watch main video
            if playback_success:
                main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
                logger.info(f"Instance {cfg.instance_id}: Watching main for {main_watch}s")
                watch_with_human_behavior(driver, main_watch, cfg.is_mobile)
            else:
                logger.warning(f"Instance {cfg.instance_id}: Main video playback failed, skipping watch")
            
            # Step 5: Suggested video
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
                        logger.warning(f"Instance {cfg.instance_id}: Suggested video playback failed")
                else:
                    logger.warning(f"Instance {cfg.instance_id}: Could not load suggested video")
            
            cycles_done += 1
            
            if total_cycles == 0 or cycles_done < total_cycles:
                pause_duration = random.uniform(5, 15)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause_duration:.1f}s before next cycle")
                time.sleep(pause_duration)
                
                # Reset for next cycle
                driver.delete_all_cookies()
                driver.get("https://www.google.com")
                time.sleep(2)
        
        logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycle(s)")
        
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
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: No token, will use native")
        
        # Get video title
        video_title = d.get("video_title", "")
        if not video_title and video_id:
            video_title = fetch_video_title_from_url(d.get("url", ""))
            if not video_title:
                video_title = video_id
        
        assigned_proxy = d.get("proxy", None)
        
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
            user_agent=d.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            is_mobile=d.get("is_mobile", False),
            cycles=d.get("cycles", 1),
            po_token=po_token,
            visitor_id=visitor_id,
            po_token_source=po_token_source,
            proxy=assigned_proxy
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        logger.info(f"Instance {cfg.instance_id} started in process {p.pid}")
        time.sleep(random.uniform(1, 3))
    
    for p in processes:
        p.join()
        logger.info(f"Process {p.pid} completed")
    
    logger.info("All sessions finished")


if __name__ == "__main__":
    main()