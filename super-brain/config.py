
import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    BRAIN_NAME = "SUPER-BRAIN v1.0"
    MAX_ROBOTS = 100
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    LOG_LEVEL = "INFO"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    MEMORY_FILE = "brain_memory.json"
    AUTO_HEAL = True
    HEARTBEAT_INTERVAL = 5  # ثانیه

config = Config()
