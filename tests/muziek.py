"""Nagemaakte muziek om de analyse te testen en te ijken: hardstyle, house, rustig, opbouw, breakdown."""
import numpy as np

SR = 44100


def _ruis(n, rng):
    return rng.standard_normal(n).astype(np.float32)


def kick(lengte=0.35, hard=False):
    t = np.arange(int(lengte * SR)) / SR
    toon = 45 + (220 if hard else 110) * np.exp(-t * (18 if hard else 30))
    fase = 2 * np.pi * np.cumsum(toon) / SR
    k = np.sin(fase) * np.exp(-t * (6 if hard else 14))
    if hard:                                   # vervormd, zoals een hardstyle-kick
        k = np.tanh(4 * k) * 0.9
    return k.astype(np.float32)


def _leg(y, stuk, t):
    i = int(t * SR)
    if i >= len(y):
        return
    n = min(len(stuk), len(y) - i)
    y[i:i + n] += stuk[:n]


def _toon(freq, lengte, zacht=True):
    t = np.arange(int(lengte * SR)) / SR
    omhulling = np.minimum(1, t / 0.05) * np.exp(-t * (1.5 if zacht else 4))
    return (sum(np.sin(2 * np.pi * freq * k * t) / k for k in (1, 2, 3)) * omhulling * 0.25).astype(np.float32)


def rustig(bpm=150, sec=20, seed=1):
    """Rustig nummer op een hoog tempo: pianotonen, zachte pad, zachte hi-hat, lange basnoten, géén kick."""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(sec * SR), dtype=np.float32)
    p = 60 / bpm
    noten = [261.6, 329.6, 392.0, 440.0, 349.2, 293.7]
    for k, t in enumerate(np.arange(0, sec, p)):
        _leg(y, _toon(noten[k % len(noten)], p * 2), t)
        hat = 0.03 * _ruis(int(0.03 * SR), rng) * np.exp(-np.arange(int(0.03 * SR)) / SR * 80)
        _leg(y, hat, t + p / 2)
    for t in np.arange(0, sec, p * 8):          # basnoot per 2 maten, lang aangehouden
        _leg(y, 0.3 * _toon(65.4, p * 8), t)
    pad = 0.05 * np.sin(2 * np.pi * 220 * np.arange(len(y)) / SR) * (0.6 + 0.4 * np.sin(np.arange(len(y)) / SR))
    return (y + pad).astype(np.float32)


def hardstyle(bpm=150, sec=20, seed=2):
    """Harde kick op elke tel, vervormd, plus een lead."""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(sec * SR), dtype=np.float32)
    p = 60 / bpm
    for k, t in enumerate(np.arange(0, sec, p)):
        _leg(y, kick(p * 0.95, hard=True), t)
        hat = 0.08 * _ruis(int(0.04 * SR), rng) * np.exp(-np.arange(int(0.04 * SR)) / SR * 60)
        _leg(y, hat, t + p / 2)
        _leg(y, 0.6 * _toon([440, 523, 587, 659][(k // 2) % 4], p * 0.5, zacht=False), t + p / 2)
    return np.tanh(1.2 * y).astype(np.float32)


def house(bpm=126, sec=20, seed=3):
    rng = np.random.default_rng(seed)
    y = np.zeros(int(sec * SR), dtype=np.float32)
    p = 60 / bpm
    for k, t in enumerate(np.arange(0, sec, p)):
        _leg(y, kick(0.3), t)
        _leg(y, 0.35 * _toon(55, p * 0.4, zacht=False), t + p / 2)      # bas tussen de kicks
        hat = 0.1 * _ruis(int(0.04 * SR), rng) * np.exp(-np.arange(int(0.04 * SR)) / SR * 70)
        _leg(y, hat, t + p / 2)
        if k % 2:
            clap = 0.25 * _ruis(int(0.1 * SR), rng) * np.exp(-np.arange(int(0.1 * SR)) / SR * 30)
            _leg(y, clap, t)
    return y


def opbouw(bpm=150, sec=16, seed=4):
    """Geen kick; snare-roffel die steeds sneller gaat en een ruis-riser die aanzwelt."""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(sec * SR), dtype=np.float32)
    p = 60 / bpm
    t = 0.0
    while t < sec:
        voortgang = t / sec
        stap = p if voortgang < 0.25 else p / 2 if voortgang < 0.5 else p / 4 if voortgang < 0.75 else p / 8
        snare = (0.1 + 0.35 * voortgang) * _ruis(int(0.06 * SR), rng) * np.exp(-np.arange(int(0.06 * SR)) / SR * 40)
        _leg(y, snare, t)
        t += stap
    n = len(y)
    riser = _ruis(n, rng) * np.linspace(0.0, 0.25, n)
    y += riser.astype(np.float32)
    y += (0.08 * np.sin(2 * np.pi * 330 * np.arange(n) / SR)).astype(np.float32)
    return y


def breakdown(bpm=150, sec=16, seed=5):
    """Na een drop: alleen pads en melodie, geen kick."""
    return 0.8 * rustig(bpm, sec, seed)


def achter_elkaar(*stukken):
    return np.concatenate(stukken).astype(np.float32)
