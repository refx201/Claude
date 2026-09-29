"""موسيقى ومؤثرات أصلية مركّبة بالكود لإعلان سوقلي — 120 BPM، القطعات على الضربة."""
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 44100
DUR = 15.5
N = int(SR * DUR)
rng = np.random.default_rng(7)
L = np.zeros(N); R = np.zeros(N)
BEAT = 0.5
BAR = 2.0


def t_(d): return np.arange(int(SR * d)) / SR


def filt(x, kind, f, order=2):
    if kind == 'bp':
        sos = butter(order, [f[0] / (SR / 2), f[1] / (SR / 2)], 'band', output='sos')
    else:
        sos = butter(order, f / (SR / 2), kind, output='sos')
    return sosfilt(sos, x)


def add(sig, at, g=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N: return
    s = sig[:N - i] * g
    L[i:i + len(s)] += s * np.sqrt((1 - pan) / 2) * 1.414
    R[i:i + len(s)] += s * np.sqrt((1 + pan) / 2) * 1.414


def mtof(m): return 440 * 2 ** ((m - 69) / 12)


# ---------- الآلات ----------
def kick(g=1.0):
    t = t_(0.45)
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 7.5)
    s[:120] += rng.standard_normal(120) * 0.3 * np.linspace(1, 0, 120)
    return np.tanh(s * 1.6) * g


def clap():
    t = t_(0.25)
    n = rng.standard_normal(len(t))
    env = np.exp(-t * 22)
    for d in (0.0, 0.011, 0.022):
        env += np.where(t > d, np.exp(-(t - d) * 90), 0) * 0.6
    return filt(n * env, 'bp', (900, 3500)) * 0.9


def hat(open_=False):
    t = t_(0.18 if open_ else 0.05)
    n = rng.standard_normal(len(t))
    return filt(n, 'high', 7000) * np.exp(-t * (18 if open_ else 70)) * 0.5


def saw(freq, d, detune=(0,), harm=14):
    t = t_(d); s = np.zeros(len(t))
    for dt in detune:
        f = freq * 2 ** (dt / 1200)
        for k in range(1, harm + 1):
            if f * k > 12000: break
            s += np.sin(2 * np.pi * f * k * t + k) / k
    return s / len(detune)


def bass(m, d):
    s = saw(mtof(m), d, harm=10)
    t = t_(d)
    s = filt(s, 'low', 520)
    env = np.minimum(1, t / 0.005) * np.exp(-t * 3.5)
    return np.tanh(s * env * 1.5) * 0.55


def pluck(m, d=0.35):
    t = t_(d); f = mtof(m)
    s = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t))
    return s * np.exp(-t * 11) * np.minimum(1, t / 0.002) * 0.22


def pad(ms, d):
    s = sum(saw(mtof(m), d, detune=(-9, 0, 8), harm=8) for m in ms)
    s = filt(s, 'low', 1600)
    t = t_(d)
    env = np.minimum(1, t / 0.25) * np.minimum(1, (d - t) / 0.3)
    return s * env * 0.07


# الأوتار: Am F C G  (vi IV I V)
CH = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]
ROOT = [45, 41, 48, 43]

# ---------- الإيقاع (0 → 11.5) ----------
GROOVE_END = 11.5
beats = np.arange(0, GROOVE_END - 1e-6, BEAT)
for b in beats:
    bi = int(round(b / BEAT))
    if 8.5 <= b < 9.0: continue          # فراغ قبل الضربة
    add(kick(), b, 0.95 if b >= 9 else 0.85)
    if bi % 2 == 1 and b >= 1.0: add(clap(), b, 0.45, 0.1)
for b in np.arange(0.25, GROOVE_END, BEAT):
    if 8.5 <= b < 9.0: continue
    add(hat(open_=(int(b / BEAT) % 4 == 3)), b, 0.55, -0.3)
for b in np.arange(0, GROOVE_END, BEAT / 2):
    if int(round(b / (BEAT / 2))) % 2 == 0: continue
    add(hat(), b, 0.22, 0.35)
# لفّة سنير قبل الضربة
for i, b in enumerate(np.arange(8.0, 9.0, BEAT / 4)):
    add(clap(), b, 0.12 + 0.35 * i / 8, 0.0)

# الباص والبلَك والباد
for bar in range(int(np.ceil(GROOVE_END / BAR))):
    c = bar % 4
    t0 = bar * BAR
    for k in range(8):
        tt = t0 + k * BEAT / 2
        if tt >= GROOVE_END or 8.5 <= tt < 9.0: continue
        add(bass(ROOT[c] + (12 if k % 4 == 3 else 0), BEAT / 2 * 0.95), tt, 0.9)
    arp = [CH[c][0] + 12, CH[c][1] + 12, CH[c][2] + 12, CH[c][1] + 24]
    for k in range(16):
        tt = t0 + k * BEAT / 4
        if tt >= GROOVE_END or 8.5 <= tt < 9.0: continue
        add(pluck(arp[k % 4]), tt, 0.8, 0.4 if k % 2 else -0.4)
    add(pad(CH[c], min(BAR, max(0.1, GROOVE_END - t0))), t0, 1.0)

# ---------- الخاتمة: وتر مفتوح يرنّ ----------
end_ch = (48, 55, 60, 64, 67)  # C add
add(pad(end_ch, 3.8), 11.7, 1.6)
for i, m in enumerate([72, 76, 79, 84, 88]):
    add(pluck(m, 1.2), 12.2 + i * 0.09, 0.9, (-0.5 + i * 0.25))
add(bass(36, 2.5), 12.2, 1.0)
add(kick(1.0), 12.2, 1.0)
for b in np.arange(12.25, 15.0, BEAT / 2):
    add(hat(), b, 0.12, 0.3)


# ---------- المؤثرات ----------
def sweep(n, fcs, q=(0.6, 1.6), seg=256):
    """فلتر ممرّر نطاق متحرّك بحالة متصلة (بلا طقطقة)."""
    out = np.zeros(len(n)); zi = np.zeros((1, 2))
    for j, i in enumerate(range(0, len(n), seg)):
        fc = fcs(i / len(n))
        sos = butter(1, [fc * q[0] / (SR / 2), min(0.99, fc * q[1] / (SR / 2))], 'band', output='sos')
        out[i:i + seg], zi = sosfilt(sos, n[i:i + seg], zi=zi)
    return out


def whoosh(d=0.5, up=True):
    t = t_(d); n = rng.standard_normal(len(t))
    out = sweep(n, lambda k: 400 + 5000 * (k if up else 1 - k))
    env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
    return out * env * 0.55


def pop(f0=900, d=0.12):
    t = t_(d); f = f0 * np.exp(-t * 18) + f0 * 0.4
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30) * 0.35


def click():
    t = t_(0.05)
    return (np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 180) * 0.35 +
            filt(rng.standard_normal(len(t)), 'high', 3000) * np.exp(-t * 300) * 0.3)


def ding(f=1568, d=0.7):
    t = t_(d)
    s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 12)
    return s * np.exp(-t * 6) * np.minimum(1, t / 0.003) * 0.28


def boom():
    t = t_(0.7)
    f = 38 + 90 * np.exp(-t * 20)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5)
    n = filt(rng.standard_normal(len(t)), 'low', 1800) * np.exp(-t * 16) * 0.4
    return np.tanh((s + n) * 1.4) * 0.8


def riser(d):
    t = t_(d); n = rng.standard_normal(len(t))
    out = sweep(n, lambda k: 300 + 7000 * k ** 2, (0.7, 1.4))
    return out * (t / d) ** 2 * 0.4


def shimmer(d=1.6):
    t = t_(d); s = np.zeros(len(t))
    for i, m in enumerate([84, 88, 91, 96]):
        s += np.sin(2 * np.pi * mtof(m) * t) * np.exp(-t * (2.5 + i)) * np.where(t > i * 0.05, 1, 0)
    return s * 0.08


# مشهد ١
add(whoosh(0.45, True), 0.95, 0.7, 0.2)
for a in (1.45, 1.62, 1.95, 2.04, 2.13):
    add(pop(1100 if a > 1.9 else 800), a, 0.7, 0.3)
add(click(), 1.88, 1.0)
add(whoosh(0.4, False), 2.62, 0.8, -0.2)
# مشهد ٢
add(pop(600, 0.2), 3.45, 0.9)
add(click(), 4.76, 1.0)
add(ding(1318.5, 0.6), 4.87, 0.9); add(ding(1975.5, 0.8), 4.97, 0.8)
add(whoosh(0.4, False), 5.55, 0.7, 0.2)
# مشهد ٣ — الإشعارات
NT = [6.55, 6.95, 7.28, 7.55, 7.76, 7.93, 8.07, 8.19, 8.29, 8.38, 8.46, 8.53]
for i, a in enumerate(NT):
    g = 0.9 if i < 4 else max(0.25, 0.7 - 0.05 * i)
    add(ding(1568 if i % 2 == 0 else 1760, 0.5), a, g, (-0.3 if i % 2 else 0.3))
add(riser(0.95), 8.05, 0.9)
add(whoosh(0.5, True), 8.8, 0.8)
# مشهد ٤ — الضربات
for a in (9.12, 9.36, 9.6, 9.86):
    add(boom(), a, 0.75)
add(whoosh(0.35, True), 10.15, 0.45, 0.4)
# الخاتمة
add(riser(0.5), 10.95, 0.5)
add(whoosh(0.7, True), 11.3, 0.9)
add(boom(), 12.19, 0.55)
add(shimmer(), 12.2, 1.0)
add(whoosh(0.6, False), 12.45, 0.3, -0.4)
add(pop(700, 0.2), 13.2, 0.8)
add(click(), 14.28, 1.0)
add(shimmer(1.2), 14.35, 0.8)

# ---------- ماستر ----------
fade = np.ones(N); fl = int(0.6 * SR); fade[-fl:] = np.linspace(1, 0, fl) ** 2
mix = np.stack([L, R], 1) * fade[:, None]
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
mix /= np.abs(mix).max() / 0.89
wavfile.write('../music.wav', SR, (mix * 32767).astype(np.int16))
print('ok', mix.shape)
