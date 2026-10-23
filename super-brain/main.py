
"""
SUPER BRAIN - سوپر ربات مدیر هوشمند
اجرا: python main.py
"""
import asyncio
import uvicorn
import threading
from config import config
from core.brain import SuperBrain
from core.robot_manager import RobotManager
from core.task_scheduler import SmartScheduler
from robots.sample_robots import SAMPLE_ROBOTS
from api import server

async def main_loop():
    # 1. بیدار کردن مغز
    brain = SuperBrain()
    manager = RobotManager(brain)
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

    # 2. ثبت ربات های نمونه (شما ربات های خودت رو جایگزین کن)
    for r in SAMPLE_ROBOTS:
        manager.register_robot(r["name"], r["type"], r["capabilities"])

    # 3. اضافه کردن چند کار نمونه
    scheduler.add_task("تمیز کردن سالن اصلی", "cleaning", priority=6, duration=4)
    scheduler.add_task("بررسی دوربین های امنیتی", "security", priority=9, duration=2)
    scheduler.add_task("تحویل بسته به انبار", "delivery", priority=7, duration=3)
    scheduler.add_task("تحلیل داده های امروز", "data_analysis", priority=5, duration=5)

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
