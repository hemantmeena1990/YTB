#!/usr/bin/env python3
"""
YouTube Automation Dashboard – Backend Only
HTML template is in templates/dash.html
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
from flask import Flask, render_template, request, jsonify

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
    result = {"name": channel_handle, "avatar_url": "", "subscriber_count": ""}
    handle = channel_handle.lstrip('@')
    channel_url = f"https://www.youtube.com/@{handle}"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
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
    except Exception as e:
        print(f"yt-dlp channel error: {e}")
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
        with open(PROXY_LIST_FILE, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
    return proxies

def load_blacklist():
    blacklist = []
    if BLACKLIST_FILE.exists():
        with open(BLACKLIST_FILE, 'r') as f:
            blacklist = [line.strip() for line in f if line.strip()]
    return blacklist

def save_proxy_list(proxies):
    with open(PROXY_LIST_FILE, 'w') as f:
        for proxy in proxies:
            f.write(f"{proxy}\n")

def save_blacklist(blacklist):
    with open(BLACKLIST_FILE, 'w') as f:
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

# ==================== PO Token Helper Functions ====================

def get_po_token_from_potgen(video_id):
    """Get PO token from po-token-generator service (port 4417)"""
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
    """Get PO token from external bgutil server (port 4416)"""
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
            return f.read()
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
    return jsonify({"success": True})

@app.route('/api/proxy/manual/remove', methods=['POST'])
def proxy_manual_remove():
    proxy = request.json.get('proxy')
    if proxy:
        proxies = load_proxy_list()
        if proxy in proxies:
            proxies.remove(proxy)
            save_proxy_list(proxies)
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
    return jsonify({"success": True})

@app.route('/api/proxy/blacklist/remove', methods=['POST'])
def proxy_blacklist_remove():
    proxy = request.json.get('proxy')
    if proxy:
        blacklist = load_blacklist()
        if proxy in blacklist:
            blacklist.remove(proxy)
            save_blacklist(blacklist)
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
    return jsonify({"success": True})

@app.route('/api/proxy/fetch_from_sources', methods=['POST'])
def proxy_fetch_from_sources():
    sources = request.json.get('sources', [])
    all_proxies = set()
    
    for source in sources:
        protocol = source.get('protocol', 'http')
        url = source.get('url')
        try:
            response = http_requests.get(url, timeout=30)
            if response.status_code == 200:
                lines = response.text.splitlines()
                for line in lines:
                    proxy = line.strip()
                    if proxy and not proxy.startswith('#'):
                        if '://' not in proxy:
                            proxy = f"{protocol}://{proxy}"
                        all_proxies.add(proxy)
        except Exception as e:
            print(f"Failed to fetch from {url}: {e}")
    
    existing = load_proxy_list()
    new_proxies = list(all_proxies)
    merged = list(set(existing + new_proxies))
    save_proxy_list(merged)
    
    return jsonify({"total": len(new_proxies), "sources_count": len(sources)})

@app.route('/api/proxy/test_all', methods=['POST'])
def proxy_test_all():
    proxies = load_proxy_list()
    blacklist = load_blacklist()
    working = []
    failed = []
    
    test_url = "https://httpbin.org/ip"
    timeout = 10
    
    def test_proxy(proxy):
        try:
            proxies_dict = {"http": proxy, "https": proxy}
            response = http_requests.get(test_url, proxies=proxies_dict, timeout=timeout)
            if response.status_code == 200:
                return proxy, True
        except:
            pass
        return proxy, False
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_proxy, proxy): proxy for proxy in proxies}
        for future in as_completed(futures):
            proxy, is_working = future.result()
            if is_working:
                working.append(proxy)
            else:
                failed.append(proxy)
    
    new_blacklist = list(set(blacklist + failed))
    save_blacklist(new_blacklist)
    save_proxy_list(working)
    
    return jsonify({"working": len(working), "failed": len(failed)})

@app.route('/api/proxy/test/single', methods=['POST'])
def proxy_test_single():
    proxy = request.json.get('proxy')
    try:
        proxies_dict = {"http": proxy, "https": proxy}
        response = http_requests.get("https://httpbin.org/ip", proxies=proxies_dict, timeout=10)
        if response.status_code == 200:
            return jsonify({"working": True, "response_time": 100})
    except:
        pass
    return jsonify({"working": False})

# ==================== PO Token API Routes ====================

@app.route('/api/get_po_token', methods=['POST'])
def api_get_po_token():
    """Get PO token from selected source"""
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

@app.route('/api/get_channel_info', methods=['POST'])
def api_get_channel_info():
    handle = request.json.get('handle', '')
    info = get_channel_info_ytdlp(handle)
    return jsonify({"success": True, **info})

@app.route('/api/save_config', methods=['POST'])
def api_save_config():
    save_config(request.json)
    return jsonify({"success": True})

@app.route('/api/load_config')
def api_load_config():
    return jsonify(load_config())

@app.route('/api/get_video_details', methods=['POST'])
def api_get_video_details():
    url = request.json.get('url', '')
    result = get_video_details_ytdlp(url)
    return jsonify(result)

@app.route('/api/get_view_types_by_type', methods=['POST'])
def api_get_view_types_by_type():
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
    try:
        result = cleanup_all()
        return jsonify({"success": True, "deleted_files": result["deleted_files"], "deleted_folders": result["deleted_folders"], "freed_space_mb": result.get("freed_space_mb", 0)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

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
    
    if cycles < 1:
        return jsonify({"success": False, "error": "Cycles must be at least 1"})
    
    details = get_video_details_ytdlp(url)
    if not details.get('success'):
        return jsonify({"success": False, "error": f"Could not validate video: {details.get('error', 'Unknown error')}"})
    
    is_short = details.get('is_short', False)
    
    if is_short:
        available_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        available_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    
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
        print(f"[PROXY] Using proxy list with {len(available_proxies)} working proxies")
    else:
        print(f"[PROXY] No proxy - direct connection")
    
    for cycle in range(1, cycles + 1):
        print(f"[DEBUG] Starting Cycle {cycle}/{cycles}")
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
            cfg['is_auto_random'] = is_auto_random
            cfg['available_view_types'] = available_types if is_auto_random else []
            cfg['cycle_number'] = cycle
            cfg['traffic_source'] = traffic_source
            cfg['po_token_source'] = po_token_source
            cfg['proxy_mode'] = proxy_mode
            cfg['num_instances'] = num_instances
            
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
                group_temp_file = DATA_DIR / f"launch_config_cycle{cycle}_{script_file}_{int(time.time())}.json"
                with open(group_temp_file, 'w') as f:
                    json.dump(group_configs, f, indent=2)
                
                if automation_version == 'playwright':
                    script_path = BASE_DIR / "playwright" / "scripts" / script_file
                else:
                    script_path = BASE_DIR / "selenium" / "scripts" / script_file
                
                if script_path.exists():
                    cmd = [sys.executable, str(script_path), str(group_temp_file)]
                    if sys.platform == "win32":
                        proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        proc = subprocess.Popen(cmd)
                    cycle_processes.append(proc)
                    launched_total += len(group_configs)
                else:
                    print(f"[WARNING] Script not found: {script_path}")
        
        for proc in cycle_processes:
            proc.wait()
        
        print(f"[DEBUG] Cycle {cycle} completed")
        
        if cycle < cycles:
            time.sleep(random.uniform(5, 10))
    
    # Build status message
    proxy_msg = ""
    if proxy_mode == 'tor_service':
        proxy_msg = " Proxy: Tor Service (port 9050)"
    elif proxy_mode == 'tor_browser':
        proxy_msg = " Proxy: Tor Browser (port 9150)"
    elif proxy_mode == 'list':
        working_count = len([p for p in load_proxy_list() if p not in load_blacklist()])
        proxy_msg = f" Proxy: Rotating from list ({working_count} proxies available)"
    else:
        proxy_msg = " Proxy: None (Direct)"
    
    stealth_msg = " (Undetected Stealth Mode)" if use_undetected else ""
    
    if po_token_source == 'native':
        po_msg = " PO Token: Native Browser"
    elif po_token_source == 'external':
        po_msg = " PO Token: External Server (bgutil)"
    else:
        po_msg = " PO Token: po-token-generator (Node.js)"
    
    return jsonify({"success": True, "message": f"Completed {cycles} cycle(s) with {num_instances} instance(s) each. Total {launched_total} sessions. Traffic source: {traffic_source}.{po_msg}{proxy_msg}{stealth_msg}"})

def open_browser():
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    print("Starting YouTube Automation Dashboard at http://127.0.0.1:5000")
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
    print(f"Log directory: {LOG_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print("\n🔐 PO Token Sources Available:")
    print("   🌿 Native Browser - YouTube generates token via embedded player")
    print("   🖥️ External Server - bgutil on port 4416")
    print("   🤖 po-token-generator - Node.js service on port 4417")
    print("\n🔌 Proxy Modes Available:")
    print("   🚫 No Proxy - Direct connection")
    print("   🌐 Tor Service - Tor service on port 9050")
    print("   🌐 Tor Browser - Tor Browser on port 9150")
    print("   🔄 Proxy List - Rotating proxies from proxy_list.txt")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=False)