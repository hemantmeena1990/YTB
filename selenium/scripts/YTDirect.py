#!/usr/bin/env python3
"""
YouTube Direct Watch - WITH TRAFFIC SOURCE SUPPORT
Respects dashboard traffic source dropdown from YTDash.py
Uses direct YouTube watch URLs with referer header for traffic source.

INTEGRATED: Undetected ChromeDriver, cognitive delays, natural watch behavior
FLOW: Direct navigation to constructed URL (no homepage visit)
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
import re
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass

# ========== PATH SETUP ==========
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
set_po_logger = _po_token_module.set_logger
set_po_token_source = _po_token_module.set_po_token_source

# Human Behavior (with cognitive delays)
_human_behavior_path = COMMON_ROOT / "human_behavior.py"
_human_behavior_module = _load_module_from_file("human_behavior", _human_behavior_path)
watch_with_human_behavior = _human_behavior_module.watch_with_human_behavior
click_suggested_video = _human_behavior_module.click_suggested_video
attempt_video_playback_with_retry = _human_behavior_module.attempt_video_playback_with_retry
handle_all_popups = _human_behavior_module.handle_all_popups
is_video_playing = _human_behavior_module.is_video_playing
human_delay = _human_behavior_module.human_delay
cognitive_delay = _human_behavior_module.cognitive_delay

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
is_login_page = _utils_module.is_login_page

# ========== LOGGING ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTDirect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTDirect")
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

logger.info(f"YTDirect.py started - PID: {os.getpid()}")
logger.info(f"Project root: {PROJECT_ROOT}")


# ========== CONFIGURATION ==========
@dataclass
class SessionConfig:
    instance_id: int
    url: str
    video_id: str
    video_title: str
    traffic_source: str
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
    referer: str = None
    automation_version: str = "selenium"
    use_undetected: bool = False
    view_type: str = "Direct/Unknown"
    # ========== FINGERPRINT FIELDS ==========
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
    # ==========================================


# ========== DIRECT WATCH (Original Flow - Direct Navigation) ==========

def watch_direct(driver, cfg: SessionConfig):
    """
    Watch video directly using YouTube watch URL.
    DIRECT NAVIGATION - NO HOMEPAGE VISIT.
    """
    try:
        # Build watch URL with PO token if available
        watch_url = f"https://www.youtube.com/watch?v={cfg.video_id}"
        if cfg.po_token:
            separator = '&' if '?' in watch_url else '?'
            watch_url = f"{watch_url}{separator}pot={cfg.po_token}"
        
        logger.info(f"Instance {cfg.instance_id}: ========== DIRECT WATCH ==========")
        logger.info(f"Instance {cfg.instance_id}: View Type: {cfg.view_type if hasattr(cfg, 'view_type') else 'Direct/Unknown'}")
        logger.info(f"Instance {cfg.instance_id}: Traffic Source: {cfg.traffic_source}")
        logger.info(f"Instance {cfg.instance_id}: Referer: {cfg.referer if cfg.referer else 'None'}")
        logger.info(f"Instance {cfg.instance_id}: Watch URL: {watch_url[:150]}...")
        logger.info(f"Instance {cfg.instance_id}: PO Token Present: {cfg.po_token is not None}")
        logger.info(f"Instance {cfg.instance_id}: ====================================")
        
        # ========== DIRECT NAVIGATION (NO HOMEPAGE) ==========
        driver.get(watch_url)
        wait_for_page_load(driver, 20)
        cognitive_delay("read")
        
        # ========== VIEW TYPE SPECIFIC BEHAVIOR ==========
        # For "Other YouTube features", add extra natural behavior
        if hasattr(cfg, 'view_type') and cfg.view_type == "Other YouTube features":
            # Extra cognitive pause (as if checking if this is the right video)
            cognitive_delay("process")
            # Small natural scroll (as if looking around the page)
            from common.human_behavior import random_scroll
            random_scroll(driver, cfg.is_mobile)
            cognitive_delay("read")
        # ===================================================
        
        # Handle popups
        handle_all_popups(driver, cfg.instance_id)
        handle_cookies(driver, cfg.instance_id)
        
        # Check playback
        playback_success = is_video_playing(driver)
        if not playback_success:
            logger.warning(f"Instance {cfg.instance_id}: Video not playing, retrying...")
            playback_success = attempt_video_playback_with_retry(
                driver, cfg.instance_id, cfg.is_mobile, is_suggested=False, max_retries=3
            )
        
        if playback_success:
            cognitive_delay("process")
            watch_time = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching for {watch_time}s")
            watch_with_human_behavior(driver, watch_time, cfg.is_mobile)
            return True
        else:
            logger.warning(f"Instance {cfg.instance_id}: Playback failed")
            return False
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error in watch_direct: {e}")
        logger.error(traceback.format_exc())
        return False
        

def watch_suggested_direct(driver, cfg: SessionConfig):
    """Watch suggested video with enhanced natural behavior."""
    try:
        # ========== ENHANCED NATURAL BEHAVIOR ==========
        # 1. Natural decision pause
        cognitive_delay("decide")
        
        # 2. Light scroll through suggestions (natural browsing)
        for _ in range(random.randint(1, 2)):
            from common.human_behavior import random_scroll
            random_scroll(driver, cfg.is_mobile)
            cognitive_delay("scroll")
        
        # 3. Click suggested with natural behavior (pass instance_id)
        if not click_suggested_video(driver, cfg.is_mobile, cfg.instance_id):
            logger.warning(f"Instance {cfg.instance_id}: Could not click suggested")
            return False
        
        # 4. Natural navigation delay
        cognitive_delay("navigate")
        wait_for_page_load(driver, 15)
        
        # Get current URL and video ID
        current_url = driver.current_url
        match = re.search(r'(?:v=|/v/|/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})', current_url)
        if not match:
            logger.warning(f"Instance {cfg.instance_id}: Could not extract suggested ID")
            return False
        
        suggested_id = match.group(1)
        logger.info(f"Instance {cfg.instance_id}: Suggested video ID: {suggested_id}")
        
        # Navigate with token and referer (already set in driver)
        suggested_url = f"https://www.youtube.com/watch?v={suggested_id}"
        if cfg.po_token:
            separator = '&' if '?' in suggested_url else '?'
            suggested_url = f"{suggested_url}{separator}pot={cfg.po_token}"
        
        driver.get(suggested_url)
        wait_for_page_load(driver, 15)
        cognitive_delay("read")
        
        handle_all_popups(driver, cfg.instance_id)
        handle_cookies(driver, cfg.instance_id)
        
        playback_success = attempt_video_playback_with_retry(
            driver, cfg.instance_id, cfg.is_mobile, is_suggested=True, max_retries=2
        )
        if playback_success:
            cognitive_delay("process")
            suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
            logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
            watch_with_human_behavior(driver, suggested_watch, cfg.is_mobile)
        
        return playback_success
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error in watch_suggested_direct: {e}")
        return False
        

# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    
    try:
        logger.info(f"Instance {cfg.instance_id}: ========== Starting YTDirect Session ==========")
        logger.info(f"Instance {cfg.instance_id}: Video ID: {cfg.video_id}")
        logger.info(f"Instance {cfg.instance_id}: Traffic Source: {cfg.traffic_source}")
        logger.info(f"Instance {cfg.instance_id}: Referer: {cfg.referer if cfg.referer else 'None'}")
        logger.info(f"Instance {cfg.instance_id}: PO Token Source: {cfg.po_token_source}")
        logger.info(f"Instance {cfg.instance_id}: Proxy: {cfg.proxy if cfg.proxy else 'none'}")
        logger.info(f"Instance {cfg.instance_id}: Cycles: {cfg.cycles}")
        
        # Create driver (referer is set in po_driver)
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_direct_cache")
        
        
        # ========== DEBUG: Check actual window size ==========
        try:
            actual_width = driver.execute_script("return window.innerWidth")
            actual_height = driver.execute_script("return window.innerHeight")
            logger.info(f"Instance {cfg.instance_id}: 🔍 Actual viewport: {actual_width}x{actual_height}")
            logger.info(f"Instance {cfg.instance_id}: 🔍 Expected viewport: {cfg.viewport_width}x{cfg.viewport_height}")
            if actual_width != cfg.viewport_width or actual_height != cfg.viewport_height:
                logger.warning(f"Instance {cfg.instance_id}: ⚠️ Viewport mismatch! Expected {cfg.viewport_width}x{cfg.viewport_height}, got {actual_width}x{actual_height}")
        except Exception as e:
            logger.warning(f"Instance {cfg.instance_id}: Could not get viewport: {e}")
        # =====================================================
        
        
        # Human-like delay after driver creation
        cognitive_delay("process")
        
        cycles_done = 0
        total_cycles = cfg.cycles
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: --- Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'} ---")
            
            watch_success = watch_direct(driver, cfg)
            if not watch_success:
                logger.warning(f"Instance {cfg.instance_id}: Main video watch had issues")
            
            if random.random() < cfg.suggested_chance:
                logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
                watch_suggested_direct(driver, cfg)
            
            cycles_done += 1
            if total_cycles == 0 or cycles_done < total_cycles:
                pause = random.uniform(8, 20)  # Slightly longer for natural feel
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause:.1f}s between cycles")
                time.sleep(pause)
        
        logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycles")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Session error: {e}")
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
        logger.error("Usage: python YTDirect.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    logger.info(f"Loading config from: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    logger.info(f"Starting YTDirect with {len(instances)} instance(s)")
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
        
        traffic_source = d.get("traffic_source", "direct")
        logger.info(f"[TRAFFIC] Instance {d.get('instance_id', 0)}: {traffic_source}")
        
        cfg = SessionConfig(
            instance_id=d.get("instance_id", 0),
            url=d.get("url", ""),
            video_id=video_id,
            video_title=d.get("video_title", video_id),
            traffic_source=traffic_source,
            min_watch_time=d.get("min_watch_time", 30),
            max_watch_time=d.get("max_watch_time", 180),
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
            proxy=d.get("proxy", None),
            proxy_mode=d.get("proxy_mode", "none"),
            num_instances=d.get("num_instances", 1),
            current_proxy=d.get("proxy", None),
            cycle_number=d.get("cycle_number", 1),
            referer=d.get("referer", None),
            automation_version=d.get("automation_version", "selenium"),
            use_undetected=d.get("use_undetected", False),
            view_type=d.get("view_type", "Direct/Unknown"),
            # ========== READ FINGERPRINT FIELDS ==========
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
            fingerprint_type=d.get("fingerprint_type", "desktop")
            # ==========================================
            )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        logger.info(f"Instance {cfg.instance_id} started in process {p.pid}")
        time.sleep(random.uniform(1, 3))
    
    for p in processes:
        p.join()
        logger.info(f"Process {p.pid} completed")
    
    logger.info("All YTDirect sessions finished")


if __name__ == "__main__":
    main()