"""CYRUS TEAM — venv_bootstrap.py

INTERPRETER STANDARD (VIRAL-PROTOCOL.md §7).

Team entry points (main_pipeline.py, check_system_health.py)
run on the robot-team venv python:

    ~/workspace/ultimate-robot-team/venv/bin/python

That interpreter carries python-dotenv + openai. Any other
interpreter on this machine does NOT — and the old guarded
`try: from dotenv import load_dotenv ... except: pass` then
skipped the repo-root .env SILENTLY: the pipeline ran
unconfigured and the health check reported every service
NOT_SET while .env was fully configured (a silent no-op, found
2026-10-27).

ensure_team_interpreter() is called by the entry points when
they run as scripts, BEFORE anything reads the environment:

  * dotenv AND openai importable -> return silently.
  * Either missing -> re-exec the SAME script under the venv
    python (argv preserved, one-shot sentinel so a broken venv
    can never loop).
  * Venv python missing, or already re-execed and STILL missing
    -> FAIL LOUDLY on stderr with the exact fix, exit code 2.

Imported use (tests importing the pipeline module) never
triggers this — it only guards script execution.
"""

import os
import sys

VENV_PYTHON = os.path.expanduser(
    "~/workspace/ultimate-robot-team/venv/bin/python")
REQUIRED_MODULES = ("dotenv", "openai")
_SENTINEL = "CYRUS_TEAM_VENV_REEXEC"


def _missing_modules():
    missing = []
    for name in REQUIRED_MODULES:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    return missing


def _fail_loudly(missing, why):
    sys.stderr.write(
        "\n[cyrus-team] FATAL — wrong interpreter, refusing to "
        "run unconfigured.\n"
        f"  interpreter: {sys.executable}\n"
        f"  missing modules: {', '.join(missing)}\n"
        f"  reason: {why}\n"
        "  The team standard is the robot-team venv python:\n"
        f"      {VENV_PYTHON}\n"
        "  Re-run with it, e.g.:\n"
        f"      {VENV_PYTHON} {os.path.basename(sys.argv[0])} ...\n"
        "  (Silently skipping the .env load is forbidden — "
        "VIRAL-PROTOCOL §7.)\n")
    raise SystemExit(2)


def ensure_team_interpreter():
    """Guarantee dotenv + openai are importable, re-execing
    under the team venv python when needed. Never returns in a
    knowingly-broken state: it either re-execs or exits loudly.
    """
    missing = _missing_modules()
    if not missing:
        return
    if os.environ.get(_SENTINEL) == "1":
        _fail_loudly(missing, "already re-execed once under the "
                              "venv python and the modules are "
                              "STILL missing — the venv itself is "
                              "broken (repair it; do not loop)")
    if not (os.path.isfile(VENV_PYTHON)
            and os.access(VENV_PYTHON, os.X_OK)):
        _fail_loudly(missing, f"team venv python not found at "
                              f"{VENV_PYTHON}")
    # "Already running under the venv" is tested via sys.prefix:
    # a venv's python binary is a SYMLINK to the base interpreter,
    # so realpath(sys.executable) collapses venv and system
    # pythons to the same file — sys.prefix is the honest test.
    venv_root = os.path.dirname(os.path.dirname(VENV_PYTHON))
    if os.path.realpath(sys.prefix) == os.path.realpath(venv_root):
        _fail_loudly(missing, "this IS the venv python (prefix "
                              "match), yet the modules are "
                              "missing — the venv itself is "
                              "broken")
    sys.stderr.write(
        f"[cyrus-team] interpreter {sys.executable} is missing "
        f"{', '.join(missing)} — re-running under the team venv "
        f"python ({VENV_PYTHON}). Standard: VIRAL-PROTOCOL §7.\n")
    os.environ[_SENTINEL] = "1"
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)
