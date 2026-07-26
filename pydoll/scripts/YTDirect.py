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
set_referrer_header = _po_driver_module.set_referrer_header
lock_referrer_js = _po_driver_module.lock_referrer_js
start_background_monitor = _po_driver_module.start_background_monitor
PYDOLL_AVAILABLE = _po_driver_module.PYDOLL_AVAILABLE
set_driver_logger = _po_driver_module.set_logger
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
    fingerprint_profile: dict = None
    is_short: bool = False


# ========== HELPER FUNCTIONS ==========

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


async def set_referrer_header(page, referrer, instance_id):
    """Set referrer header via CDP before navigation."""
    try:
        cdp = None
        if hasattr(page, '_connection_handler') and page._connection_handler:
            cdp = page._connection_handler
        elif hasattr(page, 'connection') and hasattr(page.connection, 'send'):
            cdp = page.connection
        
        if cdp:
            if hasattr(cdp, 'execute_command'):
                await cdp.execute_command({
                    "method": "Network.setExtraHTTPHeaders",
                    "params": {"headers": {"Referer": referrer}}
                })
            elif hasattr(cdp, 'send'):
                await cdp.send("Network.setExtraHTTPHeaders", {
                    "headers": {"Referer": referrer}
                })
            logger.info(f"Instance {instance_id}: [REFERRER] ✅ Header set: {referrer}")
            return True
    except Exception as e:
        logger.warning(f"Instance {instance_id}: [REFERRER] ⚠️ Failed to set header: {e}")
    return False


async def lock_referrer_js(page, referrer, instance_id):
    """Lock referrer via JavaScript after page loads."""
    if not referrer:
        return
    try:
        await page.execute_script(f"""
            (function() {{
                try {{ delete Document.prototype.referrer; }} catch(e) {{}}
                Object.defineProperty(Document.prototype, 'referrer', {{
                    get: function() {{ return '{referrer}'; }},
                    set: function() {{ }},
                    configurable: false,
                    enumerable: true
                }});
                try {{
                    Object.defineProperty(document, 'referrer', {{
                        get: function() {{ return '{referrer}'; }},
                        set: function() {{ }},
                        configurable: false,
                        enumerable: true
                    }});
                }} catch(e) {{}}
                console.log('✅ Referrer locked: {referrer}');
            }})();
        """)
        logger.info(f"Instance {instance_id}: [REFERRER] ✅ Locked via JavaScript: {referrer}")
    except Exception as e:
        logger.warning(f"Instance {instance_id}: [REFERRER] ⚠️ JS lock failed: {e}")


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
            
            await set_referrer_header(page, cfg.referer, cfg.instance_id)
            await page.go_to(cfg.referer)
            await wait_for_page_load(page, 10)
            
            await apply_fingerprint_overrides(page, cfg, cfg.instance_id, custom_referer=cfg.referer)
            logger.info(f"Instance {cfg.instance_id}: [FINGERPRINT] Applied during referrer navigation")
            
            
            await handle_all_popups(page, cfg.instance_id)
            
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
            
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            await lock_referrer_js(page, cfg.referer, cfg.instance_id)
        else:
            await apply_fingerprint_overrides(page, cfg, cfg.instance_id, custom_referer="")
            logger.info(f"Instance {cfg.instance_id}: [FINGERPRINT] Applied (no referrer)")
            

        # ========== STEP B: PO TOKEN HANDLING ==========
        if (cfg.po_token_source == "external" or cfg.po_token_source == "potgen" or cfg.po_token_source == "wpc") and not cfg.po_token:
            logger.info(f"Instance {cfg.instance_id}: [TOKEN] Fetching PO token with proxy...")
            
            proxy_url = None
            if cfg.proxy_mode == "tor_browser":
                proxy_url = "socks5://127.0.0.1:9150"
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] Using Tor Browser proxy: {proxy_url}")
            elif cfg.proxy_mode == "tor_service":
                proxy_url = "socks5://127.0.0.1:9050"
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] Using Tor Service proxy: {proxy_url}")
            elif cfg.proxy:
                proxy_url = cfg.proxy
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] Using custom proxy: {proxy_url}")
            else:
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] No proxy configured, using direct connection")
            
            from common.po_token import get_po_token_from_external, get_po_token_from_potgen, get_po_token_from_wpc
            
            if cfg.po_token_source == "external":
                po_token, visitor_id = get_po_token_from_external(cfg.video_id, cfg.instance_id, proxy_url)
            elif cfg.po_token_source == "potgen":
                po_token, visitor_id = get_po_token_from_potgen(cfg.video_id, cfg.instance_id)
            else:  # wpc
                po_token, visitor_id = get_po_token_from_wpc(cfg.video_id, cfg.instance_id, proxy_url)
            
            if po_token:
                cfg.po_token = po_token
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] ✅ PO Token fetched: {po_token[:20]}...")
                watch_url = add_po_token_to_url(watch_url, po_token)
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] Updated watch URL with PO token")
            elif visitor_id:
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] ✅ Visitor ID obtained: {visitor_id[:30]}...")
            else:
                logger.warning(f"Instance {cfg.instance_id}: [TOKEN] ⚠️ Failed to fetch PO token")
                logger.warning(f"Instance {cfg.instance_id}: [TOKEN] ⚠️ Video may fail at 40-60s without PO token!")
        else:
            # Native mode (cfg.po_token is None) OR existing token
            if cfg.po_token:
                watch_url = add_po_token_to_url(watch_url, cfg.po_token)
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] Using existing PO token in URL")
            else:
                logger.info(f"Instance {cfg.instance_id}: [TOKEN] Native mode - browser will generate token")
                # Remove pot parameter if present (native mode doesn't need it)
                if 'pot=' in watch_url:
                    import re
                    watch_url = re.sub(r'[?&]pot=[^&]*', '', watch_url)
                    watch_url = watch_url.rstrip('?&')
                    logger.info(f"Instance {cfg.instance_id}: [TOKEN] Removed pot parameter for native mode")

        # ========== STEP C: NAVIGATE TO YOUTUBE ==========
        if cfg.referer:
            logger.info(f"Instance {cfg.instance_id}: [REFERRER] Step 2: Navigating to YouTube")
            await set_referrer_header(page, cfg.referer, cfg.instance_id)
        else:
            logger.info(f"Instance {cfg.instance_id}: [DIRECT] Routing directly to main watch link")
        
        nav_task = asyncio.create_task(page.go_to(watch_url, timeout=60))  # 60 second timeout
        
        async def reapply_fingerprint_immediate():
            await asyncio.sleep(0.3)
            if cfg.referer:
                await apply_fingerprint_overrides(page, cfg, cfg.instance_id, custom_referer=cfg.referer)
            else:
                await apply_fingerprint_overrides(page, cfg, cfg.instance_id, custom_referer="")
            logger.info(f"Instance {cfg.instance_id}: [FINGERPRINT] Re-applied during YouTube navigation")
        
        fingerprint_task = asyncio.create_task(reapply_fingerprint_immediate())
        
        await nav_task
        await fingerprint_task
        await wait_for_page_load(page, 12)
        
        # ✅ FIX 5: Re-apply fingerprint after page load (handles reloads)
        logger.info(f"Instance {cfg.instance_id}: [FINGERPRINT] Re-applying after page load...")
        if cfg.referer:
            await apply_fingerprint_overrides(page, cfg, cfg.instance_id, custom_referer=cfg.referer)
        else:
            await apply_fingerprint_overrides(page, cfg, cfg.instance_id, custom_referer="")
        
        # Lock referrer after YouTube loads
        if cfg.referer:
            await lock_referrer_js(page, cfg.referer, cfg.instance_id)
        
        await handle_all_popups(page, cfg.instance_id)
        try:
            await handle_cookies_async(page, cfg.instance_id)
        except:
            pass
        
        # ✅ FIX 6: Re-lock referrer after popups (handles cookie consent reload)
        if cfg.referer:
            await lock_referrer_js(page, cfg.referer, cfg.instance_id)
            logger.info(f"Instance {cfg.instance_id}: [REFERRER] Re-locked after popups")
        
        await asyncio.sleep(0.5)

        if cfg.view_type == "Other YouTube features":
            await random_scroll(page, cfg.is_mobile)

        # ========== CHECK AND START PLAYBACK ==========
        playback_success = await is_video_playing(page)
        if not playback_success:
            logger.warning(f"Instance {cfg.instance_id}: Video not playing, retrying...")
            playback_success = await attempt_video_playback_with_retry(
                page, cfg.instance_id, cfg.is_mobile, is_suggested=False, max_retries=3
            )

        if playback_success:
            watch_time = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
            logger.info(f"Instance {cfg.instance_id}: Watching for {watch_time}s")
            
            # Unified background monitor handles fingerprint, popups, CAPTCHAs
            await watch_with_human_behavior(
                page, 
                watch_time, 
                cfg.is_mobile, 
                cfg, 
                cfg.instance_id,
                None
            )
            
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

            driver_tuple = await create_driver_with_po_token_pydoll(cfg, "yt_direct_pydoll_cache")
            browser = driver_tuple[0]
            page = driver_tuple[1]
            profile_dir = driver_tuple[2] if len(driver_tuple) > 2 else None

            await apply_fingerprint_overrides(page, cfg, cfg.instance_id)

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
                
                # ========== PO TOKEN: Will be fetched in watch_direct_async with proxy ==========
                if cfg.po_token_source == "external" or cfg.po_token_source == "potgen":
                    logger.info(f"Instance {cfg.instance_id}: PO token will be fetched in watch_direct_async with proxy")
                else:
                    logger.info(f"Instance {cfg.instance_id}: Native mode - token will be generated by browser")
                #if cfg.po_token_source == "external" or cfg.po_token_source == "potgen":
                #    try:
                #        po_token, _ = get_po_token(cfg.video_id, cfg.instance_id)
                #        if po_token:
                #            cfg.po_token = po_token
                #            logger.info(f"Instance {cfg.instance_id}: ✅ PO Token fetched from {cfg.po_token_source}")
                #        else:
                #            logger.warning(f"Instance {cfg.instance_id}: ⚠️ Failed to fetch PO token from {cfg.po_token_source}")
                #    except Exception as e_po:
                #        logger.warning(f"Instance {cfg.instance_id}: Unable to fetch token: {e_po}")
                #else:
                #    logger.info(f"Instance {cfg.instance_id}: Native mode - token will be generated by browser")

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
            
            if browser:
                try:
                    await asyncio.wait_for(browser.stop(), timeout=5.0)
                    logger.info(f"Instance {cfg.instance_id}: ✅ Browser stopped")
                except asyncio.TimeoutError:
                    logger.warning(f"Instance {cfg.instance_id}: ⚠️ Browser stop timeout, forcing cleanup...")
                    cleanup_all_browsers()
                except Exception as e:
                    logger.warning(f"Instance {cfg.instance_id}: ⚠️ Browser stop error: {e}")
                    cleanup_all_browsers()
            
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

        # Token will be fetched in watch_direct_async with proxy
        logger.info(f"[TOKEN] Instance {d.get('instance_id', 0)}: Token will be fetched with proxy in watch_direct_async")

        traffic_source = d.get("traffic_source", "direct")
        logger.info(f"[TRAFFIC] Instance {d.get('instance_id', 0)}: {traffic_source}")

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
            is_ios=d.get("is_ios", False),
            is_android=d.get("is_android", False),
            fingerprint_profile=d.get("fingerprint_profile", None)
        )

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