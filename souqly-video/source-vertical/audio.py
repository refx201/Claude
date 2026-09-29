"""موسيقى إلكترونية مستقبلية + مؤثرات متزامنة لإعلان سوقلي العمودي (18 ث، 120 BPM، فا صغير)."""
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 44100; DUR = 18.0; N = int(SR * DUR)
rng = np.random.default_rng(11)
BEAT = 0.5; BAR = 2.0
MUS = np.zeros((N, 2)); PADB = np.zeros((N, 2)); SFX = np.zeros((N, 2))


def T(d): return np.arange(int(SR * d)) / SR
def mtof(m): return 440 * 2 ** ((m - 69) / 12)


def filt(x, kind, f, order=2):
    if kind == 'bp':
        sos = butter(order, [f[0] / (SR / 2), min(.99, f[1] / (SR / 2))], 'band', output='sos')
    else:
        sos = butter(order, min(.99, f / (SR / 2)), kind, output='sos')
    return sosfilt(sos, x)


def sweep(n, fcs, q=(0.6, 1.6), seg=256):
    out = np.zeros(len(n)); zi = np.zeros((1, 2))
    for i in range(0, len(n), seg):
        fc = fcs(i / len(n))
        sos = butter(1, [max(20, fc * q[0]) / (SR / 2), min(0.99, fc * q[1] / (SR / 2))], 'band', output='sos')
        out[i:i + seg], zi = sosfilt(sos, n[i:i + seg], zi=zi)
    return out


def add(bus, sig, at, g=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N or at < 0: return
    s = sig[:N - i] * g
    bus[i:i + len(s), 0] += s * np.sqrt((1 - pan) / 2) * 1.414
    bus[i:i + len(s), 1] += s * np.sqrt((1 + pan) / 2) * 1.414


# ---------- آلات ----------
def kick(g=1.0):
    t = T(0.5); f = 42 + 130 * np.exp(-t * 30)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6.5)
    s[:100] += rng.standard_normal(100) * .35 * np.linspace(1, 0, 100)
    return np.tanh(s * 1.8) * g


def clap():
    t = T(0.3); n = rng.standard_normal(len(t)); env = np.exp(-t * 18)
    for d in (0, .012, .024): env += np.where(t > d, np.exp(-(t - d) * 80), 0) * .6
    return filt(n * env, 'bp', (1000, 4000)) * .9


def hat(op=False):
    t = T(.2 if op else .045)
    return filt(rng.standard_normal(len(t)), 'high', 8000) * np.exp(-t * (15 if op else 80)) * .5


def supersaw(m, d, voices=7, spread=22, harm=16):
    t = T(d); s = np.zeros(len(t)); f0 = mtof(m)
    for v in range(voices):
        f = f0 * 2 ** (((v - (voices - 1) / 2) / ((voices - 1) / 2)) * spread / 1200)
        ph = rng.random() * 6.28
        for k in range(1, harm + 1):
            if f * k > 14000: break
            s += np.sin(2 * np.pi * f * k * t + ph * k) / k
    return s / voices


def chord(ms, d, cut=2400):
    s = sum(supersaw(m, d) for m in ms)
    t = T(d); env = np.minimum(1, t / .02) * np.minimum(1, (d - t) / .08)
    return filt(s, 'low', cut) * env * .06


def subbass(m, d):
    t = T(d); f = mtof(m)
    s = np.sin(2 * np.pi * f * t) + .5 * filt(supersaw(m, d, 3, 8, 8), 'low', 400)
    env = np.minimum(1, t / .005) * np.minimum(1, (d - t) / .03)
    return np.tanh(s * env * 1.4) * .5


def pluck(m, d=.3, bright=1.0):
    t = T(d); f = mtof(m)
    s = np.sign(np.sin(2 * np.pi * f * t)) * .35 + np.sin(2 * np.pi * f * t)
    s = filt(s, 'low', 1500 + 4000 * bright)
    return s * np.exp(-t * 12) * np.minimum(1, t / .002) * .14


def pad(ms, d, cut=1200):
    s = sum(supersaw(m, d, 5, 14, 10) for m in ms)
    t = T(d); env = np.minimum(1, t / .6) * np.minimum(1, (d - t) / .8)
    return filt(s, 'low', cut) * env * .05


# فا صغير: Fm Db Ab Eb
CH = [(53, 56, 60), (49, 53, 56), (56, 60, 63), (51, 55, 58)]
RT = [41, 37, 44, 39]

# ---------- المقدمة 0-4: باد + تكّات رقمية ----------
add(PADB, pad(CH[0] + (65,), 4.2, 900), 0, 1.0)
add(MUS, subbass(29, 4.0) * np.linspace(0, 1, int(SR * 4.0)) ** 2, 0, .5)
arpI = [65, 68, 72, 75]
for k, tt in enumerate(np.arange(0, 3.9, BEAT / 4)):
    add(MUS, pluck(arpI[k % 4] + (12 if k % 8 >= 6 else 0), .2, .3 + .7 * tt / 4), tt, .55 + .5 * tt / 4, .5 if k % 2 else -.5)
for tt in np.arange(1.0, 3.9, BEAT):
    add(MUS, hat(), tt + .25, .25, .3)

# ---------- القسم الرئيسي 4-11 ----------
G0, G1 = 4.0, 11.0
for b in np.arange(G0, G1, BEAT):
    add(MUS, kick(), b, .9)
    if int(round((b - G0) / BEAT)) % 2 == 1: add(MUS, clap(), b, .4, .1)
for b in np.arange(G0 + .25, G1, BEAT):
    add(MUS, hat(int(round((b - G0 - .25) / BEAT)) % 4 == 3), b, .45, -.3)
for b in np.arange(G0, G1, BEAT / 4):
    add(MUS, hat(), b, .12, .4)
for bar in range(int((G1 - G0) / BAR) + 1):
    t0 = G0 + bar * BAR; c = bar % 4
    if t0 >= G1: break
    d = min(BAR, G1 - t0)
    add(PADB, chord(CH[c] + (CH[c][0] + 12,), d, 3200), t0, 1.0)
    for k in range(8):
        tt = t0 + k * BEAT / 2
        if tt >= G1: break
        add(MUS, subbass(RT[c] - 12 + (12 if k % 2 else 0), BEAT / 2 * .9), tt, .75)
    arp = [CH[c][0] + 24, CH[c][2] + 12, CH[c][1] + 24, CH[c][2] + 24]
    for k in range(16):
        tt = t0 + k * BEAT / 4
        if tt >= G1: break
        add(MUS, pluck(arp[k % 4], .22, 1.0), tt, .6, .45 if k % 2 else -.45)

# ---------- البناء 10.5-12 ----------
for i, b in enumerate(np.arange(11.0, 12.0, BEAT / 4)):
    add(MUS, clap(), b, .1 + .4 * i / 8)
for i, b in enumerate(np.arange(11.0, 12.0, BEAT / 8)):
    add(MUS, pluck(77 + (i % 4) * 3, .12, 1), b, .2 + .3 * i / 16, .3 if i % 2 else -.3)
n = rng.standard_normal(int(SR * 1.5))
add(MUS, sweep(n, lambda k: 300 + 9000 * k ** 2, (.7, 1.4)) * np.linspace(0, 1, len(n)) ** 2 * .9, 10.5, 1.0)

# ---------- الضربة النهائية 12 + الخاتمة ----------
t = T(2.5); f = 32 + 140 * np.exp(-t * 14)
boom = np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2) * 2.2) * .9
add(MUS, boom, 12.0, 1.0)
crash = filt(rng.standard_normal(int(SR * 2.5)), 'high', 4000) * np.exp(-T(2.5) * 2.2) * .35
add(MUS, crash, 12.0, 1.0, -.2); add(MUS, crash[::-1][::-1] * .8, 12.01, 1.0, .2)
add(MUS, chord((53, 60, 65, 68, 72), 1.2, 5000) * np.exp(-T(1.2) * 2.5) * 2.2, 12.0, 1.0)
add(PADB, pad((41, 53, 60, 65, 68, 72), 6.0, 1600), 12.0, 1.6)
arpO = [72, 75, 77, 80, 84, 80, 77, 75]
for k, tt in enumerate(np.arange(12.5, 17.6, BEAT / 2)):
    g = .5 * (1 - (tt - 12.5) / 5.5)
    add(MUS, pluck(arpO[k % 8], .35, .6), tt, g, .5 if k % 2 else -.5)
add(MUS, subbass(29, 5.5) * np.exp(-T(5.5) * .6), 12.0, .6)

# ---------- مضخّة السايدتشين على الباد ----------
pump = np.ones(N); tt = np.arange(N) / SR
m = (tt >= G0) & (tt < G1)
ph = ((tt - G0) % BEAT)
pump[m] = 1 - .75 * np.exp(-ph[m] * 9)
MUS += PADB * pump[:, None]


# ---------- مؤثرات ----------
def whoosh(d=.5, up=True, g=.6):
    n = rng.standard_normal(int(SR * d)); t = T(d)
    o = sweep(n, lambda k: 300 + 6000 * (k if up else 1 - k))
    return o * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2 * g * 3


def tick(f=4200):
    t = T(.04)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 220) * .4 +
            filt(rng.standard_normal(len(t)), 'high', 5000) * np.exp(-t * 400) * .25)


def click():
    t = T(.06)
    return np.sin(2 * np.pi * 2600 * t) * np.exp(-t * 160) * .5 + filt(rng.standard_normal(len(t)), 'high', 2500) * np.exp(-t * 300) * .3


def zap(f0=2400, f1=600, d=.18):
    t = T(d); f = np.linspace(f0, f1, len(t))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 18) * .25


def ping(f1=1568, f2=2093):
    t = T(.7)
    a = np.sin(2 * np.pi * f1 * t) * np.exp(-t * 7)
    b = np.where(t > .09, np.sin(2 * np.pi * f2 * (t - .09)) * np.exp(-(t - .09) * 6), 0)
    return (a + b) * np.minimum(1, t / .003) * .22


def impact(g=1.0):
    t = T(1.0); f = 38 + 100 * np.exp(-t * 18)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4)
    nz = filt(rng.standard_normal(len(t)), 'low', 2500) * np.exp(-t * 12) * .5
    return np.tanh((s + nz) * 1.5) * .7 * g


def shimmer(d=1.4):
    t = T(d); s = np.zeros(len(t))
    for i, m in enumerate([84, 89, 91, 96, 101]):
        s += np.sin(2 * np.pi * mtof(m) * t) * np.exp(-t * (2.5 + i)) * (t > i * .04)
    return s * .06


# المقدمة: البطاقات
for i, a in enumerate([.15, .5, .85, 1.2, 1.5, 1.75]):
    add(SFX, whoosh(.35, True, .35), a - .12, 1, (-.5 if i % 2 else .5))
    add(SFX, tick(3600 + 300 * i), a + .18, .8, (-.3 if i % 2 else .3))
# الروابط
for i in range(6):
    add(SFX, zap(3000 - i * 200, 900), 2.85 + i * .05, .8, (-.4 if i % 2 else .4))
for i, a in enumerate(np.arange(3.2, 3.95, .09)):
    add(SFX, tick(5000 + 150 * i), a, .35)
n = rng.standard_normal(int(SR * 1.0))
add(SFX, sweep(n, lambda k: 400 + 6000 * k ** 2) * np.linspace(0, 1, len(n)) ** 2 * 1.2, 3.0, 1.0)
# الانفجار والتجميع
add(SFX, impact(1.0), 4.0, 1.0)
add(SFX, whoosh(.5, False, .5), 3.95, 1.0)
for i in range(8):
    add(SFX, tick(3000 + 200 * i), 4.22 + i * .07, .55, (-.3 if i % 2 else .3))
add(SFX, shimmer(1.0), 4.75, .9)
add(SFX, click(), 5.37, 1.0)
add(SFX, whoosh(.45, True, .3), 5.5, 1.0, -.3)
add(SFX, ping(2093, 2637), 5.98, .8)
add(SFX, whoosh(.8, False, .25), 6.3, 1.0, .3)
# التصغير للجوال
n = rng.standard_normal(int(SR * .6)); rev = filt(n, 'high', 3000) * np.linspace(0, 1, len(n)) ** 3 * .6
add(SFX, rev, 7.4, 1.0)
add(SFX, whoosh(.6, True, .5), 7.75, 1.0)
add(SFX, impact(.75), 8.0, 1.0)
# الإشعارات
for i, a in enumerate([9.0, 9.5, 10.0, 10.5]):
    add(SFX, whoosh(.25, True, .2), a - .08, 1.0, (.4 if i % 2 else -.4))
    add(SFX, ping(1568 if i % 2 == 0 else 1760, 2093 if i % 2 == 0 else 2349), a + .05, .9, (.3 if i % 2 else -.3))
# الجسيمات
n = rng.standard_normal(int(SR * 1.0))
gran = filt(n, 'bp', (3000, 9000)) * (rng.random(len(n)) > .985) * 4
add(SFX, gran * np.sin(np.pi * np.linspace(0, 1, len(n))) * .5, 11.0, 1.0)
add(SFX, whoosh(1.0, True, .45), 11.0, 1.0)
# الضربة
add(SFX, shimmer(1.8), 12.0, 1.4)
# النصوص
for i in range(4): add(SFX, tick(2600 + 250 * i), 12.62 + i * .14, .35)
add(SFX, whoosh(.4, True, .2), 13.4, 1.0)
add(SFX, click(), 14.1, .8)
add(SFX, shimmer(1.0), 14.6, .7)

# ---------- ماستر ----------
mix = MUS * .85 + SFX
fade = np.ones(N); fl = int(1.2 * SR); fade[-fl:] = np.linspace(1, 0, fl) ** 1.5
mix *= fade[:, None]
mix = np.tanh(mix * 1.2) / np.tanh(1.2)
mix /= np.abs(mix).max() / .9
wavfile.write('../music2.wav', SR, (mix * 32767).astype(np.int16))
print('ok')
