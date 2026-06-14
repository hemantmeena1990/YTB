#!/usr/bin/env python3
"""
YouTube Shorts Automation - With mouse wheel navigation, URL verification, fallback to keys.
Uses human_behavior functions for playback, mute/unmute, watching, wheel.
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
add_po_token_to_url = _po_token_module.add_po_token_to_url
set_po_logger = _po_token_module.set_logger
set_po_token_source = _po_token_module.set_po_token_source

# Human Behavior (includes playback, popups, wheel)
_human_behavior_path = COMMON_ROOT / "human_behavior.py"
_human_behavior_module = _load_module_from_file("human_behavior", _human_behavior_path)
watch_with_human_behavior = _human_behavior_module.watch_with_human_behavior
start_video_with_audio_mute = _human_behavior_module.start_video_with_audio_mute
click_suggested_video = _human_behavior_module.click_suggested_video
ensure_video_playback = _human_behavior_module.ensure_video_playback
handle_all_popups = _human_behavior_module.handle_all_popups
simulate_mouse_wheel = _human_behavior_module.simulate_mouse_wheel
attempt_video_playback_with_retry = _human_behavior_module.attempt_video_playback_with_retry
navigate_shorts_with_fallback = _human_behavior_module.navigate_shorts_with_fallback


# PO Driver
_po_driver_path = SELENIUM_COMMON_ROOT / "po_driver.py"
_po_driver_module = _load_module_from_file("po_driver", _po_driver_path)
create_driver_with_po_token = _po_driver_module.create_driver_with_po_token
set_driver_logger = _po_driver_module.set_logger

# Utils (wait_for_url_change is here)
_utils_path = SELENIUM_COMMON_ROOT / "utils.py"
_utils_module = _load_module_from_file("utils", _utils_path)
handle_cookies = _utils_module.handle_cookies
get_variable_watch_time = _utils_module.get_variable_watch_time
wait_for_page_load = _utils_module.wait_for_page_load
wait_for_url_change = _utils_module.wait_for_url_change   # imported from utils, not human_behavior

# ========== LOGGING ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTShort_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTShort")
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

logger.info(f"YTShort.py started - PID: {os.getpid()}")
logger.info(f"Project root: {PROJECT_ROOT}")

# ========== CONFIGURATION ==========
@dataclass
class SessionConfig:
    instance_id: int
    urls: list
    min_watch_time: int
    max_watch_time: int
    suggested_min: int
    suggested_max: int
    suggested_chance: float
    headless: bool
    user_agent: str
    is_mobile: bool
    constructed_url: str
    video_id: str = ""
    po_token: str = None
    visitor_id: str = None
    po_token_source: str = "native"
    proxy: str = None
    proxy_mode: str = "none"
    num_instances: int = 1
    current_proxy: str = None
    cycle_number: int = 1
    shorts_max_total: int = 3

# ========== NAVIGATION HELPERS ==========
def get_current_url(driver):
    return driver.current_url

def navigate_next_short(driver, cfg: SessionConfig):
    """Navigate to next short using fallback chain (wheel → button → arrow)"""
    success = navigate_shorts_with_fallback(driver, direction='next', max_attempts=3)
    if success:
        logger.info(f"Instance {cfg.instance_id}: Navigated to next short")
    else:
        logger.warning(f"Instance {cfg.instance_id}: Failed to navigate to next short")
    return success


def navigate_prev_short(driver, cfg: SessionConfig):
    """Navigate to previous short using fallback chain (wheel → button → arrow)"""
    success = navigate_shorts_with_fallback(driver, direction='prev', max_attempts=3)
    if success:
        logger.info(f"Instance {cfg.instance_id}: Navigated to previous short")
    else:
        logger.warning(f"Instance {cfg.instance_id}: Failed to navigate to previous short")
    return success
    

# ========== WATCH SHORTS WITH RETURN LOGIC ==========
def watch_short_with_behavior(driver, cfg: SessionConfig, is_original=True):
    """Watch a single short with retry logic"""
    success = attempt_video_playback_with_retry(
        driver, 
        cfg.instance_id, 
        cfg.is_mobile, 
        is_suggested=not is_original,
        max_retries=3
    )
    
    if success:
        watch_time = random.randint(cfg.min_watch_time, cfg.max_watch_time)
        logger.info(f"Instance {cfg.instance_id}: Watching {'original' if is_original else 'additional'} short for {watch_time}s")
        watch_with_human_behavior(driver, watch_time, cfg.is_mobile)
        return True
    else:
        logger.warning(f"Instance {cfg.instance_id}: Playback failed for {'original' if is_original else 'additional'} short, skipping")
        return False

def watch_shorts_feed(driver, cfg: SessionConfig):
    try:
        # Load original short with PO token
        start_url = cfg.constructed_url if cfg.constructed_url else "https://www.youtube.com/shorts"
        if cfg.po_token:
            watch_url = add_po_token_to_url(start_url, cfg.po_token)
            logger.info(f"Instance {cfg.instance_id}: Added PO token to URL")
        else:
            watch_url = start_url
        logger.info(f"Instance {cfg.instance_id}: Navigating to {watch_url}")
        driver.get(watch_url)
        wait_for_page_load(driver, 20)
        handle_all_popups(driver, cfg.instance_id)
        handle_cookies(driver, cfg.instance_id)
        time.sleep(2)

        # Watch original
        watch_short_with_behavior(driver, cfg, is_original=True)

        # Determine how many additional shorts (0-2)
        max_additional = min(cfg.shorts_max_total - 1, 2)
        additional_count = random.randint(0, max_additional) if max_additional >= 0 else 0
        logger.info(f"Instance {cfg.instance_id}: Will watch {additional_count} additional short(s)")

        # Watch additional shorts
        for i in range(additional_count):
            logger.info(f"Instance {cfg.instance_id}: Moving to next short (additional {i+1}/{additional_count})")
            if not navigate_next_short(driver, cfg):
                logger.warning(f"Instance {cfg.instance_id}: Failed to navigate, stopping additional")
                break
            handle_all_popups(driver, cfg.instance_id)
            handle_cookies(driver, cfg.instance_id)
            ensure_video_playback(driver, cfg.instance_id)
            watch_short_with_behavior(driver, cfg, is_original=False)

            # Early return chance
            if i < additional_count - 1 and random.random() < 0.3:
                logger.info(f"Instance {cfg.instance_id}: Returning to original early")
                navigate_prev_short(driver, cfg)
                short_watch = random.randint(5, 12)
                watch_with_human_behavior(driver, short_watch, cfg.is_mobile)
                break

        # Optional final return to original
        if additional_count > 0 and random.random() < 0.5:
            logger.info(f"Instance {cfg.instance_id}: Returning to original at end")
            for _ in range(additional_count):
                navigate_prev_short(driver, cfg)
            short_watch = random.randint(5, 12)
            watch_with_human_behavior(driver, short_watch, cfg.is_mobile)

        return True
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error in watch_shorts_feed: {e}")
        logger.error(traceback.format_exc())
        return False

# ========== SESSION RUNNER ==========
def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        if cfg.proxy:
            logger.info(f"Instance {cfg.instance_id}: Using proxy: {cfg.proxy[:80]}")
        else:
            logger.info(f"Instance {cfg.instance_id}: Direct connection")

        driver, profile_dir = create_driver_with_po_token(cfg, "yt_shorts_cache")
        logger.info(f"Instance {cfg.instance_id}: Starting cycle {cfg.cycle_number}")
        success = watch_shorts_feed(driver, cfg)
        if not success:
            logger.warning(f"Instance {cfg.instance_id}: Shorts session incomplete")
        logger.info(f"Instance {cfg.instance_id}: Completed cycle {cfg.cycle_number}")
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error - {e}")
        if cfg.current_proxy:
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

# ========== MAIN ==========
def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTShort.py <config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    logger.info(f"Loading config from: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    logger.info(f"Starting YTShort with {len(instances)} parallel instance(s)")
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
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: PO token received")
            else:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: No token")

        assigned_proxy = d.get("proxy", None)
        cycle_number = d.get("cycle_number", 1)
        constructed_url = d.get("constructed_url", "")
        if not constructed_url and video_id:
            constructed_url = f"https://www.youtube.com/shorts/{video_id}"
        elif not constructed_url:
            constructed_url = "https://www.youtube.com/shorts"

        shorts_max_total = d.get("shorts_max_count", 3)
        shorts_max_total = max(1, min(shorts_max_total, 3))

        cfg = SessionConfig(
            instance_id=d.get("instance_id", 0),
            urls=[d.get("url", "")],
            min_watch_time=d.get("min_watch_time", 10),
            max_watch_time=d.get("max_watch_time", 25),
            suggested_min=d.get("suggested_min", 15),
            suggested_max=d.get("suggested_max", 35),
            suggested_chance=d.get("suggested_chance", 0.0),
            headless=d.get("headless", False),
            user_agent=d.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            is_mobile=d.get("is_mobile", False),
            constructed_url=constructed_url,
            video_id=video_id,
            po_token=po_token,
            visitor_id=visitor_id,
            po_token_source=po_token_source,
            proxy=assigned_proxy,
            proxy_mode=d.get("proxy_mode", "none"),
            num_instances=d.get("num_instances", 1),
            current_proxy=assigned_proxy,
            cycle_number=cycle_number,
            shorts_max_total=shorts_max_total
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