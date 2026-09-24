"""De effecten: welke kleur, helderheid en positie een lamp op een bepaalde beat krijgt.

Alle functies zijn 'puur': dezelfde invoer geeft dezelfde uitvoer. i/n = plek van de lamp in de rij
(links naar rechts), beat = hoeveelste beat sinds de start (met breuk), x = positie op het podium (0-100).
"""
import math
import random
import re


def clamp(v, laag, hoog):
    return max(laag, min(hoog, v))


def hex_rgb(h):
    try:
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except (ValueError, IndexError, AttributeError):
        return (255, 255, 255)


def rgb_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(clamp(round(c), 0, 255)) for c in rgb)


def hsv_rgb(h):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    q, t = 255 * (1 - f), 255 * f
    return [(255, t, 0), (q, 255, 0), (0, 255, t), (0, q, 255), (t, 0, 255), (255, 0, q)][i]


def noot_kleur(klasse):
    """Elke toon een vaste kleur. Via de kwintencirkel, zodat een stapje in de melodie een duidelijk andere kleur geeft."""
    return hsv_rgb(((klasse * 7) % 12) / 12.0)


def _stap_fase(cfg, beat):
    s = max(0.125, float(cfg.get("snelheid", 1)))
    return s, int(math.floor(beat / s)), (beat / s) % 1.0


def _overloop(fase, zacht):
    """Rustige stukken (de lichtman zet 'zacht'): het laatste deel van elke stap loopt vloeiend over in de volgende."""
    if zacht <= 0:
        return 0.0
    f = clamp((fase - (1.0 - zacht)) / zacht, 0.0, 1.0)
    return f * f * (3 - 2 * f)


# effecten die in stappen gaan (die kunnen zacht overlopen); de rest loopt al vloeiend
STAP_INTENSITEIT = {"chase", "chase_terug", "pingpong", "dubbel_chase", "om_en_om", "linksrechts", "binnenbuiten",
                    "midden_uit", "buiten_in", "vullen", "knipper", "random"}
STAP_KLEUR = {"wissel", "chase", "split", "regenboog_stap", "random"}


# ---------------------------------------------------------------- intensiteit

INTENSITEIT_MODI = [
    ("aan", "Alles aan"), ("noot_puls", "♪ Puls op melodie"), ("chase", "Chase"), ("chase_terug", "Chase terug"),
    ("pingpong", "Ping-pong"), ("dubbel_chase", "Dubbele chase"), ("om_en_om", "Om en om"),
    ("linksrechts", "Links/Rechts"), ("binnenbuiten", "Binnen/Buiten"), ("midden_uit", "Midden → buiten"),
    ("buiten_in", "Buiten → midden"), ("vullen", "Vullen"), ("golf", "Golf"), ("puls", "Puls"), ("flits", "Flits op beat"),
    ("knipper", "Knipperen"), ("ademen", "Ademen"), ("zaag_op", "Zaag omhoog"), ("zaag_neer", "Zaag omlaag"),
    ("sparkle", "Sparkle"), ("random", "Random"),
]


def intensiteit_effect(cfg, beat, i, n, x, sinds_noot=None):
    m = cfg.get("modus", "aan")
    n = max(1, n)
    zacht = float(cfg.get("zacht") or 0)
    if zacht > 0:
        hard = dict(cfg, zacht=0)
        if m in STAP_INTENSITEIT:
            s, _, fase = _stap_fase(cfg, beat)
            a = intensiteit_effect(hard, beat, i, n, x, sinds_noot)
            f = _overloop(fase, zacht)
            return a if f <= 0 else a + (intensiteit_effect(hard, beat + s, i, n, x, sinds_noot) - a) * f
        if m in ("puls", "flits", "zaag_op", "zaag_neer", "sparkle"):
            v = intensiteit_effect(hard, beat, i, n, x, sinds_noot)
            return v * (1 - zacht) + zacht * (0.45 + 0.55 * v)
    if m == "noot_puls":
        if sinds_noot is None:
            return 1.0
        rest = max(0.0, 1.0 - sinds_noot / 0.35)
        return 0.15 + 0.85 * rest * rest
    s, stap, fase = _stap_fase(cfg, beat)
    if m == "chase":
        return 1.0 if stap % n == i else 0.0
    if m == "chase_terug":
        return 1.0 if stap % n == n - 1 - i else 0.0
    if m == "pingpong":
        p = stap % max(1, 2 * n - 2)
        return 1.0 if (p if p < n else 2 * n - 2 - p) == i else 0.0
    if m == "dubbel_chase":
        return 1.0 if i in (stap % n, (stap + n // 2) % n) else 0.0
    if m == "om_en_om":
        return 1.0 if (i + stap) % 2 == 0 else 0.0
    if m == "linksrechts":
        return 1.0 if (x < 50) == (stap % 2 == 0) else 0.0
    if m == "binnenbuiten":
        return 1.0 if (abs(x - 50) < 25) == (stap % 2 == 0) else 0.0
    if m in ("midden_uit", "buiten_in"):
        helft = (n + 1) // 2
        afstand = int(abs(i - (n - 1) / 2.0))           # 0 = midden
        if m == "buiten_in":
            afstand = helft - 1 - afstand
        return 1.0 if stap % helft == afstand else 0.0
    if m == "vullen":
        return 1.0 if i < stap % (n + 1) else 0.0
    if m == "golf":
        return 0.5 + 0.5 * math.sin(2 * math.pi * (beat / (s * 4) - x / 100.0))
    if m == "puls":
        return (1.0 - fase) ** 2
    if m == "flits":
        return (1.0 - fase) ** 6
    if m == "knipper":
        return 1.0 if stap % 2 == 0 else 0.0
    if m == "ademen":
        return 0.5 - 0.5 * math.cos(2 * math.pi * beat / (s * 8))
    if m == "zaag_op":
        return fase
    if m == "zaag_neer":
        return 1.0 - fase
    if m == "sparkle":
        rnd = random.Random(stap * 7121 + i * 31)
        return (1.0 - fase) ** 3 if rnd.random() < 0.3 else 0.0
    if m == "random":
        return 1.0 if random.Random(stap * 7919 + i).random() < 0.5 else 0.0
    return 1.0


# ---------------------------------------------------------------- kleur

KLEUR_MODI = [
    ("vast", "Vast"), ("wissel", "Wissel"), ("chase", "Chase"), ("fade", "Fade"), ("verloop", "Verloop"),
    ("split", "Links/Rechts"), ("regenboog", "Regenboog"), ("regenboog_stap", "Regenboog-stappen"),
    ("random", "Random"), ("melodie", "♪ Melodie"),
]


def kleur_effect(cfg, beat, i, n, noten=(), x=50.0):
    m = cfg.get("modus", "vast")
    zacht = float(cfg.get("zacht") or 0)
    if zacht > 0 and m in STAP_KLEUR:
        hard = dict(cfg, zacht=0)
        s, _, fase = _stap_fase(cfg, beat)
        a = kleur_effect(hard, beat, i, n, noten, x)
        f = _overloop(fase, zacht)
        if f <= 0:
            return a
        b = kleur_effect(hard, beat + s, i, n, noten, x)
        return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))
    palet = [hex_rgb(c) for c in (cfg.get("palet") or ["#ffffff"])]
    n = max(1, n)
    s, stap, _ = _stap_fase(cfg, beat)
    spreid = clamp(float(cfg.get("spreiding", 0)), 0, 100) / 100.0
    verschuiving = int(round(spreid * i))  # bij spreiding 100 heeft elke lamp een eigen stap
    if m == "melodie":
        if not noten:                       # geen melodie te horen: rustig door de regenboog
            return hsv_rgb((beat / 64.0 + spreid * i / n) % 1.0)
        # spreiding: lamp 1 = huidige noot, lamp 2 = de noot daarvoor, ... (melodie loopt over de lampen)
        return noot_kleur(noten[-1 - min(len(noten) - 1, verschuiving)])
    if m == "wissel":
        return palet[(stap + verschuiving) % len(palet)]
    if m == "chase":
        return palet[(stap + i) % len(palet)]
    if m == "split":
        return palet[(stap + (0 if x < 50 else 1)) % len(palet)]
    if m == "regenboog":
        return hsv_rgb((beat / (s * 16) + spreid * i / n) % 1.0)
    if m == "regenboog_stap":
        return hsv_rgb((stap * 0.137 + spreid * i / n) % 1.0)
    if m in ("fade", "verloop"):
        if m == "fade":
            p = (beat / (s * 4) + spreid * i / n * len(palet)) % len(palet)
        else:                               # vaste kleurovergang van links naar rechts over het palet
            p = (i / max(1, n - 1)) * (len(palet) - 1) if len(palet) > 1 else 0.0
        a, b, f = palet[int(p) % len(palet)], palet[(int(p) + 1) % len(palet)], p % 1.0
        return tuple(a[k] + (b[k] - a[k]) * f for k in range(3))
    if m == "random":
        rnd = random.Random(stap * 104729 + i)
        return palet[rnd.randrange(len(palet))] if len(palet) > 1 else hsv_rgb(rnd.random())
    return palet[0]


# ---------------------------------------------------------------- beweging

BEWEGING_MODI = [
    ("stil", "Stil"), ("cirkel", "Cirkel"), ("acht", "Acht"), ("opneer", "Op/Neer"), ("linksrechts", "Links/Rechts"),
    ("zwaai", "Zwaai"), ("vierkant", "Vierkant"), ("driehoek", "Driehoek"), ("spiraal", "Spiraal"),
    ("bloem", "Bloem"), ("ballyhoo", "Ballyhoo"), ("knik", "Knik"), ("random", "Random"),
]


def _veelhoek(t, punten):
    """Punt op de omtrek van een veelhoek, t = 0..1."""
    t = (t % 1.0) * len(punten)
    k = int(t)
    a, b, f = punten[k % len(punten)], punten[(k + 1) % len(punten)], t - k
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


VIERKANT = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
DRIEHOEK = [(0, -1), (0.87, 0.5), (-0.87, 0.5)]


def beweging_effect(cfg, fase, i, n):
    """fase = aantal afgelegde rondes (wordt per frame opgeteld, zodat een snelheidswissel geen sprong geeft)."""
    m = cfg.get("modus", "stil")
    n = max(1, n)
    g = clamp(float(cfg.get("grootte", 50)), 0, 100) / 200.0
    cp = clamp(float(cfg.get("pan", 50)), 0, 100) / 100.0
    ct = clamp(float(cfg.get("tilt", 50)), 0, 100) / 100.0
    spreid = clamp(float(cfg.get("spreiding", 0)), 0, 100) / 100.0 * i / n
    r = fase + spreid                           # rondes, met verschuiving per lamp
    f = 2 * math.pi * r
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
    elif m == "vierkant":
        dp, dt = (g * v for v in _veelhoek(r, VIERKANT))
    elif m == "driehoek":
        dp, dt = (g * v for v in _veelhoek(r, DRIEHOEK))
    elif m == "spiraal":
        straal = g * (0.55 + 0.45 * math.sin(f / 4.0))
        dp, dt = straal * math.cos(f), straal * math.sin(f)
    elif m == "bloem":
        straal = g * math.cos(3 * f / 2.0)
        dp, dt = straal * math.cos(f / 2.0), straal * math.sin(f / 2.0)
    elif m == "ballyhoo":
        dp, dt = g * 1.6 * math.sin(f), g * (0.3 + 0.7 * abs(math.sin(1.5 * f)))
    elif m == "knik":
        dt = g * (1.0 - 2.0 * (1.0 - (r % 1.0)) ** 3)
    elif m == "random":
        k = math.floor(r)
        zaad = int(i * 7 if spreid else 0)

        def punt(j):
            rnd = random.Random(j * 15485863 + zaad)
            return rnd.uniform(-1, 1), rnd.uniform(-1, 1)

        a, b = punt(k), punt(k + 1)
        w = 0.5 - 0.5 * math.cos(math.pi * (r - k))
        dp, dt = g * (a[0] + (b[0] - a[0]) * w), g * (a[1] + (b[1] - a[1]) * w)
    return clamp(cp + dp, 0.0, 1.0), clamp(ct + dt, 0.0, 1.0)


# ---------------------------------------------------------------- patronen, kleurprogramma's, rotatie, … (lasers, spots)

ATTRIBUUT_MODI = [("uit", "Uit (vaste stand)"), ("wissel", "Wissel op de beat"), ("random", "Willekeurig op de beat"),
                  ("energie", "Volgt de energie")]
_NIET_BRUIKBAAR = re.compile(r"^(geen|uit\b|no function|nothing|reserved|gereserveerd|onderhoud|reset)|gereserveerd|reserved",
                             re.IGNORECASE)


def bruikbare_opties(kanaal):
    """Keuzes van een kanaal waar de show mee kan wisselen (dus niet 'geen functie' of 'gereserveerd')."""
    return [o for o in (kanaal.get("opties") or []) if not _NIET_BRUIKBAAR.search(str(o.get("naam", "")).strip())]


def attribuut_keuzes(kanaal, namen=None):
    """Waarden waartussen gewisseld wordt. Eén doorlopend bereik (bijv. 'patroon 0-255') wordt 8 stappen."""
    opties = bruikbare_opties(kanaal)
    if namen:
        gekozen = [o for o in opties if o.get("naam") in namen]
        opties = gekozen or opties
    if len(opties) >= 2:
        return [int(round((o["van"] + o["tot"]) / 2.0)) for o in opties]
    van, tot = (opties[0]["van"], opties[0]["tot"]) if opties else (0, 255)
    return [int(round(van + (tot - van) * (k + 0.5) / 8.0)) for k in range(8)]


def attribuut_effect(cfg, kanaal, beat, nr, energie=None):
    """Waarde voor een kanaal als patroon, kleurprogramma of rotatie, of None als het effect uit staat."""
    m = cfg.get("modus", "uit")
    if m == "uit":
        return None
    keuzes = attribuut_keuzes(kanaal, cfg.get("keuzes"))
    elke = max(0.25, float(cfg.get("elke", 4) or 4))
    stap = int(math.floor(beat / elke))
    if m == "wissel":
        return keuzes[stap % len(keuzes)]
    if m == "random":
        return random.Random(stap * 7919 + nr * 104729).choice(keuzes)
    if m == "energie":
        e = 0.5 if energie is None else clamp(float(energie), 0.0, 1.0)
        opties = bruikbare_opties(kanaal)
        if len(keuzes) > 1 and len(opties) > 1:
            return keuzes[min(len(keuzes) - 1, int(e * len(keuzes)))]
        van, tot = (opties[0]["van"], opties[0]["tot"]) if opties else (0, 255)
        return int(round(van + (tot - van) * e))
    return None
