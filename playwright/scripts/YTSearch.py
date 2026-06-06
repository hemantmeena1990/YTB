#!/usr/bin/env python3
"""
YouTube Automation - SEARCH MODE for Regular Videos (Playwright Version)
Correct Path: project/playwright/scripts/YTSearch.py
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

# 1. Resolve Strict Absolute Directory Pathing relative to this file
SCRIPT_FILE_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SCRIPT_FILE_PATH.parent         # project/playwright/scripts
PLAYWRIGHT_DIR = SCRIPTS_DIR.parent           # project/playwright
PROJECT_ROOT = PLAYWRIGHT_DIR.parent          # project (Main Workspace Root)

# 2. Add BOTH Project Root and Playwright Dir to sys.path to ensure absolute fallback mapping
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PLAYWRIGHT_DIR) not in sys.path:
    sys.path.insert(0, str(PLAYWRIGHT_DIR))

# 3. Dynamic Package Resolution Layer (Tries both system route styles to guarantee zero crash)
try:
    # Try via explicit package layout path
    from playwright.common.utils import get_random_user_agent, get_variable_watch_time, extract_video_id
    from playwright.common.behavior import (
        watch_with_human_behavior, start_video_with_audio_mute, click_suggested_video,
        ensure_video_playback, handle_cookies
    )
    from playwright.common.search import DesktopSearch, MobileSearch
    from playwright.common.find import find_and_click_video_result
    print("SUCCESS: Modules bound via standard package routing.")
except ModuleNotFoundError:
    try:
        # Fallback in case internal environment prefers direct directory mapping
        from common.utils import get_random_user_agent, get_variable_watch_time, extract_video_id
        from common.behavior import (
            watch_with_human_behavior, start_video_with_audio_mute, click_suggested_video,
            ensure_video_playback, handle_cookies
        )
        from common.search import DesktopSearch, MobileSearch
        from common.find import find_and_click_video_result
        print("SUCCESS: Modules bound via directory path mappings fallback.")
    except ModuleNotFoundError as e:
        print(f"\nCRITICAL STRUCTURAL FAULT: Lookups failed for common modules.")
        print(f"Path Checked: {PLAYWRIGHT_DIR / 'common'}")
        print(f"Detailed Internal Exception: {e}\n")
        sys.exit(1)

# Check Playwright Framework Setup
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("ERROR: playwright module not found. Run: pip install playwright && playwright install")
    sys.exit(1)

# Configure Safe Data Logging paths
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTSearch_Playwright_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTSearch_Playwright")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fh = logging.FileHandler(log_filename, encoding='utf-8')
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
    proxy: str = None


# ========== STEALTH HANDLING SYSTEM ==========

def apply_manual_stealth(page):
    """Core manual JavaScript overrides framework layer."""
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {} };
    """)

def try_apply_stealth(page, instance_id):
    """Hooks safe third-party anti-fingerprint bypass arrays before routing execution."""
    try:
        import pw_stealth_enhanced
        if hasattr(pw_stealth_enhanced, 'stealth_sync'):
            pw_stealth_enhanced.stealth_sync(page)
            logger.info(f"Instance {instance_id}: Active stealth engine -> pw-stealth-enhanced")
            return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"pw-stealth-enhanced hook tracing fault: {e}")
    
    try:
        import playwright_stealth
        if hasattr(playwright_stealth, 'stealth_sync'):
            playwright_stealth.stealth_sync(page)
            logger.info(f"Instance {instance_id}: Active stealth engine -> playwright-stealth")
            return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"playwright-stealth hook tracing fault: {e}")
    
    logger.info(f"Instance {instance_id}: Active stealth engine -> core manual overrides scripts")
    apply_manual_stealth(page)
    return True


# ========== CORE INSTANCE OPERATIONAL BLOCK ==========

def create_browser_and_page(cfg: SessionConfig):
    """Spawns an isolated target browser worker window context with tracking bypass maps."""
    playwright = sync_playwright().start()
    
    launch_opts = {
        'headless': cfg.headless,
        'args': [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
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
    
    # Critical Execution Order Fix: Inject structural patches into DOM before navigation hits
    try_apply_stealth(page, cfg.instance_id)
    
    return playwright, browser, context, page


def run_session(cfg: SessionConfig):
    """The individual automation worker execution tracking wrapper loop."""
    playwright = None
    browser = None
    context = None
    page = None
    
    try:
        playwright, browser, context, page = create_browser_and_page(cfg)
        search_query = cfg.video_title.strip()
        if not search_query:
            logger.error(
                f"Instance {cfg.instance_id}: video_title is required for search mode"
            )
            return
        logger.info(f"Instance {cfg.instance_id}: Processing query target -> {search_query[:45]}...")
        
        # Instantiate engine instances cleanly to handle non-static class definitions safely
        if cfg.is_mobile:
            search_engine = MobileSearch()
            if not search_engine.perform_search(page, search_query):
                logger.error(f"Instance {cfg.instance_id}: Mobile layout parser search execution hit faults.")
                return
        else:
            search_engine = DesktopSearch()
            if not search_engine.perform_search(page, search_query):
                logger.error(f"Instance {cfg.instance_id}: Desktop layout parser search execution hit faults.")
                return
        
        # Search page click target execution block
        if not find_and_click_video_result(page, cfg.video_id, cfg.instance_id):
            logger.error(f"Instance {cfg.instance_id}: Target Video ID selector missing from results container arrays.")
            return
        
        try:
            page.wait_for_load_state('networkidle', timeout=8000)
        except:
            pass
            
        time.sleep(2)
        handle_cookies(page, cfg.instance_id)
        
        # Initialize media content parameters
        start_video_with_audio_mute(page, cfg.instance_id, cfg.is_mobile, is_suggested=False)
        
        # Watch timer calculations
        main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
        logger.info(f"Instance {cfg.instance_id}: Monitoring video view actions simulation for {main_watch}s.")
        watch_with_human_behavior(page, main_watch, cfg.is_mobile)
        
        # Recommendation flow algorithms loops
        if random.random() < cfg.suggested_chance:
            logger.info(f"Instance {cfg.instance_id}: Related navigation loop activated.")
            if click_suggested_video(page, cfg.is_mobile):
                time.sleep(2)
                handle_cookies(page, cfg.instance_id)
                start_video_with_audio_mute(page, cfg.instance_id, cfg.is_mobile, is_suggested=True)
                suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                logger.info(f"Instance {cfg.instance_id}: Processing related recommendations view loop for {suggested_watch}s.")
                watch_with_human_behavior(page, suggested_watch, cfg.is_mobile)
            else:
                logger.warning(f"Instance {cfg.instance_id}: Related link selection component coordinate tracking failed.")
        
        logger.info(f"Instance {cfg.instance_id}: Process cycle finalized cleanly.")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Pipeline Functional Crash - {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Graceful asset tear-down layer
        if page:
            try: page.close()
            except: pass
        if context:
            try: context.close()
            except: pass
        if browser:
            try: browser.close()
            except: pass
        if playwright:
            try: playwright.stop()
            except: pass


def main():
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Core component tracking driver failed binding validation steps.")
        sys.exit(1)
        
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Operational Command Mismatch. Usage Format: python YTSearch.py <your_config_file.json>")
        sys.exit(1)
        
    with open(sys.argv[1], 'r') as f:
        instances = json.load(f)
        
    logger.info(f"Spawning Subprocess Instances Worker Threads. Total Threads Active: {len(instances)}")
    
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
            is_mobile=d["is_mobile"],
            proxy=d.get("proxy")
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        # Stagger delay window to prevent parallel proxy authentication conflicts
        time.sleep(random.uniform(2.5, 4.5))
        
    for p in processes:
        p.join()
        
    logger.info("Operational framework threads clean exit routine executed successfully.")


if __name__ == "__main__":
    main()