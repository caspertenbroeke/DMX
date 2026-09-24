"""De lichtman: hoort waar het nummer is en stuurt de show zoals een lichtman achter de tafel dat zou doen.

Uit de analyse komt elke ~0,1 s een meting, met het moment waarop dat stukje te HOREN is. Door de voorsprong
(Spotify-speaker, Pi) komen die metingen seconden vooruit binnen: de lichtman weet dus wat er aankomt.

  kick   0..1  pompt de bas op de beat (dance, hardstyle) of niet (rustig nummer, opbouw, breakdown)
  e      0..1  energie: kick, drukte, helderheid en luidheid samen
  drops  momenten waarop de kick terugkomt na een stuk zonder kick

Secties (wat de lichtman ervan maakt):
  rustig  geen kick, en het nummer is rustig             zachte overgangen, langzaam, gedimd
  break   geen kick, maar eerder in het nummer wel       rustig, klaar voor de volgende klap
  opbouw  geen kick en de drop komt eraan                steeds sneller op de maat, feller, naar wit, vlak voor
                                                         de drop even donker
  groove  kick, niet heel hard                           op de maat maar niet op elke tel
  drop    kick en veel energie                           alles op de beat, punch op elke kick, snel en groot

BPM alleen zegt dus weinig: een rustig nummer op 150 BPM blijft rustig, hardstyle op 150 BPM gaat los.
"""
from collections import deque

SECTIES = {"rustig": "Rustig", "break": "Break", "opbouw": "Opbouw", "groove": "Groove", "drop": "Vol gas"}

# Per sectie: stap = effecten x zoveel trager (kleur apart), zacht = stappen in elkaar laten overlopen,
# dim = helderheid, bew_snel/bew_groot = beweging trager en kleiner, punch = helderheid knalt op elke kick,
# adem = langzame golf over de lampen (rustige stukken staan dan niet stil)
PROFIEL = {
    "rustig": dict(stap=4.0, kleur_stap=8.0, zacht=1.0, dim=0.45, bew_snel=3.0, bew_groot=0.45, punch=0.0, adem=0.35),
    "break": dict(stap=4.0, kleur_stap=8.0, zacht=1.0, dim=0.55, bew_snel=2.5, bew_groot=0.55, punch=0.0, adem=0.3),
    "groove": dict(stap=2.0, kleur_stap=4.0, zacht=0.3, dim=0.85, bew_snel=1.4, bew_groot=0.8, punch=0.3, adem=0.0),
    "drop": dict(stap=1.0, kleur_stap=1.0, zacht=0.0, dim=1.0, bew_snel=0.7, bew_groot=1.0, punch=0.65, adem=0.0),
}
NEUTRAAL = dict(stap=1.0, kleur_stap=1.0, zacht=0.0, dim=1.0, bew_snel=1.0, bew_groot=1.0, punch=0.0, adem=0.0)

KICK_AAN, KICK_UIT = 0.55, 0.30
OPBOUW_LANG = 16.0       # s: zo lang voor een (bekende) drop mag de opbouw al beginnen
NA_DROP = 8.0            # s: zo lang na een drop blijft het sowieso vol gas
FLITS = 0.45             # s: witte flits op het moment van de drop
GAT = 0.3                # s: vlak voor de drop even donker


def _clamp(v, laag=0.0, hoog=1.0):
    return max(laag, min(hoog, v))


def profiel(sectie, opbouw=None, contrast=0.7, extreem=False):
    """Hoe de show zich nu gedraagt. contrast 0 = de lichtman doet bijna niets, 1 = maximaal verschil."""
    if sectie == "opbouw":
        p = opbouw or 0.0
        a, b = PROFIEL["break"], PROFIEL["drop"]
        doel = {k: a[k] + (b[k] - a[k]) * p for k in a}
        doel.update(stap=4.0 * (1 - p) + 1.0 * p, kleur_stap=8.0 * (1 - p) + 2.0 * p, zacht=1.0 - p, punch=0.0,
                    adem=0.0)
    else:
        doel = dict(PROFIEL.get(sectie, NEUTRAAL))
        if sectie == "drop" and extreem:
            doel.update(stap=0.5, punch=0.8)
    c = _clamp(contrast)
    uit = {k: NEUTRAAL[k] + (doel[k] - NEUTRAAL[k]) * c for k in NEUTRAAL}
    # drop met weinig contrast: wat punch houden (anders voelt het vlak)
    if sectie == "drop":
        uit["punch"] = max(uit["punch"], 0.25)
    return uit


class Lichtman:
    def __init__(self):
        self.punten = deque(maxlen=1800)   # (t, kick, e): ~3 minuten
        self.drops = deque(maxlen=32)
        self.sectie = None
        self.sinds = 0.0
        self.laatste_kick = -1e9           # laatste moment met kick (voor break vs. rustig)
        self.geen_kick_sinds = None
        self.opbouw_van = None
        self.opbouw_drop = None
        self.opbouw_p = 0.0                # hoe ver de opbouw nu is (gaat alleen omhoog)
        self.stijgt = False
        self._t, self._basis = None, None

    # ------------------------------------------------------------ invoer
    def punt(self, t, kick, e):
        """t = wanneer dit te horen is (kick al teruggerekend naar het midden van zijn meetvenster)."""
        if self.punten and t < self.punten[-1][0] - 1.5:
            self.vergeet_vanaf(t)          # analyse opnieuw begonnen (ander nummer): oude toekomst weg
        self.punten.append((float(t), float(kick), float(e)))

    def drop(self, t):
        t = float(t)
        if not any(abs(t - d) < 2.0 for d in self.drops):
            self.drops.append(t)

    def vergeet_vanaf(self, t):
        """Alles vanaf t geldt niet meer (bijv. volgend nummer gekozen): weg met die metingen en drops."""
        while self.punten and self.punten[-1][0] >= t:
            self.punten.pop()
        for d in [d for d in self.drops if d >= t]:
            self.drops.remove(d)
        self._t = None

    def tempo_vasthouden(self, t):
        """In een dansnummer zonder kick (break, opbouw) het tempo niet aanpassen: een snelle snare-roffel of
        een pianostuk is geen nieuw tempo. Een lichtman houdt dan gewoon de maat vast."""
        kick, _ = self._gemiddeld(t - 1.8, t + 0.6)     # (de kick-meting van precies nu komt iets later binnen)
        if kick is None or kick >= KICK_UIT:
            return False
        return any(kk >= KICK_AAN and t - 120.0 <= tt <= t for tt, kk, _ in self.punten)   # dansnummer?

    def verschuif(self, van, duur):
        """Pauze van `duur` s vanaf `van`: alles wat daarna zou klinken, klinkt nu zoveel later."""
        self.punten = deque(((t + duur if t >= van else t), k, e) for t, k, e in self.punten)
        self.punten = deque(sorted(self.punten), maxlen=1800)
        self.drops = deque((d + duur if d >= van else d for d in self.drops), maxlen=32)
        if self.opbouw_van is not None and self.opbouw_van >= van:
            self.opbouw_van += duur
        if self.opbouw_drop is not None and self.opbouw_drop >= van:
            self.opbouw_drop += duur
        if self.geen_kick_sinds is not None:
            self.geen_kick_sinds += duur
        self.laatste_kick += duur
        self._t = None

    # ------------------------------------------------------------ hulp
    def _gemiddeld(self, van, tot):
        k = e = 0.0
        n = 0
        for t, kk, ee in reversed(self.punten):
            if t < van:
                break
            if t <= tot:
                k, e, n = k + kk, e + ee, n + 1
        return (k / n, e / n) if n else (None, None)

    def _volgende_drop(self, nu):
        kandidaten = [d for d in self.drops if d > nu - 0.05]
        return min(kandidaten) if kandidaten else None

    def _laatste_drop(self, nu):
        gehad = [d for d in self.drops if d <= nu]
        return max(gehad) if gehad else None

    # ------------------------------------------------------------ de beslissing
    def _beslis(self, nu):
        # met voorsprong liggen er ook metingen van straks klaar: dan rond 'nu' middelen (geen vertraging)
        # (maar niet over een drop heen kijken: die kicks horen pas ná het moment van de drop)
        volgende = self._volgende_drop(nu)
        vooruit = bool(self.punten) and self.punten[-1][0] >= nu + 0.6
        tot = nu + 0.6 if vooruit else nu
        if volgende is not None and volgende > nu:
            tot = min(tot, max(nu, volgende - 0.1))
        kick, e = self._gemiddeld(tot - 1.2, tot)
        if kick is None:
            laatste = self.punten[-1] if self.punten else None
            if laatste is None or nu - laatste[0] > 4.0 or laatste[0] > nu:
                return None                 # hoort (nu) niets
            kick, e = laatste[1], laatste[2]
        in_kick = self.sectie in ("groove", "drop")
        heeft_kick = kick >= (KICK_UIT if in_kick else KICK_AAN)
        if heeft_kick:
            self.laatste_kick, self.geen_kick_sinds = nu, None
        elif self.geen_kick_sinds is None:
            self.geen_kick_sinds = nu
        niveau = _clamp(0.55 * kick + 0.45 * e)
        vorige = self._laatste_drop(nu)
        opbouw = None
        if vorige is not None and 0 <= nu - vorige < NA_DROP:
            sectie = "drop"                 # net gedropt: vol gas, ook als de kick-meting nog moet volgen
            self.laatste_kick = nu
        elif heeft_kick:
            vol = niveau >= (0.60 if self.sectie == "drop" else 0.68)
            sectie = "drop" if vol else "groove"
        elif volgende is not None and volgende > nu:
            if self.opbouw_drop != volgende:
                # de drop is net in zicht: vanaf waar de opbouw nu is soepel naar 1 op het moment van de drop
                p0 = self.opbouw_p if self.sectie == "opbouw" else 0.0
                if p0 <= 0.0 and self.geen_kick_sinds is not None:
                    # al lang geen kick: begin (hooguit OPBOUW_LANG voor de drop) bij het begin van dit stuk
                    self.opbouw_van = max(self.geen_kick_sinds, volgende - OPBOUW_LANG, nu - 0.5 * (volgende - nu))
                else:
                    self.opbouw_van = nu - p0 / max(0.01, 1.0 - p0) * (volgende - nu)
                self.opbouw_drop = volgende
            sectie = "opbouw"
            opbouw = _clamp((nu - self.opbouw_van) / max(0.5, volgende - self.opbouw_van))
        else:
            stijging = self._stijging(nu)
            lang_stil = self.geen_kick_sinds is not None and nu - self.geen_kick_sinds > 3.0
            dans = nu - self.laatste_kick < 120.0     # opbouw hoort bij dansmuziek: na een stuk met kick
            if stijging is not None and lang_stil and e > 0.25:
                self.stijgt = stijging > (0.05 if self.stijgt else (0.15 if dans else 0.28))
            else:
                self.stijgt = False
            if self.stijgt:
                sectie = "opbouw"
                opbouw = max(self.opbouw_p if self.sectie == "opbouw" else 0.0,
                             _clamp((stijging - 0.05) / 0.35, 0.0, 0.5))
            else:
                sectie = "break" if nu - self.laatste_kick < 120.0 else "rustig"
        self.opbouw_p = opbouw if sectie == "opbouw" else 0.0
        if sectie != self.sectie:
            self.sectie, self.sinds = sectie, nu
        return {"sectie": sectie, "kick": round(kick, 2), "e": round(e, 2), "niveau": round(niveau, 2),
                "opbouw": opbouw, "drop_t": volgende if volgende is not None and volgende > nu else None,
                "extreem": sectie == "drop" and kick > 0.9 and e > 0.75}

    def _stijging(self, nu):
        """Hoeveel de energie de laatste ~6 s gestegen is (opbouw zonder dat de drop al te zien is)."""
        _, nu_e = self._gemiddeld(nu - 1.5, nu)
        _, toen = self._gemiddeld(nu - 7.0, nu - 5.0)
        if nu_e is None or toen is None:
            return None
        return nu_e - toen

    def stand(self, nu, contrast=0.7):
        """Wat de show nu moet doen. None = geen muziek gehoord (dan doet de show gewoon wat is ingesteld)."""
        if self._t is None or not (0 <= nu - self._t < 0.1):
            self._basis, self._t = self._beslis(nu), nu
        b = self._basis
        if b is None:
            return None
        st = dict(b)
        if st["sectie"] == "opbouw" and st["drop_t"] is not None and self.opbouw_van is not None:
            st["opbouw"] = _clamp((nu - self.opbouw_van) / max(0.5, st["drop_t"] - self.opbouw_van))
            self.opbouw_p = st["opbouw"]
        vorige = self._laatste_drop(nu)
        st["flits"] = vorige is not None and 0 <= nu - vorige < FLITS
        st["gat"] = st["drop_t"] is not None and 0 < st["drop_t"] - nu < GAT
        st["profiel"] = profiel(st["sectie"], st["opbouw"], contrast, st["extreem"])
        return st
