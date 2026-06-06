#!/usr/bin/env python3
"""
YouTube Automation - DIRECT ENTRY MODE (Playwright Version)
View Types: Direct/Unknown, Other YouTube features, Suggested
Uses pw-stealth-enhanced with playwright-stealth fallback for anti-detection.
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

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.input import extract_video_id
from common.utils import get_random_user_agent, get_variable_watch_time

# Import Playwright
try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("ERROR: playwright not installed! Run: pip install playwright && playwright install")
    sys.exit(1)

# Import stealth modules
STEALTH_AVAILABLE = False
try:
    from pw_stealth_enhanced import stealth_sync
    STEALTH_METHOD = "pw_stealth_enhanced"
    STEALTH_AVAILABLE = True
    print("Using pw-stealth-enhanced for anti-detection")
except ImportError:
    try:
        from playwright_stealth import stealth_sync
        STEALTH_METHOD = "playwright_stealth"
        STEALTH_AVAILABLE = True
        print("Using playwright-stealth for anti-detection (fallback)")
    except ImportError:
        STEALTH_AVAILABLE = False
        print("WARNING: No stealth module installed. Proceeding without stealth patches.")

# Setup logging
DATA_DIR = Path(__file__).parent.parent / "data"
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


# ========== HUMAN BEHAVIOR FUNCTIONS (Playwright Native) ==========

def random_scroll(page: Page, is_mobile: bool = False):
    """Perform random scroll using mouse wheel."""
    amount = random.randint(100, 500) if is_mobile else random.randint(80, 400)
    page.mouse.wheel(0, amount)
    time.sleep(random.uniform(0.2, 0.6))


def random_key_press(page: Page):
    """Simulate random key presses (desktop only)."""
    if random.random() < 0.12:
        keys = ['ArrowDown', 'ArrowUp', 'Space', 'PageDown', 'PageUp']
        key = random.choice(keys)
        page.keyboard.press(key)
        time.sleep(random.uniform(0.05, 0.15))
        if key == 'Space' and random.random() < 0.4:
            time.sleep(random.uniform(0.3, 0.8))
            page.keyboard.press('Space')


def random_mouse_movement(page: Page):
    """Move mouse to random position."""
    if random.random() < 0.3:
        try:
            viewport = page.viewport_size
            if viewport:
                x = random.randint(50, viewport['width'] - 50)
                y = random.randint(50, viewport['height'] - 50)
                page.mouse.move(x, y)
                time.sleep(random.uniform(0.1, 0.3))
        except:
            pass


def watch_with_human_behavior(page: Page, duration: int, is_mobile: bool = False):
    """
    Watch video for given duration while performing random human-like actions.
    """
    start = time.time()
    next_action = random.randint(5, 15)
    paused = False
    
    while time.time() - start < duration:
        remaining = duration - (time.time() - start)
        if remaining < next_action:
            time.sleep(remaining)
            break
        
        time.sleep(next_action)
        r = random.random()
        
        if r < 0.4:
            random_scroll(page, is_mobile)
        elif r < 0.7:
            random_mouse_movement(page)
        else:
            random_key_press(page)
        
        # Simulate pause (like user getting distracted)
        if not paused and random.random() < 0.06 and duration > 30:
            try:
                page.keyboard.press('Space')
                time.sleep(random.uniform(4, 10))
                page.keyboard.press('Space')
                paused = True
                logger.info("Simulated user pause")
            except:
                pass
        
        next_action = random.expovariate(0.12) + random.uniform(2, 8)
        next_action = min(max(next_action, 4), 20)


# ========== VIDEO PLAYBACK FUNCTIONS ==========

def is_video_playing(page: Page) -> bool:
    """Check if video element is currently playing."""
    try:
        result = page.evaluate("""
            () => {
                const v = document.querySelector('video');
                return v && !v.paused && !v.ended && v.readyState >= 2;
            }
        """)
        return result
    except:
        return False


def ensure_video_playback(page: Page, instance_id: int) -> bool:
    """Ensure video is playing (spacebar, click, JavaScript)."""
    if is_video_playing(page):
        return True
    
    logger.warning(f"Instance {instance_id}: Video not playing. Attempting start...")
    
    # Try spacebar
    page.keyboard.press('Space')
    time.sleep(1)
    if is_video_playing(page):
        logger.info(f"Instance {instance_id}: Started with SPACEBAR")
        return True
    
    # Try clicking on video
    try:
        video = page.query_selector('video')
        if video:
            video.click()
            time.sleep(1)
            if is_video_playing(page):
                logger.info(f"Instance {instance_id}: Started with CLICK")
                return True
    except:
        pass
    
    # JavaScript fallback
    try:
        page.evaluate("document.querySelector('video')?.play();")
        time.sleep(1)
        if is_video_playing(page):
            logger.info(f"Instance {instance_id}: Started with JavaScript")
            return True
    except:
        pass
    
    logger.error(f"Instance {instance_id}: Failed to start video")
    return False


def start_video_with_audio_mute(page: Page, instance_id: int, is_mobile: bool = False, is_suggested: bool = False):
    """
    Set random volume, start video, unmute if needed, then mute after random delay.
    """
    try:
        mute_delay = random.choice([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        initial_volume = random.uniform(0.3, 0.8)
        logger.info(f"Instance {instance_id} {'(suggested)' if is_suggested else ''}: Volume {int(initial_volume*100)}%, mute in {mute_delay}s")
        
        # Ensure video is playing
        ensure_video_playback(page, instance_id)
        
        # For mobile: click on video to create user gesture
        if is_mobile:
            try:
                video = page.query_selector('video')
                if video:
                    video.click()
                    time.sleep(0.3)
            except:
                pass
        
        # Check and unmute if muted
        is_muted = page.evaluate("document.querySelector('video')?.muted || false")
        if is_muted:
            logger.info(f"Instance {instance_id}: Video was muted, unmuting now")
            page.evaluate("document.querySelector('video').muted = false;")
            time.sleep(0.2)
        
        # Set volume
        page.evaluate(f"document.querySelector('video').volume = {initial_volume};")
        
        # Schedule mute after delay
        if mute_delay > 0:
            time.sleep(mute_delay)
            page.evaluate("document.querySelector('video').muted = true;")
        
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Video start error - {e}")
        return False


# ========== SUGGESTED VIDEO CLICK ==========

def click_suggested_video(page: Page, is_mobile: bool = False) -> bool:
    """
    Click a suggested video from sidebar (desktop) or after scrolling (mobile).
    Playwright's auto-wait makes this much simpler.
    """
    try:
        current_url = page.url
        
        if is_mobile:
            # Scroll to load suggestions
            for _ in range(3):
                page.mouse.wheel(0, 500)
                time.sleep(0.5)
            
            # Find suggested video links
            suggested = page.query_selector_all('ytm-compact-video-renderer a, a[href*="/watch?v="]')
        else:
            # Scroll sidebar
            page.mouse.wheel(0, 300)
            time.sleep(0.5)
            
            # Desktop sidebar suggestions
            suggested = page.query_selector_all('#secondary a[href*="/watch?v="]')
        
        if not suggested:
            logger.warning("No suggested video links found")
            return False
        
        # Pick a random suggestion (skip first if too many)
        idx = random.randint(0, min(len(suggested) - 1, 5))
        link = suggested[idx]
        
        # Scroll into view and click
        link.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.3, 0.8))
        
        old_url = page.url
        link.click()
        
        # Wait for navigation
        for _ in range(12):
            time.sleep(0.5)
            if page.url != old_url:
                logger.info("Suggested video navigation succeeded")
                return True
        
        logger.warning("Suggested video clicked but URL did not change")
        return False
        
    except Exception as e:
        logger.error(f"Error clicking suggested video: {e}")
        return False


# ========== COOKIE HANDLING ==========

def handle_cookies(page: Page, instance_id: int) -> bool:
    """Accept cookie consent if present."""
    try:
        accept_buttons = page.query_selector_all('button:has-text("Accept"), button:has-text("Accept all"), button:has-text("I agree"), button:has-text("Got it")')
        for btn in accept_buttons:
            if btn.is_visible():
                btn.click()
                time.sleep(0.5)
                logger.info(f"Instance {instance_id}: Accepted cookies")
                return True
    except:
        pass
    return False


# ========== BROWSER CREATION WITH STEALTH ==========

def create_browser_and_page(cfg: SessionConfig):
    """
    Create Playwright browser with stealth patches.
    Tries pw-stealth-enhanced first, then playwright-stealth as fallback.
    """
    playwright = sync_playwright().start()
    
    # Launch options
    launch_options = {
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
    
    # Add proxy if configured
    if cfg.proxy:
        launch_options['proxy'] = {'server': cfg.proxy}
    
    browser = playwright.chromium.launch(**launch_options)
    
    # Context options
    context_options = {
        'user_agent': cfg.user_agent,
        'viewport': {'width': 390, 'height': 844} if cfg.is_mobile else {'width': 1366, 'height': 768},
        'locale': 'en-US',
        'timezone_id': 'America/New_York',
    }
    
    context = browser.new_context(**context_options)
    page = context.new_page()
    
    # Apply stealth patches
    if STEALTH_AVAILABLE:
        try:
            stealth_sync(page)
            logger.info(f"Instance {cfg.instance_id}: Applied stealth patches ({STEALTH_METHOD})")
        except Exception as e:
            logger.warning(f"Instance {cfg.instance_id}: Stealth patch failed: {e}")
    
    return playwright, browser, context, page


# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    """Main session execution for DIRECT mode."""
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
        
        # Start video
        start_video_with_audio_mute(page, cfg.instance_id, cfg.is_mobile, is_suggested=False)
        
        # Main watch
        main_watch = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
        logger.info(f"Instance {cfg.instance_id}: Watching main for {main_watch}s")
        watch_with_human_behavior(page, main_watch, cfg.is_mobile)
        
        # Suggested video (for ALL view types)
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


# ========== MAIN ==========

def main():
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright is not installed. Run: pip install playwright && playwright install")
        sys.exit(1)
    
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTDirect.py <config.json>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        instances = json.load(f)
    
    logger.info(f"Starting YTDirect with {len(instances)} instance(s)")
    logger.info(f"Stealth method: {STEALTH_METHOD if STEALTH_AVAILABLE else 'None'}")
    
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