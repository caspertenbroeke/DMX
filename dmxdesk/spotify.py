"""DMXDesk als Spotify-speaker (Spotify Connect), net als Sonos of raspotify op de Pi.

In de Spotify-app kies je 'DMXDesk' (of de naam die je instelt) als speaker. librespot (ingebouwd in de app)
levert het geluid aan DMXDesk; dat analyseert de muziek eerst en speelt hem met een paar seconden voorsprong
af op de geluidskaart van deze computer. Zo weet de lichtshow vooraf waar de beats en drops vallen.
Spotify Premium is nodig (dat geldt voor elke Spotify Connect-speaker).
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque

try:
    import sounddevice as sd
except (ImportError, OSError):
    sd = None

from . import paden
from .beatluister import SR, Analyse, Doorgever

BRON = "connect"      # naam van deze bron bij de beat-analyse (Spotify via de Pi heet "spotify")
NUMMER = re.compile(r"Loading <(.+?)> with Spotify URI")
VERBONDEN = re.compile(r"Authenticated as|Connected to AP|active device", re.IGNORECASE)


def foutmelding(logboek, code):
    """De laatste fout van librespot, in gewone woorden waar dat kan."""
    fouten = [r.split("]", 1)[-1].strip() for r in logboek if " ERROR " in r or " WARN " in r]
    tekst = " ".join(fouten)
    if "discovery" in tekst.lower():
        oorzaak = next((f.split(":", 1)[1].strip() for f in fouten if "failed to start" in f or "initialise" in f), "")
        return ("Kan niet als speaker op het netwerk verschijnen" + (f" ({oorzaak})" if oorzaak else ""))[:200]
    if "bad credentials" in tekst.lower() or "premium" in tekst.lower():
        return "Spotify weigert het account: voor een Spotify-speaker is Spotify Premium nodig."
    return (fouten[-1] if fouten else f"librespot stopte (code {code})")[:200]


def librespot_pad():
    naam = "librespot.exe" if sys.platform == "win32" else "librespot"
    for pad in (os.environ.get("DMXDESK_LIBRESPOT"), os.path.join(paden.pakket_map(), "bin", naam)):
        if pad and os.path.isfile(pad):
            return pad
    return shutil.which("librespot")


def _geen_venster():
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def ruim_oude_op(pidbestand):
    """Is DMXDesk de vorige keer gecrasht, dan draait zijn librespot misschien nog (dubbele speaker): stoppen."""
    try:
        with open(pidbestand) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return
    try:
        if sys.platform == "win32":
            uit = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                                 timeout=5, **_geen_venster()).stdout
            if "librespot" in uit.lower():
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=5, **_geen_venster())
        else:
            uit = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True, timeout=5).stdout
            if "librespot" in uit:
                os.kill(pid, signal.SIGTERM)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        os.remove(pidbestand)
    except OSError:
        pass


def uitvoer_apparaten():
    if sd is None:
        return []
    try:
        lijst, hostapis = sd.query_devices(), sd.query_hostapis()
        standaard = sd.default.device[1] if sd.default.device else None
    except Exception:
        return []
    uit = []
    for i, d in enumerate(lijst):
        if d.get("max_output_channels", 0) < 2:
            continue
        api = hostapis[d["hostapi"]]["name"] if d.get("hostapi") is not None else ""
        uit.append({"naam": f"{d['name']} ({api})" if api else d["name"], "standaard": i == standaard})
    return uit


def _zoek_uitvoer(naam):
    if not naam:
        return None
    hostapis = sd.query_hostapis()
    for i, d in enumerate(sd.query_devices()):
        api = hostapis[d["hostapi"]]["name"] if d.get("hostapi") is not None else ""
        if d.get("max_output_channels", 0) >= 2 and naam in (f"{d['name']} ({api})", d["name"]):
            return i
    raise OSError(f"geluidsapparaat '{naam}' niet gevonden")


class GeluidskaartUitgang:
    """Afspelen via de geluidskaart van deze computer (PortAudio)."""

    def __init__(self, apparaat=None):
        self.apparaat, self.stream = apparaat, None
        try:       # hoe lang het duurt voor geschreven geluid te horen is (na het openen: de echte waarde)
            nr = _zoek_uitvoer(apparaat)
            self.latentie = float(sd.query_devices(nr if nr is not None else sd.default.device[1])
                                  ["default_high_output_latency"])
        except Exception:
            self.latentie = 0.1

    def start(self):
        nr = _zoek_uitvoer(self.apparaat)
        if nr is None and not any(d.get("max_output_channels", 0) >= 2 for d in sd.query_devices()):
            raise OSError("geen luidspreker of geluidskaart gevonden")
        try:
            self.stream = sd.RawOutputStream(samplerate=SR, channels=2, dtype="int16", device=nr)
            self.stream.start()
        except Exception as e:
            self.stream = None
            raise OSError(f"luidspreker gaat niet open ({e})") from e
        try:
            self.latentie = float(self.stream.latency)
        except (TypeError, ValueError):
            pass

    def schrijf(self, data):
        self.stream.write(data)

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        self.stream = None


class SpotifySpeaker:
    def __init__(self, engine):
        self.engine = engine
        self.proc = None
        self.doorgever = None
        self.huidig = None
        self.fout = ""
        self.nummer = ""
        self.verbonden = False
        self.logboek = deque(maxlen=30)
        self.stoppen = threading.Event()
        self.lock = threading.Lock()
        self.status_bijwerken()

    @staticmethod
    def beschikbaar():
        return librespot_pad() is not None and sd is not None

    def status_bijwerken(self):
        cfg = self.engine.data.get("spotify") or {}
        self.engine.extra_status["spotify"] = {
            "beschikbaar": self.beschikbaar(),
            "aan": self.proc is not None and self.proc.poll() is None,
            "naam": cfg.get("naam"),
            "verbonden": self.verbonden,
            "speelt": bool(self.doorgever and self.doorgever.speelt),
            "nummer": self.nummer,
            "voorsprong": cfg.get("voorsprong"),
            "fout": self.fout or (f"Geen geluid: {self.doorgever.fout}" if self.doorgever and self.doorgever.fout else ""),
        }

    def bijwerken(self):
        with self.engine.lock:
            cfg = dict(self.engine.data.get("spotify") or {})
        gewenst = (cfg.get("naam"), cfg.get("apparaat"), float(cfg.get("voorsprong") or 0),
                   int(cfg.get("zeroconf_poort") or 0)) if cfg.get("aan") else None
        with self.lock:
            draait = self.proc is not None and self.proc.poll() is None
            if draait and gewenst == self.huidig:
                return
            self._stop()
            self.huidig = gewenst
            self.fout = ""
            if gewenst:
                self.stoppen = threading.Event()
                threading.Thread(target=self._bewaak, args=(gewenst, self.stoppen), daemon=True, name="spotify").start()
            self.status_bijwerken()

    def _stop(self):
        self.stoppen.set()
        proc, doorgever = self.proc, self.doorgever
        if doorgever:
            doorgever.stop()
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.proc, self.doorgever, self.verbonden, self.nummer = None, None, False, ""

    def stop(self):
        with self.lock:
            self._stop()
            self.status_bijwerken()

    def _bewaak(self, cfg, stoppen):
        """Start librespot en houdt hem draaiende (ook na een fout of als hij stopt)."""
        naam, apparaat, voorsprong, zc_poort = cfg
        wacht = 0
        while not stoppen.is_set():
            pad = librespot_pad()
            if pad is None or sd is None:
                self.fout = ("librespot ontbreekt in deze installatie" if pad is None
                             else "geluidskaart niet beschikbaar (sounddevice/PortAudio ontbreekt)")
                self.status_bijwerken()
                return
            cache = os.path.join(paden.gebruikers_map(), "spotify")
            os.makedirs(cache, exist_ok=True)
            pidbestand = os.path.join(cache, "librespot.pid")
            ruim_oude_op(pidbestand)
            args = [pad, "--name", naam or "DMXDesk", "--backend", "pipe", "--format", "S16", "--bitrate", "320",
                    "--initial-volume", "100", "--volume-ctrl", "linear", "--device-type", "speaker",
                    "--cache", cache, "--disable-audio-cache"]
            if zc_poort:
                args += ["--zeroconf-port", str(zc_poort)]
            with self.lock:
                if stoppen.is_set():
                    return
                try:
                    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            stdin=subprocess.DEVNULL, **_geen_venster())
                except OSError as e:
                    proc = None
                    self.fout = f"librespot start niet: {e}"
                if proc is not None:
                    try:
                        with open(pidbestand, "w") as f:
                            f.write(str(proc.pid))
                    except OSError:
                        pass
                    doorgever = Doorgever(Analyse(BRON, zender=self.engine.beat_bericht),
                                          GeluidskaartUitgang(apparaat), voorsprong, melding=self.status_bijwerken)
                    self.proc, self.doorgever = proc, doorgever
                self.status_bijwerken()
            if proc is None:
                stoppen.wait(10)
                continue
            gestart = time.time()
            self.logboek.clear()
            print(f"Spotify-speaker '{naam}' gestart (voorsprong {voorsprong:g} s)", flush=True)
            threading.Thread(target=self._lees_logboek, args=(proc,), daemon=True, name="spotify-log").start()
            uit = proc.stdout.fileno()
            try:
                doorgever.draai(lambda: os.read(uit, 8192))
            except OSError:
                doorgever.stop()
            code = proc.wait()
            if stoppen.is_set():
                break
            wacht = 5 if self.verbonden or time.time() - gestart > 60 else min(60, max(5, wacht * 2))
            self.fout = foutmelding(list(self.logboek), code)
            self.verbonden = False
            self.status_bijwerken()
            print(f"Spotify-speaker gestopt: {self.fout} - opnieuw starten over {wacht} s", flush=True)
            stoppen.wait(wacht)

    def _lees_logboek(self, proc):
        for regel in iter(proc.stderr.readline, b""):
            tekst = regel.decode("utf-8", "replace").rstrip()
            self.logboek.append(tekst)
            m = NUMMER.search(tekst)
            if m:
                self.nummer, self.verbonden, self.fout = m.group(1), True, ""
            elif VERBONDEN.search(tekst):
                self.verbonden, self.fout = True, ""
            if proc is self.proc:
                self.status_bijwerken()
