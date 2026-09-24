import json
import threading
import urllib.request

import pytest

from dmxdesk.bibliotheek import Bibliotheek
from dmxdesk.engine import Engine
from dmxdesk.server import App, maak_server


@pytest.fixture
def server(tmp_path):
    e = Engine(str(tmp_path / "show.json"))
    app = App(e, Bibliotheek())
    srv = maak_server(app, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{srv.server_address[1]}"
    yield basis, e
    app.stoppen.set()
    srv.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as fout:
        return fout.code, json.loads(fout.read())


def test_paginas(server):
    basis, _ = server
    for pad in ("/", "/desk", "/instellingen", "/static/desk.css", "/static/js/main.js", "/static/js/tabs/live.js",
                "/manifest.webmanifest", "/static/icoon.svg"):
        assert get(basis + pad)[0] == 200, pad
    with pytest.raises(urllib.error.HTTPError):
        get(basis + "/static/../engine.py")


def test_api(server):
    basis, e = server
    status, body = get(basis + "/api/state")
    s = json.loads(body)
    assert status == 200 and s["fixtures"] and s["modi"]["kleur"]
    licht = json.loads(get(basis + "/api/state?deel=licht")[1])
    assert "fixtures" not in licht and "show" in licht
    assert post(basis + "/api/show", {"master": 40})[0] == 200
    assert e.data["show"]["master"] == 40
    assert post(basis + "/api/scene", {"actie": "opslaan", "naam": "Test", "inhoud": "effecten"})[0] == 200
    assert post(basis + "/api/scene", {"actie": "laden", "naam": "Test"})[0] == 200
    code, fout = post(basis + "/api/scene", {"actie": "laden", "naam": "Bestaat niet"})
    assert code == 400 and "bestaat niet" in fout["fout"]
    assert post(basis + "/api/hold", {"strobe": True})[0] == 200
    assert json.loads(get(basis + "/api/status")[1])["strobe"]
    code, r = post(basis + "/api/profiel-import", {"naam": "x.json", "inhoud": "geen json"})
    assert code == 400
    r = json.loads(get(basis + "/api/bibliotheek?zoek=chauvet")[1])
    assert r["totaal"] > 0
    export = json.loads(get(basis + "/api/export")[1])
    assert "Test" in export["scenes"]


def test_live_stream(server):
    basis, _ = server
    with urllib.request.urlopen(basis + "/api/live?monitor=1", timeout=5) as r:
        regel = r.readline()
    d = json.loads(regel[len(b"data: "):])
    assert "s" in d and "v" in d and len(d["f"]) == 512
