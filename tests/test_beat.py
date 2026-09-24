import numpy as np

from dmxdesk import beatluister as bl


def muziek(bpm, sec=24, sr=44100, start=0.37):
    rng = np.random.default_rng(1)
    y = 0.02 * rng.standard_normal(int(sec * sr))
    periode = 60.0 / bpm
    for k in np.arange(start, sec, periode):
        i, n = int(k * sr), int(0.15 * sr)
        t = np.arange(n) / sr
        y[i:i + n] += (0.8 * np.sin(2 * np.pi * (50 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 18))[:len(y[i:i + n])]
        j = int((k + periode / 2) * sr)
        hat = 0.2 * rng.standard_normal(int(0.05 * sr)) * np.exp(-np.arange(int(0.05 * sr)) / sr * 60)
        y[j:j + len(hat)] += hat[:len(y[j:j + len(hat)])]
    return y.astype(np.float32)


def test_numpy_beatzoeker_vindt_tempo_en_fase():
    for bpm in (100, 128, 140):
        berichten = []
        a = bl.Analyse("test", zender=berichten.append)
        a.tempo = bl.NumpyTempo()
        y = muziek(bpm)
        for s in range(0, len(y), 1024):
            a.voer_mono(y[s:s + 1024], (s + 1024) / 44100)
        beats = [m for m in berichten if m["soort"] == "beat" and m["t"] > 12]
        assert beats, bpm
        assert abs(np.median([m["bpm"] for m in beats]) - bpm) < 1.5, bpm
        periode = 60.0 / bpm
        fout = [((m["t"] - 0.37 + periode / 2) % periode - periode / 2) for m in beats]
        assert abs(np.median(fout)) < 0.05, (bpm, np.median(fout))
