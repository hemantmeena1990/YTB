#!/usr/bin/env python3
"""
YouTube Automation Dashboard – Enhanced Two-Column Layout
Features:
- Left column: all input fields + video title/ID/duration
- Right column: Save/Load buttons, channel avatar, thumbnail + video type badge
- Video statistics (views, likes, comments, upload date) below thumbnail
- Subscriber count below channel info
- Selenium/Playwright selector
- Uses yt-dlp for accurate video info
"""

import sys
import json
import webbrowser
import threading
import time
import shutil
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify

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
    extract_video_id
)

app = Flask(__name__)

# Ensure data directory exists
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LOG_DIR = DATA_DIR / "logs"
CACHE_PATTERNS = ["yt_direct_cache_*", "yt_search_cache_*", "yt_channel_cache_*", "yt_shorts_cache_*", "yt_ss_cache_*"]

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Automation Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', sans-serif; background: #1e1e2f; padding: 20px; color: #eee; }
        .dashboard-container { display: flex; gap: 20px; max-width: 1600px; margin: 0 auto; }
        .main-content { flex: 1; min-width: 0; }
        .sidebar { width: 35%; min-width: 300px; }
        .card { background: #2d2d3a; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
        h1 { font-size: 1.6rem; margin: 0; }
        h2 { font-size: 1.2rem; margin-bottom: 15px; color: #a1a1aa; }
        label { display: block; margin: 10px 0 5px; font-weight: bold; font-size: 0.85rem; }
        input, select, textarea { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #555; background: #3a3a4a; color: #fff; }
        button { background: #4f46e5; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #6366f1; }
        .btn-danger { background: #dc2626; }
        .btn-danger:hover { background: #b91c1c; }
        .btn-success { background: #10b981; }
        .btn-success:hover { background: #059669; }
        .btn-secondary { background: #6b7280; }
        .btn-secondary:hover { background: #4b5563; }
        .row { display: flex; gap: 15px; flex-wrap: wrap; }
        .row .form-group { flex: 1; min-width: 120px; }
        .console { background: #0f0f17; border-radius: 8px; padding: 12px; font-family: monospace; font-size: 0.75rem; height: calc(100vh - 200px); overflow-y: auto; }
        .log { border-left: 3px solid #4f46e5; padding: 4px 8px; margin: 4px 0; word-break: break-word; }
        .log-error { border-left-color: #dc2626; color: #fca5a5; }
        .log-success { border-left-color: #10b981; }
        .log-warning { border-left-color: #f59e0b; }
        .preview-card { background: #1e1e2f; border: 1px solid #4f46e5; border-radius: 8px; padding: 12px; margin-top: 15px; }
        .preview-card h4 { margin-bottom: 8px; color: #4f46e5; font-size: 0.9rem; }
        .info-text { font-family: monospace; font-size: 0.75rem; color: #a1a1aa; word-break: break-all; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: bold; }
        .badge-short { background: #dc2626; color: white; }
        .badge-video { background: #10b981; color: white; }
        .flex-between { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .button-group { display: flex; gap: 10px; flex-wrap: wrap; }
        hr { border-color: #3a3a4a; margin: 15px 0; }
        .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #4f46e5; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; margin-left: 10px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { color: #a1a1aa; font-size: 0.75rem; margin-left: 10px; }
        
        /* Right column - fixed width matching button group */
        .right-column {
            flex: 0 0 auto;
            width: 220px;
        }
        
        /* Channel avatar and thumbnail containers - full width of right column */
        #channelAvatar, #thumbnailContainer {
            width: 100%;
            box-sizing: border-box;
        }
        
        /* Ensure buttons are side by side with proper spacing */
        .right-buttons {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-bottom: 20px;
        }
        
        .right-buttons button {
            flex: 1;
            min-width: 80px;
            text-align: center;
        }
        
        /* Video stats styling */
        .video-stats {
            background: #1e1e2f;
            border-radius: 8px;
            padding: 10px;
            margin-top: 10px;
            font-size: 0.7rem;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 6px;
        }
        .stat-label {
            color: #a1a1aa;
        }
        .stat-value {
            color: #4f46e5;
            font-weight: bold;
        }
        
        /* Subscriber count styling */
        .subscriber-count {
            font-size: 0.7rem;
            color: #10b981;
            margin-top: 4px;
        }
    </style>
</head>
<body>
<div class="dashboard-container">
    <!-- Main Content Area -->
    <div class="main-content">
        <div class="flex-between" style="margin-bottom: 20px;">
            <h1>🎬 YouTube Automation Dashboard</h1>
            <div class="button-group">
                <select id="automation_version" style="width: auto; background: #3a3a4a; padding: 8px 12px;">
                    <option value="selenium">🐍 Selenium (Stable)</option>
                    <option value="playwright">🎭 Playwright (Experimental)</option>
                </select>
                <button class="btn-secondary" onclick="clearConsole()" style="background:#6b7280;">🗑️ Clear Console</button>
                <button class="btn-danger" onclick="cleanupAll()" style="background:#dc2626;">🧹 Cleanup All</button>
            </div>
        </div>

        <!-- Configuration Card - Two Column Layout -->
        <div class="card">
            <div class="card-header">
                <h2>📝 Configuration</h2>
            </div>
            
            <!-- Two column layout -->
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <!-- LEFT COLUMN -->
                <div style="flex: 1; min-width: 300px;">
                    <!-- Channel Name -->
                    <div class="form-group">
                        <label>📢 Channel Name/Handle</label>
                        <input type="text" id="channel_name" placeholder="rajasthanidesidiaries or @handle">
                    </div>
                    
                    <!-- YouTube URL -->
                    <div class="form-group">
                        <label>🔗 YouTube URL</label>
                        <input type="text" id="urlInput" placeholder="https://youtube.com/watch?v=... or https://youtube.com/shorts/...">
                    </div>
                    
                    <hr>
                    
                    <!-- Video Info (Title, ID, Duration) - Left side -->
                    <div id="videoInfoDisplay" style="background: #1e1e2f; border-radius: 8px; padding: 12px; margin-bottom: 15px; display: none;">
                        <h3 id="videoTitle" style="margin-bottom: 8px; color: #4f46e5; font-size: 0.95rem;">-</h3>
                        <p><strong>🆔 Video ID:</strong> <span id="videoId">-</span></p>
                        <p><strong>⏱️ Duration:</strong> <span id="videoDuration">-</span> seconds</p>
                    </div>
                    
                    <!-- Instance Settings -->
                    <div class="row">
                        <div class="form-group"><label>📊 Instances</label><input type="number" id="num_instances" value="1" min="1" max="10"></div>
                        <div class="form-group"><label>🔄 Cycles (0=∞)</label><input type="number" id="cycles" value="1" min="0"></div>
                        <div class="form-group"><label>🎭 Headless</label><select id="headless"><option value="false">No</option><option value="true">Yes</option></select></div>
                    </div>
                    
                    <div class="row">
                        <div class="form-group"><label>⏱️ Min watch (s)</label><input type="number" id="min_watch" value="15"></div>
                        <div class="form-group"><label>⏱️ Max watch (s)</label><input type="number" id="max_watch" value="30"></div>
                        <div class="form-group"><label>⏭️ Next Suggested min</label><input type="number" id="suggested_min" value="15"></div>
                        <div class="form-group"><label>⏭️ Next Suggested max</label><input type="number" id="suggested_max" value="35"></div>
                    </div>
                    
                    <div class="row">
                        <div class="form-group"><label>🎲 Next Suggested chance (%)</label><input type="range" id="suggested_chance" min="0" max="100" value="40"><span id="chance_val">40%</span></div>
                        <div class="form-group"><label>🔌 Use Proxy</label><select id="use_proxy"><option value="false">No</option><option value="true">Yes</option></select></div>
                        <div class="form-group"><label>🌐 Custom Proxy URL</label><input type="text" id="proxy_url" placeholder="socks5://127.0.0.1:9050"></div>
                    </div>
                </div>
                
                <!-- RIGHT COLUMN: Fixed width matching button group -->
                <div class="right-column">
                    <!-- Save/Load buttons -->
                    <div class="right-buttons">
                        <button onclick="saveConfig()">💾 Save</button>
                        <button onclick="loadConfig()">📂 Load</button>
                    </div>
                    
                    <!-- Channel Avatar & Name -->
                    <div id="channelAvatar" style="display: none; background: #1e1e2f; border-radius: 12px; padding: 12px; margin-bottom: 15px; text-align: center;">
                        <img id="channelAvatarImg" src="" alt="" style="width: 50px; height: 50px; border-radius: 50%; margin-bottom: 8px;">
                        <div>
                            <span id="channelDisplayName" style="font-weight: bold; font-size: 0.85rem; display: block;">-</span>
                            <small id="channelHandle" style="color: #a1a1aa; font-size: 0.7rem;">-</small>
                            <div id="subscriberCount" class="subscriber-count">-</div>
                        </div>
                    </div>
                    
                    <!-- Thumbnail + Video Type Badge + Stats -->
                    <div id="thumbnailContainer" style="display: none; background: #1e1e2f; border-radius: 12px; padding: 12px; text-align: center;">
                        <img id="videoThumbnail" src="" alt="Thumbnail" style="width: 100%; max-width: 160px; border-radius: 6px; margin-bottom: 8px;">
                        <div id="videoTypeBadgeContainer" style="margin-top: 5px;"></div>
                        
                        <!-- Video Statistics -->
                        <div id="videoStats" class="video-stats" style="display: none;">
                            <div class="stat-row">
                                <span class="stat-label">👁️ Views:</span>
                                <span class="stat-value" id="viewCount">-</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">👍 Likes:</span>
                                <span class="stat-value" id="likeCount">-</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">💬 Comments:</span>
                                <span class="stat-value" id="commentCount">-</span>
                            </div>
                            <div class="stat-row">
                                <span class="stat-label">📅 Uploaded:</span>
                                <span class="stat-value" id="uploadDate">-</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- View Type Card -->
        <div class="card">
            <div class="card-header">
                <h2>🎯 View Type</h2>
                <button class="btn-success" onclick="launch()" style="background:#10b981;">🚀 Launch</button>
            </div>
            <select id="view_type" style="width:100%; padding:8px; margin-bottom:15px;"></select>
            <div id="viewTypeWarning" style="color:#f59e0b; font-size:0.85rem; display:none; margin-bottom:10px;"></div>
                 
        </div>
    </div>

    <!-- Sidebar: Activity Log -->
    <div class="sidebar">
        <div class="card" style="height: 100%; display: flex; flex-direction: column;">
            <div class="card-header">
                <h2>📋 Activity Log</h2>
            </div>
            <div class="console" id="console">
                <div class="log">Dashboard ready.</div>
            </div>
             <div id="previewSection" class="preview-card" style="display:none;">
                <h4>🔍 Preview for Selected View Type</h4>
                <div id="previewContent"></div>
            </div>
        </div>
    </div>
</div>

<script>
// ========== Helper Functions ==========
function addLog(msg, type='info') {
    const c = document.getElementById('console');
    const d = document.createElement('div');
    d.className = 'log';
    if (type === 'error') d.className += ' log-error';
    if (type === 'success') d.className += ' log-success';
    if (type === 'warning') d.className += ' log-warning';
    d.innerText = '[' + new Date().toLocaleTimeString() + '] ' + msg;
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}

function clearConsole() {
    const c = document.getElementById('console');
    c.innerHTML = '<div class="log">Console cleared.</div>';
    addLog('Console cleared by user', 'info');
}

// ========== Format Number (for views, likes, etc.) ==========
function formatNumber(num) {
    if (!num) return '-';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

// ========== Channel Info Fetching ==========
async function fetchChannelInfo(handle) {
    if (!handle) return;
    try {
        const res = await fetch('/api/get_channel_info', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({handle: handle})
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('channelDisplayName').innerText = data.name || handle;
            document.getElementById('channelHandle').innerText = '@' + handle.replace('@', '');
            if (data.avatar_url) {
                document.getElementById('channelAvatarImg').src = data.avatar_url;
            }
            if (data.subscriber_count) {
                document.getElementById('subscriberCount').innerHTML = '👥 ' + data.subscriber_count;
            }
            document.getElementById('channelAvatar').style.display = 'block';
        } else {
            document.getElementById('channelAvatar').style.display = 'none';
        }
    } catch (err) {
        console.error(err);
    }
}

// ========== Video Details Fetching (using yt-dlp) ==========
async function fetchVideoDetails(url) {
    if (!url) return;
    
    // Show loading state in left column
    document.getElementById('videoInfoDisplay').style.display = 'block';
    document.getElementById('videoTitle').innerHTML = '<span class="spinner"></span><span class="loading-text">Fetching...</span>';
    document.getElementById('videoId').innerText = '-';
    document.getElementById('videoDuration').innerText = '-';
    
    // Hide thumbnail container initially
    document.getElementById('thumbnailContainer').style.display = 'none';
    document.getElementById('videoStats').style.display = 'none';
    
    try {
        const res = await fetch('/api/get_video_details', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url})
        });
        const data = await res.json();
        if (data.success) {
            // Left column - video info
            document.getElementById('videoTitle').innerHTML = data.title || 'Untitled';
            document.getElementById('videoId').innerText = data.video_id || '-';
            document.getElementById('videoDuration').innerText = data.duration;
            
            // Right column - thumbnail and type badge
            if (data.thumbnail_url) {
                document.getElementById('videoThumbnail').src = data.thumbnail_url;
                document.getElementById('thumbnailContainer').style.display = 'block';
            } else {
                document.getElementById('thumbnailContainer').style.display = 'none';
            }
            
            // Show type badge below thumbnail
            var badgeHtml = data.is_short ? '<span class="badge badge-short">📱 SHORT</span>' : '<span class="badge badge-video">🎬 VIDEO</span>';
            document.getElementById('videoTypeBadgeContainer').innerHTML = badgeHtml;
            
            // Show video statistics
            if (data.view_count || data.like_count || data.comment_count || data.upload_date) {
                document.getElementById('viewCount').innerHTML = formatNumber(data.view_count);
                document.getElementById('likeCount').innerHTML = formatNumber(data.like_count);
                document.getElementById('commentCount').innerHTML = formatNumber(data.comment_count);
                document.getElementById('uploadDate').innerHTML = data.upload_date || '-';
                document.getElementById('videoStats').style.display = 'block';
            }
            
            // Auto-set max watch time to video duration
            if (data.duration && data.duration > 0) {
                var maxWatchField = document.getElementById('max_watch');
                var currentValue = parseInt(maxWatchField.value);
                if (isNaN(currentValue) || currentValue === 30) {
                    maxWatchField.value = data.duration;
                    addLog(`Auto-set max watch time from ${currentValue || 30}s to ${data.duration}s (video duration)`, 'info');
                }
            }
            
            // Update view types based on the is_short flag from yt-dlp
            await updateViewTypesByType(data.is_short);
            
            return data;
        } else {
            document.getElementById('videoInfoDisplay').style.display = 'none';
            addLog(`Error: ${data.error}`, 'error');
            return null;
        }
    } catch (err) {
        addLog(`Error: ${err.message}`, 'error');
        document.getElementById('videoInfoDisplay').style.display = 'none';
        return null;
    }
}

// ========== View Type Functions ==========
async function updateViewTypesByType(isShort) {
    try {
        const res = await fetch('/api/get_view_types_by_type', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({is_short: isShort})
        });
        const data = await res.json();
        var select = document.getElementById('view_type');
        select.innerHTML = '<option value="">-- Select View Type --</option>';
        var types = data.view_types || [];
        for (var i = 0; i < types.length; i++) {
            var opt = document.createElement('option');
            opt.value = types[i];
            opt.text = types[i];
            select.appendChild(opt);
        }
        if (types.length === 1) {
            select.value = types[0];
            addLog('Auto-selected view type: ' + types[0], 'success');
            updatePreview();
        }
    } catch (err) {
        addLog('Error loading view types: ' + err.message, 'error');
    }
}

async function updatePreview() {
    var url = document.getElementById('urlInput').value.trim();
    var viewType = document.getElementById('view_type').value;
    if (!url || !viewType) {
        document.getElementById('previewSection').style.display = 'none';
        return;
    }
    try {
        const res = await fetch('/api/preview', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url, view_type: viewType})
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('previewSection').style.display = 'block';
            document.getElementById('previewContent').innerHTML = `
                <div class="row">
                    <div class="form-group"><strong>Constructed URL:</strong><br><span class="info-text">${data.constructed_url}</span></div>
                    <div class="form-group"><strong>User Agent:</strong><br><span class="info-text">${data.user_agent.substring(0,70)}...</span></div>
                    <div class="form-group"><strong>Device:</strong><br>${data.is_mobile ? '📱 Mobile' : '💻 Desktop'}</div>
                </div>
            `;
        } else {
            document.getElementById('previewSection').style.display = 'block';
            document.getElementById('previewContent').innerHTML = `<div style="color:#f59e0b;">⚠️ ${data.error}</div>`;
        }
    } catch (err) {
        console.error(err);
    }
}

// ========== Save/Load Config ==========
async function saveConfig() {
    var url = document.getElementById('urlInput').value.trim();
    var config = {
        url: url,
        num_instances: parseInt(document.getElementById('num_instances').value),
        cycles: parseInt(document.getElementById('cycles').value),
        headless: document.getElementById('headless').value === 'true',
        min_watch_time: parseInt(document.getElementById('min_watch').value),
        max_watch_time: parseInt(document.getElementById('max_watch').value),
        suggested_min: parseInt(document.getElementById('suggested_min').value),
        suggested_max: parseInt(document.getElementById('suggested_max').value),
        suggested_chance: parseInt(document.getElementById('suggested_chance').value) / 100,
        use_proxy: document.getElementById('use_proxy').value === 'true',
        proxy_url: document.getElementById('proxy_url').value,
        channel_name: document.getElementById('channel_name').value,
        view_type: document.getElementById('view_type').value
    };
    try {
        const res = await fetch('/api/save_config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(config)});
        if (res.ok) addLog('Configuration saved', 'success');
        else addLog('Save failed', 'error');
    } catch (err) { addLog('Save error: ' + err.message, 'error'); }
}

async function loadConfig() {
    try {
        const res = await fetch('/api/load_config');
        const cfg = await res.json();
        document.getElementById('channel_name').value = cfg.channel_name || '';
        if (cfg.channel_name) fetchChannelInfo(cfg.channel_name.replace('@', ''));
        if (cfg.url) {
            document.getElementById('urlInput').value = cfg.url;
            await fetchVideoDetails(cfg.url);
        }
        document.getElementById('num_instances').value = cfg.num_instances || 1;
        document.getElementById('cycles').value = cfg.cycles || 1;
        document.getElementById('headless').value = cfg.headless ? 'true' : 'false';
        document.getElementById('min_watch').value = cfg.min_watch_time || 15;
        document.getElementById('max_watch').value = cfg.max_watch_time || 30;
        document.getElementById('suggested_min').value = cfg.suggested_min || 15;
        document.getElementById('suggested_max').value = cfg.suggested_max || 35;
        var chanceSlider = document.getElementById('suggested_chance');
        var chanceSpan = document.getElementById('chance_val');
        chanceSlider.value = (cfg.suggested_chance || 0.4) * 100;
        chanceSpan.innerText = chanceSlider.value + '%';
        document.getElementById('use_proxy').value = cfg.use_proxy ? 'true' : 'false';
        document.getElementById('proxy_url').value = cfg.proxy_url || '';
        if (cfg.view_type) {
            var select = document.getElementById('view_type');
            for (var i = 0; i < select.options.length; i++) {
                if (select.options[i].value === cfg.view_type) {
                    select.value = cfg.view_type;
                    break;
                }
            }
            await updatePreview();
        }
        addLog('Configuration loaded', 'success');
    } catch (err) { addLog('Load error: ' + err.message, 'error'); }
}

// ========== Cleanup ==========
async function cleanupAll() {
    if (!confirm('Delete all logs, cache folders, and old launch configs?')) return;
    addLog('Starting cleanup...', 'info');
    try {
        const res = await fetch('/api/cleanup', {method: 'POST'});
        const data = await res.json();
        if (data.success) addLog(`Cleanup: ${data.deleted_files} files, ${data.deleted_folders} folders deleted`, 'success');
        else addLog('Cleanup failed: ' + data.error, 'error');
    } catch (err) { addLog('Cleanup error: ' + err.message, 'error'); }
}

// ========== Launch ==========
async function launch() {
    var url = document.getElementById('urlInput').value.trim();
    if (!url) { addLog('No URL entered', 'error'); return; }
    var viewType = document.getElementById('view_type').value;
    if (!viewType) { addLog('Select a view type', 'error'); return; }
    var automationVersion = document.getElementById('automation_version').value;
    
    try {
        const validateRes = await fetch('/api/validate_view_type', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url, view_type: viewType})
        });
        const validateData = await validateRes.json();
        if (!validateData.valid) {
            document.getElementById('viewTypeWarning').innerHTML = `⚠️ ${validateData.error}`;
            document.getElementById('viewTypeWarning').style.display = 'block';
            addLog(`Validation failed: ${validateData.error}`, 'error');
            return;
        }
        document.getElementById('viewTypeWarning').style.display = 'none';
    } catch (err) { addLog('Validation error: ' + err.message, 'error'); return; }
    
    var config = {
        urls: [url],
        num_instances: parseInt(document.getElementById('num_instances').value),
        cycles: parseInt(document.getElementById('cycles').value),
        headless: document.getElementById('headless').value === 'true',
        min_watch_time: parseInt(document.getElementById('min_watch').value),
        max_watch_time: parseInt(document.getElementById('max_watch').value),
        suggested_min: parseInt(document.getElementById('suggested_min').value),
        suggested_max: parseInt(document.getElementById('suggested_max').value),
        suggested_chance: parseInt(document.getElementById('suggested_chance').value) / 100,
        use_proxy: document.getElementById('use_proxy').value === 'true',
        proxy_url: document.getElementById('proxy_url').value,
        channel_name: document.getElementById('channel_name').value,
        view_type: viewType,
        automation_version: automationVersion
    };
    addLog('Launching ' + config.num_instances + ' instance(s) with ' + viewType + ' using ' + automationVersion.toUpperCase(), 'info');
    try {
        const res = await fetch('/api/launch', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(config)});
        const result = await res.json();
        if (result.success) addLog(result.message, 'success');
        else addLog('Launch error: ' + result.error, 'error');
    } catch (err) { addLog('Launch failed: ' + err.message, 'error'); }
}

// ========== Event Listeners ==========
document.getElementById('channel_name').addEventListener('blur', function() {
    var handle = this.value.trim().replace('@', '');
    if (handle) fetchChannelInfo(handle);
});

document.getElementById('urlInput').addEventListener('blur', function() {
    var url = this.value.trim();
    if (url) {
        fetchVideoDetails(url);
    }
});

document.getElementById('view_type').addEventListener('change', updatePreview);

var chanceSlider = document.getElementById('suggested_chance');
var chanceSpan = document.getElementById('chance_val');
chanceSlider.oninput = function() { chanceSpan.innerText = chanceSlider.value + '%'; };

window.onload = function() { loadConfig(); };
</script>
</body>
</html>
"""

# ==================== Helper Functions ====================

def get_video_details_ytdlp(url: str) -> dict:
    """Get video details using yt-dlp (accurate duration, title, thumbnail, stats)."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                duration = info.get('duration', 30)
                title = info.get('title', 'Title not found')
                video_id = info.get('id', extract_video_id(url))
                is_short = '/shorts/' in url or duration < 60
                thumbnail = info.get('thumbnail', '')
                if not thumbnail and info.get('thumbnails'):
                    thumbnail = info['thumbnails'][-1].get('url', '')
                
                # Extract statistics
                view_count = info.get('view_count', 0)
                like_count = info.get('like_count', 0)
                comment_count = info.get('comment_count', 0)
                upload_date = info.get('upload_date', '')
                if upload_date and len(upload_date) == 8:
                    upload_date = f"{upload_date[6:8]}/{upload_date[4:6]}/{upload_date[0:4]}"
                
                # Extract subscriber count (from channel info if available)
                subscriber_count = info.get('channel_follower_count', 0)
                if subscriber_count:
                    subscriber_count = format_number(subscriber_count)
                
                return {
                    "success": True,
                    "video_id": video_id,
                    "title": title,
                    "is_short": is_short,
                    "duration": duration,
                    "thumbnail_url": thumbnail,
                    "view_count": view_count,
                    "like_count": like_count,
                    "comment_count": comment_count,
                    "upload_date": upload_date,
                    "subscriber_count": subscriber_count
                }
    except Exception as e:
        print(f"yt-dlp error: {e}")
    
    return {"success": False, "error": "Failed to fetch video info"}


def format_number(num):
    """Format large numbers with K/M suffix."""
    if not num or num == 0:
        return ""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)


def get_channel_info_ytdlp(channel_handle: str) -> dict:
    """Fetch channel name, avatar, and subscriber count using yt-dlp."""
    result = {"name": channel_handle, "avatar_url": "", "subscriber_count": ""}
    handle = channel_handle.lstrip('@')
    channel_url = f"https://www.youtube.com/@{handle}"
    ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
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
    """Generate preview info for a given URL and view type."""
    video_id = extract_video_id(url)
    if not video_id:
        return {"success": False, "error": "Invalid YouTube URL"}
    
    # Get user agent based on view type (using self-contained logic)
    import random
    DESKTOP_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    MOBILE_AGENTS = [
        "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    ]
    
    if view_type in ("Other YouTube features", "Direct/Unknown"):
        is_mobile = True
        ua = random.choice(MOBILE_AGENTS)
    elif view_type == "Suggested":
        is_mobile = False
        ua = random.choice(DESKTOP_AGENTS)
    else:
        is_mobile = random.choice([True, False])
        ua = random.choice(MOBILE_AGENTS if is_mobile else DESKTOP_AGENTS)
    
    if view_type == "Other YouTube features":
        constructed_url = f"https://youtu.be/{video_id}"
    else:
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
    
    return {
        "success": True,
        "constructed_url": constructed_url,
        "user_agent": ua,
        "is_mobile": is_mobile,
        "video_id": video_id
    }


def cleanup_all():
    """Delete logs, old launch configs, and cache folders."""
    deleted_files = 0
    deleted_folders = 0
    
    if LOG_DIR.exists():
        for log_file in LOG_DIR.glob("*.log"):
            try:
                log_file.unlink()
                deleted_files += 1
            except:
                pass
    
    for config_file in DATA_DIR.glob("launch_config_*.json"):
        try:
            file_age = time.time() - config_file.stat().st_mtime
            if file_age > 3600:
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
    
    return {"deleted_files": deleted_files, "deleted_folders": deleted_folders}


# ==================== Flask Routes ====================

@app.route('/')
def dashboard():
    return render_template_string(HTML)

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
    return jsonify(get_video_details_ytdlp(url))

@app.route('/api/get_view_types_by_type', methods=['POST'])
def api_get_view_types_by_type():
    is_short = request.json.get('is_short', False)
    if is_short:
        view_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        view_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    return jsonify({"view_types": view_types})

@app.route('/api/detect_view_types', methods=['POST'])
def api_detect_view_types():
    urls = request.json.get('urls', [])
    if not urls:
        return jsonify({"view_types": []})
    first = urls[0]
    if '/shorts/' in first:
        return jsonify({"view_types": ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]})
    else:
        return jsonify({"view_types": ["Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]})

@app.route('/api/validate_view_type', methods=['POST'])
def api_validate_view_type():
    url = request.json.get('url', '')
    view_type = request.json.get('view_type', '')
    details = get_video_details_ytdlp(url)
    if not details.get('success'):
        return jsonify({"valid": False, "error": "Could not determine video type"})
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
        return jsonify({"success": True, "deleted_files": result["deleted_files"], "deleted_folders": result["deleted_folders"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/launch', methods=['POST'])
def api_launch():
    data = request.json
    view_type = data['view_type']
    automation_version = data.get('automation_version', 'selenium')
    
    # Validate view type
    url = data['urls'][0]
    details = get_video_details_ytdlp(url)
    if not details.get('success'):
        return jsonify({"success": False, "error": "Could not validate video type"})
    is_short = details.get('is_short', False)
    if is_short:
        valid_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View"]
    else:
        valid_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View"]
    if view_type not in valid_types:
        return jsonify({"success": False, "error": f"View type '{view_type}' not valid for this video"})
    
    view_to_script = {
        "Other YouTube features": "YTDirect.py",
        "Direct/Unknown": "YTDirect.py",
        "Suggested": "YTDirect.py",
        "Search (Video)": "YTSearch.py",
        "Short Feeds": "YTShort.py",
        "Channel View": "YTChannel.py"
    }
    script_file = view_to_script.get(view_type)
    if not script_file:
        return jsonify({"success": False, "error": f"Invalid view type: {view_type}"})
    
    # Choose script path based on automation version
    if automation_version == 'playwright':
        script_path = BASE_DIR / "playwright" / "scripts" / script_file
    else:
        script_path = BASE_DIR / "selenium" / "scripts" / script_file
    
    if not script_path.exists():
        return jsonify({"success": False, "error": f"Script not found: {script_path}"})

    configs = []
    for i in range(data['num_instances']):
        url = data['urls'][i % len(data['urls'])]
        cfg = build_script_config(i+1, data, url, view_type)
        if data.get('proxy_url'):
            cfg['proxy'] = data['proxy_url']
        configs.append(cfg)

    temp_file = DATA_DIR / f"launch_config_{int(time.time())}.json"
    with open(temp_file, 'w') as f:
        json.dump(configs, f, indent=2)

    import subprocess
    cmd = [sys.executable, str(script_path), str(temp_file)]
    if sys.platform == "win32":
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen(cmd)
    return jsonify({"success": True, "message": f"Launched {len(configs)} instance(s) with {view_type} using {automation_version.upper()}"})

def open_browser():
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    print("Starting YouTube Automation Dashboard at http://127.0.0.1:5000")
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
    print(f"Log directory: {LOG_DIR}")
    print(f"Data directory: {DATA_DIR}")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=False)