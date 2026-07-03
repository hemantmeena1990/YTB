#!/usr/bin/env python3
"""
Pydoll Driver - YouTube Automation with Pydoll
Uses Pydoll's native CDP connection for stealth automation
"""

import os
import sys
import time
import random
import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple, Any

# ========== PATH SETUP ==========
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "common"))

# ========== Pydoll Imports ==========
PYDOLL_AVAILABLE = False

try:
    from pydoll.browser import Chrome
    from pydoll.browser.options import Options
    PYDOLL_AVAILABLE = True
    print("[PYDOLL] ✅ Pydoll imported successfully from pydoll.browser")
except ImportError:
    try:
        from pydoll_python.browser import Chrome
        from pydoll_python.browser.options import Options
        PYDOLL_AVAILABLE = True
        print("[PYDOLL] ✅ Pydoll imported successfully from pydoll_python.browser")
    except ImportError:
        print("[PYDOLL] ❌ Pydoll import failed. Please install: pip install pydoll-python")

if not PYDOLL_AVAILABLE:
    print("[PYDOLL] ⚠️ Pydoll not available. Please install: pip install pydoll-python")

# ========== Common Imports ==========
from common.po_token import add_po_token_to_url
from common.proxy_manager import get_rotating_proxy, get_working_proxies
from common.socks_to_http import start_tor_bridge, get_http_proxy_for_socks

# Global logger
_script_logger = None


def set_logger(logger):
    """Set global logger for driver"""
    global _script_logger
    _script_logger = logger


def _get_proxy_url(cfg):
    """
    Get proxy URL for Pydoll.
    Converts SOCKS5 to HTTP bridge if needed.
    """
    proxy_url = None
    proxy_mode = getattr(cfg, 'proxy_mode', 'none')
    
    if cfg.proxy:
        # Direct proxy from config
        proxy_url = cfg.proxy
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using direct proxy: {proxy_url[:60]}")
        return proxy_url
    
    elif proxy_mode == 'tor_service':
        # Use HTTP bridge for Tor Service (port 9050)
        http_bridge = start_tor_bridge(tor_port=9050, http_port=8888)
        proxy_url = http_bridge if http_bridge else "http://127.0.0.1:8888"
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using Tor Service HTTP bridge: {proxy_url}")
        return proxy_url
    
    elif proxy_mode == 'tor_browser':
        # Use HTTP bridge for Tor Browser (port 9150)
        http_bridge = start_tor_bridge(tor_port=9150, http_port=8889)
        proxy_url = http_bridge if http_bridge else "http://127.0.0.1:8889"
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using Tor Browser HTTP bridge: {proxy_url}")
        return proxy_url
    
    elif proxy_mode == 'list':
        # Get proxy from rotating pool
        proxy_url = get_rotating_proxy()
        if not proxy_url:
            working = get_working_proxies()
            if working:
                proxy_url = random.choice(working)
        
        if proxy_url:
            # ✅ Convert SOCKS5 to HTTP bridge if needed
            if 'socks5://' in proxy_url or 'socks4://' in proxy_url:
                http_proxy = get_http_proxy_for_socks(proxy_url)
                if http_proxy:
                    proxy_url = http_proxy
                    if _script_logger:
                        _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Converted SOCKS to HTTP bridge")
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using rotating proxy: {proxy_url[:60]}")
            return proxy_url
        else:
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [PROXY] No proxy available")
    
    return None


async def create_driver_with_po_token_pydoll(cfg, profile_prefix: str = "yt_pydoll_cache"):
    """
    Create Pydoll browser with PO token and fingerprint support.
    """
    if not PYDOLL_AVAILABLE:
        raise ImportError("Pydoll is not available. Install: pip install pydoll-python")
    
    if _script_logger:
        _script_logger.info(f"Instance {cfg.instance_id}: 🚀 Starting Pydoll browser...")
        _script_logger.info(f"Instance {cfg.instance_id}: 📱 Platform: {cfg.platform}")
        _script_logger.info(f"Instance {cfg.instance_id}: 📱 Device: {cfg.device_category}")
        _script_logger.info(f"Instance {cfg.instance_id}: 🔌 Proxy Mode: {cfg.proxy_mode}")
    
    try:
        # ========== Setup Chrome Options ==========
        # Try using Options class if available
        try:
            options = Options()
        except:
            options = {}
        
        # User Agent
        if cfg.user_agent:
            if hasattr(options, 'user_agent'):
                options.user_agent = cfg.user_agent
        
        # Headless
        if cfg.headless:
            if hasattr(options, 'headless'):
                options.headless = True
        
        # Window Size
        if cfg.viewport_width and cfg.viewport_height:
            if hasattr(options, 'window_size'):
                options.window_size = (cfg.viewport_width, cfg.viewport_height)
        
        # ========== PROXY SETUP ==========
        proxy_url = _get_proxy_url(cfg)
        
        if proxy_url:
            # ✅ Pydoll accepts proxy via chrome_arguments
            if hasattr(options, 'chrome_arguments'):
                options.chrome_arguments = [
                    f'--proxy-server={proxy_url}',
                    '--proxy-bypass-list=<-loopback>'
                ]
            else:
                # If Options doesn't have chrome_arguments, use direct dict
                if isinstance(options, dict):
                    options['chrome_arguments'] = [
                        f'--proxy-server={proxy_url}',
                        '--proxy-bypass-list=<-loopback>'
                    ]
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Applied via chrome_arguments")
        else:
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Direct connection")
        
        # ========== CHROME ARGUMENTS ==========
        chrome_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-gpu',
            '--disable-notifications',
            '--disable-extensions',
        ]
        
        # Add referer
        if cfg.referer:
            chrome_args.append(f'--referer={cfg.referer}')
        
        # Add custom chrome args
        if cfg.chrome_args:
            chrome_args.extend(cfg.chrome_args)
        
        # Apply chrome_arguments to options
        if hasattr(options, 'chrome_arguments'):
            # If options already has proxy args, extend them
            if not proxy_url:
                options.chrome_arguments = chrome_args
            else:
                options.chrome_arguments.extend(chrome_args)
        else:
            if isinstance(options, dict):
                if 'chrome_arguments' in options:
                    options['chrome_arguments'].extend(chrome_args)
                else:
                    options['chrome_arguments'] = chrome_args
        
        # ========== Launch Browser ==========
        # Try with Options if available
        try:
            if hasattr(options, 'chrome_arguments'):
                chrome = Chrome(options=options)
            else:
                chrome = Chrome(**options)
        except:
            chrome = Chrome()
        
        # Start browser
        tab = await chrome.start()
        
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: ✅ Browser launched")
        
        # Apply fingerprint enhancements
        await apply_fingerprint_enhancements(tab, cfg, cfg.instance_id)
        
        # Store PO token
        if cfg.po_token:
            tab._po_token = cfg.po_token
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: ✅ PO token stored")
        
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: ✅ Pydoll driver ready")
        
        return chrome, tab, None
        
    except Exception as e:
        if _script_logger:
            _script_logger.error(f"Instance {cfg.instance_id}: ❌ Failed to create Pydoll driver: {e}")
            import traceback
            _script_logger.error(traceback.format_exc())
        raise


async def apply_fingerprint_enhancements(page, cfg, instance_id):
    """Apply enhanced fingerprint overrides via CDP."""
    if not _script_logger:
        return
    
    try:
        user_agent = cfg.user_agent
        viewport_width = cfg.viewport_width
        viewport_height = cfg.viewport_height
        screen_width = cfg.screen_width
        screen_height = cfg.screen_height
        plugins_length = cfg.plugins_length
        device_category = cfg.device_category
        platform = cfg.platform
        language = cfg.language
        vendor = cfg.vendor
        
        import re
        chrome_version = '138'
        if user_agent:
            match = re.search(r'Chrome/(\d+)\.', user_agent)
            if match:
                chrome_version = match.group(1)
        
        # Build appVersion
        app_version = f'5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36'
        
        # Use screen dimensions for screen object
        screen_w = screen_width if screen_width else viewport_width
        screen_h = screen_height if screen_height else viewport_height
        
        script_source = f'''
            (function() {{
                const navProto = Object.getPrototypeOf(navigator);
                
                // webdriver hiding
                if (navigator.hasOwnProperty('webdriver')) {{
                    delete navigator.webdriver;
                }}
                Object.defineProperty(navProto, 'webdriver', {{
                    value: false,
                    writable: false,
                    configurable: false,
                    enumerable: false
                }});
                
                // Plugins
                Object.defineProperty(navProto, 'plugins', {{
                    get: function() {{
                        const pluginCount = {plugins_length if plugins_length is not None else 0};
                        const plugins = [];
                        for (let i = 0; i < pluginCount; i++) {{
                            plugins[i] = {{
                                name: 'PDF Viewer',
                                filename: 'internal-pdf-viewer',
                                description: 'Portable Document Format',
                                length: 1,
                                item: function(index) {{ return this; }},
                                namedItem: function(name) {{ return this; }}
                            }};
                        }}
                        plugins.length = pluginCount;
                        plugins.item = function(index) {{ return this[index] || null; }};
                        plugins.namedItem = function(name) {{
                            for (let i = 0; i < this.length; i++) {{
                                if (this[i].name === name) return this[i];
                            }}
                            return null;
                        }};
                        plugins.refresh = function() {{}};
                        Object.defineProperty(plugins, Symbol.toStringTag, {{
                            value: 'PluginArray',
                            enumerable: false
                        }});
                        return plugins;
                    }},
                    configurable: true
                }});
                
                // MIME Types
                Object.defineProperty(navProto, 'mimeTypes', {{
                    get: function() {{
                        const mimeTypes = [];
                        mimeTypes.length = 0;
                        mimeTypes.item = function(index) {{ return null; }};
                        mimeTypes.namedItem = function(name) {{ return null; }};
                        Object.defineProperty(mimeTypes, Symbol.toStringTag, {{
                            value: 'MimeTypeArray',
                            enumerable: false
                        }});
                        return mimeTypes;
                    }},
                    configurable: true
                }});
                
                // Language
                Object.defineProperty(navProto, 'language', {{
                    get: function() {{ return '{language}'; }},
                    configurable: true
                }});
                Object.defineProperty(navProto, 'languages', {{
                    get: function() {{ return ['{language}']; }},
                    configurable: true
                }});
                
                // User Agent
                Object.defineProperty(navProto, 'userAgent', {{
                    get: function() {{ return '{user_agent}'; }},
                    configurable: true
                }});
                
                // Platform
                Object.defineProperty(navProto, 'platform', {{
                    get: function() {{ return '{platform}'; }},
                    configurable: true
                }});
                
                // App Version
                Object.defineProperty(navProto, 'appVersion', {{
                    get: function() {{ 
                        return '{app_version}';
                    }},
                    configurable: true
                }});
                
                // Vendor
                Object.defineProperty(navProto, 'vendor', {{
                    get: function() {{ return '{vendor}'; }},
                    configurable: true
                }});
                
                // userAgentData
                Object.defineProperty(navProto, 'userAgentData', {{
                    get: function() {{
                        return {{
                            brands: [
                                {{ brand: 'Google Chrome', version: '{chrome_version}' }},
                                {{ brand: 'Chromium', version: '{chrome_version}' }},
                                {{ brand: 'Not?A_Brand', version: '99' }}
                            ],
                            mobile: {str(device_category == 'mobile').lower()},
                            platform: '{platform}',
                            getHighEntropyValues: function(hints) {{
                                return Promise.resolve({{
                                    platform: '{platform}',
                                    platformVersion: '10.0',
                                    architecture: 'x64',
                                    model: '',
                                    uaFullVersion: '{chrome_version}.0.0.0'
                                }});
                            }}
                        }};
                    }},
                    configurable: true
                }});
                
                // Screen
                Object.defineProperty(screen, 'width', {{
                    get: function() {{ return {screen_w}; }},
                    configurable: true
                }});
                Object.defineProperty(screen, 'height', {{
                    get: function() {{ return {screen_h}; }},
                    configurable: true
                }});
                
                // Viewport
                Object.defineProperty(window, 'innerWidth', {{
                    get: function() {{ return {viewport_width}; }},
                    configurable: true
                }});
                Object.defineProperty(window, 'innerHeight', {{
                    get: function() {{ return {viewport_height}; }},
                    configurable: true
                }});
                Object.defineProperty(window, 'devicePixelRatio', {{
                    get: function() {{ return 1; }},
                    configurable: true
                }});
                
                // Device Memory
                Object.defineProperty(navProto, 'deviceMemory', {{
                    get: function() {{ return 8; }},
                    configurable: true
                }});
                
                console.log('✅ Pydoll fingerprint enhancements applied');
            }})();
        '''
        
        await page.execute_script(script_source)
        
        if _script_logger:
            _script_logger.info(f"Instance {instance_id}: ✅ Fingerprint enhancements applied")
            
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: ⚠️ Fingerprint enhancements failed: {e}")


def get_page_with_po_token(page, video_id: str, po_token: str = None) -> str:
    """Get URL with PO token applied."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    if po_token:
        url = add_po_token_to_url(url, po_token)
    return url


# ========== EXPORTS ==========
__all__ = [
    'create_driver_with_po_token_pydoll',
    'apply_fingerprint_enhancements',
    'get_page_with_po_token',
    'set_logger',
    'PYDOLL_AVAILABLE'
]