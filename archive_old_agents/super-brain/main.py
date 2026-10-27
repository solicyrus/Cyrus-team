
"""
SUPER BRAIN - سوپر ربات مدیر هوشمند
اجرا: python main.py
"""
import asyncio
import uvicorn
import threading
from config import config
from core.brain import SuperBrain
from core.task_scheduler import SmartScheduler
from robots.real_robots import RealRobotManager, register_all_real_robots
from api import server

async def main_loop():
    # 1. بیدار کردن مغز
    brain = SuperBrain()
    manager = RealRobotManager(brain)  # real execution (subclass; core untouched)
    scheduler = SmartScheduler()

    # اتصال به API
    server.brain = brain
    server.manager = manager
    server.scheduler = scheduler

    brain.status = "ACTIVE"
    print(f"\n{'='*50}")
    print(f"🧠 {brain.name} فعال شد")
    print(f"📡 API: http://localhost:{config.API_PORT}/docs")
    print(f"{'='*50}\n")

    # 2. ثبت ربات های واقعی (نمونه های شبیه سازی شده بازنشسته شدن)
    register_all_real_robots(manager)

    # 3. چند کار واقعی نمونه
    scheduler.add_task("چک سلامت سایت اصلی", "web_check", priority=8,
                       payload={"url": "https://victoriatourandadventure.com"})
    scheduler.add_task("چک سلامت اپ", "web_check", priority=8,
                       payload={"url": "https://app.victoriatourandadventure.com"})
    scheduler.add_task("قیمت لحظه ای بازار", "market_data", priority=6,
                       payload={"symbols": ["BTC-USD", "ETH-USD", "CAD=X"]})
    scheduler.add_task("جستجوی وب نمونه", "web_search", priority=5,
                       payload={"query": "Victoria BC tourism"})

    # 4. اجرای خودکار کارها
    while scheduler.queue:
        task = scheduler.get_next()
        await manager.assign_task(task)
        await asyncio.sleep(1)

    print("\n✅ تمام کارهای اولیه واگذار شد. سیستم در حالت انتظار...")
    print("برای اضافه کردن کار جدید از API استفاده کن یا کد را تغییر بده")

    # حلقه زنده نگه داشتن
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)
        # چک سلامت ربات ها
        # اینجا میتونی منطق خودترمیمی اضافه کنی

def run_api():
    uvicorn.run(server.app, host=config.API_HOST, port=config.API_PORT, log_level="error")

if __name__ == "__main__":
    # API در یک ترد جدا
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # حلقه اصلی مغز
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n🧠 SUPER BRAIN خاموش شد. خدانگهدار!")
