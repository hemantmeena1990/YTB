# common/humanclick.py
"""
Human-like click utility for all YouTube automation scripts.
Provides a single function `human_click()` that performs:
- Smooth scroll into view
- Random offset within element (not exact center)
- Human-like hesitation (50-200ms) before click
- Variable click duration (80-150ms press time)
- Regular Selenium click first, JavaScript fallback
- Navigation verification (up to 6 seconds)
- Retry with force click if navigation fails
- Occasional double-click (5% chance)
- Occasional click + hold (8% chance)
"""

import time
import random
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

logger = logging.getLogger(__name__)


def human_click(driver, element, instance_id, element_type="element"):
    """
    Perform a human-like click on an element with stale element recovery and navigation verification.
    
    Args:
        driver: Selenium WebDriver
        element: The web element to click (can be stale, will be re-fetched if needed)
        instance_id: Instance ID for logging
        element_type: Description of what is being clicked (for logging)
    
    Returns:
        bool: True if navigation was detected (URL changed), False otherwise
    """
    max_retries = 8
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Re-fetch element if it's stale (stale element recovery)
            try:
                # Check if element is stale by accessing a property
                _ = element.is_enabled()
            except Exception as stale_e:
                if "stale" in str(stale_e).lower():
                    logger.warning(f"Instance {instance_id}: Stale element for {element_type}, attempt {attempt + 1}, will retry with re-fetch")
                    # The caller needs to re-fetch, so return False to indicate retry needed
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    else:
                        return False
            
            # Smooth scroll into view
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                element
            )
            
            # Random pause before interacting (0.3 to 0.8 seconds)
            pause = random.uniform(0.3, 0.8)
            logger.info(f"Instance {instance_id}: Pausing {pause:.2f}s before clicking {element_type}")
            time.sleep(pause)
            
            # Get element dimensions for random offset
            rect = element.rect
            element_width = rect['width']
            element_height = rect['height']
            
            # Calculate random offset within element (20-80% range to avoid edges)
            min_offset_x = max(5, element_width * 0.2)
            max_offset_x = min(element_width - 5, element_width * 0.8)
            min_offset_y = max(5, element_height * 0.2)
            max_offset_y = min(element_height - 5, element_height * 0.8)
            
            if max_offset_x <= min_offset_x:
                offset_x = element_width // 2
            else:
                offset_x = random.randint(int(min_offset_x), int(max_offset_x))
            if max_offset_y <= min_offset_y:
                offset_y = element_height // 2
            else:
                offset_y = random.randint(int(min_offset_y), int(max_offset_y))
            
            # Calculate offset from center for ActionChains
            center_x = element_width // 2
            center_y = element_height // 2
            move_x = offset_x - center_x
            move_y = offset_y - center_y
            
            # Store current URL before click
            old_url = driver.current_url
            
            # Build action chain with human-like characteristics
            actions = ActionChains(driver)
            
            # Move to element with random offset
            actions.move_to_element_with_offset(element, move_x, move_y)
            
            # Random hesitation before click (50-200ms)
            hesitation = random.uniform(0.05, 0.2)
            actions.pause(hesitation)
            
            # Click with variable duration (80-150ms press time)
            click_duration = random.uniform(0.08, 0.15)
            actions.click_and_hold().pause(click_duration).release()
            
            # Execute the click
            actions.perform()
            logger.info(f"Instance {instance_id}: Clicked {element_type} (offset: {offset_x},{offset_y})")
            
            # Random post-click delay (100-400ms) before next action
            post_delay = random.uniform(0.1, 0.4)
            time.sleep(post_delay)
            
            # Occasional double-click (5% chance)
            if random.random() < 0.05:
                time.sleep(random.uniform(0.08, 0.15))
                actions2 = ActionChains(driver)
                actions2.move_to_element_with_offset(element, move_x, move_y)
                actions2.click().perform()
                logger.info(f"Instance {instance_id}: Performed double-click on {element_type}")
                time.sleep(random.uniform(0.05, 0.1))
            
            # Occasional click and hold (8% chance - simulates reading/thinking)
            if random.random() < 0.08:
                hold_duration = random.uniform(0.3, 0.8)
                actions3 = ActionChains(driver)
                actions3.move_to_element_with_offset(element, move_x, move_y)
                actions3.click_and_hold().pause(hold_duration).release().perform()
                logger.info(f"Instance {instance_id}: Click and hold on {element_type} for {hold_duration:.2f}s")
                time.sleep(random.uniform(0.1, 0.2))
            
            # Verify navigation (up to 6 seconds)
            for attempt_url in range(12):
                time.sleep(0.5)
                if driver.current_url != old_url:
                    logger.info(f"Instance {instance_id}: Navigation confirmed for {element_type} (attempt {attempt_url+1})")
                    return True
            
            # If still no navigation, try one more time with force click
            logger.warning(f"Instance {instance_id}: First click on {element_type} didn't navigate, retrying...")
            driver.execute_script("arguments[0].click();", element)
            time.sleep(1.5)
            if driver.current_url != old_url:
                logger.info(f"Instance {instance_id}: Second click on {element_type} succeeded!")
                return True
            
            logger.error(f"Instance {instance_id}: Click on {element_type} did not navigate - URL unchanged")
            return False
            
        except Exception as e:
            last_error = e
            if "stale" in str(e).lower() and attempt < max_retries - 1:
                logger.warning(f"Instance {instance_id}: Stale element error for {element_type}, attempt {attempt + 1}, retrying...")
                time.sleep(1)
                continue
            else:
                # Fallback to JavaScript click
                logger.warning(f"Instance {instance_id}: ActionChains failed ({e}), trying JavaScript fallback")
                try:
                    old_url = driver.current_url
                    driver.execute_script("arguments[0].click();", element)
                    time.sleep(1.5)
                    if driver.current_url != old_url:
                        logger.info(f"Instance {instance_id}: JavaScript click succeeded for {element_type}")
                        return True
                except:
                    pass
                logger.error(f"Instance {instance_id}: Error in human click for {element_type}: {e}")
                return False
    
    if last_error:
        logger.error(f"Instance {instance_id}: All retries failed for {element_type}: {last_error}")
    return False