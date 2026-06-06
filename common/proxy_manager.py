# common/proxy_manager.py
"""
Proxy Manager for YouTube Automation Suite
- Fetch proxies from online sources (user configurable)
- Manual proxy management (add/remove)
- Whitelist/Blacklist support
- Proxy rotation (round-robin)
- Parallel testing with configurable timeout
"""

import random
import requests
import logging
import concurrent.futures
import json
from pathlib import Path
from typing import List, Optional, Dict, Callable
from time import time, sleep
from collections import deque

logger = logging.getLogger(__name__)

# ========== Paths ==========
DATA_DIR = Path(__file__).parent.parent / "data"
PROXY_LIST_FILE = DATA_DIR / "proxy_list.txt"
WORKING_PROXIES_FILE = DATA_DIR / "working_proxies.txt"
BLACKLIST_FILE = DATA_DIR / "blacklist.txt"
WHITELIST_FILE = DATA_DIR / "whitelist.txt"
MANUAL_PROXIES_FILE = DATA_DIR / "manual_proxies.txt"
PROXY_SOURCES_FILE = DATA_DIR / "proxy_sources.json"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ========== Default Proxy Sources ==========
DEFAULT_PROXY_SOURCES = {
    "socks4": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://www.proxy-list.download/api/v1/get?type=socks4",
    ],
    "socks5": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
    ],
    "http": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://www.proxy-list.download/api/v1/get?type=https",
    ]
}

# ========== Settings ==========
TEST_URL = "https://httpbin.org/ip"
TEST_TIMEOUT = 10  # seconds (can be changed by user)
MAX_WORKERS = 20   # parallel test threads

# Proxy rotation state
_proxy_rotation_index = 0
_proxy_rotation_list = []


# ========== File Operations ==========
def _load_json_file(file_path: Path, default: dict) -> dict:
    """Load JSON file or return default."""
    if file_path.exists():
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except:
            return default
    return default


def _save_json_file(file_path: Path, data: dict) -> None:
    """Save data to JSON file."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def _load_text_lines(file_path: Path) -> List[str]:
    """Load lines from a text file."""
    if not file_path.exists():
        return []
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def _save_text_lines(file_path: Path, lines: List[str]) -> None:
    """Save lines to a text file."""
    with open(file_path, 'w') as f:
        f.write('\n'.join(lines))


# ========== Source Management ==========
def get_proxy_sources() -> dict:
    """Get all proxy sources (user configured + defaults)."""
    saved = _load_json_file(PROXY_SOURCES_FILE, {})
    # Merge with defaults, user additions override
    result = DEFAULT_PROXY_SOURCES.copy()
    for key, sources in saved.items():
        if key in result:
            result[key] = sources
        else:
            result[key] = sources
    return result


def save_proxy_sources(sources: dict) -> None:
    """Save proxy sources configuration."""
    _save_json_file(PROXY_SOURCES_FILE, sources)


def add_proxy_source(protocol: str, url: str) -> bool:
    """Add a custom proxy source URL."""
    sources = get_proxy_sources()
    if protocol not in sources:
        sources[protocol] = []
    if url not in sources[protocol]:
        sources[protocol].append(url)
        save_proxy_sources(sources)
        return True
    return False


def remove_proxy_source(protocol: str, url: str) -> bool:
    """Remove a proxy source URL."""
    sources = get_proxy_sources()
    if protocol in sources and url in sources[protocol]:
        sources[protocol].remove(url)
        save_proxy_sources(sources)
        return True
    return False


# ========== Manual Proxy Management ==========
def get_manual_proxies() -> List[str]:
    """Get list of manually added proxies."""
    return _load_text_lines(MANUAL_PROXIES_FILE)


def add_manual_proxy(proxy: str) -> bool:
    """Add a manual proxy (format: protocol://ip:port)."""
    proxies = get_manual_proxies()
    if proxy not in proxies:
        proxies.append(proxy)
        _save_text_lines(MANUAL_PROXIES_FILE, proxies)
        return True
    return False


def remove_manual_proxy(proxy: str) -> bool:
    """Remove a manual proxy."""
    proxies = get_manual_proxies()
    if proxy in proxies:
        proxies.remove(proxy)
        _save_text_lines(MANUAL_PROXIES_FILE, proxies)
        return True
    return False


# ========== Whitelist/Blacklist Management ==========
def get_whitelist() -> List[str]:
    """Get whitelisted proxies (always considered working)."""
    return _load_text_lines(WHITELIST_FILE)


def add_to_whitelist(proxy: str) -> bool:
    """Add proxy to whitelist."""
    whitelist = get_whitelist()
    if proxy not in whitelist:
        whitelist.append(proxy)
        _save_text_lines(WHITELIST_FILE, whitelist)
        # Also remove from blacklist if present
        remove_from_blacklist(proxy)
        return True
    return False


def remove_from_whitelist(proxy: str) -> bool:
    """Remove proxy from whitelist."""
    whitelist = get_whitelist()
    if proxy in whitelist:
        whitelist.remove(proxy)
        _save_text_lines(WHITELIST_FILE, whitelist)
        return True
    return False


def get_blacklist() -> List[str]:
    """Get blacklisted proxies."""
    return _load_text_lines(BLACKLIST_FILE)


def add_to_blacklist(proxy: str) -> bool:
    """Add proxy to blacklist."""
    blacklist = get_blacklist()
    if proxy not in blacklist:
        blacklist.append(proxy)
        _save_text_lines(BLACKLIST_FILE, blacklist)
        # Also remove from working proxies if present
        working = _load_text_lines(WORKING_PROXIES_FILE)
        if proxy in working:
            working.remove(proxy)
            _save_text_lines(WORKING_PROXIES_FILE, working)
        return True
    return False


def remove_from_blacklist(proxy: str) -> bool:
    """Remove proxy from blacklist."""
    blacklist = get_blacklist()
    if proxy in blacklist:
        blacklist.remove(proxy)
        _save_text_lines(BLACKLIST_FILE, blacklist)
        return True
    return False


# ========== Proxy Fetching ==========
def fetch_proxies(proxy_type: str = 'all', max_count: int = 100) -> List[str]:
    """Fetch proxies from all configured sources."""
    sources = get_proxy_sources()
    types_to_fetch = ['socks4', 'socks5', 'http'] if proxy_type == 'all' else [proxy_type]
    all_proxies = set()
    
    # Add manual proxies first
    for proxy in get_manual_proxies():
        all_proxies.add(proxy)
    
    for ptype in types_to_fetch:
        for url in sources.get(ptype, []):
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    lines = response.text.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and ':' in line:
                            # Remove existing protocol prefix
                            if '://' in line:
                                line = line.split('://', 1)[1]
                            formatted = f"{ptype}://{line}"
                            all_proxies.add(formatted)
                            if len(all_proxies) >= max_count:
                                break
            except Exception as e:
                logger.debug(f"Failed to fetch from {url}: {e}")
        if len(all_proxies) >= max_count:
            break
    
    proxy_list = list(all_proxies)[:max_count]
    _save_text_lines(PROXY_LIST_FILE, proxy_list)
    logger.info(f"Fetched {len(proxy_list)} proxies")
    return proxy_list


# ========== Proxy Testing ==========
def test_single_proxy(proxy: str, timeout: int = None) -> tuple:
    """Test a single proxy."""
    t = timeout if timeout else TEST_TIMEOUT
    start_time = time()
    try:
        proxies_dict = {"http": proxy, "https": proxy}
        response = requests.get(TEST_URL, proxies=proxies_dict, timeout=t)
        elapsed = time() - start_time
        if response.status_code == 200:
            return (proxy, True, elapsed)
    except Exception:
        pass
    return (proxy, False, None)


def test_proxies_parallel(proxies: List[str], callback: Optional[Callable] = None, timeout: int = None) -> Dict[str, any]:
    """Test proxies in parallel."""
    t = timeout if timeout else TEST_TIMEOUT
    working = []
    failed = []
    total = len(proxies)
    tested = 0
    
    # Check whitelist first
    whitelist = get_whitelist()
    blacklist = get_blacklist()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {executor.submit(test_single_proxy, proxy, t): proxy for proxy in proxies}
        for future in concurrent.futures.as_completed(future_to_proxy):
            proxy, is_working, elapsed = future.result()
            tested += 1
            
            if is_working or proxy in whitelist:
                working.append(proxy)
            else:
                failed.append(proxy)
            
            if callback:
                callback(total, len(working), len(failed))
    
    # Save working proxies
    _save_text_lines(WORKING_PROXIES_FILE, working)
    
    # Update blacklist with failed (unless in whitelist)
    for proxy in failed:
        if proxy not in whitelist:
            add_to_blacklist(proxy)
    
    logger.info(f"Proxy test complete: {len(working)} working, {len(failed)} failed")
    return {
        "working": working,
        "failed": failed,
        "working_count": len(working),
        "failed_count": len(failed),
        "total": total
    }


# ========== Proxy Rotation ==========
def init_rotation(proxies: List[str] = None):
    """Initialize the rotation list with working proxies."""
    global _proxy_rotation_list, _proxy_rotation_index
    if proxies is None:
        proxies = get_working_proxies()
    _proxy_rotation_list = proxies.copy()
    _proxy_rotation_index = 0
    random.shuffle(_proxy_rotation_list)
    logger.info(f"Proxy rotation initialized with {len(_proxy_rotation_list)} proxies")


def get_next_proxy() -> Optional[str]:
    """Get next proxy in rotation (round-robin)."""
    global _proxy_rotation_index, _proxy_rotation_list
    
    if not _proxy_rotation_list:
        # Initialize with working proxies
        working = get_working_proxies()
        if working:
            init_rotation(working)
        else:
            return None
    
    if not _proxy_rotation_list:
        return None
    
    proxy = _proxy_rotation_list[_proxy_rotation_index % len(_proxy_rotation_list)]
    _proxy_rotation_index += 1
    return proxy


def get_random_proxy(refresh: bool = False) -> Optional[str]:
    """Get a random working proxy (fallback if rotation not used)."""
    working = get_working_proxies(refresh)
    if not working:
        # Try to fetch new ones
        proxies = fetch_proxies('all', 50)
        if proxies:
            working = test_proxies_parallel(proxies)["working"]
        else:
            return None
    return random.choice(working) if working else None


def get_working_proxies(refresh: bool = False) -> List[str]:
    """Get list of currently known working proxies."""
    if refresh:
        all_proxies = _load_text_lines(PROXY_LIST_FILE)
        if not all_proxies:
            all_proxies = fetch_proxies('all', 100)
        if all_proxies:
            return test_proxies_parallel(all_proxies)["working"]
        return []
    else:
        working = _load_text_lines(WORKING_PROXIES_FILE)
        # Also include whitelist proxies
        whitelist = get_whitelist()
        for proxy in whitelist:
            if proxy not in working:
                working.append(proxy)
        return working


def mark_proxy_failed(proxy: str) -> None:
    """Mark a proxy as failed (called when script fails with this proxy)."""
    add_to_blacklist(proxy)
    # Remove from rotation list if present
    global _proxy_rotation_list
    if proxy in _proxy_rotation_list:
        _proxy_rotation_list.remove(proxy)
        logger.info(f"Removed failed proxy from rotation: {proxy}")


# ========== Settings Management ==========
def get_settings() -> dict:
    """Get current proxy settings."""
    return {
        "test_url": TEST_URL,
        "test_timeout": TEST_TIMEOUT,
        "max_workers": MAX_WORKERS
    }


def update_settings(timeout: int = None, max_workers: int = None) -> None:
    """Update proxy settings (global module variables)."""
    global TEST_TIMEOUT, MAX_WORKERS
    if timeout is not None:
        TEST_TIMEOUT = timeout
    if max_workers is not None:
        MAX_WORKERS = max_workers


# ========== Cleanup ==========
def clear_all_data() -> dict:
    """Clear all proxy data files."""
    deleted = 0
    for file_path in [PROXY_LIST_FILE, WORKING_PROXIES_FILE, BLACKLIST_FILE, WHITELIST_FILE, MANUAL_PROXIES_FILE]:
        if file_path.exists():
            file_path.unlink()
            deleted += 1
    _save_json_file(PROXY_SOURCES_FILE, {})
    return {"deleted_files": deleted}


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== Proxy Manager Test ===")
    print(f"Settings: timeout={TEST_TIMEOUT}, workers={MAX_WORKERS}")
    print("Fetching proxies...")
    proxies = fetch_proxies('all', 20)
    print(f"Fetched {len(proxies)} proxies")
    print("\nTesting proxies...")
    results = test_proxies_parallel(proxies)
    print(f"Working: {results['working_count']}, Failed: {results['failed_count']}")
    print("\nProxy rotation test:")
    init_rotation()
    for i in range(5):
        proxy = get_next_proxy()
        print(f"Proxy {i+1}: {proxy}")