from types import SimpleNamespace

from dmxdesk import midi
from dmxdesk.engine import Engine


def bericht(soort, **kw):
    return SimpleNamespace(type=soort, **kw)


def test_leren_en_uitvoeren():
    e = Engine(None)
    m = midi.Midi(e)
    m.leren("hold", "strobe")
    m.bericht(bericht("note_on", channel=0, note=36, velocity=30))
    assert e.data["midi"]["koppelingen"] == {"noot:1:36": {"actie": "hold", "arg": "strobe"}}
    m.bericht(bericht("note_on", channel=0, note=36, velocity=10))    # ook een zachte aanslag telt
    assert e.status_info()["strobe"]
    m.bericht(bericht("note_off", channel=0, note=36, velocity=0))
    assert not e.status_info()["strobe"]
    m.leren("master")
    m.bericht(bericht("control_change", channel=0, control=7, value=64))
    m.bericht(bericht("control_change", channel=0, control=7, value=0))
    assert e.data["show"]["master"] == 0
