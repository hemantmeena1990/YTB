#!/usr/bin/env python3
"""
YouTube Automation - DIRECT ENTRY MODE (Config-only)
With PO token support using shared modules
"""

import sys
import os
import json
import random
import shutil
import time
import logging
import importlib.util
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass
from enum import Enum

# ========== Setup Paths ==========
PROJECT_ROOT = Path(__file__).parent.parent.parent
SELENIUM_ROOT = Path(__file__).parent.parent
COMMON_ROOT = PROJECT_ROOT / "common"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SELENIUM_ROOT))

# ========== Import po_token with fallback ==========
try:
    from common.po_token import get_po_token, add_po_token_to_url, set_logger as set_po_logger, set_po_token_source
except ImportError:
    spec = importlib.util.spec_from_file_location("po_token", COMMON_ROOT / "po_token.py")
    po_token_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(po_token_module)
    get_po_token = po_token_module.get_po_token
    add_po_token_to_url = po_token_module.add_po_token_to_url
    set_po_logger = po_token_module.set_logger
    set_po_token_source = po_token_module.set_po_token_source

# ========== Import po_driver with fallback ==========
try:
    from common.po_driver import create_driver_with_po_token, set_logger as set_driver_logger
except ImportError:
    spec = importlib.util.spec_from_file_location("po_driver", SELENIUM_ROOT / "common" / "po_driver.py")
    po_driver_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(po_driver_module)
    create_driver_with_po_token = po_driver_module.create_driver_with_po_token
    set_driver_logger = po_driver_module.set_logger

# ========== Regular Imports ==========
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from common.utils import (
    handle_cookies, get_variable_watch_time, wait_for_page_load
)
from common.human_behavior import (
    watch_with_human_behavior, start_video_with_audio_mute, click_suggested_video,
    ensure_video_playback
)

# ========== Setup Logging ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTDirect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTDirect")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(log_filename)
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

set_po_logger(logger)
set_driver_logger(logger)


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
    cycles: int = 1
    proxy: str = None 


# ========== Session Runner ==========
def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    cycles_done = 0
    total_cycles = cfg.cycles
    
    try:
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_direct_cache")
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'}")
            
            watch_url = add_po_token_to_url(cfg.constructed_url, cfg.po_token)
            if cfg.po_token and cycles_done == 0:
                logger.info(f"Instance {cfg.instance_id}: Added PO token to URL")
            
            driver.get(watch_url)
            wait_for_page_load(driver, 25)
            handle_cookies(driver, cfg.instance_id)

            start_video_with_audio_mute(driver, cfg.instance_id, cfg.is_mobile, is_suggested=False)

            main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching main for {main_watch}s")
            watch_with_human_behavior(driver, main_watch, cfg.is_mobile)

            if random.random() < cfg.suggested_chance:
                logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
                if click_suggested_video(driver, cfg.is_mobile):
                    time.sleep(2)
                    wait_for_page_load(driver, 20)
                    handle_cookies(driver, cfg.instance_id)
                    start_video_with_audio_mute(driver, cfg.instance_id, cfg.is_mobile, is_suggested=True)
                    suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                    logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
                    watch_with_human_behavior(driver, suggested_watch, cfg.is_mobile)
                else:
                    logger.warning(f"Instance {cfg.instance_id}: Could not load suggested video")
            
            cycles_done += 1
            
            if total_cycles == 0 or cycles_done < total_cycles:
                pause_duration = random.uniform(5, 15)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause_duration:.1f}s before next cycle")
                time.sleep(pause_duration)
                driver.delete_all_cookies()

        logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycle(s)")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error - {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if driver:
            driver.quit()
        if profile_dir and os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)


# ========== Main ==========
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
        vt_map = {
            "Other YouTube features": ViewType.OTHER_YOUTUBE,
            "Direct/Unknown": ViewType.DIRECT_UNKNOWN,
            "Suggested": ViewType.SUGGESTED
        }
        view_type = vt_map.get(d.get("view_type", ""), ViewType.DIRECT_UNKNOWN)
        
        video_id = d.get("video_id", "")
        po_token = None
        visitor_id = None
        
        # CRITICAL: Set the PO token source FIRST before fetching token
        po_token_source = d.get("po_token_source", "native")
        set_po_token_source(po_token_source)
        logger.info(f"Instance {d.get('instance_id', 0)}: PO Token Source set to: {po_token_source}")
        
        # NOW fetch the PO token using the configured source
        if video_id:
            po_token, visitor_id = get_po_token(video_id, d.get("instance_id", 0))
            if po_token:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: PO token received successfully (length: {len(po_token)})")
            else:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: No token from external source, will use native")
        
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
            cycles=d.get("cycles", 1),
            proxy=d.get("proxy", None)
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        time.sleep(random.uniform(1, 3))
    
    for p in processes:
        p.join()
    
    logger.info("All sessions finished")


if __name__ == "__main__":
    main()