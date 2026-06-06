#!/usr/bin/env python3
"""
YouTube Shorts Automation - Short Feeds (Playwright Version)
Swipe up to explore Shorts, watch, return, repeat.
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
    ensure_video_playback, handle_cookies
)
from common.shortinteract import (
    swipe_up, swipe_down, delayed_mute, watch_with_exploration
)

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
log_filename = LOG_DIR / f"YTShort_Playwright_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTShort_Playwright")
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
    headless: bool
    user_agent: str
    is_mobile: bool
    cycles: int
    min_watch_time: int
    max_watch_time: int
    suggested_min: int
    suggested_max: int
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
        
        logger.info(f"Instance {cfg.instance_id}: Navigating to {cfg.constructed_url}")
        page.goto(cfg.constructed_url, wait_until='domcontentloaded')
        time.sleep(2)
        
        handle_cookies(page, cfg.instance_id)
        
        # Ensure video is playing
        ensure_video_playback(page, cfg.instance_id)
        
        # Setup audio (volume then mute after delay)
        delayed_mute(page, delay_range=(0, 4), volume_range=(0.3, 0.8))
        
        cycles_done = 0
        
        while cfg.cycles == 0 or cycles_done < cfg.cycles:
            logger.info(f"Instance {cfg.instance_id}: {'='*50}")
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{cfg.cycles if cfg.cycles > 0 else 'infinite'}")
            logger.info(f"Instance {cfg.instance_id}: {'='*50}")
            
            # Watch with exploration (full cycle)
            total_time = watch_with_exploration(
                page,
                orig_watch=(cfg.min_watch_time, cfg.max_watch_time),
                explore_watch=(cfg.suggested_min, cfg.suggested_max),
                explore_count=random.randint(2, 4),
                return_watch=(cfg.min_watch_time, cfg.max_watch_time)
            )
            
            cycles_done += 1
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done} completed - Total {total_time:.1f}s")
            
            # Pause between cycles
            if cfg.cycles == 0 or cycles_done < cfg.cycles:
                pause = random.uniform(5, 12)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause:.1f}s before next cycle")
                time.sleep(pause)
        
        logger.info(f"Instance {cfg.instance_id}: Session completed after {cycles_done} cycles")
        
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
        logger.error("Usage: python YTShort.py <config.json>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        instances = json.load(f)
    
    logger.info(f"Starting YTShort (Playwright) with {len(instances)} instance(s)")
    
    processes = []
    for d in instances:
        cfg = SessionConfig(
            instance_id=d["instance_id"],
            url=d["url"],
            constructed_url=d["constructed_url"],
            video_id=d["video_id"],
            headless=d["headless"],
            user_agent=d["user_agent"],
            is_mobile=d["is_mobile"],
            cycles=d.get("cycles", 1),
            min_watch_time=d["min_watch_time"],
            max_watch_time=d["max_watch_time"],
            suggested_min=d.get("suggested_min", 3),
            suggested_max=d.get("suggested_max", 8),
            proxy=d.get("proxy")
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        time.sleep(random.uniform(1, 2))
    
    for p in processes:
        p.join()
    
    logger.info("All sessions finished")


if __name__ == "__main__":
    main()