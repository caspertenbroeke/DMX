import json
import sys
import threading
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
    assert spotify.foutmelding([], 3) == "librespot stopte (code 3)"


def test_spotify_instellingen_worden_gecontroleerd():
    e = Engine(None)
    assert e.data["spotify"]["aan"] is None and e.data["spotify"]["voorsprong"] == 4.0
    nieuw = e.normaliseer({"versie": 3, "spotify": {"aan": True, "naam": "  Wagen   1 ", "voorsprong": 99}})
    assert nieuw["spotify"] == {"aan": True, "naam": "Wagen 1", "apparaat": None, "voorsprong": 10.0, "zeroconf_poort": 0}
    assert "spotify" not in e.export()


NEP_LIBRESPOT = """#!{python}
import json, os, sys, time
open(os.environ["NEP_ARGS"], "w").write(json.dumps(sys.argv[1:]))
sys.stderr.write("[2026-01-01T00:00:00Z INFO  librespot_core::session] Authenticated as 'test' !\\n")
sys.stderr.write("[2026-01-01T00:00:01Z INFO  librespot_playback::player] Loading <Testnummer> with Spotify URI <spotify:track:1>\\n")
sys.stderr.flush()
sys.stdout.buffer.write(open(os.environ["NEP_GELUID"], "rb").read())
sys.stdout.flush()
time.sleep(60)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="nep-librespot is een script met #!")
def test_spotify_speaker_met_nep_librespot(tmp_path, monkeypatch):
    geluid = klikken(1.5)
    (tmp_path / "geluid.raw").write_bytes(geluid)
    nep = tmp_path / "librespot"
    nep.write_text(NEP_LIBRESPOT.format(python=sys.executable))
    nep.chmod(0o755)
    monkeypatch.setenv("DMXDESK_LIBRESPOT", str(nep))
    monkeypatch.setenv("NEP_ARGS", str(tmp_path / "args.json"))
    monkeypatch.setenv("NEP_GELUID", str(tmp_path / "geluid.raw"))
    monkeypatch.setattr(spotify.paden, "gebruikers_map", lambda: str(tmp_path))

    gespeeld = bytearray()
    klaar = threading.Event()

    class NepStream:
        latency = 0.02

        def __init__(self, **kw):
            assert kw["samplerate"] == bl.SR and kw["channels"] == 2 and kw["dtype"] == "int16"

        def start(self):
            pass

        def write(self, data):
            time.sleep(len(data) / BPS)
            gespeeld.extend(data)
            if len(gespeeld) >= len(geluid):
                klaar.set()

        def stop(self):
            pass

        def close(self):
            pass

    apparaat = {"name": "Luidspreker", "max_output_channels": 2, "hostapi": 0, "default_high_output_latency": 0.1}
    monkeypatch.setattr(spotify, "sd", types.SimpleNamespace(
        RawOutputStream=NepStream, query_hostapis=lambda: [{"name": "Nep"}],
        query_devices=lambda i=None: apparaat if i is not None else [apparaat],
        default=types.SimpleNamespace(device=(0, 0))))

    e = Engine(None)
    e.data["spotify"].update(aan=True, naam="Test Wagen", voorsprong=0.5)
    sp = spotify.SpotifySpeaker(e)
    assert spotify.uitvoer_apparaten() == [{"naam": "Luidspreker (Nep)", "standaard": True}]
    sp.bijwerken()
    try:
        assert klaar.wait(15), "het geluid kwam niet (helemaal) uit de luidspreker"
        assert bytes(gespeeld[:len(geluid)]) == geluid
        st = e.extra_status["spotify"]
        assert st["verbonden"] and st["nummer"] == "Testnummer" and st["aan"] and st["beschikbaar"]
        args = json.loads((tmp_path / "args.json").read_text())
        assert args[args.index("--name") + 1] == "Test Wagen"
        assert args[args.index("--backend") + 1] == "pipe"
        assert "connect" in e.luister                   # de analyse is bij de lichtshow aangekomen
        proc = sp.proc
    finally:
        sp.stop()
    assert proc.poll() is not None                      # librespot is gestopt
    assert not e.extra_status["spotify"]["aan"]


def test_opbouw_naar_een_drop_die_eraan_komt():
    e = Engine(None)
    e.data["show"]["energie"]["aan"] = True
    nu = time.time()
    e.beat_bericht({"soort": "energie", "bron": "connect", "t": nu + 2.0, "e": 0.9})
    e.beat_bericht({"soort": "drop", "bron": "connect", "t": nu + 3.0})
    e.render(nu)
    assert e.energie != 0.9                             # nog niet te horen
    e.render(nu + 2.1)
    assert e.energie == 0.9
    drop = nu + 3.0 + e.data["show"]["beat"]["vertraging_connect"] / 1000.0
    helder = []
    for i in range(40):                                 # laatste 2 seconden voor de drop: knipperen
        e.render(drop - 2.0 + i * 0.045)
        assert e.opbouw is not None and 0 <= e.opbouw < 1
        helder.append(sum(e.frames[1]))
    assert len(set(helder)) > 2
    e.render(drop - 0.1)
    assert e.opbouw is not None
    e.render(drop + 0.1)
    assert e.opbouw is None and e.drop_nu              # de flits
