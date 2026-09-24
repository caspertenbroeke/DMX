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

SECTIES = {"rustig": "Rustig", "break": "Break", "opbouw": "Opbouw", "groove": "Groove", "druk": "Druk",
           "drop": "Vol gas", "extreem": "Extreem!"}
KICK_NIVEAUS = ("groove", "druk", "drop", "extreem")      # stukken met kick, van rustig naar wild

# Per sectie: stap = effecten x zoveel trager (kleur apart), zacht = stappen in elkaar laten overlopen,
# dim = helderheid, bew_snel/bew_groot = beweging trager en kleiner, punch = helderheid knalt op elke kick,
# adem = langzame golf over de lampen (rustige stukken staan dan niet stil)
PROFIEL = {
    "rustig": dict(stap=4.0, kleur_stap=8.0, zacht=1.0, dim=0.45, bew_snel=3.0, bew_groot=0.45, punch=0.0, adem=0.35),
    "break": dict(stap=4.0, kleur_stap=8.0, zacht=1.0, dim=0.55, bew_snel=2.5, bew_groot=0.55, punch=0.0, adem=0.3),
    "groove": dict(stap=2.0, kleur_stap=4.0, zacht=0.3, dim=0.85, bew_snel=1.4, bew_groot=0.8, punch=0.3, adem=0.0),
    "druk": dict(stap=1.0, kleur_stap=2.0, zacht=0.1, dim=0.92, bew_snel=1.0, bew_groot=0.9, punch=0.45, adem=0.0),
    "drop": dict(stap=1.0, kleur_stap=1.0, zacht=0.0, dim=1.0, bew_snel=0.7, bew_groot=1.0, punch=0.65, adem=0.0),
    "extreem": dict(stap=0.5, kleur_stap=1.0, zacht=0.0, dim=1.0, bew_snel=0.5, bew_groot=1.0, punch=0.8, adem=0.0),
}
# drempels (score 0..1: hoe hard en vol het nu is t.o.v. het nummer, plus hoe druk/fel) voor groove → druk → vol gas
# → extreem. De schuif 'wildheid' schuift ze op: lager = pas later vol gas.
DREMPELS = (0.42, 0.60, 0.78)
TERUG = 0.07             # zoveel moet de score onder de drempel zakken voor een stap terug
BLIJF = 3.0              # s: minstens zo lang op een niveau (geen heen-en-weer)
NEUTRAAL = dict(stap=1.0, kleur_stap=1.0, zacht=0.0, dim=1.0, bew_snel=1.0, bew_groot=1.0, punch=0.0, adem=0.0)

KICK_AAN, KICK_UIT = 0.55, 0.30
OPBOUW_LANG = 16.0       # s: zo lang voor een (bekende) drop mag de opbouw al beginnen
NA_DROP = 8.0            # s: zo lang na een drop blijft het sowieso vol gas
FLITS = 0.45             # s: witte flits op het moment van de drop
GAT = 0.3                # s: vlak voor de drop even donker


def _clamp(v, laag=0.0, hoog=1.0):
    return max(laag, min(hoog, v))


def profiel(sectie, opbouw=None, contrast=0.7, extreem=False):
    """Hoe de show zich nu gedraagt. contrast 0 = de lichtman doet bijna niets, 1 = maximaal verschil.
    (extreem: oude aanroep, nu een eigen sectie)"""
    if sectie == "opbouw":
        p = opbouw or 0.0
        a, b = PROFIEL["break"], PROFIEL["drop"]
        doel = {k: a[k] + (b[k] - a[k]) * p for k in a}
        doel.update(stap=4.0 * (1 - p) + 1.0 * p, kleur_stap=8.0 * (1 - p) + 2.0 * p, zacht=1.0 - p, punch=0.0,
                    adem=0.0)
    else:
        doel = dict(PROFIEL.get("extreem" if (sectie == "drop" and extreem) else sectie, NEUTRAAL))
    c = _clamp(contrast)
    uit = {k: NEUTRAAL[k] + (doel[k] - NEUTRAAL[k]) * c for k in NEUTRAAL}
    # drop met weinig contrast: wat punch houden (anders voelt het vlak)
    if sectie in ("drop", "extreem"):
        uit["punch"] = max(uit["punch"], 0.25)
    return uit


class Lichtman:
    def __init__(self):
        self.punten = deque(maxlen=1800)   # (t, kick, e, rel, abs): ~3 minuten
        self.drops = deque(maxlen=32)
        self.sectie = None
        self.sinds = 0.0
        self.laatste_kick = -1e9           # laatste moment met kick (voor break vs. rustig)
        self.geen_kick_sinds = None
        self.opbouw_van = None
        self.opbouw_drop = None
        self.opbouw_p = 0.0                # hoe ver de opbouw nu is (gaat alleen omhoog)
        self.stijgt = False
        self.nummer_start = -1e9           # begin van het huidige nummer (drops tellen, 'hard' bepalen)
        self._t, self._basis = None, None

    # ------------------------------------------------------------ invoer
    def punt(self, t, kick, e, rel=None, abs_=None):
        """t = wanneer dit te horen is (kick al teruggerekend naar het midden van zijn meetvenster).
        rel = hoe hard t.o.v. de laatste 30 s (0..1), abs_ = hoe druk en fel (0..1)."""
        if self.punten and t < self.punten[-1][0] - 1.5:
            self.vergeet_vanaf(t)          # analyse opnieuw begonnen (ander nummer): oude toekomst weg
        if not self.punten or t - self.punten[-1][0] > 4.0:
            self.nummer_start = t          # na een stilte: een nieuw nummer
        self.punten.append((float(t), float(kick), float(e), float(e if rel is None else rel),
                            float(e if abs_ is None else abs_)))

    def nieuw_nummer(self, t):
        """Een ander nummer begint te klinken (drops tellen weer vanaf 1)."""
        self.nummer_start = t
        self._t = None

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
        return any(p[1] >= KICK_AAN and t - 120.0 <= p[0] <= t for p in self.punten)   # dansnummer?

    def verschuif(self, van, duur):
        """Pauze van `duur` s vanaf `van`: alles wat daarna zou klinken, klinkt nu zoveel later."""
        self.punten = deque(sorted(((p[0] + duur if p[0] >= van else p[0]),) + tuple(p[1:]) for p in self.punten),
                            maxlen=1800)
        if self.nummer_start >= van:
            self.nummer_start += duur
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
    def _gemiddeld(self, van, tot, met_score=False):
        k = e = sc = 0.0
        n = 0
        for p in reversed(self.punten):
            if p[0] < van:
                break
            if p[0] <= tot:
                k, e, sc, n = k + p[1], e + p[2], sc + 0.4 * p[3] + 0.6 * p[4], n + 1
        if met_score:
            return (k / n, e / n, sc / n) if n else (None, None, None)
        return (k / n, e / n) if n else (None, None)

    def _hard(self, nu):
        """Is dit nummer hard (hardstyle, hardcore)? Drukte en felheid in de stukken met kick."""
        waarden = sorted(p[4] for p in self.punten
                         if p[1] >= KICK_AAN and max(self.nummer_start, nu - 120.0) <= p[0] <= nu)
        return len(waarden) >= 20 and waarden[len(waarden) // 2] >= 0.6

    def drops_in_nummer(self, nu):
        return sum(1 for d in self.drops if self.nummer_start <= d <= nu)

    def _kick_niveau(self, score, nu, wild, hard):
        """Groove / druk / vol gas / extreem, met drempels die de wildheid opschuift en wat vertraging."""
        schuif = (0.6 - wild) * 0.35
        drempels = [d + schuif for d in DREMPELS]
        huidig = KICK_NIVEAUS.index(self.sectie) if self.sectie in KICK_NIVEAUS else None
        doel = 0
        for i, d in enumerate(drempels, start=1):
            if score >= d:
                doel = i
        if doel == 3 and not hard:
            doel = 2                                        # extreem alleen bij harde nummers
        if huidig is None:
            return KICK_NIVEAUS[doel]
        if doel < huidig and score >= drempels[huidig - 1] - TERUG:
            doel = huidig                                   # nog niet ver genoeg gezakt
        if doel != huidig and nu - self.sinds < BLIJF:
            doel = huidig                                   # niet te snel wisselen
        return KICK_NIVEAUS[doel]

    def _volgende_drop(self, nu):
        kandidaten = [d for d in self.drops if d > nu - 0.05]
        return min(kandidaten) if kandidaten else None

    def _laatste_drop(self, nu):
        gehad = [d for d in self.drops if d <= nu]
        return max(gehad) if gehad else None

    # ------------------------------------------------------------ de beslissing
    def _beslis(self, nu, wild=0.6):
        # met voorsprong liggen er ook metingen van straks klaar: dan rond 'nu' middelen (geen vertraging)
        # (maar niet over een drop heen kijken: die kicks horen pas ná het moment van de drop)
        volgende = self._volgende_drop(nu)
        vooruit = bool(self.punten) and self.punten[-1][0] >= nu + 0.6
        tot = nu + 0.6 if vooruit else nu
        if volgende is not None and volgende > nu:
            tot = min(tot, max(nu, volgende - 0.1))
        kick, e, score = self._gemiddeld(tot - 1.2, tot, met_score=True)
        if kick is None:
            laatste = self.punten[-1] if self.punten else None
            if laatste is None or nu - laatste[0] > 4.0 or laatste[0] > nu:
                return None                 # hoort (nu) niets
            kick, e, score = laatste[1], laatste[2], 0.4 * laatste[3] + 0.6 * laatste[4]
        _, _, score_lang = self._gemiddeld(tot - 3.0, tot, met_score=True)   # iets rustiger voor de niveaus
        in_kick = self.sectie in KICK_NIVEAUS
        heeft_kick = kick >= (KICK_UIT if in_kick else KICK_AAN)
        if heeft_kick:
            self.laatste_kick, self.geen_kick_sinds = nu, None
        elif self.geen_kick_sinds is None:
            self.geen_kick_sinds = nu
        niveau = _clamp(score_lang if score_lang is not None else score)
        vorige = self._laatste_drop(nu)
        hard = self._hard(nu)
        opbouw = None
        if vorige is not None and 0 <= nu - vorige < NA_DROP:
            # net gedropt: vol gas (of extreem), ook als de kick-meting nog moet volgen
            sectie = "extreem" if (hard and self.sectie == "extreem") else "drop"
            if hard and self.drops_in_nummer(nu) >= 2:
                sectie = "extreem"
            self.laatste_kick = nu
        elif heeft_kick:
            sectie = self._kick_niveau(niveau, nu, wild, hard)
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
                "extreem": sectie == "extreem", "hard": hard}

    def _stijging(self, nu):
        """Hoeveel de energie de laatste ~6 s gestegen is (opbouw zonder dat de drop al te zien is)."""
        _, nu_e = self._gemiddeld(nu - 1.5, nu)
        _, toen = self._gemiddeld(nu - 7.0, nu - 5.0)
        if nu_e is None or toen is None:
            return None
        return nu_e - toen

    def stand(self, nu, contrast=0.7):
        """Wat de show nu moet doen. None = geen muziek gehoord (dan doet de show gewoon wat is ingesteld).
        contrast (de schuif 'wildheid', 0..1): hoe groot het verschil tussen rustig en wild, en hoe snel vol gas."""
        if self._t is None or not (0 <= nu - self._t < 0.1):
            self._basis, self._t = self._beslis(nu, contrast), nu
        b = self._basis
        if b is None:
            return None
        st = dict(b)
        if st["sectie"] == "opbouw" and st["drop_t"] is not None and self.opbouw_van is not None:
            st["opbouw"] = _clamp((nu - self.opbouw_van) / max(0.5, st["drop_t"] - self.opbouw_van))
            self.opbouw_p = st["opbouw"]
        vorige = self._laatste_drop(nu)
        st["flits"] = vorige is not None and 0 <= nu - vorige < FLITS
        st["sinds_drop"] = nu - vorige if vorige is not None else None
        st["drop_nr"] = self.drops_in_nummer(nu) if vorige is not None else 0
        st["gat"] = st["drop_t"] is not None and 0 < st["drop_t"] - nu < GAT
        st["profiel"] = profiel(st["sectie"], st["opbouw"], contrast)
        return st
