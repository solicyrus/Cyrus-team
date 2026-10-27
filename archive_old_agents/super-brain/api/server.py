
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="SUPER BRAIN API", description="API کنترل سوپر ربات مدیر")

# اینها بعدا از main ست میشن
brain = None
manager = None
scheduler = None

class TaskRequest(BaseModel):
    name: str
    capability_required: str = "general"
    priority: int = 5
    duration: int = 2
    payload: dict = {}

class RobotRequest(BaseModel):
    name: str
    robot_type: str
    capabilities: List[str]

@app.get("/")
def root():
    return {"message": "🧠 SUPER BRAIN Online", "brain": brain.get_status() if brain else {}}

@app.get("/robots")
def list_robots():
    return manager.get_all_robots() if manager else []

@app.post("/robots")
def add_robot(req: RobotRequest):
    robot = manager.register_robot(req.name, req.robot_type, req.capabilities)
    return robot.to_dict()

@app.post("/tasks")
async def create_task(req: TaskRequest):
    task = scheduler.add_task(req.name, req.capability_required, req.priority, req.duration, req.payload)
    robot = await manager.assign_task(task)
    return {"task": task, "assigned_to": robot.to_dict() if robot else "queued"}

@app.get("/tasks/pending")
def pending_tasks():
    return scheduler.list_pending()

@app.get("/brain/status")
def brain_status():
    return brain.get_status()

@app.get("/brain/decisions")
def brain_decisions():
    return brain.decision_log[-20:]
