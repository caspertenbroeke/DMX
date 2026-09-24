#!/usr/bin/env python3
"""Start de zojuist gebouwde app echt op en kijkt of hij antwoordt (na packaging/bouw.py).

  python packaging/rooktest.py            zonder venster (--server): moet werken, anders faalt de build
  python packaging/rooktest.py --venster  gewoon opstarten zoals een gebruiker; meldt of het app-venster opengaat
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HIER)
sys.path.insert(0, ROOT)
from dmxdesk import paden  # noqa: E402


def programma():
    if sys.platform == "win32":
        return os.path.join(ROOT, "dist", "DMXDesk", "DMXDesk.exe")
    if sys.platform == "darwin":
        return os.path.join(ROOT, "dist", "DMXDesk.app", "Contents", "MacOS", "DMXDesk")
    return os.path.join(ROOT, "dist", "DMXDesk", "DMXDesk")


def vraag(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return r.status, r.read()


def wacht_op(poort, proc, seconden=90):
    eind = time.time() + seconden
    while time.time() < eind:
        if proc.poll() is not None:
            return False
        try:
            if json.loads(vraag(f"http://127.0.0.1:{poort}/api/info")[1]).get("naam") == "DMXDesk":
                return True
        except Exception:
            time.sleep(1)
    return False


def zonder_venster():
    poort = 8765
    tmp = tempfile.mkdtemp()
    log = open(os.path.join(tmp, "uitvoer.log"), "w+")
    proc = subprocess.Popen([programma(), "--server", "--poort", str(poort), "--show", os.path.join(tmp, "show.json")],
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        ok = wacht_op(poort, proc)
        if ok:
            for pad in ("/", "/desk", "/static/js/main.js", "/api/state", "/api/bibliotheek?zoek=par",
                        "/api/bibliotheek/profielen?sleutel=ingebouwd/rgb_3"):
                status, _ = vraag(f"http://127.0.0.1:{poort}{pad}")
                assert status == 200, pad
            state = json.loads(vraag(f"http://127.0.0.1:{poort}/api/state")[1])
            print("Rooktest OK:", state["versie"], "-", len(state["fixtures"]), "lampen,",
                  state["bibliotheek"]["aantal"], "in de bibliotheek, qr:", state["systeem"]["qr"])
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.seek(0)
        print("---- uitvoer van de app ----\n" + log.read())
    if not ok:
        sys.exit("De app startte niet of antwoordde niet (zie hierboven).")


def met_venster():
    logpad = os.path.join(paden.gebruikers_map(), "dmxdesk.log")
    if os.path.exists(logpad):
        os.remove(logpad)
    proc = subprocess.Popen([programma()])
    try:
        ok = wacht_op(8080, proc, 60)
        time.sleep(8)       # het venster de tijd geven om te openen (of te mislukken)
        nog_bezig = proc.poll() is None
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
    log = open(logpad, encoding="utf-8", errors="replace").read() if os.path.exists(logpad) else "(geen logbestand)"
    print("---- logbestand ----\n" + log)
    if not ok:
        sys.exit("De app startte niet of antwoordde niet (zie het logbestand hierboven).")
    if "mislukt" in log or "niet beschikbaar" in log or not nog_bezig:
        print("::warning::De app draait, maar het eigen app-venster ging niet open (dan opent hij in de browser).")
    else:
        print("Venstertest OK: de app draait met een eigen venster.")


if __name__ == "__main__":
    met_venster() if "--venster" in sys.argv else zonder_venster()
