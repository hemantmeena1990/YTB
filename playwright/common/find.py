# playwright/common/find.py
"""
Playwright functions to find and click specific result types on YouTube.
Only custom logic - uses Playwright's built-in locators directly.
"""

import time
import random
import logging
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


def find_and_click_video_result(page: Page, instance_id: int, video_id: str, is_mobile: bool = False, po_token: str = None) -> bool:
    """
    On the search results page, find the video link containing the given video ID.
    Navigates directly with token injection.
    """
    try:
        time.sleep(2)
        
        if is_mobile:
            selectors = [
                f"a[href*='{video_id}']",
                "ytm-compact-video-renderer a",
                "a[href*='/watch?v=']"
            ]
        else:
            selectors = [
                f"a[href*='{video_id}']",
                "ytd-video-renderer a#thumbnail"
            ]
        
        video_link = None
        for selector in selectors:
            try:
                elements = page.locator(selector).all()
                for el in elements:
                    href = el.get_attribute('href')
                    if href and video_id in href:
                        video_link = el
                        break
                if video_link:
                    break
            except:
                continue
        
        if not video_link:
            logger.warning(f"Instance {instance_id}: Video result not found for ID {video_id}")
            return False
        
        final_href = video_link.get_attribute('href')
        
        if po_token and final_href and 'pot=' not in final_href:
            separator = '&' if '?' in final_href else '?'
            final_href = f"{final_href}{separator}pot={po_token}"
            logger.info(f"Instance {instance_id}: Injected PO token")
        
        if final_href:
            logger.info(f"Instance {instance_id}: Navigating to video")
            page.goto(final_href)
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error in find_and_click_video_result - {e}")
        return False


def find_and_click_channel_result(page: Page, instance_id: int, channel_name: str, is_mobile: bool = False) -> bool:
    """Find and click channel result on search results page"""
    try:
        time.sleep(2)
        clean_name = channel_name.lstrip('@')
        logger.info(f"Instance {instance_id}: Looking for channel: {clean_name}")
        
        if is_mobile:
            selectors = [
                f"a[href*='/@{clean_name}']",
                f"a[href*='/{clean_name}']",
                "ytm-compact-channel-renderer a",
                "a[href*='/channel/']"
            ]
        else:
            selectors = [
                f"a[href*='/@{clean_name}']",
                f"a[href*='/{clean_name}']",
                "ytd-channel-renderer a#main-link",
                "ytd-channel-renderer ytd-channel-name a"
            ]
        
        for selector in selectors:
            elements = page.locator(selector).all()
            for elem in elements:
                if elem.is_visible():
                    elem.click()
                    time.sleep(2)
                    logger.info(f"Instance {instance_id}: Clicked channel result")
                    return True
        
        logger.error(f"Instance {instance_id}: Channel result not found for {clean_name}")
        return False
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Error in find_and_click_channel_result - {e}")
        return False


def channel_internal_search(page: Page, instance_id: int, video_id: str, is_mobile: bool = False, po_token: str = None, video_title: str = None) -> bool:
    """
    On the channel page, first try to find video directly.
    If not found, perform search and navigate directly with token.
    """
    try:
        logger.info(f"Instance {instance_id}: channel_internal_search called")
        
        # ========== FIRST: Try to find video directly on current page ==========
        logger.info(f"Instance {instance_id}: Checking for video on channel page...")
        
        video_link = None
        link_selectors = [
            f"a[href*='{video_id}']",
            f"a[href*='/watch?v={video_id}']",
            "ytd-video-renderer a#thumbnail",
            "ytm-compact-video-renderer a",
            "a[href*='/watch?v=']"
        ]
        
        for selector in link_selectors:
            elements = page.locator(selector).all()
            for elem in elements:
                href = elem.get_attribute('href')
                if href and video_id in href:
                    video_link = elem
                    logger.info(f"Instance {instance_id}: Found video directly on page")
                    break
            if video_link:
                break
        
        if video_link:
            final_href = video_link.get_attribute('href')
            if po_token and final_href and 'pot=' not in final_href:
                separator = '&' if '?' in final_href else '?'
                final_href = f"{final_href}{separator}pot={po_token}"
                logger.info(f"Instance {instance_id}: Injected PO token")
            
            if final_href:
                page.goto(final_href)
                return True
        
        # ========== SECOND: Perform search ==========
        logger.info(f"Instance {instance_id}: Video not found, performing channel search...")
        
        # Build search terms list
        search_terms = []
        if video_title:
            search_terms.append(video_title)
        search_terms.append(video_id)
        
        for search_term in search_terms:
            logger.info(f"Instance {instance_id}: Searching for: {search_term[:50]}...")
            
            if is_mobile:
                # Mobile: Click Search tab
                search_tab = page.locator("yt-tab-shape[tab-title='Search']")
                if search_tab.count() > 0:
                    search_tab.first.click()
                    time.sleep(2)
                
                # Find and fill search input
                search_box = page.locator("input[name='query']")
                if search_box.count() == 0:
                    search_box = page.locator("input[placeholder='Search channel']")
                
                if search_box.count() > 0:
                    search_box.first.click()
                    search_box.first.fill(search_term)
                    search_box.first.press("Enter")
                else:
                    continue
            else:
                # Desktop: Click search button
                search_btn = page.locator("button[aria-label='Search']")
                if search_btn.count() == 0:
                    search_btn = page.locator("ytd-expandable-tab-renderer yt-icon-button#icon-button")
                
                if search_btn.count() > 0:
                    search_btn.first.click()
                    time.sleep(2)
                    
                    search_box = page.locator("input[name='query']")
                    if search_box.count() > 0:
                        search_box.first.fill(search_term)
                        search_box.first.press("Enter")
                    else:
                        continue
                else:
                    continue
            
            # Wait for results
            time.sleep(4)
            
            # Find video link
            video_link = None
            all_links = page.locator("a[href*='/watch?v=']").all()
            
            for link in all_links:
                href = link.get_attribute('href')
                if href and video_id in href:
                    video_link = link
                    logger.info(f"Instance {instance_id}: Found video match")
                    break
            
            if video_link:
                final_href = video_link.get_attribute('href')
                if po_token and final_href and 'pot=' not in final_href:
                    separator = '&' if '?' in final_href else '?'
                    final_href = f"{final_href}{separator}pot={po_token}"
                    logger.info(f"Instance {instance_id}: Injected PO token")
                
                if final_href:
                    page.goto(final_href)
                    return True
        
        logger.error(f"Instance {instance_id}: Video not found in channel")
        return False
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Channel internal search error - {e}")
        return False