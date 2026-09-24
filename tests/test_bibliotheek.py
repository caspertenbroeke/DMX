import json

from dmxdesk.bibliotheek import Bibliotheek, importeer_bestand, ofl_naar_profielen

QXF = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE FixtureDefinition>
<FixtureDefinition xmlns="http://www.qlcplus.org/FixtureDefinition">
 <Manufacturer>Testmerk</Manufacturer>
 <Model>Spot 7</Model>
 <Type>Moving Head</Type>
 <Channel Name="Pan" Preset="PositionPan"/>
 <Channel Name="Tilt"><Group Byte="0">Tilt</Group></Channel>
 <Channel Name="Shutter" Preset="ShutterStrobeSlowFast">
  <Capability Min="0" Max="7">Closed</Capability>
  <Capability Min="8" Max="15" Preset="ShutterOpen">Open</Capability>
  <Capability Min="16" Max="255" Preset="StrobeSlowToFast">Strobe slow to fast</Capability>
 </Channel>
 <Channel Name="Dimmer" Preset="IntensityMasterDimmer"/>
 <Channel Name="Red" Preset="IntensityRed"/>
 <Channel Name="Green"><Group Byte="0">Intensity</Group><Colour>Green</Colour></Channel>
 <Channel Name="Gobo">
  <Group Byte="0">Gobo</Group>
  <Capability Min="0" Max="9">Open</Capability>
  <Capability Min="10" Max="19">Gobo 1</Capability>
 </Channel>
 <Mode Name="7 kanalen">
  <Channel Number="0">Pan</Channel><Channel Number="1">Tilt</Channel><Channel Number="2">Shutter</Channel>
  <Channel Number="3">Dimmer</Channel><Channel Number="4">Red</Channel><Channel Number="5">Green</Channel>
  <Channel Number="6">Gobo</Channel>
 </Mode>
</FixtureDefinition>"""


def test_qxf():
    modi = importeer_bestand("spot.qxf", QXF)
    assert len(modi) == 1
    naam, p = modi[0]
    assert p["fabrikant"] == "Testmerk" and p["soort"] == "moving"
    fn = [k["functie"] for k in p["kanalen"]]
    assert fn == ["pan", "tilt", "strobe", "dimmer", "red", "green", "fixed"]
    shutter = p["kanalen"][2]
    assert shutter["standaard"] == 8 and 16 < shutter["strobe"] <= 255
    assert p["kanalen"][6]["opties"][1]["naam"] == "Gobo 1"


def test_ofl_json_met_pixels():
    d = {
        "name": "Bar 4", "categories": ["Pixel Bar"],
        "availableChannels": {"Dimmer": {"capability": {"type": "Intensity"}}},
        "templateChannels": {c + " $pixelKey": {"capability": {"type": "ColorIntensity", "color": c}}
                             for c in ("Red", "Green", "Blue")},
        "matrix": {"pixelCount": [4, 1, 1]},
        "modes": [{"name": "13ch", "channels": ["Dimmer", {"insert": "matrixChannels", "repeatFor": "eachPixelXYZ",
                                                           "channelOrder": "perPixel",
                                                           "templateChannels": ["Red $pixelKey", "Green $pixelKey", "Blue $pixelKey"]}]}],
    }
    (_, p), = ofl_naar_profielen(d, "Merk")
    assert len(p["kanalen"]) == 13 and p["soort"] == "bar"
    assert [k["kop"] for k in p["kanalen"]] == [0] + [1] * 3 + [2] * 3 + [3] * 3 + [4] * 3
    assert p["kanalen"][4]["naam"] == "Red 2" and p["kanalen"][4]["functie"] == "red"
    modi = importeer_bestand("bar.json", json.dumps(d))
    assert modi[0][1]["naam"].startswith("Bar 4")


def test_bibliotheek_compleet():
    b = Bibliotheek()
    info = b.info()
    assert info["aantal"] > 600
    r = b.zoek("american dj mega par")
    assert r["totaal"] >= 1
    modi = b.profielen(r["resultaten"][0]["sleutel"])
    assert modi and modi[0]["profiel"]["kanalen"]
    assert b.profielen("ingebouwd/rgb_3")[0]["profiel"]["soort"] == "par"


def test_alle_ofl_lampen_omzetbaar():
    b = Bibliotheek()
    assert len(b.ofl()["index"]) > 600
    for item in b.ofl()["index"]:
        for m in b.profielen(item["sleutel"]):
            assert all(0 <= k["standaard"] <= 255 for k in m["profiel"]["kanalen"])
