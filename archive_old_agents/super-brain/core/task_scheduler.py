
import asyncio
import heapq
from datetime import datetime

class SmartScheduler:
    """زمانبند هوشمند کارها"""

    def __init__(self):
        self.queue = []  # heap queue: (priority, time, task)
        self.completed = []

    def add_task(self, name, capability_required="general", priority=5, duration=2, payload=None):
        task = {
            "id": f"task-{len(self.queue)+len(self.completed)+1}",
            "name": name,
            "capability_required": capability_required,
            "priority": priority,
            "duration": duration,
            "payload": payload or {},
            "created_at": datetime.now().isoformat()
        }
        heapq.heappush(self.queue, (-priority, datetime.now(), task))  # منفی برای max-heap
        print(f"📋 کار جدید: {name} | اولویت: {priority} | نیاز: {capability_required}")
        return task

    def get_next(self):
        if self.queue:
            return heapq.heappop(self.queue)[2]
        return None

    def list_pending(self):
        return [t[2] for t in sorted(self.queue, reverse=True)]
