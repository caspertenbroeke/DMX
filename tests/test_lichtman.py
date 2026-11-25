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
    assert secties_hard and secties_hard <= {"druk", "drop", "extreem"}, secties_hard
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
    assert sectie[5.0] in ("groove", "druk", "drop")
    assert sectie[16.0] in ("break", "rustig")
    assert sectie[round(drop - 2.0, 2)] == "opbouw"
    assert sectie[round(drop + 1.0, 2)] in ("drop", "extreem")
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


def test_pauze_schuift_alles_mee_en_ander_nummer_vergeet():
    e = Engine(None)
    nu = time.time()
    v = e.data["show"]["beat"]["vertraging_connect"] / 1000.0
    e.beat_bericht({"soort": "energie", "bron": "connect", "t": nu + 5, "kt": nu + 5, "kick": 0.0, "e": 0.3})
    e.beat_bericht({"soort": "drop", "bron": "connect", "t": nu + 6})
    t0 = e.bpm_t0
    e.muziek_pauze(nu - 2.0)                      # 2 s geleden op pauze gezet
    e.render(nu)
    assert e.lm["sectie"] == "pauze"
    e.muziek_hervat()
    assert e.pauze_sinds is None
    assert abs(e.bpm_t0 - t0 - 2.0) < 0.1          # de maat schuift mee
    assert abs(e.lichtman.drops[-1] - (nu + 6 + v + 2.0)) < 0.1
    assert abs(e.lichtman.punten[-1][0] - (nu + 5 + v + 2.0)) < 0.1
    e.muziek_vergeet(time.time())                 # volgende nummer: de oude toekomst geldt niet meer
    assert not e.lichtman.drops and not e.lichtman.punten


def _lm_nummer(lm, van, tot, kick, abs_, rel=0.5, e=0.6):
    for i in range(int((tot - van) * 10)):
        lm.punt(van + i / 10, kick, e, rel, abs_)


def test_meer_stappen_en_de_schuif_maakt_het_rustiger():
    """Rustig nummer met kick = groove; luider/voller refrein = hoger; met de schuif laag wordt dat minder wild."""
    uitkomst = {}
    for wild in (0.2, 0.7, 1.0):
        lm = Lichtman()
        _lm_nummer(lm, 0, 20, kick=1.0, abs_=0.2, rel=0.5)          # couplet: rustig nummer mét kick
        _lm_nummer(lm, 20, 40, kick=1.0, abs_=0.65, rel=0.85)       # refrein: voller en harder
        couplet = [lm.stand(t, wild)["sectie"] for t in (8, 12, 16)]
        refrein = [lm.stand(t, wild)["sectie"] for t in (30, 34, 38)]
        uitkomst[wild] = (couplet, refrein)
    for wild, (couplet, refrein) in uitkomst.items():
        assert set(couplet) <= ({"groove"} if wild <= 0.7 else {"groove", "druk"}), (wild, couplet)
    rang = {s: i for i, s in enumerate(["groove", "druk", "drop", "extreem"])}
    assert rang[uitkomst[0.7][1][-1]] >= rang["druk"]
    assert rang[uitkomst[0.2][1][-1]] < rang[uitkomst[1.0][1][-1]]     # schuif laag = minder snel vol gas


def test_strobe_bij_de_tweede_drop_van_een_hard_nummer():
    e = Engine(None)
    e.bpm_t0 = 0.0
    nu = time.time()
    v = e.data["show"]["beat"]["vertraging_connect"] / 1000.0
    for i in range(700):                                            # 70 s: hard nummer met twee breaks
        t = nu - 20 + i / 10
        kick = 0.0 if (5 < t - nu < 15 or 30 < t - nu < 40) else 1.0
        e.beat_bericht({"soort": "energie", "bron": "connect", "t": t, "kt": t, "kick": kick, "e": 0.8,
                        "rel": 0.6, "abs": 0.85})
    for d in (15, 40):
        e.beat_bericht({"soort": "drop", "bron": "connect", "t": nu + d - v})
    tel = 60.0 / e.data["show"]["bpm"]
    e.bpm_t0 = nu + 40 + 4 * tel + 0.3 - 16 * tel      # daar valt tel 16 van 32: geen 'af en toe'-strobeklap
    e.render(nu + 15 + 1.0)
    assert not e.drop_nu                    # 1e drop: alleen de korte flits (0,45 s), daarna geen strobe
    e.render(nu + 40 + 1.0)
    assert e.drop_nu                        # 2e drop van een hard nummer: strobe
    e.render(nu + 40 + 4 * tel + 0.3)
    assert not e.drop_nu                    # na 4 tellen weer uit
    e.data["show"]["energie"]["strobe"] = False
    e.render(nu + 40 + 1.0)
    assert not e.drop_nu                    # uit te zetten


def test_korte_break_is_geen_drop():
    """Een fill of korte break (een paar tellen geen kick) geeft geen DROP; een echte breakdown wel."""
    y = M.achter_elkaar(M.hardstyle(sec=10), M.breakdown(sec=4), M.hardstyle(sec=8, seed=7),
                        M.breakdown(sec=12), M.hardstyle(sec=8, seed=9))
    drops = [m["t"] for m in analyseer(y) if m["soort"] == "drop"]
    assert len(drops) == 1 and abs(drops[0] - 34.0) < 0.15, drops      # alleen na de breakdown van 12 s
    lm = Lichtman()
    for i in range(100):                                               # kick zat er gewoon in
        lm.punt(i / 10, 1.0, 0.8)
    lm.drop(10.0)
    assert not lm.drops


def test_knop_opbouw_blijft_aan_tot_drop():
    """OPBOUW blijft ingedrukt en bouwt steeds verder op; DROP geeft de flits en vol gas (ook zonder analyse)."""
    e = Engine(None)
    gehoord = []
    e.bij_knop.append(lambda soort, t, aan: gehoord.append((soort, aan)))
    e.lichtman_knop("opbouw")
    nu = time.time()
    st = e.lichtman.stand(nu + 3.0)
    assert st["sectie"] == "opbouw" and st["hand"] and 0.3 < st["opbouw"] < 0.5, st
    assert e.lichtman.stand(nu + 12.0)["opbouw"] > st["opbouw"]           # steeds verder, tot DROP
    e.lichtman_knop("drop")
    nu = time.time()
    st = e.lichtman.stand(nu + 0.1)
    assert st["flits"] and st["sectie"] in ("drop", "extreem") and not st["hand"], st
    assert e.lichtman.stand(nu + 5.0)["sectie"] in ("drop", "extreem")
    assert gehoord == [("opbouw", True), ("drop", False)]
    with pytest.raises(ValueError):
        e.lichtman_knop("iets")


def test_geleerde_momenten_vervangen_en_drop_knop_stopt_opbouw():
    lm = Lichtman()
    lm.leer([(110.0, 125.0)], nu=100.0)              # eerst (even) de plek van het vorige nummer
    lm.leer([(130.0, 140.0), (None, 200.0)], nu=100.0)   # meteen daarna de juiste: vervangt
    assert lm.geleerd == [(130.0, 140.0)] and sorted(lm.drops) == [140.0, 200.0]
    assert lm.stand(135.0)["sectie"] == "opbouw"
    lm.knop_drop(136.0)                               # zelf eerder op DROP: de geleerde opbouw stopt
    st = lm.stand(137.0)
    assert st["sectie"] in ("drop", "extreem") and not lm.geleerd
    lm.verschuif(150.0, 5.0)                          # pauze: de geleerde drop schuift mee
    lm.vergeet_geleerd(150.0)
    assert list(lm.drops) == [136.0]                  # de geleerde weg, de gedrukte blijft


def test_lijn_van_20_lampen_en_bal_cues():
    e = Engine(None)
    e.data["show"]["energie"]["aan"] = False                      # alleen het patroon bekijken
    r = e.voeg_lijn_toe(20, "drgb_4")
    lijn = sorted([f for f in e.data["fixtures"] if f["groep"] == "Lijn"], key=lambda f: f["x"])
    assert len(lijn) == 20 and r["adres"] == 71 and lijn[-1]["adres"] == 71 + 19 * 4      # na de rookmachine (70)
    assert lijn[0]["x"] < lijn[-1]["x"]
    groep, namen = e.maak_bal_cues()
    assert groep == "Lijn" and len(namen) == 8 and e.data["cuelijsten"]["Bal"]["stappen"][0]["scene"] == "Bal wit"
    e.cue_start("Bal")
    tel = 60 / e.data["show"]["bpm"]
    plekken = []
    for b in (0.25, 0.5, 0.75, 1.5):                               # 1 beat = de hele lijn over, dan terug
        frame = e.render(e.bpm_t0 + b * tel)[1]
        helder = [frame[f["adres"] - 1] for f in lijn]
        kop = max(range(20), key=lambda k: helder[k])
        assert helder[kop] > 200 and sum(h > 200 for h in helder) <= 2, helder   # één felle bal
        assert sum(h > 0 for h in helder) <= 6                     # met een korte veeg, de rest donker
        plekken.append(kop)
    assert plekken[0] < plekken[1] < plekken[2] and plekken[3] < plekken[2]       # vliegt heen, en weer terug
    assert abs(plekken[1] - 9.5) <= 1                              # op een halve beat al halverwege de zaal
    par1 = next(f for f in e.data["fixtures"] if f["naam"] == "Par 1")
    assert e.render(e.bpm_t0 + 0.5 * tel)[1][par1["adres"] - 1] > 0     # de andere lampen doen gewoon hun ding
    with pytest.raises(ValueError):
        e.maak_bal_cues("Bestaat niet")
    with pytest.raises(ValueError):
        e.voeg_lijn_toe(30, "ledbar_8")                            # 30 × 24 kanalen past niet in één universe
    r = e.voeg_lijn_toe(20, "ledbar_8", "Bars")                    # 20 × 24 = 480: in universe 2
    assert r["universe"] == 2 and r["adres"] == 1


def test_scene_gaat_voor_de_auto_show_tot_je_hem_loslaat():
    e = Engine(None)
    e.voeg_lijn_toe(20, "drgb_4")
    e.maak_bal_cues()
    e.data["show"]["auto"]["aan"] = True
    e.laad_scene("Bal snel rood")
    assert e.data["show"]["auto"]["aan"]                       # de auto-show gaat gewoon door
    globaal = []
    for k in range(6):                                         # auto-show kiest een paar keer iets nieuws
        e.auto_stap(k * 40.0)
        globaal.append(e.data["show"]["intensiteit"]["modus"])
    lijn = e.data["show"]["lagen"]["Lijn"]
    assert lijn["intensiteit"]["modus"] == "bal" and lijn["kleur"]["palet"] == ["#ff0000"]   # de lijn is van de scène
    assert len(set(globaal)) > 1                               # de rest wisselt wel
    lijn["kleur"]["palet"] = ["#00ff00"]                       # zelf de kleur aangepast, en bewaard
    e.scene_opslaan("Bal snel rood", "effecten")
    sc = e.data["scenes"]["Bal snel rood"]
    assert set(sc["effecten"]) == {"lagen"} and sc["effecten"]["lagen"]["Lijn"]["kleur"]["palet"] == ["#00ff00"]
    e.scene_loslaten()                                         # "tot ik het zeg": nu doet de lijn weer mee
    assert "Lijn" not in e.data["show"]["lagen"] and e.data["show"]["auto"]["aan"]

    # een scène voor alle lampen: zolang hij geladen is, verandert de auto-show niets; daarna weer wel
    e.data["show"]["intensiteit"]["modus"] = "chase"
    e.scene_opslaan("Alles chase", "effecten")
    e.laad_scene("Alles chase")
    for k in range(6, 10):
        e.auto_stap(k * 40.0)
    assert e.data["show"]["intensiteit"]["modus"] == "chase" and e.data["show"]["auto"]["aan"]
    e.scene_loslaten()
    import random
    random.seed(3)
    na = []
    for k in range(10, 16):
        e.auto_stap(k * 40.0)
        na.append(e.data["show"]["intensiteit"]["modus"])
    assert any(m != "chase" for m in na)                      # losgelaten: de auto-show pakt het weer op
    e.wijzig_show({"lagen": {"Pars": {"eigen": True}}})
    e.wijzig_show({"lagen": {"Pars": {"auto": False}}})        # per laag kan de auto-show er ook vast af
    assert e.data["show"]["lagen"]["Pars"]["auto"] is False


def test_laag_opslaan_als_scene_neemt_alleen_die_lampen():
    import random
    random.seed(5)
    e = Engine(None)
    e.voeg_lijn_toe(20, "drgb_4")
    e.wijzig_show({"lagen": {"Lijn": {"eigen": True, "intensiteit": {"modus": "bal"}, "kleur": {"modus": "vast", "palet": ["#ff0000"]}}}})
    e.scene_opslaan("Mijn lijn", "effecten", laag="Lijn")
    assert set(e.data["scenes"]["Mijn lijn"]["effecten"]) == {"lagen"}
    assert set(e.data["scenes"]["Mijn lijn"]["effecten"]["lagen"]) == {"Lijn"}
    e.data["show"]["auto"]["aan"] = True
    e.laad_scene("Mijn lijn")
    rest = set()
    for k in range(8):
        e.auto_stap(k * 40.0)
        rest.add(e.data["show"]["intensiteit"]["modus"])
    assert len(rest) > 1 and e.data["show"]["lagen"]["Lijn"]["intensiteit"]["modus"] == "bal"
    # per ongeluk als 'alle lampen' bewaard: met 'alleen laag Lijn bewaren' weer goed te zetten
    e.scene_opslaan("Per ongeluk", "effecten")
    assert set(e.data["scenes"]["Per ongeluk"]["effecten"]) > {"lagen"}
    e.scene_opslaan("Per ongeluk", "effecten", laag="Lijn")
    assert set(e.data["scenes"]["Per ongeluk"]["effecten"]) == {"lagen"}
    with pytest.raises(ValueError):
        e.scene_opslaan("X", "effecten", laag="Pars")             # Pars heeft geen eigen patronen


def test_helderheid_per_laag_en_in_de_scene():
    e = Engine(None)
    e.data["show"]["energie"]["aan"] = False
    e.voeg_lijn_toe(4, "drgb_4")
    e.wijzig_show({"lagen": {"Lijn": {"eigen": True, "intensiteit": {"modus": "aan", "helderheid": 40}}},
                   "intensiteit": {"modus": "aan"}})
    lijn = next(f for f in e.data["fixtures"] if f["groep"] == "Lijn")
    par = next(f for f in e.data["fixtures"] if f["naam"] == "Par 1")
    frame = e.render(time.time())[1]
    assert 95 < frame[lijn["adres"] - 1] < 110 and frame[par["adres"] - 1] == 255     # 40% alleen voor de lijn
    e.scene_opslaan("Lijn zacht", "effecten", laag="Lijn")
    assert e.data["scenes"]["Lijn zacht"]["effecten"]["lagen"]["Lijn"]["intensiteit"]["helderheid"] == 40
