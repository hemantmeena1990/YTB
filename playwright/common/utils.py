# playwright/common/utils.py
"""
Playwright-specific utilities for YouTube Automation.
Includes: user agents, delays, watch time calculation, URL helpers.
"""

import random
import time
import re
from typing import Tuple, Optional


# ========== USER AGENT FUNCTIONS ==========

DESKTOP_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

MOBILE_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6301.2 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
]


def get_random_user_agent(force_mobile: bool = None) -> Tuple[str, bool]:
    """
    Get random user agent.
    
    Args:
        force_mobile: True=mobile only, False=desktop only, None=random mix
    
    Returns:
        Tuple of (user_agent_string, is_mobile)
    """
    if force_mobile is True:
        return random.choice(MOBILE_AGENTS), True
    elif force_mobile is False:
        return random.choice(DESKTOP_AGENTS), False
    else:
        if random.random() < 0.5:
            return random.choice(DESKTOP_AGENTS), False
        else:
            return random.choice(MOBILE_AGENTS), True


# ========== DELAY FUNCTIONS ==========

def human_delay(min_seconds: float = 0.3, max_seconds: float = 1.5) -> None:
    """Sleep with human-like variation."""
    delay = random.expovariate(1.5) + random.uniform(min_seconds, max_seconds)
    delay = min(max(delay, min_seconds), max_seconds * 2)
    time.sleep(delay)


# ========== WATCH TIME FUNCTIONS ==========

def get_variable_watch_time(min_time: int, max_time: int) -> int:
    """
    Generate watch time with non-linear distribution.
    
    Distribution:
    - 30% short (20-40% of range)
    - 40% medium (40-70% of range)
    - 20% long (70-95% of range)
    - 10% full (max + 0-30 extra)
    """
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
    else:  # full
        return max_time + random.randint(0, 30)


# ========== URL HELPERS ==========

def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL."""
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


def is_shorts_url(url: str) -> bool:
    """Check if URL is a YouTube Shorts URL."""
    return '/shorts/' in url