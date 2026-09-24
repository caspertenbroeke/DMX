"""Maakt het app-icoon (packaging/icoon.png, .ico) met Pillow, in dezelfde stijl als dmxdesk/web/icoon.svg."""
import os

from PIL import Image, ImageChops, ImageDraw

HIER = os.path.dirname(os.path.abspath(__file__))
N = 1024


def laag():
    return Image.new("RGBA", (N, N), (0, 0, 0, 0))


def maak():
    s = N / 64
    basis = laag()
    d = ImageDraw.Draw(basis)
    d.rounded_rectangle([0, 0, N - 1, N - 1], radius=int(14 * s), fill=(20, 20, 24, 255))
    bundel = laag()
    ImageDraw.Draw(bundel).polygon([(25 * s, 13 * s), (39 * s, 13 * s), (52 * s, 54 * s), (12 * s, 54 * s)],
                                   fill=(255, 196, 0, 44))
    basis = Image.alpha_composite(basis, bundel)
    ImageDraw.Draw(basis).rounded_rectangle([23 * s, 7 * s, 41 * s, 16 * s], radius=int(3 * s), fill=(255, 196, 0, 255))
    licht = Image.new("RGB", (N, N), (0, 0, 0))
    for (x, y), kleur in (((23, 44), (255, 59, 48)), ((41, 44), (10, 132, 255)), ((32, 34), (48, 209, 88))):
        cirkel = Image.new("RGB", (N, N), (0, 0, 0))
        ImageDraw.Draw(cirkel).ellipse([(x - 10) * s, (y - 10) * s, (x + 10) * s, (y + 10) * s], fill=kleur)
        licht = ImageChops.add(licht, cirkel)       # optellen, zoals licht: rood + groen = geel
    masker = licht.convert("L").point(lambda v: 255 if v > 0 else 0)
    basis.paste(licht, (0, 0), masker)
    return basis


if __name__ == "__main__":
    img = maak()
    img.save(os.path.join(HIER, "icoon.png"))
    img.save(os.path.join(HIER, "icoon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icoon.png en icoon.ico gemaakt")
