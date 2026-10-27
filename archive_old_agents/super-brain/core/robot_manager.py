
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List
from enum import Enum

class RobotStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"
    CHARGING = "charging"

class Robot:
    def __init__(self, name: str, robot_type: str, capabilities: List[str]):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.type = robot_type
        self.capabilities = capabilities
        self.status = RobotStatus.IDLE
        self.current_task = None
        self.task_history = []
        self.last_heartbeat = datetime.now()
        self.performance_score = 100

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "current_task": self.current_task,
            "performance": self.performance_score,
            "last_seen": self.last_heartbeat.isoformat()
        }

class RobotManager:
    """مدیریت تمام ربات ها - قلب سیستم"""

    def __init__(self, brain):
        self.brain = brain
        self.robots: Dict[str, Robot] = {}
        self.task_queue = asyncio.Queue()

    def register_robot(self, name, robot_type, capabilities):
        robot = Robot(name, robot_type, capabilities)
        self.robots[robot.id] = robot
        print(f"✅ ربات جدید ثبت شد: {name} [{robot.id}] - توانایی ها: {capabilities}")
        return robot

    def get_best_robot_for_task(self, required_capability: str) -> Robot:
        candidates = [
            r for r in self.robots.values()
            if required_capability in r.capabilities and r.status == RobotStatus.IDLE
        ]
        if not candidates:
            return None
        # انتخاب بهترین بر اساس امتیاز عملکرد
        return sorted(candidates, key=lambda x: x.performance_score, reverse=True)[0]

    async def assign_task(self, task: dict):
        """واگذاری هوشمند کار به بهترین ربات"""
        decision = await self.brain.think(task)
        capability = task.get("capability_required", "general")
        robot = self.get_best_robot_for_task(capability)

        if not robot:
            print(f"⚠️ هیچ رباتی برای {capability} آزاد نیست، در صف قرار گرفت")
            await self.task_queue.put(task)
            return None

        robot.status = RobotStatus.BUSY
        robot.current_task = task
        robot.task_history.append(task)
        print(f"🚀 کار '{task.get('name')}' به {robot.name} واگذار شد | تصمیم مغز: {decision['action']}")

        # شبیه سازی انجام کار
        asyncio.create_task(self._execute_task(robot, task))
        return robot

    async def _execute_task(self, robot: Robot, task: dict):
        try:
            duration = task.get("duration", 3)
            await asyncio.sleep(duration)
            robot.status = RobotStatus.IDLE
            robot.current_task = None
            robot.performance_score = min(100, robot.performance_score + 1)
            print(f"✅ {robot.name} کار {task.get('name')} را تمام کرد")
            # چک کردن صف
            if not self.task_queue.empty():
                next_task = await self.task_queue.get()
                await self.assign_task(next_task)
        except Exception as e:
            robot.status = RobotStatus.ERROR
            print(f"❌ خطا در {robot.name}: {e}")
            if self.brain:
                await self.brain.think({"type": "error", "robot": robot.id, "error": str(e)})

    def get_all_robots(self):
        return [r.to_dict() for r in self.robots.values()]

    def heartbeat(self, robot_id):
        if robot_id in self.robots:
            self.robots[robot_id].last_heartbeat = datetime.now()
            self.robots[robot_id].status = RobotStatus.IDLE
