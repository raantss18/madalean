"""Children of the server: local llama-server, Lean checks, GPU/disk monitor, updates, Jupyter."""
import shutil

SETPRIV = shutil.which("setpriv")


def guarded(program: str, args: list[str]) -> list[str]:
    """Command line that dies with the server, even after `kill -9` of the server (PR_SET_PDEATHSIG)."""
    if SETPRIV:
        return [SETPRIV, "--pdeathsig", "KILL", "--", program, *args]
    return [program, *args]
