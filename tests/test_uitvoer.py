import struct
import uuid

from dmxdesk.uitvoer import artnet_pakket, enttec_pro_pakket, sacn_multicast, sacn_pakket


def test_artnet():
    data = bytes(range(256)) * 2
    p = artnet_pakket(0x0123, 7, data)
    assert p[:8] == b"Art-Net\0"
    assert struct.unpack("<H", p[8:10])[0] == 0x5000
    assert p[12] == 7
    assert p[14:16] == bytes([0x23, 0x01])       # SubUni, Net
    assert struct.unpack(">H", p[16:18])[0] == 512
    assert p[18:] == data


def test_sacn():
    cid = uuid.uuid4().bytes
    p = sacn_pakket(3, 9, bytes([5] * 512), cid, bron="Test")
    assert len(p) == 638
    assert p[4:16] == b"ASC-E1.17\0\0\0"
    assert struct.unpack(">H", p[16:18])[0] & 0x0FFF == 622
    assert p[22:38] == cid
    assert p[44:48] == b"Test"
    assert p[111] == 9 and struct.unpack(">H", p[113:115])[0] == 3
    assert struct.unpack(">H", p[123:125])[0] == 513
    assert p[125] == 0 and p[126:] == bytes([5] * 512)
    assert sacn_multicast(3) == "239.255.0.3" and sacn_multicast(300) == "239.255.1.44"


def test_enttec_pro():
    p = enttec_pro_pakket(bytes([1] * 512))
    assert p[0] == 0x7E and p[1] == 6 and p[-1] == 0xE7
    assert struct.unpack("<H", p[2:4])[0] == 513
    assert len(p) == 518
