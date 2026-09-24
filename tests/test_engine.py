import copy
import importlib.util
import json
import os
import time

import pytest

from dmxdesk.engine import Engine

HIER = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HIER)
PI_SHOW = os.path.join(ROOT, "pi", "show.json")


@pytest.fixture
def e():
    eng = Engine(None)
    eng.bpm_t0 = 1000.0
    return eng


def kanalen(e, naam, t=1000.0, u=1):
    """DMX-waarden van één lamp."""
    frames = e.render(t)
    f = next(x for x in e.data["fixtures"] if x["naam"] == naam)
    n = len(e.data["profielen"][f["profiel"]]["kanalen"])
    return list(frames[u][f["adres"] - 1:f["adres"] - 1 + n])


def test_standaardshow_rekent(e):
    frames = e.render(1000.0)
    assert set(frames) == {1}
    assert len(frames[1]) == 512
    assert any(frames[1])
    assert len(e.voorbeeld) == len(e.data["fixtures"])


def test_zelfde_uitvoer_als_versie_1():
    """De show van de carnavalswagen moet precies hetzelfde licht geven als DMXDesk 1."""
    spec = importlib.util.spec_from_file_location("oud", os.path.join(ROOT, "oud", "dmxdesk_v1.py"))
    oud = importlib.util.module_from_spec(spec)
    os.environ["DMXDESK_SHOW"] = PI_SHOW
    spec.loader.exec_module(oud)
    a, b = oud.Engine(), Engine(PI_SHOW)
    a.bpm_t0 = b.bpm_t0 = 5000.0
    for kleur in ("random", "chase", "fade", "regenboog", "wissel"):
        for inten in ("aan", "chase", "golf", "pingpong", "puls"):
            for eng in (a, b):
                eng.data["show"]["kleur"]["modus"] = kleur
                eng.data["show"]["intensiteit"]["modus"] = inten
            for i in range(30):
                t = 5000.0 + i / 30
                if i == 15:
                    a.hold["strobe"] = b.hold["strobe"] = t + 10
                assert bytes(a.render(t)) == bytes(b.render(t)[1]), (kleur, inten, i)
            a.hold["strobe"] = b.hold["strobe"] = 0.0


def test_migratie_v1():
    e = Engine(PI_SHOW)
    assert e.data["versie"] == 2
    assert e.data["uitgangen"][0]["soort"] == "opendmx"
    assert all(f["universe"] == 1 for f in e.data["fixtures"])
    assert "laser_20" in e.data["profielen"]


def test_programmer_gaat_voor_effect(e):
    e.programmer_zet([1], {"dim": 50, "kleur": "#00ff00"})
    dim, r, g, b = kanalen(e, "Par 1")
    assert (dim, r, g, b) == (128, 0, 255, 0)
    e.programmer_zet([1], {"kanalen": {"2": 77}})
    assert kanalen(e, "Par 1")[1] == 77
    e.programmer_wissen()
    assert not e.programmer


def test_master_en_blackout(e):
    e.programmer_zet([1], {"dim": 100, "kleur": "#ffffff"})
    e.data["show"]["master"] = 50
    assert kanalen(e, "Par 1")[0] == 128
    e.data["show"]["blackout"] = True
    assert kanalen(e, "Par 1")[0] == 0


def test_scene_met_fade(e):
    e.programmer_zet([1, 2], {"dim": 100, "kleur": "#0000ff"})
    e.scene_opslaan("Blauw", inhoud="vast", fade=2.0)
    e.programmer_wissen()
    e.laad_scene("Blauw")
    t0 = e.scene_actief["t0"]
    e.data["show"]["kleur"] = {"modus": "vast", "palet": ["#ff0000"], "snelheid": 1, "spreiding": 0}
    begin = kanalen(e, "Par 1", t0)
    halverwege = kanalen(e, "Par 1", t0 + 1.0)
    eind = kanalen(e, "Par 1", t0 + 2.5)
    assert begin[1] == 255 and begin[3] == 0        # nog rood
    assert 100 < halverwege[1] < 160 and 100 < halverwege[3] < 160
    assert eind[1] == 0 and eind[3] == 255          # helemaal blauw
    assert kanalen(e, "Par 3", t0 + 2.5)[1] == 255  # andere lampen volgen het effect
    e.scene_loslaten(fade=0)
    assert kanalen(e, "Par 1", time.time() + 1)[1] == 255


def test_cuelijst_loopt_op_de_beat(e):
    e.scene_opslaan("A", inhoud="effecten")
    e.scene_opslaan("B", inhoud="effecten")
    e.zet_cuelijsten({"Show": {"stappen": [{"scene": "A", "duur": 4}, {"scene": "B", "duur": 4}], "eenheid": "beats"}})
    e.cue_start("Show")
    assert e.cue["stap"] == 0
    start = time.time()
    beat = 60.0 / e.data["show"]["bpm"]
    e.render(start + 4.2 * beat)
    assert e.cue["stap"] == 1 and e.scene_actief["naam"] == "B"
    e.render(start + 8.4 * beat)
    assert e.cue["stap"] == 0


def test_vasthouden(e):
    nu = time.time()
    e.zet_hold(smoke=True)
    rook = next(f for f in e.data["fixtures"] if f["naam"] == "Rookmachine")
    assert e.render(nu)[1][rook["adres"] - 1] == 255
    e.zet_hold(blinder=True)
    assert kanalen(e, "Par 1", nu) == [255, 255, 255, 255]
    e.zet_hold()
    e.actie("hold", "strobe", True)          # via MIDI: blijft aan tot loslaten
    assert e.status_info()["strobe"]
    e.actie("hold", "strobe", False)
    assert not e.status_info()["strobe"]


def test_ledbar_cellen_lopen_mee(e):
    e.data["show"]["kleur"] = {"modus": "chase", "palet": ["#ff0000", "#0000ff"], "snelheid": 1, "spreiding": 0}
    waarden = kanalen(e, "LED-bar")
    cellen = [tuple(waarden[i:i + 3]) for i in range(0, 24, 3)]
    assert len(set(cellen)) == 2                  # afwisselend rood en blauw over de segmenten


def test_meerdere_universes(e):
    fx = copy.deepcopy(e.data["fixtures"])
    fx[0]["universe"] = 2
    e.zet_fixtures(fx)
    frames = e.render(1000.0)
    assert set(frames) == {1, 2}
    assert frames[2][0] == frames[1][4]           # Par 1 (universe 2) doet hetzelfde als Par 2 bij 'alles aan'


def test_macro_fader_rook(e):
    rook = next(f for f in e.data["fixtures"] if f["naam"] == "Rookmachine")
    e.zet_fader(1, 40)
    assert e.render(1000.0)[1][rook["adres"] - 1] == 102


def test_export_import(e, tmp_path):
    e.scene_opslaan("X", inhoud="effecten")
    data = json.loads(json.dumps(e.export()))
    e2 = Engine(str(tmp_path / "s.json"))
    e2.importeer(data)
    assert "X" in e2.data["scenes"]
    assert len(e2.data["fixtures"]) == len(e.data["fixtures"])
    with pytest.raises(ValueError):
        e2.importeer({"iets": 1})


def test_kapotte_show_wordt_bewaard(tmp_path):
    pad = tmp_path / "show.json"
    pad.write_text("{kapot")
    e = Engine(str(pad))
    assert e.data["fixtures"]
    assert any(p.name.startswith("show.json.kapot") for p in tmp_path.iterdir())


def test_pincode(e):
    e.zet_pin("1234")
    assert e.pin_klopt("1234") and not e.pin_klopt("0000")
    e.zet_pin("")
    assert e.pin_klopt("wat dan ook")
    with pytest.raises(ValueError):
        e.zet_pin("12")


def test_tempo_factor_zonder_sprong(e):
    e.render(1000.0)
    voor = e.effect_beat(e.beat(1001.0))
    e.data["show"]["tempo_factor"] = 2
    na = e.effect_beat(e.beat(1001.0))
    assert abs(voor - na) < 1e-6
    later = e.effect_beat(e.beat(1002.0))
    assert abs((later - na) - 2 * e.data["show"]["bpm"] / 60) < 1e-6
