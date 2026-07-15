#!/usr/bin/env python3
"""
Pydoll-specific Shared Utilities
Async-first utilities for Pydoll automation.
"""

import os
import re
import json
import random
import logging
import asyncio
import subprocess
import unicodedata
from time import sleep, time
from typing import Optional, Tuple, List, Dict, Any, Union

# Try to import psutil for RAM monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)


# ============================================================================
# USER AGENT DATABASES (Shared with Selenium)
# ============================================================================

DESKTOP_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

MOBILE_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6301.2 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
]

# Screen resolutions
DESKTOP_RESOLUTIONS = [(1366, 768), (1920, 1080), (1536, 864), (1440, 900), (1280, 720)]
MOBILE_RESOLUTIONS = [(375, 667), (390, 844), (393, 852), (412, 915), (360, 800)]


# ============================================================================
# URL & VIDEO ID FUNCTIONS
# ============================================================================

def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'm\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def construct_watch_url(video_id: str, use_short_link: bool = False) -> str:
    """Construct a watch URL from video ID."""
    if use_short_link:
        return f"https://youtu.be/{video_id}"
    return f"https://www.youtube.com/watch?v={video_id}"


def get_video_title(video_url: str) -> Optional[str]:
    """Fetch video title using yt-dlp."""
    try:
        import yt_dlp
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get('title')
    except Exception:
        return None


def sanitize_text(text: str) -> str:
    """Remove emoji and non-BMP characters."""
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ============================================================================
# USER AGENT FUNCTIONS
# ============================================================================

def get_random_user_agent(force_mobile: bool = None) -> Tuple[str, bool]:
    """Get random user agent based on force_mobile flag."""
    if force_mobile is True:
        return random.choice(MOBILE_AGENTS), True
    elif force_mobile is False:
        return random.choice(DESKTOP_AGENTS), False
    else:
        if random.random() < 0.5:
            return random.choice(DESKTOP_AGENTS), False
        return random.choice(MOBILE_AGENTS), True


def get_random_resolution(is_mobile: bool) -> Tuple[int, int]:
    """Get random resolution based on device type."""
    if is_mobile:
        return random.choice(MOBILE_RESOLUTIONS)
    return random.choice(DESKTOP_RESOLUTIONS)


# ============================================================================
# PAGE & VIDEO VERIFICATION (Async)
# ============================================================================

async def wait_for_page_load(page, timeout: int = 25) -> bool:
    """Wait for page to finish loading (Pydoll async)."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
        await asyncio.sleep(0.5)  # Extra time for dynamic content
        return True
    except Exception:
        return False


async def is_video_playing_async(page) -> bool:
    """Check if any video is playing (Pydoll async)."""
    try:
        result = await page.evaluate("""
            var videos = document.querySelectorAll('video');
            for (var i = 0; i < videos.length; i++) {
                var v = videos[i];
                if (v && !v.paused && !v.ended && v.readyState >= 2 && v.currentTime > 0) {
                    return true;
                }
            }
            return false;
        """)
        
        # Unpack Pydoll's CDP dictionary response
        if isinstance(result, dict):
            result = result.get('result', {}).get('result', {}).get('value', False)
        
        return bool(result)
    except:
        return False


# ============================================================================
# COOKIE & LOGIN HANDLING (Async)
# ============================================================================

async def handle_cookies_async(page, instance_id: int = 0) -> bool:
    """Handle cookie consent popups (Pydoll async)."""
    consent_texts = ['Accept all', 'I agree', 'Accept', 'Got it', 'OK']
    try:
        for text in consent_texts:
            try:
                button = await page.find(text=text)
                if button and await button.is_visible():
                    await button.click(humanize=True)
                    await asyncio.sleep(1)
                    return True
            except:
                continue
        
        # Try by aria-label
        try:
            button = await page.find(aria_label='Accept')
            if button and await button.is_visible():
                await button.click(humanize=True)
                await asyncio.sleep(1)
                return True
        except:
            pass
        
        return False
    except:
        return False


async def is_login_page_async(page) -> bool:
    """Check if current page is a login page (Pydoll async)."""
    try:
        raw_url = await page.evaluate("window.location.href")
        
        # Safely unpack Pydoll's CDP dictionary response
        if isinstance(raw_url, dict):
            current_url = raw_url.get('result', {}).get('result', {}).get('value', '')
        else:
            current_url = str(raw_url) if raw_url else ''
        
        current_url = current_url.lower()
        login_patterns = ['accounts.google.com', 'accounts.youtube.com', 'signin', 'servicelogin', 'login']
        for pattern in login_patterns:
            if pattern in current_url:
                return True
        
        # Check for login form elements
        try:
            email_input = await page.find(name='email') or await page.find(id='email') or await page.find(type='email')
            if email_input and await email_input.is_visible():
                return True
        except:
            pass
        
        try:
            password_input = await page.find(type='password')
            if password_input and await password_input.is_visible():
                return True
        except:
            pass
        
        return False
    except:
        return False


# ============================================================================
# SYSTEM MONITORING
# ============================================================================

def get_system_ram_usage() -> float:
    """Get system RAM usage percentage."""
    if HAS_PSUTIL:
        return psutil.virtual_memory().percent
    if os.name == 'nt':
        try:
            result = subprocess.run(
                ['wmic', 'os', 'get', 'freephysicalmemory', '/value'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if 'FreePhysicalMemory' in line:
                    free_kb = int(line.split('=')[1].strip())
                    total_kb = psutil.virtual_memory().total / 1024 if HAS_PSUTIL else 8 * 1024 * 1024
                    used_percent = ((total_kb - free_kb) / total_kb) * 100
                    return round(used_percent, 1)
        except:
            pass
    return 50.0


def get_variable_watch_time(min_time: int, max_time: int) -> int:
    """Get variable watch time based on human-like distribution."""
    distribution = random.choices(
        population=['short', 'medium', 'long', 'full'],
        weights=[0.3, 0.4, 0.2, 0.1],
        k=1
    )[0]
    video_range = max_time - min_time
    
    if distribution == 'short':
        return min_time + int(video_range * random.uniform(0.2, 0.4))
    elif distribution == 'medium':
        return min_time + int(video_range * random.uniform(0.4, 0.7))
    elif distribution == 'long':
        return min_time + int(video_range * random.uniform(0.7, 0.95))
    else:  # 'full'
        return max_time + random.randint(-10, 10)


# ============================================================================
# COMPATIBILITY WRAPPERS (Sync)
# ============================================================================

#def wait_for_page_load_sync(page, timeout: int = 25) -> bool:
#    """Sync wrapper for wait_for_page_load."""
#    return asyncio.run(wait_for_page_load(page, timeout))
#
#
#def is_video_playing_sync(page) -> bool:
#    """Sync wrapper for is_video_playing_async."""
#    return asyncio.run(is_video_playing_async(page))
#
#
#def handle_cookies_sync(page, instance_id: int = 0) -> bool:
#    """Sync wrapper for handle_cookies_async."""
#    return asyncio.run(handle_cookies_async(page, instance_id))
#
#
#def is_login_page_sync(page) -> bool:
#    """Sync wrapper for is_login_page_async."""
#    return asyncio.run(is_login_page_async(page))


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # User agent databases
    'DESKTOP_AGENTS', 'MOBILE_AGENTS', 'DESKTOP_RESOLUTIONS', 'MOBILE_RESOLUTIONS',
    
    # URL functions
    'extract_video_id', 'construct_watch_url', 'get_video_title', 'sanitize_text',
    
    # User agent functions
    'get_random_user_agent', 'get_random_resolution',
    
    # Page verification (async)
    'wait_for_page_load', 'is_video_playing_async',
    
    # Cookie handling (async)
    'handle_cookies_async', 'is_login_page_async',
    
    # Page verification (sync wrappers)
#    'wait_for_page_load_sync', 'is_video_playing_sync',
    
    # Cookie handling (sync wrappers)
#    'handle_cookies_sync', 'is_login_page_sync',
    
    # System
    'get_system_ram_usage', 'get_variable_watch_time',
]