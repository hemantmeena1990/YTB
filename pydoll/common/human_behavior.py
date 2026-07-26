#!/usr/bin/env python3
"""
Pydoll-specific Human Behavior Functions
Uses Pydoll's native humanize=True for physics-based interactions
"""

import asyncio
import random
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ========== DELAYS ==========

async def human_delay(min_seconds: float = 0.5, max_seconds: float = 1.5):
    """Random human-like delay (async)"""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def cognitive_delay(action_type: str = "read"):
    """Simulate human cognitive processing time."""
    base_delays = {
        "read": (1.0, 3.0),
        "process": (0.5, 2.0),
        "decide": (0.8, 1.8),
        "move": (0.3, 0.8),
        "click": (0.1, 0.4),
        "scroll": (0.5, 1.5),
        "navigate": (0.8, 2.5),
        "watch": (5.0, 30.0),
    }
    
    min_delay, max_delay = base_delays.get(action_type, (0.5, 2.0))
    delay = random.uniform(min_delay, max_delay)
    await asyncio.sleep(delay)


# ========== SCROLLING ==========

async def scroll_element_into_view(page, element, instance_id: int = 0):
    """Scroll element into view smoothly before interaction."""
    try:
        await page.execute_script("""
            arguments[0].scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'center'
            });
        """, element)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        logger.debug(f"Instance {instance_id}: Scrolled element into view")
        return True
    except Exception as e:
        logger.debug(f"Instance {instance_id}: Scroll into view failed: {e}")
        return False


async def random_scroll(page, is_mobile: bool = False):
    """
    Perform a random scroll with human-like behavior.
    Ensures viewport dimensions remain consistent.
    """
    try:
        vp_w = await page.execute_script("return window.innerWidth;")
        vp_h = await page.execute_script("return window.innerHeight;")
        
        if is_mobile:
            scroll_amount = random.randint(100, 400)
        else:
            scroll_amount = random.randint(50, 300)
        
        direction = random.choice(['down', 'up'])
        if direction == 'down':
            await page.execute_script(f"window.scrollBy(0, {scroll_amount});")
        else:
            await page.execute_script(f"window.scrollBy(0, -{scroll_amount});")
        
        await asyncio.sleep(random.uniform(0.3, 1.0))
        
    except Exception as e:
        logger.debug(f"Scroll error: {e}")


async def simulate_mouse_wheel(page, delta_y: int, duration_ms: int = 100):
    """Simulate mouse wheel scroll using JavaScript"""
    try:
        script = """
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
        await page.execute_script(script, delta_y)
        await asyncio.sleep(duration_ms / 1000)
        return True
    except Exception as e:
        logger.debug(f"Mouse wheel error: {e}")
        return False


# ========== HUMANIZED CLICK FUNCTIONS ==========

async def humanized_click(page, element, instance_id: int = 0, scroll_first: bool = True):
    """
    Perform a humanized click on an element using Pydoll's native physics.
    - Scrolls element into view first (optional)
    - Uses humanize=True for Bezier curves, Fitts's Law, and physiological tremors
    - Adds cognitive delay before clicking
    """
    if not element:
        return False
    
    try:
        # Scroll element into view if requested
        if scroll_first:
            await scroll_element_into_view(page, element, instance_id)
        
        # Small cognitive delay before clicking (human reaction time)
        await asyncio.sleep(random.uniform(0.1, 0.4))
        
        # Click with Pydoll's native humanized physics
        await element.click(humanize=True)
        
        # Post-click delay (human takes time to process click)
        await asyncio.sleep(random.uniform(0.05, 0.2))
        
        logger.debug(f"Instance {instance_id}: ✅ Humanized click performed")
        return True
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Humanized click failed: {e}")
        return False


async def humanized_click_selector(page, selector: str, instance_id: int = 0, scroll_first: bool = True):
    """
    Find element by selector and perform a humanized click.
    """
    try:
        element = await page.find(selector=selector)
        if element:
            return await humanized_click(page, element, instance_id, scroll_first)
        else:
            logger.debug(f"Instance {instance_id}: Element not found: {selector}")
            return False
    except Exception as e:
        logger.debug(f"Instance {instance_id}: Selector click failed: {e}")
        return False


async def humanized_click_text(page, text: str, instance_id: int = 0, scroll_first: bool = True):
    """
    Find element by text and perform a humanized click.
    """
    try:
        element = await page.find(text=text)
        if element:
            return await humanized_click(page, element, instance_id, scroll_first)
        else:
            logger.debug(f"Instance {instance_id}: Element not found with text: {text}")
            return False
    except Exception as e:
        logger.debug(f"Instance {instance_id}: Text click failed: {e}")
        return False


async def humanized_mouse_move(page, x: int, y: int, instance_id: int = 0):
    """
    Move mouse to coordinates with human-like trajectory.
    """
    try:
        # Pydoll's mouse move with humanize=True creates Bezier curves
        await page.mouse.move(x, y, humanize=True)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        logger.debug(f"Instance {instance_id}: Mouse moved to ({x}, {y})")
        return True
    except Exception as e:
        logger.debug(f"Instance {instance_id}: Mouse move failed: {e}")
        return False


# ========== KEYBOARD & MOUSE ==========

async def random_key_press(page):
    """Random key press using Pydoll's keyboard"""
    if random.random() < 0.12:
        keys = ['ArrowDown', 'ArrowUp', 'Space', 'PageDown', 'PageUp']
        key = random.choice(keys)
        try:
            await page.keyboard.press(key)
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            if key == 'Space' and random.random() < 0.4:
                await asyncio.sleep(random.uniform(0.3, 0.8))
                await page.keyboard.press('Space')
        except Exception as e:
            logger.debug(f"Key press error: {e}")


async def random_mouse_movement(page):
    """Random mouse movement using Pydoll's mouse with humanize=True"""
    try:
        viewport = await page.execute_script("return {w: window.innerWidth, h: window.innerHeight}")
        x = random.randint(50, viewport['w'] - 50)
        y = random.randint(50, viewport['h'] - 50)
        await page.mouse.move(x, y, humanize=True)
        await asyncio.sleep(random.uniform(0.1, 0.3))
    except Exception as e:
        logger.debug(f"Mouse movement error: {e}")


# ========== VIDEO PLAYBACK ==========

async def is_video_playing(page) -> bool:
    """Check if video is playing"""
    try:
        result = await page.execute_script("""
            var videos = document.querySelectorAll('video');
            for (var i = 0; i < videos.length; i++) {
                var v = videos[i];
                if (v && !v.paused && !v.ended && v.readyState >= 2 && v.currentTime > 0) {
                    return true;
                }
            }
            return false;
        """)
        
        if isinstance(result, dict):
            result = result.get('result', {}).get('result', {}).get('value', False)
        
        return bool(result)
    except:
        return False


async def ensure_video_playback(page, instance_id: int = 0) -> bool:
    """Ensure video is playing using humanized clicks."""
    if await is_video_playing(page):
        logger.debug(f"Instance {instance_id}: Video already playing")
        return True
    
    logger.warning(f"Instance {instance_id}: Video not playing. Attempting start...")
    
    # Try spacebar first (most natural)
    for _ in range(2):
        try:
            await page.keyboard.press('Space')
        except:
            pass
        await asyncio.sleep(1)
        if await is_video_playing(page):
            logger.info(f"Instance {instance_id}: Started with SPACEBAR")
            return True
    
    # Try clicking video with humanized click
    try:
        video = await page.find(tag_name="video")
        if video:
            await humanized_click(page, video, instance_id, scroll_first=True)
            await asyncio.sleep(1)
            if await is_video_playing(page):
                logger.info(f"Instance {instance_id}: Started with video click (humanized)")
                return True
    except:
        pass
    
    # Try clicking player container
    try:
        player = await page.find(selector=".html5-video-player")
        if player:
            await humanized_click(page, player, instance_id, scroll_first=True)
            await asyncio.sleep(1)
            if await is_video_playing(page):
                logger.info(f"Instance {instance_id}: Started with player click (humanized)")
                return True
    except:
        pass
    
    # JavaScript fallback
    try:
        await page.execute_script("document.querySelector('video')?.play();")
        await asyncio.sleep(1)
        if await is_video_playing(page):
            logger.info(f"Instance {instance_id}: Started with JavaScript")
            return True
    except:
        pass
    
    logger.error(f"Instance {instance_id}: Failed to start video")
    return False


async def start_video_with_audio_mute(page, instance_id: int, is_mobile: bool = False, is_suggested: bool = False) -> bool:
    """Start video with audio mute after random delay."""
    try:
        mute_delay = random.choice([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        initial_volume = random.uniform(0.3, 0.8)
        logger.info(f"Instance {instance_id} {'(suggested)' if is_suggested else ''}: Volume {int(initial_volume*100)}%, mute in {mute_delay}s")
        
        if not await ensure_video_playback(page, instance_id):
            return False
        
        if is_mobile:
            try:
                video = await page.find(tag_name="video")
                if video:
                    await humanized_click(page, video, instance_id, scroll_first=True)
                    await asyncio.sleep(0.3)
            except:
                pass
        
        is_muted = await page.execute_script("var v = document.querySelector('video'); return v ? v.muted : false;")
        if is_muted:
            logger.info(f"Instance {instance_id}: Video was muted, unmuting now")
            await page.execute_script("document.querySelector('video').muted = false;")
            await asyncio.sleep(0.5)
        
        await page.execute_script(f"var v = document.querySelector('video'); if (v) v.volume = {initial_volume};")
        
        if mute_delay > 0:
            await page.execute_script(f"""
                setTimeout(function() {{
                    var v = document.querySelector('video');
                    if (v) v.muted = true;
                }}, {mute_delay * 1000});
            """)
        
        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Video start error - {e}")
        return False


async def attempt_video_playback_with_retry(page, instance_id: int, is_mobile: bool = False, 
                                             is_suggested: bool = False, max_retries: int = 3) -> bool:
    """Attempt to start video playback with retry logic using humanized clicks."""
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Instance {instance_id}: Retry attempt {attempt+1}/{max_retries}")
            await asyncio.sleep(random.uniform(2, 4))
            
            # ========== MOBILE: Click overlay with humanized click ==========
            if is_mobile:
                mobile_selectors = [
                    '.player-control-overlay',
                    '.ytp-play-button',
                    '.ytp-large-play-button',
                    'button[aria-label*="Play"]',
                    '.ytp-play-button.ytp-player-button'
                ]
                for selector in mobile_selectors:
                    try:
                        if await humanized_click_selector(page, selector, instance_id, scroll_first=True):
                            await asyncio.sleep(1.5)
                            if await is_video_playing(page):
                                logger.info(f"Instance {instance_id}: Started with mobile overlay click (attempt {attempt+1})")
                                return True
                    except:
                        pass
            
            # Try video element click with humanized click
            try:
                video = await page.find(tag_name="video")
                if video:
                    if await humanized_click(page, video, instance_id, scroll_first=True):
                        await asyncio.sleep(1.5)
                        if await is_video_playing(page):
                            logger.info(f"Instance {instance_id}: Started with video click (attempt {attempt+1})")
                            return True
            except:
                pass
            
            # Try spacebar
            try:
                await page.keyboard.press('Space')
            except:
                pass
            await asyncio.sleep(1.5)
            if await is_video_playing(page):
                logger.info(f"Instance {instance_id}: Started with spacebar (attempt {attempt+1})")
                return True
            
            # Try player container with humanized click
            try:
                player = await page.find(selector=".html5-video-player")
                if player:
                    if await humanized_click(page, player, instance_id, scroll_first=True):
                        await asyncio.sleep(1.5)
                        if await is_video_playing(page):
                            logger.info(f"Instance {instance_id}: Started with player click (attempt {attempt+1})")
                            return True
            except:
                pass
            
            # JavaScript fallback
            try:
                await page.execute_script("document.querySelector('video')?.play();")
                await asyncio.sleep(1.5)
                if await is_video_playing(page):
                    logger.info(f"Instance {instance_id}: Started with JavaScript (attempt {attempt+1})")
                    return True
            except:
                pass
        
        else:
            if await start_video_with_audio_mute(page, instance_id, is_mobile, is_suggested):
                return True
    
    logger.error(f"Instance {instance_id}: All {max_retries} playback attempts failed")
    return False


async def simulate_pause(page):
    """Simulate user pausing and resuming video with humanized click."""
    try:
        player = await page.find(selector=".html5-video-player")
        if player:
            await humanized_click(page, player, 0, scroll_first=True)
            await asyncio.sleep(random.uniform(3, 10))
            await humanized_click(page, player, 0, scroll_first=True)
            logger.info("Simulated user pause")
            return True
    except Exception as e:
        logger.debug(f"Pause error: {e}")
    return False



# ========== RECAPTCHA HANDLING ==========

async def handle_recaptcha(page, instance_id: int = 0) -> bool:
    """
    Handle reCAPTCHA natively using pydoll's stealth and humanized behavior.
    Works for reCAPTCHA v3 (invisible) and attempts v2 checkbox.
    Returns True if CAPTCHA was handled or not present.
    """
    try:
        logger.info(f"Instance {instance_id}: [CAPTCHA] Checking for reCAPTCHA...")
        
        # Wait a bit for CAPTCHA to load
        await asyncio.sleep(2)
        
        # ========== CHECK FOR reCAPTCHA v2 IFRAME ==========
        try:
            # Check for reCAPTCHA iframe
            iframe = await page.find(selector="iframe[src*='recaptcha/api2']")
            if iframe:
                logger.info(f"Instance {instance_id}: [CAPTCHA] reCAPTCHA v2 detected - attempting checkbox click")
                
                # Wait for iframe to load
                await asyncio.sleep(1)
                
                # Switch to iframe context
                # Note: Pydoll may have different API for frames
                try:
                    # Try to find the checkbox inside iframe
                    # The checkbox usually has role='checkbox' or aria-label='I'm not a robot'
                    await page.execute_script("""
                        var iframe = document.querySelector('iframe[src*="recaptcha/api2"]');
                        if (iframe) {
                            // Click on the checkbox inside the iframe
                            // This is a simplified approach
                            var rect = iframe.getBoundingClientRect();
                            var x = rect.left + rect.width / 2;
                            var y = rect.top + rect.height / 2;
                            
                            // Dispatch click event on the iframe
                            var event = new MouseEvent('click', {
                                clientX: x,
                                clientY: y,
                                bubbles: true
                            });
                            iframe.dispatchEvent(event);
                            return true;
                        }
                        return false;
                    """)
                    logger.info(f"Instance {instance_id}: [CAPTCHA] Checkbox clicked")
                    await asyncio.sleep(2)
                    return True
                except Exception as e:
                    logger.debug(f"Instance {instance_id}: [CAPTCHA] Iframe click failed: {e}")
        except Exception as e:
            logger.debug(f"Instance {instance_id}: [CAPTCHA] No v2 iframe found: {e}")
        
        # ========== CHECK FOR reCAPTCHA v3 (invisible) ==========
        try:
            # Check if reCAPTCHA v3 is present
            badge = await page.find(selector=".grecaptcha-badge")
            if badge:
                logger.info(f"Instance {instance_id}: [CAPTCHA] reCAPTCHA v3 detected (badge visible)")
                # v3 is passive - just ensure natural behavior
                # The heartbeat and humanized clicks already provide this
                logger.info(f"Instance {instance_id}: [CAPTCHA] reCAPTCHA v3 will be handled natively")
                return True
        except Exception as e:
            logger.debug(f"Instance {instance_id}: [CAPTCHA] No v3 badge found: {e}")
        
        # ========== CHECK FOR RECAPTCHA RESPONSE FIELD ==========
        try:
            # Check if there's a hidden response field (indicates CAPTCHA is present)
            response_field = await page.find(selector="#g-recaptcha-response")
            if response_field:
                # Check if it has a value (already solved)
                value = await page.execute_script("return document.getElementById('g-recaptcha-response').value;")
                if value and len(value) > 10:
                    logger.info(f"Instance {instance_id}: [CAPTCHA] Already solved (has value)")
                    return True
                else:
                    logger.info(f"Instance {instance_id}: [CAPTCHA] reCAPTCHA response field found but empty")
                    # Try to solve by clicking the checkbox if visible
                    try:
                        await page.execute_script("""
                            var checkbox = document.querySelector('.recaptcha-checkbox-border');
                            if (checkbox) {
                                checkbox.click();
                                return true;
                            }
                            return false;
                        """)
                        logger.info(f"Instance {instance_id}: [CAPTCHA] Checkbox clicked via JavaScript")
                        await asyncio.sleep(2)
                        return True
                    except:
                        pass
        except Exception as e:
            logger.debug(f"Instance {instance_id}: [CAPTCHA] Response field check failed: {e}")
        
        # ========== NATIVE BEHAVIOR FOR TRUST SCORE ==========
        # If reCAPTCHA is present, perform human-like interactions
        # This increases the trust score for v3
        
        # Human-like scroll to show engagement
        await page.execute_script("window.scrollBy(0, Math.floor(Math.random() * 300) + 100);")
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.execute_script("window.scrollBy(0, Math.floor(Math.random() * -100) - 50);")
        await asyncio.sleep(random.uniform(0.3, 0.8))
        
        # Random mouse movement to mimic human - FIXED
        try:
            viewport = await page.execute_script("return {width: window.innerWidth, height: window.innerHeight}")
            # Unpack Pydoll's nested response structure
            if isinstance(viewport, dict):
                # Handle nested result structure
                if 'result' in viewport and isinstance(viewport['result'], dict):
                    inner = viewport['result']
                    if 'value' in inner:
                        viewport = inner['value']
                    elif 'result' in inner:
                        viewport = inner['result']
                elif 'value' in viewport:
                    viewport = viewport['value']
            
            if viewport and isinstance(viewport, dict):
                width = viewport.get('width', 0)
                height = viewport.get('height', 0)
                if width > 100 and height > 100:
                    x = random.randint(50, width - 50)
                    y = random.randint(50, height - 50)
                    await page.mouse.move(x, y, humanize=True)
                    await asyncio.sleep(random.uniform(0.2, 0.5))
        except Exception as e:
            logger.debug(f"Instance {instance_id}: [CAPTCHA] Mouse movement failed: {e}")
        
        logger.info(f"Instance {instance_id}: [CAPTCHA] Humanized interactions performed")
        return True
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: [CAPTCHA] Error handling reCAPTCHA: {e}")
        return True  # Return True to continue execution, even if CAPTCHA handling fails


# ========== WATCHING ==========

async def watch_with_human_behavior(page, duration: int, is_mobile: bool = False, cfg=None, instance_id: int = 0, heartbeat_func=None):
    """
    Watch video with human-like behavior.
    Uses existing heartbeat (started early) - does NOT start a new one.
    The heartbeat was already started in watch_direct_async and runs in background.
    """
    logger.info(f"Instance {instance_id}: Starting human behavior for {duration}s")
    
    start_time = time.time()
    elapsed = 0
    next_action = random.randint(5, 15)
    paused = False
    
    try:
        original_vp_w = await page.execute_script("return window.innerWidth;")
        original_vp_h = await page.execute_script("return window.innerHeight;")
    except:
        original_vp_w = original_vp_h = None
    
    try:
        while elapsed < duration:
            remaining = duration - elapsed
            
            if remaining < next_action:
                await asyncio.sleep(remaining)
                break
            
            await asyncio.sleep(next_action)
            elapsed = time.time() - start_time
            
            r = random.random()
            if r < 0.4:
                await random_scroll(page, is_mobile)
            elif r < 0.7:
                await random_mouse_movement(page)
            else:
                await random_key_press(page)
            
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                try:
                    await page.execute_script("""
                        window.scrollBy(0, Math.random() * 2 - 1);
                        var event = new MouseEvent('mousemove', {
                            clientX: window.innerWidth / 2 + (Math.random() * 10 - 5),
                            clientY: window.innerHeight / 2 + (Math.random() * 10 - 5)
                        });
                        document.dispatchEvent(event);
                    """)
                    logger.debug(f"Instance {instance_id}: Micro-interaction performed")
                except:
                    pass
            
            if not paused and random.random() < 0.06 and duration > 30:
                if await simulate_pause(page):
                    paused = True
            
            next_action = random.expovariate(0.12) + random.uniform(2, 8)
            next_action = min(max(next_action, 4), 20)
            
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                logger.info(f"Instance {instance_id}: Watch progress: {int(elapsed)}/{duration}s")
        
        logger.info(f"Instance {instance_id}: Watch complete")
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error during watch: {e}")
        raise


# ========== POPUPS & COOKIES ==========

async def handle_consent_popups(page, instance_id: int = 0) -> bool:
    """
    Handle consent popups using Pydoll's native methods with humanized clicks.
    """
    try:
        await asyncio.sleep(2)
        
        # ========== METHOD 1: Find by text content ==========
        consent_texts = [
            'Accept all', 'I agree', 'Accept', 'Got it', 'OK',
            'Agree', 'Continue', 'Allow', 'Dismiss', 'Close',
            'No thanks', 'Skip', 'Next', 'Accept All'
        ]
        
        for text in consent_texts:
            try:
                button = await page.find(text=text)
                if button:
                    is_visible = await button.is_visible()
                    if is_visible:
                        logger.info(f"Instance {instance_id}: Found consent popup - clicking: {text}")
                        await humanized_click(page, button, instance_id, scroll_first=True)
                        await asyncio.sleep(random.uniform(1, 2))
                        return True
            except Exception as e:
                logger.debug(f"Instance {instance_id}: Text search '{text}' failed: {e}")
                continue
        
        # ========== METHOD 2: Find by aria-label ==========
        aria_labels = [
            'Accept all', 'Accept', 'I agree', 'Agree', 
            'Got it', 'OK', 'Dismiss', 'Close'
        ]
        
        for label in aria_labels:
            try:
                button = await page.find(aria_label=label)
                if button:
                    is_visible = await button.is_visible()
                    if is_visible:
                        logger.info(f"Instance {instance_id}: Found consent popup via aria-label - clicking: {label}")
                        await humanized_click(page, button, instance_id, scroll_first=True)
                        await asyncio.sleep(random.uniform(1, 2))
                        return True
            except Exception as e:
                logger.debug(f"Instance {instance_id}: Aria-label search '{label}' failed: {e}")
                continue
        
        # ========== METHOD 3: Find by CSS selector ==========
        selectors = [
            'button[aria-label*="Accept"]',
            'button[aria-label*="accept"]',
            'button[aria-label*="Agree"]',
            'button[aria-label*="agree"]',
            'button[aria-label*="Got it"]',
            'button[aria-label*="got it"]',
            'button[aria-label*="OK"]',
            'button[aria-label*="Dismiss"]',
            'button[aria-label*="Close"]',
            'button[aria-label*="close"]',
            'button[aria-label*="consent"]',
            'button[aria-label*="Consent"]',
            '#accept-consent',
            '#consent-accept',
            '.consent-accept',
            '.accept-all',
            '.accept',
            '[data-action="accept"]',
            '[data-action="Accept"]',
            '.yt-spec-button-shape-next',
            'button[jsname="V67aGc"]',
            'button[jsname="XSnjRc"]',
            'button[aria-label="Accept all"]',
            'button[aria-label="I agree"]',
            'button[aria-label="Got it"]',
        ]
        
        for selector in selectors:
            try:
                buttons = await page.find_all(selector)
                for button in buttons:
                    is_visible = await button.is_visible()
                    if is_visible:
                        logger.info(f"Instance {instance_id}: Found consent popup via selector - clicking: {selector}")
                        await humanized_click(page, button, instance_id, scroll_first=True)
                        await asyncio.sleep(random.uniform(1, 2))
                        return True
            except Exception as e:
                logger.debug(f"Instance {instance_id}: Selector '{selector}' failed: {e}")
                continue
        
        # ========== METHOD 4: JavaScript fallback ==========
        try:
            result = await page.execute_script("""
                (function() {
                    var selectors = [
                        'button[aria-label*="Accept"]',
                        'button[aria-label*="accept"]',
                        'button[aria-label*="Agree"]',
                        'button[aria-label*="agree"]',
                        'button[aria-label*="Got it"]',
                        'button[aria-label*="got it"]',
                        'button[aria-label*="OK"]',
                        'button[aria-label*="Dismiss"]',
                        'button[aria-label*="Close"]',
                        'button[aria-label*="close"]',
                        '#accept-consent',
                        '#consent-accept',
                        '.consent-accept',
                        '.accept-all',
                        '.accept',
                        '.yt-spec-button-shape-next'
                    ];
                    
                    for (var i = 0; i < selectors.length; i++) {
                        var elements = document.querySelectorAll(selectors[i]);
                        for (var j = 0; j < elements.length; j++) {
                            var el = elements[j];
                            var rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                el.click();
                                return true;
                            }
                        }
                    }
                    
                    var buttons = document.querySelectorAll('button');
                    var consentTexts = ['accept all', 'i agree', 'accept', 'got it', 'ok', 'agree', 'continue', 'allow', 'dismiss', 'close'];
                    for (var i = 0; i < buttons.length; i++) {
                        var text = buttons[i].innerText.toLowerCase();
                        for (var j = 0; j < consentTexts.length; j++) {
                            if (text.includes(consentTexts[j])) {
                                buttons[i].click();
                                return true;
                            }
                        }
                    }
                    return false;
                })();
            """)
            if result:
                logger.info(f"Instance {instance_id}: Consent handled via JavaScript fallback")
                await asyncio.sleep(random.uniform(1, 2))
                return True
        except Exception as e:
            logger.debug(f"Instance {instance_id}: JavaScript fallback failed: {e}")
        
        return False
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Consent handling error - {e}")
        return False


async def handle_all_popups(page, instance_id, max_attempts=5):
    """
    Handle all YouTube popups using Pydoll's native methods with humanized clicks.
    """
    logger.debug(f"Instance {instance_id}: Checking for popups...")
    
    handled = False
    
    # ========== METHOD 1: Pydoll Native find_element with selectors ==========
    popup_selectors = [
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('Allow')",
        "button:has-text('OK')",
        "[aria-label='Accept all']",
        "#accept-button",
        "button[aria-label='No thanks']",
        "button[aria-label='Skip']",
        "button[aria-label='Dismiss']",
        "[aria-label='Close']",
        "button[aria-label='Close']",
        "#dismiss-button",
        "button[aria-label='Not interested']",
        "button:has-text('No thanks')",
        "button:has-text('Skip')",
        "button:has-text('Dismiss')",
        "button:has-text('Close')",
    ]
    
    for attempt in range(max_attempts):
        try:
            for selector in popup_selectors:
                try:
                    elements = await page.find_elements(selector)
                    if elements:
                        for element in elements:
                            try:
                                is_visible = await element.is_visible() if hasattr(element, 'is_visible') else True
                                if is_visible:
                                    await humanized_click(page, element, instance_id, scroll_first=True)
                                    handled = True
                                    logger.debug(f"Instance {instance_id}: ✅ Clicked popup via selector: {selector}")
                                    await asyncio.sleep(0.3)
                                    break
                            except:
                                continue
                        if handled:
                            break
                except Exception:
                    continue
            
            if handled:
                break
                
        except Exception as e:
            logger.debug(f"Instance {instance_id}: Native popup handling attempt {attempt+1} failed: {e}")
        
        # ========== METHOD 2: JavaScript fallback ==========
        if not handled:
            try:
                js_result = await page.execute_script("""
                    function handlePopups() {
                        var handled = false;
                        
                        var cookieTexts = ['Accept all', 'Accept', 'Allow', 'OK'];
                        var allButtons = document.querySelectorAll('button, a, [role="button"]');
                        for (var i = 0; i < allButtons.length; i++) {
                            var text = allButtons[i].textContent || allButtons[i].innerText || '';
                            for (var c = 0; c < cookieTexts.length; c++) {
                                if (text.trim() === cookieTexts[c] || text.includes(cookieTexts[c])) {
                                    if (allButtons[i].offsetParent !== null) {
                                        allButtons[i].click();
                                        handled = true;
                                        return true;
                                    }
                                }
                            }
                        }
                        
                        var selectors = [
                            'button[aria-label="No thanks"]',
                            'button[aria-label="Skip"]',
                            'button[aria-label="Dismiss"]',
                            '[aria-label="Close"]',
                            'button[aria-label="Close"]',
                            '#dismiss-button',
                            'button[aria-label="Not interested"]'
                        ];
                        
                        for (var s = 0; s < selectors.length; s++) {
                            var elements = document.querySelectorAll(selectors[s]);
                            for (var e = 0; e < elements.length; e++) {
                                if (elements[e].offsetParent !== null) {
                                    elements[e].click();
                                    handled = true;
                                    return true;
                                }
                            }
                        }
                        
                        var popupTexts = ['No thanks', 'Skip', 'Dismiss', 'Close', 'Not interested'];
                        for (var i = 0; i < allButtons.length; i++) {
                            var text = allButtons[i].textContent || allButtons[i].innerText || '';
                            for (var p = 0; p < popupTexts.length; p++) {
                                if (text.trim() === popupTexts[p]) {
                                    if (allButtons[i].offsetParent !== null) {
                                        allButtons[i].click();
                                        handled = true;
                                        return true;
                                    }
                                }
                            }
                        }
                        
                        return handled;
                    }
                    return handlePopups();
                """)
                
                if js_result:
                    handled = True
                    logger.debug(f"Instance {instance_id}: ✅ JavaScript fallback handled popup")
                    break
                    
            except Exception as e:
                logger.debug(f"Instance {instance_id}: JS fallback failed: {e}")
        
        # ========== METHOD 3: CDP-based click ==========
        if not handled and hasattr(page, '_cdp_client') and page._cdp_client:
            try:
                cdp_result = await page.execute_script("""
                    var selectors = [
                        '[aria-label*="Accept"]',
                        '[aria-label*="allow"]',
                        '[aria-label*="No thanks"]',
                        '[aria-label*="Skip"]',
                        '[aria-label*="Dismiss"]'
                    ];
                    
                    for (var s = 0; s < selectors.length; s++) {
                        var elements = document.querySelectorAll(selectors[s]);
                        for (var e = 0; e < elements.length; e++) {
                            if (elements[e].offsetParent !== null) {
                                var text = elements[e].textContent || '';
                                if (text.includes('Accept') || text.includes('Allow') || 
                                    text.includes('No thanks') || text.includes('Skip') ||
                                    text.includes('Dismiss') || text.includes('Close')) {
                                    elements[e].click();
                                    return true;
                                }
                            }
                        }
                    }
                    return false;
                """)
                
                if cdp_result:
                    handled = True
                    logger.debug(f"Instance {instance_id}: ✅ CDP-based handling succeeded")
                    break
                    
            except Exception as e:
                logger.debug(f"Instance {instance_id}: CDP handling failed: {e}")
        
        # ========== METHOD 4: Wait and retry ==========
        if not handled and attempt < max_attempts - 1:
            await asyncio.sleep(0.5)
    
    if handled:
        logger.debug(f"Instance {instance_id}: ✅ Popup handling complete")
    else:
        logger.debug(f"Instance {instance_id}: No popups found or unable to handle")
    
    return handled


# ========== SUGGESTED VIDEO ==========

async def click_suggested_video(page, is_mobile: bool = False, instance_id: int = 0) -> str:
    """
    Find, click, and navigate to a random suggested video with humanized click.
    """
    try:
        current_url = await page.execute_script("return window.location.href;")
        current_vid = None
        if isinstance(current_url, str):
            if 'v=' in current_url:
                current_vid = current_url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in current_url:
                current_vid = current_url.split('youtu.be/')[1].split('?')[0]
        
        logger.info(f"Instance {instance_id}: Current video ID: {current_vid}")
        
        # Scroll to load suggestions
        await page.execute_script("window.scrollBy(0, 400);")
        await asyncio.sleep(1.5)
        await page.execute_script("window.scrollBy(0, 400);")
        await asyncio.sleep(1.5)
        
        js_code = """
            (function() {
                var currentVid = arguments[0];
                var links = document.querySelectorAll('a[href*="/watch?v="]');
                var candidates = [];
                
                for (var i = 0; i < links.length; i++) {
                    var href = links[i].href;
                    if (href && href.indexOf('/watch?v=') !== -1) {
                        if (currentVid && href.indexOf(currentVid) !== -1) {
                            continue;
                        }
                        var rect = links[i].getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            candidates.push({
                                element: links[i],
                                href: href
                            });
                        }
                    }
                }
                
                if (candidates.length === 0) {
                    return null;
                }
                
                var randomIndex = Math.floor(Math.random() * candidates.length);
                var selected = candidates[randomIndex];
                
                // Scroll to element
                selected.element.scrollIntoView({block: 'center', behavior: 'smooth'});
                
                // Return the element and href as a tuple
                return {
                    href: selected.href,
                    element: selected.element
                };
            })();
        """
        
        result = await page.execute_script(js_code, current_vid)
        
        if result is None:
            logger.warning(f"Instance {instance_id}: No suggested video links found")
            return None
        
        # Extract href and element from result
        clicked_url = None
        element = None
        
        if isinstance(result, dict):
            # Unpack Pydoll's nested response
            if 'result' in result:
                inner = result['result']
                if isinstance(inner, dict) and 'value' in inner:
                    val = inner['value']
                    if isinstance(val, dict):
                        clicked_url = val.get('href')
                        # element is not directly usable from JS result
                else:
                    clicked_url = result.get('href')
            else:
                clicked_url = result.get('href')
            
            # If URL contains video ID, we can click via JavaScript
            if clicked_url and '/watch?v=' in clicked_url:
                # Use humanized click via JavaScript with scroll
                await page.execute_script(f"""
                    (function() {{
                        var links = document.querySelectorAll('a[href*="/watch?v="]');
                        for (var i = 0; i < links.length; i++) {{
                            if (links[i].href && links[i].href.indexOf('{clicked_url.split('v=')[1][:11]}') !== -1) {{
                                links[i].scrollIntoView({{block: 'center', behavior: 'smooth'}});
                                setTimeout(function() {{
                                    links[i].click();
                                }}, 300);
                                return true;
                            }}
                        }}
                        return false;
                    }})();
                """)
                await asyncio.sleep(1)
        
        if not clicked_url:
            logger.warning(f"Instance {instance_id}: Could not extract URL from result")
            return None
        
        logger.info(f"Instance {instance_id}: ✅ Clicked suggested video: {clicked_url[:80]}...")
        
        # Wait for navigation
        await asyncio.sleep(2)
        
        for attempt in range(10):
            try:
                ready_state = await page.execute_script("return document.readyState;")
                if ready_state == "complete":
                    break
            except:
                pass
            await asyncio.sleep(0.5)
        
        await asyncio.sleep(1)
        
        return clicked_url
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error clicking suggested video: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


# ========== SHORTS FUNCTIONS ==========

async def shorts_next_video(page, direction: str = 'down'):
    """Navigate to next/previous short using mouse wheel."""
    if direction == 'down':
        delta_y = random.randint(600, 900)
    else:
        delta_y = random.randint(-900, -600)
    
    await simulate_mouse_wheel(page, delta_y)
    await asyncio.sleep(random.uniform(1.5, 3))
    
    if random.random() < 0.3:
        await asyncio.sleep(0.5)
        await simulate_mouse_wheel(page, random.randint(50, 150))
    
    return True


async def shorts_swipe_with_hesitation(page, direction: str = 'down'):
    """Simulate a human-like swipe with hesitation (pause mid-scroll)"""
    if direction == 'down':
        await simulate_mouse_wheel(page, random.randint(200, 400))
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await simulate_mouse_wheel(page, random.randint(400, 600))
    else:
        await simulate_mouse_wheel(page, random.randint(-500, -300))
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await simulate_mouse_wheel(page, random.randint(-400, -200))
    
    await asyncio.sleep(random.uniform(1, 2))


async def watch_shorts_with_human_behavior(page, max_shorts: int = 2, session_duration_seconds: Optional[int] = None):
    """Watch YouTube Shorts with human-like behavior."""
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
    current_url = await page.execute_script("window.location.href")
    
    if '/shorts/' not in current_url:
        logger.info("Navigating to YouTube Shorts")
        await page.go_to("https://www.youtube.com/shorts")
        await asyncio.sleep(3)
        await handle_all_popups(page, 0)
    
    shorts_watched = 1
    stats["shorts_watched"] = shorts_watched
    
    watch_time = random.uniform(12, 25)
    await asyncio.sleep(watch_time)
    
    while shorts_watched < max_shorts:
        action = random.choices(
            ["next", "stay", "hover_then_next", "return_previous"],
            weights=[0.6, 0.2, 0.1, 0.1]
        )[0]
        
        if action in ["next", "hover_then_next"]:
            if action == "hover_then_next":
                await asyncio.sleep(random.uniform(1, 2))
            
            await shorts_next_video(page, direction='down')
            stats["mouse_wheel_movements"] += 1
            
            shorts_watched += 1
            stats["shorts_watched"] = shorts_watched
            
            watch_time = random.uniform(10, 20)
            await asyncio.sleep(watch_time)
            
        elif action == "stay":
            extra_time = random.uniform(5, 12)
            await asyncio.sleep(extra_time)
            
        elif action == "return_previous":
            if shorts_watched > 1:
                await shorts_next_video(page, direction='up')
                stats["mouse_wheel_movements"] += 1
                stats["returns_to_original"] += 1
                shorts_watched -= 1
                watch_time = random.uniform(8, 15)
                await asyncio.sleep(watch_time)
        
        if session_duration_seconds and (time.time() - start_time) > session_duration_seconds:
            break
    
    stats["time_spent"] = time.time() - start_time
    logger.info(f"Instance: Shorts complete: {stats['shorts_watched']} shorts, {stats['time_spent']:.1f}s")
    
    return stats


async def navigate_shorts_with_fallback(page, direction: str = 'next', max_attempts: int = 3) -> bool:
    """Navigate shorts using fallback chain."""
    old_url = await page.execute_script("window.location.href")
    
    delay = random.uniform(0, 3)
    logger.debug(f"Waiting {delay:.1f}s before {direction} short navigation")
    await asyncio.sleep(delay)
    
    for attempt in range(max_attempts):
        delta_y = random.randint(600, 900) if direction == 'next' else random.randint(-900, -600)
        await simulate_mouse_wheel(page, delta_y)
        await asyncio.sleep(1.2)
        
        current_url = await page.execute_script("window.location.href")
        if current_url != old_url:
            logger.info(f"Navigation succeeded with mouse wheel (attempt {attempt+1})")
            return True
        await asyncio.sleep(0.5)
    
    logger.info(f"Mouse wheel failed, trying {direction} button click")
    button = await find_shorts_navigation_button(page, direction)
    if button:
        try:
            await humanized_click(page, button, 0, scroll_first=True)
            await asyncio.sleep(1.5)
            current_url = await page.execute_script("window.location.href")
            if current_url != old_url:
                logger.info(f"Navigation succeeded with {direction} button click")
                return True
        except:
            pass
    
    logger.info(f"Button click failed, using arrow {direction} key")
    key = 'ArrowDown' if direction == 'next' else 'ArrowUp'
    try:
        await page.keyboard.press(key)
    except:
        pass
    await asyncio.sleep(2)
    current_url = await page.execute_script("window.location.href")
    
    return current_url != old_url


async def find_shorts_navigation_button(page, direction: str = 'next'):
    """Find the next/previous short navigation button."""
    if direction == 'next':
        selectors = [
            "button[aria-label='Next video']",
            "button[aria-label='Next']",
            "div[aria-label='Next video']",
            ".yt-spec-touch-feedback-shape-fill",
            "div[role='button'][aria-label*='Next']"
        ]
    else:
        selectors = [
            "button[aria-label='Previous video']",
            "button[aria-label='Previous']",
            "div[aria-label='Previous video']",
            "div[role='button'][aria-label*='Previous']"
        ]
    
    for selector in selectors:
        try:
            elements = await page.find_all(selector)
            for elem in elements:
                if await elem.is_visible():
                    return elem
        except:
            continue
    return None


async def click_shorts_navigation_button(page, direction: str = 'next') -> bool:
    """Click the next/previous short navigation button with humanized click."""
    button = await find_shorts_navigation_button(page, direction)
    if button:
        try:
            await humanized_click(page, button, 0, scroll_first=True)
            await asyncio.sleep(random.uniform(0.2, 0.5))
            logger.debug(f"Clicked {direction} shorts navigation button")
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.debug(f"Failed to click {direction} button: {e}")
    return False


async def _hover_like_button_only(page):
    """Hover over like button without clicking."""
    try:
        like_selectors = [
            "button[aria-label*='like this video']",
            "button[aria-label*='like']",
            "#segmented-like-button",
            "ytd-segmented-like-dislike-button-renderer button:first-child"
        ]
        
        for selector in like_selectors:
            try:
                like_btn = await page.find(selector=selector)
                if like_btn and await like_btn.is_visible():
                    await like_btn.hover()
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    logger.debug("Hovered over like button")
                    return True
            except:
                continue
    except Exception as e:
        logger.debug(f"Hover like failed: {e}")
    
    return False


async def _hover_share_button_only(page):
    """Hover over share button without clicking."""
    try:
        share_selectors = [
            "button[aria-label*='Share']",
            "button[aria-label*='share']",
            "ytd-button-renderer button[aria-label*='Share']"
        ]
        
        for selector in share_selectors:
            try:
                share_btn = await page.find(selector=selector)
                if share_btn and await share_btn.is_visible():
                    await share_btn.hover()
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    logger.debug("Hovered over share button")
                    return True
            except:
                continue
    except Exception as e:
        logger.debug(f"Hover share failed: {e}")
    
    return False


async def _hover_random_shorts_button(page):
    """Hover over a random shorts control button."""
    button_types = ["like", "share", "comment", "subscribe"]
    weights = [0.4, 0.3, 0.2, 0.1]
    
    choice = random.choices(button_types, weights=weights)[0]
    
    if choice == "like":
        return await _hover_like_button_only(page)
    elif choice == "share":
        return await _hover_share_button_only(page)
    elif choice == "comment":
        try:
            comment_selectors = [
                "button[aria-label*='Comment']",
                "button[aria-label*='comment']"
            ]
            for selector in comment_selectors:
                comment_btn = await page.find(selector=selector)
                if comment_btn and await comment_btn.is_visible():
                    await comment_btn.hover()
                    await asyncio.sleep(random.uniform(0.3, 0.6))
                    return True
        except:
            pass
    elif choice == "subscribe":
        try:
            sub_selectors = [
                "button[aria-label*='Subscribe']",
                "#subscribe-button button"
            ]
            for selector in sub_selectors:
                sub_btn = await page.find(selector=selector)
                if sub_btn and await sub_btn.is_visible():
                    await sub_btn.hover()
                    await asyncio.sleep(random.uniform(0.3, 0.6))
                    return True
        except:
            pass
    
    return False


# ========== URL CHANGE DETECTION ==========

async def wait_for_url_change(page, old_url: str, timeout: int = 5) -> bool:
    """Wait for URL to change from old_url."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            current_url = await page.execute_script("window.location.href")
            if current_url != old_url:
                return True
        except:
            pass
        await asyncio.sleep(0.3)
    return False


# ========== NATURAL SESSION FLOW ==========

async def natural_session_flow(page, video_id: str, instance_id: int, search_term: Optional[str] = None, view_type: Optional[str] = None):
    """Simulate a natural browsing session before watching."""
    try:
        logger.info(f"Instance {instance_id}: Starting natural session flow")
        
        await page.go_to("https://www.youtube.com")
        await cognitive_delay("read")
        
        for _ in range(random.randint(1, 3)):
            await random_scroll(page, is_mobile=False)
            await cognitive_delay("scroll")
        
        await cognitive_delay("process")
        
        if search_term:
            search_box = await page.find(name="search_query")
            if search_box:
                for char in search_term[:60]:
                    await search_box.type_text(char)
                    await asyncio.sleep(random.uniform(0.08, 0.25))
                
                await cognitive_delay("decide")
                await search_box.press('Enter')
                
                await cognitive_delay("read")
                await random_scroll(page, is_mobile=False)
                await cognitive_delay("process")
                
                links = await page.find_all(f"a[href*='{video_id}']")
                if links:
                    video_link = links[0]
                else:
                    links = await page.find_all("a[href*='/watch?v=']")
                    video_link = None
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and video_id in href:
                            video_link = link
                            break
                
                if video_link:
                    await humanized_click(page, video_link, instance_id, scroll_first=True)
                    await cognitive_delay("navigate")
                else:
                    await page.go_to(f"https://www.youtube.com/watch?v={video_id}")
                    await cognitive_delay("navigate")
        else:
            await page.go_to(f"https://www.youtube.com/watch?v={video_id}")
            await cognitive_delay("navigate")
        
        logger.info(f"Instance {instance_id}: Natural session flow completed")
        return True
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Natural session flow failed: {e}")
        try:
            await page.go_to(f"https://www.youtube.com/watch?v={video_id}")
        except:
            pass
        return False


# ========== UTILITY ==========

def get_variable_watch_time(min_time: int, max_time: int) -> int:
    """Get a variable watch time based on human-like distribution."""
    distribution = random.choices(
        population=['short', 'medium', 'long', 'full'],
        weights=[0.3, 0.4, 0.2, 0.1],
        k=1
    )[0]
    video_range = max_time - min_time
    
    if distribution == 'short':
        return min_time + int(video_range * random.uniform(0.2, 0.4))
    elif distribution == 'medium':
        return min_time + int(video_range * random.uniform(0.4, 0.7))
    elif distribution == 'long':
        return min_time + int(video_range * random.uniform(0.7, 0.95))
    else:
        return max_time + random.randint(-10, 10)


# ========== EXPORTS ==========

__all__ = [
    'human_delay',
    'cognitive_delay',
    'random_scroll',
    'simulate_mouse_wheel',
    'random_key_press',
    'random_mouse_movement',
    'is_video_playing',
    'ensure_video_playback',
    'start_video_with_audio_mute',
    'attempt_video_playback_with_retry',
    'simulate_pause',
    'watch_with_human_behavior',
    'handle_consent_popups',
    'handle_all_popups',
    'click_suggested_video',
    'shorts_next_video',
    'shorts_swipe_with_hesitation',
    'watch_shorts_with_human_behavior',
    'navigate_shorts_with_fallback',
    'find_shorts_navigation_button',
    'click_shorts_navigation_button',
    '_hover_like_button_only',
    '_hover_share_button_only',
    '_hover_random_shorts_button',
    'wait_for_url_change',
    'natural_session_flow',
    'get_variable_watch_time',
    'humanized_click',
    'humanized_click_selector',
    'humanized_click_text',
    'humanized_mouse_move',
    'scroll_element_into_view',
    'handle_recaptcha',
]