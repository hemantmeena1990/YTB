#!/usr/bin/env python3
"""
YouTube Automation - CHANNEL VIEW MODE (Config-only)
With PO token support, retry logic, and human_click integration.
"""

import sys
import os
import json
import random
import shutil
import time
import logging
import importlib.util
import traceback
from selenium.webdriver.common.by import By
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass

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
get_random_resolution = _utils_module.get_random_resolution
human_delay = _utils_module.human_delay

# Search and Find modules
_search_path = SELENIUM_COMMON_ROOT / "search.py"
_find_path = SELENIUM_COMMON_ROOT / "find.py"

_search_module = _load_module_from_file("search", _search_path)
DesktopSearch = _search_module.DesktopSearch
MobileSearch = _search_module.MobileSearch

_find_module = _load_module_from_file("find", _find_path)
find_and_click_channel_result = _find_module.find_and_click_channel_result
channel_internal_search = _find_module.channel_internal_search

# ========== LOGGING ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTChannel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTChannel")
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

logger.info(f"YTChannel.py started - PID: {os.getpid()}")
logger.info(f"Project root: {PROJECT_ROOT}")

# ========== CONFIGURATION ==========
@dataclass
class SessionConfig:
    instance_id: int
    url: str
    constructed_url: str
    video_id: str
    channel_name: str
    min_watch_time: int
    max_watch_time: int
    suggested_min: int
    suggested_max: int
    suggested_chance: float
    headless: bool
    user_agent: str
    is_mobile: bool
    video_title: str = ""
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
        logger.info(f"Instance {cfg.instance_id}: Starting with channel: {cfg.channel_name}")
        
        # Create driver with PO token (passing proxy if available)
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_channel_cache")
        
        search_query = cfg.channel_name
        cycles_done = 0
        total_cycles = cfg.cycles
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'}")
            
            # Search for channel on YouTube homepage
            if cfg.is_mobile:
                if not MobileSearch.perform_search(driver, cfg.instance_id, search_query):
                    logger.error(f"Instance {cfg.instance_id}: Mobile search failed")
                    return
            else:
                if not DesktopSearch.perform_search(driver, cfg.instance_id, search_query):
                    logger.error(f"Instance {cfg.instance_id}: Desktop search failed")
                    return
            
            # Click channel result (uses human_click internally now)
            if not find_and_click_channel_result(driver, cfg.instance_id, search_query, cfg.is_mobile):
                logger.error(f"Instance {cfg.instance_id}: Could not find/click channel result")
                return
            
            time.sleep(2)
            wait_for_page_load(driver, 15)
            
            # Inside channel, search for AND click video (PO token injection happens inside)
            logger.info(f"Instance {cfg.instance_id}: Calling channel_internal_search with po_token = {cfg.po_token is not None}")
            if cfg.po_token:
                logger.info(f"Instance {cfg.instance_id}: PO token first 50 chars: {cfg.po_token[:50]}")
            logger.info(f"Instance {cfg.instance_id}: *** cfg.po_token value: {cfg.po_token is not None} ***")
            if cfg.po_token:
                logger.info(f"Instance {cfg.instance_id}: *** cfg.po_token length: {len(cfg.po_token)} ***")
            search_result = channel_internal_search(driver, cfg.instance_id, cfg.video_id, cfg.is_mobile, cfg.po_token, cfg.video_title)
            if not search_result:
                logger.error(f"Instance {cfg.instance_id}: Could not search within channel or click video")
                return
            else:
                logger.info(f"Instance {cfg.instance_id}: channel_internal_search returned True, continuing...")
            
            logger.info(f"Instance {cfg.instance_id}: Video clicked successfully")
            
            # Wait for video page to load
            logger.info(f"Instance {cfg.instance_id}: Waiting for video page to load...")
            wait_for_page_load(driver, 30)
                        # Wait for video page to load
            logger.info(f"Instance {cfg.instance_id}: Waiting for video page to load...")
            wait_for_page_load(driver, 30)
            time.sleep(random.uniform(2, 4))
            
            # DEBUG: Check the final URL after page load
            final_url = driver.current_url
            logger.info(f"Instance {cfg.instance_id}: FINAL VIDEO PAGE URL: {final_url[:200]}")
            if 'pot=' in final_url:
                logger.info(f"Instance {cfg.instance_id}: *** TOKEN IS PRESENT IN FINAL URL ***")
            else:
                logger.warning(f"Instance {cfg.instance_id}: *** NO TOKEN IN FINAL URL ***")
            time.sleep(random.uniform(2, 4))  # Extra buffer for video to start
            
            if is_login_page(driver):
                logger.warning(f"Instance {cfg.instance_id}: Login page, aborting")
                return
            
            handle_cookies(driver, cfg.instance_id)
            
            # Check if video is already playing before attempting retry
            if is_video_playing(driver):
                logger.info(f"Instance {cfg.instance_id}: Video is already playing, skipping playback retry")
                playback_success = True
            else:
                logger.info(f"Instance {cfg.instance_id}: Video not playing, attempting to start...")
                # Use retry function for video playback
                playback_success = attempt_video_playback_with_retry(
                    driver,
                    cfg.instance_id,
                    cfg.is_mobile,
                    is_suggested=False,
                    max_retries=2
                )
            
            if playback_success:
                main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
                logger.info(f"Instance {cfg.instance_id}: Watching main for {main_watch}s")
                watch_with_human_behavior(driver, main_watch, cfg.is_mobile)
            else:
                logger.warning(f"Instance {cfg.instance_id}: Main video playback failed, but continuing with watch anyway")
                # Still watch even if playback detection failed (video might be playing)
                main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
                logger.info(f"Instance {cfg.instance_id}: Attempting to watch for {main_watch}s despite detection issue")
                watch_with_human_behavior(driver, main_watch, cfg.is_mobile)
            
            # Suggested video
            if random.random() < cfg.suggested_chance:
                logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
                if click_suggested_video(driver, cfg.is_mobile):
                    time.sleep(2)
                    wait_for_page_load(driver, 20)
                    handle_cookies(driver, cfg.instance_id)
                    
                    suggested_playback = attempt_video_playback_with_retry(
                        driver,
                        cfg.instance_id,
                        cfg.is_mobile,
                        is_suggested=True,
                        max_retries=2
                    )
                    
                    if suggested_playback:
                        suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                        logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
                        watch_with_human_behavior(driver, suggested_watch, cfg.is_mobile)
                    else:
                        logger.warning(f"Instance {cfg.instance_id}: Suggested video playback failed, skipping")
                else:
                    logger.warning(f"Instance {cfg.instance_id}: Could not load suggested video")
            
            cycles_done += 1
            
            if total_cycles == 0 or cycles_done < total_cycles:
                pause_duration = random.uniform(5, 15)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause_duration:.1f}s before next cycle")
                time.sleep(pause_duration)
                
                # Clear cookies and return to home page for next cycle
                driver.delete_all_cookies()
                driver.get("https://www.youtube.com")
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
        logger.error("Usage: python YTChannel.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    logger.info(f"Loading config from: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    logger.info(f"Starting YTChannel with {len(instances)} instance(s)")
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
        
        assigned_proxy = d.get("proxy", None)
        
        cfg = SessionConfig(
            instance_id=d.get("instance_id", 0),
            url=d.get("url", ""),
            constructed_url=d.get("constructed_url", ""),
            video_id=video_id,
            channel_name=d.get("channel_name", ""),
            video_title=d.get("video_title", ""),
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