"""DMX naar buiten sturen: USB-dongles (Open DMX / FTDI, Enttec DMX USB Pro) en netwerk (Art-Net, sACN).

Elke uitgang heeft een eigen draad die steeds het laatste frame van zijn universe verstuurt.
Een uitgang die wegvalt (dongle eruit, netwerk weg) probeert het vanzelf opnieuw.
"""
import glob
import socket
import struct
import sys
import threading
import time
import uuid

try:
    import serial
    from serial.tools import list_ports
except ImportError:          # zonder pyserial werken alleen de netwerkuitgangen
    serial = None
    list_ports = None

from . import NAAM

FTDI_VID = 0x0403
ARTNET_POORT = 6454
SACN_POORT = 5568
FPS = 40


# ---------------------------------------------------------------- pakketten

def artnet_pakket(port_adres, volgnummer, data):
    """ArtDmx-pakket. port_adres = 15 bits: net (7) + subnet (4) + universe (4), Art-Net telt vanaf 0."""
    data = bytes(data[:512]).ljust(512, b"\0")
    return (b"Art-Net\0" + struct.pack("<H", 0x5000) + struct.pack(">H", 14)
            + bytes([volgnummer & 0xFF, 0]) + struct.pack("<H", port_adres & 0x7FFF)
            + struct.pack(">H", len(data)) + data)


def sacn_pakket(universe, volgnummer, data, cid, bron=NAAM, prioriteit=100):
    """E1.31 (sACN) datapakket met 512 kanalen. universe telt vanaf 1."""
    data = bytes(data[:512]).ljust(512, b"\0")
    lengte = 126 + len(data)                      # 638 bij 512 kanalen
    wortel = (struct.pack(">HH", 0x0010, 0x0000) + b"ASC-E1.17\0\0\0"
              + struct.pack(">H", 0x7000 | (lengte - 16)) + struct.pack(">I", 0x00000004) + cid)
    naam = bron.encode("utf-8")[:63].ljust(64, b"\0")
    kader = (struct.pack(">H", 0x7000 | (lengte - 38)) + struct.pack(">I", 0x00000002) + naam
             + bytes([prioriteit]) + struct.pack(">H", 0) + bytes([volgnummer & 0xFF, 0])
             + struct.pack(">H", universe))
    dmp = (struct.pack(">H", 0x7000 | (lengte - 115)) + bytes([0x02, 0xA1]) + struct.pack(">HHH", 0, 1, len(data) + 1)
           + b"\0" + data)
    return wortel + kader + dmp


def sacn_multicast(universe):
    return f"239.255.{(universe >> 8) & 0xFF}.{universe & 0xFF}"


def enttec_pro_pakket(data):
    """'Output Only Send DMX Packet' (label 6) voor de Enttec DMX USB Pro."""
    inhoud = b"\0" + bytes(data[:512]).ljust(512, b"\0")
    return b"\x7e\x06" + struct.pack("<H", len(inhoud)) + inhoud + b"\xe7"


# ---------------------------------------------------------------- poorten zoeken

def poorten():
    """Alle seriële poorten van deze computer, FTDI-chips (de meeste USB-DMX-dongles) eerst."""
    uit = []
    if list_ports is not None:
        for p in list_ports.comports():
            if sys.platform == "darwin" and p.device.startswith("/dev/tty."):
                continue     # op de Mac altijd de /dev/cu.-variant gebruiken
            uit.append({"poort": p.device, "naam": p.description if p.description not in (None, "n/a") else p.device,
                        "ftdi": p.vid == FTDI_VID, "fabrikant": p.manufacturer or "", "serienummer": p.serial_number or ""})
    if not uit and sys.platform.startswith("linux"):
        for pad in sorted(glob.glob("/dev/ttyUSB*")):
            uit.append({"poort": pad, "naam": pad, "ftdi": True, "fabrikant": "", "serienummer": ""})
    uit.sort(key=lambda p: (not p["ftdi"], p["poort"]))
    return uit


def zoek_poort(voorkeur, soort, bezet=()):
    if voorkeur and voorkeur != "auto":
        return voorkeur
    kandidaten = [p for p in poorten() if p["ftdi"] and p["poort"] not in bezet]
    pro = [p for p in kandidaten if "pro" in (p["naam"] + " " + p["fabrikant"]).lower()]
    if soort == "enttecpro" and pro:
        return pro[0]["poort"]
    if soort == "opendmx":
        kandidaten = [p for p in kandidaten if p not in pro] or kandidaten
    return kandidaten[0]["poort"] if kandidaten else None


# ---------------------------------------------------------------- uitgangen

class Uitgang(threading.Thread):
    fps = FPS

    def __init__(self, engine, cfg, beheer):
        super().__init__(daemon=True, name=f"uitgang-{cfg['id']}")
        self.engine, self.cfg, self.beheer = engine, cfg, beheer
        self.stoppen = threading.Event()
        self.verstuurd, self.meet_start = 0, time.time()
        self.tekst = "opstarten…"
        self.ok = False

    def status(self, ok, tekst):
        self.ok, self.tekst = ok, tekst
        self.engine.uitgang_status[self.cfg["id"]] = {"ok": ok, "tekst": tekst, "fps": self.engine.uitgang_status.get(
            self.cfg["id"], {}).get("fps", 0)}

    def frame(self):
        return self.engine.frames.get(self.cfg["universe"]) or bytes(512)

    def openen(self):
        pass

    def sluiten(self):
        pass

    def stuur(self, data):
        raise NotImplementedError

    def run(self):
        volgende_poging = 0.0
        open_ = False
        while not self.stoppen.is_set():
            start = time.time()
            if not open_:
                if start < volgende_poging:
                    self.stoppen.wait(min(0.5, volgende_poging - start))
                    continue
                try:
                    self.openen()
                    open_ = True
                except Exception as e:
                    self.status(False, str(e) or e.__class__.__name__)
                    volgende_poging = time.time() + 2.0
                    continue
            try:
                self.stuur(self.frame())
                self.verstuurd += 1
            except Exception as e:
                print(f"DMX-uitgang {self.cfg['naam']}: fout, opnieuw openen:", e, flush=True)
                self.status(False, str(e) or e.__class__.__name__)
                self.sluiten()
                open_ = False
                volgende_poging = time.time() + 1.0
                continue
            if start - self.meet_start >= 1.0:
                st = self.engine.uitgang_status.setdefault(self.cfg["id"], {"ok": self.ok, "tekst": self.tekst})
                st["fps"] = self.verstuurd
                self.verstuurd, self.meet_start = 0, start
            rust = 1.0 / self.fps - (time.time() - start)
            if rust > 0:
                self.stoppen.wait(rust)
        self.sluiten()


class SerieelUitgang(Uitgang):
    def __init__(self, engine, cfg, beheer):
        super().__init__(engine, cfg, beheer)
        self.ser = None
        self.poort = None

    def sluiten(self):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.beheer.poort_vrij(self.poort)
        self.poort = None

    def open_serieel(self, **opties):
        if serial is None:
            raise OSError("pyserial ontbreekt (pip install pyserial)")
        poort = self.beheer.claim_poort(self, self.cfg["poort"], self.cfg["soort"])
        if not poort:
            raise OSError("geen USB-DMX dongle gevonden")
        try:
            self.ser = serial.Serial(poort, timeout=1, write_timeout=1, **opties)
        except Exception:
            self.beheer.poort_vrij(poort)
            raise
        self.poort = poort
        print(f"DMX-dongle geopend: {poort} ({self.cfg['soort']})", flush=True)


class OpenDmxUitgang(SerieelUitgang):
    """Goedkope FTDI-dongle (Open DMX): de computer maakt zelf het DMX-signaal, met break en 250 kbit/s."""

    def openen(self):
        self.open_serieel(baudrate=250000, bytesize=8, parity="N", stopbits=2)
        self.status(True, f"verbonden ({self.poort})")

    def stuur(self, data):
        self.ser.break_condition = True
        time.sleep(0.00015)
        self.ser.break_condition = False
        time.sleep(0.00002)
        self.ser.write(b"\x00" + bytes(data))
        self.ser.flush()  # wacht tot het frame echt verstuurd is (voorkomt flikkeren)


class EnttecProUitgang(SerieelUitgang):
    """Enttec DMX USB Pro (en klonen zoals DMXking ultraDMX): de dongle maakt het DMX-signaal zelf."""

    def openen(self):
        self.open_serieel(baudrate=57600)
        self.status(True, f"verbonden ({self.poort})")

    def stuur(self, data):
        self.ser.write(enttec_pro_pakket(data))


class NetwerkUitgang(Uitgang):
    def __init__(self, engine, cfg, beheer):
        super().__init__(engine, cfg, beheer)
        self.sock = None
        self.volgnummer = 0
        self.vorige, self.vorige_t = None, 0.0

    def sluiten(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None

    def nieuwe_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return sock

    def moet_sturen(self, data):
        """Alleen bij veranderingen, en minstens twee keer per seconde (anders denkt de ontvanger dat we weg zijn)."""
        nu = time.time()
        data = bytes(data)
        if data == self.vorige and nu - self.vorige_t < 0.5:
            return None
        self.vorige, self.vorige_t = data, nu
        self.volgnummer = self.volgnummer % 255 + 1
        return data


class ArtNetUitgang(NetwerkUitgang):
    def openen(self):
        self.sock = self.nieuwe_socket()
        self.doel = (self.cfg["ip"] or "255.255.255.255", ARTNET_POORT)
        self.status(True, f"Art-Net universe {self.cfg['net_universe']} → {self.doel[0]}")

    def stuur(self, data):
        data = self.moet_sturen(data)
        if data is not None:
            self.sock.sendto(artnet_pakket(self.cfg["net_universe"], self.volgnummer, data), self.doel)


class SacnUitgang(NetwerkUitgang):
    def openen(self):
        self.sock = self.nieuwe_socket()
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 8)
        self.universe = max(1, self.cfg["net_universe"] or self.cfg["universe"])
        self.doel = (self.cfg["ip"] or sacn_multicast(self.universe), SACN_POORT)
        self.status(True, f"sACN universe {self.universe} → {self.doel[0]}")

    def stuur(self, data):
        data = self.moet_sturen(data)
        if data is not None:
            self.sock.sendto(sacn_pakket(self.universe, self.volgnummer, data, self.beheer.cid), self.doel)


SOORTEN = {"opendmx": OpenDmxUitgang, "enttecpro": EnttecProUitgang, "artnet": ArtNetUitgang, "sacn": SacnUitgang}


class UitvoerBeheer:
    """Start en stopt de uitgangen als de instellingen veranderen."""

    def __init__(self, engine):
        self.engine = engine
        self.draden = {}
        self.lock = threading.Lock()
        self.bezet = {}
        self.cid = uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname() + ".dmxdesk").bytes
        engine.bij_uitgangen.append(self.bijwerken)

    def claim_poort(self, draad, voorkeur, soort):
        with self.lock:
            poort = zoek_poort(voorkeur, soort, bezet=set(self.bezet) - {draad.poort})
            if poort in self.bezet and self.bezet[poort] is not draad:
                raise OSError(f"{poort} is al in gebruik door een andere uitgang")
            if poort:
                self.bezet[poort] = draad
            return poort

    def poort_vrij(self, poort):
        with self.lock:
            self.bezet.pop(poort, None)

    def bijwerken(self):
        with self.engine.lock:
            gewenst = {u["id"]: dict(u) for u in self.engine.data["uitgangen"] if u["aan"]}
            alle = {u["id"] for u in self.engine.data["uitgangen"]}
        for uid, draad in list(self.draden.items()):
            if gewenst.get(uid) != draad.cfg:
                draad.stoppen.set()
                draad.join(timeout=2.0)
                del self.draden[uid]
        for uid in list(self.engine.uitgang_status):
            if uid not in gewenst:
                self.engine.uitgang_status[uid] = {"ok": False, "tekst": "uit" if uid in alle else "", "fps": 0}
                if uid not in alle:
                    del self.engine.uitgang_status[uid]
        for uid, cfg in gewenst.items():
            if uid not in self.draden:
                draad = SOORTEN[cfg["soort"]](self.engine, cfg, self)
                self.draden[uid] = draad
                draad.start()

    def stop(self):
        for draad in self.draden.values():
            draad.stoppen.set()
        for draad in self.draden.values():
            draad.join(timeout=2.0)
        self.draden = {}
