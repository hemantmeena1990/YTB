#!/usr/bin/env python3
"""
Cleanup Utility for YouTube Automation Suite
Handles cleaning of cache, logs, temp profiles, and other garbage files
Can be used by dashboard or run as standalone script
"""

import os
import sys
import shutil
import time
import glob
import tempfile
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# ========== Paths ==========
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
TEMP_BASE = os.path.join(tempfile.gettempdir(), "yt_automation")

# Cache patterns to clean
CACHE_PATTERNS = [
    "yt_direct_cache_*",
    "yt_search_cache_*",
    "yt_channel_cache_*",
    "yt_shorts_cache_*",
    "yt_ss_cache_*",
    "launch_config_*.json",
    "temp_instance_*.json"
]

CHROME_TEMP_PATTERNS = [
    os.path.join(tempfile.gettempdir(), "scoped_dir*"),
    os.path.join(tempfile.gettempdir(), "chrome_*"),
    os.path.join(tempfile.gettempdir(), "Crashpad*")
]


def format_size(bytes_size: int) -> str:
    """Convert bytes to human readable format"""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"


def get_file_age_days(file_path: Path) -> float:
    """Get file age in days"""
    if not file_path.exists():
        return 0
    age_seconds = time.time() - file_path.stat().st_mtime
    return age_seconds / (24 * 3600)


def clean_old_logs(days_old: int = 7, dry_run: bool = False) -> Dict[str, int]:
    """
    Clean log files older than specified days
    
    Args:
        days_old: Delete logs older than this many days
        dry_run: If True, only report what would be deleted
    
    Returns:
        Dictionary with counts and size
    """
    deleted = 0
    size = 0
    
    if not LOG_DIR.exists():
        return {"deleted": 0, "size_bytes": 0, "size_human": "0 B"}
    
    for log_file in LOG_DIR.glob("*.log"):
        if get_file_age_days(log_file) > days_old:
            if not dry_run:
                size += log_file.stat().st_size
                log_file.unlink()
            else:
                size += log_file.stat().st_size
            deleted += 1
    
    return {"deleted": deleted, "size_bytes": size, "size_human": format_size(size)}


def clean_old_configs(days_old: int = 1, dry_run: bool = False) -> Dict[str, int]:
    """
    Clean old launch config files
    
    Args:
        days_old: Delete configs older than this many days
        dry_run: If True, only report what would be deleted
    
    Returns:
        Dictionary with counts and size
    """
    deleted = 0
    size = 0
    
    for pattern in ["launch_config_*.json", "temp_instance_*.json"]:
        for config_file in DATA_DIR.glob(pattern):
            if get_file_age_days(config_file) > days_old:
                if not dry_run:
                    size += config_file.stat().st_size
                    config_file.unlink()
                else:
                    size += config_file.stat().st_size
                deleted += 1
    
    return {"deleted": deleted, "size_bytes": size, "size_human": format_size(size)}


def clean_cache_folders(dry_run: bool = False) -> Dict[str, int]:
    """
    Clean automation cache folders
    
    Args:
        dry_run: If True, only report what would be deleted
    
    Returns:
        Dictionary with counts and size
    """
    deleted_folders = 0
    deleted_files = 0
    size = 0
    
    for pattern in CACHE_PATTERNS:
        # Search in project root
        for folder in PROJECT_ROOT.glob(pattern):
            if folder.is_dir():
                if not dry_run:
                    folder_size = sum(f.stat().st_size for f in folder.glob("**/*") if f.is_file())
                    size += folder_size
                    shutil.rmtree(folder, ignore_errors=True)
                else:
                    folder_size = sum(f.stat().st_size for f in folder.glob("**/*") if f.is_file())
                    size += folder_size
                deleted_folders += 1
        
        # Search in subdirectories (selenium, playwright, etc.)
        for folder in PROJECT_ROOT.glob(f"*/{pattern}"):
            if folder.is_dir():
                if not dry_run:
                    folder_size = sum(f.stat().st_size for f in folder.glob("**/*") if f.is_file())
                    size += folder_size
                    shutil.rmtree(folder, ignore_errors=True)
                else:
                    folder_size = sum(f.stat().st_size for f in folder.glob("**/*") if f.is_file())
                    size += folder_size
                deleted_folders += 1
    
    return {
        "deleted_folders": deleted_folders,
        "deleted_files": deleted_files,
        "size_bytes": size,
        "size_human": format_size(size)
    }


def clean_temp_profiles(dry_run: bool = False) -> Dict[str, int]:
    """
    Clean temporary Chrome profiles
    
    Args:
        dry_run: If True, only report what would be deleted
    
    Returns:
        Dictionary with counts and size
    """
    deleted = 0
    size = 0
    
    if os.path.exists(TEMP_BASE):
        for folder in os.listdir(TEMP_BASE):
            folder_path = os.path.join(TEMP_BASE, folder)
            if os.path.isdir(folder_path):
                if not dry_run:
                    folder_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                     for dirpath, dirnames, filenames in os.walk(folder_path)
                                     for filename in filenames)
                    size += folder_size
                    shutil.rmtree(folder_path, ignore_errors=True)
                else:
                    folder_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                     for dirpath, dirnames, filenames in os.walk(folder_path)
                                     for filename in filenames)
                    size += folder_size
                deleted += 1
    
    return {"deleted": deleted, "size_bytes": size, "size_human": format_size(size)}


def clean_chrome_temp(dry_run: bool = False) -> Dict[str, int]:
    """
    Clean Chrome temporary files
    
    Args:
        dry_run: If True, only report what would be deleted
    
    Returns:
        Dictionary with counts and size
    """
    deleted = 0
    size = 0
    
    for pattern in CHROME_TEMP_PATTERNS:
        for folder in glob.glob(pattern):
            if os.path.isdir(folder):
                if not dry_run:
                    folder_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                     for dirpath, dirnames, filenames in os.walk(folder)
                                     for filename in filenames)
                    size += folder_size
                    shutil.rmtree(folder, ignore_errors=True)
                else:
                    folder_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                     for dirpath, dirnames, filenames in os.walk(folder)
                                     for filename in filenames)
                    size += folder_size
                deleted += 1
    
    return {"deleted": deleted, "size_bytes": size, "size_human": format_size(size)}


def clean_cache_files(dry_run: bool = False) -> Dict[str, int]:
    """
    Clean cached video/channel data files (keep images, delete expired JSON)
    
    Args:
        dry_run: If True, only report what would be deleted
    
    Returns:
        Dictionary with counts and size
    """
    deleted = 0
    size = 0
    
    if CACHE_DIR.exists():
        # Delete expired JSON cache files (older than 7 days)
        for json_file in CACHE_DIR.glob("**/*.json"):
            if get_file_age_days(json_file) > 7:
                if not dry_run:
                    size += json_file.stat().st_size
                    json_file.unlink()
                else:
                    size += json_file.stat().st_size
                deleted += 1
        
        # Delete orphaned image files (no matching JSON)
        for img_file in CACHE_DIR.glob("**/*.jpg"):
            json_file = img_file.with_suffix('.json')
            if not json_file.exists():
                if not dry_run:
                    size += img_file.stat().st_size
                    img_file.unlink()
                else:
                    size += img_file.stat().st_size
                deleted += 1
    
    return {"deleted": deleted, "size_bytes": size, "size_human": format_size(size)}
    

def clean_pycache(dry_run: bool = False) -> Dict[str, int]:
    """
    Clean all __pycache__ folders in the project
    
    Args:
        dry_run: If True, only report what would be deleted
    
    Returns:
        Dictionary with counts and size
    """
    deleted_folders = 0
    size = 0
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Skip data directory (keep user data)
        if 'data' in root.split(os.sep):
            continue
        # Skip venv if exists
        if 'venv' in root.split(os.sep) or 'env' in root.split(os.sep):
            continue
        # Skip .git if exists
        if '.git' in root.split(os.sep):
            continue
        
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            
            # Calculate folder size
            folder_size = 0
            for item in os.listdir(pycache_path):
                item_path = os.path.join(pycache_path, item)
                if os.path.isfile(item_path):
                    folder_size += os.path.getsize(item_path)
            
            if not dry_run:
                shutil.rmtree(pycache_path, ignore_errors=True)
            
            deleted_folders += 1
            size += folder_size
    
    return {
        "deleted_folders": deleted_folders,
        "size_bytes": size,
        "size_human": format_size(size)
    }


def clean_all(dry_run: bool = False) -> Dict[str, any]:
    """
    Run all cleanup operations
    
    Args:
        dry_run: If True, only report what would be deleted
    
    Returns:
        Dictionary with all cleanup results
    """
    results = {
        "logs": clean_old_logs(7, dry_run),
        "configs": clean_old_configs(1, dry_run),
        "cache_folders": clean_cache_folders(dry_run),
        "temp_profiles": clean_temp_profiles(dry_run),
        "chrome_temp": clean_chrome_temp(dry_run),
        "cache_files": clean_cache_files(dry_run),
                "pycache": clean_pycache(dry_run),  # <-- ADD THIS LINE

    }
    
    # Calculate totals
    total_deleted = sum(r.get("deleted", r.get("deleted_folders", 0)) for r in results.values())
    total_size = sum(r.get("size_bytes", 0) for r in results.values())
    
    results["total"] = {
        "deleted": total_deleted,
        "size_bytes": total_size,
        "size_human": format_size(total_size)
    }
    
    return results


def print_results(results: Dict[str, any]) -> None:
    """Print cleanup results in a readable format"""
    print("\n" + "=" * 60)
    print("CLEANUP RESULTS")
    print("=" * 60)
    
    categories = [
        ("Logs (older than 7 days)", "logs"),
        ("Old config files", "configs"),
        ("Cache folders", "cache_folders"),
        ("Temp profiles", "temp_profiles"),
        ("Chrome temp files", "chrome_temp"),
        ("Expired cache files", "cache_files"),
    ]
    
    for label, key in categories:
        result = results[key]
        if "deleted_folders" in result:
            print(f"\n📁 {label}:")
            print(f"   🗑️  Deleted folders: {result['deleted_folders']}")
            print(f"   💾 Space freed: {result['size_human']}")
        else:
            print(f"\n📁 {label}:")
            print(f"   🗑️  Deleted files: {result['deleted']}")
            print(f"   💾 Space freed: {result['size_human']}")
    
    print("\n" + "=" * 60)
    print(f"📊 TOTAL:")
    print(f"   🗑️  Deleted items: {results['total']['deleted']}")
    print(f"   💾 Total space freed: {results['total']['size_human']}")
    print("=" * 60)


def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(description="Cleanup Utility for YouTube Automation Suite")
    parser.add_argument("--dry-run", "-n", action="store_true", 
                       help="Show what would be deleted without actually deleting")
    parser.add_argument("--logs", type=int, metavar="DAYS", 
                       help="Delete logs older than DAYS (default: 7)")
    parser.add_argument("--configs", type=int, metavar="DAYS",
                       help="Delete configs older than DAYS (default: 1)")
    parser.add_argument("--cache", action="store_true",
                       help="Clean cache folders")
    parser.add_argument("--temp", action="store_true",
                       help="Clean temp profiles")
    parser.add_argument("--chrome", action="store_true",
                       help="Clean Chrome temp files")
    parser.add_argument("--all", action="store_true",
                       help="Run all cleanup operations")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be deleted\n")
    
    if args.all or (not any([args.logs, args.configs, args.cache, args.temp, args.chrome])):
        # Run all cleanup
        results = clean_all(args.dry_run)
        print_results(results)
    else:
        # Run specific cleanup
        results = {}
        
        if args.logs:
            results["logs"] = clean_old_logs(args.logs, args.dry_run)
            print(f"\n📁 Logs older than {args.logs} days:")
            print(f"   🗑️  Deleted: {results['logs']['deleted']}")
            print(f"   💾 Freed: {results['logs']['size_human']}")
        
        if args.configs:
            results["configs"] = clean_old_configs(args.configs, args.dry_run)
            print(f"\n📁 Configs older than {args.configs} days:")
            print(f"   🗑️  Deleted: {results['configs']['deleted']}")
            print(f"   💾 Freed: {results['configs']['size_human']}")
        
        if args.cache:
            results["cache_folders"] = clean_cache_folders(args.dry_run)
            print(f"\n📁 Cache folders:")
            print(f"   🗑️  Deleted folders: {results['cache_folders']['deleted_folders']}")
            print(f"   💾 Freed: {results['cache_folders']['size_human']}")
        
        if args.temp:
            results["temp_profiles"] = clean_temp_profiles(args.dry_run)
            print(f"\n📁 Temp profiles:")
            print(f"   🗑️  Deleted: {results['temp_profiles']['deleted']}")
            print(f"   💾 Freed: {results['temp_profiles']['size_human']}")
        
        if args.chrome:
            results["chrome_temp"] = clean_chrome_temp(args.dry_run)
            print(f"\n📁 Chrome temp files:")
            print(f"   🗑️  Deleted: {results['chrome_temp']['deleted']}")
            print(f"   💾 Freed: {results['chrome_temp']['size_human']}")


if __name__ == "__main__":
    main()