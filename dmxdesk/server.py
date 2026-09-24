"""Webserver: het bedieningspaneel (app-venster, browser, telefoon) praat hiermee.

  /            telefoonpagina (grote knoppen SMOKE / STROBE / BLINDER, scènes)
  /desk        het volledige bedieningspaneel (ook /instellingen, voor de oude links)
  /api/...     JSON-API, /api/live stuurt 15x per seconde de toestand (Server-Sent Events)
"""
import copy
import importlib.util
import json
import mimetypes
import os
import secrets
import socket
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import NAAM, VERSIE, paden
from .bibliotheek import importeer_bestand
from .engine import MODI, UITGANG_SOORTEN
from .profielen import FUNCTIES, SOORTEN
from . import audio as audio_mod
from . import midi as midi_mod
from . import uitvoer as uitvoer_mod

MAX_BODY = 32 * 1024 * 1024
LIVE_FPS = 15
LOKAAL = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
VRIJ_ZONDER_PIN = ("/api/login", "/api/info")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")


_adressen = {"t": 0.0, "ips": []}


def lan_adressen(poort):
    """Adressen waarop telefoons deze computer kunnen bereiken (30 s onthouden: opzoeken kan traag zijn)."""
    if time.time() - _adressen["t"] > 30:
        _adressen.update(t=time.time(), ips=_zoek_ips())
    return [f"http://{ip}:{poort}/" for ip in _adressen["ips"]]


def _zoek_ips():
    """Zonder DNS (dat kan op een Mac tientallen seconden hangen): via welk eigen adres gaat verkeer naar
    een paar netwerken toe. Er gaat niets echt de deur uit, connect() op UDP kiest alleen een route."""
    ips = []
    for doel in ("10.255.255.255", "192.168.255.255", "172.31.255.255", "8.8.8.8"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect((doel, 1))
                ip = s.getsockname()[0]
            finally:
                s.close()
        except OSError:
            continue
        if ip not in ips and not ip.startswith(("127.", "0.")):
            ips.append(ip)
    return ips


def qr_beschikbaar():
    return importlib.util.find_spec("qrcode") is not None


def qr_svg(tekst):
    if not qr_beschikbaar():
        return None
    import qrcode
    from qrcode.image.svg import SvgPathImage
    img = qrcode.make(tekst, image_factory=SvgPathImage, box_size=10, border=2)
    return img.to_string()


class App:
    """Alle onderdelen bij elkaar, zodat de webserver erbij kan."""

    def __init__(self, engine, bibliotheek, uitvoer=None, audio=None, midi=None, poort=8080, afsluiten=None):
        self.engine, self.bibliotheek, self.uitvoer, self.audio, self.midi = engine, bibliotheek, uitvoer, audio, midi
        self.poort = poort
        self.afsluiten = afsluiten
        self.sessies = set()
        self.systeem_knoppen = os.environ.get("DMXDESK_SYSTEEMKNOPPEN") == "1"
        self.stoppen = threading.Event()


class Handler(BaseHTTPRequestHandler):
    app = None
    server_version = f"{NAAM}/{VERSIE}"

    def log_message(self, *args):
        pass

    # ------------------------------------------------------------ antwoorden
    def stuur(self, code, inhoud, soort="application/json; charset=utf-8", extra=None):
        data = inhoud if isinstance(inhoud, bytes) else json.dumps(inhoud, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def bestand(self, naam):
        web = os.path.realpath(paden.web_map())
        pad = os.path.realpath(os.path.join(web, naam))
        if not pad.startswith(web + os.sep) or not os.path.isfile(pad):
            return self.stuur(404, {"fout": "niet gevonden"})
        soort = mimetypes.guess_type(pad)[0] or "application/octet-stream"
        if soort.startswith("text/") or soort in ("application/javascript", "application/json", "image/svg+xml",
                                                  "application/manifest+json"):
            soort += "; charset=utf-8"
        with open(pad, "rb") as f:
            self.stuur(200, f.read(), soort)

    @property
    def lokaal(self):
        return self.client_address[0] in LOKAAL

    def ingelogd(self):
        e = self.app.engine
        if self.lokaal or not e.data["instellingen"].get("pin_hash"):
            return True
        cookies = self.headers.get("Cookie") or ""
        for deel in cookies.split(";"):
            k, _, v = deel.strip().partition("=")
            if k == "dmxdesk" and v in self.app.sessies:
                return True
        return False

    def body(self):
        lengte = int(self.headers.get("Content-Length") or 0)
        if lengte > MAX_BODY:
            raise ValueError("Te groot")
        ruw = self.rfile.read(lengte) if lengte else b""
        return json.loads(ruw or b"{}")

    # ------------------------------------------------------------ GET
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlparse(self.path)
        pad, q = url.path, parse_qs(url.query)
        if pad in ("/", "/telefoon"):
            return self.bestand("telefoon.html")
        if pad in ("/desk", "/instellingen"):
            return self.bestand("index.html")
        if pad == "/manifest.webmanifest":
            return self.bestand("manifest.webmanifest")
        if pad.startswith("/static/"):
            return self.bestand(pad[len("/static/"):])
        if pad == "/favicon.ico":
            return self.bestand("icoon.svg")
        if not pad.startswith("/api/"):
            return self.stuur(404, {"fout": "niet gevonden"})
        if pad not in VRIJ_ZONDER_PIN and not self.ingelogd():
            return self.stuur(401, {"fout": "pincode nodig", "pin": True})
        try:
            return self.api_get(pad, q)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, KeyError, TypeError) as fout:
            self.stuur(400, {"fout": str(fout)})

    def api_get(self, pad, q):
        a, e = self.app, self.app.engine
        if pad == "/api/info":
            return self.stuur(200, {"naam": NAAM, "versie": VERSIE, "pin": bool(e.data["instellingen"].get("pin_hash"))
                                    and not self.lokaal})
        if pad == "/api/status":
            return self.stuur(200, e.status_info())
        if pad == "/api/state":
            # ?deel=licht: zonder lampen en profielen (die zijn groot en veranderen zelden)
            sleutels = ["naam", "show", "scenes", "cuelijsten", "faders", "uitgangen", "audio", "midi"]
            if (q.get("deel") or [""])[0] != "licht":
                sleutels += ["fixtures", "profielen"]
            with e.lock:
                data = copy.deepcopy({k: e.data[k] for k in sleutels})
                data["programmer"] = copy.deepcopy(e.programmer)
                data["attributen"] = e.attribuut_overzicht()
                data["instellingen"] = {"pin": bool(e.data["instellingen"].get("pin_hash"))}
            data.update(versie=VERSIE, functies=FUNCTIES, soorten=SOORTEN, modi=MODI, uitgang_soorten=UITGANG_SOORTEN,
                        status=e.status_info(), bibliotheek=a.bibliotheek.info(),
                        systeem={"platform": sys.platform, "knoppen": a.systeem_knoppen, "lokaal": self.lokaal,
                                 "adressen": lan_adressen(a.poort), "poort": a.poort,
                                 "show_bestand": e.show_bestand if self.lokaal else None,
                                 "qr": qr_beschikbaar()})
            return self.stuur(200, data)
        if pad == "/api/live":
            return self.live(q)
        if pad == "/api/frame":
            u = int((q.get("u") or ["1"])[0])
            return self.stuur(200, list(e.frames.get(u) or bytes(512)))
        if pad == "/api/poorten":
            return self.stuur(200, uitvoer_mod.poorten())
        if pad == "/api/audio/apparaten":
            return self.stuur(200, {"beschikbaar": audio_mod.sd is not None, "apparaten": audio_mod.apparaten()})
        if pad == "/api/midi/apparaten":
            return self.stuur(200, {"beschikbaar": midi_mod.mido is not None,
                                    "apparaten": midi_mod.Midi.apparaten()})
        if pad == "/api/bibliotheek":
            return self.stuur(200, a.bibliotheek.zoek((q.get("zoek") or [""])[0], (q.get("soort") or [""])[0]))
        if pad == "/api/bibliotheek/profielen":
            return self.stuur(200, a.bibliotheek.profielen((q.get("sleutel") or [""])[0]))
        if pad == "/api/export":
            data = json.dumps(e.export(), indent=2, ensure_ascii=False).encode("utf-8")
            naam = "".join(c if c.isalnum() or c in " -_" else "_" for c in e.data.get("naam", "show")).strip() or "show"
            return self.stuur(200, data, extra={"Content-Disposition": f'attachment; filename="{naam}.dmxshow.json"'})
        if pad == "/api/qr":
            url = (q.get("url") or [""])[0]
            svg = qr_svg(url) if url.startswith("http") else None
            if svg is None:
                return self.stuur(404, {"fout": "qrcode-pakket ontbreekt"})
            return self.stuur(200, svg if isinstance(svg, bytes) else svg.encode(), "image/svg+xml")
        return self.stuur(404, {"fout": "niet gevonden"})

    def live(self, q):
        """Server-Sent Events: status en wat elke lamp doet, 15 keer per seconde."""
        e = self.app.engine
        monitor = int((q.get("monitor") or ["0"])[0] or 0)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        while not self.app.stoppen.is_set():
            start = time.time()
            bericht = {"s": e.status_info(), "v": e.voorbeeld}
            if monitor:
                bericht["f"] = list(e.frames.get(monitor) or bytes(512))
            self.wfile.write(b"data: " + json.dumps(bericht, separators=(",", ":")).encode() + b"\n\n")
            self.wfile.flush()
            rust = 1.0 / LIVE_FPS - (time.time() - start)
            if rust > 0:
                time.sleep(rust)

    # ------------------------------------------------------------ POST
    def do_POST(self):
        pad = urlparse(self.path).path
        if not pad.startswith("/api/"):
            return self.stuur(404, {"fout": "niet gevonden"})
        try:
            body = self.body()
            if pad == "/api/login":
                return self.login(body)
            if not self.ingelogd():
                return self.stuur(401, {"fout": "pincode nodig", "pin": True})
            antwoord = self.api_post(pad, body)
            if antwoord is None:
                return self.stuur(404, {"fout": "niet gevonden"})
            self.stuur(200, antwoord)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, TypeError, KeyError) as fout:
            self.stuur(400, {"fout": str(fout)})

    def login(self, body):
        e = self.app.engine
        time.sleep(0.3)          # raden gaat zo een stuk trager
        if not e.pin_klopt(str(body.get("pin", ""))):
            return self.stuur(403, {"fout": "Verkeerde pincode"})
        token = secrets.token_urlsafe(24)
        self.app.sessies.add(token)
        return self.stuur(200, {"ok": True},
                          extra={"Set-Cookie": f"dmxdesk={token}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax"})

    def api_post(self, pad, body):
        a, e = self.app, self.app.engine
        ok = {"ok": True}
        if pad == "/api/hold":
            e.zet_hold(bool(body.get("smoke")), bool(body.get("strobe")), bool(body.get("blinder")))
        elif pad == "/api/tap":
            e.tap()
        elif pad == "/api/show":
            e.wijzig_show(body)
        elif pad == "/api/naam":
            e.zet_naam(body.get("naam", ""))
        elif pad == "/api/fixtures":
            e.zet_fixtures(body)
        elif pad == "/api/profielen":
            e.zet_profielen(body)
        elif pad == "/api/profiel-toevoegen":
            return {"id": e.voeg_profiel_toe(body["profiel"])}
        elif pad == "/api/profiel-import":
            inhoud = body.get("inhoud", "")
            return {"profielen": [{"modus": m, "profiel": p} for m, p in importeer_bestand(body.get("naam", ""), inhoud)]}
        elif pad == "/api/scene":
            actie, naam = body.get("actie"), str(body.get("naam", ""))
            if actie == "opslaan":
                e.scene_opslaan(naam, body.get("inhoud", "beide"), body.get("fixtures"), body.get("fade"),
                                body.get("kleur", ""))
            elif actie == "laden":
                e.laad_scene(naam, body.get("fade"))
            elif actie == "verwijderen":
                e.scene_verwijderen(naam)
            elif actie == "loslaten":
                e.scene_loslaten(body.get("fade"))
            else:
                raise ValueError("onbekende actie")
        elif pad == "/api/scenes":
            e.zet_scenes(body)
        elif pad == "/api/cuelijsten":
            e.zet_cuelijsten(body)
        elif pad == "/api/cue":
            actie = body.get("actie")
            if actie == "start":
                e.cue_start(str(body.get("naam", "")), int(body.get("stap") or 0))
            elif actie == "stop":
                e.cue_stop()
            elif actie == "volgende":
                e.cue_volgende(1)
            elif actie == "vorige":
                e.cue_volgende(-1)
            elif actie == "pauze":
                e.cue_pauze()
            else:
                raise ValueError("onbekende actie")
        elif pad == "/api/programmer":
            if body.get("actie") == "wissen":
                e.programmer_wissen(body.get("fixtures"))
            else:
                e.programmer_zet(body.get("fixtures") or [], body.get("waarden") or {})
        elif pad == "/api/faders":
            e.zet_faders(body)
        elif pad == "/api/fader":
            e.zet_fader(body["id"], body.get("waarde", 0))
        elif pad == "/api/test":
            e.zet_test(body.get("fixture"), body.get("waarden", []))
        elif pad == "/api/zoek":
            e.identificeer(body.get("fixture"), float(body.get("seconden") or 4))
        elif pad == "/api/uitgangen":
            e.zet_uitgangen(body)
        elif pad == "/api/audio":
            with e.lock:
                e.data["audio"] = {"aan": bool(body.get("aan")), "apparaat": body.get("apparaat") or None}
                e.gewijzigd()
            if a.audio:
                a.audio.bijwerken()
        elif pad == "/api/midi":
            with e.lock:
                if "apparaat" in body:
                    e.data["midi"]["apparaat"] = str(body.get("apparaat") or "")
                if "koppelingen" in body and isinstance(body["koppelingen"], dict):
                    e.data["midi"]["koppelingen"] = {str(k): {"actie": str(v.get("actie")), "arg": v.get("arg")}
                                                     for k, v in body["koppelingen"].items() if isinstance(v, dict)}
                e.gewijzigd()
            if a.midi:
                a.midi.bijwerken()
        elif pad == "/api/midi/leer":
            if not a.midi:
                raise ValueError("MIDI niet beschikbaar")
            a.midi.leren(body.get("actie"), body.get("arg"))
        elif pad == "/api/actie":
            e.actie(str(body.get("soort")), body.get("arg"), body.get("waarde"))
        elif pad == "/api/import":
            e.importeer(body.get("show"), bool(body.get("uitgangen_ook")))
            if a.audio:
                a.audio.bijwerken()
        elif pad == "/api/pin":
            e.zet_pin(body.get("pin", ""))
            a.sessies.clear()
        elif pad == "/api/systeem":
            if not a.systeem_knoppen:
                raise ValueError("Uitzetten op afstand staat uit op deze computer")
            actie = {"uitzetten": "poweroff", "herstarten": "reboot"}.get(body.get("actie"))
            if not actie:
                raise ValueError("onbekende actie")
            threading.Thread(target=systeem_actie, args=(e, actie), daemon=True).start()
        elif pad == "/api/afsluiten":
            if not self.lokaal or not a.afsluiten:
                raise ValueError("Afsluiten kan alleen op de computer zelf")
            threading.Timer(0.5, a.afsluiten).start()
        else:
            return None
        return ok


def systeem_actie(engine, actie):
    """Raspberry Pi netjes uitzetten of herstarten (vanaf de telefoon, op de wagen is er geen laptop)."""
    import subprocess
    print("Computer wordt", "uitgezet" if actie == "poweroff" else "herstart", flush=True)
    try:
        engine.opslaan()
    except OSError:
        pass
    time.sleep(1.0)   # eerst het antwoord naar de telefoon laten gaan
    subprocess.run(["sudo", "-n", "systemctl", actie], check=False)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = sys.platform != "win32"   # op Windows zou een tweede DMXDesk dezelfde poort kunnen pakken

    def server_bind(self):
        # HTTPServer zoekt hier de computernaam op in DNS (socket.getfqdn); dat kan op een Mac lang duren
        # en is niet nodig
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "dmxdesk", self.server_address[1]


def maak_server(app, poort):
    handler = type("DeskHandler", (Handler,), {"app": app})
    return Server(("0.0.0.0", poort), handler)
