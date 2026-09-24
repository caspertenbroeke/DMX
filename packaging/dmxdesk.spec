# PyInstaller-recept voor DMXDesk. Bouwen: python packaging/bouw.py
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
PKG = os.path.join(ROOT, "dmxdesk")
IS_MAC, IS_WIN = sys.platform == "darwin", sys.platform == "win32"
ICOON = os.path.join(SPECPATH, "icoon.ico" if IS_WIN else "icoon.png")

datas = [(os.path.join(PKG, "web"), "dmxdesk/web"), (os.path.join(PKG, "data"), "dmxdesk/data")]
# Spotify-speaker: librespot (gebouwd met: cargo install librespot --root .librespot, zie de workflow)
LIBRESPOT = os.environ.get("DMXDESK_LIBRESPOT_BOUW") or os.path.join(
    ROOT, ".librespot", "bin", "librespot.exe" if IS_WIN else "librespot")
binaries = [(LIBRESPOT, "dmxdesk/bin")] if os.path.isfile(LIBRESPOT) else []
print("librespot:", LIBRESPOT if binaries else "NIET gevonden - de app wordt gebouwd zonder Spotify-speaker")
verborgen = ["serial.tools.list_ports", "mido.backends.rtmidi", "qrcode.image.svg"]

a = Analysis(
    [os.path.join(SPECPATH, "start.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=verborgen,
    excludes=["tkinter", "PIL", "matplotlib", "PyQt5", "PyQt6", "PySide2", "PySide6", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="DMXDesk",
    console=not (IS_MAC or IS_WIN),   # Linux: in een terminal, met de browser als scherm
    icon=ICOON,
    codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="DMXDesk")

if IS_MAC:
    app = BUNDLE(
        coll,
        name="DMXDesk.app",
        icon=ICOON,
        bundle_identifier="nl.dmxdesk.app",
        info_plist={
            "CFBundleName": "DMXDesk",
            "CFBundleDisplayName": "DMXDesk",
            "CFBundleShortVersionString": os.environ.get("DMXDESK_VERSIE", "2.0.0"),
            "NSHighResolutionCapable": True,
            "NSMicrophoneUsageDescription": "DMXDesk luistert naar de muziek om de lichtshow op de beat te laten lopen.",
            "NSLocalNetworkUsageDescription": "DMXDesk stuurt licht via het netwerk (Art-Net/sACN), laat je telefoon "
                                              "meebedienen en verschijnt in Spotify als speaker.",
            "NSBonjourServices": ["_spotify-connect._tcp"],
            "LSApplicationCategoryType": "public.app-category.music",
        },
    )
