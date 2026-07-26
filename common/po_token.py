#!/usr/bin/env python3
"""
Shared PO Token utilities for ALL automation scripts (Selenium & Playwright)
This is the SINGLE source of truth for PO token generation.
Supports three sources:
1. Native Browser - YouTube generates token via embedded player
2. External Server - bgutil on port 4416
3. po-token-generator - Node.js service on port 4417
"""

import sys
import os
import requests
import logging
import time
import random as rand
import asyncio
from pathlib import Path

# Ensure project root is in path for any imports from this module
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_script_logger = None
_po_token_source = 'native'  # Default to native

def set_logger(logger):
    """Set the logger for this module"""
    global _script_logger
    _script_logger = logger

def set_po_token_source(source):
    """Set the PO token source to use (native, external, potgen)"""
    global _po_token_source
    _po_token_source = source
    if _script_logger:
        _script_logger.info(f"[PO_TOKEN] Source set to: {source}")


# ========== VISITOR COOKIE GENERATION (HTTP Method - No Browser) ==========

def warmup_youtube_session(video_id: str = None, proxy_url: str = None, fingerprint: dict = None) -> Optional[str]:
    """
    Generate VISITOR_INFO1_LIVE cookie using HTTP request (no browser).
    Uses fingerprint details to ensure cookie matches browser profile.
    
    Args:
        video_id: Optional video ID for embed URL
        proxy_url: Optional proxy URL for the request
        fingerprint: Dictionary containing userAgent, platform, screen, etc.
    
    Returns:
        str: VISITOR_INFO1_LIVE cookie value or None
    """
    try:
        if _script_logger:
            _script_logger.info("[COOKIE] Warming up YouTube session to generate VISITOR_INFO1_LIVE...")
        
        # Extract fingerprint values or use defaults
        user_agent = fingerprint.get('userAgent') if fingerprint else None
        platform = fingerprint.get('platform') if fingerprint else None
        screen_width = fingerprint.get('screenWidth') if fingerprint else None
        screen_height = fingerprint.get('screenHeight') if fingerprint else None
        
        # Build headers matching the fingerprint
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive"
        }
        
        # Use fingerprint's user agent if available
        if user_agent:
            headers["User-Agent"] = user_agent
            if _script_logger:
                _script_logger.info(f"[COOKIE] Using fingerprint User-Agent: {user_agent[:50]}...")
        else:
            headers["User-Agent"] = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            if _script_logger:
                _script_logger.warning("[COOKIE] No User-Agent in fingerprint, using fallback")
        
        # Add platform to headers if available
        if platform:
            headers["Sec-CH-UA-Platform"] = platform
            headers["Sec-CH-UA"] = f'"{platform}"'
            if _script_logger:
                _script_logger.info(f"[COOKIE] Using fingerprint Platform: {platform}")
        
        # Add viewport/screen hints if available
        if screen_width and screen_height:
            headers["Viewport-Width"] = str(screen_width)
            headers["Sec-CH-UA-Viewport-Width"] = str(screen_width)
        
        # Use embed URL to force tracking layer to wake up
        embed_id = video_id if video_id else "dQw4w9WgXcQ"
        url = f"https://www.youtube.com/embed/{embed_id}"
        
        if _script_logger:
            _script_logger.info(f"[COOKIE] Sending handshake to: {url}")
        
        # Configure proxy if provided
        proxies = None
        if proxy_url:
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            if _script_logger:
                _script_logger.info(f"[COOKIE] Using proxy: {proxy_url}")
        
        # Use session to handle cookies
        session = requests.Session()
        if proxies:
            session.proxies.update(proxies)
        
        # Send request with fingerprint headers
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # Method 1: Check for cookie in session
            if 'VISITOR_INFO1_LIVE' in session.cookies:
                visitor_cookie = session.cookies['VISITOR_INFO1_LIVE']
                if _script_logger:
                    _script_logger.info(f"[COOKIE] ✅ VISITOR_INFO1_LIVE found: {visitor_cookie[:30]}...")
                return visitor_cookie
            
            # Method 2: Extract visitorData from HTML (yt-dlp method)
            import re
            visitor_data_match = re.search(r'"visitorData":"([^"]+)"', response.text)
            if visitor_data_match:
                extracted_token = visitor_data_match.group(1)
                if _script_logger:
                    _script_logger.info(f"[COOKIE] ✅ visitorData extracted: {extracted_token[:30]}...")
                return extracted_token
            
            if _script_logger:
                _script_logger.warning("[COOKIE] ⚠️ No visitor cookie or data found in response")
        else:
            if _script_logger:
                _script_logger.warning(f"[COOKIE] ❌ Handshake failed. Status: {response.status_code}")
                
    except requests.exceptions.ConnectionError:
        if _script_logger:
            _script_logger.warning("[COOKIE] ❌ Connection error - network issue")
    except requests.exceptions.Timeout:
        if _script_logger:
            _script_logger.warning("[COOKIE] ❌ Timeout - server too slow")
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"[COOKIE] ❌ Error: {e}")
    
    return None


def get_visitor_data(video_id: str = None, proxy_url: str = None, fingerprint: dict = None) -> Optional[str]:
    """
    Wrapper for warmup_youtube_session to get VISITOR_INFO1_LIVE or visitorData.
    Pass fingerprint dictionary to ensure cookie matches browser profile.
    """
    return warmup_youtube_session(video_id, proxy_url, fingerprint)


def get_po_token_from_potgen(video_id, instance_id):
    """Get PO token from po-token-generator service (port 4417)"""
    start_time = time.time()
    try:
        if _script_logger:
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Trying po-token-generator on port 4417...")
        
        response = requests.post(
            "http://127.0.0.1:4417/get_token",
            json={"videoId": video_id},
            timeout=15
        )
        elapsed = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            po_token = data.get('poToken')
            visitor_id = data.get('visitorData')
            if po_token and _script_logger:
                _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: SUCCESS - Token received from po-token-generator (port 4417) - {elapsed:.0f}ms - Length: {len(po_token)}")
                if visitor_id:
                    _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: Visitor ID: {visitor_id[:30]}...")
            return po_token, visitor_id
        else:
            if _script_logger:
                _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: po-token-generator returned HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        if _script_logger:
            _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: FAILED - po-token-generator NOT running on port 4417")
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Start with: node token_service.js")
    except requests.exceptions.Timeout:
        if _script_logger:
            _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: FAILED - po-token-generator timeout after 30s")
    except Exception as e:
        if _script_logger:
            _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: Error - {e}")
    return None, None


def get_po_token_from_external(video_id, instance_id, proxy_url=None):
    """Get PO token from external bgutil server (port 4416) with optional proxy."""
    start_time = time.time()
    try:
        if _script_logger:
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Trying external server on port 4416...")
            if proxy_url:
                _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using proxy: {proxy_url}")
        
        # Configure proxy if provided
        proxies = None
        if proxy_url:
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        
        response = requests.post(
            "http://127.0.0.1:4416/get_pot",
            json={"video_id": video_id},
            timeout=15,
            proxies=proxies
        )
        elapsed = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            po_token = data.get('poToken')
            visitor_id = data.get('visitorId')
            if po_token and _script_logger:
                _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: SUCCESS - Token received - {elapsed:.0f}ms - Length: {len(po_token)}")
                if visitor_id:
                    _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: Visitor ID: {visitor_id[:30]}...")
            return po_token, visitor_id
        else:
            if _script_logger:
                _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: External server returned HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        if _script_logger:
            _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: FAILED - External server NOT running on port 4416")
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Start with: node build/main.js --port 4416")
    except requests.exceptions.Timeout:
        if _script_logger:
            _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: FAILED - External server timeout after 15s")
    except Exception as e:
        if _script_logger:
            _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: Error - {e}")
    return None, None



def get_po_token(video_id, instance_id, proxy_url=None):
    """
    Fetch PO token based on the configured source.
    Supports: native, external, potgen, wpc
    """
    global _po_token_source
    
    if not video_id:
        if _script_logger:
            _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: No video_id, skipping")
        return None, None

    if _script_logger:
        if _po_token_source == 'wpc':
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using source: yt-dlp-getpot-wpc")
        elif _po_token_source == 'potgen':
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using source: po-token-generator (port 4417)")
        elif _po_token_source == 'external':
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using source: External Server (port 4416)")
        else:
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using source: Native Browser")
    
    if _po_token_source == 'wpc':
        return get_po_token_from_wpc(video_id, instance_id, proxy_url)
    elif _po_token_source == 'potgen':
        return get_po_token_from_potgen(video_id, instance_id)
    elif _po_token_source == 'external':
        return get_po_token_from_external(video_id, instance_id, proxy_url)
    else:  # native
        if _script_logger:
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Native mode - token will be generated by browser")
        return None, None


def add_po_token_to_url(url, po_token):
    """Add PO token parameter to URL if available"""
    if not po_token:
        return url
    separator = '&' if '?' in url else '?'
    return f"{url}{separator}pot={po_token}"


# ========== SELENIUM VERSIONS (Synchronous) ==========

def inject_visitor_cookie(driver, instance_id, visitor_id):
    """Inject VISITOR_INFO1_LIVE cookie into the Selenium driver"""
    if not visitor_id:
        return False
    
    try:
        driver.get("https://www.youtube.com/robots.txt")
        driver.add_cookie({
            'name': 'VISITOR_INFO1_LIVE',
            'value': visitor_id,
            'domain': '.youtube.com',
            'path': '/'
        })
        if _script_logger:
            _script_logger.info(f"[COOKIE] Instance {instance_id}: Injected VISITOR_INFO1_LIVE cookie")
        return True
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"[COOKIE] Instance {instance_id}: Failed to inject cookie - {e}")
        return False


def warmup_youtube_embed(driver, instance_id):
    """
    Load an embedded YouTube player to trigger native BotGuard challenge.
    Selenium version - synchronous.
    """
    try:
        embed_urls = [
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/9bZkp7q19f0",
            "https://www.youtube.com/embed/5qap5aO4i9A",
        ]
        embed_url = rand.choice(embed_urls)
        
        if _script_logger:
            _script_logger.info(f"[NATIVE] Instance {instance_id}: Loading embedded player for token generation")
        
        driver.get(embed_url)
        time.sleep(rand.uniform(5, 8))
        
        # Extract visitor cookie
        cookies = driver.get_cookies()
        for cookie in cookies:
            if cookie.get('name') == 'VISITOR_INFO1_LIVE':
                visitor_id = cookie.get('value')
                if _script_logger:
                    _script_logger.info(f"[NATIVE] Instance {instance_id}: SUCCESS - Native token generated! Visitor ID: {visitor_id[:30]}...")
                return visitor_id
        
        if _script_logger:
            _script_logger.warning(f"[NATIVE] Instance {instance_id}: FAILED - VISITOR_INFO1_LIVE cookie not found")
        return None
        
    except Exception as e:
        if _script_logger:
            _script_logger.warning(f"[NATIVE] Instance {instance_id}: Failed - {e}")
        return None


# ========== PYDOLL VERSIONS (Asynchronous) ==========



def get_po_token_from_wpc(video_id, instance_id, proxy_url=None):
    """Get PO token from yt-dlp-getpot-wpc service."""
    start_time = time.time()
    try:
        if _script_logger:
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Trying yt-dlp-getpot-wpc...")
            if proxy_url:
                _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using proxy: {proxy_url}")
        
        # Configure proxy if provided
        proxies = None
        if proxy_url:
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        
        # yt-dlp-getpot-wpc runs on port 4418 (or configurable)
        response = requests.post(
            "http://127.0.0.1:4418/get_pot",
            json={"video_id": video_id},
            timeout=30,
            proxies=proxies
        )
        elapsed = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            po_token = data.get('poToken')
            visitor_id = data.get('visitorData')
            if po_token and _script_logger:
                _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: SUCCESS - WPC token received - {elapsed:.0f}ms - Length: {len(po_token)}")
                if visitor_id:
                    _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: Visitor ID: {visitor_id[:30]}...")
            return po_token, visitor_id
        else:
            if _script_logger:
                _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: WPC returned HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        if _script_logger:
            _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: FAILED - WPC not running on port 4418")
    except Exception as e:
        if _script_logger:
            _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: Error - {e}")
    return None, None


# Export public functions
__all__ = [
    'set_logger',
    'set_po_token_source',
    'get_po_token',
    'get_po_token_from_external',
    'get_po_token_from_potgen',
    'add_po_token_to_url',
    'inject_visitor_cookie',
    'warmup_youtube_embed',
    'warmup_youtube_session',  # ✅ ADD
    'get_visitor_data',        # ✅ ADD
    'get_po_token_from_wpc',
]