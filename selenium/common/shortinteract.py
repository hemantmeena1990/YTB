# common/shortinteract.py
import random
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

logger = logging.getLogger(__name__)

def swipe_up(driver, fallback=True):
    try:
        driver.execute_script("window.scrollBy({top: window.innerHeight, behavior: 'smooth'});")
        time.sleep(0.5)
        return True
    except:
        if fallback:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ARROW_DOWN)
            time.sleep(0.3)
            return True
    return False

def swipe_down(driver, fallback=True):
    try:
        driver.execute_script("window.scrollBy({top: -window.innerHeight, behavior: 'smooth'});")
        time.sleep(0.5)
        return True
    except:
        if fallback:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ARROW_UP)
            time.sleep(0.3)
            return True
    return False

def delayed_mute(driver, delay_range=(0,4), volume_range=(0.3,0.8)):
    delay = random.uniform(*delay_range)
    vol = random.uniform(*volume_range)
    driver.execute_script(f"""
        var v = document.querySelector('video');
        if(v) {{ v.volume = {vol}; }}
        if({delay} > 0) {{
            setTimeout(function() {{
                var v2 = document.querySelector('video');
                if(v2) v2.muted = true;
            }}, {delay*1000});
        }}
    """)
    logger.info(f"Shorts volume {int(vol*100)}%, mute in {delay:.1f}s")
    return delay

def explore_cycle(driver, explore_count=None, watch_range=(3,8)):
    if explore_count is None:
        explore_count = random.randint(2,4)
    for i in range(explore_count):
        swipe_up(driver)
        t = random.uniform(*watch_range)
        logger.debug(f"Exploring {i+1}: {t:.1f}s")
        time.sleep(t)
    for _ in range(explore_count):
        swipe_down(driver)
        time.sleep(0.5)
    return True

def watch_with_exploration(driver, orig_watch=(5,10), explore_watch=(2,5), explore_count=None, return_watch=(4,8)):
    total = 0
    t = random.uniform(*orig_watch)
    logger.info(f"Original Short: {t:.1f}s")
    time.sleep(t)
    total += t
    if explore_count is None:
        explore_count = random.randint(2,4)
    for i in range(explore_count):
        swipe_up(driver)
        t2 = random.uniform(*explore_watch)
        logger.info(f"Explore {i+1}: {t2:.1f}s")
        time.sleep(t2)
        total += t2
    for _ in range(explore_count):
        swipe_down(driver)
        time.sleep(0.5)
    t3 = random.uniform(*return_watch)
    logger.info(f"Return watch: {t3:.1f}s")
    time.sleep(t3)
    total += t3
    return total