#!/usr/bin/env python3
"""
YouTube Automation - DIRECT ENTRY MODE (Playwright Version)
View Types: Direct/Unknown, Other YouTube features, Suggested
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
from enum import Enum
from typing import Optional

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

# Check Playwright availability
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("ERROR: playwright not installed! Run: pip install playwright && playwright install")
    sys.exit(1)

# Setup logging - CORRECT PATH (project root level)
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTDirect_Playwright_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTDirect_Playwright")
logger.setLevel(logging.INFO)
# File handler
fh = logging.FileHandler(log_filename, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
# Console handler
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

# Also log to console that logging is set up
logger.info(f"Log file: {log_filename}")


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
    proxy: Optional[str] = None


# ========== MANUAL STEALTH PATCHES ==========

def apply_manual_stealth(page):
    """Apply manual stealth patches (works without external modules)."""
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
    """Try to apply stealth using available modules, fallback to manual."""
    # Try pw_stealth_enhanced
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
    
    # Try playwright-stealth
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
    
    # Manual fallback
    logger.info(f"Instance {instance_id}: Using manual stealth patches")
    apply_manual_stealth(page)
    return True


# ========== BROWSER CREATION ==========

def create_browser_and_page(cfg: SessionConfig):
    """Create Playwright browser with stealth patches."""
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
    
    # Apply stealth
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
        
        # Main video
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
        logger.error("Usage: python YTDirect.py <config.json>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        instances = json.load(f)
    
    logger.info(f"Starting YTDirect (Playwright) with {len(instances)} instance(s)")
    
    processes = []
    for d in instances:
        vt_map = {
            "Other YouTube features": ViewType.OTHER_YOUTUBE,
            "Direct/Unknown": ViewType.DIRECT_UNKNOWN,
            "Suggested": ViewType.SUGGESTED
        }
        view_type = vt_map.get(d["view_type"], ViewType.DIRECT_UNKNOWN)
        
        cfg = SessionConfig(
            instance_id=d["instance_id"],
            urls=[d["url"]],
            view_type=view_type,
            min_watch_time=d["min_watch_time"],
            max_watch_time=d["max_watch_time"],
            suggested_min=d["suggested_min"],
            suggested_max=d["suggested_max"],
            suggested_chance=d.get("suggested_chance", 0.4),
            headless=d["headless"],
            user_agent=d["user_agent"],
            is_mobile=d["is_mobile"],
            constructed_url=d["constructed_url"],
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