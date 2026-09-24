#!/usr/bin/env python3
"""Beat-luisteraar voor DMXDesk.

Analyseert de muziek (beat, BPM, melodie, energie, drops) en stuurt alles naar DMXDesk (UDP 127.0.0.1:8091).
Gebruikt aubio voor de beat als dat er is (Raspberry Pi), anders een eigen beat-zoeker met alleen numpy.
De app zelf gebruikt de klasse Analyse ook rechtstreeks voor de geluidskaart (zie audio.py).

  beatluister.py spotify [--voorsprong 4]     leest het geluid van librespot (--backend pipe) via stdin,
                                              analyseert het en speelt het af met aplay
  beatluister.py pijp <bron> [--voorsprong 4] hetzelfde voor een andere bron, bijv. 'mpd' (MPD pipe-uitgang)
  beatluister.py mpd <fifo>                   leest de fifo-uitgang van MPD en analyseert alleen
                                              (het afspelen doet MPD zelf)

--voorsprong: zoveel seconden eerder analyseren dan het geluid te horen is. Dan staat de beat vanaf de
eerste tel goed en ziet de lichtshow drops aankomen. Pauze, volgende nummer en volume gaan dan ook zoveel later.

Dit bestand moet op zichzelf kunnen draaien (op de Pi staat het in /usr/local/lib/zeutekauwn/).
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections import deque

import numpy as np

try:
    import aubio
except ImportError:          # geen aubio (Windows/Mac-app): de eigen beat-zoeker hieronder wordt gebruikt
    aubio = None

SR = 44100
HOP = 512
WIN = 1024
FRAME_BYTES = 4          # 16 bit stereo
DOEL = ("127.0.0.1", 8091)
APLAY_DEVICE = os.environ.get("BEAT_APLAY_DEVICE", "plughw:1,0")
F_SETPIPE_SZ = 1031
HANN = np.hanning(WIN).astype(np.float32)

# energie: blokken vanaf ~5 kHz tellen als "helder" (hi-hats, cymbals, snerpende synths)
HOOG_BIN = int(5000 / (SR / WIN))
# ijkpunten (laag, hoog) voor drukte en helderheid: wat telt als rustig (0) en extreem (1)
IJK_DRUKTE = (0.20, 0.29)     # geijkt op de 9 nummers in de bibliotheek (sept 2026)
IJK_HOOG = (0.10, 0.40)


def schaal(waarde, laag, hoog):
    return clamp01((waarde - laag) / (hoog - laag))


def clamp01(v):
    return max(0.0, min(1.0, v))


# melodie-analyse: groot venster (~93 ms) voor genoeg toonhoogte-resolutie
MELODIE_WIN = 4096
HANN_MELODIE = np.hanning(MELODIE_WIN).astype(np.float32)
_freqs = np.fft.rfftfreq(MELODIE_WIN, 1.0 / SR)
MELODIE_BAND = (_freqs >= 220) & (_freqs <= 2000)                  # zang en lead, boven bas en kick
MELODIE_KLASSE = (np.round(12 * np.log2(_freqs[MELODIE_BAND] / 261.63)).astype(int)) % 12   # 0 = C


class NumpyTempo:
    """Beat-zoeker zonder aubio, met dezelfde aanroepen als aubio.tempo.

    1. Onset-sterkte per blok: hoeveel het (logaritmische) spectrum ineens toeneemt (spectral flux).
    2. Elke ~0,5 s: tempo uit de autocorrelatie van de laatste 8 s onsets, met een voorkeur rond 120 BPM.
    3. Fase: het beat-raster (met dat tempo) dat het best op de onsets past. Daaruit volgt de volgende beat.
    """

    def __init__(self, win=WIN, hop=HOP, sr=SR):
        self.win, self.hop, self.sr = win, hop, sr
        self.fps = sr / hop
        self.venster = np.zeros(win, dtype=np.float32)
        self.hann = np.hanning(win).astype(np.float32)
        # banden met gelijke toonafstand; de lage banden (kick, bas) tellen zwaarder dan hi-hats en bekkens,
        # anders valt de beat bij dansmuziek precies tussen de kicks (op de hi-hat)
        freqs = np.fft.rfftfreq(win, 1.0 / sr)
        grenzen = np.geomspace(30, min(16000, sr / 2 - 1), 25)
        self.band = np.digitize(freqs, grenzen) - 1
        self.band[(freqs < grenzen[0]) | (freqs >= grenzen[-1])] = -1
        midden = np.sqrt(grenzen[:-1] * grenzen[1:])
        self.gewicht = np.where(midden < 200, 4.0, np.where(midden < 2000, 1.5, 0.5))
        self.vorig = None
        self.onsets = deque(maxlen=int(8 * self.fps))
        self.n = 0                     # aantal verwerkte blokken
        self.periode = None            # beat-lengte in blokken
        self.volgende = None           # bloknummer (met breuk) van de volgende beat
        self.laatste = 0               # sample waarop de laatste beat viel
        self.bpm, self.zekerheid = 0.0, 0.0

    def __call__(self, blok):
        self.venster = np.concatenate((self.venster[self.hop:], blok))
        spectrum = np.abs(np.fft.rfft(self.venster * self.hann)) ** 2
        geldig = self.band >= 0
        banden = np.log1p(1000.0 * np.bincount(self.band[geldig], weights=spectrum[geldig], minlength=len(self.gewicht)))
        flux = 0.0 if self.vorig is None else float((np.maximum(0.0, banden - self.vorig) * self.gewicht).sum())
        self.vorig = banden
        self.onsets.append(flux)
        self.n += 1
        if self.n % 43 == 0 and len(self.onsets) >= 4 * self.fps:
            self.schatten()
        if self.volgende is not None and self.n >= self.volgende:
            self.laatste = int(self.volgende * self.hop)
            while self.volgende <= self.n:
                self.volgende += self.periode
            return np.array([1.0], dtype=np.float32)
        return np.array([0.0], dtype=np.float32)

    def schatten(self):
        x = np.array(self.onsets, dtype=np.float64)
        # lokaal gemiddelde eraf (0,5 s), alleen pieken tellen
        k = int(self.fps / 2)
        gem = np.convolve(x, np.ones(k) / k, mode="same")
        x = np.maximum(0.0, x - gem)
        if x.sum() <= 1e-9:
            self.zekerheid = 0.0
            return
        x = x / (x.std() + 1e-9)
        lags = np.arange(int(60 * self.fps / 220), int(60 * self.fps / 55) + 1)
        ac = np.array([np.dot(x[lag:], x[:-lag]) / (len(x) - lag) for lag in lags])
        bpm_van = 60 * self.fps / lags
        gewicht = np.exp(-0.5 * (np.log2(bpm_van / 120.0) / 0.9) ** 2)
        score = ac * gewicht
        best = int(np.argmax(score))
        if score[best] <= 0:
            self.zekerheid = 0.0
            return
        lag = float(lags[best])
        if 0 < best < len(score) - 1:               # parabool door de top: beter dan hele blokken
            a, b, c = score[best - 1], score[best], score[best + 1]
            deler = a - 2 * b + c
            if deler < 0:
                lag += 0.5 * (a - c) / deler
        self.zekerheid = float(score[best] / (np.mean(np.abs(score)) + 1e-9))
        nieuw_bpm = 60 * self.fps / lag
        if self.periode is None or abs(nieuw_bpm - self.bpm) > 3:
            self.periode = lag
        else:
            self.periode += 0.3 * (lag - self.periode)
        self.bpm = 60 * self.fps / self.periode
        # fase: welk raster met deze periode raakt de meeste onsets (van nu terug)
        p = self.periode
        aantal = int(len(x) // p)
        fasen = np.arange(0, int(np.ceil(p)))
        som = [x[np.clip((len(x) - 1 - f - np.arange(aantal) * p).round().astype(int), 0, len(x) - 1)].sum()
               for f in fasen]
        fase = float(fasen[int(np.argmax(som))])
        laatste_beat = self.n - 1 - fase
        verwacht = laatste_beat + p
        while verwacht <= self.n:
            verwacht += p
        if self.volgende is None:
            self.volgende = verwacht
        else:
            # zachtjes bijsturen, zodat de beat niet heen en weer springt
            fout = (verwacht - self.volgende + p / 2) % p - p / 2
            self.volgende += 0.5 * fout
            while self.volgende <= self.n:
                self.volgende += p

    def get_last(self):
        return self.laatste

    def get_bpm(self):
        return self.bpm

    def get_confidence(self):
        return self.zekerheid


def nieuwe_tempo():
    if aubio is not None:
        return aubio.tempo("default", WIN, HOP, SR)
    return NumpyTempo()


class Analyse:
    def __init__(self, bron, zender=None):
        """zender: functie die elk bericht (dict) krijgt. Zonder zender gaat het via UDP naar DMXDesk."""
        self.bron = bron
        self.zender = zender
        self.sock = None if zender else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.laatste_status = 0.0
        self.reset()

    def reset(self):
        self.tempo = nieuwe_tempo()
        self.rest = b""
        self.buf = np.zeros(0, dtype=np.float32)
        self.verwerkt = 0     # aantal samples dat door aubio is gegaan
        self.niveau = 0.0
        # kick-detectie: aubio kiest bij snelle nummers (bv. 208) vaak de helft (104).
        # We meten of er precies tussen twee gevonden beats ook een kick zit.
        self.venster = np.zeros(WIN, dtype=np.float32)
        self.vorige_bas = 0.0
        self.kicks = deque(maxlen=520)          # kick-sterkte per blok van 512 samples: de laatste ~6 s
        # melodie: welke van de 12 tonen klinkt het sterkst in het midden/hoog (zang, lead-synth)
        self.lang = np.zeros(MELODIE_WIN, dtype=np.float32)
        self.blok_nr = 0
        self.noot = None
        self.kandidaat, self.kandidaat_n = None, 0
        self.noot_sinds = 0.0
        # energie: luidheid, drukte (hoeveel er verandert) en helderheid (hi-hats/cymbals), per blok
        self.vorig_spectrum = None
        self.e_blokken = deque(maxlen=65)       # (rms, drukte, hoog) van de laatste ~0,75 s
        self.luidheid_historie = deque(maxlen=260)   # luidheid elke ~0,12 s, de laatste 30 s
        self.energie = None
        self.e_teller = 0
        self.e_historie = deque(maxlen=52)      # trage energie van de laatste 6 s (voor drops)
        self.e_traag = None
        self.e_start = None                     # pas na 10 s luisteren drops melden
        self.laatste_drop = -100.0

    def energie_meting(self, blok, spectrum, t_blok):
        totaal = float(spectrum.sum()) + 1e-9
        if self.vorig_spectrum is None:
            drukte = 0.0
        else:
            drukte = float(np.maximum(0.0, spectrum - self.vorig_spectrum).sum()) / totaal
        self.vorig_spectrum = spectrum
        hoog = float(spectrum[HOOG_BIN:].sum()) / totaal
        self.e_blokken.append((float(np.sqrt(np.mean(blok * blok))), drukte, hoog))
        self.e_teller += 1
        if self.e_teller % 10 or len(self.e_blokken) < self.e_blokken.maxlen:   # elke ~0,12 s, na 0,75 s opwarmen
            return
        blokken = np.array(self.e_blokken)
        luid = 20 * np.log10(1e-6 + float(np.mean(blokken[-34:, 0])))      # dB over de laatste 0,4 s
        druk = float(np.mean(blokken[:, 1]))                                 # over de laatste 0,75 s
        helder = float(np.mean(blokken[:, 2]))
        self.luidheid_historie.append(luid)
        # relatief: hoe hard is het nu vergeleken met de afgelopen 30 s (breakdown laag, drop hoog)
        hist = np.array(self.luidheid_historie)
        relatief = float(np.mean(hist <= luid)) if len(hist) >= 16 else 0.5
        # absoluut: drukte en helderheid, geijkt op de eigen muziekbibliotheek
        absoluut = 0.6 * schaal(druk, *IJK_DRUKTE) + 0.4 * schaal(helder, *IJK_HOOG)
        stil = luid < -45
        doel = 0.0 if stil else clamp01(0.45 * relatief + 0.55 * absoluut)
        # drop: na een rustig stuk (laatste 6 s) ineens veel energie. Dit gebeurt op een rustigere versie
        # van de energie; de snelle versie (voor meter en show) zou ook bij kleine dipjes een drop zien.
        if self.e_traag is None:
            self.e_traag = doel
        else:
            self.e_traag += (doel - self.e_traag) * (0.35 if doel > self.e_traag else 0.07)
        if self.e_start is None:
            self.e_start = t_blok
        if (t_blok - self.e_start > 10.0 and self.e_traag > 0.65 and min(self.e_historie) < 0.35
                and t_blok - self.laatste_drop > 10.0):
            self.laatste_drop = t_blok
            self.stuur({"soort": "drop", "t": t_blok - 0.35})
        self.e_historie.append(self.e_traag)
        # snel omhoog (drop!), rustiger omlaag
        if self.energie is None:
            self.energie = doel
        else:
            self.energie += (doel - self.energie) * (0.7 if doel > self.energie else 0.25)
        self.stuur({"soort": "energie", "e": round(self.energie, 3), "t": t_blok,
                    "luid": round(luid, 1), "druk": round(druk, 4), "hoog": round(helder, 4), "rel": round(relatief, 2)})

    def melodie(self, blok, t_blok):
        """Stuurt een 'noot'-bericht als de sterkste toon in het melodiebereik verandert."""
        self.lang = np.concatenate((self.lang[HOP:], blok))
        self.blok_nr += 1
        if self.blok_nr % 2:                       # elke ~23 ms is ruim genoeg
            return
        spectrum = np.abs(np.fft.rfft(self.lang * HANN_MELODIE))[MELODIE_BAND]
        chroma = np.bincount(MELODIE_KLASSE, weights=spectrum, minlength=12)
        totaal = float(chroma.sum())
        if totaal < 1.0:                           # (bijna) stil
            self.kandidaat = None
            return
        klasse = int(np.argmax(chroma))
        helder = float(chroma[klasse]) / totaal    # 1/12 = alles even sterk, hoger = duidelijke toon
        if helder < 0.16 or klasse == self.noot:
            self.kandidaat = None
            return
        if klasse == self.kandidaat:
            self.kandidaat_n += 1
        else:
            self.kandidaat, self.kandidaat_n = klasse, 1
        if self.kandidaat_n >= 2 and t_blok - self.noot_sinds >= 0.09:
            self.noot, self.noot_sinds = klasse, t_blok
            self.stuur({"soort": "noot", "klasse": klasse, "helder": round(helder, 2),
                        "t": t_blok - MELODIE_WIN / 2 / SR})

    def kick_sterkte(self, spectrum):
        """Toename van de energie in de lage tonen (43-170 Hz): een kick-drum geeft een flinke sprong."""
        bas = float(np.sqrt(np.sum(spectrum[1:5] ** 2)))   # lineair: alleen een echte kick geeft een grote sprong
        sterkte = max(0.0, bas - self.vorige_bas)
        self.vorige_bas = bas
        return sterkte

    def kick_verhouding(self, bpm):
        """Herhalen de kicks zich al na een halve beat van aubio? 0 = nee (rustig nummer), ~1 = ja (dubbel zo snel).

        Autocorrelatie van de kick-sterkte bij een vertraging van een halve en een hele beat. Dit hangt niet af
        van waar aubio de beat precies neerlegt, alleen van het tempo."""
        if bpm <= 0 or len(self.kicks) < 300:
            return None
        x = np.array(self.kicks, dtype=np.float32)
        x = x - x.mean()

        def ac(vertraging):
            beste = 0.0
            for lag in range(int(vertraging) - 1, int(vertraging) + 3):
                if 1 <= lag < len(x) // 2:
                    beste = max(beste, float(np.dot(x[lag:], x[:-lag])) / (len(x) - lag))
            return beste

        periode = 60.0 / bpm * SR / HOP            # een beat van aubio, in blokken
        heel = ac(periode)
        if heel <= 0:
            return None
        return round(ac(periode / 2) / heel, 2)

    def stuur(self, bericht):
        bericht["bron"] = self.bron
        if self.zender is not None:
            self.zender(bericht)
            return
        try:
            self.sock.sendto(json.dumps(bericht).encode(), DOEL)
        except OSError:
            pass

    def voer(self, data, t_nu):
        """data = ruwe S16LE stereo; t_nu = moment waarop het laatste sample 'binnen' is."""
        data = self.rest + data
        n = len(data) - len(data) % FRAME_BYTES
        self.rest = data[n:]
        if n == 0:
            return
        mono = np.frombuffer(data[:n], dtype="<i2").astype(np.float32).reshape(-1, 2).mean(axis=1) / 32768.0
        self.voer_mono(mono, t_nu)

    def voer_mono(self, mono, t_nu):
        """mono = float32 samples (-1..1) op 44,1 kHz; t_nu = moment waarop het laatste sample 'binnen' is."""
        self.niveau = 0.8 * self.niveau + 0.2 * float(np.sqrt(np.mean(mono * mono)))
        self.buf = np.concatenate((self.buf, mono))
        totaal = self.verwerkt + len(self.buf)
        while len(self.buf) >= HOP:
            blok, self.buf = self.buf[:HOP], self.buf[HOP:]
            is_beat = self.tempo(blok)
            self.verwerkt += HOP
            t_blok = t_nu - (totaal - self.verwerkt) / SR
            self.venster = np.concatenate((self.venster[HOP:], blok))
            spectrum = np.abs(np.fft.rfft(self.venster * HANN))
            self.kicks.append(self.kick_sterkte(spectrum))
            self.energie_meting(blok, spectrum, t_blok)
            self.melodie(blok, t_blok)
            if is_beat[0]:
                t_beat = t_nu - (totaal - self.tempo.get_last()) / SR
                bpm = float(self.tempo.get_bpm())
                self.stuur({"soort": "beat", "t": t_beat, "bpm": bpm,
                            "conf": float(self.tempo.get_confidence()),
                            "kick_ratio": self.kick_verhouding(bpm)})
        if t_nu - self.laatste_status > 1.0:
            self.laatste_status = t_nu
            self.stuur({"soort": "status", "bpm": float(self.tempo.get_bpm()),
                        "conf": float(self.tempo.get_confidence()), "niveau": round(self.niveau, 4)})


class AplayUitgang:
    """Geluid naar de geluidskaart van de Pi via aplay (dmix werkt daar niet: alleen open zolang er muziek is)."""

    def __init__(self, apparaat=APLAY_DEVICE):
        self.apparaat, self.p = apparaat, None

    def start(self):
        self.p = subprocess.Popen(["aplay", "-q", "-D", self.apparaat, "-t", "raw", "-f", "S16_LE", "-r", str(SR), "-c", "2",
                                   "--buffer-time=150000"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            import fcntl       # alleen Linux (de Pi); bestaat niet op Windows
            fcntl.fcntl(self.p.stdin.fileno(), F_SETPIPE_SZ, 8192)   # kleine pijp = weinig vertraging
        except (ImportError, OSError):
            pass

    def schrijf(self, data):
        if self.p is None or self.p.poll() is not None:
            raise OSError("aplay draait niet")
        self.p.stdin.write(data)
        self.p.stdin.flush()

    def stop(self):
        if self.p is None:
            return
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            self.p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.p.kill()
        self.p = None


class Doorgever:
    """Muziek met voorsprong doorgeven: eerst analyseren, pas `voorsprong` seconden later afspelen.

    Zo weet de lichtshow vooraf wanneer elke beat, noot en drop te horen is (en kan hij naar een drop
    opbouwen). Spotify (librespot) en MPD leveren sneller dan echte tijd; de rij houdt ze in toom en
    het afspelen bepaalt het tempo. Bij een pauze speelt de rij nog leeg en gaat de geluidskaart dicht."""

    BPS = SR * FRAME_BYTES      # bytes per seconde

    def __init__(self, analyse, uitgang, voorsprong=0.0, melding=None):
        """melding: functie die aangeroepen wordt als 'speelt' of 'fout' verandert (voor een statusscherm)."""
        self.a, self.uitgang, self.melding = analyse, uitgang, melding
        self.voorsprong = max(0.0, float(voorsprong))
        self.max_bytes = max(8192, int(self.voorsprong * self.BPS))
        self.rij = deque()
        self.in_rij = 0
        self.cond = threading.Condition()
        self.klaar = False
        self.bezig = 0              # bytes die nu naar de geluidskaart geschreven worden
        self.stoppen = threading.Event()
        self.speelt = False
        self.fout = None            # waarom de geluidskaart niet open kan

    def _zet(self, speelt, fout):
        if (speelt, fout) != (self.speelt, self.fout):
            self.speelt, self.fout = speelt, fout
            if self.melding:
                self.melding()

    def lees(self, lees_blok):
        """Leest tot het einde: lees_blok() geeft bytes, b"" = einde. Analyseert meteen, afspelen gebeurt later."""
        rest, laatste = b"", time.time()
        try:
            while not self.stoppen.is_set():
                data = lees_blok()
                if not data:
                    break
                nu = time.time()
                if nu - laatste > 0.6:          # na een pauze: opnieuw beginnen met luisteren
                    self.a.reset()
                laatste = nu
                data = rest + data
                heel = len(data) - len(data) % FRAME_BYTES   # alleen hele samples, anders ruis na een pauze
                data, rest = data[:heel], data[heel:]
                if not data:
                    continue
                with self.cond:
                    while self.in_rij >= self.max_bytes and not self.stoppen.is_set():
                        self.cond.wait(0.1)
                    self.rij.append(data)
                    self.in_rij += len(data)
                    # dit stukje is de geluidskaart in na alles wat er nog voor staat (rij + wat nu geschreven wordt);
                    # zelfde moment als vroeger 'net geschreven', dus de schuiven 'licht gelijk zetten' blijven kloppen
                    t_speel = (time.time() + (self.in_rij + self.bezig) / self.BPS
                               + getattr(self.uitgang, "latentie", 0.0))
                    self.cond.notify_all()
                self.a.voer(data, t_speel)
        finally:
            with self.cond:
                self.klaar = True
                self.cond.notify_all()

    def speel(self):
        """Speelt de rij af; geeft de geluidskaart vrij als er even niets is."""
        open_, leeg_sinds, niet_voor = False, None, 0.0
        while not self.stoppen.is_set():
            with self.cond:
                if not self.rij:
                    if self.klaar:
                        break
                    self.cond.wait(0.25)
                data = self.rij.popleft() if self.rij else None
                if data is not None:
                    self.in_rij -= len(data)
                    self.bezig = len(data)
                    self.cond.notify_all()
            nu = time.time()
            if data is None:
                leeg_sinds = leeg_sinds or nu
                if open_ and nu - leeg_sinds > 0.6:      # gepauzeerd: geluidskaart vrijgeven
                    self.uitgang.stop()
                    open_ = False
                    self._zet(False, None)
                continue
            leeg_sinds = None
            if not open_ and nu >= niet_voor:
                try:
                    self.uitgang.start()
                    open_ = True
                except Exception as e:
                    niet_voor = nu + 0.3
                    self._zet(False, str(e) or type(e).__name__)
            geschreven = False
            if open_:
                try:
                    self.uitgang.schrijf(data)
                    geschreven = True
                    self._zet(True, None)
                except Exception:
                    self.uitgang.stop()
                    open_, niet_voor = False, time.time() + 0.3     # geluidskaart bezet: straks opnieuw
            if not geschreven:
                time.sleep(len(data) / self.BPS)               # zelf het tempo bewaken
            self.bezig = 0
        if open_:
            self.uitgang.stop()
        self._zet(False, self.fout)

    def draai(self, lees_blok):
        """lees() en speel() tegelijk; komt terug als de invoer ophoudt en alles gespeeld is."""
        speler = threading.Thread(target=self.speel, daemon=True, name="afspelen")
        speler.start()
        self.lees(lees_blok)
        speler.join()

    def stop(self):
        self.stoppen.set()
        with self.cond:
            self.cond.notify_all()


def doorgeven(bron, voorsprong):
    """librespot of MPD (via stdin) analyseren en met voorsprong afspelen op de geluidskaart."""
    fd = sys.stdin.buffer.fileno()
    Doorgever(Analyse(bron), AplayUitgang(), voorsprong).draai(lambda: os.read(fd, 8192))


def mpd(pad):
    """Alleen analyseren (het afspelen doet MPD zelf): leest de fifo-uitgang van MPD."""
    a = Analyse("mpd")
    while True:
        try:
            fd = os.open(pad, os.O_RDONLY)      # wacht tot MPD begint te spelen
        except OSError:
            time.sleep(1.0)
            continue
        a.reset()
        with os.fdopen(fd, "rb", buffering=0) as f:
            while True:
                data = f.read(8192)
                if not data:
                    break
                a.voer(data, time.time())


def _voorsprong(args):
    if "--voorsprong" in args:
        try:
            return float(args[args.index("--voorsprong") + 1])
        except (IndexError, ValueError):
            pass
    return 0.0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "spotify":
        doorgeven("spotify", _voorsprong(args))
    elif len(args) >= 2 and args[0] == "pijp":
        doorgeven(args[1], _voorsprong(args))
    elif len(args) >= 2 and args[0] == "mpd":
        mpd(args[1])
    else:
        print(__doc__)
        sys.exit(2)
