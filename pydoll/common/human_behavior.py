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

async def random_scroll(page, is_mobile: bool = False):
    """Random scroll using Pydoll's execute_script"""
    try:
        if is_mobile:
            amount = random.randint(100, 500)
        else:
            amount = random.randint(80, 400)
        
        await page.execute_script(f"window.scrollBy({{top: {amount}, behavior: 'smooth'}})")
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        if random.random() < 0.3:
            back_amount = random.randint(20, 100) * (1 if random.random() < 0.7 else -1)
            await page.execute_script(f"window.scrollBy(0, {back_amount})")
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        return True
    except Exception as e:
        logger.debug(f"Scroll error: {e}")
        return False


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
    """Random mouse movement using Pydoll's mouse"""
    try:
        viewport = await page.execute_script("return {w: window.innerWidth, h: window.innerHeight}")
        x = random.randint(50, viewport['w'] - 50)
        y = random.randint(50, viewport['h'] - 50)
        await page.mouse.move(x, y)
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
        
        # Unpack Pydoll's CDP dictionary response
        if isinstance(result, dict):
            result = result.get('result', {}).get('result', {}).get('value', False)
        
        return bool(result)
    except:
        return False


async def ensure_video_playback(page, instance_id: int = 0) -> bool:
    """Ensure video is playing."""
    if await is_video_playing(page):
        logger.debug(f"Instance {instance_id}: Video already playing")
        return True
    
    logger.warning(f"Instance {instance_id}: Video not playing. Attempting start...")
    
    for _ in range(2):
        try:
            await page.keyboard.press('Space')
        except:
            pass
        await asyncio.sleep(1)
        if await is_video_playing(page):
            logger.info(f"Instance {instance_id}: Started with SPACEBAR")
            return True
    
    try:
        video = await page.find(tag_name="video")
        if video:
            # ✅ Use Pydoll's native humanize=True for physics click
            await video.click(humanize=True)
            await asyncio.sleep(1)
            if await is_video_playing(page):
                logger.info(f"Instance {instance_id}: Started with CLICK (humanized)")
                return True
    except:
        pass
    
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
                    await video.click(humanize=True)
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
    """Attempt to start video playback with retry logic."""
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Instance {instance_id}: Retry attempt {attempt+1}/{max_retries}")
            await asyncio.sleep(random.uniform(2, 4))
            
            # ========== MOBILE: Click overlay first ==========
            if is_mobile:
                # Try mobile-specific play button/overlay
                mobile_selectors = [
                    '.player-control-overlay',
                    '.ytp-play-button',
                    '.ytp-large-play-button',
                    'button[aria-label*="Play"]',
                    '.ytp-play-button.ytp-player-button'
                ]
                for selector in mobile_selectors:
                    try:
                        overlay = await page.find(selector=selector)
                        if overlay:
                            await overlay.click(humanize=True)
                            await asyncio.sleep(1.5)
                            if await is_video_playing(page):
                                logger.info(f"Instance {instance_id}: Started with mobile overlay click (attempt {attempt+1})")
                                return True
                    except:
                        pass
            
            # Try video element click (fallback)
            try:
                video = await page.find(tag_name="video")
                if video:
                    await video.click(humanize=True)
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
            
            # Try player container
            try:
                player = await page.find(selector=".html5-video-player")
                if player:
                    await player.click(humanize=True)
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
    """Simulate user pausing and resuming video"""
    try:
        player = await page.find(selector=".html5-video-player")
        if player:
            # ✅ Use Pydoll's native humanize=True
            await player.click(humanize=True)
            await asyncio.sleep(random.uniform(3, 10))
            await player.click(humanize=True)
            logger.info("Simulated user pause")
            return True
    except Exception as e:
        logger.debug(f"Pause error: {e}")
    return False


# ========== WATCHING ==========

async def watch_with_human_behavior(page, duration: int, is_mobile: bool = False, cfg=None, instance_id: int = 0, heartbeat_func=None):
    """
    Watch video with human-like behavior and fingerprint heartbeat.
    Ensures fingerprint consistency during playback.
    """
    start_time = time.time()
    next_action = random.randint(5, 15)
    paused = False
    heartbeat_interval = random.randint(15, 25)
    last_heartbeat = start_time
    last_fingerprint_check = start_time
    
    
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time
        remaining = duration - elapsed
        
        if remaining < next_action:
            await asyncio.sleep(remaining)
            break
        
        await asyncio.sleep(next_action)
        
        # Random human-like actions
        r = random.random()
        if r < 0.4:
            await random_scroll(page, is_mobile)
        elif r < 0.7:
            await random_mouse_movement(page)
        else:
            await random_key_press(page)
        
        # ========== HEARTBEAT: Prevent background throttling ==========
        if time.time() - last_heartbeat > heartbeat_interval:
            try:
                await page.execute_script("""
                    var ev = new MouseEvent('mousemove', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: Math.random() * window.innerWidth,
                        clientY: Math.random() * window.innerHeight
                    });
                    document.dispatchEvent(ev);
                """)
                last_heartbeat = time.time()
                heartbeat_interval = random.randint(15, 25)
            except Exception as e:
                if _script_logger:
                    _script_logger.debug(f"Heartbeat mouse move failed: {e}")
        
        # ========== FINGERPRINT HEARTBEAT: Check consistency ==========
        if cfg and heartbeat_func and time.time() - last_fingerprint_check > 30:
            try:
                await heartbeat_func(page, cfg, instance_id)
                last_fingerprint_check = time.time()
            except Exception as e:
                if _script_logger:
                    _script_logger.debug(f"Fingerprint heartbeat check failed: {e}")
        
        # Simulate pause if not already paused and duration is long enough
        if not paused and random.random() < 0.06 and duration > 30:
            if await simulate_pause(page):
                paused = True
        
        # Randomize next action time
        next_action = random.expovariate(0.12) + random.uniform(2, 8)
        next_action = min(max(next_action, 4), 20)




# ========== POPUPS & COOKIES ==========

async def handle_consent_popups(page, instance_id: int = 0) -> bool:
    """
    Handle consent popups using Pydoll's native methods.
    Improved version with better detection and clicking.
    """
    try:
        # Wait for popups to fully load
        await asyncio.sleep(2)
        
        # ========== METHOD 1: Find by text content ==========
        consent_texts = [
            'Accept all', 'I agree', 'Accept', 'Got it', 'OK',
            'Agree', 'Continue', 'Allow', 'Dismiss', 'Close',
            'No thanks', 'Skip', 'Next', 'Accept All'
        ]
        
        for text in consent_texts:
            try:
                # Use Pydoll's find with text
                button = await page.find(text=text)
                if button:
                    # Check if visible and enabled
                    is_visible = await button.is_visible()
                    if is_visible:
                        logger.info(f"Instance {instance_id}: Found consent popup - clicking: {text}")
                        # Use Pydoll's native humanized click
                        await button.click(humanize=True)
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
                        await button.click(humanize=True)
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
            'button[jsname="V67aGc"]',  # Google-specific
            'button[jsname="XSnjRc"]',  # Google-specific
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
                        await button.click(humanize=True)
                        await asyncio.sleep(random.uniform(1, 2))
                        return True
            except Exception as e:
                logger.debug(f"Instance {instance_id}: Selector '{selector}' failed: {e}")
                continue
        
        # ========== METHOD 4: JavaScript fallback ==========
        try:
            result = await page.execute_script("""
                (function() {
                    // Try to find and click accept button
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
                            // Check if visible
                            var rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                el.click();
                                return true;
                            }
                        }
                    }
                    
                    // Fallback: find any button with consent text
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


async def handle_all_popups(page, instance_id: int = 0) -> int:
    """
    Comprehensive popup handler with improved detection.
    """
    popups_handled = 0
    
    try:
        # Wait for popups to appear
        await asyncio.sleep(2)
        
        # Try multiple times with increasing delays
        for attempt in range(4):
            if await handle_consent_popups(page, instance_id):
                popups_handled += 1
                # After handling one popup, wait for others to appear
                await asyncio.sleep(1.5)
            else:
                # If no popup found, wait a bit and try again
                await asyncio.sleep(0.5)
        
        # Check for any remaining popups using JavaScript
        try:
            remaining = await page.execute_script("""
                var popups = document.querySelectorAll('[role="dialog"], .modal, .popup, .consent, .overlay');
                return popups.length;
            """)
            if remaining > 0:
                logger.debug(f"Instance {instance_id}: {remaining} popups still visible")
        except:
            pass
        
        if popups_handled > 0:
            logger.info(f"Instance {instance_id}: Handled {popups_handled} popup(s)")
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: Popup handling error: {e}")
    
    return popups_handled




# ========== SUGGESTED VIDEO ==========

async def click_suggested_video(page, is_mobile: bool = False, instance_id: int = 0) -> str:
    """
    Find, click, and navigate to a random suggested video.
    Returns the URL of the video that was clicked, or None if failed.
    """
    try:
        # Get current video ID
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
        
        # ========== JAVASCRIPT: Find, select, and click a random video ==========
        js_code = """
            (function() {
                var currentVid = arguments[0];
                var links = document.querySelectorAll('a[href*="/watch?v="]');
                var candidates = [];
                
                for (var i = 0; i < links.length; i++) {
                    var href = links[i].href;
                    if (href && href.indexOf('/watch?v=') !== -1) {
                        // Skip current video
                        if (currentVid && href.indexOf(currentVid) !== -1) {
                            continue;
                        }
                        // Check if visible
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
                
                // Pick a random candidate
                var randomIndex = Math.floor(Math.random() * candidates.length);
                var selected = candidates[randomIndex];
                
                // Scroll to element
                selected.element.scrollIntoView({block: 'center', behavior: 'smooth'});
                
                // Click the element
                selected.element.click();
                
                // Return the href as a string
                return selected.href;
            })();
        """
        
        result = await page.execute_script(js_code, current_vid)
        
        if result is None:
            logger.warning(f"Instance {instance_id}: No suggested video links found")
            return None
        
        # ========== ✅ IMPROVED URL EXTRACTION ==========
        clicked_url = None
        
        # Case 1: Result is a string
        if isinstance(result, str) and '/watch?v=' in result:
            clicked_url = result
        
        # Case 2: Result is a dict with nested result structure
        elif isinstance(result, dict):
            logger.debug(f"Instance {instance_id}: Result dict keys: {list(result.keys())}")
            
            # Check for nested result structure: result['result']['value']
            if 'result' in result:
                inner = result['result']
                if isinstance(inner, dict) and 'value' in inner:
                    val = inner['value']
                    if isinstance(val, str) and '/watch?v=' in val:
                        clicked_url = val
                        logger.debug(f"Instance {instance_id}: Extracted from result['result']['value']")
            
            # If not found, recursively search for any string with '/watch?v='
            if not clicked_url:
                import json
                result_str = json.dumps(result)
                import re
                match = re.search(r'https://www\.youtube\.com/watch\?v=[a-zA-Z0-9_-]+', result_str)
                if match:
                    clicked_url = match.group(0)
                    logger.debug(f"Instance {instance_id}: Extracted via regex from JSON string")
            
            # Try numeric keys (array-like)
            if not clicked_url:
                for key in result:
                    val = result[key]
                    if isinstance(val, str) and '/watch?v=' in val:
                        clicked_url = val
                        break
                    if isinstance(val, dict):
                        # Recursively search in nested dict
                        for sub_key in val:
                            sub_val = val[sub_key]
                            if isinstance(sub_val, str) and '/watch?v=' in sub_val:
                                clicked_url = sub_val
                                break
                        if clicked_url:
                            break
        
        # Case 3: Result is a list
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, str) and '/watch?v=' in item:
                    clicked_url = item
                    break
                if isinstance(item, dict):
                    for key in item:
                        val = item[key]
                        if isinstance(val, str) and '/watch?v=' in val:
                            clicked_url = val
                            break
                    if clicked_url:
                        break
        
        if not clicked_url:
            logger.warning(f"Instance {instance_id}: Could not extract URL from result: {type(result)}")
            import json
            logger.debug(f"Instance {instance_id}: Result content: {json.dumps(result, indent=2) if isinstance(result, (dict, list)) else result}")
            return None
        
        logger.info(f"Instance {instance_id}: ✅ Clicked suggested video: {clicked_url[:80]}...")
        
        # ========== WAIT FOR NAVIGATION ==========
        await asyncio.sleep(2)
        
        # Wait for page to load
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
            await button.click(humanize=True)
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
    """Click the next/previous short navigation button."""
    button = await find_shorts_navigation_button(page, direction)
    if button:
        try:
            await button.click(humanize=True)
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
                    await video_link.click(humanize=True)
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
]