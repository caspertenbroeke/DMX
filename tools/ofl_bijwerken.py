#!/usr/bin/env python3
"""Haalt de complete Open Fixture Library op en pakt die in voor DMXDesk (dmxdesk/data/ofl.json.gz).

  python tools/ofl_bijwerken.py              downloaden van open-fixture-library.org
  python tools/ofl_bijwerken.py ofl.zip      een eerder gedownloade download.ofl gebruiken

De fixtures blijven in het OFL-formaat (verkleind); DMXDesk zet ze pas om als je een lamp kiest.
Licentie van de data: MIT, (c) de makers van de Open Fixture Library.
"""
import gzip
import io
import json
import os
import sys
import time
import urllib.request
import zipfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))

from dmxdesk.bibliotheek import ofl_naar_profielen  # noqa: E402

URL = "https://open-fixture-library.org/download.ofl"
DATA = os.path.join(os.path.dirname(HIER), "dmxdesk", "data")
DOEL = os.path.join(DATA, "ofl.json.gz")            # {sleutel: fixture als JSON-tekst}: pas uitpakken als je hem kiest
INDEX = os.path.join(DATA, "ofl-index.json.gz")     # klein: om te zoeken
WEG = {"$schema", "meta", "links", "rdm", "helpWanted", "comment", "physical", "fixtureKey", "manufacturerKey", "oflURL"}


def opschonen(o, diepte=0):
    if isinstance(o, dict):
        return {k: opschonen(v, diepte + 1) for k, v in o.items()
                if not (k in WEG and diepte == 0) and k not in ("helpWanted", "rdmPersonalityIndex")}
    if isinstance(o, list):
        return [opschonen(v, diepte + 1) for v in o]
    return o


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            ruw = f.read()
    else:
        print("Downloaden:", URL)
        with urllib.request.urlopen(URL, timeout=120) as r:
            ruw = r.read()
    zf = zipfile.ZipFile(io.BytesIO(ruw))
    fabrikanten = {k: v["name"] for k, v in json.loads(zf.read("manufacturers.json")).items() if not k.startswith("$")}
    fixtures, index, fouten = {}, [], 0
    for naam in sorted(zf.namelist()):
        if not naam.endswith(".json") or "/" not in naam:
            continue
        sleutel = naam[:-5]
        man = sleutel.split("/")[0]
        d = json.loads(zf.read(naam))
        schoon = opschonen(d)
        try:
            modi = ofl_naar_profielen(schoon, fabrikanten.get(man, man))
        except Exception as e:  # een kapotte fixture mag de rest niet tegenhouden
            fouten += 1
            print("Overgeslagen:", sleutel, repr(e))
            continue
        if not modi:
            continue
        fixtures[sleutel] = json.dumps(schoon, ensure_ascii=False, separators=(",", ":"))
        index.append({"sleutel": sleutel, "fabrikant": fabrikanten.get(man, man), "naam": d.get("name", sleutel),
                      "soort": modi[0][1]["soort"],
                      "modi": [{"naam": m, "kanalen": len(p["kanalen"])} for m, p in modi]})
    kop = {"bron": "Open Fixture Library (https://open-fixture-library.org), MIT-licentie",
           "datum": time.strftime("%Y-%m-%d"), "fabrikanten": fabrikanten}
    os.makedirs(DATA, exist_ok=True)
    with gzip.open(INDEX, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(dict(kop, index=index), f, ensure_ascii=False, separators=(",", ":"))
    with gzip.open(DOEL, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(fixtures, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(index)} lampen van {len(fabrikanten)} merken, {fouten} overgeslagen -> {DATA} "
          f"({os.path.getsize(INDEX) // 1024} + {os.path.getsize(DOEL) // 1024} kB)")


if __name__ == "__main__":
    main()
