# playwright/common/humanclick.py
"""
Playwright human-like click utility - only custom offset/delay logic.
"""

import time
import random
import logging
from playwright.sync_api import Page, ElementHandle

logger = logging.getLogger(__name__)


def human_click(page: Page, element: ElementHandle, instance_id: int, element_type: str = "element") -> bool:
    """
    Perform a human-like click with random offset and hesitation.
    Uses Playwright's built-in click with custom positioning.
    """
    try:
        # Scroll into view
        element.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.2, 0.5))
        
        # Get bounding box for random offset
        box = element.bounding_box()
        if box:
            offset_x = random.randint(int(box['width'] * 0.2), int(box['width'] * 0.8))
            offset_y = random.randint(int(box['height'] * 0.2), int(box['height'] * 0.8))
            
            # Random hesitation (50-200ms)
            time.sleep(random.uniform(0.05, 0.2))
            
            # Click at offset position
            page.mouse.click(box['x'] + offset_x, box['y'] + offset_y)
        else:
            element.click()
        
        # Post-click delay
        time.sleep(random.uniform(0.1, 0.4))
        
        logger.info(f"Instance {instance_id}: Clicked {element_type}")
        return True
        
    except Exception as e:
        logger.error(f"Instance {instance_id}: Human click error for {element_type}: {e}")
        try:
            element.click()
            return True
        except:
            return False