# playwright/common/human_behavior.py
"""
Playwright human behavior functions - only custom logic.
Uses Playwright's built-in methods directly where possible.
"""

import random
import time
import logging
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


def human_delay(min_seconds: float = 0.5, max_seconds: float = 1.5):
    """Random human-like delay"""
    time.sleep(random.uniform(min_seconds, max_seconds))


# ========== Video playback helpers ==========
def is_video_playing(page: Page) -> bool:
    """Check if video is playing"""
    try:
        return page.evaluate("""
            const v = document.querySelector('video');
            return v && !v.paused && v.currentTime > 0 && !v.ended;
        """)
    except:
        return False


def ensure_video_playback(page: Page, instance_id: int = 0) -> bool:
    """Try to start video if not playing. If already playing, do nothing."""
    if is_video_playing(page):
        logger.debug(f"[Instance {instance_id}] Video already playing, skipping start attempt")
        return True
    
    logger.warning(f"[Instance {instance_id}] Video not playing. Attempting start...")
    
    for _ in range(2):
        try:
            page.keyboard.press('Space')
            time.sleep(1)
            if is_video_playing(page):
                logger.info(f"[Instance {instance_id}] Started with SPACEBAR")
                return True
        except:
            pass
    
    for _ in range(2):
        try:
            video = page.locator('video').first
            if video.count() > 0:
                video.click()
            time.sleep(1)
            if is_video_playing(page):
                logger.info(f"[Instance {instance_id}] Started with CLICK")
                return True
        except:
            pass
    
    try:
        page.evaluate("document.querySelector('video')?.play();")
        time.sleep(1)
        if is_video_playing(page):
            logger.info(f"[Instance {instance_id}] Started with JavaScript")
            return True
    except:
        pass
    
    logger.error(f"[Instance {instance_id}] Failed to start video")
    return False


def start_video_with_audio_mute(page: Page, instance_id: int, is_mobile: bool = False, is_suggested: bool = False) -> bool:
    """Set random volume, start video, then mute after random delay"""
    try:
        mute_delay = random.choice([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        initial_volume = random.uniform(0.3, 0.8)
        logger.info(f"Instance {instance_id} {'(suggested)' if is_suggested else ''}: Volume {int(initial_volume*100)}%, mute in {mute_delay}s")
        
        if not is_video_playing(page):
            ensure_video_playback(page, instance_id)
        
        if is_mobile:
            try:
                video = page.locator('video').first
                if video.count() > 0:
                    video.click()
                logger.info(f"Instance {instance_id}: Clicked on video for mobile gesture")
                time.sleep(0.3)
            except:
                pass
        
        is_muted = page.evaluate("""
            var v = document.querySelector('video');
            return v ? v.muted : false;
        """)
        if is_muted:
            logger.info(f"Instance {instance_id}: Video was muted, unmuting now")
            page.evaluate("document.querySelector('video').muted = false;")
            time.sleep(0.5)
        
        page.evaluate(f"""
            var v = document.querySelector('video');
            if (v) v.volume = {initial_volume};
        """)
        
        if mute_delay > 0:
            page.evaluate(f"""
                setTimeout(function() {{
                    var v = document.querySelector('video');
                    if (v) v.muted = true;
                }}, {mute_delay * 1000});
            """)
        
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Video start error - {e}")
        return False


def attempt_video_playback_with_retry(page: Page, instance_id: int, is_mobile: bool = False, is_suggested: bool = False, max_retries: int = 3) -> bool:
    """Attempt to start video with retry logic"""
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"[Instance {instance_id}] Retry attempt {attempt+1}/{max_retries}")
            time.sleep(random.uniform(2, 4))
            
            # Try direct video click first (using Playwright)
            try:
                video = page.locator('video').first
                if video.count() > 0:
                    video.click()
                time.sleep(1.5)
                if is_video_playing(page):
                    logger.info(f"[Instance {instance_id}] Started with direct video click (attempt {attempt+1})")
                    return True
            except:
                pass
            
            # Try spacebar
            try:
                page.keyboard.press('Space')
                time.sleep(1.5)
                if is_video_playing(page):
                    logger.info(f"[Instance {instance_id}] Started with spacebar (attempt {attempt+1})")
                    return True
            except:
                pass
            
            # Try player click
            try:
                player = page.locator('.html5-video-player').first
                if player.count() > 0:
                    player.click()
                time.sleep(1.5)
                if is_video_playing(page):
                    logger.info(f"[Instance {instance_id}] Started with player click (attempt {attempt+1})")
                    return True
            except:
                pass
        
        else:
            success = start_video_with_audio_mute(page, instance_id, is_mobile, is_suggested)
            if success:
                return True
    
    logger.error(f"[Instance {instance_id}] All {max_retries} playback attempts failed")
    return False


# ========== Popup Handlers ==========
def handle_consent_popups(page: Page, instance_id: int = 0) -> bool:
    """Handle various YouTube popups and consent dialogs"""
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
        
        for selector in consent_selectors:
            try:
                elements = page.locator(selector).all()
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
            result = page.evaluate(js_click)
            if result:
                logger.info(f"Instance {instance_id}: Consent handled via JavaScript fallback")
                handled = True
    except Exception as e:
        logger.debug(f"Instance {instance_id}: Error checking consent popups - {e}")
    
    if handled:
        time.sleep(random.uniform(1, 2))
    
    return handled


def handle_all_popups(page: Page, instance_id: int = 0) -> int:
    """Comprehensive popup handler"""
    popups_handled = 0
    
    for attempt in range(3):
        if handle_consent_popups(page, instance_id):
            popups_handled += 1
        time.sleep(0.5)
    
    if popups_handled > 0:
        logger.info(f"Instance {instance_id}: Handled {popups_handled} popup(s)")
    
    return popups_handled


# ========== Suggested video click ==========
def click_suggested_video(page: Page, is_mobile: bool = False) -> bool:
    """Click a suggested video from the sidebar"""
    try:
        current_url = page.url
        current_vid = None
        if 'v=' in current_url:
            current_vid = current_url.split('v=')[1].split('&')[0]
        elif 'youtu.be/' in current_url:
            current_vid = current_url.split('youtu.be/')[1].split('?')[0]

        candidates = []

        if is_mobile:
            for _ in range(3):
                page.mouse.wheel(0, 500)
                time.sleep(1)
            
            selectors = [
                "ytm-compact-video-renderer a",
                ".compact-media-item a[href*='/watch?v=']",
                "a[href*='/watch?v=']"
            ]
            for selector in selectors:
                elements = page.locator(selector).all()
                for el in elements:
                    href = el.get_attribute('href')
                    if href and '/watch?v=' in href:
                        if current_vid and current_vid in href:
                            continue
                        if el.is_visible():
                            candidates.append(el)
        else:
            page.mouse.wheel(0, 300)
            time.sleep(1)
            selectors = [
                "#secondary a[href*='/watch?v=']",
                "ytd-compact-video-renderer a#thumbnail"
            ]
            for selector in selectors:
                elements = page.locator(selector).all()
                for el in elements:
                    href = el.get_attribute('href')
                    if href and '/watch?v=' in href:
                        if current_vid and current_vid in href:
                            continue
                        candidates.append(el)

        if not candidates:
            logger.warning("No suggested video links found")
            return False

        idx = random.randint(0, min(len(candidates) - 1, 5))
        candidates[idx].click()
        time.sleep(2)
        return True
        
    except Exception as e:
        logger.error(f"Error in click_suggested_video: {e}")
        return False


# ========== Shorts navigation functions ==========
def shorts_next_video(page: Page, direction: str = 'down'):
    """Navigate to next/previous short using Playwright's mouse wheel"""
    delta_y = random.randint(600, 900) if direction == 'down' else random.randint(-900, -600)
    page.mouse.wheel(0, delta_y)
    time.sleep(random.uniform(1.5, 3))
    return True


def find_shorts_navigation_button(page: Page, direction: str = 'next'):
    """Find the next/previous short navigation button"""
    if direction == 'next':
        selectors = [
            "button[aria-label='Next video']",
            "button[aria-label='Next']",
            "div[aria-label='Next video']",
        ]
    else:
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


def click_shorts_navigation_button(page: Page, direction: str = 'next'):
    """Click the next/previous short navigation button"""
    button = find_shorts_navigation_button(page, direction)
    if button:
        try:
            button.click()
            time.sleep(0.5)
            logger.debug(f"Clicked {direction} shorts navigation button")
            return True
        except Exception as e:
            logger.debug(f"Failed to click {direction} button: {e}")
    return False


def navigate_shorts_with_fallback(page: Page, direction: str = 'next', max_attempts: int = 3):
    """Navigate shorts using fallback chain: wheel → button → arrow"""
    old_url = page.url
    
    delay = random.uniform(0, 3)
    logger.debug(f"Waiting {delay:.1f}s before {direction} short navigation")
    time.sleep(delay)
    
    # Method 1: Mouse wheel
    for attempt in range(max_attempts):
        delta_y = random.randint(600, 900) if direction == 'next' else random.randint(-900, -600)
        page.mouse.wheel(0, delta_y)
        time.sleep(1.5)
        
        if page.url != old_url:
            logger.info(f"Navigation succeeded with mouse wheel (attempt {attempt+1})")
            return True
        time.sleep(0.5)
    
    # Method 2: Click navigation button
    logger.info(f"Mouse wheel failed, trying {direction} button click")
    if click_shorts_navigation_button(page, direction):
        time.sleep(1.5)
        if page.url != old_url:
            logger.info(f"Navigation succeeded with {direction} button click")
            return True
    
    # Method 3: Arrow key
    logger.info(f"Button click failed, using arrow {direction} key")
    key = 'ArrowDown' if direction == 'next' else 'ArrowUp'
    page.keyboard.press(key)
    time.sleep(2)
    
    return page.url != old_url


def watch_shorts_with_human_behavior(page: Page, max_shorts: int = 2, session_duration_seconds: int = None):
    """Watch YouTube Shorts with human-like behavior"""
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
    
    if '/shorts/' not in page.url:
        logger.info("Navigating to YouTube Shorts")
        page.goto("https://www.youtube.com/shorts")
        time.sleep(3)
        handle_all_popups(page, 0)
    
    current_position = 0
    shorts_watched = 1
    stats["shorts_watched"] = shorts_watched
    
    watch_time = random.uniform(12, 25)
    logger.info(f"📱 Short 1/{max_shorts} - Watching for {watch_time:.1f}s")
    time.sleep(watch_time)
    
    while shorts_watched < max_shorts:
        action = random.choices(
            ["next", "stay", "hover_then_next", "return_previous"],
            weights=[0.6, 0.2, 0.1, 0.1]
        )[0]
        
        if action == "next":
            logger.info(f"🐭 Mouse wheel scroll → Next short ({shorts_watched + 1}/{max_shorts})")
            shorts_next_video(page, direction='down')
            stats["mouse_wheel_movements"] += 1
            current_position += 1
            
            shorts_watched += 1
            stats["shorts_watched"] = shorts_watched
            
            watch_time = random.uniform(10, 20)
            logger.info(f"📱 Short {shorts_watched}/{max_shorts} - Watching for {watch_time:.1f}s")
            time.sleep(watch_time)
            
        elif action == "stay":
            logger.info("👀 Staying on current short longer")
            extra_time = random.uniform(5, 12)
            time.sleep(extra_time)
            
        elif action == "hover_then_next":
            logger.info("🖱️ Hovering on button, then moving to next short")
            _hover_random_shorts_button(page)
            time.sleep(random.uniform(1, 2))
            
            logger.info(f"🐭 Mouse wheel scroll → Next short")
            shorts_next_video(page, direction='down')
            stats["mouse_wheel_movements"] += 1
            current_position += 1
            
            shorts_watched += 1
            stats["shorts_watched"] = shorts_watched
            watch_time = random.uniform(10, 18)
            logger.info(f"📱 Short {shorts_watched}/{max_shorts} - Watching for {watch_time:.1f}s")
            time.sleep(watch_time)
            
        elif action == "return_previous":
            if current_position > 0:
                logger.info("⬆️ Mouse wheel scroll → Return to previous short")
                shorts_next_video(page, direction='up')
                stats["mouse_wheel_movements"] += 1
                stats["returns_to_original"] += 1
                current_position -= 1
                shorts_watched -= 1
                
                watch_time = random.uniform(8, 15)
                logger.info(f"📱 Short {shorts_watched}/{max_shorts} - Watching for {watch_time:.1f}s")
                time.sleep(watch_time)
        
        if session_duration_seconds and (time.time() - start_time) > session_duration_seconds:
            logger.info(f"Session duration limit reached ({session_duration_seconds}s)")
            break
    
    if stats["shorts_watched"] > 1 and random.random() < 0.4:
        logger.info("🔄 Returning to first short before leaving")
        while stats["shorts_watched"] > 1:
            shorts_next_video(page, direction='up')
            stats["mouse_wheel_movements"] += 1
            stats["shorts_watched"] -= 1
            time.sleep(random.uniform(0.8, 1.5))
    
    stats["time_spent"] = time.time() - start_time
    logger.info(f"✅ Shorts session complete: {stats['shorts_watched']} shorts, {stats['time_spent']:.1f}s")
    
    return stats


def _hover_random_shorts_button(page: Page):
    """Hover over a random shorts control button"""
    button_types = ["like", "share", "comment", "subscribe"]
    weights = [0.4, 0.3, 0.2, 0.1]
    choice = random.choices(button_types, weights=weights)[0]
    
    if choice == "like":
        try:
            like_btn = page.locator("button[aria-label*='like']").first
            if like_btn.count() > 0:
                like_btn.hover()
                time.sleep(random.uniform(0.3, 0.6))
                return True
        except:
            pass
    elif choice == "share":
        try:
            share_btn = page.locator("button[aria-label*='Share']").first
            if share_btn.count() > 0:
                share_btn.hover()
                time.sleep(random.uniform(0.3, 0.6))
                return True
        except:
            pass
    elif choice == "comment":
        try:
            comment_btn = page.locator("button[aria-label*='Comment']").first
            if comment_btn.count() > 0:
                comment_btn.hover()
                time.sleep(random.uniform(0.3, 0.6))
                return True
        except:
            pass
    elif choice == "subscribe":
        try:
            sub_btn = page.locator("button[aria-label*='Subscribe']").first
            if sub_btn.count() > 0:
                sub_btn.hover()
                time.sleep(random.uniform(0.3, 0.6))
                return True
        except:
            pass
    return False


# ========== Utility functions ==========
def get_variable_watch_time(min_seconds: int, max_seconds: int) -> int:
    """Get random watch time within range"""
    return random.randint(min_seconds, max_seconds)


def wait_for_url_change(page: Page, old_url: str, timeout: int = 5) -> bool:
    """Wait for URL to change from old_url"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            if page.url != old_url:
                return True
        except:
            pass
        time.sleep(0.3)
    return False