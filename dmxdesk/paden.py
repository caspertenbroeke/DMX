"""Waar bestanden staan: de show van de gebruiker, en de meegeleverde web- en databestanden."""
import os
import sys

from . import NAAM


def pakket_map():
    """Map van het dmxdesk-pakket, ook als de app met PyInstaller is ingepakt."""
    basis = getattr(sys, "_MEIPASS", None)
    if basis:
        return os.path.join(basis, "dmxdesk")
    return os.path.dirname(os.path.abspath(__file__))


def web_map():
    return os.path.join(pakket_map(), "web")


def data_bestand(naam):
    return os.path.join(pakket_map(), "data", naam)


def gebruikers_map():
    """Plek voor de show van deze gebruiker: %APPDATA%, ~/Library/Application Support of ~/.config."""
    if sys.platform == "win32":
        basis = os.environ.get("APPDATA") or os.path.expanduser("~")
        map_ = os.path.join(basis, NAAM)
    elif sys.platform == "darwin":
        map_ = os.path.join(os.path.expanduser("~"), "Library", "Application Support", NAAM)
    else:
        basis = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        map_ = os.path.join(basis, NAAM.lower())
    os.makedirs(map_, exist_ok=True)
    return map_


def show_bestand():
    return os.environ.get("DMXDESK_SHOW") or os.path.join(gebruikers_map(), "show.json")
