# common/input.py
"""
Central configuration module for YouTube Automation Dashboard.
Self-contained - no external dependencies, works with both Selenium and Playwright.
"""

import json
import re
import urllib.request
import random
from pathlib import Path
from typing import Dict, List, Optional

# ========== Configuration File Path ==========
CONFIG_FILE = Path(__file__).parent / "data" / "user_config.json"

# ========== Default Configuration ==========
DEFAULT_CONFIG = {
    "url": "",
    "urls": [],
    "num_instances": 1,
    "headless": False,
    "cycles": 1,
    "min_watch_time": 15,
    "max_watch_time": 30,
    "suggested_min": 15,
    "suggested_max": 35,
    "suggested_chance": 0.4,
    "use_proxy": False,
    "proxy_url": "",
    "view_type": "auto",
    "channel_name": "rajasthanidesidiaries",
}

# ========== User Agent Lists (Fallback) ==========
DESKTOP_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

MOBILE_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6301.2 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
]


# ========== Config File Operations ==========
def load_config() -> Dict:
    """Load user configuration from JSON file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        # Backward compatibility: ensure urls exists
        if "url" in config and config["url"] and not config.get("urls"):
            config["urls"] = [config["url"]]
        elif not config.get("urls"):
            config["urls"] = []
        return config
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict) -> None:
    """Save user configuration to JSON file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Ensure url field is set from urls if needed
    if config.get("urls") and len(config["urls"]) > 0 and not config.get("url"):
        config["url"] = config["urls"][0]
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


# ========== User Agent Functions ==========
def get_random_user_agent(force_mobile: bool = None) -> tuple:
    """
    Get a random user agent.
    
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


# ========== Video ID Extraction ==========
def extract_video_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from any YouTube URL format.
    
    Supported formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtube.com/shorts/VIDEO_ID
    - https://youtube.com/embed/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    """
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


# ========== Video Title Extraction (oEmbed API) ==========
def get_video_title(url: str) -> Optional[str]:
    """
    Fetch video title using YouTube oEmbed API.
    No API key required - lightweight and fast.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None
    try:
        api_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('title', '')
    except Exception:
        return None


# ========== Video Info Functions ==========
def get_video_info(url: str) -> dict:
    """Get video ID and title for a given URL."""
    video_id = extract_video_id(url)
    if not video_id:
        return {"video_id": None, "title": None, "error": "Invalid URL"}
    title = get_video_title(url)
    if not title:
        title = "Title not found"
    return {"video_id": video_id, "title": title}


def get_multiple_video_info(urls: List[str]) -> List[dict]:
    """Get video info for multiple URLs."""
    return [get_video_info(url) for url in urls]


# ========== URL Type Detection ==========
def detect_url_type(url: str) -> str:
    """
    Detect whether URL points to a regular video or a Short.
    Returns 'video', 'shorts', or 'invalid'.
    """
    vid = extract_video_id(url)
    if not vid:
        return "invalid"
    if '/shorts/' in url:
        return "shorts"
    return "video"


def get_applicable_view_types(url: str) -> List[str]:
    """
    Return list of view types that are valid for the given URL.
    Used by the dashboard for the dropdown menu.
    """
    t = detect_url_type(url)
    base_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Channel View"]
    
    if t == "video":
        return base_types + ["Search (Video)"]
    elif t == "shorts":
        return base_types + ["Short Feeds"]
    return []


# ========== Build Script Configuration ==========
def build_script_config(instance_id: int, global_config: Dict, url: str, view_type: str) -> Dict:
    """
    Build configuration dictionary for a script instance.
    This is used by the dashboard when launching scripts.
    
    Args:
        instance_id: Unique ID for this instance
        global_config: Global configuration from dashboard
        url: Original YouTube URL
        view_type: Selected view type
    
    Returns:
        Configuration dict for the script
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Invalid URL: {url}")

    # ========== URL Construction Based on View Type ==========
    
    # View types that use DIRECT navigation
    if view_type == "Other YouTube features":
        # Must use youtu.be short link with mobile agent ONLY
        constructed_url = f"https://youtu.be/{video_id}"
        ua, is_mobile = get_random_user_agent(force_mobile=True)
        video_title = ""
        
    elif view_type == "Direct/Unknown":
        # Must use standard watch URL with mobile agent ONLY
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
        ua, is_mobile = get_random_user_agent(force_mobile=True)
        video_title = ""
        
    elif view_type == "Suggested":
        # Must use standard watch URL with desktop agent ONLY
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
        ua, is_mobile = get_random_user_agent(force_mobile=False)
        video_title = ""
        
    elif view_type == "Short Feeds":
        # Uses ONLY /shorts/ link with random agent (any)
        constructed_url = f"https://www.youtube.com/shorts/{video_id}"
        ua, is_mobile = get_random_user_agent(force_mobile=None)
        video_title = ""
    
    # View types that use SEARCH (not direct navigation)
    elif view_type == "Search (Video)":
        # Opens YouTube homepage, searches for video title
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"  # fallback only
        ua, is_mobile = get_random_user_agent(force_mobile=None)
        video_title = get_video_title(constructed_url) or video_id
        
    elif view_type == "Channel View":
        # Opens YouTube homepage, searches for channel name
        # Then searches within channel for video ID
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"  # fallback only
        ua, is_mobile = get_random_user_agent(force_mobile=None)
        video_title = get_video_title(constructed_url) or video_id
        
    else:
        # Default fallback (should not happen)
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
        ua, is_mobile = get_random_user_agent(force_mobile=None)
        video_title = ""

    # Return configuration
    return {
        "instance_id": instance_id,
        "url": url,
        "constructed_url": constructed_url,
        "video_id": video_id,
        "video_title": video_title,
        "view_type": view_type,
        "min_watch_time": global_config["min_watch_time"],
        "max_watch_time": global_config["max_watch_time"],
        "suggested_min": global_config["suggested_min"],
        "suggested_max": global_config["suggested_max"],
        "suggested_chance": global_config.get("suggested_chance", 0.4),
        "headless": global_config["headless"],
        "cycles": global_config["cycles"],
        "use_proxy": global_config.get("use_proxy", False),
        "proxy": global_config.get("proxy_url", ""),
        "user_agent": ua,
        "is_mobile": is_mobile,
        "channel_name": global_config.get("channel_name", "rajasthanidesidiaries"),
    }