"""
Shared Utilities for YouTube Automation Suite
Common functions used across all scripts.
"""

import os
import re
import json
import random
import logging
import subprocess
import urllib.request
import unicodedata
from time import sleep, time
from typing import Optional, Tuple, List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Try to import psutil for RAM monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ============================================================================
# USER AGENT DATABASES
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

# Typing behaviors
TYPING_BEHAVIORS = ['slow', 'fast', 'mixed', 'corrections']
TYPING_WEIGHTS = [0.25, 0.30, 0.30, 0.15]

# ============================================================================
# URL & VIDEO ID FUNCTIONS
# ============================================================================

def extract_video_id(url: str) -> Optional[str]:
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
    """Construct a watch URL from video ID (useful for view type matching)."""
    if use_short_link:
        return f"https://youtu.be/{video_id}"
    else:
        return f"https://www.youtube.com/watch?v={video_id}"

def get_video_title(video_url: str) -> Optional[str]:
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            return None
        api_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            title = data.get('title', '')
            if title:
                title = ' '.join(title.split())
                return title
    except Exception:
        pass
    return None

def sanitize_text(text: str) -> str:
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ============================================================================
# USER AGENT FUNCTIONS
# ============================================================================

def get_random_user_agent(force_mobile: bool = None) -> Tuple[str, bool]:
    if force_mobile is True:
        return random.choice(MOBILE_AGENTS), True
    elif force_mobile is False:
        return random.choice(DESKTOP_AGENTS), False
    else:
        if random.random() < 0.5:
            return random.choice(DESKTOP_AGENTS), False
        else:
            return random.choice(MOBILE_AGENTS), True

def get_random_resolution(is_mobile: bool) -> Tuple[int, int]:
    if is_mobile:
        return random.choice(MOBILE_RESOLUTIONS)
    else:
        return random.choice(DESKTOP_RESOLUTIONS)

# ============================================================================
# HUMAN BEHAVIOR SIMULATION
# ============================================================================

def human_delay(min_seconds: float = 0.3, max_seconds: float = 1.5) -> None:
    delay = random.expovariate(1.5) + random.uniform(min_seconds, max_seconds)
    delay = min(max(delay, min_seconds), max_seconds * 2)
    sleep(delay)

def natural_typing(element, text: str, use_fast_only: bool = False) -> str:
    filtered = ''.join(c for c in text if ord(c) <= 0xFFFF)
    if use_fast_only:
        for ch in filtered:
            element.send_keys(ch)
            sleep(random.uniform(0.02, 0.05))
        return 'fast'
    
    behavior = random.choices(TYPING_BEHAVIORS, weights=TYPING_WEIGHTS, k=1)[0]
    if behavior == 'slow':
        for ch in filtered:
            element.send_keys(ch)
            sleep(random.uniform(0.08, 0.2))
    elif behavior == 'fast':
        for ch in filtered:
            element.send_keys(ch)
            sleep(random.uniform(0.03, 0.08))
    elif behavior == 'mixed':
        for ch in filtered:
            element.send_keys(ch)
            sleep(random.uniform(0.04, 0.15))
    elif behavior == 'corrections':
        typed = ""
        for ch in filtered:
            element.send_keys(ch)
            typed += ch
            sleep(random.uniform(0.05, 0.12))
            if len(typed) > 3 and random.random() < 0.08:
                backspace_count = random.randint(1, 2)
                for _ in range(backspace_count):
                    element.send_keys(Keys.BACKSPACE)
                    sleep(random.uniform(0.1, 0.2))
                typed = typed[:-backspace_count]
                for c in filtered[len(typed):len(typed) + backspace_count]:
                    element.send_keys(c)
                    sleep(random.uniform(0.05, 0.12))
                typed = filtered[:len(typed)]
    return behavior

def random_scroll(driver, is_mobile: bool = False, smooth: bool = True) -> None:
    amount = random.randint(100, 500) if is_mobile else random.randint(80, 400)
    behavior = 'smooth' if smooth else 'auto'
    driver.execute_script(f"window.scrollBy({{top: {amount}, behavior: '{behavior}'}});")
    if random.random() < 0.3:
        sleep(random.uniform(0.2, 0.6))
        additional = random.randint(20, 100) * (1 if random.random() < 0.7 else -1)
        driver.execute_script(f"window.scrollBy(0, {additional});")

def random_mouse_movement(driver, element=None) -> None:
    try:
        actions = ActionChains(driver)
        if element:
            x_offset = random.randint(-20, 20)
            y_offset = random.randint(-20, 20)
            actions.move_to_element_with_offset(element, x_offset, y_offset)
        else:
            viewport = driver.execute_script("return {width: window.innerWidth, height: window.innerHeight};")
            x = random.randint(50, viewport['width'] - 50)
            y = random.randint(50, viewport['height'] - 50)
            actions.move_by_offset(x, y)
        actions.perform()
        human_delay(0.1, 0.3)
    except:
        pass

# ============================================================================
# PAGE & VIDEO VERIFICATION
# ============================================================================

def wait_for_page_load(driver, timeout: int = 25) -> bool:
    start = time()
    stable_count = 0
    while time() - start < timeout:
        try:
            state = driver.execute_script("return document.readyState;")
            if state == "complete":
                stable_count += 1
                if stable_count >= 2:
                    return True
            else:
                stable_count = 0
        except:
            pass
        sleep(0.3)
    return False

def is_video_playing(driver) -> bool:
    try:
        return driver.execute_script("""
            var v = document.querySelector('video');
            return v && !v.paused && !v.ended && v.readyState >= 2;
        """)
    except:
        return False

# ============================================================================
# COOKIE & LOGIN HANDLING
# ============================================================================

def handle_cookies(driver, instance_id: int = 0) -> bool:
    cookie_xpaths = [
        "//button[contains(., 'Accept all')]",
        "//button[contains(., 'I agree')]",
        "//button[contains(@aria-label, 'Accept')]",
        "//button[contains(., 'Accept')]",
        "//button[contains(., 'Got it')]"
    ]
    for xpath in cookie_xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for elem in elements:
                if elem.is_displayed() and elem.is_enabled():
                    driver.execute_script("arguments[0].click();", elem)
                    sleep(1)
                    return True
        except:
            continue
    return False

def is_login_page(driver) -> bool:
    try:
        current_url = driver.current_url.lower()
        login_patterns = ['accounts.google.com', 'accounts.youtube.com', 'signin', 'servicelogin', 'login']
        for pattern in login_patterns:
            if pattern in current_url:
                return True
        page_source = driver.page_source.lower()
        text_patterns = ['sign in to continue', 'sign in - google accounts', 'use your google account']
        for pattern in text_patterns:
            if pattern in page_source:
                return True
        login_selectors = ["form#gaia_loginform", "input[type='email']", "input[type='password']"]
        for selector in login_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for elem in elements:
                if elem.is_displayed():
                    size = elem.size
                    if size.get('height', 0) > 50:
                        return True
        return False
    except:
        return False

# ============================================================================
# SYSTEM MONITORING
# ============================================================================

def get_system_ram_usage() -> float:
    if HAS_PSUTIL:
        return psutil.virtual_memory().percent
    if os.name == 'nt':
        try:
            subprocess.run('wmic os get freephysicalmemory', shell=True, capture_output=True, text=True, timeout=5)
            return 50.0
        except:
            pass
    return 50.0

def get_variable_watch_time(min_time: int, max_time: int) -> int:
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

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'DESKTOP_AGENTS', 'MOBILE_AGENTS', 'DESKTOP_RESOLUTIONS', 'MOBILE_RESOLUTIONS',
    'extract_video_id', 'construct_watch_url', 'get_video_title', 'sanitize_text',
    'get_random_user_agent', 'get_random_resolution',
    'human_delay', 'natural_typing', 'random_scroll', 'random_mouse_movement',
    'wait_for_page_load', 'is_video_playing',
    'handle_cookies', 'is_login_page',
    'get_system_ram_usage', 'get_variable_watch_time',
]