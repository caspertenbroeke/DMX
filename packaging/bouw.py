#!/usr/bin/env python3
"""Bouwt de downloadbare DMXDesk-app voor dit besturingssysteem.

  pip install -r packaging/requirements-app.txt pyinstaller pillow
  python packaging/bouw.py [naam]

Het resultaat komt in dist/uitvoer/: een .zip (Windows), .dmg (macOS) of .tar.gz (Linux).
"""
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HIER)
sys.path.insert(0, ROOT)
from dmxdesk import VERSIE  # noqa: E402

DIST = os.path.join(ROOT, "dist")
UIT = os.path.join(DIST, "uitvoer")


def run(*cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def main():
    naam = sys.argv[1] if len(sys.argv) > 1 else f"{sys.platform}-{platform.machine().lower()}"
    run(sys.executable, os.path.join(HIER, "maak_icoon.py"))
    os.environ["DMXDESK_VERSIE"] = VERSIE
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", DIST,
        "--workpath", os.path.join(ROOT, "build"), os.path.join(HIER, "dmxdesk.spec"))
    os.makedirs(UIT, exist_ok=True)
    basis = os.path.join(UIT, f"DMXDesk-{VERSIE}-{naam}")
    if sys.platform == "darwin":
        app = os.path.join(DIST, "DMXDesk.app")
        # ad-hoc ondertekenen: zonder handtekening meldt macOS dat de app 'beschadigd' is
        run("codesign", "--force", "--deep", "--sign", "-", app)
        dmg = basis + ".dmg"
        map_ = os.path.join(DIST, "dmg")
        shutil.rmtree(map_, ignore_errors=True)
        os.makedirs(map_)
        run("ditto", app, os.path.join(map_, "DMXDesk.app"))
        os.symlink("/Applications", os.path.join(map_, "Programma's"))
        for poging in range(4):      # hdiutil faalt soms met 'Resource busy'; dan even wachten en opnieuw
            try:
                run("hdiutil", "create", "-volname", "DMXDesk", "-srcfolder", map_, "-ov", "-format", "UDZO", dmg)
                break
            except subprocess.CalledProcessError:
                if poging == 3:
                    raise
                time.sleep(5)
        print("Klaar:", dmg)
    elif sys.platform == "win32":
        zipnaam = basis + ".zip"
        with zipfile.ZipFile(zipnaam, "w", zipfile.ZIP_DEFLATED) as z:
            for wortel, _, bestanden in os.walk(os.path.join(DIST, "DMXDesk")):
                for b in bestanden:
                    pad = os.path.join(wortel, b)
                    z.write(pad, os.path.relpath(pad, DIST))
        print("Klaar:", zipnaam)
    else:
        tarnaam = basis + ".tar.gz"
        with tarfile.open(tarnaam, "w:gz") as t:
            t.add(os.path.join(DIST, "DMXDesk"), arcname="DMXDesk")
        print("Klaar:", tarnaam)


if __name__ == "__main__":
    main()
