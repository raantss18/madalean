"""Isolate every test run (fresh config/cache dirs, never the real profile, never the system keyring) and run
`async def` tests with asyncio.run (pytest-asyncio is not installed)."""
import asyncio
import inspect
import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="madalean-test-"))
os.environ.setdefault("MADALEAN_CONFIG_DIR", str(_TMP / "config"))
os.environ.setdefault("MADALEAN_CACHE_DIR", str(_TMP / "cache"))
# Never the real prefix (~/.local/share/madalean, security review): an empty MADALEAN_HOME = "development checkout"
# for madalean.deps (tools from PATH, workspaces of the checkout). Tests that need a prefix build their own.
os.environ["MADALEAN_HOME"] = str(_TMP / "madalean-home")
os.environ["MADALEAN_NO_UPDATE_CHECK"] = "1"
os.environ["MADALEAN_NO_SELFTEST"] = "1"          # S-AC: the health self-test never starts by itself
os.environ["MADALEAN_NO_SYNTAX_BUILD"] = "1"      # S-AB: no background syntax-card build in test servers
os.environ["MADALEAN_NO_CALCUL_WARM"] = "1"       # S-AO: opening a Calcul document starts no kernel in tests
os.environ["MADALEAN_NO_KEYRING"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ASYNC_TIMEOUT = float(os.environ.get("MADALEAN_TEST_TIMEOUT", "600"))


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        args = {k: pyfuncitem.funcargs[k] for k in pyfuncitem._fixtureinfo.argnames}
        asyncio.run(asyncio.wait_for(pyfuncitem.obj(**args), ASYNC_TIMEOUT))
        return True
    return None


@pytest.fixture(scope="session")
def ws():
    """The real Lean workspace used by Goedel (lean-prover49), else any built one; skip when none is built."""
    from madalean.workspaces import all_workspaces
    wss = [w for w in all_workspaces(scan_user=False) if not w.problems]
    w = next((w for w in wss if w.key == "lean-prover49"), None) or (wss[0] if wss else None)
    if w is None:
        pytest.skip("no built Lean workspace")
    return w
