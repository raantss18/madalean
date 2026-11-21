"""Children of the server: local llama-server, Lean checks, GPU/disk monitor, updates, Jupyter, madalean-net."""
import sys

from .. import deps

SETPRIV = deps.tool("setpriv")
# Fallback when util-linux's setpriv is absent: a tiny Python trampoline sets PR_SET_PDEATHSIG (1) = SIGKILL (9),
# exits if the parent already died, then execs the program.
_TRAMPOLINE = ("import ctypes,os,sys;p=os.getppid();ctypes.CDLL(None,use_errno=True).prctl(1,9,0,0,0);"
               "os.getppid()==p or os._exit(1);os.execvp(sys.argv[1],sys.argv[1:])")


def guarded(program: str, args: list[str]) -> list[str]:
    """Command line that dies with the server, even after `kill -9` of the server (PR_SET_PDEATHSIG)."""
    if SETPRIV:
        return [SETPRIV, "--pdeathsig", "KILL", "--", program, *args]
    return [deps.tool("python") or sys.executable, "-I", "-c", _TRAMPOLINE, program, *args]
