#!/usr/bin/env python3
"""
YouTube Automation - SEARCH MODE for Regular Videos
With PO token support using shared driver
Runs one cycle per invocation – cycles are controlled by YTDash.
Parallel instances using multiprocessing.Process.
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
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass


# ========== PATH SETUP - PROJECT ROOT BASED ==========
# Get the absolute path of this script
_script_path = Path(__file__).resolve()
PROJECT_ROOT = _script_path.parent.parent.parent
SELENIUM_ROOT = _script_path.parent.parent
COMMON_ROOT = PROJECT_ROOT / "common"
SELENIUM_COMMON_ROOT = SELENIUM_ROOT / "common"

# Store in environment for subprocesses
os.environ['PROJECT_ROOT'] = str(PROJECT_ROOT)

# Add paths for imports
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(COMMON_ROOT))
sys.path.insert(0, str(SELENIUM_ROOT))
sys.path.insert(0, str(SELENIUM_COMMON_ROOT))


# ========== HELPER FUNCTION FOR DIRECT MODULE LOADING ==========
def _load_module_from_file(module_name, file_path):
    """Load a module directly from file path (bypasses import system)"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        raise ImportError(f"Failed to load {module_name} from {file_path}: {e}")

# ========== Import po_token (from common) ==========
_po_token_path = COMMON_ROOT / "po_token.py"
if _po_token_path.exists():
    _po_token_module = _load_module_from_file("po_token", _po_token_path)
    get_po_token = _po_token_module.get_po_token
    add_po_token_to_url = _po_token_module.add_po_token_to_url
    set_po_logger = _po_token_module.set_logger
    set_po_token_source = _po_token_module.set_po_token_source
else:
    raise ImportError(f"Cannot find po_token module at {_po_token_path}")

# ========== Import po_driver (from selenium/common) ==========
_po_driver_path = SELENIUM_COMMON_ROOT / "po_driver.py"
if _po_driver_path.exists():
    _po_driver_module = _load_module_from_file("po_driver", _po_driver_path)
    create_driver_with_po_token = _po_driver_module.create_driver_with_po_token
    set_driver_logger = _po_driver_module.set_logger
else:
    raise ImportError(f"Cannot find po_driver module at {_po_driver_path}")

# ========== Import utils (from selenium/common) ==========
_utils_path = SELENIUM_COMMON_ROOT / "utils.py"
if _utils_path.exists():
    _utils_module = _load_module_from_file("utils", _utils_path)
    handle_cookies = _utils_module.handle_cookies
    get_variable_watch_time = _utils_module.get_variable_watch_time
    wait_for_page_load = _utils_module.wait_for_page_load
    is_login_page = _utils_module.is_login_page
else:
    raise ImportError(f"Cannot find utils module at {_utils_path}")

# ========== Import human_behavior (from common) ==========
_human_behavior_path = COMMON_ROOT / "human_behavior.py"
if _human_behavior_path.exists():
    _human_behavior_module = _load_module_from_file("human_behavior", _human_behavior_path)
    watch_with_human_behavior = _human_behavior_module.watch_with_human_behavior
    start_video_with_audio_mute = _human_behavior_module.start_video_with_audio_mute
    click_suggested_video = _human_behavior_module.click_suggested_video
    ensure_video_playback = _human_behavior_module.ensure_video_playback
    handle_all_popups = _human_behavior_module.handle_all_popups
    attempt_video_playback_with_retry = _human_behavior_module.attempt_video_playback_with_retry
else:
    raise ImportError(f"Cannot find human_behavior module at {_human_behavior_path}")

# ========== Import search (from selenium/common) ==========
_search_path = SELENIUM_COMMON_ROOT / "search.py"
if _search_path.exists():
    _search_module = _load_module_from_file("search", _search_path)
    DesktopSearch = _search_module.DesktopSearch
    MobileSearch = _search_module.MobileSearch
else:
    raise ImportError(f"Cannot find search module at {_search_path}")

# ========== Import find (from selenium/common) ==========
_find_path = SELENIUM_COMMON_ROOT / "find.py"
if _find_path.exists():
    _find_module = _load_module_from_file("find", _find_path)
    find_and_click_video_result = _find_module.find_and_click_video_result
else:
    raise ImportError(f"Cannot find find module at {_find_path}")

# ========== Setup Logging ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTSearch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTSearch")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(log_filename, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

# Set loggers for imported modules
try:
    set_po_logger(logger)
except:
    pass
try:
    set_driver_logger(logger)
except:
    pass

logger.info(f"YTSearch.py started - PID: {os.getpid()}")
logger.info(f"Project root: {PROJECT_ROOT}")


# ========== Configuration ==========
@dataclass
class SessionConfig:
    instance_id: int
    url: str
    constructed_url: str
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
    po_token: str = None
    visitor_id: str = None
    po_token_source: str = "native"
    proxy: str = None
    proxy_mode: str = "none"
    num_instances: int = 1
    current_proxy: str = None
    cycle_number: int = 1


# ========== Inject PO token into video link on search page ==========
def inject_po_token_into_search_result(driver, instance_id, video_id, po_token, is_mobile):
    """
    Find the video result link and inject PO token into its href.
    Does NOT click - just prepares the link.
    """
    if not po_token:
        return False
    
    try:
        from selenium.webdriver.common.by import By
        
        # Find the video link using same logic as find.py
        video_link = None
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
            logger.warning(f"Instance {instance_id}: Could not find video link for PO injection")
            return False
        
        # Inject PO token into href
        original_href = video_link.get_attribute('href')
        if 'pot=' not in original_href:
            separator = '&' if '?' in original_href else '?'
            new_href = f"{original_href}{separator}pot={po_token}"
            driver.execute_script(f"arguments[0].setAttribute('href', '{new_href}');", video_link)
            logger.info(f"Instance {instance_id}: Injected PO token into video link")
            return True
        else:
            logger.info(f"Instance {instance_id}: PO token already present")
            return True
            
    except Exception as e:
        logger.error(f"Instance {instance_id}: PO injection error - {e}")
        return False


# ========== Session Runner ==========
def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        if cfg.proxy:
            logger.info(f"Instance {cfg.instance_id}: Using assigned proxy: {cfg.proxy[:80]}")
        
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_search_cache")
        
        search_query = cfg.video_title if cfg.video_title else cfg.video_id
        
        logger.info(f"Instance {cfg.instance_id}: Starting cycle {cfg.cycle_number}")
        # Do NOT log the search_query to avoid Unicode issues
        logger.info(f"Instance {cfg.instance_id}: Performing search...")
        
        # Perform search with video_id fallback
        if cfg.is_mobile:
            if not MobileSearch.perform_search(driver, cfg.instance_id, search_query, video_id=cfg.video_id):
                logger.error(f"Instance {cfg.instance_id}: Mobile search failed")
                return
        else:
            if not DesktopSearch.perform_search(driver, cfg.instance_id, search_query, video_id=cfg.video_id):
                logger.error(f"Instance {cfg.instance_id}: Desktop search failed")
                return

        # Wait for results to load
        logger.info(f"Instance {cfg.instance_id}: Waiting for search results...")
        time.sleep(3)
        
        # ========== INJECT PO TOKEN INTO SEARCH RESULT BEFORE CLICKING ==========
        # This ensures the token is in the URL when the video page loads
        if cfg.po_token:
            logger.info(f"Instance {cfg.instance_id}: Injecting PO token into video result link...")
            inject_success = inject_po_token_into_search_result(
                driver, cfg.instance_id, cfg.video_id, cfg.po_token, cfg.is_mobile
            )
            if inject_success:
                logger.info(f"Instance {cfg.instance_id}: PO token injected successfully")
            else:
                logger.warning(f"Instance {cfg.instance_id}: Failed to inject PO token, continuing anyway")
        else:
            logger.info(f"Instance {cfg.instance_id}: No PO token to inject")
        # ========== END OF PO TOKEN INJECTION ==========
        
        # Click the video result using find.py
        if not find_and_click_video_result(driver, cfg.instance_id, cfg.video_id, cfg.is_mobile):
            logger.error(f"Instance {cfg.instance_id}: Could not click video result")
            return

        wait_for_page_load(driver, 20)
        if is_login_page(driver):
            logger.warning(f"Instance {cfg.instance_id}: Login page, aborting")
            return

        handle_cookies(driver, cfg.instance_id)
        
        # Use retry function for playback (replaces ensure_video_playback + start_video_with_audio_mute)
        playback_success = attempt_video_playback_with_retry(
            driver, 
            cfg.instance_id, 
            cfg.is_mobile, 
            is_suggested=False,
            max_retries=3
        )
        
        if playback_success:
            watch_time = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching for {watch_time}s")
            watch_with_human_behavior(driver, watch_time, cfg.is_mobile)
        else:
            logger.warning(f"Instance {cfg.instance_id}: Playback failed after retries, skipping watch")

        if random.random() < cfg.suggested_chance:
            logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
            if click_suggested_video(driver, cfg.is_mobile):
                time.sleep(2)
                wait_for_page_load(driver, 20)
                handle_cookies(driver, cfg.instance_id)
                
                # Use retry function for suggested video
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
        
        logger.info(f"Instance {cfg.instance_id}: Completed cycle {cfg.cycle_number}")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error - {e}")
        if hasattr(cfg, 'current_proxy') and cfg.current_proxy:
            try:
                from common.proxy_manager import mark_proxy_failed
                mark_proxy_failed(cfg.current_proxy)
                logger.info(f"Instance {cfg.instance_id}: Marked proxy as failed")
            except:
                pass
        logger.error(traceback.format_exc())
    finally:
        logger.info(f"Instance {cfg.instance_id}: Cleaning up...")
        if driver:
            try:
                driver.quit()
                logger.info(f"Instance {cfg.instance_id}: Driver closed")
            except Exception as e:
                logger.warning(f"Instance {cfg.instance_id}: Error closing driver: {e}")
        if profile_dir and os.path.exists(profile_dir):
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
                logger.info(f"Instance {cfg.instance_id}: Profile deleted")
            except Exception as e:
                logger.warning(f"Instance {cfg.instance_id}: Could not delete profile: {e}")
        logger.info(f"Instance {cfg.instance_id}: Cleanup complete")
        

# ========== Main ==========
def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTSearch.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    logger.info(f"Loading config from: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    logger.info(f"Starting YTSearch with {len(instances)} parallel instance(s)")
    processes = []
    
    for d in instances:
        video_id = d.get("video_id", "")
        po_token = None
        visitor_id = None
        
        po_token_source = d.get("po_token_source", "native")
        set_po_token_source(po_token_source)
        
        if video_id:
            po_token, visitor_id = get_po_token(video_id, d.get("instance_id", 0))
            if po_token:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: PO token received (length: {len(po_token)})")
            else:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: No token, will use native")
        
        proxy_mode = d.get("proxy_mode", "none")
        num_instances = d.get("num_instances", 1)
        assigned_proxy = d.get("proxy", None)
        cycle_number = d.get("cycle_number", 1)
        
        if assigned_proxy:
            logger.info(f"Instance {d.get('instance_id', 0)}: Assigned proxy: {assigned_proxy[:80]}")
        
        cfg = SessionConfig(
            instance_id=d.get("instance_id", 0),
            url=d.get("url", ""),
            constructed_url=d.get("constructed_url", ""),
            video_id=video_id,
            video_title=d.get("video_title", ""),
            min_watch_time=d.get("min_watch_time", 15),
            max_watch_time=d.get("max_watch_time", 30),
            suggested_min=d.get("suggested_min", 15),
            suggested_max=d.get("suggested_max", 35),
            suggested_chance=d.get("suggested_chance", 0.4),
            headless=d.get("headless", False),
            user_agent=d.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            is_mobile=d.get("is_mobile", False),
            po_token=po_token,
            visitor_id=visitor_id,
            po_token_source=po_token_source,
            proxy=assigned_proxy,
            proxy_mode=proxy_mode,
            num_instances=num_instances,
            current_proxy=assigned_proxy,
            cycle_number=cycle_number
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        logger.info(f"Instance {cfg.instance_id} started in process {p.pid}")
        time.sleep(random.uniform(1, 3))
    
    for p in processes:
        p.join()
        logger.info(f"Process {p.pid} completed")
    
    logger.info("All parallel instances finished")


if __name__ == "__main__":
    main()