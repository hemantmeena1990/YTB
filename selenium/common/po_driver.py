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
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import PO token functions
try:
    from common.po_token import inject_visitor_cookie, warmup_youtube_embed, set_logger as set_po_logger
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location("po_token", PROJECT_ROOT / "common" / "po_token.py")
    po_token_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(po_token_module)
    inject_visitor_cookie = po_token_module.inject_visitor_cookie
    warmup_youtube_embed = po_token_module.warmup_youtube_embed
    set_po_logger = po_token_module.set_logger

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from common.utils import get_random_resolution

# Global logger
_script_logger = None

def set_logger(logger):
    global _script_logger
    _script_logger = logger
    set_po_logger(logger)


def load_proxy_list():
    """Load working proxies from proxy_list.txt"""
    proxy_file = PROJECT_ROOT / "data" / "proxy_list.txt"
    proxies = []
    if proxy_file.exists():
        with open(proxy_file, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
    return proxies


def load_blacklist():
    """Load blacklisted proxies from blacklist.txt"""
    blacklist_file = PROJECT_ROOT / "data" / "blacklist.txt"
    blacklist = []
    if blacklist_file.exists():
        with open(blacklist_file, 'r') as f:
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
    
    user_selected_source = getattr(cfg, 'po_token_source', 'native')
    proxy_mode = getattr(cfg, 'proxy_mode', 'none')
    
    if _script_logger:
        _script_logger.info(f"Instance {cfg.instance_id}: PO token source: {user_selected_source}")
        _script_logger.info(f"Instance {cfg.instance_id}: Proxy mode: {proxy_mode}")
    
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
        w, h = get_random_resolution(cfg.is_mobile)
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
    if proxy_mode == 'tor_service':
        # Tor Service on port 9050
        options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
        options.add_argument('--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost')
        options.add_argument('--proxy-bypass-list=<-loopback>')
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [TOR] Using Tor Service on port 9050")
        
    elif proxy_mode == 'tor_browser':
        # Tor Browser on port 9150
        options.add_argument('--proxy-server=socks5://127.0.0.1:9150')
        options.add_argument('--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost')
        options.add_argument('--proxy-bypass-list=<-loopback>')
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [TOR] Using Tor Browser on port 9150")
        
    elif proxy_mode == 'list':
        # Rotating proxy from list
        total_instances = getattr(cfg, 'num_instances', 1)
        proxy_url = get_proxy_for_instance(cfg.instance_id, total_instances)
        
        if proxy_url:
            # Parse proxy URL to extract host:port
            proxy_host = proxy_url.split('://', 1)[1] if '://' in proxy_url else proxy_url
            if '@' in proxy_host:
                proxy_host = proxy_host.split('@', 1)[1]
            options.add_argument(f'--proxy-server={proxy_host}')
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using proxy: {proxy_host}")
        else:
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [PROXY] No working proxies available")
    else:
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] No proxy - direct connection")
    
    # Create driver
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
    
    # Set custom referer if configured
    if hasattr(cfg, 'referer') and cfg.referer:
        try:
            driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                'headers': {'Referer': cfg.referer}
            })
        except:
            pass
    
    # For native mode, warm up with embedded player to generate token
    if user_selected_source == 'native':
        native_visitor = warmup_youtube_embed(driver, cfg.instance_id)
        if native_visitor:
            cfg.visitor_id = native_visitor
            inject_visitor_cookie(driver, cfg.instance_id, native_visitor)
    
    return driver, profile_dir