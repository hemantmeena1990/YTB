# common/cache_manager.py
"""
Cache Manager for YouTube Automation Suite
"""

import json
import time
import hashlib
import shutil
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import requests

logger = logging.getLogger(__name__)

# ========== Paths - FIXED ==========
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"

# Create all cache directories
VIDEO_CACHE_DIR = CACHE_DIR / "videos"
CHANNEL_CACHE_DIR = CACHE_DIR / "channels"
THUMBNAIL_CACHE_DIR = CACHE_DIR / "thumbnails"
LOGO_CACHE_DIR = CACHE_DIR / "logos"

# Ensure directories exist - use exist_ok=True
for dir_path in [CACHE_DIR, VIDEO_CACHE_DIR, CHANNEL_CACHE_DIR, THUMBNAIL_CACHE_DIR, LOGO_CACHE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)
    print(f"[Cache] Created directory: {dir_path}")

# ========== Cache Settings ==========
CACHE_EXPIRY_VIDEO = 7 * 24 * 3600
CACHE_EXPIRY_CHANNEL = 24 * 3600
CACHE_EXPIRY_THUMBNAIL = 30 * 24 * 3600
CACHE_EXPIRY_LOGO = 30 * 24 * 3600

# ========== Helper Functions ==========
def sanitize_filename(name: str) -> str:
    """Sanitize filename to be filesystem safe"""
    import re
    # Remove special characters
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    return name[:50]  # Limit length

def is_cache_valid(cache_file: Path, max_age_seconds: int) -> bool:
    if not cache_file.exists():
        return False
    file_age = time.time() - cache_file.stat().st_mtime
    return file_age < max_age_seconds

def save_json_cache(cache_dir: Path, filename: str, data: Dict[str, Any]) -> bool:
    try:
        cache_file = cache_dir / f"{filename}.json"
        cache_data = {
            "data": data,
            "cached_at": time.time(),
            "expires_at": time.time() + CACHE_EXPIRY_VIDEO
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        print(f"[Cache] Saved: {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save cache {filename}: {e}")
        return False

def load_json_cache(cache_dir: Path, filename: str, max_age: int) -> Optional[Dict[str, Any]]:
    cache_file = cache_dir / f"{filename}.json"
    
    if not is_cache_valid(cache_file, max_age):
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        print(f"[Cache] Loaded: {filename}")
        return cache_data.get("data")
    except Exception as e:
        logger.error(f"Failed to load cache {filename}: {e}")
        return None

def save_image_cache(cache_dir: Path, filename: str, image_data: bytes) -> bool:
    try:
        cache_file = cache_dir / f"{filename}.jpg"
        with open(cache_file, 'wb') as f:
            f.write(image_data)
        print(f"[Cache] Saved image: {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save image {filename}: {e}")
        return False

def load_image_cache(cache_dir: Path, filename: str) -> Optional[bytes]:
    cache_file = cache_dir / f"{filename}.jpg"
    if cache_file.exists():
        with open(cache_file, 'rb') as f:
            return f.read()
    return None

# ========== Video Cache Functions ==========
def cache_video_info(video_id: str, video_data: Dict[str, Any]) -> bool:
    return save_json_cache(VIDEO_CACHE_DIR, video_id, video_data)

def get_cached_video_info(video_id: str) -> Optional[Dict[str, Any]]:
    return load_json_cache(VIDEO_CACHE_DIR, video_id, CACHE_EXPIRY_VIDEO)

def cache_video_thumbnail(video_id: str, thumbnail_url: str) -> bool:
    try:
        response = requests.get(thumbnail_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            return save_image_cache(THUMBNAIL_CACHE_DIR, video_id, response.content)
    except Exception as e:
        logger.error(f"Failed to cache thumbnail for {video_id}: {e}")
    return False

def get_cached_video_thumbnail(video_id: str) -> Optional[bytes]:
    return load_image_cache(THUMBNAIL_CACHE_DIR, video_id)

# ========== Channel Cache Functions ==========
def cache_channel_info(channel_name: str, channel_data: Dict[str, Any]) -> bool:
    safe_name = sanitize_filename(channel_name)
    return save_json_cache(CHANNEL_CACHE_DIR, safe_name, channel_data)

def get_cached_channel_info(channel_name: str) -> Optional[Dict[str, Any]]:
    safe_name = sanitize_filename(channel_name)
    return load_json_cache(CHANNEL_CACHE_DIR, safe_name, CACHE_EXPIRY_CHANNEL)

def cache_channel_logo(channel_name: str, logo_url: str) -> bool:
    try:
        response = requests.get(logo_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            safe_name = sanitize_filename(channel_name)
            return save_image_cache(LOGO_CACHE_DIR, safe_name, response.content)
    except Exception as e:
        logger.error(f"Failed to cache logo for {channel_name}: {e}")
    return False

def get_cached_channel_logo(channel_name: str) -> Optional[bytes]:
    safe_name = sanitize_filename(channel_name)
    return load_image_cache(LOGO_CACHE_DIR, safe_name)

# ========== Cache Management ==========
def clear_expired_cache():
    deleted = 0
    for cache_dir in [VIDEO_CACHE_DIR, CHANNEL_CACHE_DIR, THUMBNAIL_CACHE_DIR, LOGO_CACHE_DIR]:
        if cache_dir.exists():
            for cache_file in cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                        expires_at = data.get("expires_at", 0)
                        if time.time() > expires_at:
                            cache_file.unlink()
                            deleted += 1
                            image_file = cache_dir / f"{cache_file.stem}.jpg"
                            if image_file.exists():
                                image_file.unlink()
                except:
                    cache_file.unlink()
                    deleted += 1
    return deleted

def clear_all_cache():
    deleted = 0
    for cache_dir in [VIDEO_CACHE_DIR, CHANNEL_CACHE_DIR, THUMBNAIL_CACHE_DIR, LOGO_CACHE_DIR]:
        if cache_dir.exists():
            for cache_file in cache_dir.glob("*"):
                cache_file.unlink()
                deleted += 1
    return deleted

def get_cache_stats():
    stats = {
        "videos": len(list(VIDEO_CACHE_DIR.glob("*.json"))) if VIDEO_CACHE_DIR.exists() else 0,
        "channels": len(list(CHANNEL_CACHE_DIR.glob("*.json"))) if CHANNEL_CACHE_DIR.exists() else 0,
        "thumbnails": len(list(THUMBNAIL_CACHE_DIR.glob("*.jpg"))) if THUMBNAIL_CACHE_DIR.exists() else 0,
        "logos": len(list(LOGO_CACHE_DIR.glob("*.jpg"))) if LOGO_CACHE_DIR.exists() else 0,
        "total_size_mb": 0
    }
    
    total_size = 0
    for cache_dir in [VIDEO_CACHE_DIR, CHANNEL_CACHE_DIR, THUMBNAIL_CACHE_DIR, LOGO_CACHE_DIR]:
        if cache_dir.exists():
            for f in cache_dir.glob("*"):
                if f.is_file():
                    total_size += f.stat().st_size
    stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
    
    return stats