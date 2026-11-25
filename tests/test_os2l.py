"""Virtual DJ via OS2L: beat, BPM en knoppen komen over het netwerk binnen."""
import json
import socket
import time

from dmxdesk.engine import Engine
from dmxdesk.os2l import OS2L


def wacht(voorwaarde, sec=3):
    eind = time.time() + sec
    while time.time() < eind:
        if voorwaarde():
            return True
        time.sleep(0.01)
    return False


def test_virtual_dj_beat_bpm_en_knoppen():
    e = Engine(None)
    e.data["show"]["energie"]["aan"] = False
    e.data["scenes"]["Rood Feest"] = {"effecten": None, "vast": {}, "fade": 0, "kleur": ""}
    vdj = OS2L(e, poort=17838, aankondigen=False)
    assert vdj.start()
    try:
        c = socket.create_connection(("127.0.0.1", vdj.poort))
        assert wacht(lambda: e.status_info()["os2l"]["verbonden"] == 1)
        tel = 60 / 131.0
        t0 = time.time()
        berichten = ""
        for k in range(6):                                  # 6 beats op 131 BPM, beat 4 is de 1 van de maat
            while time.time() < t0 + k * tel:
                time.sleep(0.001)
            # (zonder scheidingsteken achter elkaar, en in rare stukjes geknipt)
            berichten = json.dumps({"evt": "beat", "change": False, "pos": 4 + k, "bpm": 131.0, "strength": 0.5})
            c.sendall(berichten[:10].encode()); time.sleep(0.002); c.sendall(berichten[10:].encode())
        assert wacht(lambda: abs(e.data["show"]["bpm"] - 131.0) < 0.01)
        nu = time.time()
        b = e.beat(t0 + 5 * tel)
        assert abs(b - round(b)) < 0.05, b                  # de beat valt precies wanneer Virtual DJ hem stuurt
        assert round(b) % 4 == (4 + 5) % 4                 # en op de goede plek in de maat
        st = e.status_info()["os2l"]
        assert st["beat"] and st["bpm"] == 131.0 and st["adres"].endswith(str(vdj.poort))

        # het meeluisteren (geluidskaart) stuurt dan niet tegen
        e.beat_bericht({"soort": "beat", "bron": "audio", "t": nu, "bpm": 100.0, "conf": 0.9})
        e.beat_bericht({"soort": "beat", "bron": "audio", "t": nu, "bpm": 100.0, "conf": 0.9})
        e.beat_bericht({"soort": "beat", "bron": "audio", "t": nu, "bpm": 100.0, "conf": 0.9})
        assert abs(e.data["show"]["bpm"] - 131.0) < 0.01

        knop = lambda naam, staat="on": c.sendall(json.dumps({"evt": "btn", "name": naam, "page": "", "state": staat}).encode())
        knop("STROBE")
        assert wacht(lambda: "strobe" in e.hold_vast)
        knop("strobe", "off")
        assert wacht(lambda: "strobe" not in e.hold_vast)
        knop("rood feest")
        assert wacht(lambda: e.scene_actief and e.scene_actief["naam"] == "Rood Feest")
        knop("drop")
        assert wacht(lambda: e.lichtman.drops and abs(e.lichtman.drops[-1] - time.time()) < 1)
        c.sendall(b'{"evt":"cmd","id":1,"param":0.5}')
        assert wacht(lambda: e.data["show"]["master"] == 50)
        c.sendall(b'rommel{"evt":"btn","name":"blackout","state":"on"}')   # rommel ertussen: overslaan
        assert wacht(lambda: e.data["show"]["blackout"])
        c.close()
        assert wacht(lambda: e.status_info()["os2l"]["verbonden"] == 0)
    finally:
        vdj.stop()
