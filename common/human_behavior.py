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


def random_scroll(driver_or_page, is_mobile: bool = False, scroll_amount: Optional[int] = None):
    """
    Random scroll - works with Selenium driver or Playwright page
    """
    if scroll_amount is None:
        amount = random.randint(100, 500) if is_mobile else random.randint(80, 400)
    else:
        amount = scroll_amount
    
    try:
        if _is_playwright(driver_or_page):
            driver_or_page.evaluate(f"window.scrollBy(0, {amount})")
        else:
            driver_or_page.execute_script(f"window.scrollBy(0, {amount})")
    except Exception as e:
        logger.debug(f"Scroll error: {e}")
    
    time.sleep(random.uniform(0.2, 0.6))


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


def random_mouse_movement(driver_or_page):
    """
    Random mouse movement - works with Selenium or Playwright
    """
    try:
        if _is_playwright(driver_or_page):
            vp = driver_or_page.evaluate("return {w: window.innerWidth, h: window.innerHeight}")
        else:
            vp = driver_or_page.execute_script("return {w: window.innerWidth, h: window.innerHeight}")
        
        x = random.randint(50, vp['w'] - 50)
        y = random.randint(50, vp['h'] - 50)
        
        if _is_playwright(driver_or_page):
            driver_or_page.mouse.move(x, y)
        else:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver_or_page).move_by_offset(x, y).perform()
        
        time.sleep(random.uniform(0.1, 0.3))
    except Exception as e:
        logger.debug(f"Mouse movement error: {e}")


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
    """Try to start video if not playing (spacebar, click, JS). Works with both."""
    if is_video_playing(driver_or_page):
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
    Set random volume (30-80%), start video (if needed), ensure unmuted,
    then mute after random delay (0-4s). Works with both Selenium and Playwright.
    """
    try:
        mute_delay = random.choice([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        initial_volume = random.uniform(0.3, 0.8)
        logger.info(f"Instance {instance_id} {'(suggested)' if is_suggested else ''}: Volume {int(initial_volume*100)}%, mute in {mute_delay}s")
        
        ensure_video_playback(driver_or_page, instance_id)
        
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