#!/usr/bin/env python3
"""
Fingerprint Manager - Loads real-world browser fingerprints from Intoli JSON
Generated from user-agents Node.js script
Provides complete, consistent browser fingerprints for anti-detection
"""

import json
import random
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# File paths
DESKTOP_FILE = DATA_DIR / "intoli_desktop.json"
MOBILE_FILE = DATA_DIR / "intoli_mobile.json"

# Global caches
_DESKTOP_FINGERPRINTS = None
_MOBILE_FINGERPRINTS = None
_LOADED = False


def load_fingerprints():
    """Load fingerprints from JSON files"""
    global _DESKTOP_FINGERPRINTS, _MOBILE_FINGERPRINTS, _LOADED
    
    if _LOADED:
        return
    
    try:
        if DESKTOP_FILE.exists():
            with open(DESKTOP_FILE, 'r', encoding='utf-8') as f:
                _DESKTOP_FINGERPRINTS = json.load(f)
            print(f"[FINGERPRINT] Loaded {len(_DESKTOP_FINGERPRINTS)} desktop fingerprints")
        else:
            print(f"[FINGERPRINT] WARNING: Desktop fingerprint file not found: {DESKTOP_FILE}")
            _DESKTOP_FINGERPRINTS = []
    except Exception as e:
        print(f"[FINGERPRINT] ERROR loading desktop fingerprints: {e}")
        _DESKTOP_FINGERPRINTS = []
    
    try:
        if MOBILE_FILE.exists():
            with open(MOBILE_FILE, 'r', encoding='utf-8') as f:
                _MOBILE_FINGERPRINTS = json.load(f)
            print(f"[FINGERPRINT] Loaded {len(_MOBILE_FINGERPRINTS)} mobile fingerprints")
        else:
            print(f"[FINGERPRINT] WARNING: Mobile fingerprint file not found: {MOBILE_FILE}")
            _MOBILE_FINGERPRINTS = []
    except Exception as e:
        print(f"[FINGERPRINT] ERROR loading mobile fingerprints: {e}")
        _MOBILE_FINGERPRINTS = []
    
    _LOADED = True
    
    # ========== FALLBACK FINGERPRINTS ==========
    # These are used if JSON files are missing or empty
    # CRITICAL: Mobile must have pluginsLength = 0
    
    if not _DESKTOP_FINGERPRINTS:
        _DESKTOP_FINGERPRINTS = [{
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "platform": "Win32",
            "screenHeight": 1080,
            "screenWidth": 1920,
            "viewportHeight": 950,
            "viewportWidth": 1920,
            "pluginsLength": 5,
            "deviceCategory": "desktop",
            "weight": 1.0,
            "vendor": "Google Inc.",
            "language": "en-US"
        }]
    
    if not _MOBILE_FINGERPRINTS:
        _MOBILE_FINGERPRINTS = [{
            "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.7.5 Mobile/15E148 Safari/604.1",
            "platform": "iPhone",
            "screenHeight": 844,
            "screenWidth": 390,
            "viewportHeight": 699,
            "viewportWidth": 390,
            "pluginsLength": 0,
            "deviceCategory": "mobile",
            "weight": 1.0,
            "vendor": "Apple Computer, Inc.",
            "language": "en-US"
        }]


def get_desktop_fingerprints():
    """Get desktop fingerprints"""
    load_fingerprints()
    return _DESKTOP_FINGERPRINTS


def get_mobile_fingerprints():
    """Get mobile fingerprints"""
    load_fingerprints()
    return _MOBILE_FINGERPRINTS


def get_random_desktop_fingerprint():
    """Get a random desktop fingerprint (weighted by probability)"""
    fingerprints = get_desktop_fingerprints()
    if not fingerprints:
        return None
    
    weights = [fp.get('weight', 0.0001) for fp in fingerprints]
    total_weight = sum(weights)
    if total_weight == 0:
        return random.choice(fingerprints)
    return random.choices(fingerprints, weights=weights, k=1)[0]


def get_random_mobile_fingerprint():
    """Get a random mobile fingerprint (weighted by probability)"""
    fingerprints = get_mobile_fingerprints()
    if not fingerprints:
        return None
    
    weights = [fp.get('weight', 0.0001) for fp in fingerprints]
    total_weight = sum(weights)
    if total_weight == 0:
        return random.choice(fingerprints)
    return random.choices(fingerprints, weights=weights, k=1)[0]


def get_fingerprint_for_view_type(view_type, force_mobile=False):
    """
    Get appropriate fingerprint based on view type
    
    Args:
        view_type: String view type
        force_mobile: If True, always return mobile fingerprint
    
    Returns:
        Dictionary with fingerprint data, or None if unavailable
    """
    if force_mobile:
        fp = get_random_mobile_fingerprint()
        if fp:
            fp['_type'] = 'mobile'
            fp['deviceCategory'] = 'mobile'
        return fp
    
    if view_type == "Suggested":
        fp = get_random_desktop_fingerprint()
        if fp:
            fp['_type'] = 'desktop'
            fp['deviceCategory'] = 'desktop'
        return fp
    elif view_type in ("Other YouTube features", "Direct/Unknown", "External(Embed)"):
        fp = get_random_mobile_fingerprint()
        if fp:
            fp['_type'] = 'mobile'
            fp['deviceCategory'] = 'mobile'
        return fp
    elif view_type == "Google Search":
        if random.random() < 0.5:
            fp = get_random_desktop_fingerprint()
            if fp:
                fp['_type'] = 'desktop'
                fp['deviceCategory'] = 'desktop'
            return fp
        else:
            fp = get_random_mobile_fingerprint()
            if fp:
                fp['_type'] = 'mobile'
                fp['deviceCategory'] = 'mobile'
            return fp
    else:
        if random.random() < 0.5:
            fp = get_random_desktop_fingerprint()
            if fp:
                fp['_type'] = 'desktop'
                fp['deviceCategory'] = 'desktop'
            return fp
        else:
            fp = get_random_mobile_fingerprint()
            if fp:
                fp['_type'] = 'mobile'
                fp['deviceCategory'] = 'mobile'
            return fp


def get_fingerprint_with_platform(platform_type='desktop'):
    """Get fingerprint for specific platform type"""
    if platform_type == 'mobile':
        return get_random_mobile_fingerprint()
    else:
        return get_random_desktop_fingerprint()


def validate_fingerprint(fp):
    """Validate fingerprint has all required fields"""
    required_fields = [
        'userAgent', 'platform', 'screenHeight', 'screenWidth',
        'viewportHeight', 'viewportWidth', 'pluginsLength', 'deviceCategory'
    ]
    
    if not fp:
        return False
    
    for field in required_fields:
        if field not in fp:
            return False
    
    # Validate mobile fingerprints have pluginsLength = 0
    if fp.get('deviceCategory') == 'mobile' and fp.get('pluginsLength', 5) != 0:
        print(f"[FINGERPRINT] WARNING: Mobile fingerprint has pluginsLength={fp.get('pluginsLength')}, should be 0")
        fp['pluginsLength'] = 0
        return True
    
    return True


def get_fingerprint_summary(fp):
    """Get a human-readable summary of the fingerprint"""
    if not fp:
        return "No fingerprint"
    
    return (f"Device: {fp.get('deviceCategory', 'unknown')}, "
            f"UA: {fp.get('userAgent', 'unknown')[:50]}..., "
            f"Screen: {fp.get('screenWidth', 0)}x{fp.get('screenHeight', 0)}, "
            f"Viewport: {fp.get('viewportWidth', 0)}x{fp.get('viewportHeight', 0)}, "
            f"Plugins: {fp.get('pluginsLength', 0)}, "
            f"Platform: {fp.get('platform', 'unknown')}")


# Export public functions
__all__ = [
    'load_fingerprints',
    'get_desktop_fingerprints',
    'get_mobile_fingerprints',
    'get_random_desktop_fingerprint',
    'get_random_mobile_fingerprint',
    'get_fingerprint_for_view_type',
    'get_fingerprint_with_platform',
    'validate_fingerprint',
    'get_fingerprint_summary',
    'DESKTOP_FILE',
    'MOBILE_FILE'
]