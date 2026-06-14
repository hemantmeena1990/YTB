# playwright/common/utils.py
"""
Playwright utility functions - only custom logic not in Playwright.
"""

import time
import random
import re
import logging
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


def wait_for_page_load(page: Page, timeout: int = 25) -> bool:
    """Wait for page to load completely using readyState"""
    start = time.time()
    stable_count = 0
    while time.time() - start < timeout:
        try:
            state = page.evaluate("return document.readyState;")
            if state == "complete":
                stable_count += 1
                if stable_count >= 2:
                    return True
            else:
                stable_count = 0
        except:
            pass
        time.sleep(0.3)
    return False


def handle_cookies(page: Page, instance_id: int = 0) -> bool:
    """Handle cookie consent popups (site-specific)"""
    cookie_selectors = [
        "button[aria-label='Accept all']",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "button:has-text('Got it')"
    ]
    
    for selector in cookie_selectors:
        try:
            elements = page.locator(selector).all()
            for elem in elements:
                if elem.is_visible() and elem.is_enabled():
                    elem.click()
                    time.sleep(1)
                    return True
        except:
            continue
    return False


def is_login_page(page: Page) -> bool:
    """Check if current page is a login page"""
    try:
        current_url = page.url.lower()
        login_patterns = ['accounts.google.com', 'accounts.youtube.com', 'signin', 'servicelogin', 'login']
        for pattern in login_patterns:
            if pattern in current_url:
                return True
        
        page_source = page.content().lower()
        text_patterns = ['sign in to continue', 'sign in - google accounts', 'use your google account']
        for pattern in text_patterns:
            if pattern in page_source:
                return True
        
        login_selectors = ["form#gaia_loginform", "input[type='email']", "input[type='password']"]
        for selector in login_selectors:
            elements = page.locator(selector).all()
            for elem in elements:
                if elem.is_visible():
                    return True
        return False
    except:
        return False


def get_variable_watch_time(min_time: int, max_time: int) -> int:
    """Get random watch time with distribution"""
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
    else:
        return max_time + random.randint(0, 30)


def wait_for_url_change(page: Page, old_url: str, timeout: int = 5) -> bool:
    """Wait for URL to change"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            if page.url != old_url:
                return True
        except:
            pass
        time.sleep(0.3)
    return False


def get_random_resolution(is_mobile: bool):
    """Get random viewport resolution"""
    if is_mobile:
        resolutions = [(375, 667), (390, 844), (393, 852), (412, 915), (360, 800)]
    else:
        resolutions = [(1366, 768), (1920, 1080), (1536, 864), (1440, 900), (1280, 720)]
    return random.choice(resolutions)


def human_delay(min_sec: float = 0.3, max_sec: float = 1.5):
    """Random human-like delay"""
    time.sleep(random.uniform(min_sec, max_sec))


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


def get_random_user_agent(force_mobile: bool = None):
    """Get random user agent"""
    desktop_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    mobile_agents = [
        "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    ]
    
    if force_mobile is True:
        return random.choice(mobile_agents), True
    elif force_mobile is False:
        return random.choice(desktop_agents), False
    else:
        if random.random() < 0.5:
            return random.choice(desktop_agents), False
        else:
            return random.choice(mobile_agents), True