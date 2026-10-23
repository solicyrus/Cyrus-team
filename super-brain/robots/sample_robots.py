
# نمونه ربات ها برای تست - شما ربات های واقعی خودت رو اینجا اضافه کن
#
# SUPERSEDED 2026-10-22: these sample robots are NO LONGER REGISTERED.
# Real working robots live in robots/real_robots.py (WebsiteMonitor,
# MarketData, WebResearcher, FileAnalyst, SupabaseReader) and are the ones
# main.py registers. This file is kept on disk for reference only.

SAMPLE_ROBOTS = [
    {"name": "Cleaner-Bot-01", "type": "cleaning", "capabilities": ["cleaning", "general"]},
    {"name": "Security-Bot-Alpha", "type": "security", "capabilities": ["security", "monitoring", "general"]},
    {"name": "Delivery-Bot-X", "type": "delivery", "capabilities": ["delivery", "navigation", "general"]},
    {"name": "Assistant-Bot", "type": "assistant", "capabilities": ["chat", "data_analysis", "general"]},
]

# برای اضافه کردن ربات واقعی خودت:
# from core.robot_manager import Robot
# class MyCustomRobot(Robot):
#     async def do_custom_action(self):
#         # کد ربات خودت
#         pass
