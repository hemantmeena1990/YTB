#!/usr/bin/env python3
"""
Extended driver creation with PO token support and custom referer
Supports all proxy modes: none, tor_service, tor_browser, list
UPDATED: Auto-detects Chrome version and forces undetected-chromedriver to use it
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
import subprocess
import re
from pathlib import Path
from selenium.webdriver.common.by import By
from common.fingerprint_manager import get_fingerprint_with_platform, validate_fingerprint

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

# ========== DETECT CHROME VERSION ==========
def get_chrome_version():
    """
    Detect installed Chrome version and executable path.
    Returns: (major_version, full_version, executable_path)
    """
    chrome_paths = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe")
    ]
    
    chrome_exe = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_exe = path
            break
    
    if not chrome_exe:
        print("[DRIVER] ⚠️ Could not find Chrome executable")
        return None, None, None
    
    # Method 1: Get version using wmic (Windows)
    try:
        result = subprocess.run(
            ['wmic', 'datafile', 'where', f'name="{chrome_exe.replace("\\", "\\\\")}"', 'get', 'Version', '/value'],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout
        match = re.search(r'Version=(\d+)\.(\d+)\.(\d+)\.(\d+)', output)
        if match:
            major = int(match.group(1))
            full_version = f"{match.group(1)}.{match.group(2)}.{match.group(3)}.{match.group(4)}"
            return major, full_version, chrome_exe
    except:
        pass
    
    # Method 2: Try using registry
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        version = winreg.QueryValueEx(key, "version")[0]
        major = int(version.split('.')[0])
        return major, version, chrome_exe
    except:
        pass
    
    # Method 3: Try using PowerShell
    try:
        result = subprocess.run(
            ['powershell', '-Command', f'(Get-Item "{chrome_exe}").VersionInfo.ProductVersion'],
            capture_output=True,
            text=True,
            timeout=5
        )
        version = result.stdout.strip()
        if version:
            major = int(version.split('.')[0])
            return major, version, chrome_exe
    except:
        pass
    
    print("[DRIVER] ⚠️ Could not detect Chrome version, using default 149")
    return 149, "149.0.7827.201", chrome_exe


# ========== FORCE CHROME VERSION FOR UNDETECTED ==========
def get_undetected_chrome_driver(options, chrome_major_version, chrome_executable):
    """
    Create undetected-chromedriver instance with forced Chrome version.
    """
    import undetected_chromedriver as uc
    
    # Try different approaches based on the library version
    try:
        # Approach 1: Use version_main parameter (most common)
        return uc.Chrome(
            options=options,
            version_main=chrome_major_version
        )
    except TypeError:
        # Approach 2: Use browser_executable_path
        try:
            return uc.Chrome(
                options=options,
                browser_executable_path=chrome_executable
            )
        except:
            # Approach 3: No version forcing, let it auto-detect
            return uc.Chrome(options=options)


# Detect Chrome version at module load
CHROME_MAJOR_VERSION, CHROME_FULL_VERSION, CHROME_EXECUTABLE = get_chrome_version()

if CHROME_MAJOR_VERSION:
    print(f"[DRIVER] 🎯 Detected Chrome {CHROME_FULL_VERSION} at {CHROME_EXECUTABLE}")
    print(f"[DRIVER] 🔧 Forcing undetected-chromedriver to use Chrome {CHROME_MAJOR_VERSION}")

# ========== Try to import undetected-chromedriver ==========
UNDETECTED_AVAILABLE = False
UNDETECTED_VERSION = None

try:
    import undetected_chromedriver as uc
    UNDETECTED_AVAILABLE = True
    try:
        UNDETECTED_VERSION = uc.__version__
    except:
        UNDETECTED_VERSION = "unknown"
    print(f"[DRIVER] ✅ undetected-chromedriver v{UNDETECTED_VERSION} imported successfully")
except ImportError as e:
    print(f"[DRIVER] ⚠️ undetected-chromedriver import failed: {e}")

# Fallback to standard selenium
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


def create_standard_options(cfg, profile_dir):
    """Create standard Selenium ChromeOptions."""
    options = Options()
    
    # Anti-detection arguments
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=en-US")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Headless
    if cfg.headless:
        options.add_argument("--headless=new")
    
    # User agent
    options.add_argument(f"user-agent={cfg.user_agent}")
    
    # Window size
    if not cfg.headless:
        try:
            w, h = get_random_resolution(cfg.is_mobile)
        except:
            w, h = 1920, 1080
        options.add_argument(f"--window-size={w},{h}")
    else:
        options.add_argument("--window-size=1920,1080")
    
    random_port = random.randint(40000, 49999)
    options.add_argument(f"--remote-debugging-port={random_port}")
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    # Custom chrome args
    if hasattr(cfg, 'chrome_args') and cfg.chrome_args:
        for arg in cfg.chrome_args:
            options.add_argument(arg)
    
    return options


def create_undetected_options(cfg, profile_dir):
    """Create undetected-chromedriver ChromeOptions (minimal, no conflicts)."""
    from undetected_chromedriver import ChromeOptions
    options = ChromeOptions()
    
    # Only add essential options (undetected handles anti-detection internally)
    if cfg.headless:
        options.add_argument("--headless=new")
    
    # User agent
    options.add_argument(f"user-agent={cfg.user_agent}")
    
    # Window size
    if not cfg.headless:
        try:
            w, h = get_random_resolution(cfg.is_mobile)
        except:
            w, h = 1920, 1080
        options.add_argument(f"--window-size={w},{h}")
    else:
        options.add_argument("--window-size=1920,1080")
    
    # Profile directory
    options.add_argument(f"--user-data-dir={profile_dir}")
    
    # Remote debugging port
    random_port = random.randint(40000, 49999)
    options.add_argument(f"--remote-debugging-port={random_port}")
    
    # Custom chrome args
    if hasattr(cfg, 'chrome_args') and cfg.chrome_args:
        for arg in cfg.chrome_args:
            options.add_argument(arg)
    
    # ========== AUTO-DETECTED CHROME PATH ==========
    if CHROME_EXECUTABLE and os.path.exists(CHROME_EXECUTABLE):
        options.binary_location = CHROME_EXECUTABLE
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: Using Chrome: {CHROME_EXECUTABLE}")
    # ==============================================
    
    return options


def apply_fingerprint_overrides(driver, cfg, instance_id, is_undetected=False):
    """
    Apply ALL fingerprint CDP overrides to the driver.
    Uses prototype-based overrides to avoid own properties.
    """
    if not _script_logger:
        return False
    
    try:
        user_agent = getattr(cfg, 'user_agent', None)
        viewport_width = getattr(cfg, 'viewport_width', None)
        viewport_height = getattr(cfg, 'viewport_height', None)
        plugins_length = getattr(cfg, 'plugins_length', None)
        connection = getattr(cfg, 'connection', {})
        device_category = getattr(cfg, 'device_category', None)
        fingerprint_platform = getattr(cfg, 'platform', 'Win32')
        language = getattr(cfg, 'language', 'en-US')
        vendor = getattr(cfg, 'vendor', 'Google Inc.')
        
        _script_logger.info(f"Instance {instance_id}: 🔧 Applying fingerprint overrides (undetected={is_undetected})")
        _script_logger.info(f"Instance {instance_id}: 📱 Platform: {fingerprint_platform}, Device: {device_category}")
        
        # 1. User Agent
        if user_agent:
            try:
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    'userAgent': user_agent
                })
                _script_logger.info(f"Instance {instance_id}: ✅ User agent set: {user_agent[:80]}...")
            except Exception as e:
                _script_logger.warning(f"Instance {instance_id}: User agent CDP failed: {e}")
        
        # 2. Window Size
        if viewport_width and viewport_height:
            try:
                driver.set_window_size(viewport_width, viewport_height)
                _script_logger.info(f"Instance {instance_id}: ✅ Window size set to {viewport_width}x{viewport_height}")
            except Exception as e:
                _script_logger.warning(f"Instance {instance_id}: Window size failed: {e}")
        
        # ========== USE FINGERPRINT DATA ==========
        import re
        
        # Extract Chrome version from user agent
        chrome_version = '138'
        if user_agent:
            chrome_match = re.search(r'Chrome/(\d+)\.', user_agent)
            if chrome_match:
                chrome_version = chrome_match.group(1)
        
        platform_value = fingerprint_platform
        user_agent_data_platform = fingerprint_platform
        
        # Extract appVersion platform from user agent
        if user_agent:
            match = re.search(r'^Mozilla/5\.0 \(([^)]+)\)', user_agent)
            if match:
                app_version_platform = match.group(1)
            else:
                if fingerprint_platform == 'MacIntel':
                    app_version_platform = 'Macintosh; Intel Mac OS X 10_15_7'
                elif fingerprint_platform == 'iPhone':
                    app_version_platform = 'iPhone; CPU iPhone OS 18_5 like Mac OS X'
                elif fingerprint_platform == 'iPad':
                    app_version_platform = 'iPad; CPU OS 18_5 like Mac OS X'
                elif fingerprint_platform in ['Linux armv8l', 'Linux x86_64']:
                    if 'Android' in user_agent:
                        app_version_platform = 'Linux; Android 10; K'
                    else:
                        app_version_platform = 'X11; Linux x86_64'
                else:
                    app_version_platform = 'Windows NT 10.0; Win64; x64'
        else:
            if fingerprint_platform == 'MacIntel':
                app_version_platform = 'Macintosh; Intel Mac OS X 10_15_7'
            elif fingerprint_platform == 'iPhone':
                app_version_platform = 'iPhone; CPU iPhone OS 18_5 like Mac OS X'
            elif fingerprint_platform == 'iPad':
                app_version_platform = 'iPad; CPU OS 18_5 like Mac OS X'
            elif fingerprint_platform in ['Linux armv8l', 'Linux x86_64']:
                app_version_platform = 'X11; Linux x86_64'
            else:
                app_version_platform = 'Windows NT 10.0; Win64; x64'
        
        # Build appVersion
        if user_agent and 'Chrome/' in user_agent:
            app_version = f'5.0 ({app_version_platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36'
        elif user_agent and 'Firefox/' in user_agent:
            app_version = f'5.0 ({app_version_platform}) Gecko/20100101 Firefox/{chrome_version}.0'
        elif user_agent and 'Safari/' in user_agent and 'Version/' in user_agent:
            app_version = f'5.0 ({app_version_platform}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15'
        else:
            app_version = f'5.0 ({app_version_platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36'
        
        _script_logger.info(f"Instance {instance_id}: 📱 Platform: {platform_value}")
        _script_logger.info(f"Instance {instance_id}: 🔍 Chrome version from fingerprint: {chrome_version}")
        # ===========================================================
        
        # 3. PROPER Navigator overrides
        script_source = f'''
            (function() {{
                // Get the prototype of navigator
                const navProto = Object.getPrototypeOf(navigator);
                
                // ========== webdriver ONLY on prototype ==========
                if (navigator.hasOwnProperty('webdriver')) {{
                    delete navigator.webdriver;
                }}
                Object.defineProperty(navProto, 'webdriver', {{
                    value: false,
                    writable: false,
                    configurable: false,
                    enumerable: false
                }});
                // =================================================
                
                // ========== PLUGINS: Simple array with PluginArray methods ==========
                Object.defineProperty(navProto, 'plugins', {{
                    get: function() {{
                        const pluginCount = {plugins_length if plugins_length is not None else 4};
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
                        // This is the key - set toStringTag to pass type checks
                        Object.defineProperty(plugins, Symbol.toStringTag, {{
                            value: 'PluginArray',
                            enumerable: false
                        }});
                        return plugins;
                    }},
                    configurable: true
                }});
                // =================================================
                
                // ========== MIME TYPES ==========
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
                // =================================================
                
                // ========== LANGUAGE ==========
                Object.defineProperty(navProto, 'language', {{
                    get: function() {{ return '{language}'; }},
                    configurable: true
                }});
                Object.defineProperty(navProto, 'languages', {{
                    get: function() {{ return ['{language}']; }},
                    configurable: true
                }});
                
                // ========== USER AGENT ==========
                Object.defineProperty(navProto, 'userAgent', {{
                    get: function() {{ return '{user_agent}'; }},
                    configurable: true
                }});
                
                // ========== PLATFORM ==========
                Object.defineProperty(navProto, 'platform', {{
                    get: function() {{ return '{platform_value}'; }},
                    configurable: true
                }});
                
                // ========== APP VERSION ==========
                Object.defineProperty(navProto, 'appVersion', {{
                    get: function() {{ 
                        return '{app_version}';
                    }},
                    configurable: true
                }});
                
                // ========== VENDOR ==========
                Object.defineProperty(navProto, 'vendor', {{
                    get: function() {{ return '{vendor}'; }},
                    configurable: true
                }});
                
                // ========== userAgentData (ONLY on prototype, NEVER on navigator) ==========
                Object.defineProperty(navProto, 'userAgentData', {{
                    get: function() {{
                        return {{
                            brands: [
                                {{ brand: 'Google Chrome', version: '{chrome_version}' }},
                                {{ brand: 'Chromium', version: '{chrome_version}' }},
                                {{ brand: 'Not?A_Brand', version: '99' }}
                            ],
                            mobile: {str(device_category == 'mobile').lower()},
                            platform: '{user_agent_data_platform}',
                            getHighEntropyValues: function(hints) {{
                                return Promise.resolve({{
                                    platform: '{user_agent_data_platform}',
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
                // DO NOT define userAgentData on navigator directly
                // =============================================================
                
                // ========== DEVICE MEMORY & HARDWARE ==========
                Object.defineProperty(navProto, 'deviceMemory', {{
                    get: function() {{ return 8; }},
                    configurable: true
                }});
                Object.defineProperty(navProto, 'hardwareConcurrency', {{
                    get: function() {{ return 8; }},
                    configurable: true
                }});
                
                // ========== WINDOW.CHROME ==========
                if (typeof window.chrome === 'undefined' || !window.chrome) {{
                    window.chrome = {{}};
                }}
                if (!window.chrome.runtime) {{
                    window.chrome.runtime = {{}};
                }}
                if (!window.chrome.runtime.connect) {{
                    window.chrome.runtime.connect = function() {{ return {{}}; }};
                }}
                if (!window.chrome.runtime.sendMessage) {{
                    window.chrome.runtime.sendMessage = function() {{}};
                }}
                if (!window.chrome.memory) {{
                    Object.defineProperty(window.chrome, 'memory', {{
                        get: function() {{
                            return {{
                                getInfo: function() {{
                                    return {{
                                        totalJSHeapSize: 100000000,
                                        usedJSHeapSize: 50000000,
                                        jsHeapSizeLimit: 200000000
                                    }};
                                }}
                            }};
                        }},
                        configurable: true
                    }});
                }}
                if (!window.chrome.loadTimes) {{
                    window.chrome.loadTimes = function() {{
                        return {{
                            requestTime: Date.now() / 1000,
                            startLoadTime: Date.now() / 1000,
                            commitLoadTime: Date.now() / 1000,
                            finishDocumentLoadTime: Date.now() / 1000,
                            finishLoadTime: Date.now() / 1000,
                            navigationType: 'Other',
                            wasFetchedViaSpdy: false,
                            wasNpnNegotiated: false,
                            npnNegotiatedProtocol: 'unknown',
                            wasAlternateProtocolAvailable: false,
                            connectionInfo: 'unknown'
                        }};
                    }};
                }}
                if (!window.chrome.csi) {{
                    window.chrome.csi = function() {{
                        return {{
                            startE: Date.now(),
                            onloadT: Date.now(),
                            pageT: Date.now() - 1000,
                            tran: 15
                        }};
                    }};
                }}
                if (!window.chrome.app) {{
                    window.chrome.app = {{}};
                }}
                
                console.log('✅ Fingerprint overrides applied');
                console.log('📱 Platform:', navigator.platform);
                console.log('📱 appVersion:', navigator.appVersion);
                console.log('📱 plugins length:', navigator.plugins.length);
                console.log('📱 userAgentData brands:', navigator.userAgentData.brands);
            }})();
        '''
        
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': script_source
        })
        _script_logger.info(f"Instance {instance_id}: ✅ Navigator prototype overrides applied")
        
        # 4. Network Emulation
        if connection and connection.get('downlink'):
            try:
                downlink = connection.get('downlink', 10)
                rtt = connection.get('rtt', 100)
                driver.execute_cdp_cmd('Network.emulateNetworkConditions', {
                    'offline': False,
                    'latency': rtt,
                    'downloadThroughput': downlink * 1024 * 1024 / 8,
                    'uploadThroughput': downlink * 1024 * 1024 / 8,
                })
                _script_logger.info(f"Instance {instance_id}: ✅ Network emulated: {downlink}Mbps, {rtt}ms RTT")
            except Exception as e:
                _script_logger.warning(f"Instance {instance_id}: Network CDP failed: {e}")
        
        # 5. Mobile Viewport Emulation
        if device_category == 'mobile' and viewport_width and viewport_height:
            try:
                driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                    'width': viewport_width,
                    'height': viewport_height,
                    'deviceScaleFactor': 1,
                    'mobile': True,
                    'screenOrientation': {
                        'type': 'portraitPrimary',
                        'angle': 0
                    }
                })
                _script_logger.info(f"Instance {instance_id}: ✅ Mobile viewport emulated: {viewport_width}x{viewport_height}")
                
                driver.execute_script(f"""
                    var meta = document.querySelector('meta[name=viewport]');
                    if (!meta) {{
                        meta = document.createElement('meta');
                        meta.name = 'viewport';
                        document.head.appendChild(meta);
                    }}
                    meta.content = 'width={viewport_width}, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
                    window.dispatchEvent(new Event('resize'));
                """)
                
            except Exception as e:
                _script_logger.warning(f"Instance {instance_id}: Mobile emulation failed: {e}")
        
        # 6. Verify actual viewport
        try:
            actual_width = driver.execute_script("return window.innerWidth")
            actual_height = driver.execute_script("return window.innerHeight")
            _script_logger.info(f"Instance {instance_id}: 🔍 Actual viewport: {actual_width}x{actual_height}")
            if viewport_width and viewport_height:
                if actual_width != viewport_width or actual_height != viewport_height:
                    _script_logger.warning(f"Instance {instance_id}: ⚠️ Viewport mismatch! Expected {viewport_width}x{viewport_height}, got {actual_width}x{actual_height}")
        except:
            pass
        
        _script_logger.info(f"Instance {instance_id}: ✅ Fingerprint overrides applied successfully")
        return True
        
    except Exception as e:
        _script_logger.error(f"Instance {instance_id}: ❌ Fingerprint overrides failed: {e}")
        return False

def inject_fingerprint_into_iframes(driver, cfg, instance_id):
    """
    Inject fingerprint overrides into iframes using the SAME logic as apply_fingerprint_overrides.
    This ensures consistency between main page and iframe fingerprints.
    """
    if not _script_logger:
        return False
    
    try:
        # Extract fingerprint data from cfg (same as apply_fingerprint_overrides)
        user_agent = getattr(cfg, 'user_agent', None)
        viewport_width = getattr(cfg, 'viewport_width', None)
        viewport_height = getattr(cfg, 'viewport_height', None)
        plugins_length = getattr(cfg, 'plugins_length', None)
        device_category = getattr(cfg, 'device_category', None)
        fingerprint_platform = getattr(cfg, 'platform', 'Win32')
        language = getattr(cfg, 'language', 'en-US')
        vendor = getattr(cfg, 'vendor', 'Google Inc.')
        
        # Check if mobile
        if device_category != 'mobile':
            _script_logger.info(f"Instance {instance_id}: ⏭️ Skipping iframe injection (not mobile)")
            return True
        
        # Extract Chrome version from user agent (same as apply_fingerprint_overrides)
        import re
        chrome_version = '149'
        if user_agent:
            chrome_match = re.search(r'Chrome/(\d+)\.', user_agent)
            if chrome_match:
                chrome_version = chrome_match.group(1)
        
        # Use platform from fingerprint
        platform_value = fingerprint_platform
        user_agent_data_platform = fingerprint_platform
        
        # Extract appVersion platform from user agent (same as apply_fingerprint_overrides)
        if user_agent:
            match = re.search(r'^Mozilla/5\.0 \(([^)]+)\)', user_agent)
            if match:
                app_version_platform = match.group(1)
            else:
                if fingerprint_platform == 'MacIntel':
                    app_version_platform = 'Macintosh; Intel Mac OS X 10_15_7'
                elif fingerprint_platform == 'iPhone':
                    app_version_platform = 'iPhone; CPU iPhone OS 18_5 like Mac OS X'
                elif fingerprint_platform == 'iPad':
                    app_version_platform = 'iPad; CPU OS 18_5 like Mac OS X'
                elif fingerprint_platform in ['Linux armv8l', 'Linux x86_64']:
                    if 'Android' in user_agent:
                        app_version_platform = 'Linux; Android 10; K'
                    else:
                        app_version_platform = 'X11; Linux x86_64'
                else:
                    app_version_platform = 'Windows NT 10.0; Win64; x64'
        else:
            if fingerprint_platform == 'MacIntel':
                app_version_platform = 'Macintosh; Intel Mac OS X 10_15_7'
            elif fingerprint_platform == 'iPhone':
                app_version_platform = 'iPhone; CPU iPhone OS 18_5 like Mac OS X'
            elif fingerprint_platform == 'iPad':
                app_version_platform = 'iPad; CPU OS 18_5 like Mac OS X'
            elif fingerprint_platform in ['Linux armv8l', 'Linux x86_64']:
                app_version_platform = 'X11; Linux x86_64'
            else:
                app_version_platform = 'Windows NT 10.0; Win64; x64'
        
        # Build appVersion (same as apply_fingerprint_overrides)
        if user_agent and 'Chrome/' in user_agent:
            app_version = f'5.0 ({app_version_platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36'
        elif user_agent and 'Firefox/' in user_agent:
            app_version = f'5.0 ({app_version_platform}) Gecko/20100101 Firefox/{chrome_version}.0'
        elif user_agent and 'Safari/' in user_agent and 'Version/' in user_agent:
            app_version = f'5.0 ({app_version_platform}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15'
        else:
            app_version = f'5.0 ({app_version_platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36'
        
        _script_logger.info(f"Instance {instance_id}: 🔍 Injecting fingerprint into iframes...")
        
        # Find all iframes
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            _script_logger.info(f"Instance {instance_id}: Found {len(iframes)} iframe(s)")
        except Exception as e:
            _script_logger.warning(f"Instance {instance_id}: Could not find iframes: {e}")
            return False
        
        if not iframes:
            _script_logger.warning(f"Instance {instance_id}: No iframes found")
            return False
        
        # Build the fingerprint script (SAME as apply_fingerprint_overrides)
        script_source = f'''
            (function() {{
                // Get the prototype of navigator
                const navProto = Object.getPrototypeOf(navigator);
                
                // ========== webdriver ONLY on prototype ==========
                if (navigator.hasOwnProperty('webdriver')) {{
                    delete navigator.webdriver;
                }}
                Object.defineProperty(navProto, 'webdriver', {{
                    value: false,
                    writable: false,
                    configurable: false,
                    enumerable: false
                }});
                // =================================================
                
                // ========== PLUGINS ==========
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
                // =================================================
                
                // ========== MIME TYPES ==========
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
                // =================================================
                
                // ========== LANGUAGE ==========
                Object.defineProperty(navProto, 'language', {{
                    get: function() {{ return '{language}'; }},
                    configurable: true
                }});
                Object.defineProperty(navProto, 'languages', {{
                    get: function() {{ return ['{language}']; }},
                    configurable: true
                }});
                
                // ========== USER AGENT ==========
                Object.defineProperty(navProto, 'userAgent', {{
                    get: function() {{ return '{user_agent}'; }},
                    configurable: true
                }});
                
                // ========== PLATFORM ==========
                Object.defineProperty(navProto, 'platform', {{
                    get: function() {{ return '{platform_value}'; }},
                    configurable: true
                }});
                
                // ========== APP VERSION ==========
                Object.defineProperty(navProto, 'appVersion', {{
                    get: function() {{ 
                        return '{app_version}';
                    }},
                    configurable: true
                }});
                
                // ========== VENDOR ==========
                Object.defineProperty(navProto, 'vendor', {{
                    get: function() {{ return '{vendor}'; }},
                    configurable: true
                }});
                
                // ========== userAgentData ==========
                Object.defineProperty(navProto, 'userAgentData', {{
                    get: function() {{
                        return {{
                            brands: [
                                {{ brand: 'Google Chrome', version: '{chrome_version}' }},
                                {{ brand: 'Chromium', version: '{chrome_version}' }},
                                {{ brand: 'Not?A_Brand', version: '99' }}
                            ],
                            mobile: {str(device_category == 'mobile').lower()},
                            platform: '{user_agent_data_platform}',
                            getHighEntropyValues: function(hints) {{
                                return Promise.resolve({{
                                    platform: '{user_agent_data_platform}',
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
                
                // ========== DEVICE MEMORY & HARDWARE ==========
                Object.defineProperty(navProto, 'deviceMemory', {{
                    get: function() {{ return 8; }},
                    configurable: true
                }});
                Object.defineProperty(navProto, 'hardwareConcurrency', {{
                    get: function() {{ return 8; }},
                    configurable: true
                }});
                
                // ========== SCREEN & VIEWPORT ==========
                Object.defineProperty(screen, 'width', {{
                    get: function() {{ return {viewport_width}; }},
                    configurable: true
                }});
                Object.defineProperty(screen, 'height', {{
                    get: function() {{ return {viewport_height}; }},
                    configurable: true
                }});
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
                
                console.log('✅ Fingerprint injected into iframe');
                console.log('📱 Platform:', navigator.platform);
                console.log('📱 plugins length:', navigator.plugins.length);
                console.log('📱 viewport:', window.innerWidth + 'x' + window.innerHeight);
            }})();
        '''
        
        # Inject script into each iframe
        injected_count = 0
        for i, iframe in enumerate(iframes):
            try:
                # Switch to iframe
                driver.switch_to.frame(iframe)
                
                # Execute the fingerprint script in iframe context
                driver.execute_script(script_source)
                
                # Switch back to main page
                driver.switch_to.default_content()
                injected_count += 1
                _script_logger.info(f"Instance {instance_id}: ✅ Injected fingerprint into iframe {i+1}")
                
            except Exception as e:
                driver.switch_to.default_content()
                _script_logger.warning(f"Instance {instance_id}: Could not inject into iframe {i+1}: {e}")
        
        _script_logger.info(f"Instance {instance_id}: ✅ Injected fingerprint into {injected_count}/{len(iframes)} iframe(s)")
        return injected_count > 0
        
    except Exception as e:
        try:
            driver.switch_to.default_content()
        except:
            pass
        _script_logger.error(f"Instance {instance_id}: Iframe injection failed: {e}")
        return False        
        
        
def create_driver_with_po_token(cfg, profile_prefix):
    """
    Create Chrome driver with PO token and proxy support.
    Uses undetected-chromedriver when explicitly enabled in config.
    Integrates Intoli fingerprints for consistent browser signals.
    """
    
    user_selected_source = getattr(cfg, 'po_token_source', 'native')
    proxy_mode = getattr(cfg, 'proxy_mode', 'none')
    
    # ========== READ FROM CONFIG CORRECTLY ==========
    automation_version = getattr(cfg, 'automation_version', 'selenium')
    use_undetected = getattr(cfg, 'use_undetected', False)
    
    if automation_version == 'selenium_undetected':
        use_undetected = True
    elif automation_version == 'selenium':
        use_undetected = False
    # ================================================
    
    if _script_logger:
        _script_logger.info(f"Instance {cfg.instance_id}: PO token source: {user_selected_source}")
        _script_logger.info(f"Instance {cfg.instance_id}: Proxy mode: {proxy_mode}")
        _script_logger.info(f"Instance {cfg.instance_id}: Automation version: {automation_version}")
        _script_logger.info(f"Instance {cfg.instance_id}: Use undetected: {use_undetected}")
        _script_logger.info(f"Instance {cfg.instance_id}: UNDETECTED_AVAILABLE: {UNDETECTED_AVAILABLE}")
        if CHROME_MAJOR_VERSION:
            _script_logger.info(f"Instance {cfg.instance_id}: Detected Chrome version: {CHROME_FULL_VERSION}")
    
    # ========== SETUP PROFILE DIRECTORY ==========
    temp_base = os.path.join(tempfile.gettempdir(), "yt_automation")
    os.makedirs(temp_base, exist_ok=True)
    
    try:
        current_time = time.time()
        max_age = 86400 if use_undetected else 3600
        for item in os.listdir(temp_base):
            item_path = os.path.join(temp_base, item)
            if os.path.isdir(item_path) and item.startswith(profile_prefix[:10]):
                if current_time - os.path.getmtime(item_path) > max_age:
                    shutil.rmtree(item_path, ignore_errors=True)
    except:
        pass
    
    unique_id = f"{int(time.time())}_{cfg.instance_id}_{uuid.uuid4().hex[:12]}"
    profile_dir = os.path.join(temp_base, f"{profile_prefix}_{unique_id}")
    
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except:
            pass
    os.makedirs(profile_dir, exist_ok=True)
    
    # ========== FINGERPRINT SIGNALS ==========
    platform = getattr(cfg, 'platform', 'Win32')
    vendor = getattr(cfg, 'vendor', 'Google Inc.')
    connection = getattr(cfg, 'connection', {})
    random_port = random.randint(40000, 49999)
    # ==========================================
    
    # ========== PROXY CONFIGURATION ==========
    proxy_host = None
    
    if hasattr(cfg, 'proxy') and cfg.proxy:
        proxy_url = cfg.proxy
        
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Processing: {proxy_url[:80]}")
        
        http_proxy = get_http_proxy_for_socks(proxy_url)
        
        if http_proxy and http_proxy != proxy_url:
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [SOCKS] Converted to HTTP bridge")
            proxy_host = http_proxy.split('://', 1)[1] if '://' in http_proxy else http_proxy
        elif http_proxy:
            proxy_host = http_proxy.split('://', 1)[1] if '://' in http_proxy else http_proxy
            if '@' in proxy_host:
                proxy_host = proxy_host.split('@', 1)[1]
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [HTTP] Using proxy")
        
        if hasattr(cfg, 'current_proxy'):
            cfg.current_proxy = proxy_url
    
    elif proxy_mode == 'tor_service':
        tor_bridge = start_tor_bridge(tor_port=9050, http_port=8888)
        if tor_bridge:
            proxy_host = tor_bridge.split('://', 1)[1]
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [TOR] Using HTTP bridge on port 8888")
        else:
            proxy_host = "socks5://127.0.0.1:9050"
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [TOR] Bridge failed, using SOCKS5")
    
    elif proxy_mode == 'tor_browser':
        tor_bridge = start_tor_bridge(tor_port=9150, http_port=8889)
        if tor_bridge:
            proxy_host = tor_bridge.split('://', 1)[1]
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [TOR] Using HTTP bridge")
        else:
            proxy_host = "socks5://127.0.0.1:9150"
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
                if _script_logger:
                    _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using proxy from list")
        else:
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [PROXY] No proxy available")
    else:
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Direct connection")
    
    # ========== CREATE DRIVER ==========
    driver = None
    driver_type = "unknown"
    
    # Try undetected-chromedriver if explicitly enabled
    if use_undetected and UNDETECTED_AVAILABLE:
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: 🚀 Attempting undetected-chromedriver...")
        try:
            # Create options specifically for undetected
            from undetected_chromedriver import ChromeOptions
            options = ChromeOptions()
            
            # ========== UNDETECTED OPTIONS (MINIMAL) ==========
            if cfg.headless:
                options.add_argument("--headless=new")
            
            # User agent from fingerprint
            if hasattr(cfg, 'user_agent') and cfg.user_agent:
                options.add_argument(f"user-agent={cfg.user_agent}")
                try:
                    options.user_agent = cfg.user_agent
                except:
                    pass
                if _script_logger:
                    _script_logger.info(f"Instance {cfg.instance_id}: User agent set: {cfg.user_agent[:80]}...")
            else:
                if _script_logger:
                    _script_logger.warning(f"Instance {cfg.instance_id}: No user agent found in config!")
            
            # ========== WINDOW SIZE - CRITICAL FOR FINGERPRINT ==========
            # Use viewport size for visible window
            if not cfg.headless:
                if hasattr(cfg, 'viewport_width') and hasattr(cfg, 'viewport_height'):
                    options.add_argument(f"--window-size={cfg.viewport_width},{cfg.viewport_height}")
                    if _script_logger:
                        _script_logger.info(f"Instance {cfg.instance_id}: Window size set to {cfg.viewport_width}x{cfg.viewport_height}")
                else:
                    options.add_argument("--window-size=390,844")  # Default mobile
            else:
                # Headless: use screen size
                if hasattr(cfg, 'screen_width') and hasattr(cfg, 'screen_height'):
                    options.add_argument(f"--window-size={cfg.screen_width},{cfg.screen_height}")
                else:
                    options.add_argument("--window-size=1920,1080")
            # =========================================================
            
            # ========== FASTER STARTUP OPTIONS ==========
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")
            options.add_argument("--disable-javascript")  # Only for initial load
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: Added faster startup options")
            # =============================================
            
            # Profile
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument(f"--remote-debugging-port={random_port}")
            
            # Custom chrome args
            if hasattr(cfg, 'chrome_args') and cfg.chrome_args:
                for arg in cfg.chrome_args:
                    options.add_argument(arg)
            
            # Proxy
            if proxy_host:
                options.add_argument(f'--proxy-server={proxy_host}')
            
            # Referer
            if hasattr(cfg, 'referer') and cfg.referer:
                options.add_argument(f'--referer={cfg.referer}')
            
            # ========== DO NOT ADD excludeSwitches FOR UNDETECTED ==========
            # NO options.add_experimental_option("excludeSwitches", [...])
            # NO options.add_experimental_option('useAutomationExtension', False)
            # =============================================================
            
            # ========== DEBUG: Print all options ==========
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: 🔍 Chrome options: {options.arguments}")
            # =============================================
        
            # Try with version forcing
            try:
                driver = uc.Chrome(
                    options=options,
                    version_main=CHROME_MAJOR_VERSION
                )
                if _script_logger:
                    _script_logger.info(f"Instance {cfg.instance_id}: Using version_main={CHROME_MAJOR_VERSION}")
            except TypeError:
                if CHROME_EXECUTABLE and os.path.exists(CHROME_EXECUTABLE):
                    driver = uc.Chrome(
                        options=options,
                        browser_executable_path=CHROME_EXECUTABLE
                    )
                    if _script_logger:
                        _script_logger.info(f"Instance {cfg.instance_id}: Using browser_executable_path")
                else:
                    driver = uc.Chrome(options=options)
                    if _script_logger:
                        _script_logger.info(f"Instance {cfg.instance_id}: Using default (no version forcing)")
            
            # ========== APPLY FINGERPRINT OVERRIDES (UNIFIED) ==========
            apply_fingerprint_overrides(driver, cfg, cfg.instance_id, is_undetected=True)
            # ============================================================
            
            driver_type = "undetected"
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: ✅ Created profile at {profile_dir} (undetected)")

        except Exception as e:
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: undetected-chromedriver failed: {e}, falling back to standard")
            driver = None

    # ========== STANDARD SELENIUM (FALLBACK) ==========
    if driver is None:
        try:
            # Create standard options
            from selenium.webdriver.chrome.options import Options
            options = Options()
            
            # Standard anti-detection (includes excludeSwitches)
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-notifications")
            options.add_argument("--lang=en-US")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-translate")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            
            # ========== STANDARD EXCLUDESWITCHES (ONLY FOR STANDARD) ==========
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            # =================================================================
            
            if cfg.headless:
                options.add_argument("--headless=new")
            
            # User agent from fingerprint
            if hasattr(cfg, 'user_agent') and cfg.user_agent:
                options.add_argument(f"user-agent={cfg.user_agent}")
            
            # ========== WINDOW SIZE - CRITICAL FOR FINGERPRINT ==========
            if not cfg.headless:
                if hasattr(cfg, 'viewport_width') and hasattr(cfg, 'viewport_height'):
                    options.add_argument(f"--window-size={cfg.viewport_width},{cfg.viewport_height}")
                    if _script_logger:
                        _script_logger.info(f"Instance {cfg.instance_id}: Window size set to {cfg.viewport_width}x{cfg.viewport_height}")
                else:
                    options.add_argument("--window-size=390,844")
            else:
                if hasattr(cfg, 'screen_width') and hasattr(cfg, 'screen_height'):
                    options.add_argument(f"--window-size={cfg.screen_width},{cfg.screen_height}")
                else:
                    options.add_argument("--window-size=1920,1080")
            # =============================================================
            
            options.add_argument(f"--remote-debugging-port={random_port}")
            options.add_argument(f"--user-data-dir={profile_dir}")
            
            # Custom chrome args
            if hasattr(cfg, 'chrome_args') and cfg.chrome_args:
                for arg in cfg.chrome_args:
                    options.add_argument(arg)
            
            # Proxy
            if proxy_host:
                options.add_argument(f'--proxy-server={proxy_host}')
            
            # Referer
            if hasattr(cfg, 'referer') and cfg.referer:
                options.add_argument(f'--referer={cfg.referer}')
            
            # Standard Selenium
            service = Service(ChromeDriverManager().install())
            service.creation_flags = 0x08000000
            driver = webdriver.Chrome(service=service, options=options)
            
            # ========== APPLY FINGERPRINT OVERRIDES (UNIFIED) ==========
            apply_fingerprint_overrides(driver, cfg, cfg.instance_id, is_undetected=False)
            # ============================================================
            
            driver_type = "standard"
            
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: Created profile at {profile_dir} (standard)")
                
        except Exception as e:
            if _script_logger:
                _script_logger.error(f"Instance {cfg.instance_id}: Failed to create driver: {e}")
            raise
    
    if _script_logger and driver:
        _script_logger.info(f"Instance {cfg.instance_id}: 🏁 Driver type: {driver_type}")
    
    driver.set_page_load_timeout(60)
    
    # Add marker file
    marker_file = os.path.join(profile_dir, f"instance_{cfg.instance_id}.lock")
    with open(marker_file, 'w') as f:
        f.write(f"Created at: {time.time()}\nInstance: {cfg.instance_id}")
        f.write(f"Proxy mode: {proxy_mode}\n")
        f.write(f"Use undetected: {use_undetected}\n")
        f.write(f"Driver type: {driver_type}\n")
        f.write(f"Chrome version: {CHROME_FULL_VERSION}\n")
        if hasattr(cfg, 'proxy') and cfg.proxy:
            f.write(f"Assigned proxy: {cfg.proxy}\n")
        if hasattr(cfg, 'referer') and cfg.referer:
            f.write(f"Referer: {cfg.referer}\n")
        if hasattr(cfg, 'chrome_args') and cfg.chrome_args:
            f.write(f"Chrome args: {cfg.chrome_args}\n")
        if hasattr(cfg, 'user_agent') and cfg.user_agent:
            f.write(f"User Agent: {cfg.user_agent[:100]}...\n")
        if hasattr(cfg, 'screen_width') and hasattr(cfg, 'screen_height'):
            f.write(f"Screen: {cfg.screen_width}x{cfg.screen_height}\n")
        if hasattr(cfg, 'viewport_width') and hasattr(cfg, 'viewport_height'):
            f.write(f"Viewport: {cfg.viewport_width}x{cfg.viewport_height}\n")
        if platform:
            f.write(f"Platform: {platform}\n")
        if vendor:
            f.write(f"Vendor: {vendor}\n")
        if connection:
            f.write(f"Connection: {connection}\n")

    # ========== SET CDP REFERER ==========
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