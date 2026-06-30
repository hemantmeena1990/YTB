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
    
    # Fallback if files are empty
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
            "weight": 1.0
        }]
    
    if not _MOBILE_FINGERPRINTS:
        _MOBILE_FINGERPRINTS = [{
            "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.7.5 Mobile/15E148 Safari/604.1",
            "platform": "iPhone",
            "screenHeight": 844,
            "screenWidth": 390,
            "viewportHeight": 699,
            "viewportWidth": 390,
            "pluginsLength": 5,
            "deviceCategory": "mobile",
            "weight": 1.0
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
    
    # Use weight for weighted random selection
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
    
    # Use weight for weighted random selection
    weights = [fp.get('weight', 0.0001) for fp in fingerprints]
    total_weight = sum(weights)
    if total_weight == 0:
        return random.choice(fingerprints)
    return random.choices(fingerprints, weights=weights, k=1)[0]


def get_fingerprint_for_view_type(view_type):
    """Get appropriate fingerprint based on view type"""
    if view_type == "Suggested":
        # Desktop only for Suggested
        fp = get_random_desktop_fingerprint()
        if fp:
            fp['_type'] = 'desktop'
        return fp
    elif view_type in ("Other YouTube features", "Direct/Unknown"):
        # Mobile only for these
        fp = get_random_mobile_fingerprint()
        if fp:
            fp['_type'] = 'mobile'
        return fp
    elif view_type == "Google Search":
        # Random for search
        if random.random() < 0.5:
            fp = get_random_desktop_fingerprint()
            if fp:
                fp['_type'] = 'desktop'
            return fp
        else:
            fp = get_random_mobile_fingerprint()
            if fp:
                fp['_type'] = 'mobile'
            return fp
    else:
        # Random for others
        if random.random() < 0.5:
            fp = get_random_desktop_fingerprint()
            if fp:
                fp['_type'] = 'desktop'
            return fp
        else:
            fp = get_random_mobile_fingerprint()
            if fp:
                fp['_type'] = 'mobile'
            return fp


# Export public functions
__all__ = [
    'load_fingerprints',
    'get_desktop_fingerprints',
    'get_mobile_fingerprints',
    'get_random_desktop_fingerprint',
    'get_random_mobile_fingerprint',
    'get_fingerprint_for_view_type',
    'DESKTOP_FILE',
    'MOBILE_FILE'
]