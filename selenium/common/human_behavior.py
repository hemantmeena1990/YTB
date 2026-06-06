# common/human_behavior.py
"""
Shared human behavior functions for all YouTube automation scripts.
Includes: random scrolling, mouse movements, key presses, simulated pause,
watching loop, delayed mute with volume, and suggested video clicking (enhanced).
"""

import random
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from common.utils import is_video_playing


# Import the shared human click utility
from common.humanclick import human_click

logger = logging.getLogger(__name__)

# ---------- Basic actions ----------
def random_scroll(driver, is_mobile=False):
    amount = random.randint(100, 500) if is_mobile else random.randint(80, 400)
    driver.execute_script(f"window.scrollBy(0, {amount});")
    time.sleep(random.uniform(0.2, 0.6))

def random_key_press(driver):
    if random.random() < 0.12:
        key = random.choice([Keys.ARROW_DOWN, Keys.ARROW_UP, Keys.SPACE, Keys.PAGE_DOWN, Keys.PAGE_UP])
        ActionChains(driver).send_keys(key).perform()
        time.sleep(random.uniform(0.05, 0.15))
        if key == Keys.SPACE and random.random() < 0.4:
            time.sleep(random.uniform(0.3, 0.8))
            ActionChains(driver).send_keys(Keys.SPACE).perform()

def random_mouse_movement(driver):
    try:
        vp = driver.execute_script("return {w: window.innerWidth, h: window.innerHeight}")
        x = random.randint(50, vp['w'] - 50)
        y = random.randint(50, vp['h'] - 50)
        ActionChains(driver).move_by_offset(x, y).perform()
        time.sleep(random.uniform(0.1, 0.3))
    except:
        pass

def simulate_pause(driver, duration=None):
    """Pause the video by clicking on the player, then resume after a random time."""
    try:
        player = driver.find_element(By.CLASS_NAME, "html5-video-player")
        player.click()
        time.sleep(random.uniform(3, 10))
        player.click()
        logger.info("Simulated user pause")
        return True
    except:
        return False

# ---------- Watching loop ----------
def watch_with_human_behavior(driver, duration, is_mobile=False):
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
            random_scroll(driver, is_mobile)
        elif r < 0.7:
            random_mouse_movement(driver)
        else:
            random_key_press(driver)
        if not paused and random.random() < 0.06 and duration > 30:
            if simulate_pause(driver):
                paused = True
        next_action = random.expovariate(0.12) + random.uniform(2, 8)
        next_action = min(max(next_action, 4), 20)

# ---------- Video playback helpers ----------
def ensure_video_playback(driver, instance_id=0):
    """Try to start video if not playing (spacebar, click, JS)."""
    if is_video_playing(driver):
        return True
    logger.warning(f"[Instance {instance_id}] Video not playing. Attempting start...")
    # Spacebar
    for _ in range(2):
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.SPACE)
            time.sleep(1)
            if is_video_playing(driver):
                logger.info(f"[Instance {instance_id}] Started with SPACEBAR")
                return True
        except:
            pass
    # Click on video
    for _ in range(2):
        try:
            video = driver.find_element(By.TAG_NAME, "video")
            ActionChains(driver).move_to_element(video).click().perform()
            time.sleep(1)
            if is_video_playing(driver):
                logger.info(f"[Instance {instance_id}] Started with CLICK")
                return True
        except:
            pass
    # JS fallback
    try:
        driver.execute_script("document.querySelector('video')?.play();")
        time.sleep(1)
        if is_video_playing(driver):
            logger.info(f"[Instance {instance_id}] Started with JavaScript")
            return True
    except:
        pass
    logger.error(f"[Instance {instance_id}] Failed to start video")
    return False

def start_video_with_audio_mute(driver, instance_id, is_mobile=False, is_suggested=False):
    """
    Set random volume (30-80%), start video (if needed), ensure unmuted,
    then mute after random delay (0-4s). Handles both desktop and mobile.
    """
    try:
        mute_delay = random.choice([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        initial_volume = random.uniform(0.3, 0.8)
        logger.info(f"Instance {instance_id} {'(suggested)' if is_suggested else ''}: Volume {int(initial_volume*100)}%, mute in {mute_delay}s")
        
        # Ensure video element exists and is playing
        ensure_video_playback(driver, instance_id)
        
        # For mobile: click on the video first (creates user gesture)
        if is_mobile:
            try:
                video = driver.find_element(By.TAG_NAME, "video")
                video.click()
                logger.info(f"Instance {instance_id}: Clicked on video for mobile gesture")
                time.sleep(0.3)
            except:
                pass
        
        # Check if video is currently muted, and unmute if necessary
        is_muted = driver.execute_script("""
            var v = document.querySelector('video');
            return v ? v.muted : false;
        """)
        if is_muted:
            logger.info(f"Instance {instance_id}: Video was muted, unmuting now")
            driver.execute_script("document.querySelector('video').muted = false;")
            time.sleep(0.5)  # brief moment for unmute to apply
        
        # Set volume
        driver.execute_script(f"""
            var v = document.querySelector('video');
            if (v) v.volume = {initial_volume};
        """)
        
        # Schedule muting after delay (if delay > 0)
        if mute_delay > 0:
            driver.execute_script(f"""
                setTimeout(function() {{
                    var v = document.querySelector('video');
                    if (v) v.muted = true;
                }}, {mute_delay * 1000});
            """)
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Video start error - {e}")
        return False

# ---------- Suggested video click (enhanced with human_click) ----------
def click_suggested_video(driver, is_mobile=False):
    """
    Click a suggested video from the sidebar (desktop) or after scrolling (mobile).
    Uses human-like click with navigation verification.
    Returns True if navigation succeeded.
    """
    try:
        current_url = driver.current_url
        current_vid = None
        if 'v=' in current_url:
            current_vid = current_url.split('v=')[1].split('&')[0]
        elif 'youtu.be/' in current_url:
            current_vid = current_url.split('youtu.be/')[1].split('?')[0]

        candidates = []

        if is_mobile:
            # Scroll multiple times to load mobile suggestions
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(1)
            selectors = [
                "ytm-compact-video-renderer a",
                ".compact-media-item a[href*='/watch?v=']",
                "a[href*='/watch?v=']"
            ]
            for sel in selectors:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    href = el.get_attribute('href')
                    if href and '/watch?v=' in href:
                        if current_vid and current_vid in href:
                            continue
                        if el.is_displayed():
                            candidates.append(el)
            if not candidates and current_vid:
                xpath = f"//a[contains(@href, '/watch?v=') and not(contains(@href, '{current_vid}'))]"
                candidates = driver.find_elements(By.XPATH, xpath)
        else:
            # Desktop: sidebar only
            driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)
            selectors = [
                "#secondary a[href*='/watch?v=']",
                "ytd-compact-video-renderer a#thumbnail"
            ]
            for sel in selectors:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    href = el.get_attribute('href')
                    if href and '/watch?v=' in href:
                        if current_vid and current_vid in href:
                            continue
                        candidates.append(el)
            if not candidates:
                candidates = driver.find_elements(By.CSS_SELECTOR, "#secondary a[href*='/watch?v=']")

        if not candidates:
            logger.warning("No suggested video links found")
            return False

        # Pick a random candidate (prefer not the very first)
        idx = random.randint(0, min(len(candidates)-1, 5))
        link = candidates[idx]

        # Use the shared human_click function (instance_id is 0 for suggested)
        return human_click(driver, link, 0, element_type="suggested video")

    except Exception as e:
        logger.error(f"Error in click_suggested_video: {e}")
        return False