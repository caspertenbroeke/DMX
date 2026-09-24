"""Lampenbibliotheek: ingebouwde profielen, de Open Fixture Library, en het inlezen van QLC+-bestanden (.qxf).

De Open Fixture Library (https://open-fixture-library.org, MIT-licentie) zit ingepakt in data/ofl.json.gz.
Bijwerken: python tools/ofl_bijwerken.py
"""
import copy
import gzip
import json
import os
import re
import threading
import xml.etree.ElementTree as ET

from . import paden
from .profielen import STANDAARD_PROFIELEN, kanaal, raad_soort, schoon_profiel

MAX_OPTIES = 64

# ---------------------------------------------------------------- hulpjes

KLEUREN_OFL = {
    "Red": "red", "Green": "green", "Blue": "blue", "White": "white", "Warm White": "white", "Cold White": "white",
    "Amber": "amber", "UV": "uv", "Cyan": "cyan", "Magenta": "magenta", "Yellow": "yellow",
}
SOORT_OFL = [
    ({"Moving Head", "Scanner", "Barrel Scanner"}, "moving"), ({"Laser"}, "laser"), ({"Smoke", "Hazer"}, "rook"),
    ({"Pixel Bar", "Matrix"}, "bar"), ({"Color Changer", "Blinder"}, "par"), ({"Strobe"}, "strobe"),
    ({"Dimmer"}, "dimmer"),
]


def _natuurlijk(s):
    return [int(d) if d.isdigit() else d.lower() for d in re.split(r"(\d+)", str(s))]


def _dmx_waarde(v, standaard=0):
    """OFL-waarde: getal, of percentage als tekst ('50%')."""
    if isinstance(v, (int, float)):
        while v > 255:          # 16- of 24-bit waarde: alleen de grove byte
            v = int(v) >> 8
        return int(max(0, v))
    if isinstance(v, str) and v.endswith("%"):
        try:
            return int(round(max(0.0, min(100.0, float(v[:-1]))) * 2.55))
        except ValueError:
            return standaard
    return standaard


def _strobe_waarde(van, tot, langzaam_snel=True):
    """Een lekker snelle strobe binnen het bereik."""
    return int(round(van + (0.8 if langzaam_snel else 0.2) * (tot - van)))


# ---------------------------------------------------------------- Open Fixture Library

def _ofl_cap_naam(cap, wielen, kanaalnaam=""):
    if cap.get("comment"):
        return cap["comment"]
    t = cap.get("type", "")
    if t == "NoFunction":
        return "Geen functie"
    if t == "ShutterStrobe":
        e = cap.get("shutterEffect", "")
        naam = {"Open": "Open", "Closed": "Dicht", "Strobe": "Strobe", "Pulse": "Puls", "RampUp": "Ramp omhoog",
                "RampDown": "Ramp omlaag", "RampUpDown": "Ramp op/neer", "Lightning": "Bliksem",
                "Spikes": "Pieken", "Burst": "Burst"}.get(e, e)
        if cap.get("speedStart"):
            naam += f" {cap['speedStart']} → {cap.get('speedEnd', '')}"
        return naam
    if t in ("WheelSlot", "WheelShake"):
        wiel = cap.get("wheel") or kanaalnaam      # zonder 'wheel' heet het wiel zoals het kanaal
        if isinstance(wiel, list):
            wiel = wiel[0] if wiel else ""
        slots = (wielen.get(wiel) or next(iter(wielen.values()), {})).get("slots", []) if wielen else []
        nr = cap.get("slotNumber")
        if isinstance(nr, (int, float)) and 1 <= int(nr) <= len(slots):
            slot = slots[int(nr) - 1]
            naam = slot.get("name") or slot.get("type", "Slot")
            if slot.get("type") == "Open":
                naam = "Open"
            return (naam + (" (shake)" if t == "WheelShake" else "")) if int(nr) == nr else f"{naam} (tussenin)"
        return t
    if t == "ColorIntensity":
        return cap.get("color", "Kleur")
    if t == "ColorPreset":
        kleuren = cap.get("colors") or cap.get("colorsStart") or []
        return "Kleur " + ", ".join(kleuren) if kleuren else "Kleurpreset"
    if t == "Effect":
        return cap.get("effectName") or cap.get("effectPreset") or "Effect"
    return {"Maintenance": "Onderhoud", "Generic": "Algemeen", "Intensity": "Intensiteit", "Rotation": "Rotatie",
            "Prism": "Prisma", "PrismRotation": "Prisma draaien", "Focus": "Focus", "Zoom": "Zoom", "Iris": "Iris",
            "Frost": "Frost", "Fog": "Rook", "FogOutput": "Rookhoeveelheid", "EffectSpeed": "Effectsnelheid",
            "PanTiltSpeed": "Pan/tilt-snelheid", "SoundSensitivity": "Geluidsgevoeligheid", "Speed": "Snelheid",
            "WheelRotation": "Wiel draaien", "WheelSlotRotation": "Slot draaien", "ColorTemperature": "Kleurtemperatuur",
            "StrobeSpeed": "Strobesnelheid", "StrobeDuration": "Strobeduur", "Time": "Tijd"}.get(t, t)


def ofl_kanaal(naam, ch, fijn=0, wielen=None, kop=0):
    """Eén OFL-kanaal omzetten. fijn = 1 voor het 'fine'-kanaal (16 bit), 2 voor 24 bit, enz."""
    if ch is None:
        return kanaal(naam or "Leeg", "fixed", 0, kop=kop)
    caps = [ch["capability"]] if "capability" in ch else list(ch.get("capabilities") or [])
    standaard = _dmx_waarde(ch.get("defaultValue", 0)) if not fijn else 0
    typen = [c.get("type") for c in caps]
    eerste = caps[0] if caps else {}
    if fijn:
        basis = eerste.get("type")
        fn = {"Intensity": "dimmer_fine", "Pan": "pan_fine", "Tilt": "tilt_fine"}.get(basis, "fixed") if fijn == 1 else "fixed"
        return kanaal(naam, fn, 0, kop=kop)

    opties = []
    for c in caps[:MAX_OPTIES]:
        bereik = c.get("dmxRange") or [0, 255]
        opties.append({"van": _dmx_waarde(bereik[0]), "tot": _dmx_waarde(bereik[1], 255), "naam": _ofl_cap_naam(c, wielen or {}, naam)[:50]})

    if len(caps) == 1 and eerste.get("type") == "ColorIntensity":
        fn = KLEUREN_OFL.get(eerste.get("color"), "fixed")
        return kanaal(naam, fn, standaard if fn == "fixed" else 0, kop=kop)
    if eerste.get("type") == "Intensity":
        return kanaal(naam, "dimmer", 0, kop=kop, opties=opties if len(caps) > 1 else None)
    if eerste.get("type") in ("Pan", "Tilt") and len(caps) == 1:
        return kanaal(naam, eerste["type"].lower(), standaard, kop=kop)
    if any(t in ("Fog", "FogOutput") for t in typen) and not any(t == "ShutterStrobe" for t in typen):
        rook = next((c for c in caps if c.get("type") in ("Fog", "FogOutput")), eerste)
        bereik = rook.get("dmxRange") or [0, 255]
        return kanaal(naam, "smoke", 0, None, _dmx_waarde(bereik[1], 255), kop=kop,
                      opties=opties if len(caps) > 1 else None)
    if "ShutterStrobe" in typen:
        open_cap = next((c for c in caps if c.get("type") == "ShutterStrobe" and c.get("shutterEffect") == "Open"), None)
        geen = next((c for c in caps if c.get("type") == "NoFunction"), None)
        strobe = next((c for c in caps if c.get("type") == "ShutterStrobe" and c.get("shutterEffect") == "Strobe"
                       and not c.get("randomTiming")), None)
        std = standaard
        if open_cap:
            std = _dmx_waarde((open_cap.get("dmxRange") or [255])[0])
        elif geen and "defaultValue" not in ch:
            std = _dmx_waarde((geen.get("dmxRange") or [0])[0])
        strobe_w = None
        if strobe:
            van, tot = (strobe.get("dmxRange") or [0, 255])[:2]
            snel_eerst = str(strobe.get("speedStart", "")).lower() in ("fast", "100%")
            strobe_w = _strobe_waarde(_dmx_waarde(van), _dmx_waarde(tot, 255), not snel_eerst)
        return kanaal(naam, "strobe", std, strobe_w, kop=kop, opties=opties)
    return kanaal(naam, "fixed", standaard, kop=kop, opties=opties if len(caps) > 1 else None)


def _pixel_sleutels(matrix):
    """Alle pixels van de matrix als [(sleutel, (x, y, z))], plus de groepen."""
    pixels = []
    if "pixelKeys" in matrix:
        for z, laag in enumerate(matrix["pixelKeys"]):
            for y, rij in enumerate(laag):
                for x, sleutel in enumerate(rij):
                    if sleutel is not None:
                        pixels.append((sleutel, (x, y, z)))
    elif "pixelCount" in matrix:
        xs, ys, zs = (list(matrix["pixelCount"]) + [1, 1, 1])[:3]
        assen = [n for n in (xs, ys, zs) if n > 1]
        for z in range(zs):
            for y in range(ys):
                for x in range(xs):
                    pos = (x + 1, y + 1, z + 1)
                    if len(assen) == 3:
                        sleutel = f"({pos[0]}, {pos[1]}, {pos[2]})"
                    elif len(assen) == 2:
                        sleutel = "(" + ", ".join(str(p) for p, n in zip(pos, (xs, ys, zs)) if n > 1) + ")"
                    else:
                        sleutel = str(max(pos))
                    pixels.append((sleutel, (x, y, z)))
    return pixels, dict(matrix.get("pixelGroups") or {})


def _volgorde(pixels, groepen, herhaal):
    if isinstance(herhaal, list):
        return herhaal
    if herhaal == "eachPixelGroup":
        return list(groepen)
    if herhaal == "eachPixelABC":
        return sorted((p for p, _ in pixels), key=_natuurlijk)
    m = re.match(r"eachPixel([XYZ]{3})$", str(herhaal))
    if m:
        as_nr = {"X": 0, "Y": 1, "Z": 2}
        snelste = [as_nr[a] for a in m.group(1)]
        return [p for p, pos in sorted(pixels, key=lambda pp: tuple(pp[1][a] for a in reversed(snelste)))]
    return [p for p, _ in pixels]


def ofl_naar_profielen(d, fabrikant=""):
    """Alle modi van een OFL-fixture als DMXDesk-profielen: [(modusnaam, profiel)]."""
    beschikbaar = dict(d.get("availableChannels") or {})
    templates = dict(d.get("templateChannels") or {})
    wielen = d.get("wheels") or {}
    pixels, groepen = _pixel_sleutels(d.get("matrix") or {})
    alle_pixels = [p for p, _ in pixels]

    # naam -> (kanaaldefinitie, fijn-niveau, pixelsleutel)
    opzoek = {}

    def registreer(naam, ch, pixel):
        opzoek[naam] = (ch, 0, pixel)
        for n, alias in enumerate(ch.get("fineChannelAliases") or []):
            opzoek[alias] = (ch, n + 1, pixel)
        for cap in ([ch["capability"]] if "capability" in ch else ch.get("capabilities") or []):
            for alias, doel in (cap.get("switchChannels") or {}).items():
                opzoek.setdefault(alias, ("wissel", doel, pixel))

    for naam, ch in beschikbaar.items():
        registreer(naam, ch, None)
    for tnaam, ch in templates.items():
        for sleutel in alle_pixels + list(groepen):
            ch_pixel = json.loads(json.dumps(ch).replace("$pixelKey", str(sleutel)))
            registreer(tnaam.replace("$pixelKey", str(sleutel)), ch_pixel, sleutel)

    soort = None
    categorieen = set(d.get("categories") or [])
    for cats, s in SOORT_OFL:
        if cats & categorieen:
            soort = s
            break

    uitkomst = []
    for modus in d.get("modes") or []:
        namen = []
        for item in modus.get("channels") or []:
            if isinstance(item, dict) and item.get("insert") == "matrixChannels":
                volgorde = _volgorde(pixels, groepen, item.get("repeatFor"))
                tmpl = item.get("templateChannels") or []
                if item.get("channelOrder") == "perChannel":
                    namen += [(t.replace("$pixelKey", str(p)) if t else None) for t in tmpl for p in volgorde]
                else:
                    namen += [(t.replace("$pixelKey", str(p)) if t else None) for p in volgorde for t in tmpl]
            else:
                namen.append(item)
        kop_nr, kanalen = {}, []
        for naam in namen:
            gevonden = opzoek.get(naam) if naam is not None else None
            diepte = 0
            while gevonden and gevonden[0] == "wissel" and diepte < 5:   # schakelkanaal: standaarddoel nemen
                gevonden = opzoek.get(gevonden[1])
                diepte += 1
            if not gevonden or gevonden[0] == "wissel":
                kanalen.append(kanaal(str(naam or "Leeg"), "fixed", 0))
                continue
            ch, fijn, pixel = gevonden
            kop = 0
            if pixel is not None and not (groepen.get(pixel) == "all"):
                kop = kop_nr.setdefault(pixel, len(kop_nr) + 1)
            kanalen.append(ofl_kanaal(str(naam), ch, fijn, wielen, kop))
        if len(kop_nr) == 1:          # één cel = gewoon één lamp
            for k in kanalen:
                k["kop"] = 0
        prof = {"naam": f"{d.get('name', 'Lamp')} – {modus.get('name', '')}".strip(" –"),
                "fabrikant": fabrikant, "soort": soort or raad_soort(kanalen), "kanalen": kanalen, "looks": [],
                "bron": "ofl"}
        uitkomst.append((str(modus.get("name") or f"{len(kanalen)} kanalen"), schoon_profiel(prof)))
    return uitkomst


# ---------------------------------------------------------------- QLC+ (.qxf)

QLC_PRESET = {
    "IntensityMasterDimmer": "dimmer", "IntensityDimmer": "dimmer",
    "IntensityMasterDimmerFine": "dimmer_fine", "IntensityDimmerFine": "dimmer_fine",
    "IntensityRed": "red", "IntensityGreen": "green", "IntensityBlue": "blue", "IntensityWhite": "white",
    "IntensityAmber": "amber", "IntensityUV": "uv", "IntensityCyan": "cyan", "IntensityMagenta": "magenta",
    "IntensityYellow": "yellow",
    "PositionPan": "pan", "PositionPanFine": "pan_fine", "PositionTilt": "tilt", "PositionTiltFine": "tilt_fine",
    "ShutterStrobeSlowFast": "strobe", "ShutterStrobeFastSlow": "strobe",
}
QLC_KLEUR = {"Red": "red", "Green": "green", "Blue": "blue", "White": "white", "Amber": "amber", "UV": "uv",
             "Cyan": "cyan", "Magenta": "magenta", "Yellow": "yellow"}
QLC_SOORT = {"Moving Head": "moving", "Scanner": "moving", "Color Changer": "par", "LED Bar (Beams)": "bar",
             "LED Bar (Pixels)": "bar", "Laser": "laser", "Smoke": "rook", "Hazer": "rook", "Strobe": "strobe",
             "Dimmer": "dimmer"}


def _zonder_ns(el):
    for e in el.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
    return el


def qxf_naar_profielen(tekst):
    try:
        wortel = _zonder_ns(ET.fromstring(tekst))
    except ET.ParseError as e:
        raise ValueError(f"Geen geldig QLC+-bestand: {e}")
    if wortel.tag != "FixtureDefinition":
        raise ValueError("Geen QLC+-fixturedefinitie (FixtureDefinition ontbreekt)")
    fabrikant = (wortel.findtext("Manufacturer") or "").strip()
    model = (wortel.findtext("Model") or "Lamp").strip()
    soort_qlc = (wortel.findtext("Type") or "").strip()
    rook_lamp = soort_qlc in ("Smoke", "Hazer")

    definities = {}
    for ch in wortel.findall("Channel"):
        naam = ch.get("Name") or "Kanaal"
        preset = ch.get("Preset") or ""
        groep = ch.find("Group")
        groep_naam = (groep.text or "").strip() if groep is not None else ""
        fijn = groep is not None and groep.get("Byte") == "1"
        kleur = (ch.findtext("Colour") or "").strip()
        caps = [(int(c.get("Min", 0)), int(c.get("Max", 255)), (c.text or "").strip(), c.get("Preset") or "")
                for c in ch.findall("Capability")]
        standaard = int(ch.get("Default") or 0)
        opties = [{"van": a, "tot": b, "naam": t[:50] or p} for a, b, t, p in caps[:MAX_OPTIES]]

        fn = QLC_PRESET.get(preset)
        if fn is None and preset.endswith("Fine"):
            fn = "fixed"
        if fn is None:
            if groep_naam == "Intensity":
                fn = "fixed" if fijn else (QLC_KLEUR.get(kleur) or ("smoke" if rook_lamp else "dimmer"))
            elif groep_naam in ("Pan", "Tilt"):
                fn = groep_naam.lower() + ("_fine" if fijn else "")
            elif groep_naam == "Shutter" or preset.startswith("Shutter"):
                fn = "strobe"
            else:
                fn = "fixed"
        strobe_w = rook_w = None
        if fn == "strobe":
            for a, b, t, p in caps:
                tl, pl = t.lower(), p.lower()
                if "open" in tl or p == "ShutterOpen" or "no function" in tl or "no strobe" in tl:
                    if not ch.get("Default"):
                        standaard = a
                    break
            for a, b, t, p in caps:
                tl, pl = t.lower(), p.lower()
                if ("strobe" in tl or "strobe" in pl) and "random" not in tl and "random" not in pl:
                    strobe_w = _strobe_waarde(a, b, not ("fastslow" in pl.replace(" ", "") or "fast to slow" in tl))
                    break
        if fn == "smoke":
            rook_w = 255
        if fn in ("dimmer", "red", "green", "blue", "white", "amber", "uv", "cyan", "magenta", "yellow", "pan", "tilt",
                  "pan_fine", "tilt_fine", "dimmer_fine"):
            standaard = 0 if fn not in ("pan", "tilt") else standaard
            opties = [] if len(caps) <= 1 else opties
        definities[naam] = kanaal(naam, fn, standaard, strobe_w, rook_w, opties=opties if len(opties) > 1 else None)

    uitkomst = []
    for modus in wortel.findall("Mode"):
        mnaam = modus.get("Name") or "Modus"
        nummers = sorted(((int(c.get("Number", 0)), (c.text or "").strip()) for c in modus.findall("Channel")))
        kanalen = [copy.deepcopy(definities.get(naam) or kanaal(naam or "Leeg", "fixed")) for _, naam in nummers]
        koppen = modus.findall("Head")
        if len(koppen) > 1:
            for nr, kop in enumerate(koppen):
                for c in kop.findall("Channel"):
                    i = int(c.text or -1)
                    if 0 <= i < len(kanalen):
                        kanalen[i]["kop"] = nr + 1
        prof = {"naam": f"{model} – {mnaam}", "fabrikant": fabrikant,
                "soort": QLC_SOORT.get(soort_qlc) or raad_soort(kanalen), "kanalen": kanalen, "looks": [], "bron": "qlc"}
        uitkomst.append((mnaam, schoon_profiel(prof)))
    if not uitkomst:
        raise ValueError("Dit QLC+-bestand heeft geen modi")
    return uitkomst


def importeer_bestand(bestandsnaam, inhoud):
    """Een geüpload profielbestand (.qxf van QLC+, .json van de Open Fixture Library of DMXDesk)."""
    naam = (bestandsnaam or "").lower()
    tekst = inhoud.decode("utf-8-sig", errors="replace") if isinstance(inhoud, bytes) else inhoud
    if naam.endswith(".qxf") or tekst.lstrip().startswith("<"):
        return qxf_naar_profielen(tekst)
    try:
        d = json.loads(tekst)
    except ValueError:
        raise ValueError("Onbekend bestand: gebruik een .qxf (QLC+) of .json (Open Fixture Library)")
    if isinstance(d, dict) and "modes" in d and ("availableChannels" in d or "templateChannels" in d):
        return ofl_naar_profielen(d, d.get("manufacturerKey", "").replace("-", " ").title())
    if isinstance(d, dict) and "kanalen" in d:
        return [(d.get("naam", "Profiel"), schoon_profiel(d))]
    raise ValueError("Dit JSON-bestand is geen fixture uit de Open Fixture Library")


# ---------------------------------------------------------------- de bibliotheek zelf

class Bibliotheek:
    """Zoeken gaat via een kleine index; een lamp wordt pas uitgepakt als je hem kiest (zuinig op de Pi)."""

    def __init__(self, map_=None):
        self.index_bestand = os.path.join(map_, "ofl-index.json.gz") if map_ else paden.data_bestand("ofl-index.json.gz")
        self.bestand = os.path.join(map_, "ofl.json.gz") if map_ else paden.data_bestand("ofl.json.gz")
        self._index = None
        self._fixtures = None
        self._lock = threading.Lock()

    @staticmethod
    def _lees(pad, leeg):
        try:
            with gzip.open(pad, "rt", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            print("Lampenbibliotheek niet gevonden:", e, flush=True)
            return leeg

    def ofl(self):
        with self._lock:
            if self._index is None:
                self._index = self._lees(self.index_bestand, {"fabrikanten": {}, "index": []})
            return self._index

    def ofl_fixture(self, sleutel):
        with self._lock:
            if self._fixtures is None:
                self._fixtures = self._lees(self.bestand, {})
            tekst = self._fixtures.get(sleutel)
        return json.loads(tekst) if tekst else None

    def index(self):
        ingebouwd = [{"sleutel": "ingebouwd/" + pid, "fabrikant": "Generiek", "naam": p["naam"], "soort": p["soort"],
                      "modi": [{"naam": f"{len(p['kanalen'])} kanalen", "kanalen": len(p["kanalen"])}]}
                     for pid, p in STANDAARD_PROFIELEN.items()]
        return ingebouwd + self.ofl().get("index", [])

    def info(self):
        o = self.ofl()
        return {"aantal": len(o.get("index", [])) + len(STANDAARD_PROFIELEN), "fabrikanten": len(o.get("fabrikanten", {})),
                "datum": o.get("datum", "")}

    def zoek(self, term="", soort="", limiet=80):
        woorden = [w for w in str(term).lower().split() if w]
        uit = []
        for item in self.index():
            tekst = f"{item['fabrikant']} {item['naam']} {item.get('soort', '')}".lower()
            if soort and item.get("soort") != soort:
                continue
            if all(w in tekst for w in woorden):
                uit.append(item)
        uit.sort(key=lambda i: (i["fabrikant"] != "Generiek", _natuurlijk(i["fabrikant"]), _natuurlijk(i["naam"])))
        return {"totaal": len(uit), "resultaten": uit[:limiet]}

    def profielen(self, sleutel):
        if sleutel.startswith("ingebouwd/"):
            pid = sleutel.split("/", 1)[1]
            if pid not in STANDAARD_PROFIELEN:
                raise ValueError("Onbekend profiel")
            p = schoon_profiel(STANDAARD_PROFIELEN[pid])
            p["bron"] = "ingebouwd"
            return [{"modus": f"{len(p['kanalen'])} kanalen", "profiel": p}]
        d = self.ofl_fixture(sleutel)
        if d is None:
            raise ValueError("Deze lamp staat niet in de bibliotheek")
        fabrikant = self.ofl().get("fabrikanten", {}).get(sleutel.split("/")[0], sleutel.split("/")[0])
        return [{"modus": m, "profiel": p} for m, p in ofl_naar_profielen(d, fabrikant)]
