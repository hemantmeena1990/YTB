# common/proxy_manager.py
"""
Proxy Manager for YouTube Automation Suite - COMPLETELY FIXED
Handles both list and dict formats for proxy sources
"""

import random
import requests
import logging
import concurrent.futures
import json
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Callable, Tuple, Union
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# ========== Paths ==========
DATA_DIR = Path(__file__).parent.parent / "data"
PROXY_LIST_FILE = DATA_DIR / "proxy_list.txt"
WORKING_PROXIES_FILE = DATA_DIR / "working_proxies.txt"
BLACKLIST_FILE = DATA_DIR / "blacklist.txt"
WHITELIST_FILE = DATA_DIR / "whitelist.txt"
MANUAL_PROXIES_FILE = DATA_DIR / "manual_proxies.txt"
PROXY_SOURCES_FILE = DATA_DIR / "proxy_sources.json"
PROXY_SCORES_FILE = DATA_DIR / "proxy_scores.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ========== Settings ==========
TEST_URL_FAST = "https://httpbin.org/ip"
TEST_URL_YOUTUBE = "https://www.youtube.com"
TEST_TIMEOUT_QUICK = 3
TEST_TIMEOUT_VALIDATION = 8
MAX_WORKERS_QUICK = 100
MAX_WORKERS_VALIDATION = 50
MAX_WORKERS_SOURCES = 10
PROXY_SCORE_EXPIRY = 300
BACKGROUND_REFRESH_INTERVAL = 600
PROXY_ROTATION_TTL = 60

# ========== Default Sources ==========
DEFAULT_SOURCES = {
    "http": [
        "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/http.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/main/proxies/txt/http.txt"
    ],
    "socks4": [
        "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/socks4.txt"
    ],
    "socks5": [
        "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/socks5.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/main/proxies/txt/socks5.txt"
    ]
}


# ========== Proxy Scoring ==========
@dataclass
class ProxyScore:
    proxy: str
    latency_ms: float
    success_count: int
    fail_count: int
    last_tested: float
    uptime_percent: float = 100.0
    country: str = "Unknown"
    protocol: str = "http"
    
    @property
    def score(self) -> float:
        if self.fail_count + self.success_count == 0:
            return 0
        reliability = (self.success_count / (self.success_count + self.fail_count)) * 100
        latency_score = max(0, 100 - (self.latency_ms / 10))
        return (reliability * 0.7) + (latency_score * 0.3)


class ProxyScorer:
    def __init__(self):
        self.scores: Dict[str, ProxyScore] = {}
        self._load_scores()
    
    def _load_scores(self):
        if PROXY_SCORES_FILE.exists():
            try:
                with open(PROXY_SCORES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for proxy, score_data in data.items():
                        self.scores[proxy] = ProxyScore(**score_data)
            except:
                pass
    
    def _save_scores(self):
        try:
            with open(PROXY_SCORES_FILE, 'w', encoding='utf-8') as f:
                data = {p: asdict(score) for p, score in self.scores.items()}
                json.dump(data, f, indent=2)
        except:
            pass
    
    def update(self, proxy: str, latency_ms: float, success: bool, country: str = None, protocol: str = None):
        if protocol is None and '://' in proxy:
            protocol = proxy.split('://')[0]
        elif protocol is None:
            protocol = "http"
        
        if proxy not in self.scores:
            self.scores[proxy] = ProxyScore(
                proxy=proxy,
                latency_ms=latency_ms,
                success_count=0,
                fail_count=0,
                last_tested=time.time(),
                protocol=protocol
            )
        
        score = self.scores[proxy]
        if success:
            score.success_count += 1
            score.latency_ms = (score.latency_ms * 0.7) + (latency_ms * 0.3)
        else:
            score.fail_count += 1
        
        score.last_tested = time.time()
        if country:
            score.country = country
        if protocol:
            score.protocol = protocol
        
        self._save_scores()
    
    def get_best_proxies(self, count: int = 10, min_score: float = 50) -> List[str]:
        valid = {p: s for p, s in self.scores.items() if s.score >= min_score}
        sorted_proxies = sorted(valid.items(), key=lambda x: x[1].score, reverse=True)
        return [p for p, _ in sorted_proxies[:count]]
    
    def get_rotation_pool(self, size: int = 25) -> List[str]:
        return self.get_best_proxies(size, min_score=60)


_scorer = ProxyScorer()


# ========== File Operations ==========
def _load_text_lines(file_path: Path) -> List[str]:
    if not file_path.exists():
        return []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return [line.strip() for line in f if line.strip() and '<' not in line and len(line) < 200]


def _save_text_lines(file_path: Path, lines: List[str]) -> None:
    clean_lines = [l for l in lines if l and '<' not in l and len(l) < 200]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(clean_lines))


# ========== Source Management (FIXED) ==========
def get_proxy_sources() -> dict:
    """Get all proxy sources - ALWAYS returns a dictionary."""
    # If file doesn't exist, create with defaults
    if not PROXY_SOURCES_FILE.exists():
        _save_json_file(PROXY_SOURCES_FILE, DEFAULT_SOURCES.copy())
        return DEFAULT_SOURCES.copy()
    
    try:
        with open(PROXY_SOURCES_FILE, 'r', encoding='utf-8') as f:
            saved = json.load(f)
    except:
        saved = {}
    
    # Case 1: saved is a list (old format) - convert to dict
    if isinstance(saved, list):
        converted = {"http": [], "socks4": [], "socks5": []}
        for source in saved:
            if isinstance(source, dict):
                protocol = source.get('protocol', 'http')
                url = source.get('url', '')
                if protocol in converted:
                    converted[protocol].append(url)
                else:
                    converted['http'].append(url)
        _save_json_file(PROXY_SOURCES_FILE, converted)
        return converted
    
    # Case 2: saved is a dict but missing keys
    if not isinstance(saved, dict):
        saved = {}
    
    # Ensure all protocol keys exist
    if 'http' not in saved:
        saved['http'] = []
    if 'socks4' not in saved:
        saved['socks4'] = []
    if 'socks5' not in saved:
        saved['socks5'] = []
    
    # If all sources are empty, add defaults
    if not saved['http'] and not saved['socks4'] and not saved['socks5']:
        saved = DEFAULT_SOURCES.copy()
        _save_json_file(PROXY_SOURCES_FILE, saved)
    
    return saved


def _save_json_file(file_path: Path, data: Union[dict, list]) -> None:
    """Save data to JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def save_proxy_sources(sources: Union[dict, list]) -> None:
    """Save proxy sources configuration - handles both formats."""
    if isinstance(sources, list):
        # Convert list to dict format
        converted = {"http": [], "socks4": [], "socks5": []}
        for source in sources:
            if isinstance(source, dict):
                protocol = source.get('protocol', 'http')
                url = source.get('url', '')
                if protocol in converted:
                    converted[protocol].append(url)
                else:
                    converted['http'].append(url)
        sources = converted
    elif not isinstance(sources, dict):
        sources = DEFAULT_SOURCES.copy()
    
    # Ensure all keys exist
    for key in ['http', 'socks4', 'socks5']:
        if key not in sources:
            sources[key] = []
    
    _save_json_file(PROXY_SOURCES_FILE, sources)


def fetch_single_source(protocol: str, url: str, max_count: int = 100) -> List[str]:
    """Fetch proxies from a single source URL."""
    proxies = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=15, headers=headers)
        if response.status_code == 200:
            content = response.text
            if '<!DOCTYPE html>' in content[:500] or '<html' in content[:500]:
                return []
            
            lines = content.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and ':' in line and not line.startswith('#'):
                    if '<' in line or '>' in line or len(line) > 100:
                        continue
                    if '://' in line:
                        line = line.split('://', 1)[1]
                    parts = line.split(':')
                    if len(parts) == 2 and parts[0].replace('.', '').replace('-', '').isdigit():
                        formatted = f"{protocol}://{line}"
                        proxies.append(formatted)
                        if len(proxies) >= max_count:
                            break
    except Exception as e:
        logger.debug(f"Failed to fetch from {url}: {e}")
    return proxies


def fetch_proxies_parallel(proxy_type: str = 'all', max_count: int = 500) -> List[str]:
    """Fetch proxies from all sources in parallel."""
    sources = get_proxy_sources()
    
    # Ensure sources is a dictionary
    if not isinstance(sources, dict):
        sources = DEFAULT_SOURCES.copy()
    
    types_to_fetch = ['socks4', 'socks5', 'http'] if proxy_type == 'all' else [proxy_type]
    
    # Collect all fetch tasks
    fetch_tasks = []
    for ptype in types_to_fetch:
        urls = sources.get(ptype, [])
        if isinstance(urls, list):
            for url in urls:
                if url and isinstance(url, str) and url.startswith('http'):
                    fetch_tasks.append((ptype, url))
    
    manual_proxies = get_manual_proxies()
    all_proxies = set(manual_proxies)
    
    if fetch_tasks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_SOURCES) as executor:
            future_to_source = {
                executor.submit(fetch_single_source, ptype, url, max_count // len(fetch_tasks) if fetch_tasks else max_count): (ptype, url)
                for ptype, url in fetch_tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_source):
                try:
                    proxies = future.result()
                    all_proxies.update(proxies)
                    if len(all_proxies) >= max_count:
                        break
                except Exception as e:
                    logger.debug(f"Source fetch error: {e}")
    
    proxy_list = list(all_proxies)[:max_count]
    _save_text_lines(PROXY_LIST_FILE, proxy_list)
    logger.info(f"Fetched {len(proxy_list)} proxies from {len(fetch_tasks)} sources")
    return proxy_list


# ========== Proxy Testing ==========
def test_single_proxy_fast(proxy: str) -> Tuple[str, bool, float]:
    start_time = time.time()
    try:
        proxies_dict = {"http": proxy, "https": proxy}
        response = requests.get(TEST_URL_FAST, proxies=proxies_dict, timeout=TEST_TIMEOUT_QUICK)
        elapsed = (time.time() - start_time) * 1000
        if response.status_code == 200:
            return (proxy, True, elapsed)
    except:
        pass
    return (proxy, False, None)


def test_single_proxy_youtube(proxy: str) -> Tuple[str, bool, float, str]:
    start_time = time.time()
    try:
        proxies_dict = {"http": proxy, "https": proxy}
        response = requests.get(TEST_URL_YOUTUBE, proxies=proxies_dict, timeout=TEST_TIMEOUT_VALIDATION)
        elapsed = (time.time() - start_time) * 1000
        if response.status_code == 200:
            country = "Unknown"
            if 'cf-ray' in response.headers:
                ray = response.headers.get('cf-ray', '')
                if '-' in ray:
                    country = ray.split('-')[1][:2] if len(ray.split('-')) > 1 else "Unknown"
            return (proxy, True, elapsed, country)
    except:
        pass
    return (proxy, False, None, "Unknown")


def test_proxies_parallel_fast(proxies: List[str], callback: Optional[Callable] = None) -> Dict[str, any]:
    if not proxies:
        return {"working": [], "failed": [], "working_count": 0, "failed_count": 0, "total": 0}
    
    whitelist = get_whitelist()
    
    # Quick test
    logger.info(f"Testing {len(proxies)} proxies...")
    fast_working = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_QUICK) as executor:
        future_to_proxy = {executor.submit(test_single_proxy_fast, proxy): proxy for proxy in proxies}
        for future in concurrent.futures.as_completed(future_to_proxy):
            proxy, is_working, latency = future.result()
            protocol = proxy.split('://')[0] if '://' in proxy else 'http'
            
            if is_working or proxy in whitelist:
                fast_working.append(proxy)
                _scorer.update(proxy, latency or 100, True, protocol=protocol)
            else:
                _scorer.update(proxy, 1000, False, protocol=protocol)
                add_to_blacklist(proxy)
    
    if not fast_working:
        return {"working": [], "failed": proxies, "working_count": 0, "failed_count": len(proxies), "total": len(proxies)}
    
    # Validate against YouTube
    logger.info(f"Validating {len(fast_working)} proxies against YouTube...")
    validated_working = []
    blacklist = get_blacklist()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_VALIDATION) as executor:
        future_to_proxy = {executor.submit(test_single_proxy_youtube, proxy): proxy for proxy in fast_working}
        
        for future in concurrent.futures.as_completed(future_to_proxy):
            proxy, is_working, latency, country = future.result()
            protocol = proxy.split('://')[0] if '://' in proxy else 'http'
            
            if is_working:
                validated_working.append(proxy)
                _scorer.update(proxy, latency, True, country, protocol)
                if proxy in blacklist:
                    remove_from_blacklist(proxy)
            else:
                _scorer.update(proxy, latency or 500, False, protocol=protocol)
                add_to_blacklist(proxy)
    
    _save_text_lines(WORKING_PROXIES_FILE, validated_working)
    failed = [p for p in proxies if p not in validated_working and p not in whitelist]
    
    logger.info(f"Proxy test complete: {len(validated_working)} working, {len(failed)} failed")
    
    return {
        "working": validated_working,
        "failed": failed,
        "working_count": len(validated_working),
        "failed_count": len(failed),
        "total": len(proxies)
    }


# ========== Background Proxy Rotator ==========
class BackgroundProxyRotator:
    def __init__(self):
        self.running = False
        self.thread = None
        self.rotation_pool = []
        self.current_index = 0
        self.last_refresh = 0
    
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Background Proxy Rotator started")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Background Proxy Rotator stopped")
    
    def _run(self):
        while self.running:
            try:
                if time.time() - self.last_refresh > BACKGROUND_REFRESH_INTERVAL:
                    self._refresh_pool()
                    self.last_refresh = time.time()
                time.sleep(PROXY_ROTATION_TTL)
            except Exception as e:
                logger.error(f"Rotator error: {e}")
                time.sleep(30)
    
    def _refresh_pool(self):
        """Refresh the proxy pool with high-quality proxies"""
        logger.info("Refreshing proxy pool...")
        
        try:
            # Try to get working proxies first
            working = get_working_proxies()
            if working:
                self.rotation_pool = working[:25]
                random.shuffle(self.rotation_pool)
                self.current_index = 0
                logger.info(f"Rotation pool using {len(self.rotation_pool)} existing working proxies")
                return
            
            # If no working proxies, fetch new ones
            proxies = fetch_proxies_parallel('all', 200)
            if proxies:
                result = test_proxies_parallel_fast(proxies)
                working = result.get('working', [])
                if working:
                    self.rotation_pool = working[:25]
                    random.shuffle(self.rotation_pool)
                    self.current_index = 0
                    logger.info(f"Rotation pool updated with {len(self.rotation_pool)} new proxies")
                else:
                    logger.warning("No working proxies found during refresh")
            else:
                logger.warning("No proxies fetched during refresh")
        except Exception as e:
            logger.error(f"Error refreshing proxy pool: {e}")
    
    def get_next_proxy(self) -> Optional[str]:
        if not self.rotation_pool:
            self._refresh_pool()
            if not self.rotation_pool:
                return None
        
        proxy = self.rotation_pool[self.current_index % len(self.rotation_pool)]
        self.current_index += 1
        return proxy


_rotator = BackgroundProxyRotator()


# ========== Public API ==========
def start_background_service():
    _rotator.start()


def stop_background_service():
    _rotator.stop()


def get_rotating_proxy() -> Optional[str]:
    return _rotator.get_next_proxy()


def get_whitelist() -> List[str]:
    return _load_text_lines(WHITELIST_FILE)


def add_to_whitelist(proxy: str) -> bool:
    whitelist = get_whitelist()
    if proxy not in whitelist:
        whitelist.append(proxy)
        _save_text_lines(WHITELIST_FILE, whitelist)
        remove_from_blacklist(proxy)
        return True
    return False


def remove_from_whitelist(proxy: str) -> bool:
    whitelist = get_whitelist()
    if proxy in whitelist:
        whitelist.remove(proxy)
        _save_text_lines(WHITELIST_FILE, whitelist)
        return True
    return False


def get_blacklist() -> List[str]:
    return _load_text_lines(BLACKLIST_FILE)


def add_to_blacklist(proxy: str) -> bool:
    blacklist = get_blacklist()
    if proxy not in blacklist:
        blacklist.append(proxy)
        _save_text_lines(BLACKLIST_FILE, blacklist)
        working = _load_text_lines(WORKING_PROXIES_FILE)
        if proxy in working:
            working.remove(proxy)
            _save_text_lines(WORKING_PROXIES_FILE, working)
        return True
    return False


def remove_from_blacklist(proxy: str) -> bool:
    blacklist = get_blacklist()
    if proxy in blacklist:
        blacklist.remove(proxy)
        _save_text_lines(BLACKLIST_FILE, blacklist)
        return True
    return False


def get_manual_proxies() -> List[str]:
    return _load_text_lines(MANUAL_PROXIES_FILE)


def add_manual_proxy(proxy: str) -> bool:
    proxies = get_manual_proxies()
    if proxy not in proxies:
        proxies.append(proxy)
        _save_text_lines(MANUAL_PROXIES_FILE, proxies)
        return True
    return False


def remove_manual_proxy(proxy: str) -> bool:
    proxies = get_manual_proxies()
    if proxy in proxies:
        proxies.remove(proxy)
        _save_text_lines(MANUAL_PROXIES_FILE, proxies)
        return True
    return False


def get_working_proxies(refresh: bool = False) -> List[str]:
    if refresh:
        all_proxies = _load_text_lines(PROXY_LIST_FILE)
        if not all_proxies:
            all_proxies = fetch_proxies_parallel('all', 200)
        if all_proxies:
            return test_proxies_parallel_fast(all_proxies)["working"]
        return []
    else:
        return _load_text_lines(WORKING_PROXIES_FILE)


def get_best_proxies(count: int = 10) -> List[str]:
    return _scorer.get_best_proxies(count)


def get_proxy_stats() -> dict:
    working = get_working_proxies()
    blacklist = get_blacklist()
    whitelist = get_whitelist()
    scores = [s.score for s in _scorer.scores.values()]
    
    return {
        "total_proxies": len(_scorer.scores),
        "working_proxies": len(working),
        "blacklisted": len(blacklist),
        "whitelisted": len(whitelist),
        "average_score": sum(scores) / len(scores) if scores else 0,
        "best_proxy": _scorer.get_best_proxies(1)[0] if _scorer.get_best_proxies(1) else None
    }


def mark_proxy_failed(proxy: str) -> None:
    add_to_blacklist(proxy)
    logger.info(f"Marked proxy as failed: {proxy[:80]}")


def clear_all_data() -> dict:
    deleted = 0
    for file_path in [PROXY_LIST_FILE, WORKING_PROXIES_FILE, BLACKLIST_FILE, 
                     WHITELIST_FILE, MANUAL_PROXIES_FILE, PROXY_SCORES_FILE]:
        if file_path.exists():
            file_path.unlink()
            deleted += 1
    # Reset sources to defaults
    _save_json_file(PROXY_SOURCES_FILE, DEFAULT_SOURCES.copy())
    return {"deleted_files": deleted}


# Auto-start background service
start_background_service()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== Proxy Manager Test ===")
    print("Fetching proxies...")
    proxies = fetch_proxies_parallel('all', 50)
    print(f"Fetched {len(proxies)} proxies")
    print("\nTesting proxies...")
    results = test_proxies_parallel_fast(proxies[:20] if len(proxies) > 20 else proxies)
    print(f"Working: {results['working_count']}, Failed: {results['failed_count']}")