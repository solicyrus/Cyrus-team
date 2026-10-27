
import asyncio
import json
import time
import psutil
from datetime import datetime
from typing import Dict, List
from config import config
from .llm import ask_decision

class SuperBrain:
    """مغز مرکزی سوپر هوشمند"""

    def __init__(self):
        self.name = config.BRAIN_NAME
        self.start_time = datetime.now()
        self.memory = self._load_memory()
        self.knowledge_base = {}
        self.decision_log = []
        self.status = "INITIALIZING"
        print(f"🧠 {self.name} در حال بیدار شدن...")

    def _load_memory(self):
        try:
            with open(config.MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"experiences": [], "learned_rules": [], "robot_stats": {}}

    def _save_memory(self):
        with open(config.MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    async def think(self, context: dict) -> dict:
        """تفکر و تصمیم گیری هوشمند — اول AI واقعی، اگر نشد قوانین داخلی.

        Every subordinate robot decides through this method (via
        RobotManager.assign_task), so wiring AI here gives the WHOLE team
        real thinking with one change.
        """
        # 1. تحلیل وضعیت سیستم
        system_health = self._check_system_health()

        # 2. اول AI واقعی (در ترد جدا تا حلقه async قفل نشه)
        ai_decision, ai_used = await asyncio.to_thread(
            ask_decision, context, system_health)

        if ai_used and ai_decision:
            priority = ai_decision["priority"]
            action = ai_decision["action"]
            reasoning = ai_decision["reasoning"]
        else:
            # 3. fallback قوانین داخلی (بدون کلید API هم کار می‌کنه)
            priority = self._calculate_priority(context)
            action = self._decide_action(context, priority, system_health)
            reasoning = (f"با توجه به اولویت {priority} و سلامت سیستم "
                         f"{system_health['cpu']}%, بهترین اقدام انتخاب شد.")

        # 4. ثبت تصمیم
        decision = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "system_health": system_health,
            "priority": priority,
            "action": action,
            "reasoning": reasoning,
            "ai_used": ai_used,
        }
        self.decision_log.append(decision)
        self.memory["experiences"].append(decision)
        if len(self.decision_log) > 100:
            self._save_memory()
        return decision

    def _check_system_health(self):
        return {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "uptime": str(datetime.now() - self.start_time)
        }

    def _calculate_priority(self, context: dict) -> int:
        # هوش مصنوعی ساده برای اولویت بندی
        if context.get("type") == "critical": return 10
        if context.get("type") == "error": return 9
        if "urgent" in str(context).lower(): return 8
        return 5

    def _decide_action(self, context, priority, health):
        if health["cpu"] > 90:
            return "REDUCE_LOAD"
        if priority >= 9:
            return "IMMEDIATE_EXECUTION"
        if priority >= 7:
            return "SCHEDULE_HIGH"
        return "SCHEDULE_NORMAL"

    def learn(self, feedback: dict):
        """یادگیری از بازخورد"""
        self.memory["learned_rules"].append(feedback)
        self._save_memory()
        print(f"🧠 یاد گرفتم: {feedback}")

    def get_status(self):
        return {
            "name": self.name,
            "status": self.status,
            "uptime": str(datetime.now() - self.start_time),
            "total_decisions": len(self.decision_log),
            "memory_size": len(self.memory["experiences"]),
            "health": self._check_system_health()
        }
