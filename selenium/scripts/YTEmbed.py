#!/usr/bin/env python3
"""
YouTube Embed Watch - Dynamic Domain via Chrome Host Resolver Rules
- Maps traffic source domain to localhost dynamically
- Origin parameters match the traffic source
- YouTube sees embed from actual platform domain
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
import tempfile
import http.server
import socketserver
import threading
import socket
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime
from multiprocessing import Process
from dataclasses import dataclass
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# ========== PATH SETUP ==========
_script_path = Path(__file__).resolve()
PROJECT_ROOT = _script_path.parent.parent.parent
COMMON_ROOT = PROJECT_ROOT / "common"
SELENIUM_COMMON_ROOT = PROJECT_ROOT / "selenium" / "common"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(COMMON_ROOT))
sys.path.insert(0, str(SELENIUM_COMMON_ROOT))


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

# Human Behavior
_human_behavior_path = COMMON_ROOT / "human_behavior.py"
_human_behavior_module = _load_module_from_file("human_behavior", _human_behavior_path)
watch_with_human_behavior = _human_behavior_module.watch_with_human_behavior
attempt_video_playback_with_retry = _human_behavior_module.attempt_video_playback_with_retry
handle_all_popups = _human_behavior_module.handle_all_popups
is_video_playing = _human_behavior_module.is_video_playing
human_delay = _human_behavior_module.human_delay

# PO Driver
_po_driver_path = SELENIUM_COMMON_ROOT / "po_driver.py"
_po_driver_module = _load_module_from_file("po_driver", _po_driver_path)
create_driver_with_po_token = _po_driver_module.create_driver_with_po_token
set_driver_logger = _po_driver_module.set_logger

# Utils
_utils_path = SELENIUM_COMMON_ROOT / "utils.py"
_utils_module = _load_module_from_file("utils", _utils_path)
handle_cookies = _utils_module.handle_cookies
get_variable_watch_time = _utils_module.get_variable_watch_time
wait_for_page_load = _utils_module.wait_for_page_load

# ========== LOGGING ==========
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_filename = LOG_DIR / f"YTEmbed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("YTEmbed")
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

logger.info(f"YTEmbed.py started - PID: {os.getpid()}")
logger.info(f"Project root: {PROJECT_ROOT}")


# ========== TRAFFIC SOURCE TO DOMAIN MAPPING ==========

TRAFFIC_DOMAIN_MAP = {
    'google_search': 'www.google.com',
    'whatsapp_web': 'web.whatsapp.com',
    'instagram': 'www.instagram.com',
    'telegram_web': 'web.telegram.org',
    'github': 'github.com',
    'bing': 'www.bing.com',
    'twitter': 'twitter.com',
    'reddit': 'www.reddit.com',
    'facebook': 'www.facebook.com',
    'linkedin': 'www.linkedin.com',
    'discord': 'discord.com',
    'snapchat': 'www.snapchat.com',
}

# Traffic source to widget_referrer URL mapping
WIDGET_REFERRER_MAP = {
    'google_search': 'https://www.google.com',
    'whatsapp_web': 'https://web.whatsapp.com',
    'instagram': 'https://www.instagram.com',
    'telegram_web': 'https://web.telegram.org',
    'github': 'https://github.com',
    'bing': 'https://www.bing.com',
    'twitter': 'https://twitter.com',
    'reddit': 'https://www.reddit.com',
    'facebook': 'https://www.facebook.com',
    'linkedin': 'https://www.linkedin.com',
    'discord': 'https://discord.com',
    'snapchat': 'https://www.snapchat.com',
}

WIDGET_REFERRER_PLATFORMS = [
    "https://www.youtube.com/feed/trending",
    "https://www.youtube.com/feed/subscriptions",
    "https://m.youtube.com/",
    "https://www.youtube.com/results?search_query=shorts",
    "https://www.google.com",
    "https://www.facebook.com",
    "https://www.instagram.com",
    "https://t.co",
    "https://www.bing.com"
]


# ========== DOMAIN CACHE FOR RANDOM ==========
_domain_cache = {}


# ========== CONFIGURATION ==========
@dataclass
class SessionConfig:
    instance_id: int
    url: str
    video_id: str
    video_title: str
    traffic_source: str
    min_watch_time: int
    max_watch_time: int
    headless: bool
    user_agent: str
    is_mobile: bool
    widget_referrer: str = None
    traffic_source_type: str = "fixed"
    traffic_source_raw: str = None
    cycles: int = 1
    po_token: str = None
    visitor_id: str = None
    po_token_source: str = "external"
    proxy: str = None
    proxy_mode: str = "none"
    num_instances: int = 1
    current_proxy: str = None
    cycle_number: int = 1
    referer: str = None
    chrome_args: list = None
    automation_version: str = "selenium"
    use_undetected: bool = False


# ========== DYNAMIC DOMAIN FUNCTIONS ==========

def get_domain_for_traffic_source(traffic_source: str, instance_id: int = None) -> str:
    """
    Get the domain name for a given traffic source.
    Uses cache to ensure consistency per instance when traffic_source is 'random'.
    """
    # If traffic_source is 'random', pick once and cache
    if traffic_source == 'random':
        if instance_id and instance_id in _domain_cache:
            return _domain_cache[instance_id]
        
        # Pick a random domain
        domain = random.choice(list(TRAFFIC_DOMAIN_MAP.values()))
        if instance_id:
            _domain_cache[instance_id] = domain
            logger.info(f"Instance {instance_id}: Random domain selected: {domain}")
        return domain
    
    if traffic_source and traffic_source in TRAFFIC_DOMAIN_MAP:
        return TRAFFIC_DOMAIN_MAP[traffic_source]
    
    # Fallback: pick a random domain
    logger.warning(f"Unknown traffic source '{traffic_source}', using random domain")
    return random.choice(list(TRAFFIC_DOMAIN_MAP.values()))


def get_resolver_rule(traffic_source: str, instance_id: int = None) -> str:
    """Generate Chrome resolver rule for the traffic source domain."""
    domain = get_domain_for_traffic_source(traffic_source, instance_id)
    return f"MAP {domain} 127.0.0.1"


def get_chrome_resolver_args(traffic_source: str, instance_id: int = None) -> list:
    """Return Chrome arguments for host resolver rules."""
    domain = get_domain_for_traffic_source(traffic_source, instance_id)
    
    import platform
    if platform.system() == 'Windows':
        resolver_rule = f"MAP {domain} 127.0.0.1"
        return [
            f'--host-resolver-rules={resolver_rule}',
            '--ignore-certificate-errors',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-ipv6'  # <-- Force IPv4
        ]
    else:
        resolver_rule = f'"MAP {domain} 127.0.0.1"'
        return [
            f'--host-resolver-rules={resolver_rule}',
            '--ignore-certificate-errors',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process'
        ]


# ========== BUILD HTML WITH DYNAMIC DOMAIN ==========

def build_embed_html(video_id: str, widget_referrer: str, traffic_source: str, po_token: str = None, instance_id: int = None) -> tuple:
    """
    Build HTML with YouTube Player API using dynamic domain.
    """
    random_start = random.randint(0, 10)
    
    # Human-like speed variation
    speeds = [0.75, 0.85, 0.9, 0.95, 1.0, 1.0, 1.05, 1.1, 1.15, 1.25]
    random_speed = random.choice(speeds)
    
    # Get domain from traffic source (with cache for 'random')
    domain = get_domain_for_traffic_source(traffic_source, instance_id)
    
    # Build origins using the traffic source domain
    origin_url = f"https://{domain}"
    forigin_url = f"https://{domain}/multi-browser.html"
    gporigin_url = f"https://{domain}/"
    
    # Use traffic source as widget_referrer if not provided
    if not widget_referrer:
        widget_referrer = WIDGET_REFERRER_MAP.get(traffic_source, "https://www.google.com")
    
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>YouTube Embed Player</title>
    <script src="https://www.youtube.com/iframe_api"></script>
    <style>
        body {{ margin: 0; background: #000; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; }}
        #player {{ width: 100%; height: 100%; }}
    </style>
</head>
<body>
    <div id="player"></div>
    <script>
        var player;
        var videoId = '{video_id}';
        var randomStart = {random_start};
        var randomSpeed = {random_speed};
        var widgetReferrer = '{widget_referrer}';
        var origin = '{origin_url}';
        var forigin = '{forigin_url}';
        var gporigin = '{gporigin_url}';
        var unmuteDelay = Math.random() * 3000 + 2000;
        
        function onYouTubeIframeAPIReady() {{
            console.log('YouTube Iframe API ready');
            player = new YT.Player('player', {{
                height: '100%',
                width: '100%',
                videoId: videoId,
                playerVars: {{
                    'autoplay': 1,
                    'mute': 1,
                    'vq': 'default',
                    'rel': 0,
                    'controls': 1,
                    'modestbranding': 1,
                    'start': randomStart,
                    'origin': origin,
                    'playlist': videoId,
                    'widget_referrer': widgetReferrer,
                    'enablejsapi': 1,
                    'forigin': forigin,
                    'aoriginsup': 1,
                    'gporigin': gporigin
                }},
                events: {{
                    'onReady': function(event) {{
                        console.log('Player ready');
                        event.target.setPlaybackRate(randomSpeed);
                        console.log('Speed set to: ' + randomSpeed);
                    }},
                    'onStateChange': function(event) {{
                        console.log('State changed: ' + event.data);
                        if (event.data == 1) {{
                            console.log('Video is playing');
                            var qualities = ['small', 'medium', 'large', 'hd720'];
                            var selectedQuality = qualities[Math.floor(Math.random() * qualities.length)];
                            event.target.setPlaybackQuality(selectedQuality);
                            
                            setTimeout(function() {{
                                try {{
                                    event.target.unMute();
                                    event.target.setVolume(100);
                                    console.log('Unmuted');
                                }} catch(e) {{
                                    console.log('Unmute error: ' + e);
                                }}
                            }}, unmuteDelay);
                        }}
                        if (event.data == 2) {{
                            console.log('Video paused, resuming...');
                            setTimeout(function() {{
                                if (event.target && typeof event.target.playVideo === 'function') {{
                                    event.target.playVideo();
                                }}
                            }}, 500);
                        }}
                    }},
                    'onError': function(event) {{
                        console.log('Player error: ' + event.data);
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>'''
    
    return html_content, random_start, random_speed, origin_url, domain


# ========== EMBED WATCH ==========

def watch_embed(driver, cfg: SessionConfig):
    """Watch embed video using dynamic domain via Chrome resolver rules."""
    html_file = None
    httpd = None
    server_thread = None
    port = None
    original_dir = os.getcwd()
    
    try:
        # Determine widget_referrer from traffic source
        widget_referrer = cfg.widget_referrer
        if not widget_referrer:
            widget_referrer = WIDGET_REFERRER_MAP.get(cfg.traffic_source)
        if not widget_referrer:
            widget_referrer = random.choice(WIDGET_REFERRER_PLATFORMS)
            logger.info(f"Instance {cfg.instance_id}: No widget_referrer, using random: {widget_referrer}")
        
        # Build HTML with dynamic domain - pass instance_id for consistency
        html_content, random_start, random_speed, origin_url, domain = build_embed_html(
            cfg.video_id,
            widget_referrer,
            cfg.traffic_source,
            cfg.po_token,
            cfg.instance_id
        )
        
        logger.info(f"Instance {cfg.instance_id}: ========== EMBED CONTEXT ==========")
        logger.info(f"Instance {cfg.instance_id}: Traffic Source: {cfg.traffic_source}")
        logger.info(f"Instance {cfg.instance_id}: Widget Referrer: {widget_referrer}")
        logger.info(f"Instance {cfg.instance_id}: Domain: {domain}")
        logger.info(f"Instance {cfg.instance_id}: Origin: {origin_url}")
        logger.info(f"Instance {cfg.instance_id}: Random Start: {random_start}s")
        logger.info(f"Instance {cfg.instance_id}: Random Speed: {random_speed}x")
        logger.info(f"Instance {cfg.instance_id}: PO Token: {cfg.po_token is not None}")
        logger.info(f"Instance {cfg.instance_id}: ====================================")

        # Write HTML to temp file
        temp_dir = Path(tempfile.gettempdir()) / "yt_embed_context"
        temp_dir.mkdir(exist_ok=True)
        html_file = temp_dir / f"embed_{cfg.video_id}_{cfg.instance_id}_{int(time.time())}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Instance {cfg.instance_id}: Created HTML: {html_file}")

        # Find available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 0))  # <-- Bind to all interfaces
            port = s.getsockname()[1]

        # Start HTTP server on all interfaces
        os.chdir(temp_dir)
        handler = http.server.SimpleHTTPRequestHandler
        
        # ========== FIX: Bind to 0.0.0.0 (all interfaces) ==========
        httpd = socketserver.TCPServer(("0.0.0.0", port), handler)
        # ============================================================
        
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        logger.info(f"Instance {cfg.instance_id}: HTTP server on port {port} (0.0.0.0)")
        time.sleep(1)

        # Navigate to the dynamic domain
        page_url = f"http://127.0.0.1:{port}/{html_file.name}"
        logger.info(f"Instance {cfg.instance_id}: Loading: {page_url} (using 127.0.0.1 - bypasses DNS/proxy/HSTS)")
        
        driver.get(page_url)
        wait_for_page_load(driver, 20)
        time.sleep(5)

        # Handle popups
        handle_all_popups(driver, cfg.instance_id)
        handle_cookies(driver, cfg.instance_id)

        # ========== Wait for video to start ==========
        playback_success = False
        logger.info(f"Instance {cfg.instance_id}: Waiting for video to start...")
        time.sleep(5)
        
        for attempt in range(5):
            time.sleep(2)
            try:
                driver.switch_to.frame("player")
                playback_success = driver.execute_script("""
                    var video = document.querySelector('video');
                    if (video) {
                        var isPlaying = !video.paused && !video.ended && video.readyState >= 2;
                        return isPlaying;
                    }
                    return false;
                """)
                driver.switch_to.default_content()
                
                if playback_success:
                    logger.info(f"Instance {cfg.instance_id}: ✅ Video is playing (attempt {attempt+1})")
                    break
                else:
                    logger.info(f"Instance {cfg.instance_id}: ⏳ Video not playing yet (attempt {attempt+1}/5)")
                    
            except Exception as e:
                driver.switch_to.default_content()
                logger.debug(f"Instance {cfg.instance_id}: Detection attempt {attempt+1} failed: {e}")
                time.sleep(1)
        
        if not playback_success:
            logger.warning(f"Instance {cfg.instance_id}: ⚠️ Video may not be playing, continuing anyway")

        # ========== Watch ==========
        watch_time = get_variable_watch_time(cfg.min_watch_time, cfg.max_watch_time)
        logger.info(f"Instance {cfg.instance_id}: Watching for {watch_time}s")
        watch_with_human_behavior(driver, watch_time, cfg.is_mobile)
        return True

    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Error: {e}")
        logger.error(traceback.format_exc())
        return False

    finally:
        os.chdir(original_dir)
        if httpd:
            try:
                httpd.shutdown()
                logger.info(f"Instance {cfg.instance_id}: HTTP server stopped")
            except:
                pass
        if html_file and os.path.exists(html_file):
            try:
                os.unlink(html_file)
                logger.info(f"Instance {cfg.instance_id}: Deleted HTML file")
            except:
                pass
                

# ========== SESSION RUNNER ==========

def run_session(cfg: SessionConfig):
    driver = None
    profile_dir = None
    try:
        logger.info(f"Instance {cfg.instance_id}: ========== Starting YTEmbed Session ==========")
        logger.info(f"Instance {cfg.instance_id}: Video ID: {cfg.video_id}")
        
        # Log based on traffic_source_type
        if cfg.traffic_source_type == 'random':
            logger.info(f"Instance {cfg.instance_id}: 🎲 Random traffic source selected → {cfg.traffic_source}")
        else:
            logger.info(f"Instance {cfg.instance_id}: Traffic Source: {cfg.traffic_source}")
        
        logger.info(f"Instance {cfg.instance_id}: Widget Referrer: {cfg.widget_referrer}")
        logger.info(f"Instance {cfg.instance_id}: Cycles: {cfg.cycles}")
        
        # Add Chrome resolver rules based on traffic source (pass instance_id for cache)
        resolver_args = get_chrome_resolver_args(cfg.traffic_source, cfg.instance_id)
        if not hasattr(cfg, 'chrome_args') or cfg.chrome_args is None:
            cfg.chrome_args = []
        cfg.chrome_args.extend(resolver_args)
        
        logger.info(f"Instance {cfg.instance_id}: Chrome Resolver Rule: {get_resolver_rule(cfg.traffic_source, cfg.instance_id)}")
        
        driver, profile_dir = create_driver_with_po_token(cfg, "yt_embed_cache")
        
        cycles_done = 0
        total_cycles = cfg.cycles
        while total_cycles == 0 or cycles_done < total_cycles:
            logger.info(f"Instance {cfg.instance_id}: Cycle {cycles_done + 1}/{total_cycles}")
            watch_embed(driver, cfg)
            cycles_done += 1
            if cycles_done < total_cycles:
                pause = random.uniform(5, 15)
                logger.info(f"Instance {cfg.instance_id}: Pausing {pause:.1f}s")
                time.sleep(pause)
        
        logger.info(f"Instance {cfg.instance_id}: Completed {cycles_done} cycles")
        
    except Exception as e:
        logger.error(f"Instance {cfg.instance_id}: Session error: {e}")
        logger.error(traceback.format_exc())
    finally:
        if driver:
            try:
                driver.quit()
                logger.info(f"Instance {cfg.instance_id}: Driver closed")
            except:
                pass
        if profile_dir and os.path.exists(profile_dir):
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
                logger.info(f"Instance {cfg.instance_id}: Profile deleted")
            except:
                pass


# ========== MAIN ==========

def main():
    if len(sys.argv) < 2 or not sys.argv[1].endswith('.json'):
        logger.error("Usage: python YTEmbed.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    logger.info(f"Loading config from: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            instances = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)
    
    logger.info(f"Starting YTEmbed with {len(instances)} instance(s)")
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
        widget_referrer = d.get("widget_referrer", None)
        traffic_source_type = d.get("traffic_source_type", "fixed")
        traffic_source_raw = d.get("traffic_source_raw", traffic_source)
        
        logger.info(f"[TRAFFIC] Instance {d.get('instance_id', 0)}: {traffic_source} (type: {traffic_source_type})")
        logger.info(f"[WIDGET] Instance {d.get('instance_id', 0)}: {widget_referrer}")
        
        cfg = SessionConfig(
            instance_id=d.get("instance_id", 0),
            url=d.get("url", ""),
            video_id=video_id,
            video_title=d.get("video_title", video_id),
            traffic_source=traffic_source,
            min_watch_time=d.get("min_watch_time", 30),
            max_watch_time=d.get("max_watch_time", 180),
            headless=d.get("headless", False),
            user_agent=d.get("user_agent", ""),
            is_mobile=d.get("is_mobile", False),
            widget_referrer=widget_referrer,
            traffic_source_type=traffic_source_type,
            traffic_source_raw=traffic_source_raw,
            cycles=d.get("cycles", 1),
            po_token=po_token,
            visitor_id=visitor_id,
            po_token_source=po_token_source,
            proxy=d.get("proxy", None),
            proxy_mode=d.get("proxy_mode", "none"),
            num_instances=d.get("num_instances", 1),
            current_proxy=d.get("proxy", None),
            cycle_number=d.get("cycle_number", 1),
            referer=d.get("referer", None)
            automation_version=d.get("automation_version", "selenium"),
            use_undetected=d.get("use_undetected", False)
        )
        
        p = Process(target=run_session, args=(cfg,))
        processes.append(p)
        p.start()
        logger.info(f"Instance {cfg.instance_id} started in process {p.pid}")
        time.sleep(random.uniform(1, 3))
    
    for p in processes:
        p.join()
        logger.info(f"Process {p.pid} completed")
    
    logger.info("All YTEmbed sessions finished")


if __name__ == "__main__":
    main()