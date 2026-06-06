# playwright/common/find.py
"""
Playwright find and click utilities for YouTube Automation.
Finds and clicks results after search, and handles channel internal search.
"""

import time
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def find_and_click_video_result(page, video_id: str, instance_id: int = 0) -> bool:
    """
    Find exact target video using video_id.

    Flow:
    1. Search results scan.
    2. One page scroll.
    3. Scan again.
    4. Search directly by video_id.
    5. Scan again.
    """

    def scan_for_video():
        try:
            links = page.query_selector_all('a[href*="/watch?v="]')

            for link in links:
                try:
                    href = link.get_attribute("href") or ""

                    if f"watch?v={video_id}" in href:
                        return link
                except:
                    continue

            return None

        except:
            return None

    try:
        logger.info(
            f"Instance {instance_id}: Searching results for video id {video_id}"
        )

        time.sleep(2)

        # --------------------
        # PASS 1
        # --------------------
        video_link = scan_for_video()

        if video_link:
            logger.info(
                f"Instance {instance_id}: Found target video on initial scan"
            )

        # --------------------
        # SCROLL ONCE
        # --------------------
        if not video_link:

            logger.info(
                f"Instance {instance_id}: Target not found. Scrolling once."
            )

            page.mouse.wheel(0, 900)
            time.sleep(2)

            video_link = scan_for_video()

        # --------------------
        # SEARCH VIDEO ID
        # --------------------
        if not video_link:

            logger.info(
                f"Instance {instance_id}: Searching directly using video id"
            )

            search_box = None

            selectors = [
                'input[name="search_query"]',
                'input#search',
                'input[placeholder*="Search"]'
            ]

            for sel in selectors:
                try:
                    search_box = page.query_selector(sel)

                    if search_box and search_box.is_visible():
                        break
                except:
                    pass

            if not search_box:
                logger.warning(
                    f"Instance {instance_id}: Search box not found"
                )
                return False

            search_box.click()
            time.sleep(0.2)

            try:
                search_box.fill("")
            except:
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")

            time.sleep(0.2)

            search_box.type(video_id, delay=60)
            time.sleep(0.5)
            search_box.press("Enter")

            time.sleep(4)

            video_link = scan_for_video()

        # --------------------
        # FINAL CHECK
        # --------------------
        if not video_link:

            logger.warning(
                f"Instance {instance_id}: Exact video id not found"
            )

            return False

        try:
            video_link.scroll_into_view_if_needed()
        except:
            pass

        time.sleep(random.uniform(0.5, 1.0))

        old_url = page.url

        try:
            video_link.click()
        except:
            page.evaluate(
                "(el)=>el.click()",
                video_link
            )

        for _ in range(20):

            time.sleep(0.5)

            if page.url != old_url:
                logger.info(
                    f"Instance {instance_id}: Target video opened"
                )
                return True

        logger.warning(
            f"Instance {instance_id}: Navigation not detected"
        )

        return False

    except Exception as e:

        logger.error(
            f"Instance {instance_id}: Video finding error: {e}"
        )

        return False


def find_and_click_channel_result(page, channel_name: str, instance_id: int = 0) -> bool:
    """
    On the search results page, find and click the channel link.
    
    Args:
        page: Playwright page object
        channel_name: Channel name/handle to look for
        instance_id: Instance ID for logging
    
    Returns:
        True if successful
    """
    try:
        logger.info(f"Instance {instance_id}: Looking for channel result: {channel_name}")
        
        clean_handle = channel_name.lstrip('@')
        
        # Wait a moment for results
        time.sleep(1)
        
        # Try multiple selectors
        selectors = [
            f'a[href="/@{clean_handle}"]',
            f'a[href*="/@{clean_handle}"]',
            'ytd-channel-renderer a#main-link',
            'ytm-compact-channel-renderer a',
            'a[href*="/channel/"]'
        ]
        
        channel_link = None
        for selector in selectors:
            try:
                links = page.query_selector_all(selector)
                for link in links:
                    if link and link.is_visible():
                        href = link.get_attribute('href')
                        if href and (f'/@{clean_handle}' in href or '/channel/' in href):
                            channel_link = link
                            logger.info(f"Instance {instance_id}: Found channel with selector: {selector}")
                            break
                if channel_link:
                    break
            except:
                continue
        
        if not channel_link:
            # Try XPath fallback
            xpath = f'//a[contains(@href, "/@{clean_handle}")]'
            channel_link = page.query_selector(f'xpath={xpath}')
        
        if not channel_link:
            logger.warning(f"Instance {instance_id}: Channel result not found for {channel_name}")
            return False
        
        # Scroll and click
        try:
            channel_link.scroll_into_view_if_needed()
        except:
            pass
        time.sleep(random.uniform(0.3, 0.6))
        
        old_url = page.url
        try:
            channel_link.click()
        except:
            page.evaluate(f'document.querySelector(\'a[href*="/@{clean_handle}"]\').click()')
        
        # Wait for navigation
        for _ in range(15):
            time.sleep(0.5)
            if page.url != old_url:
                logger.info(f"Instance {instance_id}: Navigation to channel succeeded")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error finding/clicking channel: {e}")
        return False


def channel_internal_search(page, video_id: str, instance_id: int = 0) -> bool:
    """
    On a channel page, click the search tab, type video ID, and click the result.
    
    Args:
        page: Playwright page object
        video_id: YouTube video ID to search for
        instance_id: Instance ID for logging
    
    Returns:
        True if successful
    """
    try:
        logger.info(f"Instance {instance_id}: Performing channel internal search for {video_id}")
        
        # Step 1: Find and click the Search tab
        search_tab = None
        tab_selectors = [
            'yt-tab-shape[tab-title="Search"]',
            'div[role="tab"]:has-text("Search")',
            'yt-tab-shape:has-text("Search")'
        ]
        
        for selector in tab_selectors:
            try:
                search_tab = page.query_selector(selector)
                if search_tab and search_tab.is_visible():
                    logger.info(f"Instance {instance_id}: Found Search tab with selector: {selector}")
                    break
            except:
                continue
        
        if not search_tab:
            logger.error(f"Instance {instance_id}: Search tab not found on channel page")
            return False
        
        search_tab.click()
        time.sleep(1.5)
        
        # Step 2: Find search input box
        search_box = None
        input_selectors = [
            'input.YtmChannelSearchBoxRendererInput',
            'input[placeholder="Search channel"]',
            'input[name="query"]',
            'input[placeholder="Search"]'
        ]
        
        for selector in input_selectors:
            try:
                search_box = page.query_selector(selector)
                if search_box and search_box.is_visible():
                    logger.info(f"Instance {instance_id}: Found search input with selector: {selector}")
                    break
            except:
                continue
        
        if not search_box:
            logger.error(f"Instance {instance_id}: Search input not found")
            return False
        
        search_box.click()
        search_box.fill("")
        time.sleep(0.2)
        
        # Type video ID with natural delay
        for char in video_id:
            search_box.type(char, delay=0.05)
            time.sleep(0.01)
        
        time.sleep(0.5)
        search_box.press("Enter")
        
        # Wait for results
        page.wait_for_load_state('networkidle', timeout=10000)
        time.sleep(2)
        
        # Step 3: Find and click video result
        video_link = None
        link_selectors = [
            f'a[href*="{video_id}"]',
            f'a[href*="/watch?v={video_id}"]',
            'ytd-video-renderer a#thumbnail',
            'ytm-compact-video-renderer a'
        ]
        
        for selector in link_selectors:
            try:
                links = page.query_selector_all(selector)
                for link in links:
                    href = link.get_attribute('href')
                    if href and video_id in href:
                        video_link = link
                        break
                if video_link:
                    break
            except:
                continue
        
        if not video_link:
            logger.warning(f"Instance {instance_id}: Video not found in channel search results")
            return False
        
        try:
            video_link.scroll_into_view_if_needed()
        except:
            pass
        time.sleep(0.5)
        
        old_url = page.url
        try:
            video_link.click()
        except:
            page.evaluate(f'document.querySelector(\'a[href*="{video_id}"]\').click()')
        
        # Wait for navigation
        for _ in range(15):
            time.sleep(0.5)
            if page.url != old_url:
                logger.info(f"Instance {instance_id}: Navigation to video succeeded")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Channel internal search error: {e}")
        return False