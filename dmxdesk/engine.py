"""De motor: rekent elke 1/40 s uit wat elke lamp moet doen en zet dat in DMX-universes.

Lagen, van onder naar boven:
  1. effecten (kleur, intensiteit, beweging) op de beat van de muziek
  2. scène-laag: vaste waarden uit een scène of cuelijst, met overvloeien (fade)
  3. programmer: wat je nu met de hand instelt (wint altijd)
  4. master, groepen, energie en blackout (schalen de helderheid)
  5. looks, losse kanaalwaarden, macro-faders
  6. vasthoudknoppen (STROBE, SMOKE, BLINDER) en de testpagina
"""
import copy
import hashlib
import json
import math
import os
import random
import secrets
import threading
import time
from collections import deque

from .effecten import (ATTRIBUUT_MODI, BEWEGING_MODI, INTENSITEIT_MODI, KLEUR_MODI, attribuut_effect,
                       beweging_effect, bruikbare_opties, clamp, hex_rgb, intensiteit_effect, kleur_effect, rgb_hex)
from .lichtman import SECTIES, Lichtman, profiel
from .profielen import (ATTRIBUUT_FUNCTIES, FUNCTIES, KLEURFUNCTIES, STANDAARD_PROFIELEN, byte, koppen,
                        schoon_profiel)

FPS = 40
HOLD_TIMEOUT = 0.7   # seconden: knop geldt als losgelaten als de telefoon niets meer stuurt
TEST_TIMEOUT = 6.0   # seconden: testmodus stopt vanzelf als de testpagina dicht is
MAX_UNIVERSES = 64
HOLD_SOORTEN = ("smoke", "strobe", "blinder")
UITGANG_SOORTEN = {
    "usb": "USB-DMX-kabel (herkent zelf het type)",
    "opendmx": "USB-DMX: Open DMX / FTDI",
    "enttecpro": "Enttec DMX USB Pro (of compatibel)",
    "artnet": "Art-Net (netwerk)",
    "sacn": "sACN / E1.31 (netwerk)",
}

NOOTNAMEN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
AUTO_KLEUR = ["chase", "regenboog", "fade", "random", "wissel", "melodie", "verloop", "split"]
AUTO_INTENSITEIT = ["aan", "aan", "chase", "pingpong", "golf", "puls", "om_en_om", "linksrechts", "random",
                    "midden_uit", "dubbel_chase", "sparkle"]
AUTO_BEWEGING = ["cirkel", "acht", "linksrechts", "opneer", "zwaai", "vierkant", "spiraal", "ballyhoo"]
AUTO_PALETTEN = [
    ["#ff0000", "#0000ff"], ["#ff6600", "#ffcc00"], ["#ff00ff", "#00ffff"], ["#00ff00", "#0000ff"],
    ["#ff0000", "#ffffff"], ["#ff0000", "#ff8800", "#ffff00"], ["#8800ff", "#ff0088"],
    ["#00ffff", "#ffffff"], ["#ff0000", "#00ff00", "#0000ff"],
]


def fixture(fid, naam, profiel, adres, groep, x, y=50, universe=1, **extra):
    f = {
        "id": fid, "naam": naam, "profiel": profiel, "universe": universe, "adres": adres, "groep": groep,
        "x": x, "y": y, "breedte": 10,
        "strobe": True,
        "effecten": {"kleur": True, "intensiteit": True, "beweging": True},
        "pan_min": 0, "pan_max": 255, "tilt_min": 0, "tilt_max": 255, "pan_omkeren": False, "tilt_omkeren": False,
    }
    f.update(extra)
    return f


GEEN_EFFECTEN = {"kleur": False, "intensiteit": False, "beweging": False}
STANDAARD_FIXTURES = [
    fixture(1, "Par 1", "drgb_4", 1, "Pars", 20, 72),
    fixture(2, "Par 2", "drgb_4", 5, "Pars", 40, 72),
    fixture(3, "Par 3", "drgb_4", 9, "Pars", 60, 72),
    fixture(4, "Par 4", "drgb_4", 13, "Pars", 80, 72),
    fixture(5, "Moving head 1", "mh_11", 17, "Moving heads", 30, 35, tilt_max=160),
    fixture(6, "Moving head 2", "mh_11", 28, "Moving heads", 70, 35, tilt_max=160),
    fixture(7, "LED-bar", "ledbar_8", 39, "LED-bar", 50, 88, breedte=44),
    fixture(8, "Rookmachine", "rook_1", 70, "Rook", 92, 92, strobe=False, effecten=dict(GEEN_EFFECTEN)),
]

STANDAARD_SHOW = {
    "bpm": 128.0,
    "master": 100,
    "blackout": False,
    "strobe_hz": 12,
    "tempo_factor": 1,
    "fade": 1.0,
    "kleur": {"modus": "chase", "palet": ["#ff0000", "#0000ff"], "snelheid": 1, "spreiding": 50},
    "intensiteit": {"modus": "aan", "snelheid": 1},
    "beweging": {"modus": "cirkel", "snelheid": 8, "grootte": 50, "spreiding": 50, "pan": 50, "tilt": 50},
    "looks": {"modus": "wissel", "elke": 16, "keuze": {}},
    "auto": {"aan": False, "elke": 32},
    "beat": {"auto": True, "vertraging_spotify": 200, "vertraging_mpd": 400, "vertraging_audio": 0, "vertraging_connect": 40,
             "bpm_min": 75, "bpm_max": 220, "snel_herkennen": True},
    # de lichtman (show volgt de muziek): contrast 0 = doet bijna niets, 100 = rustig heel rustig en drops heel wild
    "energie": {"aan": True, "flits_bij_drop": True, "opbouw_voor_drop": True, "contrast": 70},
    "groepen": {},
    "lagen": {},           # groep -> {"eigen": bool, "kleur", "intensiteit", "beweging"}: eigen patronen per laag
    "attributen": {},      # functie (patroon, rotatie, …) -> {"modus", "elke", "keuzes"}
}
EFFECT_SLEUTELS = ("kleur", "intensiteit", "beweging", "looks", "attributen", "lagen")
LAAG_SLEUTELS = ("kleur", "intensiteit", "beweging")
OUDE_PROFIELNAMEN = {"Laser 20 kanalen": "laser_20"}   # naam in shows van vóór versie 3
# auto-show per sectie van het nummer (de lichtman kiest dan zelf wat bij het moment past)
AUTO_PER_SECTIE = {
    "rustig": (["fade", "verloop", "regenboog", "wissel"], ["aan", "ademen", "golf"], ["cirkel", "acht", "zwaai", "linksrechts"]),
    "groove": (["wissel", "chase", "fade", "split", "melodie"], ["aan", "golf", "om_en_om", "linksrechts", "chase", "puls"],
               ["cirkel", "acht", "linksrechts", "opneer"]),
    "drop": (["chase", "wissel", "random", "split", "regenboog_stap"],
             ["chase", "pingpong", "dubbel_chase", "om_en_om", "flits", "sparkle", "random", "midden_uit"],
             ["ballyhoo", "vierkant", "spiraal", "acht", "cirkel", "knik"]),
}
AUTO_PER_SECTIE["break"] = AUTO_PER_SECTIE["opbouw"] = AUTO_PER_SECTIE["rustig"]
# Spotify-speaker (desktop-app): aan = None betekent "nog niet gekozen" (de app zet hem bij de eerste start aan)
STANDAARD_SPOTIFY = {"aan": None, "naam": "DMXDesk", "apparaat": None, "voorsprong": 8.0, "zeroconf_poort": 0}


def samenvoegen(doel, bron):
    """Voegt bron recursief in doel, alleen voor sleutels die in doel bestaan (plus vrije dicts)."""
    for k, v in bron.items():
        if k == "attributen" and isinstance(v, dict):
            a = doel.setdefault(k, {})
            for fn, cfg in v.items():
                if fn in ATTRIBUUT_FUNCTIES and isinstance(cfg, dict):
                    a.setdefault(fn, {}).update({x: y for x, y in cfg.items() if x in ("modus", "elke", "keuzes")})
        elif k in ("keuze", "groepen") and isinstance(v, dict):
            doel.setdefault(k, {}).update(v)
        elif k == "lagen" and isinstance(v, dict):
            lagen = doel.setdefault(k, {})
            for naam, cfg in v.items():
                naam = str(naam)[:60]
                if cfg is None:
                    lagen.pop(naam, None)             # laag weer laten volgen wat voor alle lampen geldt
                elif isinstance(cfg, dict):
                    if naam not in lagen:             # nieuwe laag: begint met de huidige instellingen
                        lagen[naam] = {"eigen": False, **{s: copy.deepcopy(doel.get(s) or STANDAARD_SHOW[s])
                                                          for s in LAAG_SLEUTELS}}
                    samenvoegen(lagen[naam], cfg)
        elif isinstance(doel.get(k), dict) and isinstance(v, dict):
            samenvoegen(doel[k], v)
        elif k in doel:
            doel[k] = v


def _getal(v, standaard, laag, hoog, soort=float):
    try:
        return soort(clamp(soort(v), laag, hoog))
    except (TypeError, ValueError):
        return standaard


def schone_spotify(cfg):
    cfg = cfg if isinstance(cfg, dict) else {}
    naam = " ".join(str(cfg.get("naam") or "").split())[:40] or "DMXDesk"
    return {"aan": None if cfg.get("aan") is None else bool(cfg.get("aan")),
            "naam": naam,
            "apparaat": str(cfg["apparaat"])[:200] if cfg.get("apparaat") else None,
            "voorsprong": round(_getal(cfg.get("voorsprong"), 8.0, 0.0, 20.0), 1),
            "zeroconf_poort": _getal(cfg.get("zeroconf_poort"), 0, 0, 65535, int)}


def pin_hash(pin, zout):
    return hashlib.sha256((zout + ":" + str(pin)).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- toestand van een lamp tijdens het rekenen

class _Stand:
    """Logische toestand van één lamp: helderheid en kleur per cel, pan/tilt voor de hele lamp."""
    __slots__ = ("E", "RGB", "pan", "tilt")

    def __init__(self, E, RGB, pan, tilt):
        self.E, self.RGB, self.pan, self.tilt = E, RGB, pan, tilt

    def kopie(self):
        return _Stand(dict(self.E), dict(self.RGB), self.pan, self.tilt)

    def toepassen(self, w):
        """Waarden uit een scène of de programmer: dim/pan/tilt 0-100, kleur '#rrggbb'."""
        if not w:
            return self
        if "dim" in w:
            e = clamp(float(w["dim"]), 0, 100) / 100.0
            for k in self.E:
                self.E[k] = e
        if "kleur" in w:
            rgb = hex_rgb(w["kleur"])
            for k in self.RGB:
                self.RGB[k] = rgb
        if "pan" in w:
            self.pan = clamp(float(w["pan"]), 0, 100) / 100.0
        if "tilt" in w:
            self.tilt = clamp(float(w["tilt"]), 0, 100) / 100.0
        return self

    @staticmethod
    def meng(a, b, f):
        lerp = lambda p, q: p + (q - p) * f   # noqa: E731
        return _Stand({k: lerp(a.E[k], b.E[k]) for k in a.E},
                      {k: tuple(lerp(a.RGB[k][c], b.RGB[k][c]) for c in range(3)) for k in a.RGB},
                      lerp(a.pan, b.pan), lerp(a.tilt, b.tilt))


# ---------------------------------------------------------------- engine

class Engine:
    def __init__(self, show_bestand=None):
        self.show_bestand = show_bestand
        self.lock = threading.RLock()
        self.data = self.laden()
        self.bpm_t0 = time.time()
        self.taps = []
        self.hold = {s: 0.0 for s in HOLD_SOORTEN}
        self.hold_vast = set()           # vastgehouden via MIDI of toetsenbord (zonder herhalen)
        self.test = None
        self.zoek = None
        self.status = {"fps": 0}
        self.uitgang_status = {}         # id -> {"ok", "tekst"}, ingevuld door uitvoer.py
        self.frames = {1: bytearray(512)}
        self.voorbeeld = []
        self.auto_stap_nr = None
        self.moet_opslaan = False
        self.wijziging = 1               # telt op bij elke wijziging, zodat alle schermen bijwerken
        self.patch_versie = 1            # telt op als lampen of profielen veranderen (dan alles opnieuw ophalen)
        self._cache = None
        self.luister = {}                # per bron: wat de beat-luisteraar hoort
        self.bpm_kandidaat, self.bpm_teller = 0.0, 0
        self.noten = deque(maxlen=64)    # (tijd waarop hoorbaar, toon 0-11) van de melodie
        self.melodie_nu, self.sinds_noot = [], None
        self.energie, self.energie_gezien = 0.5, 0.0
        self.energie_attr = None
        self.energie_rij = deque(maxlen=400)   # (hoorbaar op, energie, bron): met voorsprong komen ze vooruit binnen
        self.lichtman = Lichtman()
        self.lm = None                   # wat de lichtman nu zegt (sectie, opbouw, flits, …)
        self.lm_glad = {"dim": 1.0, "bew_snel": 1.0, "bew_groot": 1.0}   # soepel naar het doel toe
        self.lm_t = None
        self.opbouw, self.gat, self.punch, self.adem = None, False, 0.0, 0.0
        self.vorige_beat, self.bew_fasen = None, {}
        self.eff, self.drop_nu = None, False
        self.muziek_beat = 0.0
        self.pauze_sinds = None          # Spotify-speaker op pauze: sinds wanneer
        self.bevroren = False
        self._eff_f, self._eff_offset, self._eff_laatste = None, 0.0, None
        self.scene_actief, self.scene_vorig = None, {}
        self.programmer = {}             # str(fixture-id) -> {"dim", "kleur", "pan", "tilt", "kanalen"}
        self.cue = None                  # {"lijst", "stap", "start", "pauze"}
        self.bij_uitgangen = []          # functies die aangeroepen worden als de uitgangen wijzigen
        self.extra_status = {}           # audio, midi: door andere onderdelen bijgehouden

    # ------------------------------------------------------------ opslag
    def standaard(self):
        return {
            "versie": 4,
            "naam": "Mijn show",
            "show": copy.deepcopy(STANDAARD_SHOW),
            "fixtures": copy.deepcopy(STANDAARD_FIXTURES),
            "profielen": copy.deepcopy(STANDAARD_PROFIELEN),
            "scenes": {},
            "cuelijsten": {},
            "faders": [{"id": 1, "naam": "Rook (continu)", "functie": "smoke", "fixtures": [], "waarde": 0}],
            "uitgangen": [{"id": 1, "naam": "USB-DMX", "soort": "usb", "universe": 1, "poort": "auto", "aan": True}],
            "audio": {"aan": False, "apparaat": None},
            "spotify": copy.deepcopy(STANDAARD_SPOTIFY),
            "midi": {"apparaat": "", "koppelingen": {}},
            "instellingen": {"pin_hash": "", "pin_zout": secrets.token_hex(8)},
        }

    def normaliseer(self, geladen, basis=None):
        """Maakt van een ingelezen show (oud of nieuw formaat) een volledige, geldige show."""
        data = basis if basis is not None else self.standaard()
        if int(geladen.get("versie", 1)) < 2:
            geladen = self.migreer_v1(geladen)
        for k in ("naam", "fixtures", "profielen", "scenes", "cuelijsten", "faders", "uitgangen", "audio", "spotify",
                  "midi", "instellingen"):
            if k in geladen:
                data[k] = copy.deepcopy(geladen[k])
        samenvoegen(data["show"], geladen.get("show", {}))
        data["profielen"] = {str(pid)[:60]: schoon_profiel(p) for pid, p in data["profielen"].items()}
        data["fixtures"] = self.schone_fixtures(data["fixtures"], data["profielen"], streng=False)
        data["scenes"] = self.schone_scenes(data["scenes"])
        data["cuelijsten"] = self.schone_cuelijsten(data["cuelijsten"])
        data["faders"] = self.schone_faders(data["faders"])
        data["uitgangen"] = self.schone_uitgangen(data["uitgangen"])
        data["spotify"] = schone_spotify(data["spotify"])
        if int(geladen.get("versie", 1)) < 3:
            self.profielen_bijwerken(data["profielen"])
        if int(geladen.get("versie", 1)) < 4:
            data["show"]["energie"]["aan"] = True           # de lichtman staat voortaan standaard aan
            if data["spotify"].get("voorsprong") == 4.0:   # oude standaard: nu 8 s (meer tijd om vooruit te horen)
                data["spotify"]["voorsprong"] = 8.0
        data["instellingen"].setdefault("pin_hash", "")
        data["instellingen"].setdefault("pin_zout", secrets.token_hex(8))
        data["midi"].setdefault("koppelingen", {})
        data["versie"] = 4
        self.groepen_bijwerken(data)
        return data

    @staticmethod
    def profielen_bijwerken(profielen):
        """Eenmalig (show van vóór versie 3): ingebouwde profielen krijgen hun echte kanaalfuncties, de keuzes uit de
        handleiding en nieuwe looks. Alleen als de kanalen nog overeenkomen; eigen aanpassingen blijven staan."""
        op_naam = {p["naam"]: pid for pid, p in STANDAARD_PROFIELEN.items()}
        op_naam.update(OUDE_PROFIELNAMEN)
        for pid, p in profielen.items():
            std = STANDAARD_PROFIELEN.get(pid) or STANDAARD_PROFIELEN.get(op_naam.get(p.get("naam"), ""))
            if not std or len(std["kanalen"]) != len(p["kanalen"]):
                continue
            paren = list(zip(p["kanalen"], std["kanalen"]))
            if any(k["functie"] not in (sk["functie"], "fixed") for k, sk in paren):
                continue       # zelf andere functies gekozen: niet aankomen
            for k, sk in paren:
                if k["functie"] == "fixed" and sk["functie"] != "fixed":
                    k["functie"] = sk["functie"]
                if not k.get("opties") and sk.get("opties"):
                    k["opties"] = copy.deepcopy(sk["opties"])
            namen = {lk["naam"] for lk in p.get("looks", [])}
            p["looks"] = p.get("looks", []) + [copy.deepcopy(lk) for lk in std.get("looks", []) if lk["naam"] not in namen]

    @staticmethod
    def migreer_v1(oud):
        """show.json van DMXDesk 1 (alleen de Pi, één USB-dongle) omzetten."""
        nieuw = dict(oud)
        poort = oud.get("dmx_poort", "auto") or "auto"
        nieuw["uitgangen"] = [{"id": 1, "naam": "USB-DMX", "soort": "usb", "universe": 1, "poort": poort, "aan": True}]
        nieuw["scenes"] = {naam: {"effecten": {k: v for k, v in sc.items() if k in EFFECT_SLEUTELS}, "vast": {},
                                  "fade": 0, "kleur": ""}
                           for naam, sc in (oud.get("scenes") or {}).items()}
        nieuw["versie"] = 2
        return nieuw

    def laden(self):
        data = self.standaard()
        if self.show_bestand and os.path.exists(self.show_bestand):
            try:
                with open(self.show_bestand, encoding="utf-8") as f:
                    data = self.normaliseer(json.load(f))
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
                # niet zomaar overschrijven: eerst een reservekopie van het kapotte bestand maken
                reserve = self.show_bestand + time.strftime(".kapot-%Y%m%d-%H%M%S")
                try:
                    os.replace(self.show_bestand, reserve)
                except OSError:
                    reserve = "(kon geen reservekopie maken)"
                print("show.json kon niet gelezen worden, standaard wordt gebruikt:", e, "- reservekopie:", reserve,
                      flush=True)
                data = self.normaliseer({"versie": 2})
        else:
            self.groepen_bijwerken(data)
        return data

    @staticmethod
    def groepen_bijwerken(data):
        groepen = data["show"].setdefault("groepen", {})
        for f in data["fixtures"]:
            groepen.setdefault(f.get("groep") or "Overig", 100)
        for g in list(groepen):
            if not any((f.get("groep") or "Overig") == g for f in data["fixtures"]):
                del groepen[g]

    def opslaan(self):
        if not self.show_bestand:
            return
        with self.lock:
            tekst = json.dumps(self.data, indent=2, ensure_ascii=False)
            self.moet_opslaan = False
        tmp = self.show_bestand + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(tekst)
        os.replace(tmp, self.show_bestand)

    def gewijzigd(self, opslaan=True, patch=False):
        """Na elke wijziging: opslaan (even later), schermen laten bijwerken, en zo nodig de patch opnieuw opbouwen."""
        self.wijziging += 1
        if opslaan:
            self.moet_opslaan = True
        if patch:
            self._cache = None
            self.patch_versie += 1

    def export(self):
        with self.lock:
            return {k: copy.deepcopy(self.data[k]) for k in
                    ("versie", "naam", "show", "fixtures", "profielen", "scenes", "cuelijsten", "faders", "uitgangen")}

    def importeer(self, geladen, uitgangen_ook=False):
        if not isinstance(geladen, dict) or not ("fixtures" in geladen or "show" in geladen):
            raise ValueError("Dit is geen DMXDesk-show")
        with self.lock:
            bewaar = {k: copy.deepcopy(self.data[k]) for k in ("audio", "spotify", "midi", "instellingen", "uitgangen")}
            nieuw = self.normaliseer(geladen)
            for k, v in bewaar.items():
                if k != "uitgangen" or not uitgangen_ook:
                    nieuw[k] = v
            self.data = nieuw
            self.programmer, self.cue, self.scene_actief, self.scene_vorig = {}, None, None, {}
            self.gewijzigd(patch=True)
        self.uitgangen_gewijzigd()

    # ------------------------------------------------------------ controleren
    @staticmethod
    def schone_fixtures(lijst, profielen, streng=True):
        schoon, ids = [], set()
        volgend_id = max([_getal(f.get("id"), 0, 0, 10 ** 6, int) for f in lijst] + [0]) + 1
        for f in lijst:
            if f.get("profiel") not in profielen:
                if not streng:          # bij het inlezen: deze fixture overslaan, de rest van de show niet kwijtraken
                    print(f"Fixture '{f.get('naam')}' overgeslagen: onbekend profiel", flush=True)
                    continue
                raise ValueError(f"Fixture '{f.get('naam')}' heeft een onbekend profiel")
            b = fixture(0, "", "", 1, "", 50)
            b.update({k: f[k] for k in b if k in f})
            fid = _getal(f.get("id"), 0, 0, 10 ** 6, int)
            if not fid or fid in ids:
                fid, volgend_id = volgend_id, volgend_id + 1
            ids.add(fid)
            b["id"] = fid
            b["naam"] = str(b["naam"])[:40] or f"Fixture {fid}"
            b["universe"] = _getal(b["universe"], 1, 1, MAX_UNIVERSES, int)
            b["adres"] = _getal(b["adres"], 1, 1, 512, int)
            b["groep"] = str(b["groep"]).strip()[:30] or "Overig"
            b["x"] = round(_getal(b["x"], 50, 0, 100), 1)
            b["y"] = round(_getal(b["y"], 50, 0, 100), 1)
            b["breedte"] = _getal(b["breedte"], 10, 1, 100)
            for k in ("pan_min", "pan_max", "tilt_min", "tilt_max"):
                b[k] = _getal(b[k], 0 if k.endswith("min") else 255, 0, 255, int)
            b["effecten"] = {s: bool((b.get("effecten") or {}).get(s, True)) for s in ("kleur", "intensiteit", "beweging")}
            for k in ("strobe", "pan_omkeren", "tilt_omkeren"):
                b[k] = bool(b[k])
            schoon.append(b)
        return schoon

    @staticmethod
    def schone_waarden(w):
        """Waarden van de programmer of een vaste scène."""
        uit = {}
        if not isinstance(w, dict):
            return uit
        for k in ("dim", "pan", "tilt"):
            if w.get(k) is not None:
                uit[k] = _getal(w[k], 0, 0, 100)
        if w.get("kleur"):
            uit["kleur"] = rgb_hex(hex_rgb(str(w["kleur"])))
        kanalen = {}
        for c, v in (w.get("kanalen") or {}).items():
            try:
                if 1 <= int(c) <= 512 and v is not None:
                    kanalen[str(int(c))] = byte(v)
            except (TypeError, ValueError):
                continue
        if kanalen:
            uit["kanalen"] = kanalen
        return uit

    def schone_scenes(self, scenes):
        schoon = {}
        for naam, sc in (scenes or {}).items():
            naam = str(naam).strip()[:40]
            if not naam or not isinstance(sc, dict):
                continue
            eff = sc.get("effecten")
            if isinstance(eff, dict):
                eff = {k: copy.deepcopy(eff[k]) for k in EFFECT_SLEUTELS if isinstance(eff.get(k), dict)} or None
            else:
                eff = None
            vast = {}
            for fid, w in (sc.get("vast") or {}).items():
                w = self.schone_waarden(w)
                if w:
                    vast[str(fid)] = w
            schoon[naam] = {"effecten": eff, "vast": vast, "fade": _getal(sc.get("fade"), 0, 0, 60),
                            "kleur": str(sc.get("kleur") or "")[:7]}
        return schoon

    @staticmethod
    def schone_cuelijsten(lijsten):
        schoon = {}
        for naam, cl in (lijsten or {}).items():
            naam = str(naam).strip()[:40]
            if not naam or not isinstance(cl, dict):
                continue
            stappen = [{"scene": str(s.get("scene", ""))[:40], "duur": _getal(s.get("duur"), 4, 0.25, 3600),
                        "fade": _getal(s.get("fade"), 0, 0, 60)}
                       for s in (cl.get("stappen") or [])[:200] if isinstance(s, dict)]
            schoon[naam] = {"stappen": stappen, "eenheid": "seconden" if cl.get("eenheid") == "seconden" else "beats",
                            "herhalen": bool(cl.get("herhalen", True))}
        return schoon

    @staticmethod
    def schone_faders(faders):
        schoon, ids = [], set()
        for n, f in enumerate((faders or [])[:32]):
            if not isinstance(f, dict):
                continue
            fid = _getal(f.get("id"), n + 1, 1, 10 ** 6, int)
            while fid in ids:
                fid += 1
            ids.add(fid)
            functie = f.get("functie") if f.get("functie") in FUNCTIES and f.get("functie") not in (
                "pan", "pan_fine", "tilt", "tilt_fine") else "dimmer"
            schoon.append({"id": fid, "naam": str(f.get("naam") or "Fader")[:30], "functie": functie,
                           "fixtures": [_getal(x, 0, 0, 10 ** 6, int) for x in (f.get("fixtures") or [])][:256],
                           "waarde": _getal(f.get("waarde"), 0, 0, 100)})
        return schoon

    @staticmethod
    def schone_uitgangen(uitgangen):
        schoon, ids = [], set()
        for n, u in enumerate((uitgangen or [])[:16]):
            if not isinstance(u, dict) or u.get("soort") not in UITGANG_SOORTEN:
                continue
            uid = _getal(u.get("id"), n + 1, 1, 10 ** 6, int)
            while uid in ids:
                uid += 1
            ids.add(uid)
            schoon.append({
                "id": uid, "naam": str(u.get("naam") or UITGANG_SOORTEN[u["soort"]])[:40], "soort": u["soort"],
                "universe": _getal(u.get("universe"), 1, 1, MAX_UNIVERSES, int),
                "poort": str(u.get("poort") or "auto")[:200],
                "ip": str(u.get("ip") or "")[:100],
                "net_universe": _getal(u.get("net_universe"), 0, 0, 63999, int),
                "aan": bool(u.get("aan", True)),
            })
        return schoon

    # ------------------------------------------------------------ beat
    def beat(self, nu):
        return (nu - self.bpm_t0) * float(self.data["show"]["bpm"]) / 60.0

    def zet_bpm(self, bpm, nu=None):
        nu = nu or time.time()
        bpm = clamp(float(bpm), 40.0, 240.0)
        beat = self.beat(nu)
        self.data["show"]["bpm"] = round(bpm, 1)
        self.bpm_t0 = nu - beat * 60.0 / bpm

    def tap(self):
        nu = time.time()
        with self.lock:
            if self.taps and nu - self.taps[-1] > 2.0:
                self.taps = []
            self.taps = (self.taps + [nu])[-6:]
            if len(self.taps) >= 2:
                gem = (self.taps[-1] - self.taps[0]) / (len(self.taps) - 1)
                self.data["show"]["bpm"] = round(clamp(60.0 / gem, 40.0, 240.0), 1)
            self.bpm_t0 = nu
            self.data["show"]["beat"]["auto"] = False   # wie tapt, wil zelf de maat bepalen
            self.gewijzigd()

    def effect_beat(self, beat):
        """Beat voor de effecten: met tempo-factor (½×, 2×) en bevriezen, zonder sprongen bij het omschakelen."""
        f = 0.0 if self.bevroren else float(self.data["show"].get("tempo_factor", 1) or 1)
        if self._eff_laatste is None:
            self._eff_f, self._eff_offset = f, beat - beat * f
        elif f != self._eff_f:
            self._eff_offset = self._eff_laatste - beat * f
            self._eff_f = f
        eb = beat * f + self._eff_offset
        self._eff_laatste = eb
        return eb

    def beat_bericht(self, m):
        """Verwerkt een bericht van de beat-luisteraar: BPM bijsturen en de maat gelijk trekken."""
        nu = time.time()
        with self.lock:
            bron = str(m.get("bron", "?"))[:20]
            info = self.luister.setdefault(bron, {"laatste_beat": 0.0})
            cfg = self.data["show"]["beat"]
            vertraging = float(cfg.get("vertraging_" + bron, 0 if bron == "audio" else 200)) / 1000.0
            soort = m.get("soort")
            if soort == "energie":
                # pas laten gelden als je het hoort (met voorsprong komt het bericht seconden eerder binnen)
                t = float(m.get("t", nu)) + vertraging
                self.energie_rij.append((t, float(m.get("e", 0.5)), bron))
                if m.get("kick") is not None:
                    self.lichtman.punt(float(m.get("kt", m.get("t", nu))) + vertraging, float(m["kick"]),
                                       float(m.get("e", 0.5)))
                else:          # oude beat-luisteraar zonder kick-meting: alleen de energie
                    self.lichtman.punt(t, 0.8 * float(m.get("e", 0.5)), float(m.get("e", 0.5)))
                return
            if soort == "drop":
                # na een stuk zonder kick komt hij terug: de lichtman bouwt ernaartoe op en flitst precies op de drop
                t = float(m.get("t", nu)) + vertraging
                self.lichtman.drop(t)
                info["laatste_drop"] = t
                return
            if soort == "noot":
                # melodie: onthouden wanneer deze noot te HOREN is (met de vertraging van de geluidsweg)
                klasse = int(m.get("klasse", 0)) % 12
                self.noten.append((float(m.get("t", nu)) + vertraging, klasse))
                info.update(noot=NOOTNAMEN[klasse], laatste_noot=nu)
                return
            info.update(bpm=round(float(m.get("bpm") or 0), 1), zekerheid=round(float(m.get("conf") or 0), 2), gezien=nu)
            if "niveau" in m:
                info["niveau"] = float(m["niveau"])
            if soort != "beat":
                return
            info["laatste_beat"] = nu
            bpm = float(m.get("bpm") or 0)
            if not cfg.get("auto") or bpm <= 0:
                return
            if self.data["show"]["energie"].get("aan") and \
                    self.lichtman.tempo_vasthouden(float(m.get("t", nu)) + vertraging):
                return          # break/opbouw: maat vasthouden tot de kick terug is
            laag, hoog = float(cfg.get("bpm_min", 75)), float(cfg.get("bpm_max", 220))
            # snel nummer? de beat-herkenning hoort dan vaak de helft; zit er een kick tússen de beats, dan verdubbelen
            ratio = m.get("kick_ratio")
            if ratio is not None:
                if ratio > 0.65:
                    info["dubbel"] = True
                elif ratio < 0.45:
                    info["dubbel"] = False
            if cfg.get("snel_herkennen", True) and info.get("dubbel") and bpm * 2 <= hoog:
                bpm *= 2
            while bpm < laag:
                bpm *= 2
            while bpm > hoog and bpm / 2 >= laag * 0.9:
                bpm /= 2
            # BPM pas aanpassen als de luisteraar een paar keer hetzelfde hoort
            if abs(bpm - self.bpm_kandidaat) < 2.5:
                self.bpm_teller += 1
                self.bpm_kandidaat = 0.7 * self.bpm_kandidaat + 0.3 * bpm
            else:
                self.bpm_kandidaat, self.bpm_teller = bpm, 1
            huidig = float(self.data["show"]["bpm"])
            if self.bpm_teller >= 3 and abs(self.bpm_kandidaat - huidig) >= 0.3:
                stap = 0.3 if abs(self.bpm_kandidaat - huidig) < 4 else 1.0
                self.zet_bpm(huidig + (self.bpm_kandidaat - huidig) * stap, nu)
            # fase: de beat valt als je hem hoort, dus met de vertraging van de geluidsweg erbij
            b = self.beat(float(m.get("t", nu)) + vertraging)
            fout = b - round(b)
            if abs(fout) < 0.35:
                self.bpm_t0 += fout * 60.0 / float(self.data["show"]["bpm"]) * 0.35

    # ------------------------------------------------------------ speler: pauze, verder, ander nummer
    def muziek_pauze(self, t):
        """De muziek staat stil (vanaf t). Het licht wordt rustig tot hij verder gaat."""
        with self.lock:
            self.pauze_sinds = t

    def muziek_hervat(self):
        """Verder na een pauze: alles wat gepland stond (beats, energie, noten, drops) schuift mee."""
        with self.lock:
            if self.pauze_sinds is None:
                return
            van, duur = self.pauze_sinds, max(0.0, time.time() - self.pauze_sinds)
            self.pauze_sinds = None
            self.bpm_t0 += duur
            self.energie_rij = deque((((t + duur) if t >= van else t, e, b) for t, e, b in self.energie_rij), maxlen=400)
            self.noten = deque((((t + duur) if t >= van else t, k) for t, k in self.noten), maxlen=64)
            self.lichtman.verschuif(van, duur)

    def muziek_vergeet(self, t):
        """Ander nummer gekozen of gespoeld: wat nog gepland stond (van het oude stuk) geldt niet meer."""
        with self.lock:
            self.pauze_sinds = None
            self.energie_rij = deque(((tt, e, b) for tt, e, b in self.energie_rij if tt < t), maxlen=400)
            self.noten = deque(((tt, k) for tt, k in self.noten if tt < t), maxlen=64)
            self.lichtman.vergeet_vanaf(t)

    # ------------------------------------------------------------ automatische show en energie
    def auto_stap(self, beat):
        auto = self.data["show"]["auto"]
        if not auto.get("aan"):
            self.auto_stap_nr, self.auto_sectie = None, None
            return
        nr = int(beat // max(4, int(auto.get("elke", 32))))
        sectie = self.lm["sectie"] if self.lm else None
        # nieuwe look op de maat, én meteen als het nummer omslaat (drop!, of het wordt rustig)
        grof = {"opbouw": "rustig", "break": "rustig"}.get(sectie, sectie)
        omslag = grof != getattr(self, "auto_sectie", None) and sectie != "opbouw"
        if nr == self.auto_stap_nr and not omslag:
            return
        self.auto_stap_nr, self.auto_sectie = nr, grof
        show = self.data["show"]
        kleuren, intens, bewegingen = AUTO_PER_SECTIE.get(sectie) or (AUTO_KLEUR, AUTO_INTENSITEIT, AUTO_BEWEGING)
        palet = random.choice(AUTO_PALETTEN)
        doelen = [show] + [lg for lg in (show.get("lagen") or {}).values() if lg.get("eigen")]
        for cfg in doelen:
            cfg["kleur"].update(modus=random.choice(kleuren), palet=palet if cfg is show else random.choice(AUTO_PALETTEN),
                                snelheid=random.choice([0.5, 1, 2]))
            cfg["intensiteit"].update(modus=random.choice(intens), snelheid=random.choice([0.5, 1, 1, 2]))
            cfg["beweging"].update(modus=random.choice(bewegingen), snelheid=random.choice([4, 8, 8, 16]))
        self.wijziging += 1

    def energie_nu(self, nu):
        if not self.data["show"]["energie"].get("aan") or nu - self.energie_gezien > 5.0:
            return None
        return self.energie

    def eigen_lagen(self):
        return sorted(n for n, lg in (self.data["show"].get("lagen") or {}).items() if lg.get("eigen"))

    def lichtman_toepassen(self, show, beat, nu):
        """De lichtman bepaalt per moment hoe snel, fel en wild de show is; per laag met de eigen patronen."""
        cfg_e = show["energie"]
        contrast = float(cfg_e.get("contrast", 70)) / 100.0
        st = self.lichtman.stand(nu, contrast) if cfg_e.get("aan") else None
        if cfg_e.get("aan") and self.pauze_sinds is not None and nu >= self.pauze_sinds:
            # muziek op pauze: rustig en gedimd tot hij verder gaat
            st = {"sectie": "pauze", "kick": 0.0, "e": 0.0, "niveau": 0.0, "opbouw": None, "drop_t": None,
                  "extreem": False, "flits": False, "gat": False, "profiel": dict(profiel("rustig", None, contrast))}
            st["profiel"]["dim"] *= 0.6
        self.lm = st
        dt = 0.0 if self.lm_t is None else clamp(nu - self.lm_t, 0.0, 0.5)
        self.lm_t = nu
        prof = st["profiel"] if st else None
        for k in self.lm_glad:
            doel = prof[k] if prof else 1.0
            snel = 1.0 if (st and (st["flits"] or st["sectie"] == "opbouw")) else min(1.0, dt / 0.8)
            self.lm_glad[k] += (doel - self.lm_glad[k]) * snel

        def traag(s, keer):
            v = s * keer
            return v if v <= 16 else max(s, 16.0)

        def effecten(cfg):
            kl, it, bw = cfg["kleur"], cfg["intensiteit"], cfg["beweging"]
            if not prof:
                return {"kleur": kl, "intensiteit": it, "beweging": bw, "dim": 1.0}
            g = self.lm_glad
            return {
                "kleur": dict(kl, snelheid=traag(float(kl.get("snelheid", 1)), prof["kleur_stap"]), zacht=prof["zacht"]),
                "intensiteit": dict(it, snelheid=traag(float(it.get("snelheid", 1)), prof["stap"]), zacht=prof["zacht"]),
                "beweging": dict(bw, snelheid=max(1.0, float(bw.get("snelheid", 8)) * g["bew_snel"]),
                                 grootte=float(bw.get("grootte", 50)) * g["bew_groot"]),
                "dim": g["dim"],
            }

        lagen = show.get("lagen") or {}
        self.eff = {None: effecten(show)}
        for naam in self.eigen_lagen():
            self.eff[naam] = effecten(lagen[naam])
        # beweging: fase optellen (per laag), dan geeft een snelheidswissel geen sprong in de positie
        d = beat - self.vorige_beat if self.vorige_beat is not None else 0.0
        for naam, eff in self.eff.items():
            fase = self.bew_fasen.get(naam, 0.0)
            if -1 < d < 1:
                fase += d / max(0.25, float(eff["beweging"].get("snelheid", 8)))
            self.bew_fasen[naam] = fase
        self.vorige_beat = beat
        self.drop_nu = bool(st and st["flits"] and cfg_e.get("flits_bij_drop", True))
        opbouw_aan = bool(st and cfg_e.get("opbouw_voor_drop", True))
        self.opbouw = st["opbouw"] if opbouw_aan and st["sectie"] == "opbouw" else None
        self.gat = bool(opbouw_aan and st["gat"])
        self.punch = prof["punch"] if prof else 0.0
        self.adem = prof["adem"] if prof else 0.0

    # ------------------------------------------------------------ patch-overzicht (alleen opnieuw bij wijzigingen)
    def cache(self):
        if self._cache is not None and self._cache["lagen"] == tuple(self.eigen_lagen()):
            return self._cache
        profielen = self.data["profielen"]
        fixtures = [f for f in self.data["fixtures"] if f.get("profiel") in profielen]
        volgorde = sorted(fixtures, key=lambda f: (f.get("x", 50), f.get("id", 0)))
        info, cellen = {}, []
        for fx in volgorde:
            prof = profielen[fx["profiel"]]
            kanalen = prof.get("kanalen", [])
            kps = koppen(prof)
            functies = [k.get("functie", "fixed") for k in kanalen]
            kop_van = [int(k.get("kop") or 0) for k in kanalen]
            dimmer_koppen = {kop_van[i] for i, fn in enumerate(functies) if fn == "dimmer"}
            wit_koppen = {kop_van[i] for i, fn in enumerate(functies) if fn == "white"}
            celnrs = kps or [0]
            for j, kop in enumerate(celnrs):
                x = float(fx.get("x", 50))
                if kps:
                    x += ((j + 0.5) / len(kps) - 0.5) * float(fx.get("breedte", 10))
                cellen.append((x, fx["id"], kop, fx))
            info[fx["id"]] = {
                "prof": prof, "kanalen": kanalen, "functies": functies, "kop_van": kop_van, "koppen": kps,
                "cellen": celnrs, "d0": 0 in dimmer_koppen, "dimmer_koppen": dimmer_koppen, "wit_koppen": wit_koppen,
                "heeft_dimmer": bool(dimmer_koppen), "dimmer_fijn": "dimmer_fine" in functies,
                "heeft_kleur": any(fn in KLEURFUNCTIES for fn in functies),
                "rook": "smoke" in functies,
            }
        cellen.sort(key=lambda c: (c[0], c[1], c[2]))
        # lagen met eigen patronen: een chase loopt dan binnen de laag (en niet over alle lampen)
        eigen = set(self.eigen_lagen())
        laag_van = {f["id"]: ((f.get("groep") or "Overig") if (f.get("groep") or "Overig") in eigen else None)
                    for f in volgorde}
        index = {"laag": laag_van}
        for soort in ("kleur", "intensiteit"):
            index[soort] = {}
            for laag in {None} | eigen:
                lijst = [c for c in cellen if c[3].get("effecten", {}).get(soort, True) and laag_van[c[1]] == laag]
                index[soort].update({(c[1], c[2]): (i, len(lijst), c[0]) for i, c in enumerate(lijst)})
        index["beweging"] = {}
        for laag in {None} | eigen:
            lijst = [f for f in volgorde if f.get("effecten", {}).get("beweging", True) and laag_van[f["id"]] == laag]
            index["beweging"].update({f["id"]: (i, len(lijst)) for i, f in enumerate(lijst)})
        universes = sorted({int(f.get("universe", 1)) for f in fixtures} |
                           {int(u["universe"]) for u in self.data["uitgangen"]} | {1})
        self._cache = {"volgorde": volgorde, "info": info, "index": index, "universes": universes,
                       "lagen": tuple(sorted(eigen))}
        return self._cache

    # ------------------------------------------------------------ scènes, cuelijsten, programmer
    def scene_menging(self, nu):
        """(vorige vaste waarden, nieuwe vaste waarden, voortgang 0..1) van de scène-laag."""
        sa = self.scene_actief
        if not sa:
            return None
        f = 1.0 if sa["fade"] <= 0 else clamp((nu - sa["t0"]) / sa["fade"], 0.0, 1.0)
        if f >= 1.0:
            self.scene_vorig = {}
            if not sa["vast"] and sa["naam"] is None:
                self.scene_actief = None
                return None
        return self.scene_vorig, sa["vast"], f

    def _start_scene_laag(self, naam, vast, fade):
        nu = time.time()
        if self.scene_actief:
            menging = self.scene_menging(nu)
            self.scene_vorig = self.scene_actief["vast"] if menging is None or menging[2] >= 0.5 else menging[0]
        else:
            self.scene_vorig = {}
        self.scene_actief = {"naam": naam, "vast": copy.deepcopy(vast), "t0": nu, "fade": max(0.0, float(fade))}

    def laad_scene(self, naam, fade=None, vanuit_cue=False):
        with self.lock:
            sc = self.data["scenes"].get(naam)
            if sc is None:
                raise ValueError(f"Scène '{naam}' bestaat niet")
            show = self.data["show"]
            if sc.get("effecten"):
                for k, v in sc["effecten"].items():
                    show[k] = copy.deepcopy(v)
                show["auto"]["aan"] = False
            if fade is None:
                fade = sc.get("fade", show.get("fade", 1.0))
            self._start_scene_laag(naam, sc.get("vast") or {}, fade)
            if not vanuit_cue:
                self.cue = None
            self.gewijzigd(opslaan=not vanuit_cue)   # een lopende cuelijst hoeft niet steeds naar de SD-kaart

    def scene_loslaten(self, fade=None):
        with self.lock:
            if self.scene_actief:
                self._start_scene_laag(None, {}, self.data["show"].get("fade", 1.0) if fade is None else fade)
            self.cue = None
            self.gewijzigd(opslaan=False)

    def scene_opslaan(self, naam, inhoud="beide", fixtures=None, fade=None, kleur=""):
        naam = str(naam).strip()[:40]
        if not naam:
            raise ValueError("Geef de scène een naam")
        with self.lock:
            show = self.data["show"]
            vast = {}
            if inhoud in ("vast", "beide"):
                vast = {fid: copy.deepcopy(w) for fid, w in self.programmer.items()
                        if w and (not fixtures or int(fid) in [int(x) for x in fixtures])}
                if inhoud == "vast" and not vast:
                    raise ValueError("De programmer is leeg: stel eerst lampen in")
            effecten = {k: copy.deepcopy(show[k]) for k in EFFECT_SLEUTELS} if inhoud in ("effecten", "beide") else None
            oud = self.data["scenes"].get(naam, {})
            self.data["scenes"][naam] = {"effecten": effecten, "vast": vast,
                                         "fade": _getal(fade if fade is not None else oud.get("fade", show.get("fade", 1)), 1, 0, 60),
                                         "kleur": str(kleur or oud.get("kleur") or "")[:7]}
            self.gewijzigd()

    def scene_verwijderen(self, naam):
        with self.lock:
            self.data["scenes"].pop(naam, None)
            self.gewijzigd()

    def zet_scenes(self, scenes):
        with self.lock:
            self.data["scenes"] = self.schone_scenes(scenes)
            self.gewijzigd()

    def zet_cuelijsten(self, lijsten):
        with self.lock:
            self.data["cuelijsten"] = self.schone_cuelijsten(lijsten)
            if self.cue and self.cue["lijst"] not in self.data["cuelijsten"]:
                self.cue = None
            self.gewijzigd()

    def cue_start(self, naam, stap=0):
        with self.lock:
            cl = self.data["cuelijsten"].get(naam)
            if not cl or not cl["stappen"]:
                raise ValueError("Deze cuelijst is leeg")
            self.cue = {"lijst": naam, "stap": int(stap) % len(cl["stappen"]), "start": None, "pauze": False}
            self._cue_laad(time.time())
            self.gewijzigd(opslaan=False)

    def cue_stop(self):
        with self.lock:
            self.cue = None
            self.gewijzigd(opslaan=False)

    def cue_pauze(self):
        with self.lock:
            if self.cue:
                self.cue["pauze"] = not self.cue["pauze"]
                if not self.cue["pauze"]:      # verder waar we waren
                    self.cue["start"] = self._cue_klok(time.time()) - self.cue.get("verstreken", 0)
                self.gewijzigd(opslaan=False)

    def cue_volgende(self, richting=1):
        with self.lock:
            if not self.cue:
                return
            cl = self.data["cuelijsten"].get(self.cue["lijst"])
            if not cl or not cl["stappen"]:
                self.cue = None
                return
            self.cue["stap"] = (self.cue["stap"] + richting) % len(cl["stappen"])
            self._cue_laad(time.time())
            self.gewijzigd(opslaan=False)

    def _cue_klok(self, nu):
        cl = self.data["cuelijsten"].get(self.cue["lijst"]) if self.cue else None
        return nu if cl and cl["eenheid"] == "seconden" else self.beat(nu)

    def _cue_laad(self, nu):
        cl = self.data["cuelijsten"][self.cue["lijst"]]
        stap = cl["stappen"][self.cue["stap"]]
        self.cue["start"] = self._cue_klok(nu)
        self.cue["verstreken"] = 0.0
        if stap["scene"] in self.data["scenes"]:
            self.laad_scene(stap["scene"], fade=stap["fade"], vanuit_cue=True)

    def cue_bijwerken(self, nu):
        if not self.cue or self.cue["pauze"]:
            return
        cl = self.data["cuelijsten"].get(self.cue["lijst"])
        if not cl or not cl["stappen"]:
            self.cue = None
            return
        stap = cl["stappen"][self.cue["stap"] % len(cl["stappen"])]
        verstreken = self._cue_klok(nu) - self.cue["start"]
        self.cue["verstreken"] = verstreken
        if verstreken >= stap["duur"]:
            if self.cue["stap"] + 1 >= len(cl["stappen"]) and not cl["herhalen"]:
                self.cue = None
            else:
                self.cue["stap"] = (self.cue["stap"] + 1) % len(cl["stappen"])
                self._cue_laad(nu)
            self.wijziging += 1

    def programmer_zet(self, fixtures, waarden):
        with self.lock:
            bekend = {f["id"] for f in self.data["fixtures"]}
            for fid in fixtures:
                fid = int(fid)
                if fid not in bekend:
                    continue
                p = self.programmer.setdefault(str(fid), {})
                for k in ("dim", "kleur", "pan", "tilt"):
                    if k in waarden:
                        if waarden[k] is None:
                            p.pop(k, None)
                        else:
                            p.update(self.schone_waarden({k: waarden[k]}))
                for c, v in (waarden.get("kanalen") or {}).items():
                    kanalen = p.setdefault("kanalen", {})
                    if v is None:
                        kanalen.pop(str(int(c)), None)
                    else:
                        kanalen.update(self.schone_waarden({"kanalen": {c: v}}).get("kanalen", {}))
                if not p.get("kanalen"):
                    p.pop("kanalen", None)
                if not p:
                    self.programmer.pop(str(fid), None)
            self.gewijzigd(opslaan=False)

    def programmer_wissen(self, fixtures=None):
        with self.lock:
            if fixtures:
                for fid in fixtures:
                    self.programmer.pop(str(int(fid)), None)
            else:
                self.programmer = {}
            self.gewijzigd(opslaan=False)

    # ------------------------------------------------------------ één DMX-frame berekenen
    def render(self, nu):
        with self.lock:
            show = self.data["show"]
            beat = self.beat(nu)
            self.auto_stap(beat)
            self.cue_bijwerken(nu)
            eb = self.effect_beat(beat)
            test = self.test if (self.test and nu < self.test["tot"]) else None
            hold = {s: nu < self.hold[s] or s in self.hold_vast for s in HOLD_SOORTEN}
            gehoord = [(t, k) for t, k in self.noten if t <= nu]
            if gehoord and nu - gehoord[-1][0] < 8.0:
                self.melodie_nu = [k for _, k in gehoord]
                self.sinds_noot = nu - gehoord[-1][0]
            else:
                self.melodie_nu, self.sinds_noot = [], None
            while self.energie_rij and self.energie_rij[0][0] <= nu:
                _, e_nieuw, bron = self.energie_rij.popleft()
                self.energie, self.energie_gezien = e_nieuw, nu
                self.luister.setdefault(bron, {"laatste_beat": 0.0}).update(energie=e_nieuw, laatste_energie=nu)
            self.muziek_beat = beat
            self.lichtman_toepassen(show, eb, nu)
            self.energie_attr = self.energie if nu - self.energie_gezien < 5.0 else None
            c = self.cache()
            menging = self.scene_menging(nu)
            master = 0.0 if show.get("blackout") else clamp(float(show.get("master", 100)), 0, 100) / 100.0
            faders = [f for f in self.data["faders"] if f["waarde"] > 0]

            frames = {u: bytearray(512) for u in c["universes"]}
            voorbeeld = []
            for fx in c["volgorde"]:
                inf = c["info"][fx["id"]]
                uit, stand = self.fixture_waarden(fx, inf, c["index"], eb, nu, show, master, menging, faders, hold, test)
                frame = frames.setdefault(int(fx.get("universe", 1)), bytearray(512))
                basis = int(fx.get("adres", 1)) - 1
                for k, v in enumerate(uit):
                    if 0 <= basis + k < 512:
                        frame[basis + k] = v
                voorbeeld.append(self.voorbeeld_van(fx, inf, uit))
            self.frames = frames
            self.voorbeeld = voorbeeld
            return frames

    def fixture_waarden(self, fx, inf, index, beat, nu, show, master, menging, faders, hold, test):
        kanalen, functies, kop_van = inf["kanalen"], inf["functies"], inf["kop_van"]
        fid = fx["id"]
        sleutel = str(fid)

        # 1. effecten per cel (met de patronen van de laag van deze lamp)
        laag = index["laag"].get(fid)
        eff = self.eff.get(laag) or self.eff[None]
        punch = 1.0
        if self.punch > 0:                       # knal op elke kick (op de maat van de muziek)
            punch = 1.0 - self.punch + self.punch * (1.0 - self.muziek_beat % 1.0) ** 2
        E, RGB = {}, {}
        for kop in inf["cellen"]:
            if (fid, kop) in index["intensiteit"]:
                i, n, cx = index["intensiteit"][(fid, kop)]
                E[kop] = intensiteit_effect(eff["intensiteit"], beat, i, n, cx, self.sinds_noot) * punch
                if self.adem > 0:              # rustig: langzame golf van links naar rechts (2 maten)
                    golf = 0.5 + 0.5 * math.sin(2 * math.pi * (self.muziek_beat / 8.0 - cx / 100.0))
                    E[kop] *= 1.0 - self.adem * golf
            else:
                E[kop] = 1.0
            if (fid, kop) in index["kleur"]:
                i, n, cx = index["kleur"][(fid, kop)]
                RGB[kop] = kleur_effect(eff["kleur"], beat, i, n, self.melodie_nu, cx)
            else:
                RGB[kop] = (255, 255, 255)
        if fid in index["beweging"]:
            i, n = index["beweging"][fid]
            pan, tilt = beweging_effect(eff["beweging"], self.bew_fasen.get(laag, 0.0), i, n)
        else:
            pan, tilt = 0.5, 0.5
        stand = _Stand(E, RGB, pan, tilt)

        # 2. scène-laag (met overvloeien) en 3. programmer
        ruw_scene = None
        if menging:
            a, b, f = menging[0].get(sleutel), menging[1].get(sleutel), menging[2]
            if a or b:
                sa, sb = stand.kopie().toepassen(a), stand.kopie().toepassen(b)
                stand = sb if f >= 1.0 else _Stand.meng(sa, sb, f)
                ruw_scene = ((a or {}).get("kanalen") or {}, (b or {}).get("kanalen") or {}, f)
        prog = self.programmer.get(sleutel)
        if prog:
            stand.toepassen(prog)

        # opbouw naar de drop: op de maat steeds sneller (1, 2, 4, 8 keer per beat), feller en naar wit;
        # vlak voor de drop even helemaal donker (het 'gat'), dan de flits
        if fx.get("strobe", True) and not inf["rook"]:
            if self.gat:
                stand.E = {k: 0.0 for k in stand.E}
            elif self.opbouw is not None:
                p = self.opbouw
                keer = 1 if p < 0.35 else 2 if p < 0.6 else 4 if p < 0.82 else 8
                aan = (self.muziek_beat * keer) % 1.0 < 0.5
                puls = 1.0 if aan else 0.1 + 0.4 * (1.0 - p)
                wit = 0.75 * p * p
                stand.E = {k: max(v, 0.3 + 0.7 * p) * puls for k, v in stand.E.items()}
                stand.RGB = {k: tuple(c + (255 - c) * wit for c in rgb) for k, rgb in stand.RGB.items()}

        # 4. helderheid: master, groep, energie
        groep = clamp(float(show["groepen"].get(fx.get("groep") or "Overig", 100)), 0, 100) / 100.0
        M = master * groep * eff["dim"]
        cel_factor, kleur_vol = {}, {}
        for kop in inf["cellen"]:
            if not inf["koppen"]:
                totaal = M * stand.E[kop]
            else:
                totaal = stand.E[kop] * (1.0 if inf["d0"] else M)
            eigen_dimmer = kop in inf["dimmer_koppen"]
            cel_factor[kop] = totaal
            r, g, b = stand.RGB[kop]
            w = 0.0
            if kop in inf["wit_koppen"]:
                w = min(r, g, b)
                r, g, b = r - w, g - w, b - w
            schaal = 1.0 if eigen_dimmer else totaal
            kleur_vol[kop] = {"red": r * schaal, "green": g * schaal, "blue": b * schaal, "white": w * schaal,
                              "amber": 0.0, "uv": 0.0,
                              "cyan": 255 - r * schaal, "magenta": 255 - g * schaal, "yellow": 255 - b * schaal}
        eerste = inf["cellen"][0]
        gem_E = sum(stand.E.values()) / max(1, len(stand.E))

        # pan/tilt binnen de grenzen van deze lamp
        p = 1.0 - stand.pan if fx.get("pan_omkeren") else stand.pan
        t = 1.0 - stand.tilt if fx.get("tilt_omkeren") else stand.tilt
        pan_v = fx.get("pan_min", 0) + p * (fx.get("pan_max", 255) - fx.get("pan_min", 0))
        tilt_v = fx.get("tilt_min", 0) + t * (fx.get("tilt_max", 255) - fx.get("tilt_min", 0))
        pan16 = int(clamp(pan_v, 0, 255) / 255.0 * 65535)
        tilt16 = int(clamp(tilt_v, 0, 255) / 255.0 * 65535)

        uit = []
        for n_k, k in enumerate(kanalen):
            fn = functies[n_k]
            kop = kop_van[n_k]
            v = float(k.get("standaard") or 0)
            if fn in ("dimmer", "dimmer_fine"):
                if inf["koppen"] and kop == 0:
                    d = M
                elif kop in cel_factor:
                    d = cel_factor[kop]
                else:
                    d = M * gem_E
                if inf["dimmer_fijn"]:
                    d16 = int(clamp(d, 0, 1) * 65535)
                    v = d16 >> 8 if fn == "dimmer" else d16 & 255
                else:
                    v = d * 255
            elif fn in KLEURFUNCTIES:
                v = kleur_vol.get(kop, kleur_vol[eerste])[fn]
            elif fn == "pan":
                v = pan16 >> 8
            elif fn == "pan_fine":
                v = pan16 & 255
            elif fn == "tilt":
                v = tilt16 >> 8
            elif fn == "tilt_fine":
                v = tilt16 & 255
            elif fn == "schakelaar":
                v = v if M * max(stand.E.values()) > 0.02 else 0
            uit.append(byte(v))

        # 5. patronen, kleurprogramma's, rotatie, … op de beat; daarna looks (vaste combinaties, bijv. laser-effecten)
        attributen = show.get("attributen") or {}
        if attributen:
            for n_k, fn in enumerate(functies):
                cfg = attributen.get(fn)
                if cfg and cfg.get("modus", "uit") != "uit":
                    v = attribuut_effect(cfg, kanalen[n_k], beat, fid, self.energie_attr)
                    if v is not None:
                        uit[n_k] = byte(v)
        looks = inf["prof"].get("looks") or []
        cfg = show["looks"]
        if looks and cfg.get("modus") != "uit":
            if cfg.get("modus") == "wissel":
                keuze = int(beat // max(1, int(cfg.get("elke", 16)))) % len(looks)
            else:
                keuze = int(cfg.get("keuze", {}).get(fx["profiel"], 0)) % len(looks)
            for kn, waarde in looks[keuze].get("waarden", {}).items():
                kn = int(kn) - 1
                if 0 <= kn < len(uit):
                    uit[kn] = byte(waarde)

        # losse kanaalwaarden uit scène en programmer
        if ruw_scene:
            ra, rb, f = ruw_scene
            for kn in set(ra) | set(rb):
                i = int(kn) - 1
                if 0 <= i < len(uit):
                    va, vb = ra.get(kn, uit[i]), rb.get(kn, uit[i])
                    uit[i] = byte(va + (vb - va) * f)
        if prog and prog.get("kanalen"):
            for kn, waarde in prog["kanalen"].items():
                i = int(kn) - 1
                if 0 <= i < len(uit):
                    uit[i] = byte(waarde)

        # macro-faders: hoogste waarde wint (HTP)
        for fd in faders:
            if fd["fixtures"] and fid not in fd["fixtures"]:
                continue
            w = byte(fd["waarde"] * 2.55)
            for i, fn in enumerate(functies):
                if fn == fd["functie"] and w > uit[i]:
                    uit[i] = w

        # 6. vasthoudknoppen
        flits = (hold["strobe"] or self.drop_nu) and fx.get("strobe", True)
        if (flits or hold["blinder"]) and fx.get("strobe", True):
            hardware = False
            for kn, k in enumerate(kanalen):
                fn = functies[kn]
                if flits and k.get("strobe") not in (None, ""):
                    uit[kn] = byte(k["strobe"])
                    hardware = hardware or fn == "strobe"
                elif fn in ("dimmer", "dimmer_fine", "red", "green", "blue", "white"):
                    uit[kn] = 255
                elif fn in ("amber", "uv", "cyan", "magenta", "yellow"):
                    uit[kn] = 0
                elif fn == "schakelaar":
                    uit[kn] = byte(k.get("standaard") or 255)
            if flits and not hardware and int(nu * float(show.get("strobe_hz", 12)) * 2) % 2:
                for kn, fn in enumerate(functies):
                    if fn == "dimmer" or (not inf["heeft_dimmer"] and fn in KLEURFUNCTIES):
                        uit[kn] = 255 if fn in ("cyan", "magenta", "yellow") else 0
        if hold["smoke"]:
            for kn, k in enumerate(kanalen):
                if k.get("rook") not in (None, ""):
                    uit[kn] = byte(k["rook"])
                elif functies[kn] == "smoke":
                    uit[kn] = 255

        # zoeken: lamp knippert (dimmer, kleuren en hoofdschakelaar aan/uit)
        zoek = self.zoek
        if zoek and zoek["fixture"] == fid and nu < zoek["tot"]:
            aan = int(nu * 4) % 2 == 0
            for kn, k in enumerate(kanalen):
                fn = functies[kn]
                if fn in ("dimmer", "red", "green", "blue", "white"):
                    uit[kn] = 255 if aan else 0
                elif fn == "schakelaar":
                    uit[kn] = byte(k.get("standaard") or 255) if aan else 0
                elif fn == "strobe":
                    uit[kn] = byte(k.get("standaard") or 0)

        # testpagina: ruwe waarden voor deze fixture
        if test and test.get("fixture") == fid:
            for kn, waarde in enumerate(test.get("waarden", [])[:len(uit)]):
                uit[kn] = byte(waarde)
        return uit, stand

    @staticmethod
    def voorbeeld_van(fx, inf, uit):
        """Wat je ongeveer zou zien: kleur per cel, pan/tilt en rook, afgeleid van de echte DMX-waarden."""
        functies, kop_van = inf["functies"], inf["kop_van"]
        per_kop = {}
        for i, fn in enumerate(functies):
            per_kop.setdefault(kop_van[i], {})[fn] = uit[i]
        vast = per_kop.get(0, {})
        dim0 = vast.get("dimmer", 255) / 255.0
        if "schakelaar" in vast and vast["schakelaar"] < 10:
            dim0 = 0.0
        kleuren = []
        for kop in inf["cellen"]:
            w = per_kop.get(kop, {}) if kop else vast
            dim = dim0 * (w.get("dimmer", 255) / 255.0 if kop else 1.0)
            if any(fn in w for fn in KLEURFUNCTIES):
                r = w.get("red", 0) + (255 - w["cyan"] if "cyan" in w else 0)
                g = w.get("green", 0) + (255 - w["magenta"] if "magenta" in w else 0)
                b = w.get("blue", 0) + (255 - w["yellow"] if "yellow" in w else 0)
                wit, am, uv = w.get("white", 0), w.get("amber", 0), w.get("uv", 0)
                rgb = (r + wit + 0.9 * am + 0.35 * uv, g + wit + 0.55 * am, b + wit + 0.8 * uv)
            elif inf["rook"]:
                rgb = (0, 0, 0)
            else:
                rgb = (255, 255, 255)
            kleuren.append(rgb_hex(tuple(min(255, c) * dim for c in rgb)))
        uitv = {"id": fx["id"], "c": kleuren}
        if "pan" in vast or "tilt" in vast:
            uitv["p"] = round(vast.get("pan", 128) / 255.0, 3)
            uitv["t"] = round(vast.get("tilt", 128) / 255.0, 3)
        if inf["rook"]:
            uitv["r"] = round(max(uit[i] for i, fn in enumerate(functies) if fn == "smoke") / 255.0, 2)
        return uitv

    def attribuut_overzicht(self):
        """Welke patroon-/programmafuncties de gepatchte lampen hebben, met hun keuzes (voor het tabblad Effecten)."""
        uit = {}
        with self.lock:
            for f in self.data["fixtures"]:
                prof = self.data["profielen"].get(f["profiel"])
                if not prof:
                    continue
                for k in prof["kanalen"]:
                    fn = k.get("functie")
                    if fn not in ATTRIBUUT_FUNCTIES:
                        continue
                    item = uit.setdefault(fn, {"opties": [], "lampen": []})
                    if f["naam"] not in item["lampen"]:
                        item["lampen"].append(f["naam"])
                    for o in bruikbare_opties(k):
                        if o["naam"] not in item["opties"]:
                            item["opties"].append(o["naam"])
        return {fn: uit[fn] for fn in ATTRIBUUT_FUNCTIES if fn in uit}

    def identificeer(self, fid, seconden=4.0):
        """Lamp laten knipperen, om te zien of adres, kabel en DMX-modus kloppen."""
        with self.lock:
            self.zoek = {"fixture": int(fid), "tot": time.time() + seconden} if fid is not None else None

    # ------------------------------------------------------------ wijzigingen via de API
    def wijzig_show(self, delta):
        with self.lock:
            show = self.data["show"]
            if "bpm" in delta:
                self.zet_bpm(delta.pop("bpm"))
                show["beat"]["auto"] = False
            samenvoegen(show, delta)
            if delta.get("auto", {}).get("aan"):
                self.auto_stap_nr = None
            self.gewijzigd()

    def zet_naam(self, naam):
        with self.lock:
            self.data["naam"] = str(naam).strip()[:60] or "Mijn show"
            self.gewijzigd()

    def zet_fixtures(self, lijst):
        with self.lock:
            schoon = self.schone_fixtures(lijst, self.data["profielen"])
            self.data["fixtures"] = schoon
            ids = {str(f["id"]) for f in schoon}
            self.programmer = {k: v for k, v in self.programmer.items() if k in ids}
            self.groepen_bijwerken(self.data)
            self.gewijzigd(patch=True)

    def zet_profielen(self, profielen):
        schoon = {str(pid)[:60]: schoon_profiel(p) for pid, p in profielen.items()}
        with self.lock:
            gebruikt = {f["profiel"] for f in self.data["fixtures"]}
            mist = gebruikt - set(schoon)
            if mist:
                raise ValueError("Dit profiel is nog in gebruik door een fixture: " +
                                 ", ".join(self.data["profielen"][m]["naam"] for m in mist if m in self.data["profielen"]))
            self.data["profielen"] = schoon
            self.gewijzigd(patch=True)

    def voeg_profiel_toe(self, prof):
        """Profiel uit de bibliotheek in de show zetten (of het bestaande teruggeven als het er al is)."""
        prof = schoon_profiel(prof)
        with self.lock:
            for pid, p in self.data["profielen"].items():
                if p["naam"] == prof["naam"] and p["kanalen"] == prof["kanalen"]:
                    return pid
            basis = "".join(c if c.isalnum() else "_" for c in prof["naam"].lower())[:40].strip("_") or "profiel"
            pid, n = basis, 2
            while pid in self.data["profielen"]:
                pid, n = f"{basis}_{n}", n + 1
            self.data["profielen"][pid] = prof
            self.gewijzigd(patch=True)
            return pid

    def zet_faders(self, faders):
        with self.lock:
            self.data["faders"] = self.schone_faders(faders)
            self.gewijzigd()

    def zet_fader(self, fid, waarde):
        with self.lock:
            for f in self.data["faders"]:
                if f["id"] == int(fid):
                    f["waarde"] = _getal(waarde, 0, 0, 100)
            self.gewijzigd()

    def zet_uitgangen(self, uitgangen):
        with self.lock:
            self.data["uitgangen"] = self.schone_uitgangen(uitgangen)
            self.gewijzigd(patch=True)
        self.uitgangen_gewijzigd()

    def uitgangen_gewijzigd(self):
        for f in self.bij_uitgangen:
            try:
                f()
            except Exception as e:  # een kapotte uitgang mag de rest niet tegenhouden
                print("Uitgangen bijwerken mislukt:", e, flush=True)

    def zet_hold(self, smoke=False, strobe=False, blinder=False):
        nu = time.time()
        with self.lock:
            for soort, aan in (("smoke", smoke), ("strobe", strobe), ("blinder", blinder)):
                self.hold[soort] = nu + HOLD_TIMEOUT if aan else 0.0

    def zet_test(self, fid, waarden):
        with self.lock:
            if fid is None:
                self.test = None
            else:
                self.test = {"fixture": int(fid), "waarden": [byte(v) for v in waarden][:512],
                             "tot": time.time() + TEST_TIMEOUT}

    def zet_pin(self, pin):
        with self.lock:
            inst = self.data["instellingen"]
            pin = str(pin or "").strip()
            if pin and (not pin.isdigit() or not 4 <= len(pin) <= 8):
                raise ValueError("De pincode moet 4 tot 8 cijfers zijn")
            inst["pin_zout"] = secrets.token_hex(8)
            inst["pin_hash"] = pin_hash(pin, inst["pin_zout"]) if pin else ""
            self.gewijzigd()

    def pin_klopt(self, pin):
        inst = self.data["instellingen"]
        return not inst.get("pin_hash") or secrets.compare_digest(pin_hash(pin, inst["pin_zout"]), inst["pin_hash"])

    # ------------------------------------------------------------ acties (knoppen, toetsenbord, MIDI)
    def actie(self, soort, arg=None, waarde=None):
        """Eén plek voor alle bedieningsacties. waarde: 0..1 voor faders, True/False voor indrukken/loslaten."""
        with self.lock:
            show = self.data["show"]
            ingedrukt = waarde is None or (waarde is True) or (isinstance(waarde, (int, float)) and waarde > 0.5)
            if soort == "hold":
                if arg in HOLD_SOORTEN:
                    (self.hold_vast.add if ingedrukt else self.hold_vast.discard)(arg)
                return
            if soort in ("master", "groep", "fader", "tempo_fader"):
                w = clamp(float(waarde or 0), 0.0, 1.0) * 100
                if soort == "master":
                    show["master"] = round(w)
                elif soort == "groep" and arg in show["groepen"]:
                    show["groepen"][arg] = round(w)
                elif soort == "fader":
                    self.zet_fader(arg, w)
                self.gewijzigd()
                return
            if not ingedrukt:
                return
            if soort == "scene":
                self.laad_scene(arg)
            elif soort == "scene_los":
                self.scene_loslaten()
            elif soort == "cue":
                if self.cue and self.cue["lijst"] == arg:
                    self.cue_stop()
                else:
                    self.cue_start(arg)
            elif soort == "cue_volgende":
                self.cue_volgende(1)
            elif soort == "cue_vorige":
                self.cue_volgende(-1)
            elif soort == "blackout":
                show["blackout"] = not show["blackout"]
                self.gewijzigd()
            elif soort == "freeze":
                self.bevroren = not self.bevroren
                self.gewijzigd(opslaan=False)
            elif soort == "auto":
                show["auto"]["aan"] = not show["auto"]["aan"]
                self.auto_stap_nr = None
                self.gewijzigd()
            elif soort == "tap":
                self.tap()
            elif soort == "tempo":
                show["tempo_factor"] = float(arg)
                self.gewijzigd()
            elif soort == "kleur_modus":
                show["kleur"]["modus"] = str(arg)
                self.gewijzigd()
            elif soort == "intensiteit_modus":
                show["intensiteit"]["modus"] = str(arg)
                self.gewijzigd()
            elif soort == "beweging_modus":
                show["beweging"]["modus"] = str(arg)
                self.gewijzigd()
            else:
                raise ValueError(f"Onbekende actie: {soort}")

    # ------------------------------------------------------------ status
    def lichtman_info(self, nu):
        st = self.lm
        if not st:
            return None
        return {"sectie": st["sectie"], "naam": SECTIES.get(st["sectie"], "Pauze" if st["sectie"] == "pauze" else st["sectie"]),
                "opbouw": round(st["opbouw"], 2) if st["opbouw"] is not None else None,
                "kick": st["kick"], "niveau": st["niveau"], "flits": st["flits"],
                "drop_over": round(st["drop_t"] - nu, 1) if st["drop_t"] else None}

    def status_info(self):
        nu = time.time()
        with self.lock:
            s = dict(self.status)
            uitg = self.data["uitgangen"]
            ok = [u for u in uitg if u["aan"] and self.uitgang_status.get(u["id"], {}).get("ok")]
            cue = None
            if self.cue:
                cl = self.data["cuelijsten"].get(self.cue["lijst"], {"stappen": []})
                cue = {"lijst": self.cue["lijst"], "stap": self.cue["stap"], "aantal": len(cl["stappen"]),
                       "pauze": self.cue["pauze"]}
            s.update(
                wijziging=self.wijziging,
                patch_versie=self.patch_versie,
                dongle=bool(ok),     # (oude naam, voor de telefoonpagina)
                uitgangen={u["id"]: self.uitgang_status.get(u["id"], {"ok": False, "tekst": "uit" if not u["aan"] else "…"})
                           for u in uitg},
                tijd=round(nu, 3),
                bpm=self.data["show"]["bpm"], beat=round(self.beat(nu), 3),
                smoke=nu < self.hold["smoke"] or "smoke" in self.hold_vast,
                strobe=nu < self.hold["strobe"] or "strobe" in self.hold_vast,
                blinder=nu < self.hold["blinder"] or "blinder" in self.hold_vast,
                test=self.test["fixture"] if self.test and nu < self.test["tot"] else None,
                auto=self.data["show"]["auto"]["aan"],
                blackout=self.data["show"]["blackout"],
                master=self.data["show"]["master"],
                bevroren=self.bevroren,
                beat_auto=self.data["show"]["beat"]["auto"],
                scene=self.scene_actief["naam"] if self.scene_actief else None,
                cue=cue,
                programmer=len(self.programmer),
                luister={b: {"bpm": i.get("bpm"), "zekerheid": i.get("zekerheid"),
                             "dubbel": bool(i.get("dubbel")) and self.data["show"]["beat"].get("snel_herkennen", True),
                             "hoort_beat": nu - i.get("laatste_beat", 0) < 3.0,
                             "noot": i.get("noot") if nu - i.get("laatste_noot", 0) < 3.0 else None,
                             "energie": round(i["energie"], 2) if nu - i.get("laatste_energie", 0) < 3.0 else None,
                             "drop": 0 <= nu - i.get("laatste_drop", 0) < 2.0,
                             "niveau": round(i.get("niveau", 0), 4) if nu - i.get("gezien", 0) < 3.0 else 0,
                             "muziek": i.get("niveau", 0) > 0.005 and nu - i.get("gezien", 0) < 3.0}
                         for b, i in self.luister.items()},
                lichtman=self.lichtman_info(nu),
            )
            s.update(self.extra_status)
        return s


def motor_lus(engine):
    """Rekent FPS keer per seconde een nieuw frame uit. De uitgangen versturen zelf het laatste frame."""
    frames, meet_start = 0, time.time()
    while True:
        start = time.time()
        try:
            engine.render(start)
        except Exception as e:   # nooit stoppen midden in de show
            print("Fout tijdens rekenen:", repr(e), flush=True)
            time.sleep(0.5)
        frames += 1
        if start - meet_start >= 1.0:
            engine.status["fps"] = frames
            frames, meet_start = 0, start
        rust = 1.0 / FPS - (time.time() - start)
        if rust > 0:
            time.sleep(rust)


def opslag_lus(engine):
    while True:
        time.sleep(2.0)
        if engine.moet_opslaan:
            try:
                engine.opslaan()
            except OSError as e:
                print("Opslaan mislukt:", e, flush=True)


MODI = {"kleur": KLEUR_MODI, "intensiteit": INTENSITEIT_MODI, "beweging": BEWEGING_MODI, "attribuut": ATTRIBUUT_MODI}
