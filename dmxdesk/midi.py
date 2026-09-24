"""MIDI-controllers (APC mini, Launchpad, nanoKONTROL, …): knoppen en faders koppelen aan acties.

Werkt met mido + python-rtmidi. Zonder die pakketten doet de rest van DMXDesk het gewoon.
Koppelen gaat door 'leren': kies in de app een actie en druk dan op de knop of beweeg de fader.
"""
import threading

try:
    import mido
    mido.Backend("mido.backends.rtmidi", load=True)     # zonder python-rtmidi werkt MIDI niet
except Exception:
    mido = None

FADER_ACTIES = ("master", "groep", "fader")


def sleutel(msg):
    """Unieke naam voor een knop of fader, bijv. 'noot:1:36' of 'cc:1:7'."""
    if msg.type in ("note_on", "note_off"):
        return f"noot:{msg.channel + 1}:{msg.note}"
    if msg.type == "control_change":
        return f"cc:{msg.channel + 1}:{msg.control}"
    return None


def waarde(msg):
    if msg.type == "note_on":
        return msg.velocity / 127.0 if msg.velocity > 0 else False
    if msg.type == "note_off":
        return False
    if msg.type == "control_change":
        return msg.value / 127.0
    return None


class Midi:
    def __init__(self, engine):
        self.engine = engine
        self.poort = None
        self.naam = None
        self.leer = None           # {"actie", "arg"} die gekoppeld wordt aan het volgende bericht
        self.laatste = None
        self.fout = ""
        self.lock = threading.Lock()
        self.status_bijwerken()

    def status_bijwerken(self):
        self.engine.extra_status["midi"] = {"beschikbaar": mido is not None, "apparaat": self.naam if self.poort else None,
                                            "fout": self.fout, "leren": self.leer, "laatste": self.laatste}

    @staticmethod
    def apparaten():
        if mido is None:
            return []
        try:
            return sorted(set(mido.get_input_names()))
        except Exception as e:
            print("MIDI-apparaten opvragen mislukt:", e, flush=True)
            return []

    def bijwerken(self):
        with self.engine.lock:
            gewenst = (self.engine.data.get("midi") or {}).get("apparaat") or ""
        with self.lock:
            if self.poort is not None and gewenst == self.naam:
                return
            self._sluiten()
            self.fout = ""
            if gewenst and mido is not None:
                try:
                    kandidaten = [n for n in self.apparaten() if n == gewenst] or \
                                 [n for n in self.apparaten() if n.split(":")[0] == gewenst.split(":")[0]]
                    if not kandidaten:
                        raise OSError(f"MIDI-apparaat '{gewenst}' niet gevonden")
                    self.poort = mido.open_input(kandidaten[0], callback=self.bericht)
                    self.naam = gewenst
                    print("MIDI geopend:", kandidaten[0], flush=True)
                except Exception as e:
                    self.fout = str(e) or e.__class__.__name__
                    self.poort = None
            elif gewenst:
                self.fout = "MIDI niet beschikbaar (mido/python-rtmidi ontbreekt)"
            self.status_bijwerken()

    def _sluiten(self):
        if self.poort is not None:
            try:
                self.poort.close()
            except Exception:
                pass
        self.poort, self.naam = None, None

    def stop(self):
        with self.lock:
            self._sluiten()

    def leren(self, actie, arg=None):
        self.leer = {"actie": actie, "arg": arg} if actie else None
        self.status_bijwerken()

    def bericht(self, msg):
        s = sleutel(msg)
        if s is None:
            return
        w = waarde(msg)
        self.laatste = {"sleutel": s, "waarde": round(w, 3) if isinstance(w, float) else w}
        if self.leer:
            if w is False:        # het loslaten van de knop die net geleerd is
                return
            with self.engine.lock:
                self.engine.data["midi"]["koppelingen"][s] = dict(self.leer)
                self.engine.gewijzigd()
            self.leer = None
            self.status_bijwerken()
            return
        self.status_bijwerken()
        self.uitvoeren(s, w)

    def uitvoeren(self, s, w):
        with self.engine.lock:
            k = (self.engine.data.get("midi") or {}).get("koppelingen", {}).get(s)
        if not k:
            return
        if k["actie"] in FADER_ACTIES:
            w = float(w or 0.0)
        elif s.startswith("noot:"):
            w = bool(w)                  # elke aanslag telt, hoe zacht ook
        else:
            w = bool(w) and w >= 0.5     # CC-knop: 127 = in, 0 = uit
        try:
            self.engine.actie(k["actie"], k.get("arg"), w)
        except Exception as e:
            print("MIDI-actie mislukt:", e, flush=True)
