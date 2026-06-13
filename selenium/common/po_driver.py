#!/usr/bin/env python3
"""
Extended driver creation with PO token support and custom referer
Supports all proxy modes: none, tor_service, tor_browser, list
"""

import sys
import os
import time
import tempfile
import uuid
import shutil
import random
import json
import threading
import socket
from pathlib import Path

# ========== PATH SETUP ==========
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "common"))

# ========== Import PO token functions ==========
try:
    from common.po_token import inject_visitor_cookie, warmup_youtube_embed, set_logger as set_po_logger
except ImportError:
    import importlib.util
    po_token_path = PROJECT_ROOT / "common" / "po_token.py"
    if po_token_path.exists():
        spec = importlib.util.spec_from_file_location("po_token", po_token_path)
        po_token_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(po_token_module)
        inject_visitor_cookie = po_token_module.inject_visitor_cookie
        warmup_youtube_embed = po_token_module.warmup_youtube_embed
        set_po_logger = po_token_module.set_logger
    else:
        def inject_visitor_cookie(*args, **kwargs): pass
        def warmup_youtube_embed(*args, **kwargs): return None
        def set_po_logger(*args, **kwargs): pass

# ========== Import SOCKS to HTTP converter ==========
try:
    from common.socks_to_http import get_http_proxy_for_socks, start_tor_bridge, is_socks_proxy
except ImportError:
    import importlib.util
    socks_path = PROJECT_ROOT / "common" / "socks_to_http.py"
    if socks_path.exists():
        spec = importlib.util.spec_from_file_location("socks_to_http", socks_path)
        socks_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(socks_module)
        get_http_proxy_for_socks = socks_module.get_http_proxy_for_socks
        start_tor_bridge = socks_module.start_tor_bridge
        is_socks_proxy = socks_module.is_socks_proxy
    else:
        def get_http_proxy_for_socks(proxy_url, force_new=False):
            return proxy_url
        def start_tor_bridge(tor_port=9050, http_port=8888):
            return f"socks5://127.0.0.1:{tor_port}"
        def is_socks_proxy(proxy_url):
            return False

# ========== Import from selenium/common ==========
try:
    from utils import get_random_resolution
except ImportError:
    from common.utils import get_random_resolution

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Global logger
_script_logger = None

def set_logger(logger):
    global _script_logger
    _script_logger = logger
    try:
        set_po_logger(logger)
    except:
        pass


def load_proxy_list():
    """Load working proxies from proxy_list.txt"""
    proxy_file = PROJECT_ROOT / "data" / "proxy_list.txt"
    proxies = []
    if proxy_file.exists():
        with open(proxy_file, 'r', encoding='utf-8', errors='ignore') as f:
            proxies = [line.strip() for line in f if line.strip() and '<' not in line]
    return proxies


def load_blacklist():
    """Load blacklisted proxies from blacklist.txt"""
    blacklist_file = PROJECT_ROOT / "data" / "blacklist.txt"
    blacklist = []
    if blacklist_file.exists():
        with open(blacklist_file, 'r', encoding='utf-8', errors='ignore') as f:
            blacklist = [line.strip() for line in f if line.strip()]
    return blacklist


def get_proxy_for_instance(instance_id, total_instances):
    """Get a proxy for a specific instance using round-robin distribution"""
    proxies = load_proxy_list()
    blacklist = load_blacklist()
    available = [p for p in proxies if p not in blacklist]
    
    if not available:
        return None
    
    proxy_index = (instance_id - 1) % len(available)
    return available[proxy_index]


def create_driver_with_po_token(cfg, profile_prefix):
    """Create Chrome driver with PO token and proxy support"""
    
    user_selected_source = getattr(cfg, 'po_token_source', 'native')
    proxy_mode = getattr(cfg, 'proxy_mode', 'none')
    
    if _script_logger:
        _script_logger.info(f"Instance {cfg.instance_id}: PO token source: {user_selected_source}")
        _script_logger.info(f"Instance {cfg.instance_id}: Proxy mode: {proxy_mode}")
    
    # ========== SETUP PROFILE DIRECTORY ==========
    temp_base = os.path.join(tempfile.gettempdir(), "yt_automation")
    os.makedirs(temp_base, exist_ok=True)
    
    # Clean up old profiles
    try:
        current_time = time.time()
        for item in os.listdir(temp_base):
            item_path = os.path.join(temp_base, item)
            if os.path.isdir(item_path) and item.startswith(profile_prefix[:10]):
                if current_time - os.path.getmtime(item_path) > 3600:
                    shutil.rmtree(item_path, ignore_errors=True)
    except:
        pass
    
    # Create new profile
    unique_id = f"{int(time.time())}_{cfg.instance_id}_{uuid.uuid4().hex[:12]}"
    profile_dir = os.path.join(temp_base, f"{profile_prefix}_{unique_id}")
    
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except:
            pass
    os.makedirs(profile_dir, exist_ok=True)
    
    # Setup Chrome options
    options = Options()
    
    if cfg.headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=en-US")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(f"user-agent={cfg.user_agent}")
    
    if not cfg.headless:
        try:
            w, h = get_random_resolution(cfg.is_mobile)
        except:
            w, h = 1920, 1080
        options.add_argument(f"--window-size={w},{h}")
    else:
        options.add_argument("--window-size=1920,1080")
    
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    
    random_port = random.randint(40000, 49999)
    options.add_argument(f"--remote-debugging-port={random_port}")
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    # ========== PROXY CONFIGURATION ==========
    
    # Check if a specific proxy was assigned
    if hasattr(cfg, 'proxy') and cfg.proxy:
        proxy_url = cfg.proxy
        
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Processing: {proxy_url[:80]}")
        
        # Convert SOCKS to HTTP if needed
        http_proxy = get_http_proxy_for_socks(proxy_url)
        
        if http_proxy and http_proxy != proxy_url:
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [SOCKS] Converted to HTTP bridge")
            proxy_host = http_proxy.split('://', 1)[1] if '://' in http_proxy else http_proxy
            options.add_argument(f'--proxy-server={proxy_host}')
        elif http_proxy:
            proxy_host = http_proxy.split('://', 1)[1] if '://' in http_proxy else http_proxy
            if '@' in proxy_host:
                proxy_host = proxy_host.split('@', 1)[1]
            options.add_argument(f'--proxy-server={proxy_host}')
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [HTTP] Using proxy")
        
        if hasattr(cfg, 'current_proxy'):
            cfg.current_proxy = proxy_url
    
    elif proxy_mode == 'tor_service':
        tor_bridge = start_tor_bridge(tor_port=9050, http_port=8888)
        if tor_bridge:
            proxy_host = tor_bridge.split('://', 1)[1]
            options.add_argument(f'--proxy-server={proxy_host}')
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [TOR] Using HTTP bridge on port 8888")
        else:
            options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [TOR] Bridge failed, using SOCKS5")
    
    # In po_driver.py, for Tor mode:
    elif proxy_mode == 'tor_browser':
        # Start bridge in background (doesn't block)
        tor_bridge = start_tor_bridge(tor_port=9150, http_port=8889)
        if tor_bridge:
            proxy_host = tor_bridge.split('://', 1)[1]
            options.add_argument(f'--proxy-server={proxy_host}')
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [TOR] Using HTTP bridge")
        else:
            options.add_argument('--proxy-server=socks5://127.0.0.1:9150')
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [TOR] Bridge failed, using SOCKS5")
    
    elif proxy_mode == 'list':
        total_instances = getattr(cfg, 'num_instances', 1)
        proxy_url = get_proxy_for_instance(cfg.instance_id, total_instances)
        
        if proxy_url:
            http_proxy = get_http_proxy_for_socks(proxy_url)
            if http_proxy:
                proxy_host = http_proxy.split('://', 1)[1] if '://' in http_proxy else http_proxy
                if '@' in proxy_host:
                    proxy_host = proxy_host.split('@', 1)[1]
                options.add_argument(f'--proxy-server={proxy_host}')
                if _script_logger:
                    _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using proxy from list")
        else:
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [PROXY] No proxy available")
    else:
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Direct connection")
    
    # ========== SET CUSTOM REFERER (BEFORE NAVIGATION) ==========
    if hasattr(cfg, 'referer') and cfg.referer:
        options.add_argument(f'--referer={cfg.referer}')
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [REFERER] Set via command line: {cfg.referer}")
    
    # ========== CREATE DRIVER (ONCE!) ==========
    service = Service(ChromeDriverManager().install())
    service.creation_flags = 0x08000000
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    
    if _script_logger:
        _script_logger.info(f"Instance {cfg.instance_id}: Created profile at {profile_dir}")
    
    # Add marker file
    marker_file = os.path.join(profile_dir, f"instance_{cfg.instance_id}.lock")
    with open(marker_file, 'w') as f:
        f.write(f"Created at: {time.time()}\nInstance: {cfg.instance_id}")
        f.write(f"Proxy mode: {proxy_mode}\n")
        if hasattr(cfg, 'proxy') and cfg.proxy:
            f.write(f"Assigned proxy: {cfg.proxy}\n")
        if hasattr(cfg, 'referer') and cfg.referer:
            f.write(f"Referer: {cfg.referer}\n")
    
    # ========== SET CDP REFERER (for additional requests) ==========
    if hasattr(cfg, 'referer') and cfg.referer:
        try:
            driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                'headers': {'Referer': cfg.referer}
            })
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [REFERER] Set via CDP: {cfg.referer}")
        except Exception as e:
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [REFERER] CDP failed: {e}")
    
    # For native mode, warm up with embedded player to generate token
    if user_selected_source == 'native':
        native_visitor = warmup_youtube_embed(driver, cfg.instance_id)
        if native_visitor:
            cfg.visitor_id = native_visitor
            inject_visitor_cookie(driver, cfg.instance_id, native_visitor)
    
    return driver, profile_dir