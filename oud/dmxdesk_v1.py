#!/usr/bin/env python3
"""Zeutekauwn DMXDesk: lichtsturing voor de carnavalswagen.

- Telefoonpagina (/): SMOKE, STROBE en SMOKE + STROBE, alleen actief zolang je de knop vasthoudt.
- Instellingenpagina (/instellingen): show-effecten, scenes, fixtures, profielen en testen.
- Stuurt een goedkope FTDI USB-DMX dongle rechtstreeks aan (geen OLA nodig).

Alles wat je instelt wordt bewaard in show.json naast dit bestand.
"""
import copy
import glob
import json
import math
import os
import random
import socket
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

try:
    import serial
except ImportError:
    serial = None

HIER = os.path.dirname(os.path.abspath(__file__))
SHOW_BESTAND = os.environ.get("DMXDESK_SHOW", os.path.join(HIER, "show.json"))
WEB_MAP = os.path.join(HIER, "web")
POORT = int(os.environ.get("DMXDESK_POORT", 8080))
FPS = 30
HOLD_TIMEOUT = 0.7   # seconden: knop geldt als losgelaten als de telefoon niets meer stuurt
TEST_TIMEOUT = 6.0   # seconden: testmodus stopt vanzelf als de testpagina dicht is

FUNCTIES = {
    "dimmer": "Dimmer / intensiteit",
    "red": "Rood",
    "green": "Groen",
    "blue": "Blauw",
    "white": "Wit",
    "amber": "Amber",
    "uv": "UV",
    "strobe": "Strobe / shutter",
    "pan": "Pan",
    "pan_fine": "Pan fijn",
    "tilt": "Tilt",
    "tilt_fine": "Tilt fijn",
    "schakelaar": "Aan/uit-schakelaar",
    "smoke": "Rook",
    "fixed": "Vaste waarde",
}
KLEURFUNCTIES = ("red", "green", "blue", "white", "amber", "uv")


def kanaal(naam, functie, standaard=0, strobe=None, rook=None):
    return {"naam": naam, "functie": functie, "standaard": standaard, "strobe": strobe, "rook": rook}


def look(naam, waarden):
    return {"naam": naam, "waarden": waarden}


STANDAARD_PROFIELEN = {
    "par_oud": {
        "naam": "RGB Par 7 kanalen (uit oud script)",
        "kanalen": [
            kanaal("Dimmer", "dimmer"),
            kanaal("Rood", "red"),
            kanaal("Groen", "green"),
            kanaal("Blauw", "blue"),
            kanaal("Kanaal 5", "fixed"),
            kanaal("Kanaal 6", "fixed"),
            kanaal("Kanaal 7", "fixed"),
        ],
        "looks": [],
    },
    "mh_11": {
        "naam": "Moving head 11 kanalen (uit oud script)",
        "kanalen": [
            kanaal("Pan", "pan"),
            kanaal("Pan fijn", "pan_fine"),
            kanaal("Tilt", "tilt"),
            kanaal("Tilt fijn", "tilt_fine"),
            kanaal("Pan/tilt snelheid", "fixed"),
            kanaal("Dimmer", "dimmer"),
            kanaal("Strobe", "strobe", 0, 255),
            kanaal("Rood", "red"),
            kanaal("Groen", "green"),
            kanaal("Blauw", "blue"),
            kanaal("Wit", "white"),
        ],
        "looks": [],
    },
    "laser_20": {
        "naam": "Laser 20 kanalen",
        "kanalen": [
            kanaal("Main switch", "schakelaar", 255),
            kanaal("Rood aan/uit", "fixed", 255),
            kanaal("Groen aan/uit (kleur bij effect)", "fixed", 255, 255),
            kanaal("Blauw aan/uit", "fixed", 255),
            kanaal("Strobe", "strobe", 0, 220),
            kanaal("Kleur", "fixed", 45, 2),
            kanaal("Kleur-loopsnelheid", "fixed", 60, 0),
            kanaal("Patroon", "fixed", 0),
            kanaal("Patroongroep", "fixed", 0),
            kanaal("Grootte", "fixed", 180),
            kanaal("Zoom", "fixed", 0),
            kanaal("Rotatie", "fixed", 0),
            kanaal("X-flip", "fixed", 0),
            kanaal("Y-flip", "fixed", 0),
            kanaal("Pan (horizontaal)", "pan"),
            kanaal("Tilt (verticaal)", "tilt"),
            kanaal("Golf", "fixed", 0),
            kanaal("Geleidelijk tekenen", "fixed", 0),
            kanaal("Ingebouwd effect", "fixed", 0, 0),
            kanaal("Effectsnelheid", "fixed", 0),
        ],
        "looks": [
            look("Lijn-effect", {"3": 0, "19": 208, "20": 80}),
            look("Animatie-effect", {"3": 0, "19": 220, "20": 100}),
            look("Landmark-effect", {"3": 0, "19": 230, "20": 100}),
            look("Random mix", {"3": 0, "19": 245, "20": 120}),
            look("Patronen 1 draaiend", {"9": 0, "12": 150}),
            look("Patronen 2 draaiend", {"9": 30, "12": 150}),
            look("Randpatronen draaiend", {"9": 60, "12": 160}),
            look("Uitgesneden patronen", {"9": 85, "12": 170}),
            look("Animaties 1", {"9": 130}),
            look("Animaties 2", {"9": 160}),
            look("Golvend patroon", {"17": 100}),
            look("Zoomend patroon", {"11": 30}),
            look("Kleurverloop", {"6": 250, "7": 60}),
        ],
    },
    "rook_1": {
        "naam": "Rookmachine 1 kanaal",
        "kanalen": [kanaal("Rook", "smoke", 0, None, 255)],
        "looks": [],
    },
}


def fixture(fid, naam, profiel, adres, groep, x, **extra):
    f = {
        "id": fid, "naam": naam, "profiel": profiel, "adres": adres, "groep": groep, "x": x,
        "strobe": True,
        "effecten": {"kleur": True, "intensiteit": True, "beweging": True},
        "pan_min": 0, "pan_max": 255, "tilt_min": 0, "tilt_max": 255, "pan_omkeren": False,
    }
    f.update(extra)
    return f


STANDAARD_FIXTURES = [
    fixture(1, "Par 1", "par_oud", 1, "Pars", 20),
    fixture(2, "Par 2", "par_oud", 8, "Pars", 40),
    fixture(3, "Par 3", "par_oud", 15, "Pars", 60),
    fixture(4, "Par 4", "par_oud", 22, "Pars", 80),
    fixture(5, "Moving head 1", "mh_11", 30, "Moving heads", 30, tilt_max=120),
    fixture(6, "Moving head 2", "mh_11", 41, "Moving heads", 70, tilt_max=120),
    fixture(7, "Laser", "laser_20", 80, "Laser", 50,
            effecten={"kleur": False, "intensiteit": False, "beweging": False}),
]

STANDAARD_SHOW = {
    "bpm": 128.0,
    "master": 100,
    "blackout": False,
    "strobe_hz": 12,
    "kleur": {"modus": "chase", "palet": ["#ff0000", "#0000ff"], "snelheid": 1, "spreiding": 50},
    "intensiteit": {"modus": "aan", "snelheid": 1},
    "beweging": {"modus": "cirkel", "snelheid": 8, "grootte": 50, "spreiding": 50, "pan": 50, "tilt": 50},
    "looks": {"modus": "wissel", "elke": 16, "keuze": {}},
    "auto": {"aan": False, "elke": 32},
    "beat": {"auto": True, "vertraging_spotify": 200, "vertraging_mpd": 400, "bpm_min": 75, "bpm_max": 220,
             "snel_herkennen": True},
    "energie": {"aan": False, "flits_bij_drop": True},
    "groepen": {},
}
BEAT_POORT = 8091   # hier stuurt beatluister.py de gevonden beats naartoe

SNELHEDEN = [0.25, 0.5, 1, 2, 4, 8, 16]
AUTO_KLEUR = ["chase", "regenboog", "fade", "random", "wissel", "melodie"]
NOOTNAMEN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
AUTO_INTENSITEIT = ["aan", "aan", "chase", "pingpong", "golf", "puls", "om_en_om", "linksrechts", "random"]
AUTO_BEWEGING = ["cirkel", "acht", "linksrechts", "opneer", "zwaai"]
AUTO_PALETTEN = [
    ["#ff0000", "#0000ff"], ["#ff6600", "#ffcc00"], ["#ff00ff", "#00ffff"], ["#00ff00", "#0000ff"],
    ["#ff0000", "#ffffff"], ["#ff0000", "#ff8800", "#ffff00"], ["#8800ff", "#ff0088"],
    ["#00ffff", "#ffffff"], ["#ff0000", "#00ff00", "#0000ff"],
]


# ---------------------------------------------------------------- hulpfuncties

def clamp(v, laag, hoog):
    return max(laag, min(hoog, v))


def byte(v):
    return int(clamp(round(v), 0, 255))


def hex_rgb(h):
    try:
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (ValueError, IndexError, AttributeError):
        return (255, 255, 255)


def hsv_rgb(h):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    q, t = 255 * (1 - f), 255 * f
    return [(255, t, 0), (q, 255, 0), (0, 255, t), (0, q, 255), (t, 0, 255), (255, 0, q)][i]


def samenvoegen(doel, bron):
    """Voegt bron recursief in doel, alleen voor sleutels die in doel bestaan (plus vrije dicts)."""
    for k, v in bron.items():
        if isinstance(doel.get(k), dict) and isinstance(v, dict) and k not in ("keuze", "groepen"):
            samenvoegen(doel[k], v)
        elif k in ("keuze", "groepen") and isinstance(v, dict):
            doel.setdefault(k, {}).update(v)
        elif k in doel:
            doel[k] = v


# ---------------------------------------------------------------- effecten

def noot_kleur(klasse):
    """Elke toon een vaste kleur. Via de kwintencirkel, zodat een stapje in de melodie een duidelijk andere kleur geeft."""
    return hsv_rgb(((klasse * 7) % 12) / 12.0)


def intensiteit_effect(cfg, beat, i, n, x, sinds_noot=None):
    m = cfg.get("modus", "aan")
    if m == "noot_puls":
        if sinds_noot is None:
            return 1.0
        rest = max(0.0, 1.0 - sinds_noot / 0.35)
        return 0.15 + 0.85 * rest * rest
    s = max(0.125, float(cfg.get("snelheid", 1)))
    stap = int(beat // s)
    fase = (beat / s) % 1.0
    if m == "chase":
        return 1.0 if stap % n == i else 0.0
    if m == "chase_terug":
        return 1.0 if stap % n == n - 1 - i else 0.0
    if m == "pingpong":
        p = stap % max(1, 2 * n - 2)
        return 1.0 if (p if p < n else 2 * n - 2 - p) == i else 0.0
    if m == "om_en_om":
        return 1.0 if (i + stap) % 2 == 0 else 0.0
    if m == "linksrechts":
        return 1.0 if (x < 50) == (stap % 2 == 0) else 0.0
    if m == "binnenbuiten":
        return 1.0 if (abs(x - 50) < 25) == (stap % 2 == 0) else 0.0
    if m == "golf":
        return 0.5 + 0.5 * math.sin(2 * math.pi * (beat / (s * 4) - x / 100.0))
    if m == "puls":
        return (1.0 - fase) ** 2
    if m == "random":
        return 1.0 if random.Random(stap * 7919 + i).random() < 0.5 else 0.0
    return 1.0


def kleur_effect(cfg, beat, i, n, noten=()):
    palet = [hex_rgb(c) for c in (cfg.get("palet") or ["#ffffff"])]
    m = cfg.get("modus", "vast")
    s = max(0.125, float(cfg.get("snelheid", 1)))
    stap = int(beat // s)
    spreid = clamp(float(cfg.get("spreiding", 0)), 0, 100) / 100.0
    verschuiving = int(round(spreid * i))  # bij spreiding 100 heeft elke lamp een eigen stap
    if m == "melodie":
        if not noten:                       # geen melodie te horen: rustig door de regenboog
            return hsv_rgb((beat / 64.0 + spreid * i / max(1, n)) % 1.0)
        # spreiding: lamp 1 = huidige noot, lamp 2 = de noot daarvoor, ... (melodie loopt over de lampen)
        return noot_kleur(noten[-1 - min(len(noten) - 1, verschuiving)])
    if m == "wissel":
        return palet[(stap + verschuiving) % len(palet)]
    if m == "chase":
        return palet[(stap + i) % len(palet)]
    if m == "regenboog":
        return hsv_rgb((beat / (s * 16) + spreid * i / max(1, n)) % 1.0)
    if m == "fade":
        p = (beat / (s * 4) + spreid * i / max(1, n) * len(palet)) % len(palet)
        a, b, f = palet[int(p) % len(palet)], palet[(int(p) + 1) % len(palet)], p % 1.0
        return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))
    if m == "random":
        rnd = random.Random(stap * 104729 + i)
        return palet[rnd.randrange(len(palet))] if len(palet) > 1 else hsv_rgb(rnd.random())
    return palet[0]


def beweging_effect(cfg, fase, i, n):
    """fase = aantal afgelegde rondes (wordt per frame opgeteld, zodat een snelheidswissel geen sprong geeft)."""
    m = cfg.get("modus", "stil")
    g = clamp(float(cfg.get("grootte", 50)), 0, 100) / 200.0
    cp = clamp(float(cfg.get("pan", 50)), 0, 100) / 100.0
    ct = clamp(float(cfg.get("tilt", 50)), 0, 100) / 100.0
    f = 2 * math.pi * (fase + clamp(float(cfg.get("spreiding", 0)), 0, 100) / 100.0 * i / max(1, n))
    dp = dt = 0.0
    if m == "cirkel":
        dp, dt = g * math.cos(f), g * math.sin(f)
    elif m == "acht":
        dp, dt = g * math.sin(f), g * 0.5 * math.sin(2 * f)
    elif m == "opneer":
        dt = g * math.sin(f)
    elif m == "linksrechts":
        dp = g * math.sin(f)
    elif m == "zwaai":
        dp, dt = g * math.sin(f), g * 0.4 * math.sin(0.5 * f)
    return clamp(cp + dp, 0.0, 1.0), clamp(ct + dt, 0.0, 1.0)


# ---------------------------------------------------------------- engine

class Engine:
    def __init__(self):
        self.lock = threading.RLock()
        self.data = self.laden()
        self.bpm_t0 = time.time()
        self.taps = []
        self.hold = {"smoke": 0.0, "strobe": 0.0}
        self.test = None
        self.status = {"dongle": False, "poort": None, "fout": "", "fps": 0}
        self.laatste_frame = bytearray(512)
        self.auto_stap_nr = None
        self.moet_opslaan = False
        self.luister = {}            # per bron: wat de beat-luisteraar hoort
        self.bpm_kandidaat, self.bpm_teller = 0.0, 0
        self.noten = deque(maxlen=64)   # (tijd waarop hoorbaar, toon 0-11) van de melodie
        self.melodie_nu, self.sinds_noot = [], None
        self.energie, self.energie_gezien = 0.5, 0.0
        self.e_stap = 1.0                      # snelheidsfactor door energie (0,5 / 1 / 2)
        self.drop_van, self.drop_tot = 0.0, 0.0
        self.vorige_beat, self.bew_fase = None, 0.0
        self.eff, self.drop_nu = None, False

    # --- opslag
    def standaard(self):
        return {
            "versie": 1,
            "dmx_poort": "auto",
            "show": copy.deepcopy(STANDAARD_SHOW),
            "fixtures": copy.deepcopy(STANDAARD_FIXTURES),
            "profielen": copy.deepcopy(STANDAARD_PROFIELEN),
            "scenes": {},
        }

    def laden(self):
        data = self.standaard()
        if os.path.exists(SHOW_BESTAND):
            try:
                with open(SHOW_BESTAND, encoding="utf-8") as f:
                    geladen = json.load(f)
                for k in ("fixtures", "profielen", "scenes", "dmx_poort"):
                    if k in geladen:
                        data[k] = geladen[k]
                samenvoegen(data["show"], geladen.get("show", {}))
            except (OSError, ValueError) as e:
                print("show.json kon niet gelezen worden, standaard wordt gebruikt:", e)
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
        with self.lock:
            tekst = json.dumps(self.data, indent=2, ensure_ascii=False)
            self.moet_opslaan = False
        tmp = SHOW_BESTAND + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(tekst)
        os.replace(tmp, SHOW_BESTAND)

    # --- beat
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
            self.moet_opslaan = True

    def beat_bericht(self, m):
        """Verwerkt een bericht van beatluister.py: BPM bijsturen en de maat gelijk trekken."""
        nu = time.time()
        with self.lock:
            bron = str(m.get("bron", "?"))[:20]
            info = self.luister.setdefault(bron, {"laatste_beat": 0.0})
            vertraging = float(self.data["show"]["beat"].get("vertraging_" + bron, 200)) / 1000.0
            if m.get("soort") == "energie":
                self.energie, self.energie_gezien = float(m.get("e", 0.5)), nu
                info.update(energie=self.energie, laatste_energie=nu)
                return
            if m.get("soort") == "drop":
                # na een rustig stuk barst het los: korte witte flits op het moment dat je het hoort
                self.drop_van = float(m.get("t", nu)) + vertraging
                self.drop_tot = self.drop_van + 0.4
                info["laatste_drop"] = nu
                return
            if m.get("soort") == "noot":
                # melodie: onthouden wanneer deze noot te HOREN is (met de vertraging van de geluidsweg)
                klasse = int(m.get("klasse", 0)) % 12
                t_hoor = float(m.get("t", nu)) + float(self.data["show"]["beat"].get("vertraging_" + bron, 200)) / 1000.0
                self.noten.append((t_hoor, klasse))
                info.update(noot=NOOTNAMEN[klasse], laatste_noot=nu)
                return
            info.update(bpm=round(float(m.get("bpm") or 0), 1), zekerheid=round(float(m.get("conf") or 0), 2), gezien=nu)
            if "niveau" in m:
                info["niveau"] = float(m["niveau"])
            if m.get("soort") != "beat":
                return
            info["laatste_beat"] = nu
            cfg = self.data["show"]["beat"]
            bpm = float(m.get("bpm") or 0)
            if not cfg.get("auto") or bpm <= 0:
                return
            laag, hoog = float(cfg.get("bpm_min", 75)), float(cfg.get("bpm_max", 220))
            # snel nummer? aubio hoort dan vaak de helft; zit er ook een kick tússen de beats, dan verdubbelen
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
            t_hoor = float(m.get("t", nu)) + float(cfg.get("vertraging_" + bron, 200)) / 1000.0
            b = self.beat(t_hoor)
            fout = b - round(b)
            if abs(fout) < 0.35:
                self.bpm_t0 += fout * 60.0 / float(self.data["show"]["bpm"]) * 0.35

    # --- automatische show
    def auto_stap(self, beat):
        auto = self.data["show"]["auto"]
        if not auto.get("aan"):
            self.auto_stap_nr = None
            return
        nr = int(beat // max(4, int(auto.get("elke", 32))))
        if nr == self.auto_stap_nr:
            return
        self.auto_stap_nr = nr
        show = self.data["show"]
        show["kleur"].update(modus=random.choice(AUTO_KLEUR), palet=random.choice(AUTO_PALETTEN),
                             snelheid=random.choice([0.5, 1, 2]))
        show["intensiteit"].update(modus=random.choice(AUTO_INTENSITEIT), snelheid=random.choice([0.5, 1, 1, 2]))
        show["beweging"].update(modus=random.choice(AUTO_BEWEGING), snelheid=random.choice([4, 8, 8, 16]))

    def energie_nu(self, nu):
        if not self.data["show"]["energie"].get("aan") or nu - self.energie_gezien > 5.0:
            return None
        return self.energie

    def energie_toepassen(self, show, beat, nu):
        """Rustige muziek = langzaam, klein en wat gedimd. Extreem = snel, groot en vol."""
        e = self.energie_nu(nu)
        if e is None:
            self.eff = {"kleur": show["kleur"], "intensiteit": show["intensiteit"], "beweging": show["beweging"], "dim": 1.0}
            self.e_stap = 1.0
        else:
            # kleur/intensiteit in stappen (x2 trager / normaal / x2 sneller), met wat marge tegen heen-en-weer springen
            if self.e_stap == 1.0:
                self.e_stap = 0.5 if e > 0.78 else (2.0 if e < 0.27 else 1.0)
            elif self.e_stap == 0.5 and e < 0.70:
                self.e_stap = 1.0
            elif self.e_stap == 2.0 and e > 0.35:
                self.e_stap = 1.0
            bew = show["beweging"]
            self.eff = {
                "kleur": dict(show["kleur"], snelheid=float(show["kleur"].get("snelheid", 1)) * self.e_stap),
                "intensiteit": dict(show["intensiteit"], snelheid=float(show["intensiteit"].get("snelheid", 1)) * self.e_stap),
                "beweging": dict(bew, snelheid=max(1.0, float(bew.get("snelheid", 8)) * 2 ** (1.5 - 3 * e)),
                                 grootte=float(bew.get("grootte", 50)) * (0.35 + 0.65 * e)),
                "dim": 0.55 + 0.45 * e,
            }
        # beweging: fase optellen, dan geeft een snelheidswissel geen sprong in de positie
        if self.vorige_beat is not None:
            d = beat - self.vorige_beat
            if 0 <= d < 1:
                self.bew_fase += d / max(0.25, float(self.eff["beweging"].get("snelheid", 8)))
        self.vorige_beat = beat
        self.drop_nu = (e is not None and show["energie"].get("flits_bij_drop", True)
                        and self.drop_van <= nu < self.drop_tot)

    # --- één DMX-frame berekenen
    def render(self, nu):
        with self.lock:
            show = self.data["show"]
            profielen = self.data["profielen"]
            beat = self.beat(nu)
            self.auto_stap(beat)
            strobe_aan = nu < self.hold["strobe"]
            rook_aan = nu < self.hold["smoke"]
            test = self.test if (self.test and nu < self.test["tot"]) else None
            gehoord = [(t, k) for t, k in self.noten if t <= nu]
            if gehoord and nu - gehoord[-1][0] < 8.0:
                self.melodie_nu = [k for _, k in gehoord]
                self.sinds_noot = nu - gehoord[-1][0]
            else:
                self.melodie_nu, self.sinds_noot = [], None
            self.energie_toepassen(show, beat, nu)

            fixtures = [f for f in self.data["fixtures"] if f.get("profiel") in profielen]
            volgorde = sorted(fixtures, key=lambda f: (f.get("x", 50), f.get("id", 0)))
            index = {}
            for soort in ("kleur", "intensiteit", "beweging"):
                lijst = [f for f in volgorde if f.get("effecten", {}).get(soort, True)]
                index[soort] = {f["id"]: (i, len(lijst)) for i, f in enumerate(lijst)}

            frame = bytearray(512)
            for nr, fx in enumerate(volgorde):
                waarden = self.fixture_waarden(fx, profielen[fx["profiel"]], nr, index, beat, nu,
                                               show, strobe_aan, rook_aan, test)
                basis = int(fx.get("adres", 1)) - 1
                for k, v in enumerate(waarden):
                    if 0 <= basis + k < 512:
                        frame[basis + k] = v
            self.laatste_frame = frame
            return frame

    def fixture_waarden(self, fx, prof, nr, index, beat, nu, show, strobe_aan, rook_aan, test):
        kanalen = prof.get("kanalen", [])
        functies = [k.get("functie", "fixed") for k in kanalen]
        fid = fx["id"]

        # intensiteit 0..1
        master = 0.0 if show.get("blackout") else clamp(float(show.get("master", 100)), 0, 100) / 100.0
        groep = clamp(float(show["groepen"].get(fx.get("groep") or "Overig", 100)), 0, 100) / 100.0
        if fid in index["intensiteit"]:
            i, n = index["intensiteit"][fid]
            inten = intensiteit_effect(self.eff["intensiteit"], beat, i, n, float(fx.get("x", 50)), self.sinds_noot)
        else:
            inten = 1.0
        inten *= master * groep * self.eff["dim"]

        # kleur
        if fid in index["kleur"]:
            i, n = index["kleur"][fid]
            r, g, b = kleur_effect(self.eff["kleur"], beat, i, n, self.melodie_nu)
        else:
            r, g, b = 255, 255, 255
        w = 0.0
        if "white" in functies:
            w = min(r, g, b)
            r, g, b = r - w, g - w, b - w

        # beweging
        if fid in index["beweging"]:
            i, n = index["beweging"][fid]
            pan, tilt = beweging_effect(self.eff["beweging"], self.bew_fase, i, n)
        else:
            pan, tilt = 0.5, 0.5
        if fx.get("pan_omkeren"):
            pan = 1.0 - pan
        pan_v = float(fx.get("pan_min", 0)) + pan * (float(fx.get("pan_max", 255)) - float(fx.get("pan_min", 0)))
        tilt_v = float(fx.get("tilt_min", 0)) + tilt * (float(fx.get("tilt_max", 255)) - float(fx.get("tilt_min", 0)))
        pan16 = int(clamp(pan_v, 0, 255) / 255.0 * 65535)
        tilt16 = int(clamp(tilt_v, 0, 255) / 255.0 * 65535)

        heeft_dimmer = "dimmer" in functies
        kleurwaarde = {"red": r, "green": g, "blue": b, "white": w, "amber": 0, "uv": 0}
        uit = []
        for k in kanalen:
            fn = k.get("functie", "fixed")
            v = float(k.get("standaard") or 0)
            if fn == "dimmer":
                v = inten * 255
            elif fn in KLEURFUNCTIES:
                v = kleurwaarde[fn] * (1.0 if heeft_dimmer else inten)
            elif fn == "pan":
                v = pan16 >> 8
            elif fn == "pan_fine":
                v = pan16 & 255
            elif fn == "tilt":
                v = tilt16 >> 8
            elif fn == "tilt_fine":
                v = tilt16 & 255
            elif fn == "schakelaar":
                v = v if inten > 0.02 else 0
            uit.append(byte(v))

        # looks (bijv. laser-effecten)
        looks = prof.get("looks") or []
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

        # STROBE-knop: alles wit en vol, met hardware-strobe of software-knipperen
        if (strobe_aan or self.drop_nu) and fx.get("strobe", True):
            hardware = False
            for kn, k in enumerate(kanalen):
                fn = functies[kn]
                if k.get("strobe") not in (None, ""):
                    uit[kn] = byte(k["strobe"])
                    hardware = hardware or fn == "strobe"
                elif fn in ("dimmer", "red", "green", "blue", "white"):
                    uit[kn] = 255
                elif fn in ("amber", "uv"):
                    uit[kn] = 0
                elif fn == "schakelaar":
                    uit[kn] = byte(k.get("standaard") or 255)
            if not hardware and int(nu * float(show.get("strobe_hz", 12)) * 2) % 2:
                for kn, fn in enumerate(functies):
                    if fn == "dimmer" or (not heeft_dimmer and fn in KLEURFUNCTIES):
                        uit[kn] = 0

        # SMOKE-knop
        if rook_aan:
            for kn, k in enumerate(kanalen):
                if k.get("rook") not in (None, ""):
                    uit[kn] = byte(k["rook"])
                elif functies[kn] == "smoke":
                    uit[kn] = 255

        # testpagina: ruwe waarden voor deze fixture
        if test and test.get("fixture") == fid:
            for kn, waarde in enumerate(test.get("waarden", [])[:len(uit)]):
                uit[kn] = byte(waarde)
        return uit

    # --- API-wijzigingen
    def wijzig_show(self, delta):
        with self.lock:
            show = self.data["show"]
            if "bpm" in delta:
                self.zet_bpm(delta.pop("bpm"))
                show["beat"]["auto"] = False
            samenvoegen(show, delta)
            if delta.get("auto", {}).get("aan"):
                self.auto_stap_nr = None
            self.moet_opslaan = True

    def zet_fixtures(self, lijst):
        schoon = []
        with self.lock:
            for n, f in enumerate(lijst):
                if f.get("profiel") not in self.data["profielen"]:
                    raise ValueError(f"Fixture '{f.get('naam')}' heeft een onbekend profiel")
                basis = fixture(0, "", "", 1, "", 50)
                basis.update({k: f[k] for k in basis if k in f})
                basis["id"] = int(f.get("id") or 0) or (max([x.get("id", 0) for x in lijst] + [0]) + n + 1)
                basis["naam"] = str(basis["naam"])[:40] or f"Fixture {basis['id']}"
                basis["adres"] = int(clamp(int(basis["adres"]), 1, 512))
                basis["groep"] = str(basis["groep"]).strip()[:30] or "Overig"
                basis["x"] = int(clamp(int(basis["x"]), 0, 100))
                for k in ("pan_min", "pan_max", "tilt_min", "tilt_max"):
                    basis[k] = int(clamp(int(basis[k]), 0, 255))
                basis["effecten"] = {s: bool(basis.get("effecten", {}).get(s, True))
                                     for s in ("kleur", "intensiteit", "beweging")}
                basis["strobe"] = bool(basis["strobe"])
                basis["pan_omkeren"] = bool(basis["pan_omkeren"])
                schoon.append(basis)
            ids = [f["id"] for f in schoon]
            if len(ids) != len(set(ids)):
                raise ValueError("Twee fixtures hebben hetzelfde id")
            self.data["fixtures"] = schoon
            self.groepen_bijwerken(self.data)
            self.moet_opslaan = True

    def zet_profielen(self, profielen):
        schoon = {}
        for pid, p in profielen.items():
            kanalen = []
            for k in p.get("kanalen", [])[:64]:
                fn = k.get("functie") if k.get("functie") in FUNCTIES else "fixed"
                opt = lambda v: None if v in (None, "") else byte(float(v))
                kanalen.append(kanaal(str(k.get("naam", ""))[:40], fn, byte(float(k.get("standaard") or 0)),
                                      opt(k.get("strobe")), opt(k.get("rook"))))
            looks = []
            for lk in p.get("looks", [])[:64]:
                waarden = {str(int(c)): byte(float(v)) for c, v in lk.get("waarden", {}).items()
                           if 1 <= int(c) <= len(kanalen)}
                looks.append(look(str(lk.get("naam", ""))[:40] or "Look", waarden))
            schoon[str(pid)[:40]] = {"naam": str(p.get("naam", pid))[:60], "kanalen": kanalen, "looks": looks}
        with self.lock:
            gebruikt = {f["profiel"] for f in self.data["fixtures"]}
            mist = gebruikt - set(schoon)
            if mist:
                raise ValueError("Dit profiel is nog in gebruik door een fixture: " +
                                 ", ".join(self.data["profielen"][m]["naam"] for m in mist))
            self.data["profielen"] = schoon
            self.moet_opslaan = True

    def scene(self, actie, naam):
        naam = str(naam).strip()[:40]
        with self.lock:
            show, scenes = self.data["show"], self.data["scenes"]
            if actie == "opslaan" and naam:
                scenes[naam] = {k: copy.deepcopy(show[k]) for k in ("kleur", "intensiteit", "beweging", "looks")}
            elif actie == "laden" and naam in scenes:
                for k, v in scenes[naam].items():
                    show[k] = copy.deepcopy(v)
                show["auto"]["aan"] = False
            elif actie == "verwijderen":
                scenes.pop(naam, None)
            self.moet_opslaan = True

    def zet_hold(self, smoke, strobe):
        nu = time.time()
        with self.lock:
            self.hold["smoke"] = nu + HOLD_TIMEOUT if smoke else 0.0
            self.hold["strobe"] = nu + HOLD_TIMEOUT if strobe else 0.0

    def zet_test(self, fid, waarden):
        with self.lock:
            if fid is None:
                self.test = None
            else:
                self.test = {"fixture": int(fid), "waarden": [byte(float(v)) for v in waarden][:64],
                             "tot": time.time() + TEST_TIMEOUT}

    def status_info(self):
        nu = time.time()
        with self.lock:
            s = dict(self.status)
            s.update(bpm=self.data["show"]["bpm"], beat=round(self.beat(nu), 2),
                     smoke=nu < self.hold["smoke"], strobe=nu < self.hold["strobe"],
                     test=self.test["fixture"] if self.test and nu < self.test["tot"] else None,
                     auto=self.data["show"]["auto"]["aan"],
                     beat_auto=self.data["show"]["beat"]["auto"],
                     luister={b: {"bpm": i.get("bpm"), "zekerheid": i.get("zekerheid"),
                                  "dubbel": bool(i.get("dubbel")) and self.data["show"]["beat"].get("snel_herkennen", True),
                                  "hoort_beat": nu - i.get("laatste_beat", 0) < 3.0,
                                  "noot": i.get("noot") if nu - i.get("laatste_noot", 0) < 3.0 else None,
                                  "energie": round(i["energie"], 2) if nu - i.get("laatste_energie", 0) < 3.0 else None,
                                  "drop": nu - i.get("laatste_drop", 0) < 2.0,
                                  "muziek": i.get("niveau", 0) > 0.005 and nu - i.get("gezien", 0) < 3.0}
                              for b, i in self.luister.items()})
        return s


# ---------------------------------------------------------------- DMX-uitvoer

def zoek_dongle(voorkeur):
    if voorkeur and voorkeur != "auto":
        return voorkeur
    kandidaten = sorted(glob.glob("/dev/serial/by-id/*FTDI*") + glob.glob("/dev/serial/by-id/*FT232*"))
    kandidaten += sorted(glob.glob("/dev/ttyUSB*"))
    return kandidaten[0] if kandidaten else None


def dmx_lus(engine):
    ser = None
    volgende_poging = 0.0
    frames, meet_start = 0, time.time()
    while True:
        start = time.time()
        frame = engine.render(start)

        if ser is None and serial is not None and start >= volgende_poging:
            poort = zoek_dongle(engine.data.get("dmx_poort", "auto"))
            try:
                if not poort:
                    raise OSError("geen USB-DMX dongle gevonden")
                ser = serial.Serial(poort, baudrate=250000, bytesize=8, parity="N", stopbits=2,
                                    timeout=1, write_timeout=1)
                engine.status.update(dongle=True, poort=poort, fout="")
                print("DMX-dongle geopend:", poort, flush=True)
            except Exception as e:
                ser = None
                engine.status.update(dongle=False, poort=poort, fout=str(e))
                volgende_poging = start + 2.0

        if ser is not None:
            try:
                ser.break_condition = True
                time.sleep(0.00015)
                ser.break_condition = False
                time.sleep(0.00002)
                ser.write(b"\x00" + bytes(frame))
                ser.flush()  # wacht tot het frame echt verstuurd is (voorkomt flikkeren)
                frames += 1
            except Exception as e:
                print("DMX-fout, dongle opnieuw openen:", e, flush=True)
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                engine.status.update(dongle=False, fout=str(e))
                volgende_poging = time.time() + 1.0

        if time.time() - meet_start >= 1.0:
            engine.status["fps"] = frames
            frames, meet_start = 0, time.time()
        rust = 1.0 / FPS - (time.time() - start)
        if rust > 0:
            time.sleep(rust)


def beat_lus(engine):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", BEAT_POORT))
    while True:
        data, _ = sock.recvfrom(4096)
        try:
            engine.beat_bericht(json.loads(data))
        except (ValueError, TypeError):
            pass


def systeem_actie(engine, actie):
    """Pi netjes uitzetten of herstarten (vanaf de telefoon, op de wagen is er geen laptop)."""
    print("Pi wordt", "uitgezet" if actie == "poweroff" else "herstart", flush=True)
    try:
        engine.opslaan()
    except OSError:
        pass
    time.sleep(1.0)   # eerst het antwoord naar de telefoon laten gaan
    subprocess.run(["sudo", "-n", "systemctl", actie], check=False)


def opslag_lus(engine):
    while True:
        time.sleep(2.0)
        if engine.moet_opslaan:
            try:
                engine.opslaan()
            except OSError as e:
                print("Opslaan mislukt:", e, flush=True)


# ---------------------------------------------------------------- webserver

class Handler(BaseHTTPRequestHandler):
    engine = None

    def log_message(self, *args):
        pass

    def stuur(self, code, inhoud, soort="application/json; charset=utf-8"):
        data = inhoud if isinstance(inhoud, bytes) else json.dumps(inhoud, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def bestand(self, naam):
        try:
            with open(os.path.join(WEB_MAP, naam), "rb") as f:
                self.stuur(200, f.read(), "text/html; charset=utf-8")
        except OSError:
            self.stuur(404, {"fout": "niet gevonden"})

    def do_GET(self):
        e = self.engine
        pad = urlparse(self.path).path
        if pad in ("/", "/telefoon"):
            return self.bestand("telefoon.html")
        if pad == "/instellingen":
            return self.bestand("instellingen.html")
        if pad == "/api/status":
            return self.stuur(200, e.status_info())
        if pad == "/api/state":
            with e.lock:
                data = copy.deepcopy({k: e.data[k] for k in ("show", "fixtures", "profielen", "scenes", "dmx_poort")})
            data["functies"] = FUNCTIES
            data["status"] = e.status_info()
            return self.stuur(200, data)
        if pad == "/api/frame":
            return self.stuur(200, list(e.laatste_frame))
        self.stuur(404, {"fout": "niet gevonden"})

    def do_POST(self):
        e = self.engine
        pad = urlparse(self.path).path
        try:
            lengte = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(lengte) or b"{}")
            if pad == "/api/hold":
                e.zet_hold(bool(body.get("smoke")), bool(body.get("strobe")))
            elif pad == "/api/tap":
                e.tap()
            elif pad == "/api/show":
                e.wijzig_show(body)
            elif pad == "/api/fixtures":
                e.zet_fixtures(body)
            elif pad == "/api/profielen":
                e.zet_profielen(body)
            elif pad == "/api/scene":
                e.scene(body.get("actie"), body.get("naam", ""))
            elif pad == "/api/test":
                e.zet_test(body.get("fixture"), body.get("waarden", []))
            elif pad == "/api/systeem":
                actie = {"uitzetten": "poweroff", "herstarten": "reboot"}.get(body.get("actie"))
                if not actie:
                    raise ValueError("onbekende actie")
                threading.Thread(target=systeem_actie, args=(e, actie), daemon=True).start()
            else:
                return self.stuur(404, {"fout": "niet gevonden"})
            self.stuur(200, {"ok": True})
        except (ValueError, TypeError, KeyError) as fout:
            self.stuur(400, {"fout": str(fout)})


def main():
    engine = Engine()
    if not os.path.exists(SHOW_BESTAND):
        engine.opslaan()
    Handler.engine = engine
    threading.Thread(target=dmx_lus, args=(engine,), daemon=True).start()
    threading.Thread(target=opslag_lus, args=(engine,), daemon=True).start()
    threading.Thread(target=beat_lus, args=(engine,), daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", POORT), Handler)
    server.daemon_threads = True
    print(f"Zeutekauwn DMXDesk draait op poort {POORT}", flush=True)
    try:
        server.serve_forever()
    finally:
        if engine.moet_opslaan:
            engine.opslaan()


if __name__ == "__main__":
    main()
