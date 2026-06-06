#!/usr/bin/env python3
"""
YouTube Shorts Automation - Short Feeds (Config-only)
First attempts natural swipe (mouse drag), then falls back to keyboard arrows.
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
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

from common.utils import (
    get_random_resolution, handle_cookies, wait_for_page_load,
    is_video_playing
)
from common.human_behavior import ensure_video_playback
from common.shortinteract import delayed_mute

# Setup logging
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTShort_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTShort")
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


# ========== HELPER FUNCTIONS ==========

def get_current_video_id(driver) -> str:
    """Extract video ID from current URL."""
    import re
    current_url = driver.current_url
    patterns = [
        r'shorts/([a-zA-Z0-9_-]{11})',
        r'watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, current_url)
        if match:
            return match.group(1)
    return ""


# ========== NATURAL SWIPE (Mouse Drag) ==========

def natural_swipe_up(driver, instance_id, attempt):
    """
    Perform natural swipe up using mouse drag.
    Each attempt swipes longer than previous.
    """
    try:
        # Get viewport dimensions
        viewport = driver.execute_script("""
            return {
                width: window.innerWidth,
                height: window.innerHeight
            };
        """)
        
        # Calculate swipe distance - longer on each attempt
        # Attempt 1: 70% of screen height
        # Attempt 2: 85% of screen height
        # Attempt 3: 100% of screen height
        swipe_percentage = [0.7, 0.85, 1.0][attempt - 1]
        swipe_distance = int(viewport['height'] * swipe_percentage)
        
        # Start from center of screen
        start_x = int(viewport['width'] / 2)
        start_y = int(viewport['height'] / 2)
        end_y = start_y - swipe_distance  # Swipe UP (decrease Y)
        
        logger.info(f"Instance {instance_id}: Natural swipe UP attempt {attempt} - distance: {swipe_distance}px")
        
        # Perform drag and drop (mouse swipe)
        action = ActionChains(driver)
        action.move_to_element_with_offset(driver.find_element(By.TAG_NAME, "body"), start_x, start_y)
        action.click_and_hold()
        action.move_by_offset(0, -swipe_distance)
        action.release()
        action.perform()
        
        time.sleep(1)  # Wait for animation
        return True
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Natural swipe UP failed - {e}")
        return False


def natural_swipe_down(driver, instance_id, attempt):
    """
    Perform natural swipe down using mouse drag.
    Each attempt swipes longer than previous.
    """
    try:
        # Get viewport dimensions
        viewport = driver.execute_script("""
            return {
                width: window.innerWidth,
                height: window.innerHeight
            };
        """)
        
        # Calculate swipe distance - longer on each attempt
        swipe_percentage = [0.7, 0.85, 1.0][attempt - 1]
        swipe_distance = int(viewport['height'] * swipe_percentage)
        
        # Start from center of screen
        start_x = int(viewport['width'] / 2)
        start_y = int(viewport['height'] / 2)
        end_y = start_y + swipe_distance  # Swipe DOWN (increase Y)
        
        logger.info(f"Instance {instance_id}: Natural swipe DOWN attempt {attempt} - distance: {swipe_distance}px")
        
        # Perform drag and drop (mouse swipe)
        action = ActionChains(driver)
        action.move_to_element_with_offset(driver.find_element(By.TAG_NAME, "body"), start_x, start_y)
        action.click_and_hold()
        action.move_by_offset(0, swipe_distance)
        action.release()
        action.perform()
        
        time.sleep(1)  # Wait for animation
        return True
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Natural swipe DOWN failed - {e}")
        return False


# ========== KEYBOARD FALLBACK ==========

def keyboard_arrow_down(driver, instance_id):
    """Fallback: Press DOWN arrow key."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ARROW_DOWN)
        logger.info(f"Instance {instance_id}: Keyboard DOWN arrow (fallback)")
        time.sleep(0.8)
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Keyboard DOWN failed - {e}")
        return False


def keyboard_arrow_up(driver, instance_id):
    """Fallback: Press UP arrow key."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ARROW_UP)
        logger.info(f"Instance {instance_id}: Keyboard UP arrow (fallback)")
        time.sleep(0.8)
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Keyboard UP failed - {e}")
        return False


# ========== SWIPE WITH PROGRESSIVE ATTEMPTS ==========

def swipe_up_with_fallback(driver, instance_id, original_video_id):
    """
    Try natural swipe 3 times (each longer), then fallback to keyboard.
    Returns True if URL changed, False otherwise.
    """
    old_url = driver.current_url
    
    # Try natural swipe up to 3 times (each attempt longer)
    for attempt in range(1, 4):
        logger.info(f"Instance {instance_id}: Natural swipe UP attempt {attempt}/3")
        
        if natural_swipe_up(driver, instance_id, attempt):
            time.sleep(1.5)  # Wait for navigation
            new_url = driver.current_url
            if new_url != old_url:
                new_video_id = get_current_video_id(driver)
                logger.info(f"Instance {instance_id}: Natural swipe succeeded! New video: {new_video_id}")
                return True
        
        # Small delay between attempts
        time.sleep(0.5)
    
    # Fallback to keyboard arrow
    logger.info(f"Instance {instance_id}: Natural swipe failed, using keyboard fallback")
    if keyboard_arrow_down(driver, instance_id):
        time.sleep(1)
        new_url = driver.current_url
        if new_url != old_url:
            new_video_id = get_current_video_id(driver)
            logger.info(f"Instance {instance_id}: Keyboard fallback succeeded! New video: {new_video_id}")
            return True
    
    logger.error(f"Instance {instance_id}: All swipe methods failed")
    return False


def swipe_down_with_fallback(driver, instance_id, target_video_id):
    """
    Try natural swipe down 3 times (each longer), then fallback to keyboard.
    Returns True if returned to target, False otherwise.
    """
    old_url = driver.current_url
    
    # Try natural swipe down up to 3 times (each attempt longer)
    for attempt in range(1, 4):
        logger.info(f"Instance {instance_id}: Natural swipe DOWN attempt {attempt}/3")
        
        if natural_swipe_down(driver, instance_id, attempt):
            time.sleep(1.5)
            new_video_id = get_current_video_id(driver)
            if new_video_id == target_video_id:
                logger.info(f"Instance {instance_id}: Natural swipe down succeeded! Returned to original")
                return True
        
        time.sleep(0.5)
    
    # Fallback to keyboard arrow
    logger.info(f"Instance {instance_id}: Natural swipe failed, using keyboard fallback")
    if keyboard_arrow_up(driver, instance_id):
        time.sleep(1)
        new_video_id = get_current_video_id(driver)
        if new_video_id == target_video_id:
            logger.info(f"Instance {instance_id}: Keyboard fallback succeeded! Returned to original")
            return True
    
    logger.error(f"Instance {instance_id}: All swipe down methods failed")
    return False


def explore_shorts(driver, instance_id, explore_count, original_video_id):
    """
    Explore multiple shorts by swiping up.
    Returns number of successfully explored shorts.
    """
    explored = 0
    current_video_id = original_video_id
    
    for i in range(explore_count):
        logger.info(f"Instance {instance_id}: Exploring Short {i + 1}/{explore_count}")
        
        if swipe_up_with_fallback(driver, instance_id, current_video_id):
            explored += 1
            current_video_id = get_current_video_id(driver)
        else:
            logger.warning(f"Instance {instance_id}: Failed to explore Short {i + 1}, stopping")
            break
        
        time.sleep(random.uniform(0.3, 0.6))
    
    return explored


def return_to_original(driver, instance_id, original_video_id, explore_count):
    """
    Swipe down to return to original Short.
    """
    logger.info(f"Instance {instance_id}: Returning to original Short")
    
    for i in range(explore_count):
        logger.info(f"Instance {instance_id}: Return attempt {i + 1}/{explore_count}")
        
        if swipe_down_with_fallback(driver, instance_id, original_video_id):
            return True
        
        time.sleep(0.5)
    
    # If all fails, try direct navigation as last resort
    logger.warning(f"Instance {instance_id}: Could not swipe back, navigating directly")
    driver.get(f"https://www.youtube.com/shorts/{original_video_id}")
    time.sleep(2)
    return True


# ========== VIDEO PLAYBACK WITH UNMUTE ==========

def start_video_with_unmute(driver, instance_id, is_mobile=False):
    """Start video and ensure it's unmuted (especially important for mobile)."""
    try:
        # Ensure video is playing
        ensure_video_playback(driver, instance_id)
        
        # For mobile: click on video first (creates user gesture for unmute)
        if is_mobile:
            try:
                video = driver.find_element(By.TAG_NAME, "video")
                video.click()
                logger.info(f"Instance {instance_id}: Clicked on video for mobile gesture")
                time.sleep(0.3)
            except:
                pass
        
        # Check if video is muted and unmute if necessary
        is_muted = driver.execute_script("""
            var v = document.querySelector('video');
            return v ? v.muted : false;
        """)
        
        if is_muted:
            logger.info(f"Instance {instance_id}: Video was muted, unmuting now")
            driver.execute_script("document.querySelector('video').muted = false;")
            time.sleep(0.3)
        
        # Set random volume
        initial_volume = random.uniform(0.3, 0.8)
        driver.execute_script(f"""
            var v = document.querySelector('video');
            if (v) v.volume = {initial_volume};
        """)
        logger.info(f"Instance {instance_id}: Volume set to {int(initial_volume*100)}%")
        
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Video start error - {e}")
        return False


# ========== DRIVER CREATION ==========

def create_driver(cfg: SessionConfig):
    """Create Chrome driver with fresh profile."""
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
        if cfg.is_mobile:
            opts.add_argument("--window-size=390,844")
        else:
            w, h = get_random_resolution(cfg.is_mobile)
            opts.add_argument(f"--window-size={w},{h}")
    else:
        opts.add_argument("--window-size=1920,1080")
    
    timestamp = int(time.time())
    profile_dir = os.path.join(os.getcwd(), f"yt_shorts_cache_{cfg.instance_id}_{timestamp}")
    opts.add_argument(f"--user-data-dir={profile_dir}")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(30)
    return driver, profile_dir


# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    """Main session execution for Short Feeds."""
    driver = None
    profile_dir = None
    
    try:
        driver, profile_dir = create_driver(cfg)
        
        logger.info(f"Instance {cfg.instance_id}: Loading Shorts URL: {cfg.constructed_url}")
        driver.get(cfg.constructed_url)
        wait_for_page_load(driver, 15)
        handle_cookies(driver, cfg.instance_id)
        
        # Get original video ID for verification
        original_video_id = get_current_video_id(driver)
        logger.info(f"Instance {cfg.instance_id}: Original video ID: {original_video_id}")
        
        # Start video with unmute
        start_video_with_unmute(driver, cfg.instance_id, cfg.is_mobile)
        
        # Apply delayed mute
        delayed_mute(driver, delay_range=(0, 4), volume_range=(0.3, 0.8))
        
        cycles_done = 0
        
        while cfg.cycles == 0 or cycles_done < cfg.cycles:
            logger.info(f"Instance {cfg.instance_id}: {'='*50}")
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{cfg.cycles if cfg.cycles > 0 else '∞'}")
            logger.info(f"Instance {cfg.instance_id}: {'='*50}")
            
            # Step 1: Watch original Short
            original_watch = random.randint(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching original Short for {original_watch}s")
            time.sleep(original_watch)
            
            # Step 2: Random explore count (2-4 shorts)
            explore_count = random.randint(2, 4)
            logger.info(f"Instance {cfg.instance_id}: Will explore {explore_count} Shorts")
            
            # Step 3: Explore shorts with progressive swipe attempts
            explored = explore_shorts(driver, cfg.instance_id, explore_count, original_video_id)
            logger.info(f"Instance {cfg.instance_id}: Successfully explored {explored} Shorts")
            
            # Step 4: Watch each explored Short
            for i in range(explored):
                explore_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
                logger.info(f"Instance {cfg.instance_id}: Watching explored Short {i+1} for {explore_watch}s")
                ensure_video_playback(driver, cfg.instance_id)
                time.sleep(explore_watch)
            
            # Step 5: Return to original Short
            return_to_original(driver, cfg.instance_id, original_video_id, explored)
            
            # Step 6: Watch original Short again
            return_watch = random.randint(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching original Short again for {return_watch}s")
            ensure_video_playback(driver, cfg.instance_id)
            time.sleep(return_watch)
            
            cycles_done += 1
            
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
        if driver:
            driver.quit()
        if profile_dir and os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)


# ========== MAIN ==========

def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTShort.py <config.json>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        instances = json.load(f)
    
    logger.info(f"Starting YTShort with {len(instances)} instance(s)")
    processes = []
    
    for d in instances:
        cfg = SessionConfig(
            instance_id=d["instance_id"],
            url=d.get("url", ""),
            constructed_url=d.get("constructed_url", ""),
            video_id=d.get("video_id", ""),
            headless=d["headless"],
            user_agent=d["user_agent"],
            is_mobile=d["is_mobile"],
            cycles=d.get("cycles", 1),
            min_watch_time=d["min_watch_time"],
            max_watch_time=d["max_watch_time"],
            suggested_min=d.get("suggested_min", 3),
            suggested_max=d.get("suggested_max", 8)
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