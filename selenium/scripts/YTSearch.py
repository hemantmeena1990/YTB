#!/usr/bin/env python3
"""
YouTube Automation - SEARCH MODE for Regular Videos (Refactored)
Uses common.search for performing search, and common.find for clicking results.
"""

import sys
import json
import os
import random
import shutil
import time
import logging
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from common.utils import (
    get_random_resolution, handle_cookies, get_variable_watch_time, wait_for_page_load,
    human_delay, is_login_page
)
from common.human_behavior import (
    watch_with_human_behavior, start_video_with_audio_mute, click_suggested_video,
    ensure_video_playback
)
from common.search import DesktopSearch, MobileSearch
from common.find import find_and_click_video_result  # only needed if channel internal used, but YTSearch only needs video result

# Setup logging
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTSearch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTSearch")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(log_filename)
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

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

def create_driver(cfg: SessionConfig):
    opts = Options()
    if cfg.headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--lang=en-US")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument(f"user-agent={cfg.user_agent}")
    if not cfg.headless:
        w, h = get_random_resolution(cfg.is_mobile)
        opts.add_argument(f"--window-size={w},{h}")
    else:
        opts.add_argument("--window-size=1920,1080")
    timestamp = int(time.time())
    profile_dir = os.path.join(os.getcwd(), f"yt_search_cache_{cfg.instance_id}_{timestamp}")
    opts.add_argument(f"--user-data-dir={profile_dir}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver, profile_dir

def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        driver, profile_dir = create_driver(cfg)
        search_query = cfg.video_title if cfg.video_title else cfg.video_id

        # Perform the search (without clicking result)
        if cfg.is_mobile:
            if not MobileSearch.perform_search(driver, cfg.instance_id, search_query):
                logger.error(f"Instance {cfg.instance_id}: Mobile search failed")
                return
        else:
            if not DesktopSearch.perform_search(driver, cfg.instance_id, search_query):
                logger.error(f"Instance {cfg.instance_id}: Desktop search failed")
                return

        # Now find and click the video result
        if not find_and_click_video_result(driver, cfg.instance_id, cfg.video_id, cfg.is_mobile):
            logger.error(f"Instance {cfg.instance_id}: Could not click video result")
            return

        wait_for_page_load(driver, 20)
        if is_login_page(driver):
            logger.warning(f"Instance {cfg.instance_id}: Login page, aborting")
            return

        handle_cookies(driver, cfg.instance_id)
        ensure_video_playback(driver, cfg.instance_id)
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
                ensure_video_playback(driver, cfg.instance_id)
                start_video_with_audio_mute(driver, cfg.instance_id, cfg.is_mobile, is_suggested=True)
                suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
                watch_with_human_behavior(driver, suggested_watch, cfg.is_mobile)
            else:
                logger.warning(f"Instance {cfg.instance_id}: Could not load suggested video")

        logger.info(f"Instance {cfg.instance_id}: Session completed")
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error - {e}")
    finally:
        if driver:
            driver.quit()
        if profile_dir and os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)

def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTSearch.py <config.json>")
        sys.exit(1)
    with open(sys.argv[1], 'r') as f:
        instances = json.load(f)

    logger.info(f"Starting YTSearch with {len(instances)} instance(s)")
    processes = []
    for d in instances:
        cfg = SessionConfig(
            instance_id=d["instance_id"],
            url=d["url"],
            constructed_url=d["constructed_url"],
            video_id=d["video_id"],
            video_title=d.get("video_title", ""),
            min_watch_time=d["min_watch_time"],
            max_watch_time=d["max_watch_time"],
            suggested_min=d["suggested_min"],
            suggested_max=d["suggested_max"],
            suggested_chance=d.get("suggested_chance", 0.4),
            headless=d["headless"],
            user_agent=d["user_agent"],
            is_mobile=d["is_mobile"]
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