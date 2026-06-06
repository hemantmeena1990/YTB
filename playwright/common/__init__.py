# playwright/common/__init__.py
"""
Playwright common utilities for YouTube Automation.
"""

from .utils import (
    get_random_user_agent,
    get_variable_watch_time,
    extract_video_id,
    human_delay,
    is_shorts_url
)

from .behavior import (
    watch_with_human_behavior,
    start_video_with_audio_mute,
    click_suggested_video,
    ensure_video_playback,
    is_video_playing,
    random_scroll,
    random_key_press,
    random_mouse_movement,
    simulate_pause,
    handle_cookies
)

from .search import (
    DesktopSearch,
    MobileSearch
)

from .find import (
    find_and_click_video_result,
    find_and_click_channel_result,
    channel_internal_search
)

from .shortinteract import (
    swipe_up,
    swipe_down,
    delayed_mute,
    explore_cycle,
    watch_with_exploration
)

__all__ = [
    # utils
    'get_random_user_agent',
    'get_variable_watch_time',
    'extract_video_id',
    'human_delay',
    'is_shorts_url',
    # behavior
    'watch_with_human_behavior',
    'start_video_with_audio_mute',
    'click_suggested_video',
    'ensure_video_playback',
    'is_video_playing',
    'random_scroll',
    'random_key_press',
    'random_mouse_movement',
    'simulate_pause',
    'handle_cookies',
    # search
    'DesktopSearch',
    'MobileSearch',
    # find
    'find_and_click_video_result',
    'find_and_click_channel_result',
    'channel_internal_search',
    # shortinteract
    'swipe_up',
    'swipe_down',
    'delayed_mute',
    'explore_cycle',
    'watch_with_exploration'
]