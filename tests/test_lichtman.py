"""De lichtman: een rustig nummer blijft rustig, hardstyle op hetzelfde tempo gaat los; opbouw en drop op tijd."""
import time

import numpy as np
import pytest

import muziek as M
from dmxdesk import beatluister as bl
from dmxdesk.engine import Engine
from dmxdesk.lichtman import Lichtman, profiel


def analyseer(y):
    berichten = []
    a = bl.Analyse("connect", zender=berichten.append)
    a.tempo = bl.NumpyTempo()
    for s in range(0, len(y), 4096):
        a.voer_mono(y[s:s + 4096], (s + len(y[s:s + 4096])) / M.SR)
    return berichten


def speel_af(y, voorsprong=8.0, stap=0.05):
    """Laat de motor de show draaien op dit nummer, met berichten die `voorsprong` s vooruit binnenkomen.
    Geeft per frame (tijd in het nummer, sectie, helderheid van de pars 0..1)."""
    berichten = sorted(analyseer(y), key=lambda m: m.get("t", 0))
    e = Engine(None)
    t0 = time.time()
    for m in berichten:
        for k in ("t", "kt"):
            if k in m:
                m[k] += t0
    vertraging = e.data["show"]["beat"]["vertraging_connect"] / 1000.0
    pars = [f for f in e.data["fixtures"] if f["groep"] == "Pars"]
    i, uit = 0, []
    for t in np.arange(0, len(y) / M.SR, stap):
        nu = t0 + t + vertraging
        while i < len(berichten) and berichten[i].get("t", 0) - voorsprong <= t0 + t:
            e.beat_bericht(berichten[i])
            i += 1
        frame = e.render(nu)[1]
        helder = np.mean([frame[f["adres"] - 1] / 255.0 for f in pars])
        uit.append((t, e.lm["sectie"] if e.lm else None, helder))
    return uit


def wildheid(frames, vanaf=4.0):
    """Gemiddelde helderheid en hoeveel de helderheid per seconde verandert (knipperen, chases)."""
    helder = np.array([h for t, _, h in frames if t >= vanaf])
    return float(helder.mean()), float(np.abs(np.diff(helder)).sum() / (len(helder) * 0.05))


@pytest.fixture(scope="module")
def rustig_en_hard():
    return speel_af(M.rustig(bpm=150, sec=20)), speel_af(M.hardstyle(bpm=150, sec=20))


def test_rustig_nummer_op_hoog_tempo_blijft_rustig(rustig_en_hard):
    rustig, hard = rustig_en_hard
    secties_rustig = {s for t, s, _ in rustig if t > 4}
    secties_hard = {s for t, s, _ in hard if t > 4}
    assert secties_rustig <= {"rustig", "break"}, secties_rustig
    assert secties_hard == {"drop"}, secties_hard
    top_rustig = np.percentile([h for t, _, h in rustig if t > 4], 95)
    top_hard = np.percentile([h for t, _, h in hard if t > 4], 95)
    assert top_hard > 0.9 and top_rustig < 0.7, (top_hard, top_rustig)   # hardstyle knalt vol open, rustig gedimd
    _, wild_rustig = wildheid(rustig)
    _, wild_hard = wildheid(hard)
    assert wild_hard > 4 * wild_rustig, (wild_hard, wild_rustig)         # en is veel wilder (punch op elke kick)
    assert wild_rustig > 0.01                                            # rustig staat niet stil: zachte golf


def test_opbouw_en_drop_op_tijd():
    stukken = [M.hardstyle(sec=10), M.breakdown(sec=12), M.opbouw(sec=14), M.hardstyle(sec=10, seed=9)]
    y = M.achter_elkaar(*stukken)
    drop = (10 + 12 + 14)
    berichten = analyseer(y)
    drops = [m["t"] for m in berichten if m["soort"] == "drop"]
    assert drops and abs(drops[-1] - drop) < 0.15, drops
    frames = speel_af(y)
    sectie = {round(t, 2): s for t, s, _ in frames}
    assert sectie[5.0] == "drop"
    assert sectie[16.0] in ("break", "rustig")
    assert sectie[round(drop - 2.0, 2)] == "opbouw"
    assert sectie[round(drop + 1.0, 2)] == "drop"
    # vlak voor de drop even donker, op de drop vol licht
    helder = {round(t, 2): h for t, _, h in frames}
    assert helder[round(drop - 0.1, 2)] == 0.0
    assert max(h for t, _, h in frames if drop <= t < drop + 0.4) > 0.9        # de flits (strobe)


def test_tempo_blijft_staan_tijdens_opbouw():
    """De snare-roffel in de opbouw gaat steeds sneller; de BPM mag daar niet op meelopen."""
    y = M.achter_elkaar(M.hardstyle(sec=12), M.opbouw(sec=14), M.hardstyle(sec=6, seed=9))
    berichten = sorted(analyseer(y), key=lambda m: m.get("t", 0))
    e = Engine(None)
    t0 = time.time() - 40
    bpms = []
    for m in berichten:
        for k in ("t", "kt"):
            if k in m:
                m[k] += t0
        e.beat_bericht(m)
        if m["soort"] == "beat" and 14 < m["t"] - t0 < 26:
            bpms.append(e.data["show"]["bpm"])
    assert bpms and max(bpms) - min(bpms) < 3 and abs(bpms[0] - 150) < 3, (min(bpms), max(bpms))


def test_lichtman_zonder_voorsprong_volgt_ook():
    """Via de microfoon (geen voorsprong) herkent hij de secties ook, alleen iets later."""
    lm = Lichtman()
    for i in range(200):
        t = i * 0.1
        lm.punt(t, 1.0 if t < 10 else 0.0, 0.8 if t < 10 else 0.15)
        st = lm.stand(t + 0.001)
    assert st["sectie"] == "break"
    assert profiel("rustig")["dim"] < profiel("drop")["dim"]
    assert profiel("drop", contrast=0.0)["stap"] == 1.0          # contrast 0: de lichtman doet (bijna) niets


def test_lagen_eigen_patronen():
    e = Engine(None)
    e.wijzig_show({"lagen": {"Pars": {"eigen": True, "intensiteit": {"modus": "chase", "snelheid": 1}}},
                   "intensiteit": {"modus": "aan"}})
    lg = e.data["show"]["lagen"]["Pars"]
    assert lg["eigen"] and lg["kleur"] == e.data["show"]["kleur"]      # nieuwe laag begint met de huidige instellingen
    pars = [f for f in e.data["fixtures"] if f["groep"] == "Pars"]
    aan = []
    for b in range(4):                                                  # chase binnen de 4 pars: elke beat een andere
        frame = e.render(e.bpm_t0 + (b + 0.5) * 60 / e.data["show"]["bpm"])[1]
        aan.append([frame[f["adres"] - 1] > 0 for f in pars])
    assert all(sum(r) == 1 for r in aan) and len({r.index(True) for r in aan}) == 4
    bar = next(f for f in e.data["fixtures"] if f["groep"] == "LED-bar")
    assert frame[bar["adres"] - 1] > 0                                  # de LED-bar volgt 'alle lampen': aan
    e.wijzig_show({"lagen": {"Pars": None}})
    assert "Pars" not in e.data["show"]["lagen"]
