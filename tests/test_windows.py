"""De app moet ook starten waar Linux-onderdelen (fcntl, termios, …) niet bestaan, zoals op Windows."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLEEN_UNIX = ("fcntl", "termios", "pwd", "grp", "resource", "tty", "pty", "syslog", "crypt")

SCRIPT = f"""
import importlib.abc, sys
class Blok(importlib.abc.MetaPathFinder):
    def find_spec(self, naam, pad, doel=None):
        if naam.split('.')[0] in {ALLEEN_UNIX!r}:
            raise ModuleNotFoundError("No module named " + repr(naam))
for m in list(sys.modules):
    if m.split('.')[0] in {ALLEEN_UNIX!r}:
        del sys.modules[m]
sys.meta_path.insert(0, Blok())
import dmxdesk.app, dmxdesk.server, dmxdesk.audio, dmxdesk.midi, dmxdesk.uitvoer, dmxdesk.beatluister
from dmxdesk.engine import Engine
Engine(None).render(1000.0)
print("ok")
"""


def test_start_zonder_unix_onderdelen():
    r = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr
