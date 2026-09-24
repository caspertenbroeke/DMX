import json
import sys
import time
import types

import numpy as np
import pytest

from dmxdesk import beatluister as bl
from dmxdesk import spotify
from dmxdesk.engine import Engine

BPS = bl.Doorgever.BPS


def klikken(seconden, bpm=120):
    """Stereo 16-bit: een klik op elke beat."""
    n = int(seconden * bl.SR)
    y = np.zeros(n, dtype=np.float32)
    for k in np.arange(0.1, seconden, 60.0 / bpm):
        i = int(k * bl.SR)
        y[i:i + 2000] = 0.8 * np.sin(np.arange(len(y[i:i + 2000])) * 0.02) * np.exp(-np.arange(len(y[i:i + 2000])) / 400)
    s = (y * 32000).astype("<i2")
    return np.repeat(s, 2).tobytes()


class NepAnalyse:
    def __init__(self):
        self.gevoerd = []
        self.berichten = []

    def stuur(self, m):
        self.berichten.append((time.time(), m))

    def voer(self, data, t):
        self.gevoerd.append((len(data), t, time.time()))

    def reset(self):
        pass


class NepUitgang:
    latentie = 0.0

    def __init__(self):
        self.data, self.eind = bytearray(), []

    def start(self):
        pass

    def schrijf(self, data):
        time.sleep(len(data) / BPS)       # zoals een echte geluidskaart: in het tempo van de muziek
        self.data.extend(data)
        self.eind.append(time.time())

    def stop(self):
        pass


def test_doorgever_speelt_alles_met_voorsprong():
    geluid = klikken(1.2)
    blokken = [geluid[i:i + 8820] for i in range(0, len(geluid), 8820)]     # stukjes van 50 ms, veel sneller dan echt
    a, uit = NepAnalyse(), NepUitgang()
    d = bl.Doorgever(a, uit, voorsprong=0.4)
    rij = list(blokken)
    grootste = []

    def lees():
        grootste.append(d.in_rij)
        return rij.pop(0) if rij else b""

    d.draai(lees)
    assert bytes(uit.data) == geluid                    # alles, in de goede volgorde
    assert max(grootste) <= d.max_bytes                 # de rij blijft binnen de voorsprong
    # het moment dat de analyse krijgt, is het moment dat het stukje echt klinkt
    afwijking = [abs(t - eind) for (_, t, _), eind in zip(a.gevoerd, uit.eind)]
    assert max(afwijking) < 0.06, afwijking
    # en dat is ~0,4 s nadat het gelezen (en geanalyseerd) werd
    voorsprong = [t - gelezen for _, t, gelezen in a.gevoerd[10:]]
    assert 0.3 < float(np.median(voorsprong)) < 0.5, voorsprong


def test_voorvullen_als_de_aanvoer_niet_sneller_is_dan_afspelen():
    """Levert de bron maar in echte tijd (niet sneller), dan wacht het afspelen tot de voorsprong er echt is,
    en kloppen de tijden die de analyse krijgt toch met wat je hoort (het licht schuift mee)."""
    geluid = klikken(2.0)
    blokken = [geluid[i:i + 4410] for i in range(0, len(geluid), 4410)]     # 25 ms per blok, in echte tijd
    a, uit = NepAnalyse(), NepUitgang()
    d = bl.Doorgever(a, uit, voorsprong=1.0)
    rij = list(blokken)
    start = time.time()

    def lees():
        if not rij:
            return b""
        time.sleep(0.025)
        return rij.pop(0)

    d.draai(lees)
    assert bytes(uit.data) == geluid
    eerste_geluid = uit.eind[0] - 4410 / BPS
    assert 0.9 < eerste_geluid - start < 1.4                # pas na ~1 s voorvullen begint het geluid
    soorten = [m["soort"] for _, m in a.berichten]
    assert soorten[:2] == ["pauze", "verder"]               # licht: stil tijdens voorvullen, dan verder
    t_pauze = a.berichten[0][1]["t"]
    t_verder = a.berichten[1][0]
    # wat de analyse kreeg (zonder de verschuiving) + hoe lang het voorvullen duurde = wanneer je het hoort
    afwijking = [abs(t + (t_verder - t_pauze) - eind) if t >= t_pauze else 0
                 for (_, t, _), eind in zip(a.gevoerd, uit.eind) if t < t_verder]
    assert afwijking and max(afwijking) < 0.08, max(afwijking)


def test_doorgever_zonder_geluidskaart_houdt_het_tempo():
    class Kapot(NepUitgang):
        def start(self):
            raise OSError("geen geluidskaart")

    a, meldingen = NepAnalyse(), []
    rij = [bytes(8820)] * 10          # 0,5 s
    start = time.time()
    d = bl.Doorgever(a, Kapot(), 0.2, melding=lambda: meldingen.append(d.fout))
    d.draai(lambda: rij.pop(0) if rij else b"")
    assert time.time() - start > 0.4
    assert len(a.gevoerd) == 10
    assert d.fout == "geen geluidskaart" and not d.speelt and meldingen == ["geen geluidskaart"]


def test_foutmeldingen_in_gewone_woorden():
    log = ["[2026 WARN  librespot_discovery::server] Discovery server failed to start: Address in use (os error 98)",
           "[2026 ERROR librespot] Discovery is unavailable and no credentials provided."]
    assert spotify.foutmelding(log, 1).startswith("Kan niet als speaker op het netwerk verschijnen (Address in use")
    assert spotify.foutmelding([], 3) == "de speaker stopte (code 3)"


def test_spotify_instellingen_worden_gecontroleerd():
    e = Engine(None)
    assert e.data["spotify"]["aan"] is None and e.data["spotify"]["voorsprong"] == 8.0
    nieuw = e.normaliseer({"versie": 3, "spotify": {"aan": True, "naam": "  Wagen   1 ", "voorsprong": 99}})
    assert nieuw["spotify"] == {"aan": True, "naam": "Wagen 1", "apparaat": None, "voorsprong": 20.0, "zeroconf_poort": 0}
    oud = e.normaliseer({"versie": 3, "spotify": {"aan": True, "voorsprong": 4.0}, "show": {"energie": {"aan": False}}})
    assert oud["spotify"]["voorsprong"] == 8.0 and oud["show"]["energie"]["aan"]     # eenmalig naar de nieuwe standaard
    assert "spotify" not in e.export()


NEP_SPEAKER = """#!{python}
# Doet zich voor als dmxdesk-spotify: berichten [soort][lengte][inhoud] op stdout, commando's op stdin.
# Geluid: links = 1000 * nummer, rechts = het hoeveelste stukje (50 ms) van het nummer (zo zie je wat er klinkt).
import json, os, struct, sys, threading, time
uit = sys.stdout.buffer
lock = threading.RLock()
toestand = {{"nummer": 1, "pauze": False, "pos": 0, "verzoek": 0}}
LENGTE = int(float(os.environ.get("NEP_LENGTE", "1000")) * 20)       # stukjes van 50 ms per nummer
open(os.environ["NEP_ARGS"], "w").write(json.dumps(sys.argv[1:]))
log = open(os.environ["NEP_ARGS"] + ".log", "w")

def bericht(soort, inhoud=b""):
    with lock:
        uit.write(soort + struct.pack("<I", len(inhoud)) + inhoud)
        uit.flush()

def e(**kw):
    bericht(b"E", json.dumps(kw).encode())

def nummer(n, laden=True):
    with lock:
        toestand["verzoek"] += 1
        toestand["nummer"], toestand["pos"] = n, 0
        v = toestand["verzoek"]
        e(t="verzoek", verzoek=v)
        if laden:                                   # (vanzelf volgend nummer: al vooraf geladen, geen 'laden')
            e(t="laden", verzoek=v, id="spotify:track:%d" % n, pos=0)
        e(t="nummer", id="spotify:track:%d" % n, naam="Nummer %d" % n, artiesten=["DJ Test"], album="A", hoes=None,
          duur=LENGTE * 50)
        e(t="speelt", verzoek=v, id="spotify:track:%d" % n, pos=0)

def commandos():
    for regel in sys.stdin:
        c = regel.split()
        log.write("%.3f %s\\n" % (time.time(), regel.strip())); log.flush()
        with lock:
            v, p = toestand["verzoek"], toestand["pos"] * 50
            if c[0] == "pause":
                toestand["pauze"] = True; e(t="pauze", verzoek=v, id="x", pos=p)
            elif c[0] == "play":
                toestand["pauze"] = False; e(t="speelt", verzoek=v, id="x", pos=p)
            elif c[0] == "next":
                nummer(toestand["nummer"] + 1)
            elif c[0] == "seek":
                toestand["pos"] = int(c[1]) // 50; e(t="gespoeld", verzoek=v, pos=toestand["pos"] * 50)
            elif c[0] == "volume":
                e(t="volume", v=int(c[1]))
    os._exit(0)          # stdin dicht: DMXDesk is weg

e(t="klaar", naam="x", volume=100)
e(t="verbonden", gebruiker="casper")
nummer(1)
threading.Thread(target=commandos, daemon=True).start()
while True:
    with lock:
        if not toestand["pauze"]:
            if toestand["pos"] >= LENGTE:           # einde: vanzelf door naar het volgende nummer
                e(t="einde", verzoek=toestand["verzoek"])
                nummer(toestand["nummer"] + 1, laden=False)
            bericht(b"A", struct.pack("<hh", 1000 * toestand["nummer"], toestand["pos"]) * 2205)    # 50 ms stereo
            toestand["pos"] += 1
    time.sleep(0.02 if toestand["pauze"] else 0.001)            # (decoderen van het volgende stukje)
"""


def nep_speaker(tmp_path, monkeypatch, lengte=None):
    """Start-klaar: nep-speaker en nep-geluidskaart. Geeft de lijst (tijd, links, rechts) van wat er klonk."""
    nep = tmp_path / "dmxdesk-spotify"
    nep.write_text(NEP_SPEAKER.format(python=sys.executable))
    nep.chmod(0o755)
    monkeypatch.setenv("DMXDESK_SPEAKER", str(nep))
    monkeypatch.setenv("NEP_ARGS", str(tmp_path / "args.json"))
    if lengte:
        monkeypatch.setenv("NEP_LENGTE", str(lengte))
    monkeypatch.setattr(spotify.paden, "gebruikers_map", lambda: str(tmp_path))

    geschreven = []                                  # (tijd, links, rechts) van alles wat naar de luidspreker ging

    class NepStream:
        latency = 0.02

        def __init__(self, **kw):
            assert kw["samplerate"] == bl.SR and kw["channels"] == 2 and kw["dtype"] == "int16"

        def start(self):
            pass

        def write(self, data):
            time.sleep(len(data) / BPS)
            links, rechts = np.frombuffer(data[:4], dtype="<i2")
            geschreven.append((time.time(), int(links), int(rechts)))

        def stop(self):
            pass

        def close(self):
            pass

    apparaat = {"name": "Luidspreker", "max_output_channels": 2, "hostapi": 0, "default_high_output_latency": 0.1}
    monkeypatch.setattr(spotify, "sd", types.SimpleNamespace(
        RawOutputStream=NepStream, query_hostapis=lambda: [{"name": "Nep"}],
        query_devices=lambda i=None: apparaat if i is not None else [apparaat],
        default=types.SimpleNamespace(device=(0, 0))))
    return geschreven


def wacht(voorwaarde, sec=8):
    eind = time.time() + sec
    while time.time() < eind:
        if voorwaarde():
            return True
        time.sleep(0.02)
    return False


def opdrachten(tmp_path):
    """(tijd, opdracht) die de nep-speaker binnenkreeg."""
    try:
        regels = (tmp_path / "args.json.log").read_text().splitlines()
    except OSError:
        return []
    return [(float(r.split(" ", 1)[0]), r.split(" ", 1)[1]) for r in regels if " " in r]


@pytest.mark.skipif(sys.platform == "win32", reason="nep-speaker is een script met #!")
def test_speler_pauze_volgende_en_volume_werken_meteen(tmp_path, monkeypatch):
    geschreven = nep_speaker(tmp_path, monkeypatch)
    e = Engine(None)
    e.data["spotify"].update(aan=True, naam="Test Wagen", voorsprong=3.0)
    sp = spotify.SpotifySpeaker(e)
    assert spotify.uitvoer_apparaten() == [{"naam": "Luidspreker (Nep)", "standaard": True}]
    sp.bijwerken()
    try:
        st = lambda: e.status_info()["spotify"]
        assert wacht(lambda: st()["speler"]["naam"] == "Nummer 1" and len(geschreven) > 5)
        assert st()["verbonden"] and st()["speler"]["artiesten"] == ["DJ Test"] and st()["speler"]["speelt"]
        args = json.loads((tmp_path / "args.json").read_text())
        assert args[args.index("--name") + 1] == "Test Wagen"
        assert wacht(lambda: sp.doorgever.in_rij > 2 * bl.Doorgever.BPS)     # voorsprong opgebouwd (3 s rij)

        # pauze: meteen stil (niet pas na 3 s), en de show weet het
        sp.commando("pause")
        assert wacht(lambda: e.pauze_sinds is not None, 2)
        t_pauze = time.time()
        time.sleep(0.4)
        assert not [t for t, *_ in geschreven if t > t_pauze + 0.15]
        assert not st()["speler"]["speelt"]
        laatste = geschreven[-1][2]
        # Spotify stond 3 s verder (zoveel las hij vooruit): terug naar wat je hoorde
        seeks = [int(o.split()[1]) for _, o in opdrachten(tmp_path) if o.startswith("seek")]
        assert seeks and abs(seeks[-1] - (laatste + 1) * 50) <= 100, (seeks, laatste)
        sp.commando("play")
        assert wacht(lambda: [t for t, *_ in geschreven if t > t_pauze + 0.4], 2)
        assert e.pauze_sinds is None
        na = [r for t, _, r in geschreven if t > t_pauze + 0.4]
        assert abs(na[0] - (laatste + 1)) <= 2, (laatste, na[:5])          # gaat verder waar hij was
        assert wacht(lambda: sp.doorgever.vooruit() > 2.5, 3)                 # en de voorsprong is er weer

        # volgende: het nieuwe nummer is meteen te horen (de wachtrij met 3 s van het oude gaat weg)
        t_volgende = time.time()
        sp.commando("next")
        assert wacht(lambda: any(w == 2000 for _, w, _ in geschreven[-3:]), 2)
        assert time.time() - t_volgende < 1.0
        assert wacht(lambda: st()["speler"]["naam"] == "Nummer 2", 2)

        # volume: meteen zachter (derde macht: 50% = 1/8)
        sp.commando("volume", 50)
        assert wacht(lambda: geschreven[-1][1] == int(2000 * spotify.versterking(50)), 2)
        assert st()["speler"]["volume"] == 50
        proc = sp.proc
    finally:
        sp.stop()
    assert proc.poll() is not None                      # de speaker is gestopt (invoer dicht)
    assert not e.status_info()["spotify"]["aan"]


def test_opbouw_naar_een_drop_die_eraan_komt():
    """Met voorsprong weet de lichtman dat de drop eraan komt: opbouw op de maat, gat, flits, vol gas."""
    e = Engine(None)
    e.bpm_t0 = 0.0
    nu = time.time()
    drop = nu + 6.0
    vertraging = e.data["show"]["beat"]["vertraging_connect"] / 1000.0
    for i in range(-100, 120):                       # metingen van 10 s terug tot 12 s vooruit, elke 0,1 s
        t = nu + i / 10
        kick = 1.0 if t >= drop - vertraging else 0.0
        e.beat_bericht({"soort": "energie", "bron": "connect", "t": t, "kt": t, "kick": kick,
                        "e": 0.8 if kick else 0.2 + 0.03 * max(0, i)})
    e.beat_bericht({"soort": "drop", "bron": "connect", "t": drop - vertraging})
    e.render(nu)
    assert e.lm["sectie"] == "opbouw"
    voortgang, helder = [], []
    for i in range(50):                              # laatste 5 s voor de drop
        t = drop - 5.0 + i * 0.1
        e.render(t)
        if t < drop - 0.35:
            assert e.opbouw is not None
            voortgang.append(e.opbouw)
            helder.append(sum(e.frames[1]))
    assert voortgang == sorted(voortgang) and voortgang[-1] > 0.9
    assert len(set(helder)) > 3                      # knippert steeds sneller
    e.render(drop - 0.1)
    assert e.gat and [e.frames[1][k] for k in (0, 4, 8, 12)] == [0, 0, 0, 0]   # vlak voor de drop: dimmers dicht
    e.render(drop + 0.1)
    assert e.drop_nu and e.opbouw is None            # de flits
    e.render(drop + 2.0)
    assert e.lm["sectie"] == "drop" and e.punch > 0.4


@pytest.mark.skipif(sys.platform == "win32", reason="nep-speaker is een script met #!")
def test_vanzelf_volgend_nummer_speelt_uit_en_spotify_loopt_gelijk(tmp_path, monkeypatch):
    """Een nummer dat vanzelf begint: het vorige speelt helemaal uit (geen gat, niets afgekapt), en Spotify
    wordt vlak voor het nieuwe nummer teruggezet, zodat zijn tijd klopt met wat je hoort."""
    geschreven = nep_speaker(tmp_path, monkeypatch, lengte=5)       # nummers van 5 s
    e = Engine(None)
    e.data["spotify"].update(aan=True, naam="Test Wagen", voorsprong=3.0)
    sp = spotify.SpotifySpeaker(e)
    sp.bijwerken()
    try:
        assert wacht(lambda: sum(1 for _, w, _ in geschreven if w == 2000) > 30, 15)
        assert e.status_info()["spotify"]["speler"]["naam"] == "Nummer 2"
    finally:
        sp.stop()
    een = [r for _, w, r in geschreven if w == 1000]
    twee = [(t, r) for t, w, r in geschreven if w == 2000]
    assert een == list(range(100)), een[-5:]                         # nummer 1 helemaal, zonder sprong of herhaling
    assert [r for _, r in twee] == list(range(len(twee))), [r for _, r in twee][:10]   # nummer 2 vanaf het begin
    t_einde = max(t for t, w, _ in geschreven if w == 1000)
    assert twee[0][0] - t_einde < 0.2                                  # geen stilte ertussen
    seeks = [(t, o) for t, o in opdrachten(tmp_path) if o.startswith("seek")]
    assert len(seeks) == 1 and seeks[0][1] == "seek 0", seeks
    assert 0.3 < twee[0][0] - seeks[0][0] < 1.6, twee[0][0] - seeks[0][0]   # vlak voordat je hem hoort


def test_speaker_leert_opbouw_en_drop_per_nummer(tmp_path, monkeypatch):
    """OPBOUW en DROP gedrukt: onthouden op welke plek in dit nummer; de volgende keer gaat het vanzelf."""
    monkeypatch.setattr(spotify.paden, "gebruikers_map", lambda: str(tmp_path))
    e = Engine(None)
    sp = spotify.SpotifySpeaker(e)
    sp.doorgever = types.SimpleNamespace(gespeeld=0)
    sp.speler.update(id="spotify:track:7", naam="Hardstyle", speelt=True)

    def op(sp, ms):                   # je hoort nu dit stuk van het nummer
        sp.doorgever.gespeeld = sp.gespeeld_bij + int((ms - sp.pos_basis) * BPS / 1000)

    op(sp, 60000)
    e.lichtman_knop("opbouw")
    op(sp, 75000)
    e.lichtman_knop("drop")
    op(sp, 75800)
    e.lichtman_knop("drop")           # nog een keer (iets later): vervangt de vorige
    opgeslagen = json.loads((tmp_path / "geleerd.json").read_text())
    assert opgeslagen["spotify:track:7"]["momenten"] == [[60000, 75800]]
    assert len(sp.geleerd["spotify:track:7"]["momenten"]) == 1

    # later, ander moment: hetzelfde nummer klinkt vanaf 50 s
    e2 = Engine(None)
    sp2 = spotify.SpotifySpeaker(e2)
    sp2.doorgever = types.SimpleNamespace(gespeeld=0)
    sp2.speler.update(id="spotify:track:7", speelt=True)
    sp2.pos_basis = 50000
    nu = time.time()
    sp2._plan_geleerd(True)
    st = e2.lichtman.stand(nu + 20.0)                       # 10 s van de 15,8 s opbouw
    assert st["sectie"] == "opbouw" and 0.55 < st["opbouw"] < 0.72, st
    assert e2.lichtman.stand(nu + 26.0)["flits"]            # de drop op 75,8 s
    sp2.vergeet_nummer()
    assert json.loads((tmp_path / "geleerd.json").read_text()) == {}
    with pytest.raises(ValueError):
        sp2.vergeet_nummer()
