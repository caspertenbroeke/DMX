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
import json, os, struct, sys, threading, time
uit = sys.stdout.buffer
lock = threading.Lock()
toestand = {{"nummer": 1, "pauze": False}}
open(os.environ["NEP_ARGS"], "w").write(json.dumps(sys.argv[1:]))

def bericht(soort, inhoud=b""):
    with lock:
        uit.write(soort + struct.pack("<I", len(inhoud)) + inhoud)
        uit.flush()

def e(**kw):
    bericht(b"E", json.dumps(kw).encode())

def nummer(n):
    e(t="laden", verzoek=n, id="spotify:track:%d" % n, pos=0)
    e(t="nummer", id="spotify:track:%d" % n, naam="Nummer %d" % n, artiesten=["DJ Test"], album="A", hoes=None, duur=60000)
    e(t="speelt", verzoek=n, id="spotify:track:%d" % n, pos=0)

def commandos():
    for regel in sys.stdin:
        c = regel.split()
        if c[0] == "pause":
            toestand["pauze"] = True; e(t="pauze", verzoek=toestand["nummer"], id="x", pos=0)
        elif c[0] == "play":
            toestand["pauze"] = False; e(t="speelt", verzoek=toestand["nummer"], id="x", pos=0)
        elif c[0] == "next":
            with lock:
                toestand["nummer"] += 1
            nummer(toestand["nummer"])
        elif c[0] == "volume":
            e(t="volume", v=int(c[1]))
    os._exit(0)          # stdin dicht: DMXDesk is weg

e(t="klaar", naam="x", volume=100)
e(t="verbonden", gebruiker="casper")
nummer(1)
threading.Thread(target=commandos, daemon=True).start()
while True:
    if toestand["pauze"]:
        time.sleep(0.02); continue
    waarde = 1000 * toestand["nummer"]          # nummer 1: 1000, nummer 2: 2000 (zo zie je wat er klinkt)
    bericht(b"A", struct.pack("<h", waarde) * 2 * 2205)    # 50 ms stereo
    time.sleep(0.001)                                          # (decoderen van het volgende stukje)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="nep-speaker is een script met #!")
def test_speler_pauze_volgende_en_volume_werken_meteen(tmp_path, monkeypatch):
    nep = tmp_path / "dmxdesk-spotify"
    nep.write_text(NEP_SPEAKER.format(python=sys.executable))
    nep.chmod(0o755)
    monkeypatch.setenv("DMXDESK_SPEAKER", str(nep))
    monkeypatch.setenv("NEP_ARGS", str(tmp_path / "args.json"))
    monkeypatch.setattr(spotify.paden, "gebruikers_map", lambda: str(tmp_path))

    geschreven = []                                  # (tijd, eerste sample) van alles wat naar de luidspreker ging

    class NepStream:
        latency = 0.02

        def __init__(self, **kw):
            assert kw["samplerate"] == bl.SR and kw["channels"] == 2 and kw["dtype"] == "int16"

        def start(self):
            pass

        def write(self, data):
            time.sleep(len(data) / BPS)
            geschreven.append((time.time(), int(np.frombuffer(data[:2], dtype="<i2")[0])))

        def stop(self):
            pass

        def close(self):
            pass

    apparaat = {"name": "Luidspreker", "max_output_channels": 2, "hostapi": 0, "default_high_output_latency": 0.1}
    monkeypatch.setattr(spotify, "sd", types.SimpleNamespace(
        RawOutputStream=NepStream, query_hostapis=lambda: [{"name": "Nep"}],
        query_devices=lambda i=None: apparaat if i is not None else [apparaat],
        default=types.SimpleNamespace(device=(0, 0))))

    def wacht(voorwaarde, sec=8):
        eind = time.time() + sec
        while time.time() < eind:
            if voorwaarde():
                return True
            time.sleep(0.02)
        return False

    e = Engine(None)
    e.data["spotify"].update(aan=True, naam="Test Wagen", voorsprong=3.0)
    sp = spotify.SpotifySpeaker(e)
    assert spotify.uitvoer_apparaten() == [{"naam": "Luidspreker (Nep)", "standaard": True}]
    sp.bijwerken()
    try:
        st = lambda: e.extra_status["spotify"]
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
        assert not [t for t, _ in geschreven if t > t_pauze + 0.15]
        assert not st()["speler"]["speelt"]
        sp.commando("play")
        assert wacht(lambda: [t for t, _ in geschreven if t > t_pauze + 0.4], 2)
        assert e.pauze_sinds is None

        # volgende: het nieuwe nummer is meteen te horen (de wachtrij met 3 s van het oude gaat weg)
        t_volgende = time.time()
        sp.commando("next")
        assert wacht(lambda: any(w == 2000 for _, w in geschreven[-3:]), 2)
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
    assert not e.extra_status["spotify"]["aan"]


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
    assert e.lm["sectie"] == "drop" and e.punch > 0.5
