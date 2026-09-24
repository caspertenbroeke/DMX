"""De USB-uitgang herkent zelf of de kabel een Enttec Pro(-kloon) of een simpele Open DMX-kabel is."""
from dmxdesk import uitvoer
from dmxdesk.engine import Engine


class NepKabel:
    def __init__(self, pro):
        self.pro, self.geschreven, self.antwoord = pro, [], b""
        self.baudrate, self.stopbits, self.timeout, self.break_condition = 57600, 1, 1, False

    @property
    def in_waiting(self):
        return len(self.antwoord)

    def reset_input_buffer(self):
        self.antwoord = b""

    def write(self, data):
        self.geschreven.append(bytes(data))
        if self.pro and data.startswith(b"\x7e\x03"):
            self.antwoord = b"\x7e\x03\x05\x00\x01\x05\x09\x01\x28\xe7"

    def read(self, n):
        uit, self.antwoord = self.antwoord[:n], self.antwoord[n:]
        return uit

    def flush(self):
        pass

    def close(self):
        pass


def maak(pro, monkeypatch):
    e = Engine(None)
    beheer = uitvoer.UitvoerBeheer(e)
    cfg = e.data["uitgangen"][0]
    assert cfg["soort"] == "usb"
    kabel = NepKabel(pro)
    u = uitvoer.UsbUitgang(e, cfg, beheer)
    monkeypatch.setattr(u, "open_serieel", lambda **kw: (setattr(u, "ser", kabel), setattr(u, "poort", "COM3")))
    u.openen()
    return u, kabel


def test_pro_herkend(monkeypatch):
    u, kabel = maak(True, monkeypatch)
    assert u.pro and "Pro" in u.tekst
    u.stuur(bytes(512))
    assert kabel.geschreven[-1][:2] == b"\x7e\x06" and len(kabel.geschreven[-1]) == 518


def test_open_dmx_herkend(monkeypatch):
    u, kabel = maak(False, monkeypatch)
    assert not u.pro and "Open DMX" in u.tekst
    assert kabel.baudrate == 250000 and kabel.stopbits == 2
    u.stuur(bytes([7] * 512))
    assert kabel.geschreven[-1] == b"\x00" + bytes([7] * 512)
