#!/usr/bin/env python3
"""
YouTube Direct Watch - Pydoll Version
Uses Pydoll's native CDP connection for stealth automation
"""

import sys
import os
import json
import random
import shutil
import time
import logging
import importlib.util
import traceback
import re
import asyncio
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass

# ========== PATH SETUP ==========
_script_path = Path(__file__).resolve()
PROJECT_ROOT = _script_path.parent.parent.parent
COMMON_ROOT = PROJECT_ROOT / "common"
PYDOLL_COMMON_ROOT = PROJECT_ROOT / "pydoll" / "common"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(COMMON_ROOT))
sys.path.insert(0, str(PYDOLL_COMMON_ROOT))


def _load_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ========== IMPORTS ==========

# PO Token
_po_token_path = COMMON_ROOT / "po_token.py"
_po_token_module = _load_module_from_file("po_token", _po_token_path)
get_po_token = _po_token_module.get_po_token
set_po_logger = _po_token_module.set_logger
set_po_token_source = _po_token_module.set_po_token_source
add_po_token_to_url = _po_token_module.add_po_token_to_url

# Pydoll Human Behavior
_human_behavior_path = PYDOLL_COMMON_ROOT / "human_behavior.py"
_human_behavior_module = _load_module_from_file("human_behavior", _human_behavior_path)
watch_with_human_behavior = _human_behavior_module.watch_with_human_behavior
click_suggested_video = _human_behavior_module.click_suggested_video
attempt_video_playback_with_retry = _human_behavior_module.attempt_video_playback_with_retry
handle_all_popups = _human_behavior_module.handle_all_popups
is_video_playing = _human_behavior_module.is_video_playing
cognitive_delay = _human_behavior_module.cognitive_delay
random_scroll = _human_behavior_module.random_scroll
get_variable_watch_time = _human_behavior_module.get_variable_watch_time

# Pydoll Utils
_utils_path = PYDOLL_COMMON_ROOT / "utils.py"
_utils_module = _load_module_from_file("utils", _utils_path)
wait_for_page_load = _utils_module.wait_for_page_load
handle_cookies_async = _utils_module.handle_cookies_async

# Pydoll Driver
_po_driver_path = PYDOLL_COMMON_ROOT / "po_driver.py"
_po_driver_module = _load_module_from_file("po_driver", _po_driver_path)
create_driver_with_po_token_pydoll = _po_driver_module.create_driver_with_po_token_pydoll
apply_fingerprint_overrides = _po_driver_module.apply_fingerprint_overrides
PYDOLL_AVAILABLE = _po_driver_module.PYDOLL_AVAILABLE
set_driver_logger = _po_driver_module.set_logger
# Cleanup functions from po_driver
cleanup_all_browsers = _po_driver_module.cleanup_all_browsers
register_cleanup_handlers = _po_driver_module.register_cleanup_handlers
kill_child_processes = _po_driver_module.kill_child_processes

# ========== LOGGING ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTDirect_Pydoll_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTDirect_Pydoll")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(log_filename, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

# ========== SAFE DIRECTORY DELETION (For Windows File-Lock) ==========
async def safe_delete_directory(path, retries=3, delay=2):
    """Safely delete a directory with retry on Windows file-lock."""
    if not path or not os.path.exists(path):
        return True
    
    for attempt in range(retries):
        try:
            # Wait for file locks to release
            await asyncio.sleep(delay)
            shutil.rmtree(path, ignore_errors=True)
            if logger:
                logger.info(f"[CLEANUP] Successfully deleted: {path}")
            return True
        except PermissionError as e:
            if attempt < retries - 1:
                logger.warning(f"[CLEANUP] PermissionError on {path}, retrying in {delay}s... (attempt {attempt+1}/{retries})")
                await asyncio.sleep(delay)
            else:
                logger.warning(f"[CLEANUP] Could not delete {path} after {retries} attempts: {e}")
        except Exception as e:
            logger.warning(f"[CLEANUP] Error deleting {path}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(delay)
    
    return False

try:
    set_po_logger(logger)
except:
    pass
try:
    set_driver_logger(logger)
except:
    pass

logger.info(f"YTDirect_Pydoll.py started - PID: {os.getpid()}")
logger.info(f"Project root: {PROJECT_ROOT}")
logger.info(f"Pydoll available: {PYDOLL_AVAILABLE}")


# ========== CONFIGURATION ==========
@dataclass
class SessionConfig:
    instance_id: int
    video_id: str
    view_type: str
    min_watch_time: int
    max_watch_time: int
    suggested_min: int
    suggested_max: int
    suggested_chance: float
    headless: bool
    user_agent: str
    is_mobile: bool
    cycles: int = 1
    po_token: str = None
    po_token_source: str = "external"
    proxy: str = None
    proxy_mode: str = "none"
    num_instances: int = 1
    referer: str = None
    traffic_source: str = "direct"
    force_mobile: bool = False
    chrome_args: list = None
    # Fingerprint fields (must come from JSON, no defaults)
    platform: str = None
    screen_width: int = None
    screen_height: int = None
    viewport_width: int = None
    viewport_height: int = None
    plugins_length: int = None
    device_category: str = None
    vendor: str = None
    connection: dict = None
    language: str = None
    is_ios: bool = False
    is_android: bool = False
    fingerprint_profile: dict = None  # ✅ ADD THIS
    is_short: bool = False  # ✅ ADD THIS



# ========== HELPER FUNCTIONS ==========

async def wait_for_page_load(page, timeout: int = 25) -> bool:
    """Wait for page to finish loading using DOM readyState."""
    try:
        for attempt in range(timeout * 2):
            try:
                ready_state = await page.execute_script("return document.readyState;")
                if isinstance(ready_state, dict):
                    ready_state = ready_state.get('result', {}).get('result', {}).get('value', '')
                if ready_state == "complete":
                    await asyncio.sleep(0.5)
                    return True
            except:
                pass
            await asyncio.sleep(0.5)
        return False
    except Exception:
        return False


async def get_viewport_size(page):
    try:
        width = await page.execute_script("return window.innerWidth;")
        height = await page.execute_script("return window.innerHeight;")
        if isinstance(width, dict):
            width = width.get('result', {}).get('result', {}).get('value', 'unknown')
        if isinstance(height, dict):
            height = height.get('result', {}).get('result', {}).get('value', 'unknown')
        return width, height
    except:
        return None, None




async def inject_embed_iframe(page, video_id: str, instance_id: int, wait_time: int = 8):
    """
    Navigate to embed page to generate VISITOR_INFO1_LIVE cookie.
    Uses direct navigation with error handling for "Error 153".
    """
    logger.info(f"Instance {instance_id}: [EMBED] Navigating to embed for token generation...")
    
    try:
        # Navigate to embed URL
        embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=0&modestbranding=1&rel=0"
        logger.info(f"Instance {instance_id}: [EMBED] Loading: {embed_url[:60]}...")
        
        await page.go_to(embed_url, timeout=30)
        await wait_for_page_load(page, 10)
        
        # Check for error
        page_content = await page.execute_script("return document.body.innerText || '';")
        if 'Error' in page_content and '153' in page_content:
            logger.warning(f"Instance {instance_id}: [EMBED] Error 153 detected, but continuing...")
            # Error 153 doesn't prevent cookie generation
            # The cookie may still be set despite the error
            await asyncio.sleep(5)
        
        # Natural interaction on embed page
        try:
            await page.execute_script("window.scrollBy(0, Math.floor(Math.random() * 100) + 50);")
            await asyncio.sleep(random.uniform(0.5, 1.5))
        except:
            pass
        
        # Wait for BotGuard
        wait_time = random.uniform(8.0, 12.0)
        logger.info(f"Instance {instance_id}: [EMBED] Waiting {wait_time:.1f}s for BotGuard...")
        await asyncio.sleep(wait_time)
        
        # Check for cookie
        raw_cookie = await page.execute_script("return document.cookie;")
        if isinstance(raw_cookie, dict):
            cookie_string = raw_cookie.get('result', {}).get('result', {}).get('value', '')
        else:
            cookie_string = str(raw_cookie) if raw_cookie else ''
        
        if cookie_string and 'VISITOR_INFO1_LIVE' in cookie_string:
            logger.info(f"Instance {instance_id}: [EMBED] ✅ VISITOR_INFO1_LIVE cookie found")
            return True
        else:
            logger.warning(f"Instance {instance_id}: [EMBED] ⚠️ VISITOR_INFO1_LIVE cookie NOT found")
            return False
            
    except Exception as e:
        logger.warning(f"Instance {instance_id}: [EMBED] Failed: {e}")
        return False




# ========== DIRECT WATCH (Async) ==========

async def watch_direct_async(page, cfg: SessionConfig):
    """Watch video directly using YouTube watch URL."""
    try:
        watch_url = f"https://www.youtube.com/watch?v={cfg.video_id}"
        if cfg.po_token:
            watch_url = add_po_token_to_url(watch_url, cfg.po_token)

        logger.info(f"Instance {cfg.instance_id}: ========== DIRECT WATCH ==========")
        logger.info(f"Instance {cfg.instance_id}: View Type: {cfg.view_type}")
        logger.info(f"Instance {cfg.instance_id}: Traffic Source: {cfg.traffic_source}")
        logger.info(f"Instance {cfg.instance_id}: Referer: {cfg.referer if cfg.referer else 'None'}")
        logger.info(f"Instance {cfg.instance_id}: Watch URL: {watch_url[:150]}...")
        logger.info(f"Instance {cfg.instance_id}: PO Token Present: {cfg.po_token is not None}")
        logger.info(f"Instance {cfg.instance_id}: ====================================")

        # ========== STEP A: REFERRER WARMUP ==========
        if cfg.referer:
            logger.info(f"Instance {cfg.instance_id}: [REFERRER] Step 1: Navigating to referrer: {cfg.referer}")
            await page.go_to(cfg.referer)
            await wait_for_page_load(page, 15)
            await handle_all_popups(page, cfg.instance_id)
            
            # Natural interaction
            try:
                await page.execute_script("""
                    window.scrollBy(0, Math.floor(Math.random() * 200) + 100);
                    var links = document.querySelectorAll('a, button, [role="button"]');
                    for (var i = 0; i < links.length; i++) {
                        var rect = links[i].getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.top > 0) {
                            links[i].dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                            return true;
                        }
                    }
                    return false;
                """)
                logger.info(f"Instance {cfg.instance_id}: [REFERRER] Natural interaction simulated")
            except Exception as e:
                logger.warning(f"Instance {cfg.instance_id}: [REFERRER] Interaction failed: {e}")
            
            await asyncio.sleep(random.uniform(2, 5))
            await cognitive_delay("read")

        # ========== STEP B: NATIVE TOKEN GENERATION ==========
        if not cfg.po_token:
            logger.info(f"Instance {cfg.instance_id}: [TOKEN] No external PO token, generating native token...")
            
            # Try embed approach first
            success = await inject_embed_iframe(page, cfg.video_id, cfg.instance_id)
            
            # If embed fails, try watch page approach
            if not success:
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] Embed failed, trying watch page approach...")
                await page.go_to("https://www.youtube.com")
                await wait_for_page_load(page, 10)
                await handle_all_popups(page, cfg.instance_id)
                
                # Click on a random video to trigger BotGuard
                await page.execute_script("""
                    var videos = document.querySelectorAll('ytd-video-renderer, ytd-rich-item-renderer');
                    if (videos.length > 0) {
                        var index = Math.floor(Math.random() * Math.min(videos.length, 5));
                        videos[index].scrollIntoView({block: 'center', behavior: 'smooth'});
                        var link = videos[index].querySelector('a#thumbnail, a#video-title-link');
                        if (link) {
                            link.click();
                            return true;
                        }
                    }
                    return false;
                """)
                await asyncio.sleep(random.uniform(5.0, 8.0))
                
                # Check cookie
                raw_cookie = await page.execute_script("return document.cookie;")
                if isinstance(raw_cookie, dict):
                    cookie_string = raw_cookie.get('result', {}).get('result', {}).get('value', '')
                else:
                    cookie_string = str(raw_cookie) if raw_cookie else ''
                
                if cookie_string and 'VISITOR_INFO1_LIVE' in cookie_string:
                    logger.info(f"Instance {cfg.instance_id}: [TOKEN] ✅ VISITOR_INFO1_LIVE cookie found (watch page)")
                    success = True

        # ========== STEP C: APPLY REFERRER AND WATCH ==========
        if cfg.referer:
            logger.info(f"Instance {cfg.instance_id}: [REFERRER] Applying prototype shield lock for: {cfg.referer}")
            await apply_fingerprint_overrides(page, cfg, cfg.instance_id, custom_referer=cfg.referer)
            
            logger.info(f"Instance {cfg.instance_id}: [REFERRER] Step 2: Navigating to YouTube from referrer")
            await page.go_to(watch_url)
            await wait_for_page_load(page, 20)
            await handle_all_popups(page, cfg.instance_id)
            await cognitive_delay("read")

            try:
                current_referrer = await page.execute_script("return document.referrer;")
                if isinstance(current_referrer, dict):
                    current_referrer = current_referrer.get('result', {}).get('result', {}).get('value', 'unknown')
                logger.info(f"Instance {cfg.instance_id}: [REFERRER] ✅ Current referrer context: {current_referrer}")
            except:
                pass
        else:
            # Direct navigation context (No referrer)
            logger.info(f"Instance {cfg.instance_id}: [DIRECT] Routing directly to main watch link")
            await apply_fingerprint_overrides(page, cfg, cfg.instance_id, custom_referer="")
            await page.go_to(watch_url)
            await wait_for_page_load(page, 20)
            
            # ✅ HANDLE POPUPS ON YOUTUBE WATCH PAGE
            await handle_all_popups(page, cfg.instance_id)
            try:
                await handle_cookies_async(page, cfg.instance_id)
            except:
                pass
            
            await cognitive_delay("read")

        # ========== VIEW TYPE SPECIFIC BEHAVIOR ==========
        if cfg.view_type == "Other YouTube features":
            await cognitive_delay("process")
            await random_scroll(page, cfg.is_mobile)
            await cognitive_delay("read")

        # ========== CHECK AND START PLAYBACK ==========
        playback_success = await is_video_playing(page)
        if not playback_success:
            logger.warning(f"Instance {cfg.instance_id}: Video not playing, retrying...")
            playback_success = await attempt_video_playback_with_retry(
                page, cfg.instance_id, cfg.is_mobile, is_suggested=False, max_retries=3
            )

        if playback_success:
            await cognitive_delay("process")
            watch_time = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching for {watch_time}s")
            
            # Start fingerprint heartbeat in background
            heartbeat_task = None
            try:
                if hasattr(page, '_start_heartbeat'):
                    heartbeat_task = asyncio.create_task(page._start_heartbeat(interval=15))
                    logger.info(f"Instance {cfg.instance_id}: [HEARTBEAT] Started fingerprint monitoring")
                else:
                    logger.warning(f"Instance {cfg.instance_id}: [HEARTBEAT] _start_heartbeat not available")
            except Exception as e:
                logger.warning(f"Instance {cfg.instance_id}: [HEARTBEAT] Could not start heartbeat: {e}")
            
            # Import heartbeat function for manual checks
            try:
                from pydoll.common.po_driver import maintain_fingerprint_heartbeat
            except ImportError:
                maintain_fingerprint_heartbeat = None
            
            # Watch with human behavior and pass heartbeat function
            try:
                await watch_with_human_behavior(
                    page, 
                    watch_time, 
                    cfg.is_mobile, 
                    cfg, 
                    cfg.instance_id,
                    maintain_fingerprint_heartbeat  # Pass the heartbeat function
                )
            except Exception as e:
                logger.error(f"Instance {cfg.instance_id}: Error during watch: {e}")
            
            # Stop heartbeat when done (with proper cleanup)
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                logger.info(f"Instance {cfg.instance_id}: [HEARTBEAT] Stopped fingerprint monitoring")
            
            return True
        else:
            logger.warning(f"Instance {cfg.instance_id}: Playback failed")
            return False

    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error in watch_direct: {e}")
        logger.error(traceback.format_exc())
        return False


async def watch_suggested_direct_async(page, cfg: SessionConfig):
    """Watch suggested video."""
    try:
        await cognitive_delay("decide")
        for _ in range(random.randint(1, 2)):
            await random_scroll(page, cfg.is_mobile)
            await cognitive_delay("scroll")

        clicked_url = await click_suggested_video(page, cfg.is_mobile, cfg.instance_id)
        if not clicked_url:
            logger.warning(f"Instance {cfg.instance_id}: Could not click suggested")
            return False

        logger.info(f"Instance {cfg.instance_id}: Navigated to suggested video")
        await cognitive_delay("read")
        await handle_all_popups(page, cfg.instance_id)

        playback_success = await attempt_video_playback_with_retry(
            page, cfg.instance_id, cfg.is_mobile, is_suggested=True, max_retries=2
        )

        if playback_success:
            await cognitive_delay("process")
            suggested_watch = random.randint(cfg.suggested_min, cfg.suggested_max)
            logger.info(f"Instance {cfg.instance_id}: Watching suggested for {suggested_watch}s")
            await watch_with_human_behavior(page, suggested_watch, cfg.is_mobile)

        return playback_success

    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error in watch_suggested_direct: {e}")
        logger.error(traceback.format_exc())
        return False


# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    if not PYDOLL_AVAILABLE:
        logger.error(f"Instance {cfg.instance_id}: ❌ Pydoll not available!")
        return
        
    # Create an isolated async loop for this multi-processing execution context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _async_session_runner():
        browser = None
        try:
            logger.info(f"Instance {cfg.instance_id}: ========== Starting YTDirect Pydoll Session ==========")
            logger.info(f"Instance {cfg.instance_id}: Video ID: {cfg.video_id}")
            logger.info(f"Instance {cfg.instance_id}: Traffic Source: {cfg.traffic_source}")
            logger.info(f"Instance {cfg.instance_id}: Referer: {cfg.referer if cfg.referer else 'None'}")
            logger.info(f"Instance {cfg.instance_id}: PO Token Source: {cfg.po_token_source}")
            logger.info(f"Instance {cfg.instance_id}: Cycles: {cfg.cycles}")

            # 1. Initialize browser instance via the driver logic
            driver_tuple = await create_driver_with_po_token_pydoll(cfg, "yt_direct_pydoll_cache")
            browser = driver_tuple[0]
            page = driver_tuple[1]
            profile_dir = driver_tuple[2] if len(driver_tuple) > 2 else None

            # 2. Register persistent pre-injection stealth hooks via CDP
            await apply_fingerprint_overrides(page, cfg, cfg.instance_id)

            # Debug and verify viewport size alignment
            try:
                actual_width, actual_height = await get_viewport_size(page)
                logger.info(f"Instance {cfg.instance_id}: 🔍 Actual viewport: {actual_width}x{actual_height}")
            except:
                pass

            await cognitive_delay("process")

            cycles_done = 0
            total_cycles = cfg.cycles

            while total_cycles == 0 or cycles_done < total_cycles:
                logger.info(f"Instance {cfg.instance_id}: --- Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'} ---")

                # Only fetch external tokens here - native tokens are generated by the browser
                if cfg.po_token_source == "external" or cfg.po_token_source == "potgen":
                    try:
                        po_token, _ = get_po_token(cfg.video_id, cfg.instance_id)
                        if po_token:
                            cfg.po_token = po_token
                            logger.info(f"Instance {cfg.instance_id}: ✅ PO Token fetched from {cfg.po_token_source}")
                        else:
                            logger.warning(f"Instance {cfg.instance_id}: ⚠️ Failed to fetch PO token from {cfg.po_token_source}")
                    except Exception as e_po:
                        logger.warning(f"Instance {cfg.instance_id}: Unable to fetch token: {e_po}")
                else:
                    # Native mode - token will be generated by the browser during embed warmup
                    logger.info(f"Instance {cfg.instance_id}: Native mode - token will be generated by browser")

                watch_success = await watch_direct_async(page, cfg)
                if not watch_success:
                    logger.warning(f"Instance {cfg.instance_id}: Main video watch had issues")

                if random.random() < cfg.suggested_chance:
                    logger.info(f"Instance {cfg.instance_id}: Attempting suggested video loop")
                    await watch_suggested_direct_async(page, cfg)

                cycles_done += 1

                if total_cycles == 0 or cycles_done < total_cycles:
                    pause = random.uniform(8, 20)
                    logger.info(f"Instance {cfg.instance_id}: Pausing {pause:.1f}s between cycles")
                    await asyncio.sleep(pause)

            logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycles successfully.")

        except asyncio.CancelledError:
            logger.warning(f"Instance {cfg.instance_id}: Session cancelled")
        except Exception as e:
            logger.error(f"Instance {cfg.instance_id}: Session execution error: {e}")
            logger.error(traceback.format_exc())
        finally:
            logger.info(f"Instance {cfg.instance_id}: 🛑 Initiating cleanup...")
            
            # 1. Close browser properly
            if browser:
                try:
                    await asyncio.wait_for(browser.stop(), timeout=5.0)
                    logger.info(f"Instance {cfg.instance_id}: ✅ Browser stopped")
                except asyncio.TimeoutError:
                    logger.warning(f"Instance {cfg.instance_id}: ⚠️ Browser stop timeout, forcing cleanup...")
                    # Force cleanup via cleanup_all_browsers
                    cleanup_all_browsers()
                except Exception as e:
                    logger.warning(f"Instance {cfg.instance_id}: ⚠️ Browser stop error: {e}")
                    cleanup_all_browsers()
            
            # 2. Clean up profile directory if it exists
            try:
                import shutil
                if 'profile_dir' in locals() and profile_dir:
                    shutil.rmtree(profile_dir, ignore_errors=True)
                    logger.info(f"Instance {cfg.instance_id}: 🧹 Deleted profile: {profile_dir}")
                elif hasattr(cfg, '_profile_dir') and cfg._profile_dir:
                    shutil.rmtree(cfg._profile_dir, ignore_errors=True)
                    logger.info(f"Instance {cfg.instance_id}: 🧹 Deleted profile: {cfg._profile_dir}")
            except Exception as e:
                logger.warning(f"Instance {cfg.instance_id}: ⚠️ Profile cleanup error: {e}")

    try:
        loop.run_until_complete(_async_session_runner())
    except KeyboardInterrupt:
        logger.info(f"Instance {cfg.instance_id}: 🛑 Keyboard interrupt received, cleaning up...")
        cleanup_all_browsers()
    finally:
        try:
            if not loop.is_closed():
                loop.close()
        except:
            pass




# ========== MAIN ==========

def main():
    
    # ========== REGISTER CLEANUP HANDLERS ==========
    register_cleanup_handlers()
    
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTDirect_Pydoll.py <config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    logger.info(f"Loading config from: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    logger.info(f"Starting YTDirect Pydoll with {len(instances)} instance(s)")
    processes = []

    for d in instances:
        video_id = d.get("video_id", "")
        po_token = None
        visitor_id = None
        po_token_source = d.get("po_token_source", "external")
        set_po_token_source(po_token_source)

        if video_id:
            po_token, visitor_id = get_po_token(video_id, d.get("instance_id", 0))
            if po_token:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: PO token received")
            else:
                logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: No token")

        traffic_source = d.get("traffic_source", "direct")
        logger.info(f"[TRAFFIC] Instance {d.get('instance_id', 0)}: {traffic_source}")

        # Create config with fingerprint fields (no defaults)
        cfg = SessionConfig(
            instance_id=d.get("instance_id", 0),
            video_id=video_id,
            view_type=d.get("view_type", "Direct/Unknown"),
            min_watch_time=d.get("min_watch_time", 30),
            max_watch_time=d.get("max_watch_time", 180),
            suggested_min=d.get("suggested_min", 15),
            suggested_max=d.get("suggested_max", 35),
            suggested_chance=d.get("suggested_chance", 0.4),
            headless=d.get("headless", False),
            user_agent=d.get("user_agent", ""),
            is_mobile=d.get("is_mobile", False),
            cycles=d.get("cycles", 1),
            po_token=po_token,
            po_token_source=po_token_source,
            proxy=d.get("proxy", None),
            proxy_mode=d.get("proxy_mode", "none"),
            num_instances=d.get("num_instances", 1),
            referer=d.get("referer", None),
            traffic_source=d.get("traffic_source", "direct"),
            force_mobile=d.get("force_mobile", False),
            chrome_args=d.get("chrome_args", None),
            # Fingerprint fields - must be in JSON
            platform=d.get("platform"),
            screen_width=d.get("screen_width"),
            screen_height=d.get("screen_height"),
            viewport_width=d.get("viewport_width"),
            viewport_height=d.get("viewport_height"),
            plugins_length=d.get("plugins_length"),
            device_category=d.get("device_category"),
            vendor=d.get("vendor"),
            connection=d.get("connection", None),
            language=d.get("language"),
            is_ios=d.get("is_ios", False),  # ✅ ADD
            is_android=d.get("is_android", False),  # ✅ ADD
            fingerprint_profile=d.get("fingerprint_profile", None)  # ✅ ADD
        )

        # Validate fingerprint fields
        missing = []
        for field in ['platform', 'screen_width', 'screen_height', 'viewport_width',
                      'viewport_height', 'plugins_length', 'device_category', 'vendor', 'language']:
            if getattr(cfg, field) is None:
                missing.append(field)
        if missing:
            logger.error(f"Instance {cfg.instance_id}: ❌ Missing fingerprint fields: {missing}")


        logger.info(f"Instance {cfg.instance_id}: 🔍 Fingerprint: Vendor={cfg.vendor}, Plugins={cfg.plugins_length}, Screen={cfg.screen_width}x{cfg.screen_height}")

        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        logger.info(f"Instance {cfg.instance_id} started in process {p.pid}")
        time.sleep(random.uniform(1, 3))

    if not processes:
        logger.error("No valid instances to process. Exiting.")
        sys.exit(1)

    for p in processes:
        p.join()
        logger.info(f"Process {p.pid} completed")

    logger.info("All YTDirect Pydoll sessions finished")
    
    
def _sync_safe_delete(path_str: str, retries: int = 3, delay: float = 0.5):
    """Synchronously deletes a profile directory, handling Windows file locks gracefully."""
    import shutil
    import time
    import os
    
    if not path_str or not os.path.exists(path_str):
        return
        
    def remove_readonly(func, path, excinfo):
        try:
            os.chmod(path, 0o777)
            func(path)
        except:
            pass

    for attempt in range(retries):
        try:
            shutil.rmtree(path_str, onerror=remove_readonly)
            return
        except PermissionError:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                shutil.rmtree(path_str, ignore_errors=True)


if __name__ == "__main__":
    main()