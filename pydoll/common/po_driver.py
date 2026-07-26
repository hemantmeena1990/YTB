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
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Any
import signal
import atexit
import psutil
import subprocess

# ========== PATH SETUP ==========
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "common"))
# Ensure pydoll/common is in path before common (for correct human_behavior import)
sys.path.insert(0, str(Path(__file__).parent))

# ========== Pydoll Imports ==========
PYDOLL_AVAILABLE = False
ChromiumOptions = None
Chrome = None

try:
    from pydoll.browser.chromium import Chrome
    from pydoll.browser.options import ChromiumOptions
    PYDOLL_AVAILABLE = True
    print("[PYDOLL] ✅ Pydoll imported from pydoll.browser.chromium")
except ImportError:
    try:
        from pydoll.browser import Chrome
        from pydoll.browser.options import ChromiumOptions
        PYDOLL_AVAILABLE = True
        print("[PYDOLL] ✅ Pydoll imported from pydoll.browser")
    except ImportError:
        try:
            from pydoll_python.browser import Chrome
            from pydoll_python.browser.options import ChromiumOptions
            PYDOLL_AVAILABLE = True
            print("[PYDOLL] ✅ Pydoll imported from pydoll_python.browser")
        except ImportError:
            print("[PYDOLL] ❌ Pydoll import failed. Please install: pip install pydoll-python")
            PYDOLL_AVAILABLE = False

if not PYDOLL_AVAILABLE:
    print("[PYDOLL] ⚠️ Pydoll not available. Please install: pip install pydoll-python")

# ========== Common Imports ==========
from common.po_token import add_po_token_to_url
from common.proxy_manager import get_rotating_proxy, get_working_proxies
from common.socks_to_http import start_tor_bridge, get_http_proxy_for_socks

# ========== Human Behavior Imports (from same directory) ==========
from human_behavior import handle_all_popups, handle_recaptcha, handle_consent_popups

# Global logger
_script_logger = None


def set_logger(logger):
    """Set global logger for driver"""
    global _script_logger
    _script_logger = logger


def get_logger():
    """Get logger with fallback"""
    if _script_logger:
        return _script_logger
    import logging
    return logging.getLogger(__name__)


# ========== CLEANUP FUNCTIONS ==========

def kill_child_processes(parent_pid: int, signal_type=signal.SIGTERM):
    """Kill all child processes of a given parent PID."""
    try:
        parent = psutil.Process(parent_pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.send_signal(signal_type)
                if _script_logger:
                    _script_logger.info(f"🧹 Killed child process: {child.pid}")
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                if _script_logger:
                    _script_logger.warning(f"⚠️ Could not kill child {child.pid}: {e}")
        try:
            parent.send_signal(signal_type)
            if _script_logger:
                _script_logger.info(f"🧹 Killed parent process: {parent_pid}")
        except psutil.NoSuchProcess:
            pass
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"⚠️ Cleanup error: {e}")


def cleanup_all_browsers():
    """Clean up all browser processes spawned by this script."""
    current_pid = os.getpid()
    if _script_logger:
        _script_logger.info(f"🧹 Cleaning up browser processes for PID: {current_pid}")
    
    try:
        try:
            parent = psutil.Process(current_pid)
            children = parent.children(recursive=True)
            if _script_logger:
                _script_logger.info(f"🧹 Found {len(children)} child process(es)")
            for child in children:
                try:
                    child.terminate()
                    if _script_logger:
                        _script_logger.info(f"🧹 Terminated child process: {child.pid}")
                    child.wait(timeout=2)
                except psutil.TimeoutExpired:
                    child.kill()
                    if _script_logger:
                        _script_logger.info(f"🧹 Force killed child process: {child.pid}")
                except psutil.NoSuchProcess:
                    pass
                except Exception as e:
                    if _script_logger:
                        _script_logger.warning(f"⚠️ Could not kill child {child.pid}: {e}")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            if _script_logger:
                _script_logger.warning(f"⚠️ Child process cleanup error: {e}")

        try:
            for proc in psutil.process_iter(['pid', 'name', 'ppid', 'cmdline']):
                try:
                    if proc.info['ppid'] == current_pid or proc.info['ppid'] in [c.pid for c in psutil.Process(current_pid).children(recursive=True)]:
                        if 'chrome' in proc.info['name'].lower() or 'chromium' in proc.info['name'].lower():
                            proc.kill()
                            if _script_logger:
                                _script_logger.info(f"🧹 Killed orphaned chrome process: {proc.pid}")
                except:
                    pass
        except Exception as e:
            if _script_logger:
                _script_logger.warning(f"⚠️ Chrome process cleanup error: {e}")
                
        if _script_logger:
            _script_logger.info("🧹 Cleanup complete")
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"⚠️ Cleanup error: {e}")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    if _script_logger:
        _script_logger.info("🛑 Received interrupt signal. Cleaning up...")
    cleanup_all_browsers()
    sys.exit(0)


def register_cleanup_handlers():
    """Register signal and atexit handlers for cleanup."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup_all_browsers)
    if _script_logger:
        _script_logger.info("🧹 Cleanup handlers registered")


def _get_proxy_config(cfg):
    """Get proxy configuration for Pydoll."""
    proxy_url = None
    extra_args = []
    proxy_mode = getattr(cfg, 'proxy_mode', 'none')
    
    if cfg.proxy:
        proxy_url = cfg.proxy
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using direct proxy: {proxy_url[:60]}")
        return proxy_url, extra_args
    
    elif proxy_mode == 'tor_service':
        http_bridge = start_tor_bridge(tor_port=9050, http_port=8888)
        if http_bridge:
            proxy_url = http_bridge
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] ✅ Tor Service HTTP bridge started: {proxy_url}")
        else:
            proxy_url = "socks5://127.0.0.1:9050"
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [PROXY] ⚠️ Bridge failed, using SOCKS5 fallback")
        return proxy_url, extra_args
    
    elif proxy_mode == 'tor_browser':
        http_bridge = start_tor_bridge(tor_port=9150, http_port=8889)
        if http_bridge:
            proxy_url = http_bridge
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] ✅ Tor Browser HTTP bridge started: {proxy_url}")
        else:
            proxy_url = "socks5://127.0.0.1:9150"
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [PROXY] ⚠️ Bridge failed, using SOCKS5 fallback")
        return proxy_url, extra_args
    
    elif proxy_mode == 'list':
        proxy_url = get_rotating_proxy()
        if not proxy_url:
            working = get_working_proxies()
            if working:
                proxy_url = random.choice(working)
        if proxy_url:
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [PROXY] Using rotating proxy: {proxy_url[:60]}")
            return proxy_url, extra_args
        else:
            if _script_logger:
                _script_logger.warning(f"Instance {cfg.instance_id}: [PROXY] No proxy available")
    
    return None, []


async def set_referrer_header(tab, referrer, instance_id):
    """Set referrer header via CDP before navigation."""
    if not referrer:
        return False
    
    logger = get_logger()
    try:
        # Try _connection_handler first (Pydoll's native)
        if hasattr(tab, '_connection_handler') and tab._connection_handler:
            await tab._connection_handler.execute_command({
                "method": "Network.setExtraHTTPHeaders",
                "params": {"headers": {"Referer": referrer}}
            })
            logger.info(f"Instance {instance_id}: [REFERRER] ✅ Header set via _connection_handler: {referrer}")
            return True
        # Try cdp.send (alternative Pydoll API)
        elif hasattr(tab, 'cdp') and hasattr(tab.cdp, 'send'):
            await tab.cdp.send("Network.setExtraHTTPHeaders", {
                "headers": {"Referer": referrer}
            })
            logger.info(f"Instance {instance_id}: [REFERRER] ✅ Header set via cdp.send: {referrer}")
            return True
        # Try connection.send (fallback)
        elif hasattr(tab, 'connection') and hasattr(tab.connection, 'send'):
            await tab.connection.send("Network.setExtraHTTPHeaders", {
                "headers": {"Referer": referrer}
            })
            logger.info(f"Instance {instance_id}: [REFERRER] ✅ Header set via connection.send: {referrer}")
            return True
    except Exception as e:
        logger.warning(f"Instance {instance_id}: [REFERRER] ⚠️ Failed to set header: {e}")
    return False


async def lock_referrer_js(tab, referrer, instance_id):
    """Lock referrer via JavaScript after page loads."""
    if not referrer:
        return
    
    logger = get_logger()
    try:
        await tab.execute_script(f"""
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


# ========== PROFILE PRE-CONFIGURATION ==========

def preconfigure_fingerprint_profile(profile_dir: Path, cfg):
    """
    Pre-configure a Chrome profile with fingerprint overrides.
    This creates the necessary preference files and extensions
    BEFORE the browser starts, eliminating the race condition.
    """
    logger = get_logger()
    
    try:
        # Create the profile directories
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        # ========== 1. Create Preferences file with all overrides ==========
        preferences = {
            # Disable automation detection
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_settings.popups": 0,
            "download.default_directory": str(PROJECT_ROOT / "data" / "downloads"),
            
            # Disable telemetry
            "safebrowsing.enabled": True,
            "safebrowsing.download_protection_enabled": False,
            "translate.enabled": False,
            "background_mode_enabled": False,
            "autofill.profile_enabled": False,
            "password_manager_enabled": False,
            "search.suggest_enabled": False,
            
            # Disable GPU telemetry
            "webgl.disabled": False,
            "gpu_blacklist_store_version": 0,
            "gpu_driver_bug_list_version": 0,
            
            # ========== FINGERPRINT OVERRIDES IN PREFERENCES ==========
            # These are baked into the profile and applied at launch
            "navigator.platform": cfg.platform,
            "navigator.vendor": cfg.vendor,
            "navigator.userAgent": cfg.user_agent,
            "navigator.webdriver": False,
            
            # Screen/Viewport overrides
            "screen.width": cfg.screen_width,
            "screen.height": cfg.screen_height,
            "window.innerWidth": cfg.viewport_width,
            "window.innerHeight": cfg.viewport_height,
            
            # Language and timezone
            "intl.accept_languages": "en-US,en;q=0.9",
            "intl.date_time_patterns": "en-US",
            "timezone.override": "Asia/Calcutta",
            
            # Disable features that might cause detection
            "webrtc.ip_handling_policy": "disable_non_proxied_udp",
            "webrtc.multiple_routes_enabled": False,
            "webrtc.nonproxied_udp_enabled": False,
        }
        
        # Write preferences to the profile
        prefs_file = profile_dir / "Preferences"
        with open(prefs_file, 'w', encoding='utf-8') as f:
            json.dump(preferences, f, indent=2)
        logger.info(f"[PROFILE] ✅ Preferences written")
        
        # ========== 2. Create Local State file ==========
        local_state = {
            "browser": {
                "enabled_labs_experiments": []
            },
            "extensions": {
                "ui": {
                    "developer_mode": True
                }
            },
            "gpu": {
                "driver_version": "0.0.0",
                "device_id": "0x0000",
                "vendor_id": "0x0000",
                "sub_sys_id": "0x0000",
                "revision": 0
            }
        }
        
        local_state_file = profile_dir / "Local State"
        with open(local_state_file, 'w', encoding='utf-8') as f:
            json.dump(local_state, f, indent=2)
        logger.info(f"[PROFILE] ✅ Local State written")
        
        # ========== 3. Create empty Extensions directory ==========
        extensions_dir = profile_dir / "Extensions"
        extensions_dir.mkdir(exist_ok=True)
        
        # ========== 4. Create a preload script for early injection ==========
        preload_dir = profile_dir / "Default" / "User Scripts"
        preload_dir.mkdir(parents=True, exist_ok=True)
        
        # Get WebGL strings based on platform
        def get_webgl_strings(platform: str, user_agent: str = ""):
            if "Android" in user_agent or "Android" in platform:
                return {
                    "vendor": "Google Inc.",
                    "renderer": "ANGLE (Android, Qualcomm Adreno 640, Vulkan 1.1)"
                }
            elif "iPhone" in user_agent or "iPad" in user_agent or "iOS" in platform:
                return {
                    "vendor": "Apple Inc.",
                    "renderer": "Apple GPU (Apple A14, Metal 3.1)"
                }
            elif "Mac" in platform:
                return {
                    "vendor": "Google Inc. (Apple)",
                    "renderer": "ANGLE (Apple, Apple M1, OpenGL 4.1)"
                }
            else:  # Windows
                return {
                    "vendor": "Google Inc. (Intel)",
                    "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620, Direct3D11)"
                }
        
        webgl_strings = get_webgl_strings(cfg.platform, cfg.user_agent)
        
        # Create the WebGL override script
        webgl_script = f"""
        (function() {{
            console.log('[PROFILE] Applying pre-baked fingerprint overrides...');
            
            // ========== PRESERVE window.chrome (Critical for stealth) ==========
            // Chrome's native window.chrome object has specific properties
            // We need to ensure it exists and has the right structure
            if (typeof window.chrome === 'undefined') {{
                console.log('[PROFILE] Creating window.chrome object...');
                window.chrome = {{
                    app: {{ isInstalled: false, InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }} }},
                    runtime: {{ OnInstalledReason: {{ CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' }} }},
                    loadTimes: function() {{ return {{}}; }},
                    csi: function() {{ return {{}}; }},
                    getVariableValue: function() {{ return ''; }}
                }};
            }}
            


            // Override WebGL renderer for all contexts
            const overrideWebGL = function(context) {{
                const getParameterOriginal = context.prototype.getParameter;
                context.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) {{
                        return "{webgl_strings['vendor']}";
                    }}
                    if (parameter === 37446) {{
                        return "{webgl_strings['renderer']}";
                    }}
                    return getParameterOriginal.apply(this, arguments);
                }};
            }};
            
            if (typeof WebGLRenderingContext !== 'undefined') {{
                overrideWebGL(WebGLRenderingContext);
            }}
            if (typeof WebGL2RenderingContext !== 'undefined') {{
                overrideWebGL(WebGL2RenderingContext);
            }}
            
            // Lock platform and other properties
            const lockProperty = (obj, prop, value) => {{
                try {{
                    Object.defineProperty(obj, prop, {{
                        get: function() {{ return value; }},
                        set: function() {{ }},
                        configurable: false,
                        enumerable: true
                    }});
                }} catch(e) {{}}
            }};
            
            lockProperty(Navigator.prototype, 'platform', '{cfg.platform}');
            lockProperty(Navigator.prototype, 'vendor', '{cfg.vendor}');
            lockProperty(Navigator.prototype, 'userAgent', '{cfg.user_agent}');
            lockProperty(Navigator.prototype, 'webdriver', false);
            
            // Lock screen and viewport
            lockProperty(Screen.prototype, 'width', {cfg.screen_width});
            lockProperty(Screen.prototype, 'height', {cfg.screen_height});
            lockProperty(window, 'innerWidth', {cfg.viewport_width});
            lockProperty(window, 'innerHeight', {cfg.viewport_height});
            
            console.log('[PROFILE] ✅ Pre-baked fingerprint overrides applied');
        }})();
        """
        
        preload_script = preload_dir / "fingerprint.js"
        with open(preload_script, 'w', encoding='utf-8') as f:
            f.write(webgl_script)
        
        logger.info(f"[PROFILE] ✅ Preload script created")
        
        return True
        
    except Exception as e:
        logger.warning(f"[PROFILE] ⚠️ Pre-configuration error: {e}")
        return False


async def apply_fingerprint_overrides(tab, cfg, instance_id: int, custom_referer: str = None):
    """
    Universal fingerprint override using PROTOTYPE SHIELDING.
    Applies fingerprint BEFORE page load using Page.addScriptToEvaluateOnNewDocument.
    """
    logger = get_logger()
    
    try:
        # ========== SAFE CONFIG ACCESS ==========
        def get_config_value(key, default=None):
            if isinstance(cfg, dict):
                val = cfg.get(key, default)
                return default if val is None else val
            val = getattr(cfg, key, default)
            return default if val is None else val
        
        # ========== USE CONFIG VALUES DIRECTLY ==========
        platform = get_config_value('platform')
        vendor = get_config_value('vendor')
        plugins_length = get_config_value('plugins_length', 5)
        is_mobile = get_config_value('is_mobile', False) or get_config_value('force_mobile', False)
        user_agent = get_config_value('user_agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        
        sw = get_config_value('screen_width')
        sh = get_config_value('screen_height')
        vw = get_config_value('viewport_width')
        vh = get_config_value('viewport_height')
        
        is_ios = get_config_value('is_ios', False) or 'iPhone' in user_agent or 'iPad' in user_agent
        is_android = get_config_value('is_android', False) or 'Android' in user_agent
        remove_connection = is_ios
        
        if custom_referer is not None:
            referrer = custom_referer
        else:
            referrer = get_config_value('referer', '')
        
        logger.info(f"Instance {instance_id}: [FINGERPRINT] Using platform={platform}, vendor={vendor}, plugins={plugins_length}, screen={sw}x{sh}, viewport={vw}x{vh}")
        
        is_mobile_str = 'true' if is_mobile else 'false'
        remove_connection_str = 'true' if remove_connection else 'false'

        # ========== BUILD MOCK PLUGINS ==========
        if not is_mobile:
            real_plugins = [
                {"name": "Chrome PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
                {"name": "Chromium PDF Viewer", "filename": "internal-pdf-viewer", "description": ""},
                {"name": "Google Talk Plugin", "filename": "googletalkplugin.dll", "description": "Google Talk Plugin"},
                {"name": "Google Update", "filename": "npGoogleUpdate3.dll", "description": "Google Update"},
                {"name": "Widevine Content Decryption Module", "filename": "widevinecdmadapter.dll", "description": "Widevine Content Decryption Module"},
                {"name": "Native Client", "filename": "internal-nacl-plugin", "description": "Native Client"},
            ]
            plugins_list = real_plugins[:plugins_length]
            import json
            mock_plugins_code = f"""
                const realPlugins = {json.dumps(plugins_list)};
                const mockPlugins = realPlugins.slice(0);
                mockPlugins.length = {plugins_length};
                mockPlugins.item = function(i) {{ return this[i] || null; }};
                mockPlugins.namedItem = function(n) {{
                    for (let i = 0; i < this.length; i++) {{
                        if (this[i].name === n) return this[i];
                    }}
                    return null;
                }};
                mockPlugins.refresh = function() {{}};
            """
        else:
            mock_plugins_code = """
                const mockPlugins = [];
                mockPlugins.length = 0;
                mockPlugins.item = function(i) { return null; };
                mockPlugins.namedItem = function(n) { return null; };
                mockPlugins.refresh = function() {};
            """

#        # ========== PERSISTENT FINGERPRINT SCRIPT ==========
#        fingerprint_script = f"""
#        (function() {{
#            console.log('🔍 [STEALTH] Applying persistent fingerprint overrides...');
#
#            // ========== PRESERVE window.chrome ==========
#            try {{
#                if (typeof window.chrome === 'undefined') {{
#                    window.chrome = {{
#                        app: {{ isInstalled: false, InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }} }},
#                        runtime: {{ OnInstalledReason: {{ CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' }} }},
#                        loadTimes: function() {{ return {{}}; }},
#                        csi: function() {{ return {{}}; }},
#                        getVariableValue: function() {{ return ''; }}
#                    }};
#                    console.log('✅ window.chrome created');
#                }}
#            }} catch(e) {{
#                console.log('⚠️ window.chrome creation failed');
#            }}
#            
#            const lockProperty = (obj, prop, value) => {{
#                try {{
#                    // Try to redefine with configurable: true first
#                    try {{
#                        Object.defineProperty(obj, prop, {{
#                            get: function() {{ return value; }},
#                            set: function(newValue) {{
#                                console.log('[STEALTH] Blocked attempt to change ' + prop);
#                            }},
#                            configurable: true,
#                            enumerable: true
#                        }});
#                        console.log('✅ Locked: ' + prop);
#                        return;
#                    }} catch(e) {{
#                        // If redefinition fails, try direct assignment
#                        try {{
#                            obj[prop] = value;
#                            console.log('✅ Set directly: ' + prop);
#                            return;
#                        }} catch(e2) {{}}
#                    }}
#                    
#                    // Final attempt: define with configurable: false
#                    try {{
#                        Object.defineProperty(obj, prop, {{
#                            get: function() {{ return value; }},
#                            set: function(newValue) {{
#                                console.log('[STEALTH] Blocked attempt to change ' + prop);
#                            }},
#                            configurable: false,
#                            enumerable: true
#                        }});
#                        console.log('✅ Locked (aggressive): ' + prop);
#                    }} catch(e) {{
#                        console.warn('⚠️ Failed to lock ' + prop);
#                    }}
#                }} catch(e) {{
#                    console.warn('⚠️ Failed to lock ' + prop);
#                }}
#            }};
#            
#            // Lock Navigator properties
#            lockProperty(Navigator.prototype, 'platform', '{platform}');
#            lockProperty(Navigator.prototype, 'vendor', '{vendor}');
#            lockProperty(Navigator.prototype, 'userAgent', '{user_agent}');
#            lockProperty(Navigator.prototype, 'webdriver', false);
#            
#            // Lock Plugins
#            {mock_plugins_code}
#            lockProperty(Navigator.prototype, 'plugins', mockPlugins);
#            
#            // Lock MimeTypes
#            if ({is_mobile_str}) {{
#                const emptyMimeTypes = [];
#                emptyMimeTypes.item = () => null;
#                emptyMimeTypes.namedItem = () => null;
#                lockProperty(Navigator.prototype, 'mimeTypes', emptyMimeTypes);
#            }} else {{
#                const emptyMimeTypes = [];
#                emptyMimeTypes.length = 0;
#                emptyMimeTypes.item = () => null;
#                emptyMimeTypes.namedItem = () => null;
#                lockProperty(Navigator.prototype, 'mimeTypes', emptyMimeTypes);
#            }}
#            
#            // Lock Screen properties
#            lockProperty(Screen.prototype, 'width', {sw});
#            lockProperty(Screen.prototype, 'height', {sh});
#            lockProperty(Screen.prototype, 'availWidth', {sw});
#            lockProperty(Screen.prototype, 'availHeight', {sh});
#            
#            // Lock Window properties
#            lockProperty(window, 'innerWidth', {vw});
#            lockProperty(window, 'innerHeight', {vh});
#            lockProperty(window, 'outerWidth', {sw});
#            lockProperty(window, 'outerHeight', {sh});
#            
#            // Lock Connection (iOS)
#            if ({remove_connection_str}) {{
#                try {{ delete Navigator.prototype.connection; }} catch(e) {{}}
#                try {{
#                    Object.defineProperty(Navigator.prototype, 'connection', {{
#                        get: function() {{ return undefined; }},
#                        configurable: false,
#                        enumerable: true
#                    }});
#                }} catch(e) {{}}
#            }}
#            
#            // ========== LOCK REFERRER (FIXED) ==========
#            const referrer = '{referrer}';
#            if (referrer) {{
#                try {{
#                    // Try locking via Object.defineProperty
#                    try {{
#                        Object.defineProperty(Document.prototype, 'referrer', {{
#                            get: function() {{ return referrer; }},
#                            set: function(newValue) {{
#                                console.log('[STEALTH] Blocked referrer change to: ' + newValue);
#                            }},
#                            configurable: true,
#                            enumerable: true
#                        }});
#                        console.log('✅ Referrer locked: ' + referrer);
#                    }} catch(e) {{
#                        console.log('⚠️ Referrer lock via defineProperty failed');
#                        
#                        // Fallback: Set directly on document
#                        try {{
#                            Object.defineProperty(document, 'referrer', {{
#                                get: function() {{ return referrer; }},
#                                set: function() {{ }},
#                                configurable: true,
#                                enumerable: true
#                            }});
#                            console.log('✅ Referrer locked on document directly');
#                        }} catch(e2) {{
#                            console.log('⚠️ Referrer lock fallback failed');
#                        }}
#                    }}
#                }} catch(e) {{
#                    console.warn('⚠️ Referrer lock failed');
#                }}
#            }}
#            
#            // ========== WEBGL OVERRIDE ==========
#            try {{
#                const overrideWebGL = function(context) {{
#                    const getParameterOriginal = context.prototype.getParameter;
#                    context.prototype.getParameter = function(parameter) {{
#                        if (parameter === 37445) {{
#                            return "Apple Inc.";
#                        }}
#                        if (parameter === 37446) {{
#                            return "ANGLE (Apple, Apple M1, Metal)";
#                        }}
#                        return getParameterOriginal.apply(this, arguments);
#                    }};
#                }};
#                
#                if (typeof WebGLRenderingContext !== 'undefined') {{
#                    overrideWebGL(WebGLRenderingContext);
#                    console.log('✅ WebGL1 overridden');
#                }}
#                if (typeof WebGL2RenderingContext !== 'undefined') {{
#                    overrideWebGL(WebGL2RenderingContext);
#                    console.log('✅ WebGL2 overridden');
#                }}
#            }} catch(e) {{
#                console.log('⚠️ WebGL override failed: ' + e.message);
#            }}
#            
#            console.log('✅ Persistent fingerprint overrides applied');
#        }})();
#        """

#        # ========== STEP 1: REGISTER SCRIPT BEFORE NAVIGATION ==========
#        # This ensures the script runs on the next page load
#        try:
#            if hasattr(tab, '_connection_handler') and tab._connection_handler:
#                await tab._connection_handler.execute_command({
#                    "method": "Page.addScriptToEvaluateOnNewDocument",
#                    "params": {"source": fingerprint_script}
#                })
#                logger.info(f"Instance {instance_id}: [STEALTH] ✅ Script registered via _connection_handler")
#            elif hasattr(tab, 'cdp') and hasattr(tab.cdp, 'send'):
#                await tab.cdp.send("Page.addScriptToEvaluateOnNewDocument", {
#                    "source": fingerprint_script
#                })
#                logger.info(f"Instance {instance_id}: [STEALTH] ✅ Script registered via cdp.send")
#            elif hasattr(tab, 'connection') and hasattr(tab.connection, 'send'):
#                await tab.connection.send("Page.addScriptToEvaluateOnNewDocument", {
#                    "source": fingerprint_script
#                })
#                logger.info(f"Instance {instance_id}: [STEALTH] ✅ Script registered via connection.send")
#        except Exception as e:
#            logger.warning(f"Instance {instance_id}: [STEALTH] ⚠️ Script registration failed: {e}")

        # ========== STEP 2: SET REFERRER HEADER ==========
        if referrer:
            await set_referrer_header(tab, referrer, instance_id)

        # ========== STEP 3: CDP OVERRIDES ==========
        # ========== 3a: Override User-Agent & Sec-CH-UA-Platform ==========
        try:
            # Map platform to the format expected in Sec-CH-UA-Platform
            if "Android" in user_agent or is_android:
                sec_platform = "Android"
            elif "iPhone" in user_agent or "iPad" in user_agent or is_ios:
                sec_platform = "iOS"
            elif "Mac" in platform:
                sec_platform = "macOS"
            else:
                sec_platform = "Windows"
            
            # Extract Chrome version from user-agent
            import re
            version_match = re.search(r'Chrome/(\d+)\.', user_agent)
            brand_version = version_match.group(1) if version_match else "148"
            full_version = f"{brand_version}.0.0.0"
            
            # Get values from fingerprint profile if available
            fingerprint = getattr(cfg, 'fingerprint_profile', {})
            
            # Determine platform version based on sec_platform if not in fingerprint
            if fingerprint.get('platformVersion'):
                platform_version = fingerprint.get('platformVersion')
            else:
                if sec_platform == "Windows":
                    platform_version = "10.0.0"
                elif sec_platform == "macOS":
                    platform_version = "15.7.0"
                elif sec_platform == "Android":
                    platform_version = "14.0.0"
                elif sec_platform == "iOS":
                    platform_version = "17.5.0"
                else:
                    platform_version = "10.0.0"
            
            # Set architecture based on platform
            if "Android" in user_agent or is_android:
                architecture = "arm64"
            elif "iPhone" in user_agent or "iPad" in user_agent or is_ios:
                architecture = "arm64"
            elif "Mac" in platform:
                architecture = "arm64" if "M1" in user_agent or "M2" in user_agent else "x86"
            else:
                architecture = "x86"
            
            bitness = fingerprint.get('bitness', '64')
            model = fingerprint.get('model', '')
            
            # Build the metadata payload (this sets Sec-CH-UA-Platform)
            ua_metadata = {
                "brands": [
                    {"brand": "Not A(Automated-Brand", "version": "99"},
                    {"brand": "Google Chrome", "version": brand_version},
                    {"brand": "Chromium", "version": brand_version}
                ],
                "fullVersionList": [
                    {"brand": "Not A(Automated-Brand", "version": "99.0.0.0"},
                    {"brand": "Google Chrome", "version": full_version},
                    {"brand": "Chromium", "version": full_version}
                ],
                "fullVersion": full_version,
                "platform": sec_platform,  # <-- This sets Sec-CH-UA-Platform
                "platformVersion": platform_version,
                "architecture": architecture,
                "model": model,
                "mobile": is_mobile,
                "bitness": bitness,
                "wow64": False
            }
            
            if hasattr(tab, 'cdp') and hasattr(tab.cdp, 'send'):
                await tab.cdp.send("Emulation.setUserAgentOverride", {
                    "userAgent": user_agent,
                    "acceptLanguage": "en-US,en;q=0.9",
                    "platform": platform,
                    "userAgentMetadata": ua_metadata
                })
                logger.info(f"Instance {instance_id}: [STEALTH] ✅ Sec-CH-UA-Platform set to '{sec_platform}' with architecture '{architecture}'")
        except Exception as e:
            logger.warning(f"Instance {instance_id}: [STEALTH] ⚠️ Sec-CH-UA-Platform override failed: {e}")

#        # ========== 3b: Override Device Metrics (ENABLED FOR MOBILE) ==========
#        if is_mobile:
#            try:
#                if hasattr(tab, 'cdp') and hasattr(tab.cdp, 'send'):
#                    await tab.cdp.send("Emulation.setDeviceMetricsOverride", {
#                        "width": vw,
#                        "height": vh,
#                        "deviceScaleFactor": 2,  # Mobile DPR
#                        "mobile": True,
#                        "screenOrientation": {"type": "portraitPrimary", "angle": 0}
#                    })
#                    logger.info(f"Instance {instance_id}: [STEALTH] ✅ DeviceMetrics override applied for mobile: {vw}x{vh}")
#            except Exception as e:
#                logger.warning(f"Instance {instance_id}: [STEALTH] ⚠️ DeviceMetrics override failed for mobile: {e}")
#        else:
#            # Desktop - skip DeviceMetrics override (it causes issues)
#            logger.info(f"Instance {instance_id}: [STEALTH] ⏭️ Skipping DeviceMetrics override for desktop")


        # ========== STEP 4: MINIMAL OVERRIDE (WebGL + Vendor + Plugins for ALL platforms) ==========
        try:
            # Determine WebGL values based on platform
            if "Android" in platform or is_android:
                webgl_vendor = "Google Inc."
                webgl_renderer = "ANGLE (Android, Qualcomm Adreno 640, Vulkan 1.1)"
                ios_chrome_fix = ""
            elif "iPhone" in platform or "iPad" in platform or is_ios:
                webgl_vendor = "Apple Inc."
                webgl_renderer = "Apple GPU (Apple A14, Metal 3.1)"
                # iOS - REMOVE window.chrome (real iOS browsers don't have it)
                ios_chrome_fix = """
                    // ========== iOS FIX: Remove window.chrome ==========
                    try {
                        if (window.chrome) {
                            delete window.chrome;
                            console.log('✅ window.chrome removed for iOS');
                        }
                    } catch(e) {
                        console.log('⚠️ window.chrome removal failed');
                    }
                """
            elif "Mac" in platform:
                webgl_vendor = "Apple Inc."
                webgl_renderer = "ANGLE (Apple, Apple M1, Metal)"
                ios_chrome_fix = ""
            else:  # Windows
                webgl_vendor = "Google Inc. (Intel)"
                webgl_renderer = "ANGLE (Intel, Intel(R) UHD Graphics 620, Direct3D11)"
                ios_chrome_fix = ""

            # Build the script: WebGL + Vendor + Plugins (instance-first) for ALL platforms
            minimal_override_script = f"""
            (function() {{
                try {{
                    // ========== OVERRIDE VENDOR ==========
                    try {{
                        Object.defineProperty(Navigator.prototype, 'vendor', {{
                            get: function() {{ return "{vendor}"; }},
                            set: function() {{ }},
                            configurable: true,
                            enumerable: true
                        }});
                        console.log('✅ Vendor overridden');
                    }} catch(e) {{
                        console.log('⚠️ Vendor override failed');
                    }}
                    
                    // ========== IOS FIX: Remove window.chrome ==========
                    {ios_chrome_fix}
                    
                    // ========== OVERRIDE PLUGINS (INSTANCE FIRST) ==========
                    try {{
                        {mock_plugins_code}
                        // Try to define on the instance (navigator) first
                        try {{
                            Object.defineProperty(navigator, 'plugins', {{
                                get: function() {{ return mockPlugins; }},
                                set: function() {{ }},
                                configurable: true,
                                enumerable: true
                            }});
                            console.log('✅ Plugins overridden on navigator instance');
                        }} catch(e) {{
                            // If instance fails, try prototype
                            try {{
                                Object.defineProperty(Navigator.prototype, 'plugins', {{
                                    get: function() {{ return mockPlugins; }},
                                    set: function() {{ }},
                                    configurable: true,
                                    enumerable: true
                                }});
                                console.log('✅ Plugins overridden on prototype');
                            }} catch(e2) {{
                                console.log('⚠️ Plugins override failed on both instance and prototype');
                            }}
                        }}
                    }} catch(e) {{
                        console.log('⚠️ Plugins override failed');
                    }}
                    
                    // ========== OVERRIDE MIMETYPES ==========
                    try {{
                        const emptyMimeTypes = [];
                        emptyMimeTypes.length = 0;
                        emptyMimeTypes.item = function(i) {{ return null; }};
                        emptyMimeTypes.namedItem = function(n) {{ return null; }};
                        // Try instance first
                        try {{
                            Object.defineProperty(navigator, 'mimeTypes', {{
                                get: function() {{ return emptyMimeTypes; }},
                                set: function() {{ }},
                                configurable: true,
                                enumerable: true
                            }});
                            console.log('✅ MimeTypes overridden on instance');
                        }} catch(e) {{
                            Object.defineProperty(Navigator.prototype, 'mimeTypes', {{
                                get: function() {{ return emptyMimeTypes; }},
                                set: function() {{ }},
                                configurable: true,
                                enumerable: true
                            }});
                            console.log('✅ MimeTypes overridden on prototype');
                        }}
                    }} catch(e) {{
                        console.log('⚠️ MimeTypes override failed');
                    }}
                    
                    // ========== OVERRIDE WEBGL ==========
                    try {{
                        const overrideWebGL = function(context) {{
                            const getParameterOriginal = context.prototype.getParameter;
                            context.prototype.getParameter = function(parameter) {{
                                if (parameter === 37445) return "{webgl_vendor}";
                                if (parameter === 37446) return "{webgl_renderer}";
                                return getParameterOriginal.apply(this, arguments);
                            }};
                        }};
                        if (typeof WebGLRenderingContext !== 'undefined') {{
                            overrideWebGL(WebGLRenderingContext);
                            console.log('✅ WebGL1 overridden');
                        }}
                        if (typeof WebGL2RenderingContext !== 'undefined') {{
                            overrideWebGL(WebGL2RenderingContext);
                            console.log('✅ WebGL2 overridden');
                        }}
                    }} catch(e) {{
                        console.log('⚠️ WebGL override failed:', e.message);
                    }}
                    
                    console.log('✅ Minimal fingerprint overrides applied');
                }} catch(e) {{
                    console.log('⚠️ Override script error:', e.message);
                }}
            }})();
            """
            
            # Register for future pages
            if hasattr(tab, '_connection_handler') and tab._connection_handler:
                await tab._connection_handler.execute_command({
                    "method": "Page.addScriptToEvaluateOnNewDocument",
                    "params": {"source": minimal_override_script}
                })
                logger.info(f"Instance {instance_id}: [STEALTH] ✅ Minimal override registered for {platform}")
            
            # Execute on current page
            await tab.execute_script(minimal_override_script)
            logger.info(f"Instance {instance_id}: [STEALTH] ✅ Minimal override applied to current page")
            
        except Exception as e:
            logger.warning(f"Instance {instance_id}: [STEALTH] ⚠️ Minimal override failed: {e}")




#        # ========== STEP 4: IMMEDIATE EXECUTION ON CURRENT PAGE ==========
#        # This applies the fingerprint to the current page if already loaded
#        try:
#            await tab.execute_script(fingerprint_script)
#            logger.info(f"Instance {instance_id}: [STEALTH] ✅ Fingerprint applied to current page")
#        except Exception as e:
#            logger.warning(f"Instance {instance_id}: [STEALTH] ⚠️ Current page execution failed: {e}")

        # ========== STEP 5: EXTRA REFERRER LOCK ==========
        if referrer:
            await lock_referrer_js(tab, referrer, instance_id)

        # ========== STEP 6: HANDLE RECAPTCHA ==========
        try:
            from pydoll.common.human_behavior import handle_recaptcha
            await handle_recaptcha(tab, instance_id)
        except Exception as e:
            logger.debug(f"Instance {instance_id}: [CAPTCHA] Handler error: {e}")

        return True

    except Exception as e:
        logger.error(f"Instance {instance_id}: [FINGERPRINT OVERRIDE FAILURE]: {e}")
        return False




async def maintain_fingerprint_heartbeat(tab, cfg, instance_id: int):
    """
    Periodically verify ALL fingerprint signals during watch.
    Checks: vendor, platform, userAgent, webdriver, plugins, screen, viewport, referrer, window.chrome, WebGL.
    """
    logger = get_logger()
    
    try:
        signals = await tab.execute_script("""
            return {
                vendor: navigator.vendor || '',
                platform: navigator.platform || '',
                userAgent: navigator.userAgent || '',
                webdriver: navigator.webdriver || false,
                plugins_length: navigator.plugins ? navigator.plugins.length : -1,
                mimeTypesLength: navigator.mimeTypes ? navigator.mimeTypes.length : -1,
                screenWidth: window.screen ? window.screen.width : 0,
                screenHeight: window.screen ? window.screen.height : 0,
                viewportWidth: window.innerWidth || 0,
                viewportHeight: window.innerHeight || 0,
                referrer: document.referrer || '',
                hasChrome: typeof window.chrome !== 'undefined',
                
                // ========== WEBGL / GPU CHECKS ==========
                gpuVendor: (function() {
                    try {
                        var canvas = document.createElement('canvas');
                        var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                        if (gl) {
                            var ext = gl.getExtension('WEBGL_debug_renderer_info');
                            if (ext) {
                                return gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
                            }
                        }
                        return '';
                    } catch(e) {
                        return '';
                    }
                })(),
                gpuRenderer: (function() {
                    try {
                        var canvas = document.createElement('canvas');
                        var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                        if (gl) {
                            var ext = gl.getExtension('WEBGL_debug_renderer_info');
                            if (ext) {
                                return gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
                            }
                        }
                        return '';
                    } catch(e) {
                        return '';
                    }
                })()
            }
        """)
        
        if isinstance(signals, dict):
            signals = signals.get('result', {}).get('result', {}).get('value', signals)
        
        expected_vendor = getattr(cfg, 'vendor', 'Google Inc.')
        expected_platform = getattr(cfg, 'platform', 'MacIntel')
        expected_user_agent = getattr(cfg, 'user_agent', '')
        expected_plugins_length = getattr(cfg, 'plugins_length', 5)
        expected_screen_w = getattr(cfg, 'screen_width', 1366)
        expected_screen_h = getattr(cfg, 'screen_height', 768)
        expected_viewport_w = getattr(cfg, 'viewport_width', 1366)
        expected_viewport_h = getattr(cfg, 'viewport_height', 688)
        expected_referrer = getattr(cfg, 'referer', '')
        
        # Expected WebGL values based on platform
        if "Mac" in expected_platform:
            expected_gpu_vendor = "Apple Inc."
            expected_gpu_renderer = "ANGLE (Apple, Apple M1, Metal)"
        elif "Android" in expected_platform:
            expected_gpu_vendor = "Google Inc."
            expected_gpu_renderer = "ANGLE (Android, Qualcomm Adreno 640, Vulkan 1.1)"
        else:  # Windows
            expected_gpu_vendor = "Google Inc. (Intel)"
            expected_gpu_renderer = "ANGLE (Intel, Intel(R) UHD Graphics 620, Direct3D11)"
        
        current_vendor = signals.get('vendor', '')
        current_platform = signals.get('platform', '')
        current_user_agent = signals.get('userAgent', '')
        current_webdriver = signals.get('webdriver', False)
        current_plugins = signals.get('plugins_length', -1)
        current_mime_types = signals.get('mimeTypesLength', -1)
        current_screen_w = signals.get('screenWidth', 0)
        current_screen_h = signals.get('screenHeight', 0)
        current_vp_w = signals.get('viewportWidth', 0)
        current_vp_h = signals.get('viewportHeight', 0)
        current_referrer = signals.get('referrer', '')
        has_chrome = signals.get('hasChrome', False)
        
        # WebGL values
        current_gpu_vendor = signals.get('gpuVendor', '')
        current_gpu_renderer = signals.get('gpuRenderer', '')
        
        # ========== CHECK FOR TEMPORARY BLANK STATES ==========
        all_blank = (current_vendor == "" and current_platform == "" and 
                     current_screen_w == 0 and current_screen_h == 0 and
                     current_vp_w == 0 and current_vp_h == 0)
        
        if all_blank:
            logger.info(f"Instance {instance_id}: [HEARTBEAT] Ignoring complete blank state")
            return
        
        # Fill in blank values for comparison
        if current_vendor == "":
            current_vendor = expected_vendor
        if current_platform == "":
            current_platform = expected_platform
        if current_user_agent == "":
            current_user_agent = expected_user_agent
        if current_screen_w == 0:
            current_screen_w = expected_screen_w
        if current_screen_h == 0:
            current_screen_h = expected_screen_h
        if current_vp_w == 0:
            current_vp_w = expected_viewport_w
        if current_vp_h == 0:
            current_vp_h = expected_viewport_h
        
        drift_detected = False
        
        # ========== CHECK ALL SIGNALS ==========
        # 1. Vendor
        if current_vendor != expected_vendor:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Vendor drift: {current_vendor} != {expected_vendor}")
            drift_detected = True
        
        # 2. Platform
        if current_platform != expected_platform:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Platform drift: {current_platform} != {expected_platform}")
            drift_detected = True
        
        # 3. UserAgent
        if current_user_agent != expected_user_agent and expected_user_agent:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] UserAgent drift: {current_user_agent[:50]} != {expected_user_agent[:50]}")
            drift_detected = True
        
        # 4. Webdriver
        if current_webdriver != False:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Webdriver drift: {current_webdriver} != false")
            drift_detected = True
        
        # 5. Plugins length
        if current_plugins != expected_plugins_length and current_plugins != -1:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Plugins drift: {current_plugins} != {expected_plugins_length}")
            drift_detected = True
        
        # 6. MimeTypes length
        if current_mime_types != 0 and current_mime_types != -1:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] MimeTypes drift: {current_mime_types} != 0")
            drift_detected = True
        
        # 7-8. Screen
        if current_screen_w != expected_screen_w:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Screen width drift: {current_screen_w} != {expected_screen_w}")
            drift_detected = True
        
        if current_screen_h != expected_screen_h:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Screen height drift: {current_screen_h} != {expected_screen_h}")
            drift_detected = True
        
        # 9-10. Viewport
        if current_vp_w != expected_viewport_w:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Viewport width drift: {current_vp_w} != {expected_viewport_w}")
            drift_detected = True
        
        if current_vp_h != expected_viewport_h:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Viewport height drift: {current_vp_h} != {expected_viewport_h}")
            drift_detected = True
        
        # 11. Referrer
        if expected_referrer and current_referrer and 'youtube.com' in current_referrer:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Referrer drift: {current_referrer} != {expected_referrer}")
            drift_detected = True
        elif expected_referrer and current_referrer != expected_referrer and current_referrer:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Referrer drift: {current_referrer} != {expected_referrer}")
            drift_detected = True
        
        # 12. window.chrome
        if not has_chrome:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] window.chrome missing!")
            drift_detected = True
        
        # ========== 13-14. WebGL / GPU CHECKS ==========
        if current_gpu_vendor and current_gpu_vendor != expected_gpu_vendor:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] GPU Vendor drift: {current_gpu_vendor} != {expected_gpu_vendor}")
            drift_detected = True
        
        if current_gpu_renderer and current_gpu_renderer != expected_gpu_renderer:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] GPU Renderer drift: {current_gpu_renderer[:50]} != {expected_gpu_renderer[:50]}")
            drift_detected = True
        
        # ========== RE-APPLY FINGERPRINT IF DRIFT DETECTED ==========
        if drift_detected:
            logger.warning(f"Instance {instance_id}: [HEARTBEAT] Drift detected! Re-applying...")
            
            referrer = getattr(cfg, 'referer', '')
            await apply_fingerprint_overrides(tab, cfg, instance_id, custom_referer=referrer)
            
            logger.info(f"Instance {instance_id}: [HEARTBEAT] ✅ Fingerprint restored")
        
    except Exception as e:
        logger.warning(f"Instance {instance_id}: [HEARTBEAT] Check failed: {e}")
        





# ========== UNIFIED BACKGROUND MONITOR ==========

async def start_background_monitor(tab, cfg, instance_id: int):
    """
    Start a unified background task that continuously:
    - Maintains fingerprint consistency (every 2 seconds)
    - Checks for popups (every 6 seconds)
    - Checks for reCAPTCHA (every 6 seconds)
    - Checks for cookie consent (every 6 seconds)
    """
    logger = get_logger()
    logger.info(f"Instance {instance_id}: [MONITOR] Starting unified background monitor")
    
    
    heartbeat_count = 0
    monitor_count = 0
    
    while True:
        try:
            await asyncio.sleep(15)  # Base interval: 2 seconds
            heartbeat_count += 1
            monitor_count += 1
            
            # ========== FINGERPRINT HEARTBEAT (Every 2 seconds) ==========
            try:
                await maintain_fingerprint_heartbeat(tab, cfg, instance_id)
            except Exception as e:
                logger.debug(f"Instance {instance_id}: [MONITOR] Heartbeat error: {e}")
            
            # ========== POPUPS & INTERRUPTIONS (Every 3rd check = 6 seconds) ==========
            if monitor_count % 3 == 0:
                try:
                    await handle_all_popups(tab, instance_id, max_attempts=3)
                except Exception as e:
                    logger.debug(f"Instance {instance_id}: [MONITOR] Popup error: {e}")
                
                try:
                    await handle_recaptcha(tab, instance_id)
                except Exception as e:
                    logger.debug(f"Instance {instance_id}: [MONITOR] reCAPTCHA error: {e}")
                
                try:
                    await handle_consent_popups(tab, instance_id)
                except Exception as e:
                    logger.debug(f"Instance {instance_id}: [MONITOR] Consent error: {e}")
                
                monitor_count = 0  # Reset counter
                
        except asyncio.CancelledError:
            logger.info(f"Instance {instance_id}: [MONITOR] Stopped")
            break
        except Exception as e:
            logger.debug(f"Instance {instance_id}: [MONITOR] Error: {e}")



async def create_driver_with_po_token_pydoll(cfg, profile_prefix: str = "yt_pydoll_cache"):
    """
    Create Pydoll browser with fingerprint support using persistent profile.
    The profile is pre-configured with fingerprint overrides BEFORE browser starts.
    """
    if not PYDOLL_AVAILABLE:
        raise ImportError("Pydoll is not available. Install: pip install pydoll-python")

    logger = get_logger()
    
    if _script_logger:
        _script_logger.info(f"Instance {cfg.instance_id}: 🚀 Starting Pydoll browser...")
        _script_logger.info(f"Instance {cfg.instance_id}: 📱 Platform: {cfg.platform}")
        _script_logger.info(f"Instance {cfg.instance_id}: 📱 Device: {cfg.device_category}")
        _script_logger.info(f"Instance {cfg.instance_id}: 🔌 Proxy Mode: {cfg.proxy_mode}")

    try:
        # ========== CREATE PERSISTENT PROFILE ==========
        # Generate a unique profile name from fingerprint
        profile_id = hashlib.md5(
            f"{cfg.platform}_{cfg.user_agent}_{cfg.screen_width}_{cfg.screen_height}_{cfg.vendor}".encode()
        ).hexdigest()[:16]
        
        PROFILES_DIR = PROJECT_ROOT / "data" / "browser_profiles"
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        
        profile_dir = PROFILES_DIR / f"profile_{profile_id}"
        
        # ========== PRE-CONFIGURE THE PROFILE ==========
        # This applies fingerprint BEFORE browser starts
        preconfigure_fingerprint_profile(profile_dir, cfg)
        
        cfg._profile_dir = str(profile_dir)
        
        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: 📁 Using pre-configured profile: {profile_dir}")

        options = ChromiumOptions()
        
        # ========== FINGERPRINT OVERRIDES VIA COMMAND-LINE SWITCHES ==========
        
        # 1. Platform
        if cfg.platform:
            options.add_argument(f'--platform={cfg.platform}')
        
        # 2. Force mobile viewport (disable Chrome's automatic mobile emulation)
        if cfg.force_mobile or cfg.device_category == 'mobile':
            options.add_argument('--disable-viewport')
            options.add_argument('--disable-mobile-emulation')
            options.add_argument('--disable-features=ViewportDimensions')
            options.add_argument('--enable-viewport')
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [VIEWPORT] Mobile viewport forced")
        
        # 3. User-Agent
        if cfg.user_agent:
            options.add_argument(f'--user-agent={cfg.user_agent}')
        
        # 4. Viewport / Window Size
        if cfg.viewport_width and cfg.viewport_height:
            options.add_argument(f'--window-size={cfg.viewport_width},{cfg.viewport_height}')
        
        # 5. Disable automation detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # 6. GPU/WEBGL BACKEND (Based on platform)
        if "Mac" in cfg.platform or "iPhone" in cfg.platform or "iOS" in cfg.platform:
            options.add_argument("--use-gl=angle")
            options.add_argument("--use-angle=metal")
            options.add_argument("--ignore-gpu-blocklist")
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [GPU] Using Metal backend for {cfg.platform}")
        elif "Android" in cfg.platform:
            options.add_argument("--use-gl=angle")
            options.add_argument("--use-angle=vulkan")
            options.add_argument("--ignore-gpu-blocklist")
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [GPU] Using Vulkan backend for {cfg.platform}")
        else:  # Windows
            options.add_argument("--use-gl=angle")
            options.add_argument("--use-angle=d3d11")
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [GPU] Using Direct3D11 backend for {cfg.platform}")
        
        # 7. Additional GPU flags
        options.add_argument("--disable-gpu-driver-bug-workarounds")
        options.add_argument("--disable-gpu-vsync")
        options.add_argument("--disable-features=GpuProcessLaunchFix")
        
        # 8. Mobile-specific flags (touch events, scale factor)
        if cfg.force_mobile or cfg.device_category == 'mobile':
            options.add_argument('--touch-events=enabled')
            options.add_argument('--force-device-scale-factor=2')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-extensions')
        
        # 9. Headless mode
        if cfg.headless:
            options.add_argument('--headless=new')
        
        # 10. ========== STEALTH / ANTI-DETECTION FLAGS ==========
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--disable-site-isolation-trials")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-features=CalculateNativeWinOcclusion")
        options.add_argument("--disable-features=BackgroundVideoTrackOptimization")
        options.add_argument("--disable-features=MediaSessionService")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--disable-component-update")

        # 11. Proxy Setup
        proxy_url, proxy_extra_args = _get_proxy_config(cfg)
        if proxy_url:
            proxy_args = [f'--proxy-server={proxy_url}']
            if 'http://' in proxy_url:
                proxy_args.append('--proxy-bypass-list=<-loopback>')
            if proxy_extra_args:
                proxy_args.extend(proxy_extra_args)
            for arg in proxy_args:
                options.add_argument(arg)

        # ========== LAUNCH BROWSER ==========
        chrome = Chrome(options=options)
        tab = await chrome.start()

        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: ✅ Browser launched with pre-configured fingerprint")

        # ========== LIGHTWEIGHT OVERRIDE (Just in case) ==========
        # The heavy lifting is already in the profile, so this is minimal
        await apply_fingerprint_overrides(tab, cfg, cfg.instance_id, custom_referer="")

        if cfg.po_token:
            tab._po_token = cfg.po_token
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: ✅ PO token stored")

        # ========== VERIFICATION (unchanged) ==========
        if _script_logger:
            try:
                vendor = await tab.execute_script("return navigator.vendor;")
                if isinstance(vendor, dict):
                    vendor = vendor.get('result', {}).get('result', {}).get('value', 'unknown')
                _script_logger.info(f"Instance {cfg.instance_id}: [VERIFY] Vendor: {vendor}")

                plugins = await tab.execute_script("return navigator.plugins.length;")
                if isinstance(plugins, dict):
                    plugins = plugins.get('result', {}).get('result', {}).get('value', 'unknown')
                _script_logger.info(f"Instance {cfg.instance_id}: [VERIFY] Plugins: {plugins}")

                screen_w = await tab.execute_script("return window.screen.width;")
                screen_h = await tab.execute_script("return window.screen.height;")
                if isinstance(screen_w, dict):
                    screen_w = screen_w.get('result', {}).get('result', {}).get('value', 'unknown')
                if isinstance(screen_h, dict):
                    screen_h = screen_h.get('result', {}).get('result', {}).get('value', 'unknown')
                _script_logger.info(f"Instance {cfg.instance_id}: [VERIFY] Screen: {screen_w}x{screen_h}")

                vp_w = await tab.execute_script("return window.innerWidth;")
                vp_h = await tab.execute_script("return window.innerHeight;")
                if isinstance(vp_w, dict):
                    vp_w = vp_w.get('result', {}).get('result', {}).get('value', 'unknown')
                if isinstance(vp_h, dict):
                    vp_h = vp_h.get('result', {}).get('result', {}).get('value', 'unknown')
                _script_logger.info(f"Instance {cfg.instance_id}: [VERIFY] Viewport: {vp_w}x{vp_h}")

                referrer = await tab.execute_script("return document.referrer;")
                if isinstance(referrer, dict):
                    referrer = referrer.get('result', {}).get('result', {}).get('value', 'unknown')
                _script_logger.info(f"Instance {cfg.instance_id}: [VERIFY] Referrer: {referrer}")
            except Exception as e:
                if _script_logger:
                    _script_logger.warning(f"Instance {cfg.instance_id}: [VERIFY] Verification failed: {e}")

        # ========== GENERATE VISITOR_INFO1_LIVE FOR NATIVE MODE ==========
        if cfg.po_token_source == "native":
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: [COOKIE] Native mode - attempting to generate VISITOR_INFO1_LIVE...")
            
            try:
                from common.po_token import get_visitor_data
                
                proxy_url = None
                if cfg.proxy_mode == "tor_browser":
                    proxy_url = "socks5://127.0.0.1:9150"
                elif cfg.proxy_mode == "tor_service":
                    proxy_url = "socks5://127.0.0.1:9050"
                
                fingerprint = getattr(cfg, 'fingerprint_profile', None)
                visitor_cookie = get_visitor_data(cfg.video_id, proxy_url, fingerprint)
                
                if visitor_cookie:
                    if _script_logger:
                        _script_logger.info(f"Instance {cfg.instance_id}: [COOKIE] ✅ VISITOR_INFO1_LIVE obtained: {visitor_cookie[:30]}...")
                    
                    # ========== SET COOKIE VIA CDP (Domain-Aware) ==========
                    try:
                        # Navigate to youtube.com first to set domain context
                        await tab.go_to("https://www.youtube.com")
                        await asyncio.sleep(1)
                        
                        # Get current domain to set correct cookie
                        current_url = await tab.execute_script("return window.location.href;")
                        if isinstance(current_url, dict):
                            current_url = current_url.get('result', {}).get('result', {}).get('value', '')
                        
                        # Determine the correct domain for the cookie
                        if 'm.youtube.com' in current_url:
                            cookie_domain = 'm.youtube.com'
                            if _script_logger:
                                _script_logger.info(f"Instance {cfg.instance_id}: [COOKIE] Using mobile domain: {cookie_domain}")
                        else:
                            cookie_domain = '.youtube.com'  # Wildcard domain for desktop
                            if _script_logger:
                                _script_logger.info(f"Instance {cfg.instance_id}: [COOKIE] Using desktop domain: {cookie_domain}")
                        
                        # Set VISITOR_INFO1_LIVE via CDP with correct domain
                        # Try _connection_handler first (Pydoll's native)
                        if hasattr(tab, '_connection_handler') and tab._connection_handler:
                            await tab._connection_handler.execute_command({
                                "method": "Network.setCookie",
                                "params": {
                                    "name": "VISITOR_INFO1_LIVE",
                                    "value": visitor_cookie,
                                    "domain": cookie_domain,
                                    "path": "/",
                                    "secure": True,
                                    "httpOnly": False,
                                    "sameSite": "None"
                                }
                            })
                        # Try connection.send (alternative)
                        elif hasattr(tab, 'connection') and hasattr(tab.connection, 'send'):
                            await tab.connection.send("Network.setCookie", {
                                "name": "VISITOR_INFO1_LIVE",
                                "value": visitor_cookie,
                                "domain": cookie_domain,
                                "path": "/",
                                "secure": True,
                                "httpOnly": False,
                                "sameSite": "None"
                            })
                        
                        if _script_logger:
                            _script_logger.info(f"Instance {cfg.instance_id}: [COOKIE] ✅ VISITOR_INFO1_LIVE set via CDP for domain: {cookie_domain}")
                        
                        # Verify
                        verify = await tab.execute_script("return document.cookie;")
                        if 'VISITOR_INFO1_LIVE' in verify:
                            if _script_logger:
                                _script_logger.info(f"Instance {cfg.instance_id}: [COOKIE] ✅ Verified: VISITOR_INFO1_LIVE is set")
                        else:
                            if _script_logger:
                                _script_logger.warning(f"Instance {cfg.instance_id}: [COOKIE] ⚠️ Verification failed: VISITOR_INFO1_LIVE not found")
                    except Exception as e:
                        if _script_logger:
                            _script_logger.warning(f"Instance {cfg.instance_id}: [COOKIE] CDP injection failed: {e}")
                else:
                    if _script_logger:
                        _script_logger.warning(f"Instance {cfg.instance_id}: [COOKIE] ⚠️ Could not generate VISITOR_INFO1_LIVE")
            except Exception as e:
                if _script_logger:
                    _script_logger.warning(f"Instance {cfg.instance_id}: [COOKIE] Error: {e}")

        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: ✅ Pydoll driver ready")

        # ========== STORE PROFILE PATH ==========
        tab._profile_dir = str(profile_dir)

        # ========== START UNIFIED BACKGROUND MONITOR ==========
        monitor_task = asyncio.create_task(start_background_monitor(tab, cfg, cfg.instance_id))
        tab._monitor_task = monitor_task
        tab._cfg = cfg
        tab._instance_id = cfg.instance_id

        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: ✅ Unified background monitor started")

        return chrome, tab, str(profile_dir)

    except Exception as e:
        if _script_logger:
            _script_logger.error(f"Instance {cfg.instance_id}: ❌ Failed to create Pydoll driver: {e}")
            import traceback
            _script_logger.error(traceback.format_exc())
        raise


def get_page_with_po_token(page, video_id: str, po_token: str = None) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    if po_token:
        url = add_po_token_to_url(url, po_token)
    return url


# ========== EXPORTS ==========
__all__ = [
    'create_driver_with_po_token_pydoll',
    'apply_fingerprint_overrides',
    'get_page_with_po_token',
    'set_logger',
    'get_logger',
    'PYDOLL_AVAILABLE',
    'cleanup_all_browsers',
    'register_cleanup_handlers',
    'kill_child_processes',
    'maintain_fingerprint_heartbeat',
    'start_background_monitor',
    'set_referrer_header',
    'lock_referrer_js'
]