"""Muziek via de geluidskaart analyseren: microfoon, line-in of het geluid van de computer zelf.

Voor het geluid van de computer zelf (Spotify, YouTube, DJ-software) kies je een 'loopback'-apparaat:
  Windows: een apparaat met [Loopback] in de naam, of 'Stereomix'
  macOS:   BlackHole (gratis) als tussenstation
  Linux:   'Monitor of …' instellen als standaard-opname (bijv. met pavucontrol)
"""
import queue
import threading
import time

import numpy as np

try:
    import sounddevice as sd
except (ImportError, OSError):     # geen sounddevice of geen PortAudio: geen geluidskaart, de rest werkt gewoon
    sd = None

from .beatluister import SR, Analyse

LOOPBACK_WOORDEN = ("loopback", "stereo mix", "stereomix", "wave out", "what u hear", "monitor of", "blackhole",
                    "soundflower", "vb-audio", "cable output")


class Herbemonsteraar:
    """Lineaire omzetting naar 44,1 kHz, die over blokgrenzen heen doorloopt."""

    def __init__(self, van, naar=SR):
        self.stap = float(van) / naar
        self.pos = 0.0
        self.rest = np.zeros(0, dtype=np.float32)

    def __call__(self, x):
        buf = np.concatenate((self.rest, x))
        if len(buf) < 2:
            self.rest = buf
            return np.zeros(0, dtype=np.float32)
        n = int(np.floor((len(buf) - 1 - self.pos) / self.stap)) + 1
        idx = self.pos + np.arange(n) * self.stap
        uit = np.interp(idx, np.arange(len(buf)), buf).astype(np.float32)
        eind = self.pos + n * self.stap
        weg = int(np.floor(eind))
        self.rest = buf[weg:]
        self.pos = eind - weg
        return uit


def apparaten():
    if sd is None:
        return []
    try:
        lijst = sd.query_devices()
        hostapis = sd.query_hostapis()
        standaard = sd.default.device[0] if sd.default.device else None
    except Exception as e:
        print("Geluidsapparaten opvragen mislukt:", e, flush=True)
        return []
    uit = []
    for i, d in enumerate(lijst):
        if d.get("max_input_channels", 0) <= 0:
            continue
        api = hostapis[d["hostapi"]]["name"] if d.get("hostapi") is not None else ""
        naam = d["name"]
        uit.append({"naam": f"{naam} ({api})" if api else naam, "kanalen": d["max_input_channels"],
                    "standaard": i == standaard, "loopback": any(w in naam.lower() for w in LOOPBACK_WOORDEN),
                    "samplerate": d.get("default_samplerate")})
    return uit


def _zoek(naam):
    """Index van het apparaat met deze naam (indexen veranderen als je iets in- of uitplugt, namen niet)."""
    if not naam:
        return None
    hostapis = sd.query_hostapis()
    for i, d in enumerate(sd.query_devices()):
        api = hostapis[d["hostapi"]]["name"] if d.get("hostapi") is not None else ""
        if d.get("max_input_channels", 0) > 0 and naam in (f"{d['name']} ({api})", d["name"]):
            return i
    raise OSError(f"geluidsapparaat '{naam}' niet gevonden")


class AudioInvoer:
    def __init__(self, engine):
        self.engine = engine
        self.draad = None
        self.stoppen = threading.Event()
        self.fout = ""
        self.huidig = None
        self.lock = threading.Lock()
        self.status_bijwerken()

    def status_bijwerken(self):
        self.engine.extra_status["audio"] = {
            "beschikbaar": sd is not None,
            "aan": self.draad is not None and self.draad.is_alive(),
            "apparaat": self.huidig,
            "fout": self.fout,
        }

    def bijwerken(self):
        """Instellingen uit de show toepassen (aan/uit, welk apparaat)."""
        with self.engine.lock:
            cfg = dict(self.engine.data.get("audio") or {})
        with self.lock:
            gewenst = cfg.get("apparaat") if cfg.get("aan") else False
            actief = self.draad is not None and self.draad.is_alive()
            if actief and gewenst is not False and gewenst == self.huidig:
                return
            self._stop()
            if gewenst is not False and sd is not None:
                self.huidig = gewenst
                self.fout = ""
                self.stoppen = threading.Event()
                self.draad = threading.Thread(target=self._luister, args=(gewenst, self.stoppen), daemon=True,
                                              name="audio")
                self.draad.start()
            elif gewenst is not False:
                self.fout = "Geluidskaart niet beschikbaar (sounddevice/PortAudio ontbreekt)"
            self.status_bijwerken()

    def _stop(self):
        if self.draad is not None:
            self.stoppen.set()
            self.draad.join(timeout=2.0)
        self.draad, self.huidig = None, None

    def stop(self):
        with self.lock:
            self._stop()
            self.status_bijwerken()

    def _luister(self, naam, stoppen):
        rij = queue.Queue(maxsize=64)
        analyse = Analyse("audio", zender=self.engine.beat_bericht)

        def terugroep(indata, frames, tijd, status):
            try:
                rij.put_nowait((indata.copy(), time.time()))
            except queue.Full:
                pass           # de analyse loopt achter: dit stukje overslaan

        while not stoppen.is_set():
            try:
                apparaat = _zoek(naam)
                info = sd.query_devices(apparaat if apparaat is not None else sd.default.device[0])
                kanalen = max(1, min(2, int(info["max_input_channels"])))
                stream, sr = None, None
                for probeer in (SR, info.get("default_samplerate") or 48000, 48000):
                    try:
                        stream = sd.InputStream(device=apparaat, channels=kanalen, samplerate=probeer, dtype="float32",
                                                blocksize=1024, callback=terugroep)
                        sr = probeer
                        break
                    except Exception as e:
                        fout = e
                if stream is None:
                    raise fout
                omzetten = Herbemonsteraar(sr) if int(sr) != SR else None
                with stream:
                    self.fout = ""
                    self.status_bijwerken()
                    print(f"Luistert naar {info['name']} ({int(sr)} Hz)", flush=True)
                    while not stoppen.is_set():
                        try:
                            blok, t = rij.get(timeout=0.5)
                        except queue.Empty:
                            continue
                        mono = blok.mean(axis=1) if blok.ndim == 2 else blok
                        if omzetten is not None:
                            mono = omzetten(mono)
                        analyse.voer_mono(mono.astype(np.float32), t)
            except Exception as e:
                self.fout = str(e) or e.__class__.__name__
                self.status_bijwerken()
                print("Geluidskaart:", self.fout, flush=True)
                stoppen.wait(3.0)
        self.status_bijwerken()
