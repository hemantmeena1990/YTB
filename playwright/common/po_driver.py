# playwright/common/po_driver.py
"""
Playwright driver creator with PO token network interception.
Pure Playwright - no Selenium code.
Compatible with the existing SessionConfig structure.
"""

import random
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


def create_playwright_driver(cfg, profile_name: str):
    """
    Create a Playwright browser page with network interception for PO token.
    
    Args:
        cfg: SessionConfig object with instance_id, headless, is_mobile, user_agent, po_token, proxy, etc.
        profile_name: Name for the profile (used for temp directory - Playwright manages this internally)
    
    Returns:
        tuple: (page, browser, context) - page for navigation, browser to close, context to close
    """
    playwright = sync_playwright().start()
    
    # Build launch arguments for stealth
    launch_args = [
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-sandbox',
    ]
    
    # Proxy setup
    proxy_config = None
    if cfg.proxy and cfg.proxy != 'none':
        proxy_config = {"server": cfg.proxy}
        logger.info(f"Instance {cfg.instance_id}: Using proxy: {cfg.proxy[:80]}")
    
    # Launch browser
    browser = playwright.chromium.launch(
        headless=cfg.headless,
        args=launch_args,
        proxy=proxy_config
    )
    
    # Build context options
    context_options = {
        'user_agent': cfg.user_agent,
        'viewport': {'width': 1024, 'height': 768} if not cfg.is_mobile else {'width': 375, 'height': 667},
    }
    
    # Add proxy to context if not already set at browser level
    if cfg.proxy and cfg.proxy != 'none' and not proxy_config:
        context_options['proxy'] = {"server": cfg.proxy}
    
    # Create context
    context = browser.new_context(**context_options)
    
    # ========== NETWORK INTERCEPTION FOR PO TOKEN ==========
    if cfg.po_token:
        def intercept_route(route):
            url = route.request.url
            if 'pot=' not in url:
                # Check if this is a YouTube video request
                if '/watch?v=' in url or '/shorts/' in url or 'youtu.be/' in url:
                    separator = '&' if '?' in url else '?'
                    new_url = f"{url}{separator}pot={cfg.po_token}"
                    logger.debug(f"Instance {cfg.instance_id}: Injecting PO token into: {url[:80]}...")
                    route.continue_(url=new_url)
                    return
            route.continue_()
        
        # Intercept all YouTube requests
        context.route("**/*youtube.com/*", intercept_route)
        context.route("**/*youtu.be/*", intercept_route)
        logger.info(f"Instance {cfg.instance_id}: Network interceptor active for PO token")
    
    # Create page
    page = context.new_page()
    
    # Set default timeout (30 seconds) - similar to Selenium's implicit wait
    page.set_default_timeout(30000)
    
    # Optional: Add extra headers to appear more like a real browser
    page.set_extra_http_headers({
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
    })
    
    logger.info(f"Instance {cfg.instance_id}: Playwright driver created successfully")
    
    return page, browser, context