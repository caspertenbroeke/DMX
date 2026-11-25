"""Virtual DJ (en andere DJ-software) via OS2L: de DJ-software stuurt elke beat, de BPM en knoppen.

OS2L (Open Sound To Light): DMXDesk luistert op een TCP-poort en meldt zich op het netwerk als
'_os2l._tcp' (DNS-SD/Bonjour). Virtual DJ vindt hem dan vanzelf en stuurt JSON-berichten, zonder
scheidingsteken achter elkaar:
  {"evt":"beat","change":false,"pos":123,"bpm":128.0,"strength":0.8}    elke beat van de deck die speelt
  {"evt":"btn","name":"strobe","page":"","state":"on"}                  een knop/pad in Virtual DJ
  {"evt":"cmd","id":1,"param":0.5}                                      een schuif (0..1)
Vindt Virtual DJ hem niet vanzelf, dan vul je in Virtual DJ bij de optie 'os2lDirectIp' het adres in
(staat in DMXDesk bij Geluid → Virtual DJ).

Knoppen: de naam bepaalt wat er gebeurt (hoofdletters maken niet uit):
  strobe / smoke / rook / blinder   vasthouden zolang de knop aan staat
  drop / opbouw                     de lichtman-knoppen
  blackout / freeze / auto          aan/uit
  loslaten                          de scène loslaten
  anders: een scène met die naam laden, of een cuelijst met die naam starten/stoppen
Schuif (cmd) 1 = master.
"""
import json
import socket
import threading
import time

try:
    from zeroconf import ServiceInfo, Zeroconf
except Exception:          # geen zeroconf: dan alleen met het adres in Virtual DJ (os2lDirectIp)
    Zeroconf = ServiceInfo = None

STANDAARD_POORT = 7838
HOLD = {"strobe": "strobe", "smoke": "smoke", "rook": "smoke", "blinder": "blinder"}


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


class OS2L:
    def __init__(self, engine, poort=STANDAARD_POORT, aankondigen=True):
        self.engine = engine
        self.gewenste_poort = poort
        self.aankondigen = aankondigen
        self.poort = None
        self.sock = None
        self.zc = None
        self.clients = 0
        self.laatste_beat = 0.0
        self.bpm = None
        self.fout = ""
        self.stoppen = threading.Event()
        self.status_bijwerken()

    # ------------------------------------------------------------ status voor de app
    def status(self):
        return {"aan": self.sock is not None, "poort": self.poort, "adres": f"{_lan_ip()}:{self.poort}" if self.poort else "",
                "verbonden": self.clients, "bpm": self.bpm,
                "beat": time.time() - self.laatste_beat < 3.0, "gevonden": self.zc is not None, "fout": self.fout}

    def status_bijwerken(self):
        self.engine.extra_status["os2l"] = self.status

    # ------------------------------------------------------------ starten en stoppen
    def start(self):
        for p in range(self.gewenste_poort, self.gewenste_poort + 10):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", p))
                s.listen(4)
                self.sock, self.poort = s, p
                break
            except OSError as e:
                self.fout = f"poort {p} bezet ({e})"
                s.close()
        if self.sock is None:
            self.status_bijwerken()
            return False
        self.fout = ""
        threading.Thread(target=self._accepteer, daemon=True, name="os2l").start()
        if self.aankondigen:
            threading.Thread(target=self._aankondigen, daemon=True, name="os2l-dnssd").start()
        print(f"Virtual DJ (OS2L): luistert op poort {self.poort}", flush=True)
        self.status_bijwerken()
        return True

    def _aankondigen(self):
        if Zeroconf is None:
            return
        try:
            ip = _lan_ip()
            naam = socket.gethostname().split(".")[0] or "DMXDesk"
            info = ServiceInfo("_os2l._tcp.local.", f"DMXDesk ({naam})._os2l._tcp.local.",
                               addresses=[socket.inet_aton(ip)], port=self.poort, server=f"{naam}.local.",
                               properties={})
            zc = Zeroconf()
            zc.register_service(info)
            self.zc, self._info = zc, info
        except Exception as e:      # zonder aankondiging kan Virtual DJ nog steeds via os2lDirectIp
            print("OS2L aankondigen mislukt:", e, flush=True)
        self.status_bijwerken()

    def stop(self):
        self.stoppen.set()
        if self.zc is not None:
            try:
                self.zc.unregister_service(self._info)
                self.zc.close()
            except Exception:
                pass
            self.zc = None
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    # ------------------------------------------------------------ verbindingen
    def _accepteer(self):
        while not self.stoppen.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._lees, args=(conn,), daemon=True, name="os2l-client").start()

    def _lees(self, conn):
        self.clients += 1
        self.status_bijwerken()
        print("Virtual DJ (OS2L) verbonden", flush=True)
        dec, buf = json.JSONDecoder(), ""
        try:
            conn.settimeout(1.0)
            while not self.stoppen.is_set():
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    break
                buf += data.decode("utf-8", "replace")
                while True:                      # berichten staan zonder scheidingsteken achter elkaar
                    buf = buf.lstrip()
                    if not buf:
                        break
                    if buf[0] != "{":            # rommel: overslaan tot het volgende bericht
                        i = buf.find("{")
                        buf = buf[i:] if i >= 0 else ""
                        continue
                    try:
                        m, eind = dec.raw_decode(buf)
                    except ValueError:
                        if len(buf) > 65536:
                            buf = ""
                        break                    # nog niet compleet: wachten op meer
                    buf = buf[eind:]
                    if isinstance(m, dict):
                        try:
                            self.bericht(m)
                        except Exception as e:
                            print("OS2L-bericht niet begrepen:", m, e, flush=True)
        except OSError:
            pass
        finally:
            conn.close()
            self.clients -= 1
            self.status_bijwerken()
            print("Virtual DJ (OS2L) verbinding weg", flush=True)

    # ------------------------------------------------------------ berichten
    def bericht(self, m, nu=None):
        nu = time.time() if nu is None else nu
        evt = m.get("evt")
        e = self.engine
        if evt == "beat":
            bpm = float(m.get("bpm") or 0)
            if bpm > 0:
                self.bpm, self.laatste_beat = round(bpm, 1), nu
                e.os2l_beat(bpm, int(m.get("pos") or 0), bool(m.get("change")), nu)
        elif evt == "btn":
            naam = str(m.get("name") or "").strip()
            aan = str(m.get("state", "on")).lower() in ("on", "1", "true")
            self.knop(naam, aan)
        elif evt == "cmd":
            if int(m.get("id") or 0) == 1:
                e.actie("master", waarde=float(m.get("param") or 0))

    def knop(self, naam, aan):
        e, sleutel = self.engine, naam.lower()
        if sleutel in HOLD:
            return e.actie("hold", HOLD[sleutel], aan)
        if not aan:
            return
        if sleutel in ("drop", "opbouw"):
            return e.lichtman_knop(sleutel)
        if sleutel in ("blackout", "freeze", "auto"):
            return e.actie(sleutel)
        if sleutel in ("loslaten", "scene_los", "release"):
            return e.scene_loslaten()
        scene = next((s for s in e.data["scenes"] if s.lower() == sleutel), None)
        if scene:
            return e.laad_scene(scene)
        lijst = next((c for c in e.data["cuelijsten"] if c.lower() == sleutel), None)
        if lijst:
            return e.actie("cue", lijst)
        print(f"OS2L: onbekende knop '{naam}'", flush=True)
