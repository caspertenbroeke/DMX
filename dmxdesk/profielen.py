"""Profielen: wat elk DMX-kanaal van een lamp doet, en een set ingebouwde standaardprofielen."""

FUNCTIES = {
    # licht
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
    "schakelaar": "Aan/uit-schakelaar",
    # beweging
    "pan": "Pan",
    "pan_fine": "Pan fijn",
    "tilt": "Tilt",
    "tilt_fine": "Tilt fijn",
    "snelheid": "Pan/tilt-snelheid",
    # kleur- en beeldfuncties (lasers, spots, effecten): de show kan ze op de beat laten wisselen
    "kleurmacro": "Kleurprogramma / kleurwiel",
    "kleursnelheid": "Kleurloop-snelheid",
    "cto": "Kleurtemperatuur (CTO)",
    "patroon": "Patroon / gobo",
    "patroongroep": "Patroongroep",
    "patroon_draai": "Gobo/patroon draaien",
    "grootte": "Grootte / zoom",
    "zoom_auto": "Automatisch zoomen",
    "rotatie": "Draaien (rotatie)",
    "kantel_x": "Kantelen om X-as",
    "kantel_y": "Kantelen om Y-as",
    "golf": "Golf",
    "tekenen": "Geleidelijk tekenen",
    "prisma": "Prisma",
    "focus": "Focus",
    "iris": "Iris",
    "frost": "Frost",
    "programma": "Ingebouwd programma / effect",
    "programma_snelheid": "Programma-snelheid",
    "geluid": "Geluidsmodus / -gevoeligheid",
    # overig
    "smoke": "Rook",
    "reset": "Reset / onderhoud",
    "fixed": "Vaste waarde (geen functie)",
}
# functies die geen licht, kleur of positie zijn, maar een keuze uit een lijst: die kan de show laten wisselen
ATTRIBUUT_FUNCTIES = ("kleurmacro", "kleursnelheid", "cto", "patroon", "patroongroep", "patroon_draai", "grootte",
                      "zoom_auto", "rotatie", "kantel_x", "kantel_y", "golf", "tekenen", "prisma", "focus", "iris",
                      "frost", "programma", "programma_snelheid")
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


def o(van, tot, naam):
    """Eén keuze op een kanaal, zoals in de handleiding: 'van-tot: wat het doet'."""
    return {"van": van, "tot": tot, "naam": naam}


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
        kanaal("Pan/tilt snelheid", "snelheid"), kanaal("Dimmer", "dimmer"), kanaal("Strobe", "strobe", 0, 255),
        kanaal("Rood", "red"), kanaal("Groen", "green"), kanaal("Blauw", "blue"), kanaal("Wit", "white")]),
    "mh_spot_9": profiel("Moving head spot 9 kanalen (voorbeeld)", "moving", [
        kanaal("Pan", "pan"), kanaal("Tilt", "tilt"), kanaal("Pan/tilt snelheid", "snelheid"),
        kanaal("Kleurwiel", "kleurmacro", 0, opties=[
            o(0, 9, "Wit"), o(10, 19, "Rood"), o(20, 29, "Groen"), o(30, 39, "Blauw"), o(40, 49, "Geel"),
            o(50, 59, "Magenta"), o(128, 255, "Kleurwiel draaien")]),
        kanaal("Gobo", "patroon", 0, opties=[
            o(0, 7, "Open"), o(8, 15, "Gobo 1"), o(16, 23, "Gobo 2"), o(24, 31, "Gobo 3"), o(128, 255, "Gobo shake")]),
        kanaal("Strobe", "strobe", 255, 200), kanaal("Dimmer", "dimmer"),
        kanaal("Automatisch", "programma"), kanaal("Reset", "reset")]),
    "ledbar_8": profiel("LED-bar 8 segmenten RGB 24 kanalen", "bar", _bar(8)),
    "ledbar_8d": profiel("LED-bar 8 segmenten + dimmer 26 kanalen", "bar",
                         [kanaal("Dimmer", "dimmer"), kanaal("Strobe", "strobe", 0, 230)] + _bar(8)),
    "strobe_2": profiel("Strobe 2 kanalen", "strobe", [kanaal("Dimmer", "dimmer"), kanaal("Snelheid", "strobe", 0, 250)]),
    "laser_20": profiel("Laser 20 kanalen (RGB animatielaser)", "laser", [
        kanaal("Hoofdschakelaar", "schakelaar", 255, opties=[o(0, 0, "Uit"), o(1, 255, "Aan")]),
        kanaal("Rood", "red", 255, opties=[o(0, 0, "Uit"), o(1, 255, "Aan")]),
        kanaal("Groen (ook kleur van ingebouwde effecten)", "green", 255, 255,
               opties=[o(0, 0, "Uit / standaardkleur bij ingebouwde effecten"), o(1, 255, "Aan")]),
        kanaal("Blauw", "blue", 255, opties=[o(0, 0, "Uit"), o(1, 255, "Aan")]),
        kanaal("Strobe", "strobe", 0, 220, opties=[o(0, 9, "Geen strobe"), o(10, 255, "Strobe langzaam → snel")]),
        kanaal("Kleur", "kleurmacro", 45, 2, opties=[
            o(0, 34, "Vaste kleur: wit, rood, blauw, paars, cyaan, geel, groen"),
            o(35, 39, "Alle kleuren samen wisselen (snelheid kanaal 7)"),
            o(40, 44, "Beginkleur van het patroon (snelheid kanaal 7)"),
            o(45, 46, "Zeven regenboogkleuren (snelheid kanaal 7)"),
            o(47, 66, "2 kleurvlakken, 4 stappen (snelheid kanaal 7)"),
            o(67, 96, "3 kleurvlakken, 4 stappen (snelheid kanaal 7)"),
            o(97, 126, "4 kleurvlakken, 4 stappen (snelheid kanaal 7)"),
            o(127, 150, "8 kleurvlakken, 4 stappen (snelheid kanaal 7)"),
            o(151, 174, "16 kleurvlakken, 4 stappen (snelheid kanaal 7)"),
            o(175, 214, "32 kleurvlakken, 4 stappen (snelheid kanaal 7)"),
            o(215, 247, "Kleurverdeling"),
            o(248, 255, "Kleurverloop (snelheid kanaal 7)")]),
        kanaal("Kleurloop-snelheid", "kleursnelheid", 60, 0, opties=[
            o(0, 9, "Kleur loopt niet"), o(10, 127, "Vooruit, langzaam → snel"), o(128, 255, "Achteruit, langzaam → snel")]),
        kanaal("Patroon", "patroon", 0, opties=[o(0, 255, "Patroon kiezen (uit de groep van kanaal 9)")]),
        kanaal("Patroongroep", "patroongroep", 0, opties=[
            o(0, 24, "Vaste patronen groep 1 (basisvormen)"), o(25, 49, "Vaste patronen groep 2 (basisvormen)"),
            o(50, 74, "Vaste patronen groep 3 (randen)"), o(75, 99, "Vaste patronen groep 4 (uitgesneden)"),
            o(100, 124, "Gereserveerd"), o(125, 149, "Animaties 1"), o(150, 174, "Animaties 2"),
            o(175, 199, "Animaties 3 (gereserveerd)"), o(200, 224, "Animaties 4 (gereserveerd)"),
            o(225, 255, "Zelf getekend patroon (via app)")]),
        kanaal("Grootte", "grootte", 180, opties=[o(0, 255, "Grootte met de hand, klein → groot")]),
        kanaal("Automatisch zoomen", "zoom_auto", 0, opties=[
            o(0, 15, "Vaste grootte (kanaal 10)"), o(16, 55, "Klein → groot, langzaam → snel"),
            o(56, 95, "Groot → klein, langzaam → snel"), o(96, 135, "In- en uitzoomen, langzaam → snel"),
            o(136, 175, "Onregelmatig zoomen (2 punten)"), o(176, 215, "Onregelmatig zoomen (3 punten)"),
            o(216, 255, "Onregelmatig zoomen (4 punten)")]),
        kanaal("Draaien om het midden", "rotatie", 0, opties=[
            o(0, 127, "Vaste draaihoek"), o(128, 191, "Rechtsom draaien, langzaam → snel"),
            o(192, 255, "Linksom draaien, langzaam → snel")]),
        kanaal("Kantelen om X-as", "kantel_x", 0, opties=[
            o(0, 127, "Vaste stand (horizontaal gespiegeld)"), o(128, 255, "Horizontaal kantelen, langzaam → snel")]),
        kanaal("Kantelen om Y-as", "kantel_y", 0, opties=[
            o(0, 127, "Vaste stand (verticaal gespiegeld)"), o(128, 255, "Verticaal kantelen, langzaam → snel")]),
        kanaal("Pan (horizontaal)", "pan", 128),
        kanaal("Tilt (verticaal)", "tilt", 128),
        kanaal("Golf (X-richting)", "golf", 0, opties=[
            o(0, 1, "Geen golf"), o(2, 255, "Golf: klein/langzaam → groot/snel (8 stappen van 32)")]),
        kanaal("Geleidelijk tekenen", "tekenen", 0, opties=[
            o(0, 1, "Uit"), o(2, 63, "Met de hand tekenen 1"), o(64, 127, "Met de hand tekenen 2"),
            o(128, 153, "Automatisch opbouwen"), o(154, 179, "Automatisch afbouwen"),
            o(180, 205, "Op- en afbouwen (omgekeerd)"), o(206, 255, "Op- en afbouwen (gelijk)")]),
        kanaal("Ingebouwde effecten", "programma", 0, 0, opties=[
            o(0, 1, "Geen (patronen via kanaal 8 en 9)"),
            o(2, 202, "Ingebouwd effect kiezen (kleur via kanaal 3, snelheid via 20)"),
            o(203, 214, "Lijneffecten"), o(215, 224, "Animaties"), o(225, 234, "Landmark-effecten"),
            o(235, 255, "Alle effecten willekeurig")]),
        kanaal("Effectsnelheid", "programma_snelheid", 0, opties=[
            o(0, 1, "Standaardsnelheid"), o(2, 255, "Langzaam → snel")]),
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
        look("In- en uitzoomen", {"11": 115}),
        look("Linksom draaien", {"12": 220}),
        look("Kantelen", {"13": 190, "14": 190}),
        look("Tekenen", {"18": 140}),
        look("Kleurvlakken lopend", {"6": 130, "7": 90}),
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
