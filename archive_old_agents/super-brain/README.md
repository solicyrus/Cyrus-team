
# SUPER BRAIN - سوپر مغز مدیریت ربات ها

یک سیستم مدیریت مرکزی هوشمند برای کنترل چندین ربات به صورت همزمان.

## ویژگی ها
- 🧠 مغز مرکزی هوشمند با قابلیت تصمیم گیری خودکار
- 🤖 مدیریت نامحدود ربات (ثبت، کنترل، مانیتورینگ)
- 📋 سیستم صف کار هوشمند (Task Queue)
- 🔌 معماری پلاگین برای اضافه کردن ربات جدید
- 📊 داشبورد API و مانیتورینگ زنده
- 🧠 حافظه بلند مدت و یادگیری از تجربه
- 🚨 سیستم خودترمیم و Failover

## نصب
```bash
pip install -r requirements.txt
python main.py
```

API: http://localhost:8000/docs

## 🧠 AI Thinking (wired 2026-10-22)
The brain thinks with a real LLM first (`core/llm.py`, gpt-4o-mini):
every robot's task goes through `SuperBrain.think()`, so the WHOLE team
gets AI decisions automatically — priority, action and Persian reasoning.
If no `OPENAI_API_KEY` is set (or the API fails), it falls back to the
built-in rule logic. Set the key in your environment:
```bash
export OPENAI_API_KEY="sk-..."
python main.py
```
Cost: ~200 tokens/decision (~$0.001 on gpt-4o-mini).
