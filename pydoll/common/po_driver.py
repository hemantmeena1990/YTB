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
import signal
import atexit
import psutil
import subprocess

# ========== PATH SETUP ==========
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "common"))

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

# Global logger
_script_logger = None


def set_logger(logger):
    """Set global logger for driver"""
    global _script_logger
    _script_logger = logger
    



# ========== CLEANUP FUNCTIONS ==========

def kill_child_processes(parent_pid: int, signal_type=signal.SIGTERM):
    """
    Kill all child processes of a given parent PID.
    """
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
        # Kill the parent itself
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
    """
    Clean up all browser processes spawned by this script.
    """
    current_pid = os.getpid()
    if _script_logger:
        _script_logger.info(f"🧹 Cleaning up browser processes for PID: {current_pid}")
    
    try:
        # Method 1: Kill child processes
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

        # Method 2: Kill any chrome processes with this script's PID as parent chain
        try:
            for proc in psutil.process_iter(['pid', 'name', 'ppid', 'cmdline']):
                try:
                    # Check if this process is a browser started by our script
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
    """
    Handle Ctrl+C gracefully.
    """
    if _script_logger:
        _script_logger.info("🛑 Received interrupt signal. Cleaning up...")
    cleanup_all_browsers()
    sys.exit(0)


def register_cleanup_handlers():
    """
    Register signal and atexit handlers for cleanup.
    """
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup_all_browsers)
    if _script_logger:
        _script_logger.info("🧹 Cleanup handlers registered")




def _get_proxy_config(cfg):
    """
    Get proxy configuration for Pydoll.
    Returns: (proxy_url, extra_arguments)
    """
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


async def apply_fingerprint_overrides(tab, cfg, instance_id: int, custom_referer: str = None):
    """
    Universal fingerprint override using PROTOTYPE SHIELDING.
    This survives page refreshes by modifying the base prototypes.
    """
    if not _script_logger:
        return False

    try:
        # ========== SAFE CONFIG ACCESS ==========
        def get_config_value(key, default=None):
            if isinstance(cfg, dict):
                return cfg.get(key, default)
            return getattr(cfg, key, default)
        
        # ========== GET VALUES FROM CONFIG ==========
        ua = get_config_value('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        is_mobile = get_config_value('is_mobile', False) or get_config_value('force_mobile', False)
        
        # Derive platform from User Agent
        if 'iPhone' in ua or 'iPad' in ua:
            platform = 'iPhone'
            vendor = 'Apple Computer, Inc.'
            plugins_count = 0
            remove_connection = True
            platform_version = '18_5_0'
            architecture = 'arm_64'
            model = 'iPhone'
        elif 'Android' in ua:
            platform = 'Android'
            vendor = 'Google Inc.'
            plugins_count = 0 if is_mobile else get_config_value('plugins_length', 5)
            remove_connection = False
            # Try to get from fingerprint, fallback to defaults
            platform_version = get_config_value('platform_version', '14.0.0')
            architecture = get_config_value('architecture', 'arm64-v8a')
            model = get_config_value('model', 'SM-S928B')
        elif 'Mac' in ua or 'macOS' in ua:
            platform = 'MacIntel'
            vendor = 'Apple Computer, Inc.'
            plugins_count = get_config_value('plugins_length', 5)
            remove_connection = False
            platform_version = get_config_value('platform_version', '10_15_7')
            architecture = get_config_value('architecture', 'x86_64')
            model = get_config_value('model', 'MacBookPro')
        else:
            platform = 'Win32'
            vendor = 'Google Inc.'
            plugins_count = get_config_value('plugins_length', 5)
            remove_connection = False
            platform_version = get_config_value('platform_version', '10.0')
            architecture = get_config_value('architecture', 'x64')
            model = get_config_value('model', 'Windows')
        
        # Screen dimensions
        sw = get_config_value('screen_width', 360 if is_mobile else 1920)
        sh = get_config_value('screen_height', 800 if is_mobile else 1080)
        vw = get_config_value('viewport_width', 360 if is_mobile else 1920)
        vh = get_config_value('viewport_height', 727 if is_mobile else 940)
        
        # ========== CHOOSE THE REFERRER STRATEGICALLY ==========
        # If custom_referer is explicitly passed, use it. Otherwise, fallback to config.
        if custom_referer is not None:
            referrer = custom_referer
        else:
            referrer = get_config_value('referer', '')
        
        is_mobile_str = 'true' if is_mobile else 'false'
        remove_connection_str = 'true' if remove_connection else 'false'

        # ========== BUILD MOCK PLUGINS (Desktop) ==========
        if not is_mobile:
            # Real plugin names that appear in actual Chrome browsers
            real_plugins = [
                {"name": "Chrome PDF Viewer", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
                {"name": "Chromium PDF Viewer", "filename": "internal-pdf-viewer", "description": ""},
                {"name": "Google Talk Plugin", "filename": "googletalkplugin.dll", "description": "Google Talk Plugin"},
                {"name": "Google Update", "filename": "npGoogleUpdate3.dll", "description": "Google Update"},
                {"name": "Widevine Content Decryption Module", "filename": "widevinecdmadapter.dll", "description": "Widevine Content Decryption Module"},
                {"name": "Native Client", "filename": "internal-nacl-plugin", "description": "Native Client"},
            ]
            
            # Limit to plugins_count
            plugins_list = real_plugins[:plugins_count]
            
            # Build the JavaScript code dynamically
            import json
            mock_plugins_code = f"""
                const realPlugins = {json.dumps(plugins_list)};
                const mockPlugins = realPlugins.slice(0);
                mockPlugins.length = {plugins_count};  // ✅ Fixed
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

        # ========== UNIVERSAL STEALTH SCRIPT ==========
        universal_script = f"""
        (function() {{
            console.log('🔍 [STEALTH] Securing universal prototype modifications...');
            
            const shieldProperty = (obj, prop, value) => {{
                try {{
                    Object.defineProperty(obj, prop, {{
                        get: function() {{ return value; }},
                        configurable: true,
                        enumerable: true
                    }});
                }} catch (e) {{
                    console.warn('⚠️ Property shield failed for: ' + prop, e);
                }}
            }};

            // Apply to main Navigator prototype
            shieldProperty(Navigator.prototype, 'platform', '{platform}');
            shieldProperty(Navigator.prototype, 'vendor', '{vendor}');
            shieldProperty(Navigator.prototype, 'webdriver', false);
            
            {mock_plugins_code}
            shieldProperty(Navigator.prototype, 'plugins', mockPlugins);
            
            if ({is_mobile_str}) {{
                const emptyMimeTypes = [];
                emptyMimeTypes.item = () => null;
                emptyMimeTypes.namedItem = () => null;
                shieldProperty(Navigator.prototype, 'mimeTypes', emptyMimeTypes);
            }} else {{
                const emptyMimeTypes = [];
                emptyMimeTypes.length = 0;
                emptyMimeTypes.item = () => null;
                emptyMimeTypes.namedItem = () => null;
                shieldProperty(Navigator.prototype, 'mimeTypes', emptyMimeTypes);
            }}
            
            shieldProperty(Screen.prototype, 'width', {sw});
            shieldProperty(Screen.prototype, 'height', {sh});
            shieldProperty(Screen.prototype, 'availWidth', {sw});
            shieldProperty(Screen.prototype, 'availHeight', {sh});
            
            shieldProperty(window, 'innerWidth', {vw});
            shieldProperty(window, 'innerHeight', {vh});
            shieldProperty(window, 'outerWidth', {sw});
            shieldProperty(window, 'outerHeight', {sh});
            
            if ({remove_connection_str}) {{
                try {{ delete Navigator.prototype.connection; }} catch(e) {{}}
                shieldProperty(Navigator.prototype, 'connection', undefined);
            }}
            
            // ========== REFERRER LOCKING ==========
            const referrer = '{referrer}';
            if (referrer) {{
                try {{
                    Object.defineProperty(Document.prototype, 'referrer', {{
                        get: function() {{ return referrer; }},
                        configurable: true,
                        enumerable: true
                    }});
                }} catch(e) {{
                    console.warn('⚠️ Referrer shield failed: ' + e);
                }}
            }}
            
            // ========== FINGERPRINT PERSISTENCE HEARTBEAT ==========
            // This ensures fingerprint values survive background interactions
            // and cannot be changed by YouTube's internal scripts
            const expectedVendor = '{vendor}';
            const expectedPlatform = '{platform}';
            
            // Override the getter to always return our values, even if someone tries to redefine
            Object.defineProperty(Navigator.prototype, 'vendor', {{
                get: function() {{ return expectedVendor; }},
                set: function() {{ /* ignore attempts to change */ }},
                configurable: false,
                enumerable: true
            }});
            
            Object.defineProperty(Navigator.prototype, 'platform', {{
                get: function() {{ return expectedPlatform; }},
                set: function() {{ /* ignore attempts to change */ }},
                configurable: false,
                enumerable: true
            }});
            
            // Set up a heartbeat interval to re-apply if anything changes
            // This runs every 5 seconds to ensure consistency
            setInterval(function() {{
                try {{
                    // Quick check to see if values are still correct
                    if (navigator.vendor !== expectedVendor || navigator.platform !== expectedPlatform) {{
                        console.warn('⚠️ [STEALTH] Fingerprint drift detected, re-applying...');
                        // Re-apply using the same shieldProperty logic
                        Object.defineProperty(Navigator.prototype, 'vendor', {{
                            get: function() {{ return expectedVendor; }},
                            set: function() {{ }},
                            configurable: false,
                            enumerable: true
                        }});
                        Object.defineProperty(Navigator.prototype, 'platform', {{
                            get: function() {{ return expectedPlatform; }},
                            set: function() {{ }},
                            configurable: false,
                            enumerable: true
                        }});
                        // Also check and re-apply plugins if needed
                        if (navigator.plugins.length !== {plugins_count}) {{
                            // Re-apply plugins (the mockPlugins variable is still in scope)
                            {mock_plugins_code}
                            Object.defineProperty(Navigator.prototype, 'plugins', {{
                                get: function() {{ return mockPlugins; }},
                                set: function() {{ }},
                                configurable: false,
                                enumerable: true
                            }});
                        }}
                    }}
                }} catch(e) {{
                    // Silently handle errors in heartbeat
                }}
            }}, 5000);
            
            console.log('✅ Hardened universal fingerprint definitions applied successfully with persistence heartbeat.');
            console.log('📱 [HEARTBEAT] Vendor: {vendor}, Platform: {platform}, Plugins: {plugins_count}');
        }})();
        """

        # ========== REGISTER SCRIPT WITH CDP ==========
        has_cdp = False
        
        cdp_payload = {
            "method": "Page.addScriptToEvaluateOnNewDocument",
            "params": {"source": universal_script}
        }
        
        if hasattr(tab, '_connection_handler') and tab._connection_handler:
            await tab._connection_handler.execute_command(cdp_payload)
            has_cdp = True
            if _script_logger:
                _script_logger.info(f"Instance {instance_id}: [STEALTH] ✅ CDP hook via _connection_handler")
        
        elif hasattr(tab, 'connection') and hasattr(tab.connection, 'send'):
            await tab.connection.send(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": universal_script}
            )
            has_cdp = True
            if _script_logger:
                _script_logger.info(f"Instance {instance_id}: [STEALTH] ✅ CDP hook via connection.send")

        if has_cdp and _script_logger:
            _script_logger.info(f"Instance {instance_id}: [STEALTH] ✅ Universal fingerprint registered (survives refreshes)")

        # ========== SET REFERRER VIA CDP HEADERS (Persistent across navigation) ==========
        if referrer:
            try:
                # Get CDP client - use _connection_handler
                cdp = None
                if hasattr(tab, '_connection_handler') and tab._connection_handler:
                    cdp = tab._connection_handler
                elif hasattr(tab, 'connection') and hasattr(tab.connection, 'send'):
                    cdp = tab.connection
                
                if cdp:
                    # Use the correct CDP payload format for execute_command
                    cdp_header_payload = {
                        "method": "Network.setExtraHTTPHeaders",
                        "params": {
                            "headers": {
                                "Referer": referrer
                            }
                        }
                    }
                    
                    # If using _connection_handler, use execute_command
                    if hasattr(cdp, 'execute_command'):
                        await cdp.execute_command(cdp_header_payload)
                    # If using connection.send, use send
                    elif hasattr(cdp, 'send'):
                        await cdp.send("Network.setExtraHTTPHeaders", {
                            "headers": {
                                "Referer": referrer
                            }
                        })
                    
                    if _script_logger:
                        _script_logger.info(f"Instance {instance_id}: [STEALTH] ✅ Referrer set via CDP headers: {referrer}")
            except Exception as e:
                if _script_logger:
                    _script_logger.warning(f"Instance {instance_id}: [STEALTH] ⚠️ CDP header referrer failed: {e}")

        # ========== IMMEDIATE EXECUTION FALLBACK ==========
        await tab.execute_script(universal_script)
        return True

    except Exception as e:
        if _script_logger:
            _script_logger.error(f"Instance {instance_id}: [FINGERPRINT OVERRIDE FAILURE]: {e}")
        return False




async def maintain_fingerprint_heartbeat(tab, cfg, instance_id: int):
    """
    Periodically verify fingerprint consistency during watch.
    This prevents drift during background interactions and ensures
    native token validation passes at the 40-60 second mark.
    """
    if not _script_logger:
        return
    
    try:
        # Get current values from browser
        vendor_result = await tab.execute_script("return navigator.vendor;")
        platform_result = await tab.execute_script("return navigator.platform;")
        plugins_result = await tab.execute_script("return navigator.plugins.length;")
        
        # Unpack CDP responses
        if isinstance(vendor_result, dict):
            current_vendor = vendor_result.get('result', {}).get('result', {}).get('value', '')
        else:
            current_vendor = vendor_result
        
        if isinstance(platform_result, dict):
            current_platform = platform_result.get('result', {}).get('result', {}).get('value', '')
        else:
            current_platform = platform_result
        
        if isinstance(plugins_result, dict):
            current_plugins = plugins_result.get('result', {}).get('result', {}).get('value', -1)
        else:
            current_plugins = plugins_result
        
        # Expected values from config
        expected_vendor = getattr(cfg, 'vendor', 'Google Inc.')
        expected_platform = getattr(cfg, 'platform', 'Win32')
        expected_plugins = getattr(cfg, 'plugins_length', 5)
        
        # Check for drift
        drift_detected = False
        
        if current_vendor != expected_vendor:
            if _script_logger:
                _script_logger.warning(f"Instance {instance_id}: [FINGERPRINT] Vendor drift detected: {current_vendor} != {expected_vendor}")
            drift_detected = True
        
        if current_platform != expected_platform:
            if _script_logger:
                _script_logger.warning(f"Instance {instance_id}: [FINGERPRINT] Platform drift detected: {current_platform} != {expected_platform}")
            drift_detected = True
        
        if current_plugins != expected_plugins:
            if _script_logger:
                _script_logger.warning(f"Instance {instance_id}: [FINGERPRINT] Plugins length drift detected: {current_plugins} != {expected_plugins}")
            drift_detected = True
        
        # If drift detected, re-apply fingerprint
        if drift_detected:
            if _script_logger:
                _script_logger.info(f"Instance {instance_id}: [FINGERPRINT] Re-applying fingerprint to fix drift...")
            
            # Re-apply fingerprint with current referrer
            referrer = getattr(cfg, 'referer', '')
            await apply_fingerprint_overrides(tab, cfg, instance_id, custom_referer=referrer)
            
            # Also re-apply via immediate execution
            await tab.execute_script("""
                // Force re-apply of vendor and platform
                Object.defineProperty(Navigator.prototype, 'vendor', {
                    get: function() { return '%s'; },
                    set: function() {},
                    configurable: false,
                    enumerable: true
                });
                Object.defineProperty(Navigator.prototype, 'platform', {
                    get: function() { return '%s'; },
                    set: function() {},
                    configurable: false,
                    enumerable: true
                });
            """ % (expected_vendor, expected_platform))
            
            if _script_logger:
                _script_logger.info(f"Instance {instance_id}: [FINGERPRINT] ✅ Fingerprint restored")
        else:
            if _script_logger:
                _script_logger.debug(f"Instance {instance_id}: [FINGERPRINT] ✅ Fingerprint consistent")
            
    except Exception as e:
        if _script_logger:
            _script_logger.debug(f"Instance {instance_id}: [FINGERPRINT] Heartbeat check failed: {e}")




async def start_fingerprint_heartbeat(tab, cfg, instance_id: int, interval: int = 15):
    """
    Start a background task that periodically checks fingerprint consistency.
    This runs in the background during watch sessions.
    
    Args:
        tab: Pydoll tab instance
        cfg: SessionConfig object
        instance_id: Instance ID for logging
        interval: Seconds between checks (default 15)
    """
    if not _script_logger:
        return
    
    try:
        if _script_logger:
            _script_logger.info(f"Instance {instance_id}: [HEARTBEAT] Starting fingerprint heartbeat (interval: {interval}s)")
        
        # Run a single check immediately
        await maintain_fingerprint_heartbeat(tab, cfg, instance_id)
        
        # Start background loop
        while True:
            await asyncio.sleep(interval)
            await maintain_fingerprint_heartbeat(tab, cfg, instance_id)
            
    except asyncio.CancelledError:
        if _script_logger:
            _script_logger.info(f"Instance {instance_id}: [HEARTBEAT] Fingerprint heartbeat stopped")
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"Instance {instance_id}: [HEARTBEAT] Error in heartbeat loop: {e}")



def stop_fingerprint_heartbeat(heartbeat_task):
    """
    Stop the fingerprint heartbeat background task.
    
    Args:
        heartbeat_task: The asyncio task returned by start_fingerprint_heartbeat
    """
    if heartbeat_task and not heartbeat_task.done():
        heartbeat_task.cancel()



async def create_driver_with_po_token_pydoll(cfg, profile_prefix: str = "yt_pydoll_cache"):
    """
    Create Pydoll browser with fingerprint support.
    """
    if not PYDOLL_AVAILABLE:
        raise ImportError("Pydoll is not available. Install: pip install pydoll-python")

    if _script_logger:
        _script_logger.info(f"Instance {cfg.instance_id}: 🚀 Starting Pydoll browser...")
        _script_logger.info(f"Instance {cfg.instance_id}: 📱 Platform: {cfg.platform}")
        _script_logger.info(f"Instance {cfg.instance_id}: 📱 Device: {cfg.device_category}")
        _script_logger.info(f"Instance {cfg.instance_id}: 🔌 Proxy Mode: {cfg.proxy_mode}")

    try:
        options = ChromiumOptions()
        # ========== CORS & SECURITY FLAGS (For InnerTube Tracking) ==========
        # These prevent Chrome from blocking YouTube's internal tracking requests
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--disable-site-isolation-trials")
        
        # ========== PREVENT BACKGROUND THROTTLING (Fixes 40-60s error) ==========
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-features=CalculateNativeWinOcclusion")
        

        # ========== LAYER 1: NATIVE ENGINE SWITCHES (Injected at Launch) ==========
        # These prevent the "Frankenstein profile" on refresh by setting values
        # at the binary level BEFORE any JavaScript runs.
        
        # 1. User Agent (Native)
        if cfg.user_agent:
            options.add_argument(f'--user-agent={cfg.user_agent}')
        
        # 2. Viewport / Window Size (Native)
        if cfg.viewport_width and cfg.viewport_height:
            options.add_argument(f'--window-size={cfg.viewport_width},{cfg.viewport_height}')
        
        # 3. Disable Automation Detection (Native)
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # 4. Mobile-specific native flags
        if cfg.force_mobile or cfg.device_category == 'mobile':
            options.add_argument('--touch-events=enabled')
            options.add_argument('--force-device-scale-factor=2')
            # Disable desktop plugin discovery at engine level
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-extensions')
        
        # 5. Headless (if enabled)
        if cfg.headless:
            options.add_argument('--headless=new')

        # 6. Proxy Setup (unchanged)
        proxy_url, proxy_extra_args = _get_proxy_config(cfg)
        if proxy_url:
            proxy_args = [f'--proxy-server={proxy_url}']
            if 'http://' in proxy_url:
                proxy_args.append('--proxy-bypass-list=<-loopback>')
            if proxy_extra_args:
                proxy_args.extend(proxy_extra_args)
            for arg in proxy_args:
                options.add_argument(arg)

        # Launch
        chrome = Chrome(options=options)
        tab = await chrome.start()

        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: ✅ Browser launched")

        # Apply fingerprint overrides with clean referrer for initial boot
        await apply_fingerprint_overrides(tab, cfg, cfg.instance_id, custom_referer="")

        # Store PO token
        if cfg.po_token:
            tab._po_token = cfg.po_token
            if _script_logger:
                _script_logger.info(f"Instance {cfg.instance_id}: ✅ PO token stored")

        # Verification
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

                conn = await tab.execute_script("return navigator.connection;")
                if isinstance(conn, dict):
                    conn = conn.get('result', {}).get('result', {}).get('value', 'undefined')
                _script_logger.info(f"Instance {cfg.instance_id}: [VERIFY] Connection: {'undefined' if conn is None or conn == 'undefined' else 'PRESENT (BAD)'}")

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

        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: ✅ Pydoll driver ready")

        # Get the profile directory from the browser options
        profile_dir = None
        try:
            # Try to get the profile directory from the browser instance
            if hasattr(chrome, 'options') and hasattr(chrome.options, 'arguments'):
                for arg in chrome.options.arguments:
                    if arg.startswith('--user-data-dir='):
                        profile_dir = arg.split('=', 1)[1]
                        break
            # If not found, try from cfg
            if not profile_dir and hasattr(cfg, '_profile_dir'):
                profile_dir = cfg._profile_dir
        except:
            pass

        if _script_logger and profile_dir:
            _script_logger.info(f"Instance {cfg.instance_id}: 📁 Profile directory: {profile_dir}")

        # Create a starter function for the heartbeat
        async def start_heartbeat(interval: int = 15):
            """Start the fingerprint heartbeat background task."""
            return await start_fingerprint_heartbeat(tab, cfg, cfg.instance_id, interval)

        # Store heartbeat starter in tab for later use
        tab._start_heartbeat = start_heartbeat
        tab._cfg = cfg
        tab._instance_id = cfg.instance_id

        if _script_logger:
            _script_logger.info(f"Instance {cfg.instance_id}: ✅ Fingerprint heartbeat available")

        return chrome, tab, profile_dir

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
    'PYDOLL_AVAILABLE',
    'cleanup_all_browsers',
    'register_cleanup_handlers',
    'kill_child_processes',
    'maintain_fingerprint_heartbeat',
    'start_fingerprint_heartbeat',
    'stop_fingerprint_heartbeat'
]