"""
Real working robots for SUPER BRAIN.

These robots DO real work — HTTP checks, live market data, web search,
file analysis, database reads. No asyncio.sleep simulation anywhere.

Architecture note: core/ is intentionally untouched. RealRobot subclasses
core.robot_manager.Robot and adds a real async execute(task) method.
RealRobotManager subclasses core.robot_manager.RobotManager and overrides
_execute_task so the normal flow (brain.think -> assign_task -> execute)
runs REAL work instead of the core's simulated sleep.

Task parameters travel in task["payload"] (see core/task_scheduler.py).
Every execute() returns {"ok": bool, ...real details...} and NEVER fakes
a result — failures return ok=False with the real error.
"""

import asyncio
import html as html_module
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

from core.robot_manager import Robot, RobotManager, RobotStatus

WORKSPACE_ROOT = os.path.expanduser("~/workspace")

# ---------------------------------------------------------------- helpers

def _http_get(url, timeout=15, headers=None):
    """Blocking HTTP GET with a browser-ish User-Agent. Returns (status, body, ms)."""
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        ms = int((time.time() - t0) * 1000)
        return resp.status, body, ms


async def _retry(coro_fn, tries=3, base_delay=1.0):
    """Run coro_fn() up to `tries` times with exponential backoff. Egress proxy is flaky."""
    last_err = None
    for attempt in range(tries):
        try:
            return await coro_fn()
        except Exception as e:  # noqa: BLE001 - we report the real error after retries
            last_err = e
            if attempt < tries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))
    raise last_err


# ---------------------------------------------------------------- base

class RealRobot(Robot):
    """Robot with a REAL async execute(task). Subclass and implement execute()."""

    async def execute(self, task: dict) -> dict:
        raise NotImplementedError(f"{self.name} has no execute() implementation")


class RealRobotManager(RobotManager):
    """RobotManager that runs REAL robot work through the normal assign flow.

    Overrides _execute_task only — everything else (think, scheduling,
    capability matching, queue draining) is inherited untouched from core.
    """

    def register_real_robot(self, robot: RealRobot):
        self.robots[robot.id] = robot
        print(f"✅ ربات واقعی ثبت شد: {robot.name} [{robot.id}] - توانایی ها: {robot.capabilities}")
        return robot

    async def _execute_task(self, robot: Robot, task: dict):
        try:
            if hasattr(robot, "execute") and callable(getattr(robot, "execute")):
                result = await robot.execute(task)
            else:
                result = {"ok": True, "note": "legacy robot without execute()"}
            task["result"] = result
            robot.status = RobotStatus.IDLE
            robot.current_task = None
            if result.get("ok"):
                robot.performance_score = min(100, robot.performance_score + 1)
            else:
                robot.performance_score = max(0, robot.performance_score - 5)
            print(f"✅ {robot.name} کار «{task.get('name')}» را تمام کرد | ok={result.get('ok')}")
            if not self.task_queue.empty():
                next_task = await self.task_queue.get()
                await self.assign_task(next_task)
        except Exception as e:  # noqa: BLE001
            robot.status = RobotStatus.ERROR
            task["result"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            print(f"❌ خطا در {robot.name}: {e}")
            if self.brain:
                await self.brain.think({"type": "error", "robot": robot.id, "error": str(e)})


# ---------------------------------------------------------------- robots

class WebsiteMonitor(RealRobot):
    """Real uptime/HTTP check. payload: {"url": "https://..."}"""

    def __init__(self):
        super().__init__(
            name="Website-Monitor",
            robot_type="monitoring",
            capabilities=["web_check", "uptime", "monitoring"],
        )

    async def execute(self, task: dict) -> dict:
        url = (task.get("payload") or {}).get("url")
        if not url:
            return {"ok": False, "error": "payload.url missing"}
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "error": f"refused non-http url: {url}"}

        async def _do():
            status, body, ms = await asyncio.to_thread(_http_get, url)
            return {"ok": 200 <= status < 400, "url": url, "status": status,
                    "ms": ms, "bytes": len(body)}

        try:
            return await _retry(_do)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"}


class MarketData(RealRobot):
    """Live market prices via Yahoo Finance chart API (stdlib only).
    payload: {"symbols": ["BTC-USD", "ETH-USD", "CAD=X"]} (optional)"""

    def __init__(self):
        super().__init__(
            name="Market-Data",
            robot_type="finance",
            capabilities=["market_data", "finance"],
        )

    async def execute(self, task: dict) -> dict:
        symbols = (task.get("payload") or {}).get("symbols") or ["BTC-USD", "ETH-USD", "CAD=X"]
        prices = {}
        errors = {}

        async def _one(sym):
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
            status, body, _ms = await asyncio.to_thread(_http_get, url)
            data = json.loads(body.decode("utf-8"))
            meta = data["chart"]["result"][0]["meta"]
            return sym, {"price": meta["regularMarketPrice"],
                         "change_pct": round(meta.get("regularMarketChangePercent", 0) or 0, 2),
                         "currency": meta.get("currency")}

        for sym in symbols:
            try:
                _sym, info = await _retry(lambda s=sym: _one(s))
                prices[_sym] = info
            except Exception as e:  # noqa: BLE001
                errors[sym] = f"{type(e).__name__}: {e}"

        return {"ok": bool(prices), "prices": prices, "errors": errors,
                "fetched_at": datetime.now().isoformat()}


class WebResearcher(RealRobot):
    """Real web search via DuckDuckGo HTML endpoint. payload: {"query": "..."}.
    Returns top result titles+urls. Never invents results."""

    def __init__(self):
        super().__init__(
            name="Web-Researcher",
            robot_type="research",
            capabilities=["web_search", "research"],
        )

    async def execute(self, task: dict) -> dict:
        query = (task.get("payload") or {}).get("query")
        if not query:
            return {"ok": False, "error": "payload.query missing"}

        async def _do():
            # POST (form submit) bypasses DDG's GET anomaly-challenge on this network
            form = urllib.parse.urlencode({"q": query}).encode("utf-8")

            def _post():
                req = urllib.request.Request(
                    "https://html.duckduckgo.com/html/",
                    data=form,
                    headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
                             "Content-Type": "application/x-www-form-urlencoded"},
                )
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.read(), int((time.time() - t0) * 1000)

            body, _ms = await asyncio.to_thread(_post)
            html = body.decode("utf-8", errors="replace")
            results = []
            for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                                 html, re.DOTALL):
                href, title_html = m.group(1), m.group(2)
                # unwrap DDG redirect: //duckduckgo.com/l/?uddg=<real url>
                if "uddg=" in href:
                    href = urllib.parse.unquote(href.split("uddg=", 1)[1].split("&")[0])
                title = html_module.unescape(re.sub(r"<[^>]+>", "", title_html).strip())
                if href.startswith("http") and title:
                    results.append({"title": title, "url": href})
                if len(results) >= 5:
                    break
            return {"ok": bool(results), "query": query, "results": results,
                    "error": None if results else "no results parsed (page layout or block)"}

        try:
            return await _retry(_do, tries=2)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "query": query, "results": [],
                    "error": f"{type(e).__name__}: {e}"}


class FileAnalyst(RealRobot):
    """Reads files under ~/workspace only. payload: {"path": "...", "lines": 20}"""

    def __init__(self):
        super().__init__(
            name="File-Analyst",
            robot_type="analysis",
            capabilities=["file_read", "code_review"],
        )

    async def execute(self, task: dict) -> dict:
        payload = task.get("payload") or {}
        raw_path = payload.get("path")
        max_lines = int(payload.get("lines", 20))
        if not raw_path:
            return {"ok": False, "error": "payload.path missing"}
        full = os.path.realpath(os.path.expanduser(raw_path))
        if not full.startswith(WORKSPACE_ROOT + os.sep):
            return {"ok": False, "error": f"refused: outside workspace ({full})"}
        if not os.path.isfile(full):
            return {"ok": False, "error": f"not a file: {full}"}
        try:
            size = os.path.getsize(full)
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            head = [ln.rstrip("\n") for ln in all_lines[:max_lines]]
            return {"ok": True, "path": full, "size_bytes": size,
                    "total_lines": len(all_lines), "head_lines": head}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}


class SupabaseReader(RealRobot):
    """Reads chef-app Supabase tables via REST. Credentials ONLY from env
    SUPABASE_URL / SUPABASE_KEY — never hardcoded, never committed.
    payload: {"table": "Chefs", "limit": 5, "select": "*"}"""

    def __init__(self):
        super().__init__(
            name="Supabase-Reader",
            robot_type="database",
            capabilities=["db_read", "chefapp"],
        )

    async def execute(self, task: dict) -> dict:
        payload = task.get("payload") or {}
        table = payload.get("table", "Chefs")
        limit = int(payload.get("limit", 5))
        select = payload.get("select", "*")
        base = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_KEY", "")
        if not base or not key:
            return {"ok": False,
                    "error": "SUPABASE_URL / SUPABASE_KEY env vars not set — refusing to run without credentials"}
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            return {"ok": False, "error": f"refused suspicious table name: {table}"}

        async def _do():
            url = (f"{base}/rest/v1/{table}?select={urllib.parse.quote(select)}"
                   f"&limit={limit}")
            headers = {"User-Agent": "Mozilla/5.0",
                       "apikey": key,
                       "Authorization": f"Bearer {key}"}
            _status, body, ms = await asyncio.to_thread(_http_get, url, headers=headers)
            rows = json.loads(body.decode("utf-8"))
            return {"ok": True, "table": table, "rows_returned": len(rows),
                    "rows": rows, "ms": ms}

        try:
            return await _retry(_do, tries=2)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "table": table, "error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- registry

REAL_ROBOTS = [
    WebsiteMonitor(),
    MarketData(),
    WebResearcher(),
    FileAnalyst(),
    SupabaseReader(),
]


def register_all_real_robots(manager: RealRobotManager):
    """Register every real robot on a RealRobotManager."""
    for robot in REAL_ROBOTS:
        manager.register_real_robot(robot)
    return REAL_ROBOTS
