#!/usr/bin/env python3
"""
Shared configuration module for YouTube Automation Suite
Handles config loading/saving, URL parsing, view type mapping, and script config building.
"""

import json
import re
import random
import unicodedata
from urllib.parse import quote_plus
from pathlib import Path
from typing import Optional, List, Dict, Any

# Try to import yt-dlp for video title fetching
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

# Path to config file
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "user_config.json"

# Default configuration
DEFAULT_CONFIG = {
    "url": "",
    "num_instances": 1,
    "cycles": 1,
    "headless": False,
    "min_watch_time": 15,
    "max_watch_time": 30,
    "suggested_min": 15,
    "suggested_max": 35,
    "suggested_chance": 0.4,
    "use_proxy": False,
    "proxy_url": "",
    "channel_name": "",
    "view_type": "",
    "traffic_source": "direct",
    "proxy_mode": "none",
    "po_token_source": "native"
}

# User agent lists
DESKTOP_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 OPR/129.0.0.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Safari/605.1.15",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:151.0) Gecko/20100101 Firefox/151.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 OPR/132.0.0.0",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.132 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 OPR/131.0.0.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3.1 Safari/605.1.15",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) obsidian/1.8.10 Chrome/132.0.6834.196 Electron/34.2.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
  "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 OPR/117.0.0.0",
  "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
  "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) obsidian/1.8.9 Chrome/132.0.6834.210 Electron/34.3.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) obsidian/1.8.3 Chrome/130.0.6723.191 Electron/33.3.2 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) obsidian/1.8.10 Chrome/132.0.6834.196 Electron/34.2.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:138.0) Gecko/20100101 Firefox/138.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 OPR/118.0.0.0"
]

MOBILE_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6301.2 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/30.0 Chrome/143.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 26_5_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/149.0.7827.137 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1"
    "Mozilla/5.0 (Linux; Android 13; M2101K7BNY Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 12; SM-G970U1 Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 11; SM-A405FN Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 12; itel A662L Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 10; VOG-L29 Build/HUAWEIVOG-L29; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 12; SM-A115F Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 11; 220333QNY Build/RKQ1.211001.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 13; SM-A145F Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 11; Infinix X688B Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 9; POT-LX1A Build/HUAWEIPOT-L41B; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 14; SM-A536B Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 14; TB370FU Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 14; 2109119DG Build/UKQ1.231108.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 13; SM-G985F Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.102 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 13; SM-G781B Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.102 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 11; TECNO CH9 Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 14; SM-S921B Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 14; SM-F711N Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 13; SM-G780F Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 12; M2101K6G Build/SKQ1.210908.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.102 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 13; CPH2211 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.100 Mobile Safari/537.36;",
    "Mozilla/5.0 (Linux; Android 14; SM-A725F Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.58 Mobile Safari/537.36;"
]

# ========== TRAFFIC SOURCE MAPPING ==========

# For referer headers (used in driver creation and embed widget_referrer)
REFERER_MAP = {
    'whatsapp_web': 'https://web.whatsapp.com/',
    'instagram': 'https://www.instagram.com/',
    'telegram_web': 'https://web.telegram.org/',
    'github': 'https://github.io/',
    'bing': 'https://www.bing.com/',
    'twitter': 'https://twitter.com/',
    'reddit': 'https://www.reddit.com/',
    'facebook': 'https://www.facebook.com/',
    'linkedin': 'https://www.linkedin.com/',
    'google_search': 'https://www.google.com/',
    'discord': 'https://discord.com/',
    'snapchat': 'https://www.snapchat.com/',
    'random': None,  # Handled separately
}

# Available traffic sources for random selection
AVAILABLE_TRAFFIC_SOURCES = [
    'google_search',
    'whatsapp_web',
    'instagram',
    'telegram_web',
    'github',
    'bing',
    'twitter',
    'reddit',
    'facebook',
    'linkedin'
]


# Add to the imports section
from urllib.parse import urlparse

# Add after REFERER_MAP
ORIGIN_MAP = {
    'google_search': 'https://www.google.com',
    'whatsapp_web': 'https://web.whatsapp.com',
    'instagram': 'https://www.instagram.com',
    'telegram_web': 'https://web.telegram.org',
    'github': 'https://github.com',
    'bing': 'https://www.bing.com',
    'twitter': 'https://twitter.com',
    'reddit': 'https://www.reddit.com',
    'facebook': 'https://www.facebook.com',
    'linkedin': 'https://www.linkedin.com',
    'discord': 'https://discord.com',
    'snapchat': 'https://www.snapchat.com',
}

def get_origin_for_traffic_source(traffic_source: str) -> str:
    """Get origin URL based on traffic source."""
    if traffic_source and traffic_source in ORIGIN_MAP:
        return ORIGIN_MAP[traffic_source]
    return 'https://www.google.com'


def build_embed_origins(traffic_source: str, widget_referrer: str = None) -> dict:
    """
    Build origin, forigin, and gporigin parameters based on traffic source.
    """
    if traffic_source and traffic_source in ORIGIN_MAP:
        base_url = ORIGIN_MAP[traffic_source]
    elif widget_referrer:
        parsed = urlparse(widget_referrer)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    else:
        base_url = 'https://www.google.com'
    
    return {
        'origin': base_url,
        'forigin': f"{base_url}/multi-browser.html",
        'gporigin': base_url,
    }


def resolve_traffic_source(traffic_source: str) -> tuple:
    """
    Resolve traffic source, handling 'random' option.
    
    Args:
        traffic_source: Raw traffic source from dashboard
    
    Returns:
        tuple: (resolved_source, referrer_url, source_type)
    """
    if traffic_source == 'random':
        # Pick a random source from available options
        selected = random.choice(AVAILABLE_TRAFFIC_SOURCES)
        referrer = REFERER_MAP.get(selected)
        return selected, referrer, 'random'
    else:
        referrer = REFERER_MAP.get(traffic_source)
        return traffic_source, referrer, 'fixed'


def get_widget_referrer(traffic_source: str) -> str:
    """Get widget_referrer URL for embed player."""
    if traffic_source == 'random':
        # This should not happen since random is resolved before
        return None
    return REFERER_MAP.get(traffic_source)


def build_platform_redirect_url(traffic_source: str, destination_url: str) -> str:
    """
    Build a platform-specific redirect URL.
    
    Args:
        traffic_source: Platform name (facebook, instagram, etc.)
        destination_url: The final URL to redirect to (e.g., YouTube video URL)
    
    Returns:
        Redirect URL with encoded destination, or None if platform doesn't support redirects
    """
    if not traffic_source or traffic_source == 'direct' or traffic_source == 'random':
        return destination_url
    
    encoded_dest = quote_plus(destination_url)
    
    redirect_formats = {
        'facebook': f'https://www.facebook.com/l.php?u={encoded_dest}',
        'instagram': f'https://l.instagram.com/?u={encoded_dest}',
        'google_search': f'https://www.google.com/url?q={encoded_dest}',
        'linkedin': f'https://www.linkedin.com/checkpoint/lg/redirect?url={encoded_dest}',
        'reddit': f'https://www.reddit.com/outbound?url={encoded_dest}',
    }
    
    if traffic_source in redirect_formats:
        return redirect_formats[traffic_source]
    
    # For platforms without redirect wrappers
    return destination_url


# ========== HELPER FUNCTIONS ==========

def sanitize_text(text):
    """
    Remove emoji and non-BMP characters for ChromeDriver compatibility.
    Keeps only characters within the Basic Multilingual Plane (BMP).
    """
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if ord(c) <= 0xFFFF)
    text = ' '.join(text.split())
    return text


def load_config() -> dict:
    """Load configuration from JSON file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save configuration to JSON file."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
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


def detect_url_type(url: str) -> str:
    """Detect if URL is for a short or regular video."""
    if '/shorts/' in url:
        return 'shorts'
    return 'video'


def get_applicable_view_types(url: str) -> List[str]:
    """Return list of view types applicable for the given URL."""
    if '/shorts/' in url:
        return ["Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "Channel View", "External(Embed)"]
    else:
        return ["Google Search", "Other YouTube features", "Direct/Unknown", "Suggested", "Search (Video)", "Channel View", "External(Embed)"]


def get_video_title(url: str) -> Optional[str]:
    """
    Fetch video title using yt-dlp with PO token support.
    Returns sanitized title (emojis removed) for ChromeDriver compatibility.
    """
    if not YTDLP_AVAILABLE:
        return ""
    
    try:
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '')
            return sanitize_text(title) if title else ""
    except Exception:
        return ""


def build_script_config(instance_id: int, data: dict, url: str, view_type: str) -> dict:
    """
    Build configuration dictionary for a script instance.
    Uses Intoli fingerprints for complete, consistent browser profiles.
    """
    video_id = extract_video_id(url)
    raw_traffic_source = data.get('traffic_source', 'direct')
    po_token_source = data.get('po_token_source', 'native')
    proxy_mode = data.get('proxy_mode', 'none')
    
    # Resolve traffic source (handles 'random')
    resolved_source, referrer_url, source_type = resolve_traffic_source(raw_traffic_source)
    
    # ========== USE INTOLI FINGERPRINTS (Complete Object) ==========
    from common.fingerprint_manager import get_fingerprint_for_view_type, get_random_mobile_fingerprint, get_random_desktop_fingerprint
    
    # Get force flags from data
    force_mobile = data.get('force_mobile', False)
    force_desktop = data.get('force_desktop', False)
    force_platform = data.get('force_platform', 'none')
    
    # Force Mobile takes precedence over Force Desktop
    if force_mobile or force_platform == 'mobile':
        fingerprint = get_random_mobile_fingerprint()
        print(f"[DEBUG] Force Mobile fingerprint selected")
    elif force_desktop or force_platform == 'desktop':
        fingerprint = get_random_desktop_fingerprint()
        print(f"[DEBUG] Force Desktop fingerprint selected")
    else:
        fingerprint = get_fingerprint_for_view_type(view_type)
    
    # ========== EXTRACT ALL SIGNALS FROM FINGERPRINT ==========
    user_agent = fingerprint.get('userAgent')
    platform = fingerprint.get('platform')
    screen_width = fingerprint.get('screenWidth')
    screen_height = fingerprint.get('screenHeight')
    viewport_width = fingerprint.get('viewportWidth')
    viewport_height = fingerprint.get('viewportHeight')
    plugins_length = fingerprint.get('pluginsLength')
    device_category = fingerprint.get('deviceCategory')
    vendor = fingerprint.get('vendor')
    fp_type = fingerprint.get('_type', device_category)
    
    # ========== WARNING: If any critical field is missing ==========
    if not user_agent or not platform or not screen_width or not screen_height:
        print(f"[WARNING] Instance {instance_id}: Fingerprint missing critical fields!")
        print(f"[WARNING] user_agent: {user_agent}, platform: {platform}, screen: {screen_width}x{screen_height}")
    
    is_mobile = (device_category == 'mobile')
    
    # ========== DETECT PLATFORM TYPE (For Cross-Platform Consistency) ==========
    is_ios = 'iPhone' in platform or 'iPad' in platform or 'iOS' in user_agent
    is_android = 'Android' in user_agent or 'Linux' in user_agent
    
    # If vendor doesn't match platform, force correct vendor (only if fingerprint is missing)
    if not vendor:
        if is_ios:
            vendor = "Apple Computer, Inc."
        elif is_android:
            vendor = "Google Inc."
        else:
            vendor = "Google Inc."
    
    print(f"[FINGERPRINT] Instance {instance_id}: Using {device_category} fingerprint (iOS: {is_ios}, Android: {is_android})")



    # ========== WARNING: If any critical field is missing ==========
    if not user_agent or not platform or not screen_width or not screen_height:
        print(f"[WARNING] Instance {instance_id}: Fingerprint missing critical fields!")
        print(f"[WARNING] user_agent: {user_agent}, platform: {platform}, screen: {screen_width}x{screen_height}")

    
    is_mobile = (device_category == 'mobile')
    
    # ========== DETECT PLATFORM TYPE (For Cross-Platform Consistency) ==========
    is_ios = 'iPhone' in platform or 'iPad' in platform or 'iOS' in user_agent
    is_android = 'Android' in user_agent or 'Linux' in user_agent
    
    # If vendor doesn't match platform, force correct vendor
    if is_ios and vendor != "Apple Computer, Inc.":
        vendor = "Apple Computer, Inc."
        print(f"[FINGERPRINT] Instance {instance_id}: Forced vendor to Apple Computer, Inc. for iOS")
    elif is_android and vendor != "Google Inc.":
        vendor = "Google Inc."
        print(f"[FINGERPRINT] Instance {instance_id}: Forced vendor to Google Inc. for Android")
    
    print(f"[FINGERPRINT] Instance {instance_id}: Using {device_category} fingerprint (iOS: {is_ios}, Android: {is_android})")
    # ============================================
    
    # Build constructed URL based on view type
    if view_type == "Other YouTube features":
        constructed_url = f"https://youtu.be/{video_id}"
    elif view_type == "Short Feeds":
        constructed_url = f"https://www.youtube.com/shorts/{video_id}"
    elif view_type == "Google Search":
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        constructed_url = f"https://www.youtube.com/watch?v={video_id}"
    
    config = {
        "instance_id": instance_id,
        "url": url,
        "video_id": video_id,
        "constructed_url": constructed_url,
        "view_type": view_type,
        "min_watch_time": data["min_watch_time"],
        "max_watch_time": data["max_watch_time"],
        "suggested_min": data["suggested_min"],
        "suggested_max": data["suggested_max"],
        "suggested_chance": data["suggested_chance"],
        "headless": data["headless"],
        "user_agent": user_agent,
        "is_mobile": is_mobile,
        "cycles": data.get("cycles", 1),
        "channel_name": data.get("channel_name", ""),
        "traffic_source": resolved_source,
        "traffic_source_raw": raw_traffic_source,
        "traffic_source_type": source_type,
        "po_token_source": po_token_source,
        "proxy_mode": proxy_mode,
        "num_instances": data.get("num_instances", 1),
        "force_mobile": force_mobile,
        
        # ========== FINGERPRINT SIGNALS ==========
        "platform": platform,
        "screen_width": screen_width,
        "screen_height": screen_height,
        "viewport_width": viewport_width,
        "viewport_height": viewport_height,
        "plugins_length": plugins_length,
        "device_category": device_category,
        "vendor": vendor,
        "fingerprint_type": fp_type,
        # ========== PLATFORM DETECTION (For Cross-Platform Consistency) ==========
        "is_ios": is_ios,
        "is_android": is_android,
        # ========== COMPLETE FINGERPRINT OBJECT (For CDP Injection) ==========
        "fingerprint_profile": fingerprint,  # ✅ PASS THE ENTIRE OBJECT
        # ===========================================
    }
    
    # Add undetected mode flag
    if data.get('automation_version') == 'selenium_undetected' or data.get('use_undetected'):
        config['use_undetected'] = True
    
    # Add referer for direct URL view types
    direct_url_view_types = ["Other YouTube features", "Direct/Unknown", "Suggested", "Short Feeds", "External(Embed)"]
    if view_type in direct_url_view_types and referrer_url:
        config['referer'] = referrer_url
    
    # For External(Embed) view type, also add widget_referrer
    if view_type == "External(Embed)" and referrer_url:
        config['widget_referrer'] = referrer_url
    
    # For Google Search view type, add redirect info
    if view_type == "Google Search":
        config['platform_redirect'] = True
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        if data.get('po_token'):
            separator = '&' if '?' in watch_url else '?'
            watch_url = f"{watch_url}{separator}pot={data.get('po_token')}"
        config['redirect_url'] = build_platform_redirect_url(resolved_source, watch_url)
    
    # Add video title for search mode or Google Search
    if view_type in ["Search (Video)", "Google Search", "Channel View"]:
        raw_title = get_video_title(url)
        config["video_title"] = raw_title if raw_title else ""
    
    # Add auto/random specific fields if present
    if data.get("is_auto_random"):
        config["is_auto_random"] = True
        config["available_view_types"] = data.get("available_view_types", [])
    
    return config
    
    
def get_preview_info(url: str, view_type: str) -> dict:
    """Generate preview info for a given URL and view type."""
    video_id = extract_video_id(url)
    if not video_id:
        return {"success": False, "error": "Invalid YouTube URL"}
    
    DESKTOP_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"]
    MOBILE_AGENTS = ["Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36"]
    
    if view_type == "Auto/Random":
        return {
            "success": True,
            "constructed_url": f"https://www.youtube.com/watch?v={video_id} (Auto-selected per instance)",
            "user_agent": "Random per instance",
            "is_mobile": "Random per instance",
            "video_id": video_id
        }
    
    if view_type == "Google Search":
        return {
            "success": True,
            "constructed_url": f"Via Google Search → https://www.youtube.com/watch?v={video_id}",
            "user_agent": "Random",
            "is_mobile": "Random",
            "video_id": video_id
        }
    
    if view_type == "External(Embed)":
        return {
            "success": True,
            "constructed_url": f"Embed Player → https://www.youtube.com/watch?v={video_id}",
            "user_agent": "Random",
            "is_mobile": "Random",
            "video_id": video_id
        }
    
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
    
    return {
        "success": True,
        "constructed_url": constructed_url,
        "user_agent": ua,
        "is_mobile": is_mobile,
        "video_id": video_id
    }


# Export public functions
__all__ = [
    'load_config',
    'save_config',
    'extract_video_id',
    'detect_url_type',
    'get_applicable_view_types',
    'build_script_config',
    'get_video_title',
    'get_preview_info',
    'sanitize_text',
    'REFERER_MAP',
    'resolve_traffic_source',
    'build_platform_redirect_url',
    'get_widget_referrer',
    'AVAILABLE_TRAFFIC_SOURCES',
    'DESKTOP_AGENTS',
    'MOBILE_AGENTS',
]