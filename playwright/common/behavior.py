# playwright/common/behavior.py
"""
Playwright-specific human behavior functions for YouTube Automation.
Includes: scrolling, mouse movements, key presses, watching loop, video playback.
"""
import random
import time
import logging

logger = logging.getLogger(__name__)


# ========== BASIC ACTIONS ==========
def random_scroll(page, is_mobile: bool = False):
    """Perform random scroll using mouse wheel."""
    amount = random.randint(100, 500) if is_mobile else random.randint(80, 400)
    page.mouse.wheel(0, amount)
    time.sleep(random.uniform(0.2, 0.6))


def random_key_press(page):
    """Simulate random key presses."""
    if random.random() < 0.12:
        keys = ['ArrowDown', 'ArrowUp', 'Space', 'PageDown', 'PageUp']
        key = random.choice(keys)
        page.keyboard.press(key)
        time.sleep(random.uniform(0.05, 0.15))
        if key == 'Space' and random.random() < 0.4:
            time.sleep(random.uniform(0.3, 0.8))
            page.keyboard.press('Space')


def random_mouse_movement(page):
    """Move mouse to random position."""
    if random.random() < 0.3:
        try:
            viewport = page.viewport_size
            if viewport:
                x = random.randint(50, viewport['width'] - 50)
                y = random.randint(50, viewport['height'] - 50)
                page.mouse.move(x, y)
                time.sleep(random.uniform(0.1, 0.3))
        except:
            pass


def simulate_pause(page):
    """Simulate user pausing the video."""
    try:
        page.keyboard.press('Space')
        time.sleep(random.uniform(3, 10))
        page.keyboard.press('Space')
        logger.info("Simulated user pause")
        return True
    except:
        return False


# ========== WATCHING LOOP ==========
def watch_with_human_behavior(page, duration: int, is_mobile: bool = False):
    """
    Watch video for given duration while performing random human-like actions.
    """
    start = time.time()
    next_action = random.randint(5, 15)
    paused = False

    while time.time() - start < duration:
        remaining = duration - (time.time() - start)
        if remaining < next_action:
            time.sleep(remaining)
            break

        time.sleep(next_action)
        r = random.random()

        if r < 0.4:
            random_scroll(page, is_mobile)
        elif r < 0.7:
            random_mouse_movement(page)
        else:
            random_key_press(page)

        if not paused and random.random() < 0.06 and duration > 30:
            if simulate_pause(page):
                paused = True

        next_action = random.expovariate(0.12) + random.uniform(2, 8)
        next_action = min(max(next_action, 4), 20)


# ========== VIDEO PLAYBACK HELPERS ==========
def is_video_playing(page) -> bool:
    """Check if video element is playing."""
    try:
        return page.evaluate("""
            () => {
                const v = document.querySelector('video');
                return v && !v.paused && !v.ended && v.readyState >= 2;
            }
        """)
    except:
        return False


def ensure_video_playback(page, instance_id: int = 0) -> bool:
    """Try to start video if not playing (spacebar, click, JS)."""
    if is_video_playing(page):
        return True

    logger.warning(f"[Instance {instance_id}] Video not playing. Attempting start...")

    # Spacebar
    page.keyboard.press('Space')
    time.sleep(1)
    if is_video_playing(page):
        logger.info(f"[Instance {instance_id}] Started with SPACEBAR")
        return True

    # Click on video
    try:
        video = page.query_selector('video')
        if video:
            video.click()
            time.sleep(1)
            if is_video_playing(page):
                logger.info(f"[Instance {instance_id}] Started with CLICK")
                return True
    except:
        pass

    # JavaScript fallback
    try:
        page.evaluate("document.querySelector('video')?.play();")
        time.sleep(1)
        if is_video_playing(page):
            logger.info(f"[Instance {instance_id}] Started with JavaScript")
            return True
    except:
        pass

    logger.error(f"[Instance {instance_id}] Failed to start video")
    return False


def start_video_with_audio_mute(page, instance_id: int, is_mobile: bool = False, is_suggested: bool = False):
    """
    Set random volume (30-80%), start video, ensure unmuted,
    then mute after random delay (0-4s).
    """
    try:
        mute_delay = random.choice([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        initial_volume = random.uniform(0.3, 0.8)
        logger.info(f"Instance {instance_id} {'(suggested)' if is_suggested else ''}: Volume {int(initial_volume*100)}%, mute in {mute_delay}s")

        # Ensure video is playing
        ensure_video_playback(page, instance_id)

        # For mobile: click on video to create user gesture
        if is_mobile:
            try:
                video = page.query_selector('video')
                if video:
                    video.click()
                    time.sleep(0.3)
            except:
                pass

        # Check and unmute if muted
        is_muted = page.evaluate("document.querySelector('video')?.muted || false")
        if is_muted:
            logger.info(f"Instance {instance_id}: Video was muted, unmuting now")
            page.evaluate("document.querySelector('video').muted = false;")
            time.sleep(0.2)

        # Set volume
        page.evaluate(f"document.querySelector('video').volume = {initial_volume};")

        # Schedule mute after delay
        if mute_delay > 0:
            time.sleep(mute_delay)
            page.evaluate("document.querySelector('video').muted = true;")

        return True
    except Exception as e:
        logger.error(f"Instance {instance_id}: Video start error - {e}")
        return False


# ========== SUGGESTED VIDEO CLICK ==========
def click_suggested_video(page, is_mobile: bool = False) -> bool:
    """
    Open a random suggested video.

    Excludes:
    - current video
    - shorts
    - live streams
    """

    try:

        old_url = page.url

        current_video_id = ""

        if "watch?v=" in old_url:
            current_video_id = old_url.split("watch?v=")[1].split("&")[0]

        if is_mobile:

            for _ in range(3):
                page.mouse.wheel(0, 700)
                time.sleep(0.7)

            links = page.query_selector_all(
                'a[href*="/watch?v="]'
            )

        else:

            page.mouse.wheel(0, 300)

            time.sleep(1)

            links = page.query_selector_all(
                '#secondary a[href*="/watch?v="]'
            )

        candidates = []

        for link in links:

            try:

                href = link.get_attribute("href") or ""

                if "/shorts/" in href:
                    continue

                if current_video_id and current_video_id in href:
                    continue

                text = ""

                try:
                    text = (
                        link.inner_text() or ""
                    ).lower()
                except:
                    pass

                if "live" in text:
                    continue

                candidates.append(link)

            except:
                continue

        if not candidates:

            logger.warning(
                "No suitable suggested videos found"
            )

            return False

        link = random.choice(candidates)

        try:
            link.scroll_into_view_if_needed()
        except:
            pass

        time.sleep(random.uniform(0.5, 1.2))

        link.click()

        for _ in range(20):

            time.sleep(0.5)

            if page.url != old_url:

                logger.info(
                    "Random suggested video opened"
                )

                return True

        logger.warning(
            "Suggested click did not navigate"
        )

        return False

    except Exception as e:

        logger.error(
            f"Suggested video error: {e}"
        )

        return False


# ========== COOKIE HANDLING ==========
def handle_cookies(page, instance_id: int) -> bool:
    """Accept cookie consent if present."""
    try:
        accept_btns = page.query_selector_all('button:has-text("Accept"), button:has-text("Accept all"), button:has-text("I agree"), button:has-text("Got it")')
        for btn in accept_btns:
            if btn.is_visible():
                btn.click()
                time.sleep(0.5)
                logger.info(f"Instance {instance_id}: Accepted cookies")
                return True
    except:
        pass
    return False