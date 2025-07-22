from browserforge.fingerprints import Screen
import flet as ft

LONG_DELAY = 30

BORDER_COLOR = ft.Colors.DEEP_PURPLE_200

BROWSER_OPTIONS = {
    "headless": False,
    "os": ["windows", "macos", "linux"],
    "screen": Screen(max_width=1280, max_height=720),
    "humanize": True,
    "locale": "en-US"
}