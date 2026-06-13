# common/socks_to_http.py
"""
Universal SOCKS to HTTP Proxy Converter - UPDATED
Now uses a standalone bridge server that runs independently.
"""

import socket
import subprocess
import time
import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Track bridge processes
_bridge_processes = {}


def start_bridge_server(tor_port=9050, http_port=8888, wait=True):
    """
    Start the SOCKS bridge as a separate subprocess.
    Returns True if bridge is running.
    """
    global _bridge_processes
    
    bridge_key = f"{tor_port}_{http_port}"
    
    # Check if already running
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(1)
        result = test_sock.connect_ex(('127.0.0.1', http_port))
        test_sock.close()
        if result == 0:
            return True
    except:
        pass
    
    # Start new bridge process
    try:
        script_path = Path(__file__).parent / "socks_bridge_server.py"
        if not script_path.exists():
            logger.warning(f"Bridge server not found at {script_path}")
            return False
        
        if sys.platform == "win32":
            proc = subprocess.Popen(
                [sys.executable, str(script_path), '--port', str(tor_port), '--http-port', str(http_port)],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, str(script_path), '--port', str(tor_port), '--http-port', str(http_port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        
        _bridge_processes[bridge_key] = proc
        
        if wait:
            time.sleep(2)
        
        # Verify it's running
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(1)
        result = test_sock.connect_ex(('127.0.0.1', http_port))
        test_sock.close()
        
        return result == 0
        
    except Exception as e:
        logger.error(f"Failed to start bridge server: {e}")
        return False


def stop_bridge_server(tor_port=9050, http_port=8888):
    """Stop the bridge server"""
    global _bridge_processes
    
    bridge_key = f"{tor_port}_{http_port}"
    
    if bridge_key in _bridge_processes:
        try:
            _bridge_processes[bridge_key].terminate()
            _bridge_processes[bridge_key].wait(timeout=3)
        except:
            try:
                _bridge_processes[bridge_key].kill()
            except:
                pass
        del _bridge_processes[bridge_key]


def get_http_proxy_for_socks(socks_url, force_new=False):
    """
    Get an HTTP proxy URL for a SOCKS proxy.
    Starts a bridge server if needed.
    """
    if not socks_url or 'socks' not in socks_url.lower():
        return socks_url
    
    # Parse SOCKS URL
    try:
        protocol = socks_url.split('://')[0]
        rest = socks_url.split('://')[1]
        
        if '@' in rest:
            rest = rest.split('@')[1]
        
        host, port = rest.split(':')
        port = int(port)
    except:
        return socks_url
    
    # For Tor (127.0.0.1), start a bridge server
    if host == '127.0.0.1' and port in [9050, 9150]:
        http_port = 8888 if port == 9050 else 8889
        
        if start_bridge_server(tor_port=port, http_port=http_port):
            return f"http://127.0.0.1:{http_port}"
    
    # For remote SOCKS proxies, can't bridge easily - return as-is
    return socks_url


def start_tor_bridge(tor_port=9050, http_port=8888):
    """Start a bridge for Tor (convenience function)"""
    if start_bridge_server(tor_port, http_port):
        return f"http://127.0.0.1:{http_port}"
    return None


def is_socks_proxy(proxy_url):
    """Check if a proxy URL is a SOCKS proxy"""
    if not proxy_url or '://' not in proxy_url:
        return False
    protocol = proxy_url.split('://')[0].lower()
    return protocol in ['socks4', 'socks5']


# Cleanup function (optional - bridges will be terminated when parent exits)
def cleanup_all_bridges():
    global _bridge_processes
    for key, proc in _bridge_processes.items():
        try:
            proc.terminate()
        except:
            pass
    _bridge_processes.clear()


# Register cleanup
import atexit
atexit.register(cleanup_all_bridges)