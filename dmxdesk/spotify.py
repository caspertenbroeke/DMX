"""DMXDesk als Spotify-speaker (Spotify Connect), net als Sonos of raspotify op de Pi, met een eigen speler.

In de Spotify-app kies je 'DMXDesk' (of de naam die je instelt) als speaker. Het meegeleverde programma
dmxdesk-spotify (gebouwd op librespot, zie spotify-speaker/) levert het geluid aan DMXDesk; dat analyseert de
muziek eerst en speelt hem een paar seconden later af op de geluidskaart. Zo weet de lichtshow vooraf waar de
beats en drops vallen.

Omdat dmxdesk-spotify meldt wat er gebeurt (pauze, ander nummer, spoelen, volume), werken die ondanks de
voorsprong meteen: pauze = meteen stil, volgende = de wachtrij leeg en het nieuwe nummer meteen, volume wordt pas
bij het afspelen toegepast. En in DMXDesk zelf zit een speler (vorige / pauze / volgende / volume).
Spotify Premium is nodig (dat geldt voor elke Spotify Connect-speaker).
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import deque

try:
    import numpy as np
    import sounddevice as sd
except (ImportError, OSError):
    sd = None

from . import paden
from .beatluister import SR, Analyse, Doorgever

BRON = "connect"      # naam van deze bron bij de beat-analyse (Spotify via de Pi heet "spotify")
PROGRAMMA = "dmxdesk-spotify"
COMMANDO_S = {"play", "pause", "playpause", "next", "prev", "volume", "seek", "shuffle", "repeat"}


def foutmelding(logboek, code):
    """De laatste fout van de speaker, in gewone woorden waar dat kan."""
    fouten = [r.split("]", 1)[-1].strip() for r in logboek if " ERROR " in r or " WARN " in r]
    tekst = " ".join(fouten)
    if "discovery" in tekst.lower():
        oorzaak = next((f.split(":", 1)[1].strip() for f in fouten if "failed to start" in f or "unavailable:" in f), "")
        return ("Kan niet als speaker op het netwerk verschijnen" + (f" ({oorzaak})" if oorzaak else ""))[:200]
    if "bad credentials" in tekst.lower() or "premium" in tekst.lower():
        return "Spotify weigert het account: voor een Spotify-speaker is Spotify Premium nodig."
    return (fouten[-1] if fouten else f"de speaker stopte (code {code})")[:200]


def speaker_pad():
    naam = PROGRAMMA + (".exe" if sys.platform == "win32" else "")
    for pad in (os.environ.get("DMXDESK_SPEAKER"), os.path.join(paden.pakket_map(), "bin", naam)):
        if pad and os.path.isfile(pad):
            return pad
    return shutil.which(PROGRAMMA)


def uitvoer_apparaten():
    if sd is None:
        return []
    try:
        lijst, hostapis = sd.query_devices(), sd.query_hostapis()
        standaard = sd.default.device[1] if sd.default.device else None
    except Exception:
        return []
    uit = []
    for i, d in enumerate(lijst):
        if d.get("max_output_channels", 0) < 2:
            continue
        api = hostapis[d["hostapi"]]["name"] if d.get("hostapi") is not None else ""
        uit.append({"naam": f"{d['name']} ({api})" if api else d["name"], "standaard": i == standaard})
    return uit


def _zoek_uitvoer(naam):
    if not naam:
        return None
    hostapis = sd.query_hostapis()
    for i, d in enumerate(sd.query_devices()):
        api = hostapis[d["hostapi"]]["name"] if d.get("hostapi") is not None else ""
        if d.get("max_output_channels", 0) >= 2 and naam in (f"{d['name']} ({api})", d["name"]):
            return i
    raise OSError(f"geluidsapparaat '{naam}' niet gevonden")


def versterking(procent):
    """Volume 0-100 zoals in de Spotify-app → versterking (derde macht: klinkt gelijkmatig)."""
    p = max(0.0, min(100.0, float(procent))) / 100.0
    return p * p * p


class GeluidskaartUitgang:
    """Afspelen via de geluidskaart van deze computer (PortAudio), met het volume van de speler."""

    def __init__(self, apparaat=None, volume=100):
        self.apparaat, self.stream = apparaat, None
        self.gain = self._gain_oud = versterking(volume)
        try:       # hoe lang het duurt voor geschreven geluid te horen is (na het openen: de echte waarde)
            nr = _zoek_uitvoer(apparaat)
            self.latentie = float(sd.query_devices(nr if nr is not None else sd.default.device[1])
                                  ["default_high_output_latency"])
        except Exception:
            self.latentie = 0.1

    def volume(self, procent):
        self.gain = versterking(procent)

    def wissel(self, apparaat):
        """Andere luidspreker: bij het volgende stukje dicht en met het nieuwe apparaat weer open."""
        self.nieuw_apparaat = apparaat or ""

    def start(self):
        nr = _zoek_uitvoer(self.apparaat)
        if nr is None and not any(d.get("max_output_channels", 0) >= 2 for d in sd.query_devices()):
            raise OSError("geen luidspreker of geluidskaart gevonden")
        try:
            self.stream = sd.RawOutputStream(samplerate=SR, channels=2, dtype="int16", device=nr)
            self.stream.start()
        except Exception as e:
            self.stream = None
            raise OSError(f"luidspreker gaat niet open ({e})") from e
        try:
            self.latentie = float(self.stream.latency)
        except (TypeError, ValueError):
            pass

    def schrijf(self, data):
        if getattr(self, "nieuw_apparaat", None) is not None:
            self.apparaat, self.nieuw_apparaat = self.nieuw_apparaat or None, None
            self.stop()
            raise OSError("andere luidspreker")      # de afspeler opent hem meteen opnieuw
        g, oud = self.gain, self._gain_oud
        if g < 0.999 or oud < 0.999:
            s = np.frombuffer(data, dtype="<i2").reshape(-1, 2).astype(np.float32)
            if abs(g - oud) > 1e-4:           # volume veranderd: geleidelijk binnen dit stukje (geen klik)
                s *= np.linspace(oud, g, len(s), dtype=np.float32)[:, None]
            else:
                s *= g
            data = np.clip(s, -32768, 32767).astype("<i2").tobytes()
        self._gain_oud = g
        self.stream.write(data)

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        self.stream = None


def _lees_precies(bestand, n):
    delen, over = [], n
    while over > 0:
        stuk = bestand.read(over)
        if not stuk:
            return None
        delen.append(stuk)
        over -= len(stuk)
    return b"".join(delen)


class SpotifySpeaker:
    def __init__(self, engine):
        self.engine = engine
        self.proc = None
        self.doorgever = None
        self.uitgang = None
        self.huidig = None
        self.fout = ""
        self.verbonden = False
        self.logboek = deque(maxlen=30)
        self.stoppen = threading.Event()
        self.lock = threading.Lock()
        self.schrijf_lock = threading.Lock()
        self.speler = {}                 # wat je nu hoort: nummer, artiesten, hoes, positie, volume, …
        self._nieuw_speler()
        self.geleerd_pad = os.path.join(paden.gebruikers_map(), "geleerd.json")
        self.geleerd = self._laad_geleerd()
        self.opbouw_pos = None           # OPBOUW gedrukt op deze plek in het nummer (ms), wacht op DROP
        engine.bij_knop.append(self._knop)
        self.status_bijwerken()

    def _nieuw_speler(self):
        self.speler = {"id": "", "naam": "", "artiesten": [], "album": "", "hoes": None, "duur": 0, "pos": 0, "pos_t": 0.0,
                       "speelt": False, "volume": 100, "gebruiker": "", "bediening": "", "shuffle": False}
        self.verzoek = None              # play-request van wat er nu geladen wordt
        self.einde_van = None            # play-request waarvan het einde bereikt is (volgende = vanzelf)
        self.pauze = False
        self.overgang = False            # vanzelf door naar het volgende nummer: wacht op 'speelt'
        self.b_start = None              # merkteken in de rij waar dat volgende nummer begint (nog niet gelijkgezet)
        self.gelijk = None               # 'overgang' of 'pauze': Spotify wordt gelijkgezet met wat je hoort
        self.gespeeld_bij = 0            # doorgever.gespeeld toen het huidige nummer begon te klinken
        self.pos_basis = 0

    @staticmethod
    def beschikbaar():
        return speaker_pad() is not None and sd is not None

    def status_bijwerken(self):
        self.engine.extra_status["spotify"] = self.status

    def status(self):
        cfg = self.engine.data.get("spotify") or {}
        d = self.doorgever
        return {
            "beschikbaar": self.beschikbaar(),
            "aan": self.proc is not None and self.proc.poll() is None,
            "naam": cfg.get("naam"),
            "verbonden": self.verbonden,
            "speelt": bool(d and d.speelt),
            "nummer": self.speler["naam"],
            "voorsprong": cfg.get("voorsprong"),
            "fout": self.fout or (f"Geen geluid: {d.fout}" if d and d.fout else ""),
            "vooruit": round(d.vooruit(), 1) if d else 0.0,       # hoeveel het licht nu echt vooruit hoort
            "geleerd": len((self.geleerd.get(self.speler.get("id") or "") or {}).get("momenten", [])),
            "vullen": bool(d and d.vul_nodig and not d.actief and d.in_rij > 0),
            "speler": dict(self.speler),
        }

    # ------------------------------------------------------------ aan/uit
    def bijwerken(self):
        with self.engine.lock:
            cfg = dict(self.engine.data.get("spotify") or {})
        gewenst = (cfg.get("naam"), cfg.get("apparaat"), float(cfg.get("voorsprong") or 0),
                   int(cfg.get("zeroconf_poort") or 0)) if cfg.get("aan") else None
        with self.lock:
            draait = self.proc is not None and self.proc.poll() is None
            if draait and gewenst == self.huidig:
                return
            if draait and gewenst and self.huidig and (gewenst[0], gewenst[3]) == (self.huidig[0], self.huidig[3]):
                # voorsprong of luidspreker anders: meteen toepassen, zonder de muziek en verbinding te onderbreken
                if self.doorgever and gewenst[2] != self.huidig[2]:
                    self.doorgever.zet_voorsprong(gewenst[2])
                if self.uitgang and gewenst[1] != self.huidig[1]:
                    self.uitgang.wissel(gewenst[1])
                self.huidig = gewenst
                return
            self._stop()
            self.huidig = gewenst
            self.fout = ""
            if gewenst:
                self.stoppen = threading.Event()
                threading.Thread(target=self._bewaak, args=(gewenst, self.stoppen), daemon=True, name="spotify").start()
            self.status_bijwerken()

    def _stop(self):
        self.stoppen.set()
        proc, doorgever = self.proc, self.doorgever
        if doorgever:
            doorgever.stop()
        if proc is not None and proc.poll() is None:
            try:
                proc.stdin.close()             # de speaker stopt vanzelf als zijn invoer dicht gaat
            except OSError:
                pass
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self.proc, self.doorgever, self.uitgang, self.verbonden = None, None, None, False
        self._nieuw_speler()

    def stop(self):
        with self.lock:
            self._stop()
            self.status_bijwerken()

    # ------------------------------------------------------------ bediening vanuit DMXDesk
    def commando(self, actie, waarde=None):
        actie = str(actie)
        if actie not in COMMANDO_S:
            raise ValueError(f"onbekende actie '{actie}'")
        proc = self.proc
        if proc is None or proc.poll() is not None:
            raise ValueError("De Spotify-speaker staat uit")
        regel = actie if waarde is None else f"{actie} {int(float(waarde))}"
        if actie == "volume":        # meteen horen (de speaker bevestigt het daarna)
            self._volume(int(float(waarde or 0)))
            self.status_bijwerken()
        with self.schrijf_lock:
            try:
                proc.stdin.write((regel + "\n").encode())
                proc.stdin.flush()
            except OSError as e:
                raise ValueError(f"De Spotify-speaker reageert niet ({e})") from e

    def _volume(self, procent):
        self.speler["volume"] = max(0, min(100, int(procent)))
        if self.uitgang is not None:
            self.uitgang.volume(self.speler["volume"])

    # ------------------------------------------------------------ gebeurtenissen van de speaker
    def _gebeurtenis(self, m):
        """Draait in de leesdraad, in de volgorde van het geluid."""
        soort, d = m.get("t"), self.doorgever
        sp = self.speler
        if soort == "klaar":
            self._volume(m.get("volume", 100))
        elif soort == "verbonden":
            self.verbonden, self.fout, sp["gebruiker"] = True, "", m.get("gebruiker", "")
        elif soort == "los":
            self.verbonden = False
        elif soort == "bediening":
            sp["bediening"] = m.get("naam", "")
        elif soort == "volume":
            self._volume(m.get("v", 100))
        elif soort == "shuffle":
            sp["shuffle"] = bool(m.get("aan"))
        elif soort == "verzoek":
            # elk nieuw nummer begint hiermee: vanzelf (het vorige is tot het eind gelezen) of gekozen/geskipt
            v = m.get("verzoek")
            if v != self.verzoek:
                vanzelf = self.verzoek is not None and self.einde_van == self.verzoek
                if self.verzoek is not None and not vanzelf:
                    self._leeg()          # gekozen: wat nog van het oude klaarstond weg, het nieuwe meteen
                self.verzoek, self.overgang, self.gelijk = v, vanzelf, None
        elif soort == "laden":
            self._markeer(pos=m.get("pos", 0))
        elif soort == "gespoeld":
            self._gespoeld(m.get("pos", 0))
        elif soort == "einde":
            self.einde_van = m.get("verzoek")
        elif soort == "nummer":
            info = {k: m.get(k) for k in ("id", "naam", "artiesten", "album", "hoes", "duur")}
            self._markeer(info=info)
        elif soort == "pauze" and d is not None and not self.pauze:
            self.pauze = True
            d.pauzeer()
            sp["pos"], sp["pos_t"], sp["speelt"] = self._positie(), time.time(), False
            self._pauze_gelijkzetten()
        elif soort == "speelt":
            if self.pauze and d is not None:
                self.pauze = False
                d.hervat()
            sp["pos"], sp["pos_t"], sp["speelt"] = self._positie(), time.time(), True
            if self.overgang and m.get("verzoek") == self.verzoek:
                self.overgang = False
                self._overgang_gelijkzetten(m.get("pos", 0))
        elif soort == "gestopt":
            self.einde_van, self.overgang = None, False     # daarna iets kiezen = meteen (niet eerst uitspelen)
            self._markeer(stop=True)
        self.status_bijwerken()

    # ------------------------------------------------------------ Spotify gelijk houden met wat je hoort
    # De speaker leest `voorsprong` seconden vooruit. Spotify telt de tijd vanaf dat hij een nummer begint te
    # lezen; bij kiezen/skippen is de voorsprong in een fractie van een seconde gevuld en klopt dat. Maar gaat
    # hij vanzelf door naar het volgende nummer, dan begint dat te tellen terwijl je nog de laatste seconden
    # van het vorige hoort (en na een pauze staat Spotify ook vooruit). Daarom zetten we Spotify dan terug naar
    # wat je echt hoort en lezen we vanaf daar opnieuw vooruit (dat gaat snel; het licht merkt er niets van).
    GELIJK_VOOR = 0.8          # zoveel seconden voor het nieuwe nummer te horen is, Spotify terugzetten

    def _stuur(self, regel):
        def doe():
            try:
                actie, *waarde = regel.split()
                self.commando(actie, waarde[0] if waarde else None)
            except ValueError:
                pass
        threading.Thread(target=doe, daemon=True, name="spotify-cmd").start()

    def _overgang_gelijkzetten(self, pos):
        d = self.doorgever
        if d is None or d.vooruit() < 2 * self.GELIJK_VOOR + 0.5:
            return                              # (bijna) geen voorsprong: Spotify loopt al gelijk
        merk = d.markeer(lambda: None)          # hier begint het nieuwe nummer
        self.b_start = merk

        def terugzetten():                      # vlak voordat je het nieuwe nummer hoort
            if self.b_start is merk and self.gelijk is None:
                self.gelijk = "overgang"
                d.vrij_lezen(1.0)
                self._stuur(f"seek {int(pos)}")
        d.markeer(terugzetten, voor=self.GELIJK_VOOR)

    def _pauze_gelijkzetten(self):
        d = self.doorgever
        if d is None or not self.verbonden or self.b_start is not None or self.overgang or self.gelijk:
            return
        if d.vooruit() < 1.0:
            return
        self.gelijk = "pauze"                   # Spotify terug naar waar je bent; bij 'verder' vult hij opnieuw
        self._stuur(f"seek {self._positie() + int(d.bezig * 1000 / Doorgever.BPS)}")

    def _gespoeld(self, pos):
        d, gelijk, merk = self.doorgever, self.gelijk, self.b_start
        self.gelijk = None
        if d is not None:
            d.vrij_lezen(0)
        if gelijk == "overgang" and merk is not None and d is not None:
            t = d.leeg_vanaf(merk)              # het oude nummer speelt gewoon uit, het nieuwe opnieuw vanaf pos
            if t is not None:
                self.b_start = None
                self.engine.muziek_vergeet(t)
                d.a.reset()
                self._markeer(pos=pos)
                return
        self._leeg(pauze_houden=(gelijk == "pauze"))
        self._markeer(pos=pos)

    def _positie(self):
        d = self.doorgever
        gespeeld = (d.gespeeld - self.gespeeld_bij) if d else 0
        return int(self.pos_basis + gespeeld / Doorgever.BPS * 1000)

    def _leeg(self, pauze_houden=False):
        d = self.doorgever
        if d is None:
            return
        self.b_start = None
        self.engine.muziek_vergeet(time.time())   # wat nog gepland stond (oude nummer) weg
        d.leeg()                                  # en de rij; daarna eerst weer voorvullen
        d.a.reset()                               # (zelfde draad als de analyse)
        if self.pauze and not pauze_houden:
            self.pauze = False
            d.hervat()

    def _markeer(self, pos=None, info=None, stop=False):
        """Pas als het geluid tot hier gespeeld is, weet de speler wat je hoort (nummer, positie)."""
        d = self.doorgever
        if d is None:
            return

        def nu_te_horen():
            sp = self.speler
            nieuw = info is not None and info.get("id") != sp.get("id")
            if info is not None:
                sp.update(info)
            if pos is not None:
                self.pos_basis, self.gespeeld_bij = pos, d.gespeeld
            sp["pos"], sp["pos_t"] = self._positie(), time.time()
            sp["speelt"] = not stop and not self.pauze
            if nieuw or pos is not None:
                self.opbouw_pos = None
                self._plan_geleerd(nieuw)
            self.status_bijwerken()
        d.markeer(nu_te_horen)

    # ------------------------------------------------------------ leren: OPBOUW/DROP per nummer onthouden
    def _laad_geleerd(self):
        try:
            with open(self.geleerd_pad, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _bewaar_geleerd(self):
        try:
            tmp = self.geleerd_pad + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.geleerd, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.geleerd_pad)
        except OSError as e:
            print("Geleerde drops bewaren mislukt:", e, flush=True)

    def _gehoord_ms(self):
        """Waar je nu bent in het nummer (wat uit de luidspreker komt)."""
        lat = getattr(self.uitgang, "latentie", 0.0) if self.uitgang else 0.0
        return max(0, self._positie() - int(lat * 1000))

    def _knop(self, soort, t, opbouw_aan):
        """OPBOUW/DROP gedrukt: onthouden op welke plek in dit nummer."""
        nid = self.speler.get("id")
        if not nid or not self.speler.get("speelt") or self.doorgever is None:
            return
        pos = self._gehoord_ms()
        if soort == "opbouw":
            self.opbouw_pos = pos if opbouw_aan else None
            return
        begin, self.opbouw_pos = self.opbouw_pos, None
        item = self.geleerd.setdefault(nid, {"naam": self.speler.get("naam", ""), "momenten": []})
        oud = [mo for mo in item["momenten"] if abs(mo[1] - pos) < 2500]
        if begin is None and oud:
            begin = oud[0][0]            # opnieuw gedrukt om te verbeteren: de opbouw van de vorige keer blijft
        item["momenten"] = [mo for mo in item["momenten"] if abs(mo[1] - pos) >= 2500]    # opnieuw gedrukt: vervangen
        item["momenten"].append([begin if begin is not None and begin < pos else None, pos])
        item["momenten"].sort(key=lambda mo: mo[1])
        self._bewaar_geleerd()
        print(f"Geleerd: '{item['naam']}' drop op {pos / 1000:.1f} s"
              + (f", opbouw vanaf {begin / 1000:.1f} s" if begin is not None else ""), flush=True)
        self.status_bijwerken()

    def _plan_geleerd(self, nieuw_nummer):
        """Het nummer (of een nieuwe plek erin) klinkt nu: de geleerde momenten inplannen."""
        nu = time.time()
        pos = self._gehoord_ms()
        momenten = []
        for begin, drop in (self.geleerd.get(self.speler.get("id") or "") or {}).get("momenten", []):
            if drop > pos:
                momenten.append((None if begin is None else nu + (begin - pos) / 1000.0, nu + (drop - pos) / 1000.0))
        self.engine.leer_momenten(momenten, nummer_begint=nu if nieuw_nummer else None)

    def vergeet_nummer(self):
        nid = self.speler.get("id")
        if not nid or nid not in self.geleerd:
            raise ValueError("Voor dit nummer is nog niets geleerd")
        del self.geleerd[nid]
        self._bewaar_geleerd()
        self.engine.vergeet_geleerd()
        self.status_bijwerken()

    # ------------------------------------------------------------ draaien
    def _bewaak(self, cfg, stoppen):
        """Start de speaker en houdt hem draaiende (ook na een fout of als hij stopt)."""
        naam, apparaat, voorsprong, zc_poort = cfg
        wacht = 0
        while not stoppen.is_set():
            pad = speaker_pad()
            if pad is None or sd is None:
                self.fout = ("de Spotify-speaker ontbreekt in deze installatie" if pad is None
                             else "geluidskaart niet beschikbaar (sounddevice/PortAudio ontbreekt)")
                self.status_bijwerken()
                return
            cache = os.path.join(paden.gebruikers_map(), "spotify")
            os.makedirs(cache, exist_ok=True)
            args = [pad, "--name", naam or "DMXDesk", "--cache", cache, "--volume", str(self.speler["volume"])]
            if zc_poort:
                args += ["--zeroconf-port", str(zc_poort)]
            with self.lock:
                if stoppen.is_set():
                    return
                try:
                    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            stdin=subprocess.PIPE,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except OSError as e:
                    proc = None
                    self.fout = f"de Spotify-speaker start niet: {e}"
                if proc is not None:
                    self.uitgang = GeluidskaartUitgang(apparaat, self.speler["volume"])
                    doorgever = Doorgever(Analyse(BRON, zender=self.engine.beat_bericht), self.uitgang, voorsprong,
                                          melding=self.status_bijwerken, reset_na_gat=False)
                    self.proc, self.doorgever = proc, doorgever
                self.status_bijwerken()
            if proc is None:
                stoppen.wait(10)
                continue
            gestart = time.time()
            self.logboek.clear()
            print(f"Spotify-speaker '{naam}' gestart (voorsprong {voorsprong:g} s)", flush=True)
            threading.Thread(target=self._lees_logboek, args=(proc,), daemon=True, name="spotify-log").start()
            try:
                doorgever.draai(self._lezer(proc.stdout))
            except (OSError, ValueError):
                doorgever.stop()
            code = proc.wait()
            if stoppen.is_set():
                break
            wacht = 5 if self.verbonden or time.time() - gestart > 60 else min(60, max(5, wacht * 2))
            self.fout = foutmelding(list(self.logboek), code)
            self.verbonden = False
            self.status_bijwerken()
            print(f"Spotify-speaker gestopt: {self.fout} - opnieuw starten over {wacht} s", flush=True)
            stoppen.wait(wacht)

    def _lezer(self, bestand):
        """lees_blok voor de Doorgever: geeft audio terug en handelt gebeurtenissen onderweg af."""
        def lees_blok():
            while True:
                kop = _lees_precies(bestand, 5)
                if kop is None:
                    return b""
                soort, n = kop[0:1], int.from_bytes(kop[1:5], "little")
                inhoud = _lees_precies(bestand, n) if n else b""
                if inhoud is None:
                    return b""
                if soort == b"A" and inhoud:
                    return inhoud
                if soort == b"E":
                    try:
                        self._gebeurtenis(json.loads(inhoud.decode("utf-8")))
                    except (ValueError, UnicodeDecodeError):
                        pass
        return lees_blok

    def _lees_logboek(self, proc):
        for regel in iter(proc.stderr.readline, b""):
            self.logboek.append(regel.decode("utf-8", "replace").rstrip())
