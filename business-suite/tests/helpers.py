"""Shared test bootstrap: import path + a throwaway demo client.

Every test runs against a TEMP COPY of clients/demo-dental so the
CRM writes and reports produced during tests never dirty the shipped
fixture.
"""

import os
import shutil
import sys
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SUITE_DIR = os.path.dirname(TESTS_DIR)
for _path in (SUITE_DIR, TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from business_suite.config import load_client  # noqa: E402


def make_demo_client(testcase):
    """Copy demo-dental into a temp dir and load it as a ClientBundle."""
    tmp = tempfile.mkdtemp(prefix="bs-demo-")
    testcase.addCleanup(shutil.rmtree, tmp, True)
    shutil.copytree(
        os.path.join(SUITE_DIR, "clients", "demo-dental"),
        os.path.join(tmp, "demo-dental"),
    )
    return load_client("demo-dental", clients_dir=tmp)
