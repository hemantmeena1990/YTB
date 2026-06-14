#!/usr/bin/env python3
"""
YouTube Automation - DIRECT ENTRY MODE (Config-only) - Playwright Version
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
from enum import Enum

# ========== ABSOLUTE PATH SETUP ==========
_script_path = Path(__file__).resolve()
PROJECT_ROOT = _script_path.parent.parent.parent

# Define all important paths
COMMON_ROOT = PROJECT_ROOT / "common"
PLAYWRIGHT_COMMON_ROOT = PROJECT_ROOT / "playwright" / "common"

# Add to sys.path
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(COMMON_ROOT))
sys.path.insert(0, str(PLAYWRIGHT_COMMON_ROOT))

# ========== HELPER FUNCTION FOR DIRECT MODULE LOADING ==========
def _load_module_from_file(module_name, file_path):
    """Load a module directly from file path."""
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        raise ImportError(f"Failed to load {module_name} from {file_path}: {e}")

# ========== IMPORTS ==========

# PO Token (shared - no changes needed)
_po_token_path = COMMON_ROOT / "po_token.py"
_po_token_module = _load_module_from_file("po_token", _po_token_path)
get_po_token = _po_token_module.get_po_token
add_po_token_to_url = _po_token_module.add_po_token_to_url
set_po_logger = _po_token_module.set_logger
set_po_token_source = _po_token_module.set_po_token_source

# Playwright Human Behavior
_human_behavior_path = PLAYWRIGHT_COMMON_ROOT / "human_behavior.py"
_human_behavior_module = _load_module_from_file("human_behavior", _human_behavior_path)
watch_with_human_behavior = _human_behavior_module.watch_with_human_behavior
start_video_with_audio_mute = _human_behavior_module.start_video_with_audio_mute
click_suggested_video = _human_behavior_module.click_suggested_video
ensure_video_playback = _human_behavior_module.ensure_video_playback
handle_all_popups = _human_behavior_module.handle_all_popups
attempt_video_playback_with_retry = _human_behavior_module.attempt_video_playback_with_retry
is_video_playing = _human_behavior_module.is_video_playing
wait_for_url_change = _human_behavior_module.wait_for_url_change

# Playwright Human Click
_humanclick_path = PLAYWRIGHT_COMMON_ROOT / "humanclick.py"
_humanclick_module = _load_module_from_file("humanclick", _humanclick_path)
human_click = _humanclick_module.human_click

# Playwright Driver
_playwright_driver_path = PLAYWRIGHT_COMMON_ROOT / "po_driver.py"
_playwright_driver_module = _load_module_from_file("po_driver", _playwright_driver_path)
create_playwright_driver = _playwright_driver_module.create_playwright_driver

# Playwright Utils
_utils_path = PLAYWRIGHT_COMMON_ROOT / "utils.py"
_utils_module = _load_module_from_file("utils", _utils_path)
handle_cookies = _utils_module.handle_cookies
get_variable_watch_time = _utils_module.get_variable_watch_time
wait_for_page_load = _utils_module.wait_for_page_load
is_login_page = _utils_module.is_login_page
human_delay = _utils_module.human_delay
get_random_resolution = _utils_module.get_random_resolution

# ========== Setup Logging ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTDirect_Playwright_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTDirect_Playwright")
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

logger.info(f"YTDirect_Playwright.py started - PID: {os.getpid()}")
logger.info(f"Project root: {PROJECT_ROOT}")

# ========== Configuration ==========
class ViewType(Enum):
    DIRECT_UNKNOWN = 1
    SUGGESTED = 2
    OTHER_YOUTUBE = 3


@dataclass
class SessionConfig:
    instance_id: int
    urls: list
    view_type: ViewType
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


# ========== Session Runner ==========
def run_session(cfg: SessionConfig):
    page = None
    browser = None
    context = None
    
    try:
        if cfg.proxy:
            logger.info(f"Instance {cfg.instance_id}: Using assigned proxy: {cfg.proxy[:80]}")
        
        # Create Playwright driver (returns page, browser, context)
        page, browser, context = create_playwright_driver(cfg, "yt_direct_cache")
        
        logger.info(f"Instance {cfg.instance_id}: Starting cycle {cfg.cycle_number}")
        
        # Build watch URL with PO token
        watch_url = add_po_token_to_url(cfg.constructed_url, cfg.po_token)
        if cfg.po_token:
            logger.info(f"Instance {cfg.instance_id}: Added PO token to URL")
        
        # Navigate to video
        page.goto(watch_url)
        wait_for_page_load(page, 25)
        
        try:
            handle_all_popups(page, cfg.instance_id)
        except:
            pass
        
        handle_cookies(page, cfg.instance_id)
        
        # Attempt video playback with retry
        playback_success = attempt_video_playback_with_retry(
            page, 
            cfg.instance_id, 
            cfg.is_mobile, 
            is_suggested=False,
            max_retries=3
        )
        
        if playback_success:
            main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching main for {main_watch}s")
            watch_with_human_behavior(page, main_watch, cfg.is_mobile)
        else:
            logger.warning(f"Instance {cfg.instance_id}: Main video playback failed after retries, skipping")

        # Suggested video
        if random.random() < cfg.suggested_chance:
            logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
            if click_suggested_video(page, cfg.is_mobile):
                time.sleep(2)
                wait_for_page_load(page, 20)
                handle_all_popups(page, cfg.instance_id)
                handle_cookies(page, cfg.instance_id)
                
                suggested_playback = attempt_video_playback_with_retry(
                    page,
                    cfg.instance_id,
                    cfg.is_mobile,
                    is_suggested=True,
                    max_retries=2
                )
                
                if suggested_playback:
                    suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                    logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
                    watch_with_human_behavior(page, suggested_watch, cfg.is_mobile)
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
        if page:
            try:
                page.close()
                logger.info(f"Instance {cfg.instance_id}: Page closed")
            except Exception as e:
                logger.warning(f"Instance {cfg.instance_id}: Error closing page: {e}")
        if context:
            try:
                context.close()
                logger.info(f"Instance {cfg.instance_id}: Context closed")
            except Exception as e:
                logger.warning(f"Instance {cfg.instance_id}: Error closing context: {e}")
        if browser:
            try:
                browser.close()
                logger.info(f"Instance {cfg.instance_id}: Browser closed")
            except Exception as e:
                logger.warning(f"Instance {cfg.instance_id}: Error closing browser: {e}")
        
        # Clean up temp profile directory if created
        temp_dir = Path(f"/tmp/playwright_profile_{cfg.instance_id}_{cfg.cycle_number}")
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"Instance {cfg.instance_id}: Profile deleted")
            except:
                pass


# ========== Main ==========
def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTDirect_Playwright.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    logger.info(f"Loading config from: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    logger.info(f"Starting YTDirect_Playwright with {len(instances)} parallel instance(s)")
    processes = []
    
    for d in instances:
        vt_map = {
            "Other YouTube features": ViewType.OTHER_YOUTUBE,
            "Direct/Unknown": ViewType.DIRECT_UNKNOWN,
            "Suggested": ViewType.SUGGESTED
        }
        view_type = vt_map.get(d.get("view_type", ""), ViewType.DIRECT_UNKNOWN)
        
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
            urls=[d.get("url", "")],
            view_type=view_type,
            min_watch_time=d.get("min_watch_time", 15),
            max_watch_time=d.get("max_watch_time", 30),
            suggested_min=d.get("suggested_min", 15),
            suggested_max=d.get("suggested_max", 35),
            suggested_chance=d.get("suggested_chance", 0.4),
            headless=d.get("headless", False),
            user_agent=d.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            is_mobile=d.get("is_mobile", False),
            constructed_url=d.get("constructed_url", ""),
            video_id=video_id,
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