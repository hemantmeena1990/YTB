# common/human_behavior.py
"""
Shared human behavior functions for ALL automation scripts (Selenium + Playwright)
Includes: random scrolling, mouse movements, key presses, simulated pause,
watching loop, delayed mute with volume, suggested video clicking (enhanced),
and consent/cookie popup handling.
"""

import random
import time
import logging
from typing import Union, Optional

logger = logging.getLogger(__name__)


# ========== Helper to detect driver type ==========
def _is_playwright(driver_or_page):
    """Check if the object is a Playwright page (has evaluate method)"""
    return hasattr(driver_or_page, 'evaluate') and not hasattr(driver_or_page, 'execute_script')


def _is_selenium(driver_or_page):
    """Check if the object is a Selenium driver (has execute_script method)"""
    return hasattr(driver_or_page, 'execute_script')


# ========== Basic actions (Unified) ==========
def human_delay(min_seconds: float = 0.5, max_seconds: float = 1.5):
    """Random human-like delay"""
    time.sleep(random.uniform(min_seconds, max_seconds))



def random_key_press(driver_or_page):
    """
    Random key press - works with Selenium or Playwright
    """
    if random.random() < 0.12:
        if _is_playwright(driver_or_page):
            # Playwright key mapping
            keys = ['ArrowDown', 'ArrowUp', 'Space', 'PageDown', 'PageUp']
            key = random.choice(keys)
            driver_or_page.keyboard.press(key)
            time.sleep(random.uniform(0.05, 0.15))
            if key == 'Space' and random.random() < 0.4:
                time.sleep(random.uniform(0.3, 0.8))
                driver_or_page.keyboard.press('Space')
        else:
            # Selenium key mapping
            from selenium.webdriver.common.keys import Keys
            keys = [Keys.ARROW_DOWN, Keys.ARROW_UP, Keys.SPACE, Keys.PAGE_DOWN, Keys.PAGE_UP]
            key = random.choice(keys)
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver_or_page).send_keys(key).perform()
            time.sleep(random.uniform(0.05, 0.15))
            if key == Keys.SPACE and random.random() < 0.4:
                time.sleep(random.uniform(0.3, 0.8))
                ActionChains(driver_or_page).send_keys(Keys.SPACE).perform()



def simulate_pause(driver_or_page):
    """
    Pause the video by clicking on the player, then resume after a random time.
    Works with both Selenium and Playwright.
    """
    try:
        if _is_playwright(driver_or_page):
            player = driver_or_page.locator(".html5-video-player").first
            if player:
                player.click()
                time.sleep(random.uniform(3, 10))
                player.click()
                logger.info("Simulated user pause")
                return True
        else:
            from selenium.webdriver.common.by import By
            player = driver_or_page.find_element(By.CLASS_NAME, "html5-video-player")
            player.click()
            time.sleep(random.uniform(3, 10))
            player.click()
            logger.info("Simulated user pause")
            return True
    except:
        pass
    return False


# ========== Watching loop (Unified) ==========
def watch_with_human_behavior(driver_or_page, duration: int, is_mobile: bool = False):
    """
    Watch video for given duration while performing random human-like actions.
    Works with both Selenium and Playwright.
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
            random_scroll(driver_or_page, is_mobile)
        elif r < 0.7:
            random_mouse_movement(driver_or_page)
        else:
            random_key_press(driver_or_page)
        
        if not paused and random.random() < 0.06 and duration > 30:
            if simulate_pause(driver_or_page):
                paused = True
        
        next_action = random.expovariate(0.12) + random.uniform(2, 8)
        next_action = min(max(next_action, 4), 20)


# ========== Video playback helpers (Unified) ==========
def is_video_playing(driver_or_page) -> bool:
    """Check if video is playing - works with Selenium and Playwright"""
    try:
        if _is_playwright(driver_or_page):
            return driver_or_page.evaluate("""
                const v = document.querySelector('video');
                return v && !v.paused && v.currentTime > 0 && !v.ended;
            """)
        else:
            return driver_or_page.execute_script("""
                var v = document.querySelector('video');
                return v && !v.paused && v.currentTime > 0 && !v.ended;
            """)
    except:
        return False


def ensure_video_playback(driver_or_page, instance_id: int = 0) -> bool:
    """
    Try to start video if not playing. If already playing, do nothing and return True.
    Returns True if video is playing (or was successfully started), False if failed.
    """
    # First check if video is already playing
    if is_video_playing(driver_or_page):
        logger.debug(f"[Instance {instance_id}] Video already playing, skipping start attempt")
        return True
    
    logger.warning(f"[Instance {instance_id}] Video not playing. Attempting start...")
    
    for _ in range(2):
        try:
            if _is_playwright(driver_or_page):
                driver_or_page.keyboard.press('Space')
            else:
                from selenium.webdriver.common.action_chains import ActionChains
                from selenium.webdriver.common.keys import Keys
                ActionChains(driver_or_page).send_keys(Keys.SPACE).perform()
            time.sleep(1)
            if is_video_playing(driver_or_page):
                logger.info(f"[Instance {instance_id}] Started with SPACEBAR")
                return True
        except:
            pass
    
    for _ in range(2):
        try:
            if _is_playwright(driver_or_page):
                video = driver_or_page.locator('video').first
                if video:
                    video.click()
            else:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.common.action_chains import ActionChains
                video = driver_or_page.find_element(By.TAG_NAME, "video")
                ActionChains(driver_or_page).move_to_element(video).click().perform()
            time.sleep(1)
            if is_video_playing(driver_or_page):
                logger.info(f"[Instance {instance_id}] Started with CLICK")
                return True
        except:
            pass
    
    try:
        if _is_playwright(driver_or_page):
            driver_or_page.evaluate("document.querySelector('video')?.play();")
        else:
            driver_or_page.execute_script("document.querySelector('video')?.play();")
        time.sleep(1)
        if is_video_playing(driver_or_page):
            logger.info(f"[Instance {instance_id}] Started with JavaScript")
            return True
    except:
        pass
    
    logger.error(f"[Instance {instance_id}] Failed to start video")
    return False
    

def start_video_with_audio_mute(driver_or_page, instance_id: int, is_mobile: bool = False, is_suggested: bool = False) -> bool:
    """
    Set random volume (30-80%), ensure video is playing (if not already),
    then mute after random delay (0-4s). Returns True if video is playing (or was started).
    """
    try:
        mute_delay = random.choice([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        initial_volume = random.uniform(0.3, 0.8)
        logger.info(f"Instance {instance_id} {'(suggested)' if is_suggested else ''}: Volume {int(initial_volume*100)}%, mute in {mute_delay}s")
        
        # Only attempt to start if not already playing
        playing = ensure_video_playback(driver_or_page, instance_id)
        if not playing:
            logger.error(f"Instance {instance_id}: Could not start video, playback failed")
            return False
        
        # Mobile gesture (click on video) – optional
        if is_mobile:
            try:
                if _is_playwright(driver_or_page):
                    video = driver_or_page.locator('video').first
                    if video:
                        video.click()
                else:
                    from selenium.webdriver.common.by import By
                    video = driver_or_page.find_element(By.TAG_NAME, "video")
                    video.click()
                logger.info(f"Instance {instance_id}: Clicked on video for mobile gesture")
                time.sleep(0.3)
            except:
                pass
        
        # Unmute if muted, set volume, schedule mute
        if _is_playwright(driver_or_page):
            is_muted = driver_or_page.evaluate("""
                var v = document.querySelector('video');
                return v ? v.muted : false;
            """)
            if is_muted:
                logger.info(f"Instance {instance_id}: Video was muted, unmuting now")
                driver_or_page.evaluate("document.querySelector('video').muted = false;")
                time.sleep(0.5)
            
            driver_or_page.evaluate(f"""
                var v = document.querySelector('video');
                if (v) v.volume = {initial_volume};
            """)
            
            if mute_delay > 0:
                driver_or_page.evaluate(f"""
                    setTimeout(function() {{
                        var v = document.querySelector('video');
                        if (v) v.muted = true;
                    }}, {mute_delay * 1000});
                """)
        else:
            is_muted = driver_or_page.execute_script("""
                var v = document.querySelector('video');
                return v ? v.muted : false;
            """)
            if is_muted:
                logger.info(f"Instance {instance_id}: Video was muted, unmuting now")
                driver_or_page.execute_script("document.querySelector('video').muted = false;")
                time.sleep(0.5)
            
            driver_or_page.execute_script(f"""
                var v = document.querySelector('video');
                if (v) v.volume = {initial_volume};
            """)
            
            if mute_delay > 0:
                driver_or_page.execute_script(f"""
                    setTimeout(function() {{
                        var v = document.querySelector('video');
                        if (v) v.muted = true;
                    }}, {mute_delay * 1000});
                """)
        
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Video start error - {e}")
        return False
        



def attempt_video_playback_with_retry(driver_or_page, instance_id: int, is_mobile: bool = False, is_suggested: bool = False, max_retries: int = 3) -> bool:
    """
    Attempt to start video playback with retry logic using multiple methods.
    No page reload – preserves PO tokens and session cookies.
    
    Args:
        driver_or_page: WebDriver or Playwright page
        instance_id: Instance identifier for logging
        is_mobile: Whether mobile viewport
        is_suggested: Whether this is a suggested video
        max_retries: Maximum number of retry attempts (default 3)
    
    Returns:
        True if video is playing, False otherwise
    """
    
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"[Instance {instance_id}] Retry attempt {attempt+1}/{max_retries}")
            time.sleep(random.uniform(2, 4))
            
            # On retry: try direct video click first (bypasses overlays)
            try:
                if _is_playwright(driver_or_page):
                    video = driver_or_page.locator('video').first
                    if video:
                        video.click()
                else:
                    from selenium.webdriver.common.by import By
                    video = driver_or_page.find_element(By.TAG_NAME, "video")
                    driver_or_page.execute_script("arguments[0].click();", video)
                time.sleep(1.5)
                if is_video_playing(driver_or_page):
                    logger.info(f"[Instance {instance_id}] Started with direct video click (attempt {attempt+1})")
                    return True
            except Exception as e:
                logger.debug(f"Direct click failed: {e}")
            
            # Try spacebar
            try:
                if _is_playwright(driver_or_page):
                    driver_or_page.keyboard.press('Space')
                else:
                    from selenium.webdriver.common.keys import Keys
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(driver_or_page).send_keys(Keys.SPACE).perform()
                time.sleep(1.5)
                if is_video_playing(driver_or_page):
                    logger.info(f"[Instance {instance_id}] Started with spacebar (attempt {attempt+1})")
                    return True
            except Exception as e:
                logger.debug(f"Spacebar failed: {e}")
            
            # Try click on video player area
            try:
                if _is_playwright(driver_or_page):
                    player = driver_or_page.locator('.html5-video-player').first
                    if player:
                        player.click()
                else:
                    from selenium.webdriver.common.by import By
                    player = driver_or_page.find_element(By.CLASS_NAME, "html5-video-player")
                    driver_or_page.execute_script("arguments[0].click();", player)
                time.sleep(1.5)
                if is_video_playing(driver_or_page):
                    logger.info(f"[Instance {instance_id}] Started with player click (attempt {attempt+1})")
                    return True
            except Exception as e:
                logger.debug(f"Player click failed: {e}")
            
            # Try JavaScript play as last resort
            try:
                if _is_playwright(driver_or_page):
                    driver_or_page.evaluate("document.querySelector('video')?.play();")
                else:
                    driver_or_page.execute_script("document.querySelector('video')?.play();")
                time.sleep(1.5)
                if is_video_playing(driver_or_page):
                    logger.info(f"[Instance {instance_id}] Started with JavaScript play (attempt {attempt+1})")
                    return True
            except Exception as e:
                logger.debug(f"JavaScript play failed: {e}")
        
        else:
            # First attempt: use standard method
            success = start_video_with_audio_mute(driver_or_page, instance_id, is_mobile, is_suggested)
            if success:
                return True
    
    logger.error(f"[Instance {instance_id}] All {max_retries} playback attempts failed")
    return False


# ========== Consent/Cookie Popup Handler ==========
def handle_consent_popups(driver_or_page, instance_id: int = 0, timeout: int = 5) -> bool:
    """
    Handle various YouTube popups and consent dialogs.
    Works with both Selenium and Playwright.
    """
    handled = False
    
    consent_selectors = [
        "button[aria-label='Accept all']",
        "button[aria-label='Accept the use of cookies and other data for the purposes described']",
        "#accept-button",
        "ytd-consent-bump-renderer button:first-child",
        "tp-yt-paper-dialog button:first-child",
        ".eom-buttons button:first-child",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "button:has-text('Got it')",
    ]
    
    try:
        time.sleep(1.5)
        
        if _is_playwright(driver_or_page):
            for selector in consent_selectors:
                try:
                    elements = driver_or_page.locator(selector).all()
                    for element in elements:
                        if element.is_visible() and element.is_enabled():
                            button_text = element.text_content() or element.get_attribute('aria-label') or selector[:30]
                            logger.info(f"Instance {instance_id}: Found consent popup - clicking: {button_text}")
                            element.click()
                            handled = True
                            time.sleep(random.uniform(1, 2))
                            break
                    if handled:
                        break
                except:
                    continue
            
            if not handled:
                js_click = """
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var text = buttons[i].innerText.toLowerCase();
                    if (text.includes('accept') || text.includes('agree') || text.includes('got it') || 
                        text.includes('i agree') || text.includes('ok')) {
                        buttons[i].click();
                        return true;
                    }
                }
                return false;
                """
                result = driver_or_page.evaluate(js_click)
                if result:
                    logger.info(f"Instance {instance_id}: Consent handled via JavaScript fallback")
                    handled = True
        else:
            from selenium.webdriver.common.by import By
            from selenium.common.exceptions import ElementClickInterceptedException, ElementNotInteractableException
            from selenium.webdriver.common.action_chains import ActionChains
            
            for selector in consent_selectors:
                try:
                    elements = driver_or_page.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        try:
                            if element.is_displayed() and element.is_enabled():
                                button_text = element.text.strip() or element.get_attribute('aria-label') or selector[:30]
                                logger.info(f"Instance {instance_id}: Found consent popup - clicking: {button_text}")
                                
                                driver_or_page.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                time.sleep(0.3)
                                
                                try:
                                    element.click()
                                    logger.info(f"Instance {instance_id}: Clicked via regular click")
                                except (ElementClickInterceptedException, ElementNotInteractableException):
                                    try:
                                        driver_or_page.execute_script("arguments[0].click();", element)
                                        logger.info(f"Instance {instance_id}: Clicked via JavaScript")
                                    except:
                                        try:
                                            ActionChains(driver_or_page).move_to_element(element).click().perform()
                                            logger.info(f"Instance {instance_id}: Clicked via ActionChains")
                                        except:
                                            pass
                                
                                handled = True
                                time.sleep(random.uniform(1, 2))
                                break
                        except:
                            continue
                    if handled:
                        break
                except:
                    continue
            
            if not handled:
                js_click = """
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var text = buttons[i].innerText.toLowerCase();
                    if (text.includes('accept') || text.includes('agree') || text.includes('got it') || 
                        text.includes('i agree') || text.includes('ok')) {
                        buttons[i].click();
                        return true;
                    }
                }
                return false;
                """
                result = driver_or_page.execute_script(js_click)
                if result:
                    logger.info(f"Instance {instance_id}: Consent handled via JavaScript fallback")
                    handled = True
                
    except Exception as e:
        logger.debug(f"Instance {instance_id}: Error checking consent popups - {e}")
    
    if handled:
        time.sleep(random.uniform(1, 2))
    
    return handled


def handle_all_popups(driver_or_page, instance_id: int = 0) -> int:
    """
    Comprehensive popup handler that checks for multiple types of popups.
    Call this after page load to ensure clean state.
    Works with both Selenium and Playwright.
    """
    popups_handled = 0
    
    for attempt in range(3):
        if handle_consent_popups(driver_or_page, instance_id):
            popups_handled += 1
        time.sleep(0.5)
    
    if popups_handled > 0:
        logger.info(f"Instance {instance_id}: Handled {popups_handled} popup(s)")
    
    return popups_handled


# ========== Suggested video click (enhanced) ==========
def click_suggested_video(driver_or_page, is_mobile: bool = False) -> bool:
    """
    Click a suggested video from the sidebar (desktop) or after scrolling (mobile).
    Works with both Selenium and Playwright.
    Returns True if navigation succeeded.
    """
    try:
        if _is_playwright(driver_or_page):
            current_url = driver_or_page.url
            current_vid = None
            if 'v=' in current_url:
                current_vid = current_url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in current_url:
                current_vid = current_url.split('youtu.be/')[1].split('?')[0]

            candidates = []

            if is_mobile:
                for _ in range(3):
                    driver_or_page.evaluate("window.scrollBy(0, 500);")
                    time.sleep(1)
                
                selectors = [
                    "ytm-compact-video-renderer a",
                    ".compact-media-item a[href*='/watch?v=']",
                    "a[href*='/watch?v=']"
                ]
                for selector in selectors:
                    elements = driver_or_page.locator(selector).all()
                    for el in elements:
                        href = el.get_attribute('href')
                        if href and '/watch?v=' in href:
                            if current_vid and current_vid in href:
                                continue
                            if el.is_visible():
                                candidates.append(el)
                
                if not candidates and current_vid:
                    candidates = driver_or_page.locator(f"//a[contains(@href, '/watch?v=') and not(contains(@href, '{current_vid}'))]").all()
            else:
                driver_or_page.evaluate("window.scrollBy(0, 300);")
                time.sleep(1)
                selectors = [
                    "#secondary a[href*='/watch?v=']",
                    "ytd-compact-video-renderer a#thumbnail"
                ]
                for selector in selectors:
                    elements = driver_or_page.locator(selector).all()
                    for el in elements:
                        href = el.get_attribute('href')
                        if href and '/watch?v=' in href:
                            if current_vid and current_vid in href:
                                continue
                            candidates.append(el)
                
                if not candidates:
                    candidates = driver_or_page.locator("#secondary a[href*='/watch?v=']").all()

            if not candidates:
                logger.warning("No suggested video links found")
                return False

            idx = random.randint(0, min(len(candidates) - 1, 5))
            link = candidates[idx]
            link.click()
            time.sleep(2)
            return True
            
        else:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.action_chains import ActionChains
            
            current_url = driver_or_page.current_url
            current_vid = None
            if 'v=' in current_url:
                current_vid = current_url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in current_url:
                current_vid = current_url.split('youtu.be/')[1].split('?')[0]

            candidates = []

            if is_mobile:
                for _ in range(3):
                    driver_or_page.execute_script("window.scrollBy(0, 500);")
                    time.sleep(1)
                selectors = [
                    "ytm-compact-video-renderer a",
                    ".compact-media-item a[href*='/watch?v=']",
                    "a[href*='/watch?v=']"
                ]
                for sel in selectors:
                    for el in driver_or_page.find_elements(By.CSS_SELECTOR, sel):
                        href = el.get_attribute('href')
                        if href and '/watch?v=' in href:
                            if current_vid and current_vid in href:
                                continue
                            if el.is_displayed():
                                candidates.append(el)
                if not candidates and current_vid:
                    xpath = f"//a[contains(@href, '/watch?v=') and not(contains(@href, '{current_vid}'))]"
                    candidates = driver_or_page.find_elements(By.XPATH, xpath)
            else:
                driver_or_page.execute_script("window.scrollBy(0, 300);")
                time.sleep(1)
                selectors = [
                    "#secondary a[href*='/watch?v=']",
                    "ytd-compact-video-renderer a#thumbnail"
                ]
                for sel in selectors:
                    for el in driver_or_page.find_elements(By.CSS_SELECTOR, sel):
                        href = el.get_attribute('href')
                        if href and '/watch?v=' in href:
                            if current_vid and current_vid in href:
                                continue
                            candidates.append(el)
                if not candidates:
                    candidates = driver_or_page.find_elements(By.CSS_SELECTOR, "#secondary a[href*='/watch?v=']")

            if not candidates:
                logger.warning("No suggested video links found")
                return False

            idx = random.randint(0, min(len(candidates) - 1, 5))
            link = candidates[idx]
            
            driver_or_page.execute_script("arguments[0].scrollIntoView(true);", link)
            time.sleep(0.5)
            driver_or_page.execute_script("arguments[0].click();", link)
            time.sleep(2)
            return True

    except Exception as e:
        logger.error(f"Error in click_suggested_video: {e}")
        return False


# ========== Utility functions ==========
def get_variable_watch_time(min_seconds: int, max_seconds: int) -> int:
    """Get random watch time within range"""
    return random.randint(min_seconds, max_seconds)


# ========== SHORTS-SPECIFIC FUNCTIONS (ADDED FOR YTShort.py) ==========
# These are new functions - no existing functions were modified



def shorts_next_video(driver, direction='down'):
    """
    Navigate to next/previous short using mouse wheel
    
    Args:
        driver: WebDriver instance (Selenium only)
        direction: 'down' for next short, 'up' for previous short
    
    Returns:
        bool: True if navigation succeeded
    """
    if direction == 'down':
        delta_y = random.randint(600, 900)
        simulate_mouse_wheel(driver, delta_y, duration_ms=random.randint(80, 150))
        time.sleep(random.uniform(1.5, 3))
        
        if random.random() < 0.3:
            time.sleep(0.5)
            simulate_mouse_wheel(driver, random.randint(50, 150), duration_ms=50)
        
    elif direction == 'up':
        delta_y = random.randint(-900, -600)
        simulate_mouse_wheel(driver, delta_y, duration_ms=random.randint(80, 150))
        time.sleep(random.uniform(1.5, 3))
    
    return True


def shorts_swipe_with_hesitation(driver, direction='down'):
    """
    Simulate a human-like swipe with hesitation (pause mid-scroll)
    
    Args:
        driver: WebDriver instance (Selenium only)
        direction: 'down' or 'up'
    """
    if direction == 'down':
        simulate_mouse_wheel(driver, random.randint(200, 400), duration_ms=random.randint(40, 80))
        time.sleep(random.uniform(0.2, 0.5))
        simulate_mouse_wheel(driver, random.randint(400, 600), duration_ms=random.randint(60, 100))
    else:
        simulate_mouse_wheel(driver, random.randint(-500, -300), duration_ms=random.randint(40, 80))
        time.sleep(random.uniform(0.2, 0.5))
        simulate_mouse_wheel(driver, random.randint(-400, -200), duration_ms=random.randint(60, 100))
    
    time.sleep(random.uniform(1, 2))


def watch_shorts_with_human_behavior(driver, max_shorts=2, session_duration_seconds=None):
    """
    Watch YouTube Shorts with human-like behavior using mouse wheel
    
    Features:
    - Mouse wheel simulation (not programmatic scroll)
    - Maximum 2 shorts before returning (hard limit)
    - Random watch times per short
    - Hover interactions only (no likes - requires login)
    - Occasional returns to previous short
    
    Args:
        driver: WebDriver instance (Selenium only)
        max_shorts: Maximum number of shorts to watch (HARD LIMITED TO 2)
        session_duration_seconds: Optional max session duration in seconds
    
    Returns:
        dict: Statistics {shorts_watched, time_spent, mouse_wheel_movements, returns_to_original}
    """
    
    if max_shorts > 2:
        logger.warning(f"max_shorts limited to 2 (requested {max_shorts})")
        max_shorts = 2
    
    stats = {
        "shorts_watched": 0,
        "time_spent": 0,
        "mouse_wheel_movements": 0,
        "returns_to_original": 0
    }
    
    start_time = time.time()
    
    logger.info(f"Starting Shorts session - Max {max_shorts} shorts to watch")
    
    current_url = driver.current_url
    if '/shorts/' not in current_url:
        logger.info("Navigating to YouTube Shorts")
        driver.get("https://www.youtube.com/shorts")
        time.sleep(3)
        handle_all_popups(driver, 0)
    
    current_position = 0
    shorts_watched = 1
    stats["shorts_watched"] = shorts_watched
    
    logger.info(f"📱 Short 1/{max_shorts} - Watching current short")
    watch_time = random.uniform(12, 25)
    _watch_shorts_with_hover_only(driver, watch_time, stats)
    
    while shorts_watched < max_shorts:
        
        action = random.choices(
            ["next", "stay", "hover_then_next", "return_previous"],
            weights=[0.6, 0.2, 0.1, 0.1]
        )[0]
        
        if action == "next":
            logger.info(f"🐭 Mouse wheel scroll → Next short ({shorts_watched + 1}/{max_shorts})")
            shorts_next_video(driver, direction='down')
            stats["mouse_wheel_movements"] += 1
            current_position += 1
            
            shorts_watched += 1
            stats["shorts_watched"] = shorts_watched
            
            watch_time = random.uniform(10, 20)
            logger.info(f"📱 Short {shorts_watched}/{max_shorts} - Watching for {watch_time:.1f}s")
            _watch_shorts_with_hover_only(driver, watch_time, stats)
            
        elif action == "stay":
            logger.info("👀 Staying on current short longer")
            extra_time = random.uniform(5, 12)
            _watch_shorts_with_hover_only(driver, extra_time, stats)
            
        elif action == "hover_then_next":
            logger.info("🖱️ Hovering on button, then moving to next short")
            _hover_random_shorts_button(driver)
            time.sleep(random.uniform(1, 2))
            
            logger.info(f"🐭 Mouse wheel scroll → Next short")
            shorts_next_video(driver, direction='down')
            stats["mouse_wheel_movements"] += 1
            current_position += 1
            
            shorts_watched += 1
            stats["shorts_watched"] = shorts_watched
            watch_time = random.uniform(10, 18)
            _watch_shorts_with_hover_only(driver, watch_time, stats)
            
        elif action == "return_previous":
            if current_position > 0:
                logger.info("⬆️ Mouse wheel scroll → Return to previous short")
                shorts_next_video(driver, direction='up')
                stats["mouse_wheel_movements"] += 1
                stats["returns_to_original"] += 1
                current_position -= 1
                shorts_watched -= 1
                
                watch_time = random.uniform(8, 15)
                _watch_shorts_with_hover_only(driver, watch_time, stats)
        
        if session_duration_seconds and (time.time() - start_time) > session_duration_seconds:
            logger.info(f"Session duration limit reached ({session_duration_seconds}s)")
            break
    
    if stats["shorts_watched"] > 1 and random.random() < 0.4:
        logger.info("🔄 Returning to first short before leaving")
        while stats["shorts_watched"] > 1:
            shorts_next_video(driver, direction='up')
            stats["mouse_wheel_movements"] += 1
            stats["shorts_watched"] -= 1
            time.sleep(random.uniform(0.8, 1.5))
    
    stats["time_spent"] = time.time() - start_time
    logger.info(f"✅ Shorts session complete: {stats['shorts_watched']} shorts, {stats['time_spent']:.1f}s")
    
    return stats


def _watch_shorts_with_hover_only(driver, duration_seconds, stats):
    """
    Watch a short with hover interactions only (no likes - requires login)
    """
    start_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        remaining = duration_seconds - (time.time() - start_time)
        if remaining <= 0:
            break
        
        interaction = random.random()
        
        if interaction < 0.12:
            tiny_scroll = random.randint(20, 80)
            simulate_mouse_wheel(driver, tiny_scroll, duration_ms=30)
            stats["mouse_wheel_movements"] += 1
            time.sleep(0.3)
            
        elif interaction < 0.18:
            _hover_like_button_only(driver)
            time.sleep(0.5)
            
        elif interaction < 0.22:
            _hover_share_button_only(driver)
            time.sleep(0.5)
        
        sleep_time = min(1.0, remaining)
        time.sleep(sleep_time)


def _hover_like_button_only(driver):
    """Hover over like button without clicking (safe - no login required)"""
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        like_selectors = [
            "button[aria-label*='like this video']",
            "button[aria-label*='like']",
            "#segmented-like-button",
            "ytd-segmented-like-dislike-button-renderer button:first-child"
        ]
        
        for selector in like_selectors:
            try:
                like_btn = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                ActionChains(driver).move_to_element(like_btn).perform()
                time.sleep(random.uniform(0.3, 0.8))
                logger.debug("Hovered over like button")
                return True
            except:
                continue
    except Exception as e:
        logger.debug(f"Hover like failed: {e}")
    
    return False


def _hover_share_button_only(driver):
    """Hover over share button without clicking (safe - no login required)"""
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        share_selectors = [
            "button[aria-label*='Share']",
            "button[aria-label*='share']",
            "ytd-button-renderer button[aria-label*='Share']"
        ]
        
        for selector in share_selectors:
            try:
                share_btn = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                ActionChains(driver).move_to_element(share_btn).perform()
                time.sleep(random.uniform(0.3, 0.8))
                logger.debug("Hovered over share button")
                return True
            except:
                continue
    except Exception as e:
        logger.debug(f"Hover share failed: {e}")
    
    return False


def _hover_random_shorts_button(driver):
    """
    Hover over a random shorts control button (like, share, comment, subscribe)
    No clicks - only hover interactions
    """
    button_types = ["like", "share", "comment", "subscribe"]
    weights = [0.4, 0.3, 0.2, 0.1]
    
    choice = random.choices(button_types, weights=weights)[0]
    
    if choice == "like":
        return _hover_like_button_only(driver)
    elif choice == "share":
        return _hover_share_button_only(driver)
    elif choice == "comment":
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.by import By
            
            comment_selectors = [
                "button[aria-label*='Comment']",
                "button[aria-label*='comment']"
            ]
            for selector in comment_selectors:
                comment_btn = driver.find_element(By.CSS_SELECTOR, selector)
                ActionChains(driver).move_to_element(comment_btn).perform()
                time.sleep(random.uniform(0.3, 0.6))
                return True
        except:
            pass
    elif choice == "subscribe":
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.by import By
            
            sub_selectors = [
                "button[aria-label*='Subscribe']",
                "#subscribe-button button"
            ]
            for selector in sub_selectors:
                sub_btn = driver.find_element(By.CSS_SELECTOR, selector)
                ActionChains(driver).move_to_element(sub_btn).perform()
                time.sleep(random.uniform(0.3, 0.6))
                return True
        except:
            pass
    
    return False
    
    
    # ========== URL change detection (unified) ==========
def wait_for_url_change(driver_or_page, old_url, timeout=5):
    """
    Wait for URL to change from old_url.
    Works with Selenium WebDriver or Playwright Page.
    Returns True if changed within timeout, else False.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            if _is_playwright(driver_or_page):
                current = driver_or_page.url
            else:
                current = driver_or_page.current_url
            if current != old_url:
                return True
        except:
            pass
        time.sleep(0.3)
    return False


# ========== Mouse wheel simulation (unified) ==========
def simulate_mouse_wheel(driver_or_page, delta_y, duration_ms=100):
    """
    Simulate mouse wheel scroll using multiple techniques.
    - JavaScript wheel event (primary)
    - ActionChains wheel_scroll (Selenium 4.2+)
    - window.scrollBy (fallback)
    Works with both Selenium and Playwright.
    """
    wheel_script = """
    function sendWheel(target, deltaY) {
        var ev = new WheelEvent('wheel', {
            bubbles: true,
            cancelable: true,
            deltaY: deltaY,
            deltaMode: 0x00
        });
        target.dispatchEvent(ev);
    }
    var target = document.querySelector('video') ||
                 document.querySelector('ytd-shorts') ||
                 document.querySelector('ytd-reel-video-renderer') ||
                 document.body;
    sendWheel(target, arguments[0]);
    window.scrollBy(0, arguments[0] * 0.2);
    """
    try:
        if _is_playwright(driver_or_page):
            driver_or_page.evaluate(wheel_script, delta_y)
        else:
            driver_or_page.execute_script(wheel_script, delta_y)
        time.sleep(0.2)
        return True
    except Exception as e:
        logger.debug(f"JS wheel simulation failed: {e}")

    # Selenium-specific fallback using ActionChains wheel scroll (Selenium 4.2+)
    if not _is_playwright(driver_or_page):
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.by import By
            video = driver_or_page.find_element(By.TAG_NAME, "video")
            ActionChains(driver_or_page).scroll_to_element(video).perform()
            ActionChains(driver_or_page).scroll_by_amount(0, delta_y).perform()
            time.sleep(0.3)
            logger.debug("Used ActionChains wheel scroll")
            return True
        except Exception as e2:
            logger.debug(f"ActionChains wheel failed: {e2}")

    # Final fallback: simple window scroll
    try:
        if _is_playwright(driver_or_page):
            driver_or_page.evaluate(f"window.scrollBy(0, {delta_y})")
        else:
            driver_or_page.execute_script(f"window.scrollBy(0, {delta_y})")
        logger.debug("Used window.scrollBy fallback")
        return True
    except Exception as e3:
        logger.error(f"All wheel simulation methods failed: {e3}")
        return False
        

def find_shorts_navigation_button(driver_or_page, direction='next'):
    """
    Find the next/previous short navigation button.
    Returns the element if found, None otherwise.
    
    Args:
        driver_or_page: Selenium WebDriver or Playwright page
        direction: 'next' or 'prev'
    """
    # Button selectors for YouTube Shorts navigation
    if direction == 'next':
        selectors = [
            "button[aria-label='Next video']",
            "button[aria-label='Next']",
            "div[aria-label='Next video']",
            ".yt-spec-touch-feedback-shape-fill",
            "div[role='button'][aria-label*='Next']"
        ]
    else:  # previous
        selectors = [
            "button[aria-label='Previous video']",
            "button[aria-label='Previous']",
            "div[aria-label='Previous video']",
            "div[role='button'][aria-label*='Previous']"
        ]
    
    for selector in selectors:
        try:
            if _is_playwright(driver_or_page):
                element = driver_or_page.locator(selector).first
                if element and element.is_visible():
                    return element
            else:
                from selenium.webdriver.common.by import By
                elements = driver_or_page.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed():
                        return elem
        except:
            continue
    return None



def click_shorts_navigation_button(driver_or_page, direction='next'):
    """
    Click the next/previous short navigation button using human_click.
    Returns True if clicked successfully, False otherwise.
    """
    button = find_shorts_navigation_button(driver_or_page, direction)
    if button:
        try:
            if _is_playwright(driver_or_page):
                button.click()
                time.sleep(random.uniform(0.2, 0.5))
            else:
                from humanclick import human_click
                human_click(driver_or_page, button)
            logger.debug(f"Clicked {direction} shorts navigation button")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.debug(f"Failed to click {direction} button: {e}")
    return False



def navigate_shorts_with_fallback(driver_or_page, direction='next', max_attempts=3):
    """
    Navigate shorts using fallback chain:
    1. Mouse wheel (primary)
    2. Click navigation button with human_click (secondary)
    3. Arrow key (final fallback)
    
    Returns True if navigation succeeded, False otherwise.
    """
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    
    old_url = None
    if _is_playwright(driver_or_page):
        old_url = driver_or_page.url
    else:
        old_url = driver_or_page.current_url
    
    # Random delay before navigation (0-3 sec)
    delay = random.uniform(0, 3)
    logger.debug(f"Waiting {delay:.1f}s before {direction} short navigation")
    time.sleep(delay)
    
    # Method 1: Mouse wheel
    for attempt in range(max_attempts):
        delta_y = random.randint(600, 900) if direction == 'next' else random.randint(-900, -600)
        simulate_mouse_wheel(driver_or_page, delta_y)
        time.sleep(1.2)
        
        # Check if URL changed
        if _is_playwright(driver_or_page):
            current_url = driver_or_page.url
        else:
            current_url = driver_or_page.current_url
        
        if current_url != old_url:
            logger.info(f"Navigation succeeded with mouse wheel (attempt {attempt+1})")
            return True
        time.sleep(0.5)
    
    # Method 2: Click navigation button with human_click
    logger.info(f"Mouse wheel failed, trying {direction} button click")
    if click_shorts_navigation_button(driver_or_page, direction):
        time.sleep(1.5)
        if _is_playwright(driver_or_page):
            current_url = driver_or_page.url
        else:
            current_url = driver_or_page.current_url
        
        if current_url != old_url:
            logger.info(f"Navigation succeeded with {direction} button click")
            return True
    
    # Method 3: Arrow key fallback
    logger.info(f"Button click failed, using arrow {direction} key")
    if _is_playwright(driver_or_page):
        key = 'ArrowDown' if direction == 'next' else 'ArrowUp'
        driver_or_page.keyboard.press(key)
    else:
        key = Keys.ARROW_DOWN if direction == 'next' else Keys.ARROW_UP
        ActionChains(driver_or_page).send_keys(key).perform()
    
    time.sleep(2)
    if _is_playwright(driver_or_page):
        current_url = driver_or_page.url
    else:
        current_url = driver_or_page.current_url
    
    return current_url != old_url


    
        
# ========== Unified human behaviors (moved from utils.py) ==========
def random_scroll(driver_or_page, is_mobile: bool = False, smooth: bool = True):
    """
    Random scroll using mouse wheel simulation - works with Selenium driver or Playwright page.
    More human-like than direct JavaScript scroll.
    """
    if is_mobile:
        amount = random.randint(100, 500)
    else:
        amount = random.randint(80, 400)
    
    # For Playwright, fallback to evaluate (mouse wheel simulation is complex)
    if _is_playwright(driver_or_page):
        try:
            driver_or_page.evaluate(f"window.scrollBy({{top: {amount}, behavior: 'smooth'}});")
        except Exception as e:
            logger.debug(f"Playwright scroll error: {e}")
    else:
        # Use mouse wheel simulation for Selenium
        try:
            # Break the scroll into smaller steps for more human-like behavior
            steps = random.randint(2, 4)
            step_amount = amount // steps
            
            for _ in range(steps):
                simulate_mouse_wheel(driver_or_page, step_amount)
                time.sleep(random.uniform(0.05, 0.15))
            
            # Remaining amount if not perfectly divisible
            remaining = amount - (step_amount * steps)
            if remaining != 0:
                simulate_mouse_wheel(driver_or_page, remaining)
                
        except Exception as e:
            logger.debug(f"Mouse wheel scroll failed, falling back to JavaScript: {e}")
            driver_or_page.execute_script(f"window.scrollBy({{top: {amount}, behavior: 'smooth'}});")
    
    # Sometimes scroll back a little (using mouse wheel as well)
    if random.random() < 0.3:
        time.sleep(random.uniform(0.2, 0.6))
        additional = random.randint(20, 100) * (1 if random.random() < 0.7 else -1)
        try:
            if _is_playwright(driver_or_page):
                driver_or_page.evaluate(f"window.scrollBy(0, {additional});")
            else:
                # Use mouse wheel for the reverse scroll as well
                simulate_mouse_wheel(driver_or_page, additional)
        except:
            pass
            

def random_mouse_movement(driver_or_page, element=None):
    """
    Random mouse movement – works with Selenium driver or Playwright page.
    """
    try:
        if _is_playwright(driver_or_page):
            if element:
                # Get bounding box of element and move to a random offset
                box = element.bounding_box()
                if box:
                    x = box['x'] + random.uniform(0, box['width'])
                    y = box['y'] + random.uniform(0, box['height'])
                    driver_or_page.mouse.move(x, y)
            else:
                # Move to random position within viewport
                vp = driver_or_page.evaluate("return {w: window.innerWidth, h: window.innerHeight}")
                x = random.randint(50, vp['w'] - 50)
                y = random.randint(50, vp['h'] - 50)
                driver_or_page.mouse.move(x, y)
        else:
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver_or_page)
            if element:
                x_offset = random.randint(-20, 20)
                y_offset = random.randint(-20, 20)
                actions.move_to_element_with_offset(element, x_offset, y_offset)
            else:
                viewport = driver_or_page.execute_script("return {width: window.innerWidth, height: window.innerHeight};")
                x = random.randint(50, viewport['width'] - 50)
                y = random.randint(50, viewport['height'] - 50)
                actions.move_by_offset(x, y)
            actions.perform()
        time.sleep(random.uniform(0.1, 0.3))
    except Exception as e:
        logger.debug(f"Mouse movement error: {e}")