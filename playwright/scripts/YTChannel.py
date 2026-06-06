#!/usr/bin/env python3
"""
YouTube Automation - CHANNEL VIEW MODE (Playwright Version)
Searches for channel, clicks result, then searches within channel for video.
"""

import sys
import json
import os
import random
import time
import logging
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass

# Add paths for imports
CURRENT_DIR = Path(__file__).parent
PLAYWRIGHT_DIR = CURRENT_DIR.parent
PROJECT_ROOT = PLAYWRIGHT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PLAYWRIGHT_DIR))

# Import from playwright common
from common.utils import (
    get_random_user_agent, get_variable_watch_time, extract_video_id
)
from common.behavior import (
    watch_with_human_behavior, start_video_with_audio_mute, click_suggested_video,
    ensure_video_playback, handle_cookies
)
from common.search import DesktopSearch, MobileSearch
from common.find import find_and_click_channel_result, channel_internal_search

# Check Playwright availability
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("ERROR: playwright not installed! Run: pip install playwright && playwright install")
    sys.exit(1)

# Setup logging
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTChannel_Playwright_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTChannel_Playwright")
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
    channel_name: str
    min_watch_time: int
    max_watch_time: int
    suggested_min: int
    suggested_max: int
    suggested_chance: float
    headless: bool
    user_agent: str
    is_mobile: bool
    cycles: int
    proxy: str = None


# ========== STEALTH FUNCTIONS ==========

def apply_manual_stealth(page):
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {} };
        
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        if (navigator.connection) {
            Object.defineProperty(navigator, 'connection', { get: () => undefined });
        }
    """)


def try_apply_stealth(page, instance_id):
    try:
        import pw_stealth_enhanced
        if hasattr(pw_stealth_enhanced, 'stealth_sync'):
            pw_stealth_enhanced.stealth_sync(page)
        elif hasattr(pw_stealth_enhanced, 'stealth'):
            pw_stealth_enhanced.stealth(page)
        else:
            from pw_stealth_enhanced import stealth_sync
            stealth_sync(page)
        logger.info(f"Instance {instance_id}: Applied pw-stealth-enhanced")
        return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"pw-stealth-enhanced error: {e}")
    
    try:
        import playwright_stealth
        if hasattr(playwright_stealth, 'stealth_sync'):
            playwright_stealth.stealth_sync(page)
        elif hasattr(playwright_stealth, 'stealth'):
            playwright_stealth.stealth(page)
        else:
            from playwright_stealth import stealth_sync
            stealth_sync(page)
        logger.info(f"Instance {instance_id}: Applied playwright-stealth")
        return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"playwright-stealth error: {e}")
    
    logger.info(f"Instance {instance_id}: Using manual stealth patches")
    apply_manual_stealth(page)
    return True


# ========== BROWSER CREATION ==========

def create_browser_and_page(cfg: SessionConfig):
    playwright = sync_playwright().start()
    
    launch_opts = {
        'headless': cfg.headless,
        'args': [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-notifications',
            '--lang=en-US'
        ]
    }
    
    if cfg.proxy:
        launch_opts['proxy'] = {'server': cfg.proxy}
    
    browser = playwright.chromium.launch(**launch_opts)
    
    context_opts = {
        'user_agent': cfg.user_agent,
        'viewport': {'width': 390, 'height': 844} if cfg.is_mobile else {'width': 1366, 'height': 768},
        'locale': 'en-US',
        'timezone_id': 'Asia/Kolkata'
    }
    
    context = browser.new_context(**context_opts)
    page = context.new_page()
    
    try_apply_stealth(page, cfg.instance_id)
    
    return playwright, browser, context, page


# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    playwright = None
    browser = None
    context = None
    page = None
    
    try:
        playwright, browser, context, page = create_browser_and_page(cfg)
        
        # Step 1: Search for channel
        if cfg.is_mobile:
            if not MobileSearch.perform_search(page, cfg.channel_name):
                logger.error(f"Instance {cfg.instance_id}: Mobile search for channel failed")
                return
        else:
            if not DesktopSearch.perform_search(page, cfg.channel_name):
                logger.error(f"Instance {cfg.instance_id}: Desktop search for channel failed")
                return
        
        # Step 2: Click channel result
        if not find_and_click_channel_result(page, cfg.channel_name, cfg.instance_id):
            logger.error(f"Instance {cfg.instance_id}: Could not click channel result")
            return
        
        # Step 3: Inside channel, search for video ID
        if not channel_internal_search(page, cfg.video_id, cfg.instance_id):
            logger.error(f"Instance {cfg.instance_id}: Channel internal search failed")
            return
        
        # Play video with human behavior
        ensure_video_playback(page, cfg.instance_id)
        start_video_with_audio_mute(page, cfg.instance_id, cfg.is_mobile, is_suggested=False)
        
        main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
        logger.info(f"Instance {cfg.instance_id}: Watching main for {main_watch}s")
        watch_with_human_behavior(page, main_watch, cfg.is_mobile)
        
        # Suggested video
        if random.random() < cfg.suggested_chance:
            logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
            if click_suggested_video(page, cfg.is_mobile):
                time.sleep(2)
                handle_cookies(page, cfg.instance_id)
                start_video_with_audio_mute(page, cfg.instance_id, cfg.is_mobile, is_suggested=True)
                suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
                watch_with_human_behavior(page, suggested_watch, cfg.is_mobile)
            else:
                logger.warning(f"Instance {cfg.instance_id}: Could not load suggested video")
        
        logger.info(f"Instance {cfg.instance_id}: Session completed")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error - {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if page:
            page.close()
        if context:
            context.close()
        if browser:
            browser.close()
        if playwright:
            playwright.stop()


def main():
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available")
        sys.exit(1)
    
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTChannel.py <config.json>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        instances = json.load(f)
    
    logger.info(f"Starting YTChannel (Playwright) with {len(instances)} instance(s)")
    
    processes = []
    for d in instances:
        cfg = SessionConfig(
            instance_id=d["instance_id"],
            url=d["url"],
            constructed_url=d["constructed_url"],
            video_id=d["video_id"],
            video_title=d.get("video_title", ""),
            channel_name=d.get("channel_name", "rajasthanidesidiaries"),
            min_watch_time=d["min_watch_time"],
            max_watch_time=d["max_watch_time"],
            suggested_min=d["suggested_min"],
            suggested_max=d["suggested_max"],
            suggested_chance=d.get("suggested_chance", 0.4),
            headless=d["headless"],
            user_agent=d["user_agent"],
            is_mobile=d["is_mobile"],
            cycles=d.get("cycles", 1),
            proxy=d.get("proxy")
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