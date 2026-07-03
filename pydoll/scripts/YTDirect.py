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

# Pydoll Driver
_po_driver_path = PYDOLL_COMMON_ROOT / "po_driver.py"
_po_driver_module = _load_module_from_file("po_driver", _po_driver_path)
create_driver_with_po_token_pydoll = _po_driver_module.create_driver_with_po_token_pydoll
set_driver_logger = _po_driver_module.set_logger
PYDOLL_AVAILABLE = _po_driver_module.PYDOLL_AVAILABLE


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
    proxy: str = None  # ✅ ADDED
    proxy_mode: str = "none"
    num_instances: int = 1
    referer: str = None
    traffic_source: str = "direct"  # ✅ ADDED
    force_mobile: bool = False  # ✅ ADDED
    chrome_args: list = None  # ✅ ADDED
    # ========== FINGERPRINT FIELDS ==========
    platform: str = "Win32"
    screen_width: int = 1920  # ✅ ADDED
    screen_height: int = 1080  # ✅ ADDED
    viewport_width: int = 1920
    viewport_height: int = 950
    plugins_length: int = 5
    device_category: str = "desktop"
    vendor: str = "Google Inc."
    connection: dict = None  # ✅ ADDED
    language: str = "en-US"


# ========== HELPER FUNCTIONS ==========

async def wait_for_page_load(page, timeout: int = 25) -> bool:
    """Wait for page to finish loading using DOM readyState."""
    try:
        for attempt in range(timeout * 2):  # Check every 0.5 seconds
            try:
                ready_state = await page.execute_script("return document.readyState;")
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
    """Get actual viewport size."""
    try:
        width = await page.evaluate_script("return window.innerWidth")
        height = await page.evaluate_script("return window.innerHeight")
        return width, height
    except Exception as e:
        logger.debug(f"Could not get viewport: {e}")
        return None, None


# ========== DIRECT WATCH (Async) ==========

async def watch_direct_async(page, cfg: SessionConfig):
    """Watch video directly using YouTube watch URL."""
    try:
        # Build watch URL with PO token
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
        
        # Navigate to video - ✅ FIXED: use go_to() not goto()
        await page.go_to(watch_url)
        await wait_for_page_load(page, 20)
        await cognitive_delay("read")
        
        # View type specific behavior
        if cfg.view_type == "Other YouTube features":
            await cognitive_delay("process")
            await random_scroll(page, cfg.is_mobile)
            await cognitive_delay("read")
        
        # Handle popups and cookies
        await handle_all_popups(page, cfg.instance_id)
        # Handle cookies separately if needed
        try:
            from pydoll.common.utils import handle_cookies_async
            await handle_cookies_async(page, cfg.instance_id)
        except:
            pass
        
        # Check and start playback
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
            await watch_with_human_behavior(page, watch_time, cfg.is_mobile)
            return True
        else:
            logger.warning(f"Instance {cfg.instance_id}: Playback failed")
            return False
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error in watch_direct: {e}")
        logger.error(traceback.format_exc())
        return False


async def watch_suggested_direct_async(page, cfg: SessionConfig):
    """
    Watch suggested video.
    The DECISION to call this function is made in the main loop based on suggested_chance.
    This function just handles the actual suggested video watching.
    """
    try:
        # ========== NATURAL DECISION PAUSE ==========
        await cognitive_delay("decide")
        
        # ========== LIGHT SCROLLING THROUGH SUGGESTIONS ==========
        for _ in range(random.randint(1, 2)):
            await random_scroll(page, cfg.is_mobile)
            await cognitive_delay("scroll")
        
        # ========== CLICK SUGGESTED VIDEO ==========
        # click_suggested_video() is from human_behavior.py - handles finding, clicking, navigating
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
        import traceback
        logger.error(traceback.format_exc())
        return False


# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    """Run a single session - sync wrapper for async functions"""
    if not PYDOLL_AVAILABLE:
        logger.error(f"Instance {cfg.instance_id}: ❌ Pydoll not available!")
        return
    
    asyncio.run(_run_session_async(cfg))


async def _run_session_async(cfg: SessionConfig):
    """Async session runner"""
    browser = None
    page = None
    
    try:
        logger.info(f"Instance {cfg.instance_id}: ========== Starting YTDirect Pydoll Session ==========")
        logger.info(f"Instance {cfg.instance_id}: Video ID: {cfg.video_id}")
        logger.info(f"Instance {cfg.instance_id}: Traffic Source: {cfg.traffic_source}")
        logger.info(f"Instance {cfg.instance_id}: Referer: {cfg.referer if cfg.referer else 'None'}")
        logger.info(f"Instance {cfg.instance_id}: PO Token Source: {cfg.po_token_source}")
        logger.info(f"Instance {cfg.instance_id}: Cycles: {cfg.cycles}")
        
        # Create driver
        browser, page, _ = await create_driver_with_po_token_pydoll(cfg, "yt_direct_pydoll_cache")
        
        # Debug viewport - ✅ FIXED: use evaluate_script()
        try:
            actual_width, actual_height = await get_viewport_size(page)
            if actual_width and actual_height:
                logger.info(f"Instance {cfg.instance_id}: 🔍 Actual viewport: {actual_width}x{actual_height}")
                logger.info(f"Instance {cfg.instance_id}: 🔍 Expected viewport: {cfg.viewport_width}x{cfg.viewport_height}")
        except Exception as e:
            logger.warning(f"Instance {cfg.instance_id}: Could not get viewport: {e}")
        
        await cognitive_delay("process")
        
        cycles_done = 0
        total_cycles = cfg.cycles
        
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: --- Cycle {cycles_done + 1}/{total_cycles if total_cycles > 0 else '∞'} ---")
            
            # ========== WATCH MAIN VIDEO ==========
            watch_success = await watch_direct_async(page, cfg)
            if not watch_success:
                logger.warning(f"Instance {cfg.instance_id}: Main video watch had issues")
            
            # ========== SUGGESTED VIDEO (Based on config chance) ==========
            # ✅ DECISION happens HERE in the main script
            if random.random() < cfg.suggested_chance:
                logger.info(f"Instance {cfg.instance_id}: Attempting suggested video")
                await watch_suggested_direct_async(page, cfg)
            
            cycles_done += 1
            
            # ========== PAUSE BETWEEN CYCLES ==========
            if total_cycles == 0 or cycles_done < total_cycles:
                pause = random.uniform(8, 20)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause:.1f}s between cycles")
                await asyncio.sleep(pause)
        
        logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycles")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Session error: {e}")
        logger.error(traceback.format_exc())
    finally:
        if browser:
            try:
                await browser.stop()
                logger.info(f"Instance {cfg.instance_id}: Browser closed")
            except:
                pass


# ========== MAIN ==========

def main():
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
            proxy=d.get("proxy", None),  # ✅ ADDED
            proxy_mode=d.get("proxy_mode", "none"),
            num_instances=d.get("num_instances", 1),
            referer=d.get("referer", None),
            traffic_source=d.get("traffic_source", "direct"),  # ✅ ADDED
            force_mobile=d.get("force_mobile", False),  # ✅ ADDED
            chrome_args=d.get("chrome_args", None),  # ✅ ADDED
            # ========== FINGERPRINT FIELDS ==========
            platform=d.get("platform", "Win32"),
            screen_width=d.get("screen_width", 1920),  # ✅ ADDED
            screen_height=d.get("screen_height", 1080),  # ✅ ADDED
            viewport_width=d.get("viewport_width", 1920),
            viewport_height=d.get("viewport_height", 950),
            plugins_length=d.get("plugins_length", 5),
            device_category=d.get("device_category", "desktop"),
            vendor=d.get("vendor", "Google Inc."),
            connection=d.get("connection", None),  # ✅ ADDED
            language=d.get("language", "en-US")
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        logger.info(f"Instance {cfg.instance_id} started in process {p.pid}")
        time.sleep(random.uniform(1, 3))
    
    for p in processes:
        p.join()
        logger.info(f"Process {p.pid} completed")
    
    logger.info("All YTDirect Pydoll sessions finished")


if __name__ == "__main__":
    main()