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


def get_po_token_from_potgen(video_id, instance_id):
    """Get PO token from po-token-generator service (port 4417)"""
    start_time = time.time()
    try:
        if _script_logger:
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Trying po-token-generator on port 4417...")
        
        response = requests.post(
            "http://127.0.0.1:4417/get_token",
            json={"videoId": video_id},
            timeout=30
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


def get_po_token_from_external(video_id, instance_id):
    """Get PO token from external bgutil server (port 4416)"""
    start_time = time.time()
    try:
        if _script_logger:
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Trying external server on port 4416...")
        
        response = requests.post(
            "http://127.0.0.1:4416/get_pot",
            json={"video_id": video_id},
            timeout=15
        )
        elapsed = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            po_token = data.get('poToken')
            visitor_id = data.get('visitorId')
            if po_token and _script_logger:
                _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: SUCCESS - Token received from external server (port 4416) - {elapsed:.0f}ms - Length: {len(po_token)}")
            return po_token, visitor_id
    except requests.exceptions.ConnectionError:
        if _script_logger:
            _script_logger.warning(f"[PO_TOKEN] Instance {instance_id}: FAILED - External server NOT running on port 4416")
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Start with: node build/main.js --port 4416")
    except Exception as e:
        if _script_logger:
            _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: Error - {e}")
    return None, None


def get_po_token(video_id, instance_id):
    """
    Fetch PO token based on the configured source.
    Returns (po_token, visitor_id) tuple.
    """
    global _po_token_source
    
    if not video_id:
        if _script_logger:
            _script_logger.debug(f"[PO_TOKEN] Instance {instance_id}: No video_id, skipping")
        return None, None

    if _script_logger:
        if _po_token_source == 'potgen':
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using source: po-token-generator (port 4417)")
        elif _po_token_source == 'external':
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using source: External Server (port 4416)")
        else:
            _script_logger.info(f"[PO_TOKEN] Instance {instance_id}: Using source: Native Browser (no external server)")
    
    if _po_token_source == 'potgen':
        return get_po_token_from_potgen(video_id, instance_id)
    elif _po_token_source == 'external':
        return get_po_token_from_external(video_id, instance_id)
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


def inject_visitor_cookie(driver, instance_id, visitor_id):
    """Inject VISITOR_INFO1_LIVE cookie into the driver"""
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
    This lets YouTube's JavaScript generate a PO token naturally.
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