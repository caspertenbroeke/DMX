"""DMXDesk starten.

  dmxdesk                    app-venster (of de browser als er geen venster-onderdeel is)
  dmxdesk --browser          altijd in de gewone browser
  dmxdesk --server           zonder scherm (Raspberry Pi, dienst): alleen de webserver
  dmxdesk --poort 8080       andere poort
  dmxdesk --show pad.json    andere showbestand

Telefoons en tablets op hetzelfde wifi-netwerk openen http://<ip-van-deze-computer>:<poort>/
"""
import argparse
import faulthandler
import io
import json
import os
import signal
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

from . import NAAM, VERSIE, paden
from .audio import AudioInvoer
from .spotify import SpotifySpeaker
from .bibliotheek import Bibliotheek
from .engine import Engine, motor_lus, opslag_lus
from .midi import Midi
from .server import App, lan_adressen, maak_server
from .uitvoer import UitvoerBeheer

BEAT_POORT = 8091          # hier stuurt beatluister.py (op de Pi) de gevonden beats naartoe
STANDAARD_POORT = 8080
RESERVE_POORTEN = (8088, 8089, 8888, 8180)


def logbestand_als_nodig():
    """Een ingepakte app zonder console heeft geen stdout: schrijf meldingen dan naar een logbestand."""
    zonder_console = getattr(sys, "frozen", False) and sys.platform in ("win32", "darwin")
    if sys.stdout is None or sys.stderr is None or zonder_console:
        try:
            pad = os.path.join(paden.gebruikers_map(), "dmxdesk.log")
            if os.path.exists(pad) and os.path.getsize(pad) > 2_000_000:
                os.replace(pad, pad + ".oud")
            f = open(pad, "a", encoding="utf-8", buffering=1)
            if sys.stdout is None or zonder_console:
                sys.stdout = f
            if sys.stderr is None or zonder_console:
                sys.stderr = f
        except OSError:
            pass


def beat_lus(engine):
    """Beats van de externe beat-luisteraar (Pi: Spotify en MPD) via UDP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", BEAT_POORT))
    except OSError as e:
        print(f"Beat-poort {BEAT_POORT} bezet ({e}); externe beat-luisteraar wordt niet gebruikt", flush=True)
        return
    while True:
        data, _ = sock.recvfrom(4096)
        try:
            engine.beat_bericht(json.loads(data))
        except (ValueError, TypeError, AttributeError):
            pass


def draait_al(poort):
    """Draait er op deze poort al een DMXDesk? Dan openen we die in plaats van een tweede te starten."""
    try:
        zonder_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # geen systeem-proxy nodig
        with zonder_proxy.open(f"http://127.0.0.1:{poort}/api/info", timeout=0.8) as r:
            return json.loads(r.read()).get("naam") == NAAM
    except Exception:
        return False


def open_server(app, poorten):
    fout = None
    for poort in poorten:
        try:
            return maak_server(app, poort), poort
        except OSError as e:
            fout = e
            print(f"Poort {poort} is bezet, volgende proberen…", flush=True)
    raise SystemExit(f"Geen vrije poort gevonden: {fout}")


def open_venster(url, titel):
    """Eigen app-venster met pywebview. Geeft False als dat niet lukt (dan de browser)."""
    try:
        import webview
    except Exception as e:
        print("App-venster niet beschikbaar (pywebview):", e, flush=True)
        return False
    try:
        if hasattr(webview, "settings"):
            webview.settings["ALLOW_DOWNLOADS"] = True     # show exporteren
        webview.create_window(titel, url, width=1440, height=900, min_size=(960, 600), background_color="#0b0b0d")
        print("App-venster wordt geopend", flush=True)
        webview.start()
        return True
    except Exception as e:
        print("App-venster openen mislukt, de browser wordt gebruikt:", e, flush=True)
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dmxdesk", description=f"{NAAM} {VERSIE}: DMX-lichtsturing")
    parser.add_argument("--poort", type=int, default=int(os.environ.get("DMXDESK_POORT") or 0) or None)
    parser.add_argument("--show", default=None, help="pad naar het showbestand")
    parser.add_argument("--server", action="store_true", help="zonder venster en zonder browser (Pi / dienst)")
    parser.add_argument("--browser", action="store_true", help="in de gewone browser openen in plaats van een venster")
    parser.add_argument("--versie", action="version", version=f"{NAAM} {VERSIE}")
    args = parser.parse_args(argv)
    if not args.server:
        logbestand_als_nodig()
    stapsgewijs = sys.stderr is not None and hasattr(sys.stderr, "fileno")
    if stapsgewijs:
        try:     # vastlopen of crashen tijdens het opstarten: waar precies komt in het logbestand
            faulthandler.enable(file=sys.stderr)
            faulthandler.dump_traceback_later(20, file=sys.stderr)
        except (ValueError, OSError, AttributeError, io.UnsupportedOperation):
            stapsgewijs = False

    poort_gekozen = args.poort is not None
    poort = args.poort or STANDAARD_POORT
    if not args.server and draait_al(poort):
        url = f"http://127.0.0.1:{poort}/desk"
        print(f"{NAAM} draait al, dat venster wordt geopend: {url}", flush=True)
        if not (not args.browser and open_venster(url, NAAM)):
            webbrowser.open(url)
        return

    show = args.show or paden.show_bestand()
    print(f"{NAAM} {VERSIE} – show: {show}", flush=True)
    engine = Engine(show)
    if not os.path.exists(show):
        engine.opslaan()

    uitvoer = UitvoerBeheer(engine)
    audio = AudioInvoer(engine)
    midi = Midi(engine)
    spotify = SpotifySpeaker(engine)
    bibliotheek = Bibliotheek()
    stoppen = threading.Event()
    app = App(engine, bibliotheek, uitvoer, audio, midi, afsluiten=stoppen.set, spotify=spotify)

    server, poort = open_server(app, [poort] if (poort_gekozen or args.server) else [poort, *RESERVE_POORTEN])
    app.poort = poort

    for doel in (motor_lus, opslag_lus, beat_lus):
        threading.Thread(target=doel, args=(engine,), daemon=True, name=doel.__name__).start()
    uitvoer.bijwerken()
    audio.bijwerken()
    midi.bijwerken()
    if engine.data["spotify"]["aan"] is None:
        # eerste keer: in de desktop-app is DMXDesk meteen een Spotify-speaker; op de Pi (--server) doet raspotify dat
        with engine.lock:
            engine.data["spotify"]["aan"] = not args.server and spotify.beschikbaar()
            engine.gewijzigd()
    spotify.bijwerken()
    threading.Thread(target=server.serve_forever, daemon=True, name="webserver").start()

    try:     # systemctl stop / uitzetten: netjes opslaan en de lampen uit
        signal.signal(signal.SIGTERM, lambda *_: stoppen.set())
    except (ValueError, AttributeError):
        pass

    if stapsgewijs:
        faulthandler.cancel_dump_traceback_later()
    url = f"http://127.0.0.1:{poort}/desk"
    print(f"{NAAM} draait op poort {poort}", flush=True)
    for adres in lan_adressen(poort):
        print(f"  telefoon/tablet: {adres}", flush=True)

    try:
        if args.server:
            stoppen.wait()
        elif not args.browser and open_venster(url, NAAM):
            pass            # venster is dicht: afsluiten
        else:
            webbrowser.open(url)
            print("Afsluiten: Ctrl+C, of Instellingen → Afsluiten in de app", flush=True)
            while not stoppen.wait(0.5):
                pass
    except KeyboardInterrupt:
        pass
    finally:
        afsluiten(engine, uitvoer, audio, midi, spotify, server, app)


def afsluiten(engine, uitvoer, audio, midi, spotify, server, app):
    print("Afsluiten…", flush=True)
    app.stoppen.set()
    try:
        if engine.moet_opslaan:
            engine.opslaan()
    except OSError as e:
        print("Opslaan mislukt:", e, flush=True)
    # lampen donker achterlaten: een paar lege frames versturen voor de uitgangen stoppen
    with engine.lock:
        engine.render = lambda nu: engine.frames      # motor stilzetten
        engine.frames = {u: bytearray(512) for u in engine.frames}
    time.sleep(0.15)
    for onderdeel in (spotify, audio, midi, uitvoer):
        try:
            onderdeel.stop()
        except Exception:
            pass
    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    main()
