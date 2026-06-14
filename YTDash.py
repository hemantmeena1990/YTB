#!/usr/bin/env python3
"""
YouTube Automation Dashboard – Backend Only
With integrated rotating proxy system, live progress tracking, and local caching
"""

import sys
import json
import webbrowser
import threading
import time
import shutil
import random
import glob
import tempfile
import subprocess
import os
import requests as http_requests
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify, send_file
import io
# Import cleanup module
from common.cleanup import clean_all

# Check yt-dlp
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    print("\n" + "="*60)
    print("ERROR: yt-dlp is not installed!")
    print("Please run: pip install yt-dlp")
    print("="*60 + "\n")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from common.input import (
    load_config, save_config, detect_url_type,
    get_applicable_view_types, build_script_config,
    extract_video_id, get_video_title
)

# Import proxy manager for rotating proxy support
from common.proxy_manager import start_background_service, get_rotating_proxy, get_proxy_stats

# Import cache manager
from common.cache_manager import (
    get_cached_video_info, cache_video_info, cache_video_thumbnail, get_cached_video_thumbnail,
    get_cached_channel_info, cache_channel_info, cache_channel_logo, get_cached_channel_logo,
    clear_expired_cache, clear_all_cache, get_cache_stats
)

app = Flask(__name__)

# Ensure data directory exists
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Proxy files
PROXY_LIST_FILE = DATA_DIR / "proxy_list.txt"
BLACKLIST_FILE = DATA_DIR / "blacklist.txt"

CACHE_PATTERNS = ["yt_direct_cache_*", "yt_search_cache_*", "yt_channel_cache_*", "yt_shorts_cache_*", "yt_ss_cache_*"]

# Ensure cache directories exist
from common.cache_manager import VIDEO_CACHE_DIR, CHANNEL_CACHE_DIR, THUMBNAIL_CACHE_DIR, LOGO_CACHE_DIR
for cache_dir in [VIDEO_CACHE_DIR, CHANNEL_CACHE_DIR, THUMBNAIL_CACHE_DIR, LOGO_CACHE_DIR]:
    cache_dir.mkdir(parents=True, exist_ok=True)

# Start background proxy rotation service
print("[Proxy Service] Starting background proxy rotator...")
start_background_service()
print("[Proxy Service] Background proxy rotator is running")

# Global progress tracking for proxy operations
proxy_progress = {
    "status": "idle",
    "operation": "",
    "current_source": "",
    "total_sources": 0,
    "sources_completed": 0,
    "proxies_found": 0,
    "proxies_tested": 0,
    "proxies_working": 0,
    "proxies_failed": 0,
    "blacklisted": 0,
    "whitelisted": 0,
    "total_proxies": 0,
    "percent": 0,
    "last_update": 0,
    "logs": []
}

# Auto-cleanup on startup
def auto_cleanup_on_startup():
    try:
        cleaned = 0
        if LOG_DIR.exists():
            for log_file in LOG_DIR.glob("*.log"):
                try:
                    if time.time() - log_file.stat().st_mtime > 86400:
                        log_file.unlink()
                        cleaned += 1
                except:
                    pass
        for config_file in DATA_DIR.glob("launch_config_*.json"):
            try:
                if time.time() - config_file.stat().st_mtime > 86400:
                    config_file.unlink()
                    cleaned += 1
            except:
                pass
        if cleaned > 0:
            print(f"[Auto-Cleanup] Removed {cleaned} old files")
    except Exception as e:
        print(f"[Auto-Cleanup] Error: {e}")

auto_cleanup_on_startup()

# ==================== Helper Functions ====================

def format_number(num):
    if not num or num == 0:
        return ""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

def add_progress_log(message, level="info"):
    """Add a log entry to progress tracking"""
    timestamp = time.strftime("%H:%M:%S")
    proxy_progress["logs"].append({
        "timestamp": timestamp,
        "message": message,
        "level": level
    })
    if len(proxy_progress["logs"]) > 100:
        proxy_progress["logs"] = proxy_progress["logs"][-100:]
    print(f"[{timestamp}] {message}")

def update_progress():
    """Update progress percentage and timestamp"""
    proxy_progress["last_update"] = time.time()
    if proxy_progress["total_proxies"] > 0:
        proxy_progress["percent"] = int((proxy_progress["proxies_tested"] / proxy_progress["total_proxies"]) * 100)

def get_video_details_ytdlp(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'extractor_args': {
                'youtube': {
                    'po_token': ['web.gvs+http://127.0.0.1:4416'],
                }
            },
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'success': True,
                'video_id': info.get('id', ''),
                'title': info.get('title', 'Untitled'),
                'duration': info.get('duration', 0),
                'thumbnail_url': info.get('thumbnail', ''),
                'is_short': 'shorts' in url or info.get('duration', 0) <= 60,
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'comment_count': info.get('comment_count', 0),
                'upload_date': info.get('upload_date', ''),
                'channel_name': info.get('channel', ''),
                'channel_id': info.get('channel_id', ''),
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_channel_info_ytdlp(channel_handle: str) -> dict:
    result = {"name": channel_handle, "avatar_url": "", "subscriber_count": "", "error": None}
    handle = channel_handle.lstrip('@')
    channel_url = f"https://www.youtube.com/@{handle}"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'ignoreerrors': True,
        'extractor_args': {
            'youtube': {
                'po_token': ['web.gvs+http://127.0.0.1:4416'],
            }
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            if info:
                result["name"] = info.get('channel', channel_handle)
                thumbnails = info.get('thumbnails', [])
                if thumbnails:
                    result["avatar_url"] = thumbnails[-1].get('url', '')
                subscriber_count = info.get('channel_follower_count', 0)
                if subscriber_count:
                    result["subscriber_count"] = format_number(subscriber_count) + " subscribers"
            else:
                result["error"] = "Channel not found"
    except Exception as e:
        print(f"yt-dlp channel error: {e}")
        result["error"] = str(e)
    return result

def get_preview_info(url: str, view_type: str):
    video_id = extract_video_id(url)
    if not video_id:
        return {"success": False, "error": "Invalid YouTube URL"}
    
    DESKTOP_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"]
    MOBILE_AGENTS = ["Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36"]
    
    if view_type == "Auto/Random":
        return {"success": True, "constructed_url": f"Auto-selected per instance", "user_agent": "Random", "is_mobile": "Random", "video_id": video_id}
    
    if view_type == "Google Search":
        return {"success": True, "constructed_url": f"Via Google Search → {url}", "user_agent": "Random", "is_mobile": "Random", "video_id": video_id}
    
    if view_type in ("Other YouTube features", "Direct/Unknown"):
        is_mobile = True
        ua = random.choice(MOBILE_AGENTS)
    elif view_type == "Suggested":
        is_mobile = False
        ua = random.choice(DESKTOP_AGENTS)
    elif view_type == "Short Feeds":
        is_mobile = random.choice([True, False])
        ua = random.choice(MOBILE_AGENTS if is_mobile else DESKTOP_AGENTS)
    else:
        is_mobile = random.choice([True, False])
        ua = random.choice(MOBILE_AGENTS if is_mobile else DESKTOP_AGENTS)
    
    if view_type == "Other YouTube features":
        constructed_url = f"https://youtu.be/{video_id}"
    elif view_type == "Short Feeds":
        constructed_url = f"https://www.youtube.com/shorts/{video_id}"
    else:
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
    
    return {"success": True, "constructed_url": constructed_url, "user_agent": ua, "is_mobile": is_mobile, "video_id": video_id}

def cleanup_all():
    deleted_files = 0
    deleted_folders = 0
    total_size = 0
    
    if LOG_DIR.exists():
        for log_file in LOG_DIR.glob("*.log"):
            try:
                total_size += log_file.stat().st_size
                log_file.unlink()
                deleted_files += 1
            except:
                pass
    
    for config_file in DATA_DIR.glob("launch_config_*.json"):
        try:
            total_size += config_file.stat().st_size
            config_file.unlink()
            deleted_files += 1
        except:
            pass
    
    for pattern in CACHE_PATTERNS:
        for folder in BASE_DIR.glob(pattern):
            if folder.is_dir():
                try:
                    shutil.rmtree(folder)
                    deleted_folders += 1
                except:
                    pass
        for folder in BASE_DIR.glob(f"*/{pattern}"):
            if folder.is_dir():
                try:
                    shutil.rmtree(folder)
                    deleted_folders += 1
                except:
                    pass
    
    temp_base = os.path.join(tempfile.gettempdir(), "yt_automation")
    if os.path.exists(temp_base):
        try:
            for folder in os.listdir(temp_base):
                folder_path = os.path.join(temp_base, folder)
                if os.path.isdir(folder_path):
                    shutil.rmtree(folder_path)
                    deleted_folders += 1
        except:
            pass
    
    chrome_temp_patterns = [
        os.path.join(tempfile.gettempdir(), "scoped_dir*"),
        os.path.join(tempfile.gettempdir(), "chrome_*"),
        os.path.join(tempfile.gettempdir(), "Crashpad*")
    ]
    
    for pattern in chrome_temp_patterns:
        for folder in glob.glob(pattern):
            if os.path.isdir(folder):
                try:
                    shutil.rmtree(folder)
                    deleted_folders += 1
                except:
                    pass
    
    freed_space_mb = round(total_size / (1024 * 1024), 2)
    return {"deleted_files": deleted_files, "deleted_folders": deleted_folders, "freed_space_mb": freed_space_mb}

# ==================== Proxy Helper Functions ====================

def load_proxy_list():
    proxies = []
    if PROXY_LIST_FILE.exists():
        with open(PROXY_LIST_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            proxies = [line.strip() for line in f if line.strip() and '<' not in line]
    return proxies

def load_blacklist():
    blacklist = []
    if BLACKLIST_FILE.exists():
        with open(BLACKLIST_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            blacklist = [line.strip() for line in f if line.strip()]
    return blacklist

def save_proxy_list(proxies):
    with open(PROXY_LIST_FILE, 'w', encoding='utf-8') as f:
        for proxy in proxies:
            if proxy and '<' not in proxy:
                f.write(f"{proxy}\n")

def save_blacklist(blacklist):
    with open(BLACKLIST_FILE, 'w', encoding='utf-8') as f:
        for proxy in blacklist:
            f.write(f"{proxy}\n")

def get_proxy_for_instance(instance_id, total_instances):
    proxies = load_proxy_list()
    blacklist = load_blacklist()
    available = [p for p in proxies if p not in blacklist]
    
    if not available:
        return None
    
    proxy_index = (instance_id - 1) % len(available)
    return available[proxy_index]

def get_whitelist():
    whitelist_file = DATA_DIR / "whitelist.txt"
    if whitelist_file.exists():
        with open(whitelist_file, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    return []

# ==================== PO Token Helper Functions ====================

def get_po_token_from_potgen(video_id):
    try:
        response = http_requests.post(
            "http://127.0.0.1:4417/get_token",
            json={"videoId": video_id},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('poToken'), data.get('visitorData')
    except Exception as e:
        print(f"Failed to get token from po-token-generator: {e}")
    return None, None

def get_po_token_from_external(video_id):
    try:
        response = http_requests.post(
            "http://127.0.0.1:4416/get_pot",
            json={"video_id": video_id},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('poToken'), data.get('visitorId')
    except Exception as e:
        print(f"Failed to get token from external server: {e}")
    return None, None

# ==================== Proxy API Routes ====================

@app.route('/api/proxy/settings_page')
def proxy_settings_page():
    template_path = BASE_DIR / "templates" / "proxy_settings.html"
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    return "<h1>Proxy settings page not found</h1>"

@app.route('/api/proxy/status', methods=['GET'])
def proxy_status():
    proxies = load_proxy_list()
    blacklist = load_blacklist()
    working = [p for p in proxies if p not in blacklist]
    return jsonify({
        "total_proxies": len(proxies),
        "working_proxies": len(working),
        "blacklisted": len(blacklist)
    })

@app.route('/api/proxy/progress', methods=['GET'])
def proxy_progress_endpoint():
    return jsonify(proxy_progress)

@app.route('/api/proxy/stats', methods=['GET'])
def api_proxy_stats():
    try:
        stats = get_proxy_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/proxy/manual', methods=['GET'])
def proxy_manual():
    return jsonify(load_proxy_list())

@app.route('/api/proxy/manual/add', methods=['POST'])
def proxy_manual_add():
    proxy = request.json.get('proxy')
    if proxy:
        proxies = load_proxy_list()
        if proxy not in proxies:
            proxies.append(proxy)
            save_proxy_list(proxies)
            add_progress_log(f"Added manual proxy: {proxy[:50]}")
    return jsonify({"success": True})

@app.route('/api/proxy/manual/remove', methods=['POST'])
def proxy_manual_remove():
    proxy = request.json.get('proxy')
    if proxy:
        proxies = load_proxy_list()
        if proxy in proxies:
            proxies.remove(proxy)
            save_proxy_list(proxies)
            add_progress_log(f"Removed manual proxy: {proxy[:50]}")
    return jsonify({"success": True})

@app.route('/api/proxy/blacklist', methods=['GET'])
def proxy_blacklist():
    return jsonify(load_blacklist())

@app.route('/api/proxy/blacklist/add', methods=['POST'])
def proxy_blacklist_add():
    proxy = request.json.get('proxy')
    if proxy:
        blacklist = load_blacklist()
        if proxy not in blacklist:
            blacklist.append(proxy)
            save_blacklist(blacklist)
            proxies = load_proxy_list()
            if proxy in proxies:
                proxies.remove(proxy)
                save_proxy_list(proxies)
            add_progress_log(f"Added to blacklist: {proxy[:50]}")
    return jsonify({"success": True})

@app.route('/api/proxy/blacklist/remove', methods=['POST'])
def proxy_blacklist_remove():
    proxy = request.json.get('proxy')
    if proxy:
        blacklist = load_blacklist()
        if proxy in blacklist:
            blacklist.remove(proxy)
            save_blacklist(blacklist)
            add_progress_log(f"Removed from blacklist: {proxy[:50]}")
    return jsonify({"success": True})

@app.route('/api/proxy/working', methods=['GET'])
def proxy_working():
    proxies = load_proxy_list()
    blacklist = load_blacklist()
    working = [p for p in proxies if p not in blacklist]
    return jsonify({"working": working})

@app.route('/api/proxy/clear', methods=['POST'])
def proxy_clear():
    if PROXY_LIST_FILE.exists():
        PROXY_LIST_FILE.unlink()
    if BLACKLIST_FILE.exists():
        BLACKLIST_FILE.unlink()
    add_progress_log("Cleared all proxy data")
    return jsonify({"success": True})

@app.route('/api/proxy/sources', methods=['GET'])
def proxy_sources():
    sources_file = DATA_DIR / "proxy_sources.json"
    if sources_file.exists():
        with open(sources_file, 'r') as f:
            sources = json.load(f)
        return jsonify({"sources": sources})
    return jsonify({"sources": []})

@app.route('/api/proxy/sources/save', methods=['POST'])
def proxy_sources_save():
    sources = request.json.get('sources', [])
    sources_file = DATA_DIR / "proxy_sources.json"
    with open(sources_file, 'w') as f:
        json.dump(sources, f)
    add_progress_log(f"Saved {len(sources)} proxy sources")
    return jsonify({"success": True})

@app.route('/api/proxy/fetch_from_sources', methods=['POST'])
def proxy_fetch_from_sources():
    global proxy_progress
    
    sources = request.json.get('sources', [])
    
    proxy_progress = {
        "status": "fetching",
        "operation": "Fetching proxies from sources",
        "current_source": "",
        "total_sources": len(sources),
        "sources_completed": 0,
        "proxies_found": 0,
        "proxies_tested": 0,
        "proxies_working": 0,
        "proxies_failed": 0,
        "blacklisted": len(load_blacklist()),
        "whitelisted": len(get_whitelist()),
        "total_proxies": 0,
        "percent": 0,
        "last_update": time.time(),
        "logs": []
    }
    
    all_proxies = set()
    
    for idx, source in enumerate(sources):
        protocol = source.get('protocol', 'http')
        url = source.get('url', '')
        
        if not url or not url.startswith('http'):
            continue
        
        proxy_progress["current_source"] = url[:80]
        proxy_progress["sources_completed"] = idx
        proxy_progress["last_update"] = time.time()
        
        add_progress_log(f"📡 Fetching from {protocol.upper()} source {idx+1}/{len(sources)}")
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = http_requests.get(url, timeout=30, headers=headers)
            
            if response.status_code == 200:
                content = response.text
                
                if '<!DOCTYPE html>' in content[:500] or '<html' in content[:500]:
                    add_progress_log(f"   ⚠️ Source returned HTML, skipping", "warning")
                    continue
                
                lines = content.strip().split('\n')
                source_proxies = 0
                
                for line in lines:
                    proxy = line.strip()
                    if not proxy or proxy.startswith('#') or len(proxy) < 5:
                        continue
                    if '<' in proxy or '>' in proxy or 'script' in proxy.lower():
                        continue
                    if '://' not in proxy:
                        proxy = f"{protocol}://{proxy}"
                    
                    host_part = proxy.split('://', 1)[-1].split(':')
                    if len(host_part) == 2 and host_part[0].replace('.', '').replace('-', '').replace(' ', '').isdigit():
                        all_proxies.add(proxy)
                        source_proxies += 1
                        
                        if source_proxies % 100 == 0:
                            proxy_progress["proxies_found"] = len(all_proxies)
                            add_progress_log(f"   ... found {len(all_proxies)} proxies")
                
                add_progress_log(f"   ✅ Found {source_proxies} valid proxies")
            else:
                add_progress_log(f"   ❌ HTTP {response.status_code}", "error")
        except Exception as e:
            add_progress_log(f"   ❌ Error: {str(e)[:80]}", "error")
    
    add_progress_log(f"💾 Saving {len(all_proxies)} proxies...")
    existing = load_proxy_list()
    merged = list(set(existing + list(all_proxies)))
    save_proxy_list(merged)
    
    proxy_progress["status"] = "fetch_complete"
    proxy_progress["proxies_found"] = len(all_proxies)
    add_progress_log(f"✅ Fetch complete: {len(all_proxies)} new, {len(merged)} total")
    
    return jsonify({"total": len(all_proxies), "sources_count": len(sources)})

@app.route('/api/proxy/test_all', methods=['POST'])
def proxy_test_all():
    global proxy_progress
    
    proxies = load_proxy_list()
    
    if not proxies:
        add_progress_log("❌ No proxies to test", "error")
        return jsonify({"working": 0, "failed": 0})
    
    whitelist = get_whitelist()
    blacklist = load_blacklist()
    
    proxy_progress = {
        "status": "testing",
        "operation": "Testing proxies",
        "current_source": "Testing in progress...",
        "total_sources": len(proxies),
        "sources_completed": 0,
        "proxies_found": len(proxies),
        "proxies_tested": 0,
        "proxies_working": 0,
        "proxies_failed": 0,
        "blacklisted": len(blacklist),
        "whitelisted": len(whitelist),
        "total_proxies": len(proxies),
        "percent": 0,
        "last_update": time.time(),
        "logs": []
    }
    
    working = []
    failed = []
    test_url = "https://httpbin.org/ip"
    timeout = 10
    max_workers = 50
    
    add_progress_log(f"🔍 Testing {len(proxies)} proxies with {max_workers} workers")
    
    def test_proxy_with_progress(proxy):
        try:
            proxies_dict = {"http": proxy, "https": proxy}
            start_time = time.time()
            response = http_requests.get(test_url, proxies=proxies_dict, timeout=timeout)
            elapsed = (time.time() - start_time) * 1000
            if response.status_code == 200:
                return proxy, True, elapsed
        except:
            pass
        return proxy, False, None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_proxy_with_progress, proxy): proxy for proxy in proxies}
        
        for idx, future in enumerate(as_completed(futures)):
            proxy, is_working, latency = future.result()
            
            proxy_progress["proxies_tested"] = idx + 1
            proxy_progress["last_update"] = time.time()
            
            if is_working or proxy in whitelist:
                working.append(proxy)
                proxy_progress["proxies_working"] = len(working)
            else:
                failed.append(proxy)
                proxy_progress["proxies_failed"] = len(failed)
            
            update_progress()
            
            if (idx + 1) % 100 == 0 or (idx + 1) == len(proxies):
                add_progress_log(f"📊 Tested {idx+1}/{len(proxies)} | ✅ {len(working)} | ❌ {len(failed)}")
            
            if not is_working and proxy not in whitelist:
                blacklist = load_blacklist()
                if proxy not in blacklist:
                    blacklist.append(proxy)
                    save_blacklist(blacklist)
                    proxy_progress["blacklisted"] = len(blacklist)
    
    save_proxy_list(working)
    
    proxy_progress["status"] = "complete"
    proxy_progress["percent"] = 100
    add_progress_log(f"🎉 Testing Complete! ✅ {len(working)} working, ❌ {len(failed)} failed")
    
    return jsonify({"working": len(working), "failed": len(failed)})

@app.route('/api/proxy/test/single', methods=['POST'])
def proxy_test_single():
    proxy = request.json.get('proxy')
    try:
        proxies_dict = {"http": proxy, "https": proxy}
        response = http_requests.get("https://httpbin.org/ip", proxies=proxies_dict, timeout=10)
        if response.status_code == 200:
            return jsonify({"working": True})
    except:
        pass
    return jsonify({"working": False})

# ==================== Cache API Routes ====================

@app.route('/api/cache/stats', methods=['GET'])
def api_cache_stats():
    return jsonify(get_cache_stats())

@app.route('/api/cache/clear', methods=['POST'])
def api_cache_clear():
    data = request.json
    if data.get('expired_only', False):
        deleted = clear_expired_cache()
        return jsonify({"success": True, "deleted": deleted, "message": "Cleared expired cache"})
    else:
        deleted = clear_all_cache()
        return jsonify({"success": True, "deleted": deleted, "message": "Cleared all cache"})

@app.route('/api/cache/thumbnail/<video_id>', methods=['GET'])
def api_get_thumbnail(video_id):
    thumbnail_data = get_cached_video_thumbnail(video_id)
    if thumbnail_data:
        return send_file(io.BytesIO(thumbnail_data), mimetype='image/jpeg')
    return jsonify({"error": "Thumbnail not found"}), 404

@app.route('/api/cache/logo/<channel_name>', methods=['GET'])
def api_get_logo(channel_name):
    logo_data = get_cached_channel_logo(channel_name)
    if logo_data:
        return send_file(io.BytesIO(logo_data), mimetype='image/jpeg')
    return jsonify({"error": "Logo not found"}), 404

# ==================== PO Token API Routes ====================

@app.route('/api/get_po_token', methods=['POST'])
def api_get_po_token():
    data = request.json
    video_id = data.get('video_id')
    source = data.get('source', 'native')
    
    if source == 'native':
        return jsonify({"success": True, "message": "Native browser generation"})
    elif source == 'external':
        po_token, visitor_id = get_po_token_from_external(video_id)
        if po_token:
            return jsonify({"success": True, "poToken": po_token, "visitorId": visitor_id})
        return jsonify({"success": False, "error": "External server unavailable"})
    elif source == 'potgen':
        po_token, visitor_id = get_po_token_from_potgen(video_id)
        if po_token:
            return jsonify({"success": True, "poToken": po_token, "visitorId": visitor_id})
        return jsonify({"success": False, "error": "po-token-generator service unavailable"})
    
    return jsonify({"success": False, "error": "Invalid source"})

# ==================== Main Flask Routes ====================

@app.route('/')
def dashboard():
    return render_template('dash.html')

@app.route('/api/save_config', methods=['POST'])
def api_save_config():
    data = request.json
    # Ensure channel_name is preserved
    if 'channel_name' not in data:
        # Load existing config to preserve channel
        existing = load_config()
        if 'channel_name' in existing:
            data['channel_name'] = existing['channel_name']
    save_config(data)
    return jsonify({"success": True})

# Add/Update these endpoints in YTDash.py

@app.route('/api/save_channel', methods=['POST'])
def api_save_channel():
    channel_name = request.json.get('channel_name', '')
    print(f"[DEBUG] Saving channel: '{channel_name}'")
    config = load_config()
    config['channel_name'] = channel_name
    save_config(config)
    # Verify it saved
    verify = load_config()
    print(f"[DEBUG] Verified channel in config: '{verify.get('channel_name', '')}'")
    return jsonify({"success": True, "channel_name": channel_name})

@app.route('/api/load_config')
def api_load_config():
    config = load_config()
    if 'channel_name' not in config:
        config['channel_name'] = ''
    print(f"[DEBUG] Loading config - channel: '{config.get('channel_name', '')}'")
    return jsonify(config)

@app.route('/api/auto_fetch_channel', methods=['POST'])
def api_auto_fetch_channel():
    handle = request.json.get('handle', '')
    if not handle:
        return jsonify({'success': False, 'error': 'No handle provided'})
    
    clean_handle = handle.lstrip('@')
    
    # Try to load from cache first
    cached = get_cached_channel_info(clean_handle)
    if cached:
        print(f"[Cache] Loaded channel for @{clean_handle} from cache")
        return jsonify({"success": True, **cached})
    
    # Fetch from YouTube
    result = get_channel_info_ytdlp(clean_handle)
    if result.get('name'):
        cache_channel_info(clean_handle, result)
        avatar_url = result.get('avatar_url')
        if avatar_url:
            try:
                cache_channel_logo(clean_handle, avatar_url)
            except:
                pass
        return jsonify({"success": True, **result})
    
    return jsonify({"success": False, "error": "Channel not found"})

@app.route('/api/auto_fetch_video', methods=['POST'])
def api_auto_fetch_video():
    url = request.json.get('url', '')
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'})
    
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'success': False, 'error': 'Invalid YouTube URL'})
    
    cached = get_cached_video_info(video_id)
    if cached:
        return jsonify(cached)
    
    result = get_video_details_ytdlp(url)
    if result.get('success'):
        cache_video_info(video_id, result)
        thumbnail_url = result.get('thumbnail_url')
        if thumbnail_url:
            try:
                cache_video_thumbnail(video_id, thumbnail_url)
            except:
                pass
    return jsonify(result)


@app.route('/api/get_video_details', methods=['POST'])
def api_get_video_details():
    url = request.json.get('url', '')
    force_refresh = request.json.get('force_refresh', False)
    
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'success': False, 'error': 'Invalid YouTube URL'})
    
    if not force_refresh:
        cached = get_cached_video_info(video_id)
        if cached:
            return jsonify(cached)
    
    result = get_video_details_ytdlp(url)
    if result.get('success'):
        cache_video_info(video_id, result)
        thumbnail_url = result.get('thumbnail_url')
        if thumbnail_url:
            try:
                cache_video_thumbnail(video_id, thumbnail_url)
            except:
                pass
    return jsonify(result)

@app.route('/api/get_channel_info', methods=['POST'])
def api_get_channel_info():
    handle = request.json.get('handle', '')
    force_refresh = request.json.get('force_refresh', False)
    
    if not handle:
        return jsonify({"success": False, "error": "No channel handle provided"})
    
    clean_handle = handle.lstrip('@')
    
    if not force_refresh:
        cached = get_cached_channel_info(clean_handle)
        if cached:
            return jsonify({"success": True, **cached})
    
    result = get_channel_info_ytdlp(clean_handle)
    cache_channel_info(clean_handle, result)
    avatar_url = result.get('avatar_url')
    if avatar_url:
        try:
            cache_channel_logo(clean_handle, avatar_url)
        except:
            pass
    
    return jsonify({"success": True, **result})

@app.route('/api/get_view_types_by_type', methods=['POST'])
def api_get_view_types_by_type():
    """Return view types based on is_short flag from yt-dlp."""
    is_short = request.json.get('is_short', False)
    if is_short:
        view_types = ["Auto/Random", "Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        view_types = ["Auto/Random", "Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    return jsonify({"view_types": view_types})

@app.route('/api/detect_view_types', methods=['POST'])
def api_detect_view_types():
    urls = request.json.get('urls', [])
    if not urls:
        return jsonify({"view_types": []})
    if '/shorts/' in urls[0]:
        return jsonify({"view_types": ["Auto/Random", "Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]})
    else:
        return jsonify({"view_types": ["Auto/Random", "Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]})

@app.route('/api/validate_view_type', methods=['POST'])
def api_validate_view_type():
    url = request.json.get('url', '')
    view_type = request.json.get('view_type', '')
    
    if view_type in ("Auto/Random", "Google Search"):
        return jsonify({"valid": True})
    
    details = get_video_details_ytdlp(url)
    if not details.get('success'):
        return jsonify({"valid": False, "error": details.get('error', 'Could not determine video type')})
    
    is_short = details.get('is_short', False)
    
    if is_short:
        valid_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        valid_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    
    return jsonify({"valid": view_type in valid_types})

@app.route('/api/preview', methods=['POST'])
def api_preview():
    url = request.json.get('url', '')
    view_type = request.json.get('view_type', '')
    info = get_preview_info(url, view_type)
    return jsonify(info)

@app.route('/api/cleanup', methods=['POST'])
def api_cleanup():
    """Run full cleanup - handles both JSON and empty requests"""
    try:
        # Try to get dry_run from JSON if present, otherwise default to False
        dry_run = False
        if request.is_json:
            data = request.get_json()
            dry_run = data.get('dry_run', False)
        
        results = clean_all(dry_run=dry_run)
        
        return jsonify({
            "success": True,
            "dry_run": dry_run,
            "deleted_files": results['total']['deleted'],
            "deleted_folders": results.get('cache_folders', {}).get('deleted_folders', 0),
            "freed_space_mb": round(results['total']['size_bytes'] / (1024 * 1024), 2),
            "freed_space_human": results['total']['size_human']
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/launch', methods=['POST'])
@app.route('/api/launch', methods=['POST'])
def api_launch():
    data = request.json
    view_type = data['view_type']
    automation_version = data.get('automation_version', 'selenium')
    url = data['urls'][0]
    cycles = data.get('cycles', 1)
    num_instances = data.get('num_instances', 1)
    traffic_source = data.get('traffic_source', 'direct')
    proxy_mode = data.get('proxy_mode', 'none')
    po_token_source = data.get('po_token_source', 'native')
    
    # Determine if it's a short from local cache (no yt-dlp)
    video_id = extract_video_id(url)
    is_short = None
    if video_id:
        cached = get_cached_video_info(video_id)
        if cached and cached.get('success'):
            is_short = cached.get('is_short', False)
            print(f"[DEBUG] Using cached is_short for {video_id}: {is_short}")
        else:
            # Fallback: detect from URL
            is_short = '/shorts/' in url
            print(f"[DEBUG] Cache miss, using URL detection for {video_id}: {is_short}")
    else:
        # No video ID, fallback to URL detection
        is_short = '/shorts/' in url
        print(f"[DEBUG] No video ID, using URL detection: {is_short}")
    
    if cycles < 1:
        return jsonify({"success": False, "error": "Cycles must be at least 1"})
    
    # Define valid view types based on is_short
    if is_short:
        available_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        available_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    
    # Validate view_type
    if view_type not in ["Auto/Random", "Google Search"] and view_type not in available_types:
        return jsonify({"success": False, "error": f"View type '{view_type}' not valid for this video"})
    
    view_to_script = {
        "Google Search": "YTGoogleSearch.py",
        "Other YouTube features": "YTDirect.py",
        "Direct/Unknown": "YTDirect.py",
        "Suggested": "YTDirect.py",
        "Search (Video)": "YTSearch.py",
        "Short Feeds": "YTShort.py",
        "Channel View": "YTChannel.py",
    }
    
    referer_map = {
        'whatsapp_web': 'https://web.whatsapp.com/',
        'instagram': 'https://www.instagram.com/',
        'telegram_web': 'https://web.telegram.org/',
        'github': 'https://github.io/',
        'bing': 'https://www.bing.com/',
        'twitter': 'https://twitter.com/',
        'reddit': 'https://www.reddit.com/',
        'facebook': 'https://www.facebook.com/',
        'linkedin': 'https://www.linkedin.com/',
    }
    
    direct_url_view_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds"]
    launched_total = 0
    use_undetected = (automation_version == 'selenium_undetected')
    
    # Log proxy mode
    if proxy_mode == 'tor_service':
        print(f"[PROXY] Using Tor Service on port 9050")
    elif proxy_mode == 'tor_browser':
        print(f"[PROXY] Using Tor Browser on port 9150")
    elif proxy_mode == 'list':
        proxies = load_proxy_list()
        blacklist = load_blacklist()
        available_proxies = [p for p in proxies if p not in blacklist]
        print(f"[PROXY] Using rotating proxy list with {len(available_proxies)} available proxies")
    else:
        print(f"[PROXY] No proxy - direct connection")
    
    # ========== CYCLE LOOP ==========
    for cycle in range(1, cycles + 1):
        print(f"[DEBUG] ========================================")
        print(f"[DEBUG] Starting Cycle {cycle}/{cycles} at {time.strftime('%H:%M:%S')}")
        print(f"[DEBUG] ========================================")
        
        cycle_processes = []
        cycle_configs = []
        
        for i in range(num_instances):
            instance_id = (cycle - 1) * num_instances + i + 1
            url = data['urls'][i % len(data['urls'])]
            
            if view_type == "Auto/Random":
                selected_view_type = random.choice(available_types + ["Google Search"])
                is_auto_random = True
            else:
                selected_view_type = view_type
                is_auto_random = False
            
            cfg = build_script_config(instance_id, data, url, selected_view_type)
            if 'video_title' in data:
                cfg['video_title'] = data['video_title']
            cfg['is_auto_random'] = is_auto_random
            cfg['available_view_types'] = available_types if is_auto_random else []
            cfg['cycle_number'] = cycle
            cfg['cycles'] = 1
            cfg['traffic_source'] = traffic_source
            cfg['po_token_source'] = po_token_source
            cfg['proxy_mode'] = proxy_mode
            cfg['num_instances'] = num_instances
            cfg['is_short'] = is_short   # pass to child scripts if needed
            
            if proxy_mode == 'list':
                rotating_proxy = get_rotating_proxy()
                if rotating_proxy:
                    cfg['proxy'] = rotating_proxy
                    cfg['proxy_mode'] = 'single'
                    print(f"[PROXY] Instance {instance_id} assigned rotating proxy: {rotating_proxy[:60]}")
                else:
                    manual_proxy = get_proxy_for_instance(instance_id, num_instances)
                    if manual_proxy:
                        cfg['proxy'] = manual_proxy
                        print(f"[PROXY] Instance {instance_id} assigned manual proxy (fallback): {manual_proxy[:60]}")
                    else:
                        print(f"[PROXY] WARNING: No proxy available for instance {instance_id}")
            
            if use_undetected:
                cfg['use_undetected'] = True
                cfg['automation_version'] = 'selenium_undetected'
            
            if selected_view_type in direct_url_view_types and traffic_source != 'direct' and traffic_source in referer_map:
                cfg['referer'] = referer_map[traffic_source]
            
            cycle_configs.append(cfg)
        
        script_groups = defaultdict(list)
        for cfg in cycle_configs:
            script_file = view_to_script.get(cfg['view_type'], "YTDirect.py")
            script_groups[script_file].append(cfg)
        
        for script_file, group_configs in script_groups.items():
            if group_configs:
                timestamp = int(time.time())
                group_temp_file = DATA_DIR / f"launch_config_cycle{cycle}_{script_file}_{timestamp}.json"
                try:
                    with open(group_temp_file, 'w', encoding='utf-8') as f:
                        json.dump(group_configs, f, indent=2, ensure_ascii=False)
                    with open(group_temp_file, 'r', encoding='utf-8') as f:
                        if not json.load(f):
                            raise ValueError("Config file is empty")
                    print(f"[DEBUG] Config file written: {group_temp_file.name}")
                except Exception as e:
                    print(f"[ERROR] Failed to write config file: {e}")
                    continue
                
                if automation_version == 'playwright':
                    script_path = BASE_DIR / "playwright" / "scripts" / script_file
                else:
                    script_path = BASE_DIR / "selenium" / "scripts" / script_file
                
                if script_path.exists():
                    cmd = [sys.executable, str(script_path), str(group_temp_file)]
                    print(f"[LAUNCH] {script_path.name} with {len(group_configs)} instance(s)")
                    if sys.platform == "win32":
                        proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        proc = subprocess.Popen(cmd)
                    cycle_processes.append(proc)
                    launched_total += len(group_configs)
                    print(f"[DEBUG] Process launched with PID: {proc.pid}")
                else:
                    print(f"[WARNING] Script not found: {script_path}")
        
        if cycle_processes:
            print(f"[DEBUG] Cycle {cycle}: Waiting for {len(cycle_processes)} process(es) to complete...")
            for idx, proc in enumerate(cycle_processes):
                print(f"[DEBUG] Waiting for process {idx+1}/{len(cycle_processes)} (PID: {proc.pid})...")
                while True:
                    ret = proc.poll()
                    if ret is not None:
                        print(f"[DEBUG] Process {proc.pid} completed with exit code: {ret}")
                        break
                    time.sleep(2)
                    # print(f"[DEBUG] Process {proc.pid} still running...")  # Commented out
            print(f"[DEBUG] Cycle {cycle} completed at {time.strftime('%H:%M:%S')}")
        else:
            print(f"[DEBUG] Cycle {cycle}: No processes to wait for")
        
        if cycle < cycles:
            wait_time = random.uniform(5, 10)
            print(f"[DEBUG] Waiting {wait_time:.1f}s before starting Cycle {cycle + 1}...")
            time.sleep(wait_time)
    
    # Build status message
    proxy_msg = ""
    if proxy_mode == 'tor_service':
        proxy_msg = " Proxy: Tor Service (port 9050)"
    elif proxy_mode == 'tor_browser':
        proxy_msg = " Proxy: Tor Browser (port 9150)"
    elif proxy_mode == 'list':
        proxy_msg = " Proxy: Rotating from dynamic pool"
    else:
        proxy_msg = " Proxy: None (Direct)"
    
    stealth_msg = " (Undetected Stealth Mode)" if use_undetected else ""
    
    if po_token_source == 'native':
        po_msg = " PO Token: Native Browser"
    elif po_token_source == 'external':
        po_msg = " PO Token: External Server (bgutil)"
    else:
        po_msg = " PO Token: po-token-generator (Node.js)"
    
    print(f"[DEBUG] ========================================")
    print(f"[DEBUG] ALL CYCLES COMPLETED at {time.strftime('%H:%M:%S')}")
    print(f"[DEBUG] Total sessions launched: {launched_total}")
    print(f"[DEBUG] ========================================")
    
    return jsonify({"success": True, "message": f"Completed {cycles} cycle(s) with {num_instances} instance(s) each. Total {launched_total} sessions.{po_msg}{proxy_msg}{stealth_msg}"})
    
    
def open_browser():
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    print("=" * 60)
    print("YouTube Automation Dashboard")
    print("=" * 60)
    print(f"Dashboard URL: http://127.0.0.1:5000")
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
    print(f"Log directory: {LOG_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print("\n🔐 PO Token Sources Available:")
    print("   🌿 Native Browser")
    print("   🖥️ External Server (bgutil, port 4416)")
    print("   🤖 po-token-generator (Node.js, port 4417)")
    print("\n🔌 Proxy Modes Available:")
    print("   🚫 No Proxy")
    print("   🌐 Tor Service (port 9050)")
    print("   🌐 Tor Browser (port 9150)")
    print("   🔄 Rotating Proxy")
    print("\n💾 Cache System Active")
    print("=" * 60)
    
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=False)