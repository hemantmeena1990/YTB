# common/humanclick.py
"""
Human-like click utility for all YouTube automation scripts.
Provides a single function `human_click()` that performs:
- Smooth scroll into view
- Random human-like pause (0.3-0.8 seconds)
- Regular Selenium click first, JavaScript fallback
- Navigation verification (up to 6 seconds)
- Retry with force click if navigation fails
"""

import time
import random
import logging
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


def human_click(driver, element, instance_id, element_type="element"):
    """
    Perform a human-like click on an element.
    
    Args:
        driver: Selenium WebDriver
        element: The web element to click
        instance_id: Instance ID for logging
        element_type: Description of what is being clicked (for logging)
    
    Returns:
        bool: True if navigation was detected (URL changed), False otherwise
    """
    try:
        # Smooth scroll into view
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
            element
        )
        
        # Human-like pause before clicking (0.3 to 0.8 seconds)
        pause = random.uniform(0.3, 0.8)
        logger.info(f"Instance {instance_id}: Pausing {pause:.2f}s before clicking {element_type}")
        time.sleep(pause)
        
        # Store current URL before click
        old_url = driver.current_url
        
        # Try regular Selenium click first (more human-like)
        try:
            element.click()
            logger.info(f"Instance {instance_id}: Clicked {element_type} using regular click")
        except Exception as e:
            logger.warning(f"Instance {instance_id}: Regular click failed: {e}, trying JavaScript")
            driver.execute_script("arguments[0].click();", element)
            logger.info(f"Instance {instance_id}: Clicked {element_type} using JavaScript fallback")
        
        # Verify navigation (up to 6 seconds)
        for attempt in range(12):
            time.sleep(0.5)
            if driver.current_url != old_url:
                logger.info(f"Instance {instance_id}: Navigation confirmed for {element_type} (attempt {attempt+1})")
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
        logger.error(f"Instance {instance_id}: Error in human click for {element_type}: {e}")
        return False