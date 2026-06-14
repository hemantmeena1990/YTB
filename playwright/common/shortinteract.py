# playwright/common/shortinteract.py
"""
Playwright Shorts interaction functions - pure Playwright, no Selenium.
Only custom logic for Shorts feed navigation and interaction.
"""

import time
import random
import logging
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


def get_current_short_url(page: Page) -> str:
    """Get current short URL from page"""
    return page.url


def wait_for_short_load(page: Page, timeout: int = 10) -> bool:
    """Wait for short to load by checking video element"""
    try:
        page.wait_for_selector("video", timeout=timeout * 1000)
        time.sleep(1)
        return True
    except:
        return False


def is_short_playing(page: Page) -> bool:
    """Check if short video is playing"""
    try:
        return page.evaluate("""
            const v = document.querySelector('video');
            return v && !v.paused && v.currentTime > 0 && !v.ended;
        """)
    except:
        return False


def scroll_to_next_short(page: Page) -> bool:
    """Scroll to next short using mouse wheel (Playwright built-in)"""
    try:
        # Scroll down one full viewport
        page.mouse.wheel(0, random.randint(600, 900))
        time.sleep(random.uniform(1.5, 3))
        return True
    except Exception as e:
        logger.debug(f"Scroll to next short failed: {e}")
        return False


def scroll_to_previous_short(page: Page) -> bool:
    """Scroll to previous short using mouse wheel"""
    try:
        page.mouse.wheel(0, random.randint(-900, -600))
        time.sleep(random.uniform(1.5, 3))
        return True
    except Exception as e:
        logger.debug(f"Scroll to previous short failed: {e}")
        return False


def scroll_with_hesitation(page: Page, direction: str = 'down') -> bool:
    """Scroll with hesitation (pause mid-scroll) for human-like behavior"""
    try:
        if direction == 'down':
            # First scroll (hesitation)
            page.mouse.wheel(0, random.randint(200, 400))
            time.sleep(random.uniform(0.2, 0.5))
            # Complete the scroll
            page.mouse.wheel(0, random.randint(400, 600))
        else:
            page.mouse.wheel(0, random.randint(-500, -300))
            time.sleep(random.uniform(0.2, 0.5))
            page.mouse.wheel(0, random.randint(-400, -200))
        
        time.sleep(random.uniform(1, 2))
        return True
    except Exception as e:
        logger.debug(f"Scroll with hesitation failed: {e}")
        return False


def find_next_short_button(page: Page):
    """Find the 'Next video' button in Shorts player"""
    selectors = [
        "button[aria-label='Next video']",
        "button[aria-label='Next']",
        "div[aria-label='Next video']",
        ".yt-spec-touch-feedback-shape-fill"
    ]
    
    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.count() > 0 and element.is_visible():
                return element
        except:
            continue
    return None


def find_previous_short_button(page: Page):
    """Find the 'Previous video' button in Shorts player"""
    selectors = [
        "button[aria-label='Previous video']",
        "button[aria-label='Previous']",
        "div[aria-label='Previous video']",
    ]
    
    for selector in selectors:
        try:
            element = page.locator(selector).first
            if element.count() > 0 and element.is_visible():
                return element
        except:
            continue
    return None


def click_next_short_button(page: Page, instance_id: int) -> bool:
    """Click the next short navigation button"""
    button = find_next_short_button(page)
    if button:
        try:
            button.click()
            time.sleep(random.uniform(1, 2))
            logger.info(f"Instance {instance_id}: Clicked next short button")
            return True
        except Exception as e:
            logger.debug(f"Failed to click next button: {e}")
    return False


def click_previous_short_button(page: Page, instance_id: int) -> bool:
    """Click the previous short navigation button"""
    button = find_previous_short_button(page)
    if button:
        try:
            button.click()
            time.sleep(random.uniform(1, 2))
            logger.info(f"Instance {instance_id}: Clicked previous short button")
            return True
        except Exception as e:
            logger.debug(f"Failed to click previous button: {e}")
    return False


def navigate_short_with_fallback(page: Page, instance_id: int, direction: str = 'next', max_attempts: int = 3) -> bool:
    """
    Navigate shorts using fallback chain:
    1. Mouse wheel
    2. Navigation button click
    3. Arrow key
    """
    old_url = page.url
    
    # Random delay before navigation (0-3 sec)
    delay = random.uniform(0, 3)
    logger.debug(f"Instance {instance_id}: Waiting {delay:.1f}s before {direction} short navigation")
    time.sleep(delay)
    
    # Method 1: Mouse wheel
    for attempt in range(max_attempts):
        if direction == 'next':
            page.mouse.wheel(0, random.randint(600, 900))
        else:
            page.mouse.wheel(0, random.randint(-900, -600))
        
        time.sleep(1.5)
        
        if page.url != old_url:
            logger.info(f"Instance {instance_id}: Wheel navigation succeeded (attempt {attempt+1})")
            return True
        time.sleep(0.5)
    
    # Method 2: Navigation button
    logger.info(f"Instance {instance_id}: Wheel failed, trying {direction} button")
    if direction == 'next':
        if click_next_short_button(page, instance_id):
            time.sleep(1.5)
            if page.url != old_url:
                logger.info(f"Instance {instance_id}: Button navigation succeeded")
                return True
    else:
        if click_previous_short_button(page, instance_id):
            time.sleep(1.5)
            if page.url != old_url:
                logger.info(f"Instance {instance_id}: Button navigation succeeded")
                return True
    
    # Method 3: Arrow key
    logger.info(f"Instance {instance_id}: Button failed, using arrow key")
    key = 'ArrowDown' if direction == 'next' else 'ArrowUp'
    page.keyboard.press(key)
    time.sleep(2)
    
    return page.url != old_url


def interact_with_current_short(page: Page, instance_id: int, watch_duration: int) -> dict:
    """
    Interact with current short while watching:
    - Random mouse movements
    - Occasional hover over like button
    - Tiny scrolls
    """
    stats = {
        "hover_count": 0,
        "scroll_count": 0,
        "duration": watch_duration
    }
    
    start_time = time.time()
    
    while time.time() - start_time < watch_duration:
        remaining = watch_duration - (time.time() - start_time)
        if remaining <= 0:
            break
        
        action = random.random()
        
        if action < 0.1:  # 10% chance - tiny scroll
            page.mouse.wheel(0, random.randint(20, 60))
            stats["scroll_count"] += 1
            time.sleep(0.3)
            
        elif action < 0.15:  # 5% chance - hover like button
            like_btn = page.locator("button[aria-label*='like']").first
            if like_btn.count() > 0:
                like_btn.hover()
                time.sleep(random.uniform(0.3, 0.8))
                stats["hover_count"] += 1
        
        sleep_time = min(1.0, remaining)
        time.sleep(sleep_time)
    
    return stats


def watch_shorts_feed(page: Page, instance_id: int, max_shorts: int = 2, watch_time_range: tuple = (10, 25)) -> int:
    """
    Watch shorts feed with navigation and interaction.
    Returns number of shorts watched.
    """
    if max_shorts > 2:
        logger.warning(f"Instance {instance_id}: max_shorts limited to 2 (requested {max_shorts})")
        max_shorts = 2
    
    shorts_watched = 0
    
    # Navigate to shorts
    if '/shorts/' not in page.url:
        logger.info(f"Instance {instance_id}: Navigating to YouTube Shorts")
        page.goto("https://www.youtube.com/shorts")
        wait_for_short_load(page)
    
    for i in range(max_shorts):
        logger.info(f"Instance {instance_id}: Watching short {i+1}/{max_shorts}")
        
        # Wait for short to load
        wait_for_short_load(page)
        
        # Watch current short
        watch_duration = random.randint(watch_time_range[0], watch_time_range[1])
        logger.info(f"Instance {instance_id}: Watching for {watch_duration}s")
        
        # Interact while watching
        interact_with_current_short(page, instance_id, watch_duration)
        
        shorts_watched += 1
        
        # Navigate to next short (if not last)
        if i < max_shorts - 1:
            logger.info(f"Instance {instance_id}: Navigating to next short")
            if not navigate_short_with_fallback(page, instance_id, 'next'):
                logger.warning(f"Instance {instance_id}: Failed to navigate to next short")
                break
    
    logger.info(f"Instance {instance_id}: Finished watching {shorts_watched} shorts")
    return shorts_watched


def watch_single_short(page: Page, instance_id: int, short_url: str, watch_time_range: tuple = (10, 25)) -> bool:
    """
    Watch a single specific short by URL
    """
    try:
        logger.info(f"Instance {instance_id}: Navigating to short: {short_url}")
        page.goto(short_url)
        
        wait_for_short_load(page)
        
        watch_duration = random.randint(watch_time_range[0], watch_time_range[1])
        logger.info(f"Instance {instance_id}: Watching short for {watch_duration}s")
        
        interact_with_current_short(page, instance_id, watch_duration)
        
        logger.info(f"Instance {instance_id}: Finished watching short")
        return True
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error watching short: {e}")
        return False