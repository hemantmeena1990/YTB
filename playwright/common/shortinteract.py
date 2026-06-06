# playwright/common/shortinteract.py
"""
Playwright Shorts interaction utilities for YouTube Automation.
Includes swipe gestures, delayed mute, and exploration cycles.
"""

import random
import time
import logging

logger = logging.getLogger(__name__)


def swipe_up(page, fallback: bool = True) -> bool:
    """
    Swipe up to go to next Short.
    Uses keyboard arrow as fallback.
    
    Args:
        page: Playwright page object
        fallback: Use keyboard arrow if smooth scroll fails
    
    Returns:
        True if successful
    """
    try:
        # Get viewport height
        viewport = page.viewport_size
        if viewport:
            scroll_amount = viewport['height'] - 50
            page.mouse.wheel(0, scroll_amount)
        else:
            page.mouse.wheel(0, 500)
        time.sleep(0.5)
        return True
    except:
        if fallback:
            page.keyboard.press("ArrowDown")
            time.sleep(0.3)
            return True
    return False


def swipe_down(page, fallback: bool = True) -> bool:
    """
    Swipe down to go to previous Short.
    Uses keyboard arrow as fallback.
    
    Args:
        page: Playwright page object
        fallback: Use keyboard arrow if smooth scroll fails
    
    Returns:
        True if successful
    """
    try:
        viewport = page.viewport_size
        if viewport:
            scroll_amount = -viewport['height'] + 50
            page.mouse.wheel(0, scroll_amount)
        else:
            page.mouse.wheel(0, -500)
        time.sleep(0.5)
        return True
    except:
        if fallback:
            page.keyboard.press("ArrowUp")
            time.sleep(0.3)
            return True
    return False


def delayed_mute(page, delay_range: tuple = (0, 4), volume_range: tuple = (0.3, 0.8)) -> float:
    """
    Set random volume, then mute after random delay.
    
    Args:
        page: Playwright page object
        delay_range: (min_seconds, max_seconds) for mute delay
        volume_range: (min_volume, max_volume) for initial volume
    
    Returns:
        Actual mute delay in seconds
    """
    try:
        delay = random.uniform(*delay_range)
        volume = random.uniform(*volume_range)
        
        page.evaluate(f"""
            var v = document.querySelector('video');
            if (v) {{ v.volume = {volume}; }}
            if ({delay} > 0) {{
                setTimeout(function() {{
                    var v2 = document.querySelector('video');
                    if (v2) v2.muted = true;
                }}, {delay * 1000});
            }}
        """)
        
        logger.info(f"Shorts volume set to {int(volume*100)}%, mute in {delay:.1f}s")
        return delay
    except Exception as e:
        logger.error(f"Delayed mute error: {e}")
        return 0


def explore_cycle(page, explore_count: int = None, watch_range: tuple = (3, 8)) -> bool:
    """
    Perform one explore cycle: swipe up to next Shorts, watch briefly, then return.
    
    Args:
        page: Playwright page object
        explore_count: Number of Shorts to explore (random 2-4 if None)
        watch_range: (min_seconds, max_seconds) for each explored Short
    
    Returns:
        True if successful
    """
    try:
        if explore_count is None:
            explore_count = random.randint(2, 4)
        
        logger.info(f"Exploring {explore_count} Shorts")
        
        # Swipe up and watch each explored Short
        for i in range(explore_count):
            swipe_up(page)
            watch_time = random.uniform(*watch_range)
            logger.debug(f"Exploring Short {i+1}: {watch_time:.1f}s")
            time.sleep(watch_time)
        
        # Return to original Short
        for _ in range(explore_count):
            swipe_down(page)
            time.sleep(0.5)
        
        return True
        
    except Exception as e:
        logger.error(f"Explore cycle error: {e}")
        return False


def watch_with_exploration(
    page,
    orig_watch: tuple = (5, 10),
    explore_watch: tuple = (2, 5),
    explore_count: int = None,
    return_watch: tuple = (4, 8)
) -> float:
    """
    Full shorts watching session:
    - Watch original Short (random time)
    - Explore several Shorts (swipe up, watch each)
    - Return to original and watch again
    
    Args:
        page: Playwright page object
        orig_watch: (min, max) seconds for original Short
        explore_watch: (min, max) seconds for each explored Short
        explore_count: Number of Shorts to explore (random 2-4 if None)
        return_watch: (min, max) seconds for return watch
    
    Returns:
        Total time spent
    """
    total_time = 0
    
    try:
        # Initial watch
        initial = random.uniform(*orig_watch)
        logger.info(f"Watching original Short for {initial:.1f}s")
        time.sleep(initial)
        total_time += initial
        
        # Explore
        if explore_count is None:
            explore_count = random.randint(2, 4)
        
        for i in range(explore_count):
            swipe_up(page)
            explore_time = random.uniform(*explore_watch)
            logger.info(f"Explore Short {i+1}: {explore_time:.1f}s")
            time.sleep(explore_time)
            total_time += explore_time
        
        # Return
        for _ in range(explore_count):
            swipe_down(page)
            time.sleep(0.5)
        
        # Final watch
        final = random.uniform(*return_watch)
        logger.info(f"Watching original Short again for {final:.1f}s")
        time.sleep(final)
        total_time += final
        
        return total_time
        
    except Exception as e:
        logger.error(f"Watch with exploration error: {e}")
        return total_time