"""Profielen: wat elk DMX-kanaal van een lamp doet, en een set ingebouwde standaardprofielen."""

FUNCTIES = {
    "dimmer": "Dimmer / intensiteit",
    "dimmer_fine": "Dimmer fijn",
    "red": "Rood",
    "green": "Groen",
    "blue": "Blauw",
    "white": "Wit",
    "amber": "Amber",
    "uv": "UV",
    "cyan": "Cyaan (CMY)",
    "magenta": "Magenta (CMY)",
    "yellow": "Geel (CMY)",
    "strobe": "Strobe / shutter",
    "pan": "Pan",
    "pan_fine": "Pan fijn",
    "tilt": "Tilt",
    "tilt_fine": "Tilt fijn",
    "schakelaar": "Aan/uit-schakelaar",
    "smoke": "Rook",
    "fixed": "Vaste waarde",
}
KLEURFUNCTIES = ("red", "green", "blue", "white", "amber", "uv", "cyan", "magenta", "yellow")
SOORTEN = {
    "par": "Par / wash", "moving": "Moving head", "bar": "LED-bar / pixels", "laser": "Laser",
    "strobe": "Strobe", "rook": "Rook / hazer", "dimmer": "Dimmer", "overig": "Overig",
}
MAX_KANALEN = 512


def kanaal(naam, functie, standaard=0, strobe=None, rook=None, kop=0, opties=None):
    k = {"naam": naam, "functie": functie, "standaard": standaard, "strobe": strobe, "rook": rook, "kop": kop}
    if opties:
        k["opties"] = opties
    return k


def look(naam, waarden):
    return {"naam": naam, "waarden": waarden}


def profiel(naam, soort, kanalen, looks=None, fabrikant="Generiek"):
    return {"naam": naam, "fabrikant": fabrikant, "soort": soort, "kanalen": kanalen, "looks": looks or [],
            "bron": "ingebouwd"}


def _bar(segmenten, kleuren=("red", "green", "blue")):
    namen = {"red": "Rood", "green": "Groen", "blue": "Blauw", "white": "Wit"}
    return [kanaal(f"{namen[c]} {s + 1}", c, kop=s + 1) for s in range(segmenten) for c in kleuren]


STANDAARD_PROFIELEN = {
    "dimmer_1": profiel("Dimmer 1 kanaal", "dimmer", [kanaal("Dimmer", "dimmer")]),
    "rgb_3": profiel("RGB 3 kanalen", "par", [kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue")]),
    "drgb_4": profiel("Dimmer + RGB 4 kanalen", "par", [
        kanaal("Dimmer", "dimmer"), kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue")]),
    "rgbw_4": profiel("RGBW 4 kanalen", "par", [
        kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue"), kanaal("Wit", "white")]),
    "drgbws_6": profiel("Dimmer + RGBW + strobe 6 kanalen", "par", [
        kanaal("Dimmer", "dimmer"), kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue"),
        kanaal("Wit", "white"), kanaal("Strobe", "strobe", 0, 230)]),
    "rgbwau_6": profiel("RGBWA+UV 6 kanalen", "par", [
        kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue"), kanaal("Wit", "white"),
        kanaal("Amber", "amber"), kanaal("UV", "uv")]),
    "drgbwaus_8": profiel("Dimmer + RGBWA+UV + strobe 8 kanalen", "par", [
        kanaal("Dimmer", "dimmer"), kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue"),
        kanaal("Wit", "white"), kanaal("Amber", "amber"), kanaal("UV", "uv"), kanaal("Strobe", "strobe", 0, 230)]),
    "par_oud": profiel("RGB Par 7 kanalen", "par", [
        kanaal("Dimmer", "dimmer"), kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue"),
        kanaal("Kanaal 5", "fixed"), kanaal("Kanaal 6", "fixed"), kanaal("Kanaal 7", "fixed")]),
    "mh_11": profiel("Moving head wash 11 kanalen", "moving", [
        kanaal("Pan", "pan"), kanaal("Pan fijn", "pan_fine"), kanaal("Tilt", "tilt"), kanaal("Tilt fijn", "tilt_fine"),
        kanaal("Pan/tilt snelheid", "fixed"), kanaal("Dimmer", "dimmer"), kanaal("Strobe", "strobe", 0, 255),
        kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue"), kanaal("Wit", "white")]),
    "mh_spot_9": profiel("Moving head spot 9 kanalen (voorbeeld)", "moving", [
        kanaal("Pan", "pan"), kanaal("Tilt", "tilt"), kanaal("Pan/tilt snelheid", "fixed"),
        kanaal("Kleurwiel", "fixed", 0, opties=[
            {"van": 0, "tot": 9, "naam": "Wit"}, {"van": 10, "tot": 19, "naam": "Rood"},
            {"van": 20, "tot": 29, "naam": "Groen"}, {"van": 30, "tot": 39, "naam": "Blauw"},
            {"van": 40, "tot": 49, "naam": "Geel"}, {"van": 50, "tot": 59, "naam": "Magenta"},
            {"van": 128, "tot": 255, "naam": "Kleurwiel draaien"}]),
        kanaal("Gobo", "fixed", 0, opties=[
            {"van": 0, "tot": 7, "naam": "Open"}, {"van": 8, "tot": 15, "naam": "Gobo 1"},
            {"van": 16, "tot": 23, "naam": "Gobo 2"}, {"van": 24, "tot": 31, "naam": "Gobo 3"},
            {"van": 128, "tot": 255, "naam": "Gobo shake"}]),
        kanaal("Strobe", "strobe", 255, 200), kanaal("Dimmer", "dimmer"),
        kanaal("Automatisch", "fixed"), kanaal("Reset", "fixed")]),
    "ledbar_8": profiel("LED-bar 8 segmenten RGB 24 kanalen", "bar", _bar(8)),
    "ledbar_8d": profiel("LED-bar 8 segmenten + dimmer 26 kanalen", "bar",
                         [kanaal("Dimmer", "dimmer"), kanaal("Strobe", "strobe", 0, 230)] + _bar(8)),
    "strobe_2": profiel("Strobe 2 kanalen", "strobe", [kanaal("Dimmer", "dimmer"), kanaal("Snelheid", "strobe", 0, 250)]),
    "laser_20": profiel("Laser 20 kanalen", "laser", [
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
    ], looks=[
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
    ]),
    "rook_1": profiel("Rookmachine 1 kanaal", "rook", [kanaal("Rook", "smoke", 0, None, 255)]),
    "hazer_2": profiel("Hazer 2 kanalen", "rook", [kanaal("Haze", "smoke", 0, None, 255), kanaal("Ventilator", "fixed", 128)]),
}


# ---------------------------------------------------------------- controleren en opschonen

def byte(v):
    return int(max(0, min(255, round(float(v)))))


def _optioneel(v):
    return None if v in (None, "") else byte(v)


def schoon_kanaal(k):
    fn = k.get("functie") if k.get("functie") in FUNCTIES else "fixed"
    try:
        kop = max(0, min(128, int(k.get("kop") or 0)))
    except (TypeError, ValueError):
        kop = 0
    opties = []
    for o in (k.get("opties") or [])[:64]:
        try:
            opties.append({"van": byte(o["van"]), "tot": byte(o["tot"]), "naam": str(o.get("naam", ""))[:50]})
        except (KeyError, TypeError, ValueError):
            continue
    return kanaal(str(k.get("naam", ""))[:50], fn, byte(k.get("standaard") or 0),
                  _optioneel(k.get("strobe")), _optioneel(k.get("rook")), kop, opties or None)


def schoon_profiel(p, standaard_naam="Profiel"):
    kanalen = [schoon_kanaal(k) for k in (p.get("kanalen") or [])[:MAX_KANALEN]]
    looks = []
    for lk in (p.get("looks") or [])[:64]:
        waarden = {}
        for c, v in (lk.get("waarden") or {}).items():
            try:
                if 1 <= int(c) <= len(kanalen):
                    waarden[str(int(c))] = byte(v)
            except (TypeError, ValueError):
                continue
        looks.append(look(str(lk.get("naam", ""))[:40] or "Look", waarden))
    soort = p.get("soort") if p.get("soort") in SOORTEN else raad_soort(kanalen)
    return {
        "naam": str(p.get("naam") or standaard_naam)[:80],
        "fabrikant": str(p.get("fabrikant") or "")[:60],
        "soort": soort,
        "kanalen": kanalen,
        "looks": looks,
        "bron": str(p.get("bron") or "eigen")[:20],
    }


def raad_soort(kanalen):
    fn = {k.get("functie") for k in kanalen}
    if {"pan", "tilt"} & fn:
        return "moving"
    if "smoke" in fn:
        return "rook"
    if any((k.get("kop") or 0) > 0 for k in kanalen):
        return "bar"
    if fn & set(KLEURFUNCTIES):
        return "par"
    if fn == {"dimmer"}:
        return "dimmer"
    if "strobe" in fn and "dimmer" in fn and len(kanalen) <= 3:
        return "strobe"
    return "overig"


def koppen(prof):
    """Nummers van de losse cellen (segmenten/pixels) van een lamp. Leeg = de lamp is één geheel."""
    return sorted({int(k.get("kop") or 0) for k in prof.get("kanalen", [])} - {0})
