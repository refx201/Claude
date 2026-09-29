# -*- coding: utf-8 -*-
"""وضع المؤثرات — يطبّق fx.json على الفيديو المقصوص.   python3 27_fx_render.py <workdir> [--check | --preview 12.5,18]

  (بلا خيار)        يرندر: cutz_nofx.mp4 + fx.json → cutz.mp4 (والباقي من الخطوة ٧ يكمل عادي فوقه)
  --check           يلحق يده ويقص الشخص بنوافذ المؤثرات بس، ويطبع كم ٪ من الفريمات انلقطت — قبل الرندر
  --preview T,T,…   يحفظ فريمات بهالثواني بـfx_preview/ للمعاينة السريعة (بلا ترميز)

⛔ الأصل ما ينمسّ: أول مرة ينسخ cutz.mp4 لـcutz_nofx.mp4، وكل رندر يبدأ منه — تعدّل fx.json وتعيد براحتك.
لو أعدت 03_cut_zoom.py بعدها، ينتبه إن cutz.mp4 جديد ويعتمده أصلاً.

أنواع المؤثرات (التفصيل والأمثلة بـreferences/fx.md):
  باليد  : fire · lightning · smoke · sparkle · energy          (s · e · side · point · size · color)
  لحظية  : flash · shake · punch · glitch                       (t · dur · …)
  المكان : teleport                                             (s · e · bg · transition)
  توليد  : ai                                                   (s · e · file — من 28_fx_ai.py)
"""
import os, sys, json, math, zlib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fxlib as L

L.need_cv()
import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

W = os.path.abspath(sys.argv[1])
ARGS = sys.argv[2:]
CHECK = "--check" in ARGS
PREVIEW = []
if "--preview" in ARGS:
    PREVIEW = sorted(float(x) for x in ARGS[ARGS.index("--preview") + 1].split(","))

FX = L.load_fx(W)
EVENTS = FX.get("events", [])
HAND_KINDS = {"fire", "lightning", "smoke", "sparkle", "energy"}
INSTANT = {"flash", "shake", "punch", "glitch"}
KNOWN = HAND_KINDS | INSTANT | {"teleport", "ai"}

SRC = L.base_video(W)
VW, VH, FPS, NF = L.probe(SRC)
DT = 1.0 / FPS
HW, HH = VW // 2, VH // 2                  # طبقة المؤثرات بنص الدقة (تنغبّش أصلاً) — أسرع بأربع مرات


def hexrgb(h, d):
    h = (h or d).lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


theme = {}
if os.path.exists(os.path.join(W, "theme.json")):
    theme = json.load(open(os.path.join(W, "theme.json"), encoding="utf-8"))
ACC = theme.get("acc") or theme.get("accent") or "#ffd24a"

# ─────────────── تحقق من fx.json ───────────────
errs = []
for i, ev in enumerate(EVENTS):
    ev.setdefault("id", f"{ev.get('type', '?')}{i + 1}")
    k = ev.get("type")
    if k not in KNOWN:
        errs.append(f"{ev['id']}: نوع غير معروف «{k}» — المتاح: {', '.join(sorted(KNOWN))}")
        continue
    if k in INSTANT:
        if "t" not in ev:
            errs.append(f"{ev['id']}: ناقص t")
        ev.setdefault("dur", {"flash": 0.35, "shake": 0.45, "punch": 0.4, "glitch": 0.3}[k])
        ev["s"], ev["e"] = ev["t"], ev["t"] + ev["dur"]
    elif "s" not in ev or "e" not in ev or ev["e"] <= ev["s"]:
        errs.append(f"{ev['id']}: لازم s و e (e أكبر)")
    if k == "teleport":
        bg = os.path.join(W, ev.get("bg", ""))
        if not ev.get("bg") or not os.path.exists(bg):
            errs.append(f"{ev['id']}: الخلفية مو موجودة «{ev.get('bg')}»")
    if k == "ai":
        ev.setdefault("file", f"fx_ai/{ev['id']}.mp4")
        if not CHECK and not os.path.exists(os.path.join(W, ev["file"])):
            errs.append(f"{ev['id']}: مقطع التوليد ناقص ({ev['file']}) — شغّل 28_fx_ai.py أول")
if errs:
    print("❌ fx.json:\n  " + "\n  ".join(errs))
    sys.exit(3)
ais = [e for e in EVENTS if e["type"] == "ai"]
for a in ais:
    for b in EVENTS:
        if b is not a and b["type"] not in INSTANT and b["s"] < a["e"] and a["s"] < b["e"]:
            print(f"⚠️ {b['id']} فوق مقطع التوليد {a['id']} — اليد والقص ينحسبون من الأصل، فممكن ما يطابقون")


def active(ev, t, pad=0.0):
    return ev["s"] - pad <= t < ev["e"] + pad


# ─────────────── اللقط: اليد وقص الشخص ───────────────
hand_evs = [e for e in EVENTS if e["type"] in HAND_KINDS]
tp_evs = [e for e in EVENTS if e["type"] == "teleport"]
HANDS = SEG = None
if hand_evs:
    HANDS = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=L.model("hand")), running_mode=vision.RunningMode.VIDEO,
        num_hands=2, min_hand_detection_confidence=0.4, min_hand_presence_confidence=0.4,
        min_tracking_confidence=0.4))
if tp_evs:
    SEG = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=BaseOptions(model_asset_path=L.model("person")), running_mode=vision.RunningMode.VIDEO,
        output_confidence_masks=True))


def detect_hands(small, ms):
    r = HANDS.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=small), ms)
    out = []
    for lm in r.hand_landmarks:
        p = np.array([[q.x * VW, q.y * VH] for q in lm], np.float32)
        out.append(p)
    return out


def person_mask(small, ms):
    r = SEG.segment_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=small), ms)
    m = r.confidence_masks[0].numpy_view()                       # الفئة ٠ = الخلفية
    return 1.0 - np.squeeze(m).astype(np.float32)


def guided(I, p, r=8, eps=1e-3):
    """فلتر موجَّه: يلصق حافة القناع على حواف الصورة الحقيقية (الشعر والأصابع) بدل حافة النموذج المغبّشة."""
    bf = lambda x: cv2.boxFilter(x, -1, (r, r))
    mI, mp_ = bf(I), bf(p)
    a = (bf(I * p) - mI * mp_) / (bf(I * I) - mI * mI + eps)
    b = mp_ - a * mI
    return bf(a) * I + bf(b)


# ─────────────── تتبّع يد لكل مؤثر (تنعيم + تحمّل الضياع) ───────────────
class HandTrack:
    def __init__(self, side, point):
        self.side, self.point = side, point
        self.slots = {}                    # اسم الخانة → [x, y, hs, lost, vis]

    def pick(self, hands):
        """يرجّع {خانة: (x, y, حجم اليد)}"""
        cand = []
        for p in hands:
            palm = p[[0, 5, 9, 13, 17]].mean(0)
            hs = float(np.linalg.norm(p[9] - p[0])) * 1.1
            a = p[8] if self.point == "tip" else palm + (p[9] - p[0]) * 0.15
            cand.append((float(a[0]), float(a[1]), max(hs, 30.0)))
        cand.sort(key=lambda c: c[0])
        if self.side == "both":
            if len(cand) == 2:
                return {"L": cand[0], "R": cand[1]}
            if len(cand) == 1:           # يد وحدة: نربطها بأقرب خانة سابقة
                c = cand[0]
                if self.slots:
                    k = min(self.slots, key=lambda k: abs(self.slots[k][0] - c[0]))
                else:
                    k = "L" if c[0] < VW / 2 else "R"
                return {k: c}
            return {}
        if not cand:
            return {}
        if self.side == "screenLeft":
            return {"A": cand[0]}
        if self.side == "screenRight":
            return {"A": cand[-1]}
        if "A" in self.slots and len(cand) > 1:           # any: نكمّل مع نفس اليد
            s = self.slots["A"]
            return {"A": min(cand, key=lambda c: math.hypot(c[0] - s[0], c[1] - s[1]))}
        return {"A": max(cand, key=lambda c: c[2])}

    def update(self, hands):
        got = self.pick(hands) if hands is not None else {}
        for k, (x, y, hs) in got.items():
            s = self.slots.get(k)
            if s is None or s[3] > 12:
                self.slots[k] = [x, y, hs, 0, s[4] if s else 0.0]
            else:
                a = 0.55
                s[0] += (x - s[0]) * a; s[1] += (y - s[1]) * a; s[2] += (hs - s[2]) * 0.2; s[3] = 0
        for k, s in self.slots.items():
            if k not in got:
                s[3] += 1
            vis_target = 1.0 if s[3] <= 6 else 0.0          # يمسك آخر مكان ٦ فريمات ثم يخفت
            s[4] += (vis_target - s[4]) * 0.25
        return {k: (s[0], s[1], s[2], s[4]) for k, s in self.slots.items() if s[4] > 0.02}


# ─────────────── رسم الجزيئات ───────────────
YY, XX = np.mgrid[0:HH, 0:HW].astype(np.float32)


def _noise(seed):
    """نسيج ضجيج كسري (ألسنة لهب وخيوط دخان) — يتولّد مرة ويتحرّك بالإزاحة."""
    r = np.random.default_rng(seed)
    n = np.zeros((HH, HW), np.float32)
    for k, amp in ((8, .5), (16, .25), (32, .15), (64, .1)):
        g = r.random((HH // k + 2, HW // k + 2)).astype(np.float32)
        n += cv2.resize(g, (HW + 2 * k, HH + 2 * k), interpolation=cv2.INTER_CUBIC)[k:k + HH, k:k + HW] * amp
    return np.clip((n - n.min()) / (n.max() - n.min() + 1e-6), 0, 1)


NOISE = _noise(7)


def flow(t, speed, sx=0.0):
    """الضجيج يطلع لفوق مع الوقت"""
    return np.roll(NOISE, (-int(t * speed) % HH, int(t * sx) % HW), (0, 1))


def splat(layer, xs, ys, cols, sig, stretch=1.0):
    """يرشّ جزيئات (نقاط ملوّنة بشدّتها، إحداثيات كاملة الدقة) ثم يغبّشها بسيقما (بكسلات الطبقة).
    تجمّع إضافي، فالقلب يطلع أسطع. stretch>1 يمطّها عمودياً (ألسنة لهب)."""
    if len(xs) == 0:
        return
    sig = max(0.6, float(sig))
    buf = np.zeros_like(layer)
    xi = np.clip((xs * 0.5).astype(np.int32), 0, HW - 1)
    yi = np.clip((ys * 0.5).astype(np.int32), 0, HH - 1)
    for c in range(layer.shape[2]):
        np.add.at(buf[:, :, c], (yi, xi), cols[:, c] * (2 * math.pi * sig * sig * stretch))
    layer += cv2.GaussianBlur(buf, (0, 0), sigmaX=sig, sigmaY=sig * stretch)


def radial(layer, x, y, r, col, k):
    x0, x1 = int(max(0, x * .5 - 3 * r)), int(min(HW, x * .5 + 3 * r))
    y0, y1 = int(max(0, y * .5 - 3 * r)), int(min(HH, y * .5 + 3 * r))
    if x1 <= x0 or y1 <= y0:
        return
    d2 = (XX[y0:y1, x0:x1] - x * .5) ** 2 + (YY[y0:y1, x0:x1] - y * .5) ** 2
    layer[y0:y1, x0:x1] += np.exp(-d2 / (r * r))[..., None] * col * k


class Particles:
    def __init__(self):
        self.a = np.zeros((0, 8), np.float32)        # x y vx vy age life size seed

    def emit(self, arr):
        if len(arr):
            self.a = np.vstack([self.a, np.asarray(arr, np.float32)])

    def step(self):
        a = self.a
        a[:, 0] += a[:, 2] * DT; a[:, 1] += a[:, 3] * DT; a[:, 4] += DT
        self.a = a[a[:, 4] < a[:, 5]]


FIRE_RAMP = np.array([[1.0, 0.85, 0.45], [1.0, 0.55, 0.12], [0.95, 0.26, 0.04], [0.35, 0.05, 0.02]], np.float32)


def ramp(u, R):
    u = np.clip(u, 0, 0.999) * (len(R) - 1)
    i = u.astype(int); f = (u - i)[:, None]
    return R[i] * (1 - f) + R[np.minimum(i + 1, len(R) - 1)] * f


class HandFX:
    """مؤثر واحد مربوط باليد: يولّد جزيئات حول مكانها ويرسم طبقة ضوء (add) وطبقة دخان (alpha)."""

    def __init__(self, ev):
        self.ev, self.k = ev, ev["type"]
        self.track = HandTrack(ev.get("side", "any"), ev.get("point", "palm"))
        self.size = float(ev.get("size", 1.0))
        self.col = hexrgb(ev.get("color"), {"fire": "#ff7a1a", "lightning": "#8fc4ff", "smoke": "#8a8a8a",
                                            "sparkle": ACC, "energy": "#4fd8ff"}[self.k])
        self.ps = {}
        self.rng = np.random.default_rng(zlib.crc32(ev["id"].encode()))
        self.bolts, self.t = {}, 0.0
        self.hands_seen = self.frames = 0

    def env(self, t):
        s, e = self.ev["s"], self.ev["e"]
        return float(np.clip((t - s) / 0.25, 0, 1) * np.clip((e - t) / 0.35, 0, 1))

    def frame(self, t, hands, add, alpha):
        self.t = t
        live = active(self.ev, t)
        if live:
            self.frames += 1
            self.hands_seen += bool(hands)
        anchors = self.track.update(hands) if live else {}
        env = self.env(t) if live else 0.0
        for k, (x, y, hs, vis) in anchors.items():
            getattr(self, "emit_" + self.k)(self.ps.setdefault(k, Particles()), x, y, hs * self.size, env * vis)
        for k, p in self.ps.items():
            p.step()
            a = anchors.get(k)
            getattr(self, "draw_" + self.k)(p, a, env * (a[3] if a else 0), add, alpha)

    # ── نار ──
    def emit_fire(self, P, x, y, hs, g):
        n = self.rng.poisson(34 * g)
        r = self.rng
        P.emit(np.stack([x + r.normal(0, .2 * hs, n), y + r.normal(0, .06 * hs, n) - .1 * hs,
                         r.normal(0, .2 * hs, n), -r.uniform(1.6, 2.8, n) * hs, np.zeros(n),
                         r.uniform(.4, .85, n), r.uniform(.10, .20, n) * hs, r.uniform(0, 6.28, n)], 1))
        P.ax, P.hs = x, hs

    def draw_fire(self, P, a, g, add, alpha):
        A = P.a
        if len(A) == 0:
            return
        hs = P.hs
        A[:, 3] -= 0.9 * hs * DT                                         # يتسارع لفوق
        A[:, 2] += (np.sin(A[:, 4] * 11 + A[:, 7]) * 1.1 * hs + (P.ax - A[:, 0]) * 1.8) * DT  # يتموّج ويتدبّب
        u = A[:, 4] / A[:, 5]
        col = ramp(u, FIRE_RAMP) * ((1 - u) ** 1.2)[:, None] * 0.10
        size = A[:, 6] * (1 - 0.6 * u)
        f = np.zeros_like(add)
        for lo, hi in ((0, .07), (.07, .12), (.12, 9)):
            m = (size >= lo * hs) & (size < hi * hs)
            if m.any():
                splat(f, A[m, 0], A[m, 1], col[m], float(np.mean(size[m])) * .25, stretch=2.2)
        f *= (0.35 + 1.3 * flow(self.t, hs * 1.2))[..., None]           # ألسنة: الضجيج يطلع مع اللهب
        add += f
        if a:
            fl = 0.85 + 0.15 * math.sin(self.t * 23) * math.sin(self.t * 7.3)
            radial(add, a[0], a[1] - .3 * hs, .75 * hs, np.array([1, .45, .12], np.float32), .10 * g * fl)

    # ── برق ──
    def emit_lightning(self, P, x, y, hs, g):
        P.ax, P.ay, P.hs, P.g = x, y, hs, g

    def bolt(self, x0, y0, x1, y1, depth, pts):
        if depth == 0:
            pts.append((x1, y1)); return
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        L2 = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / (L2 + 1e-6), (x1 - x0) / (L2 + 1e-6)
        off = self.rng.normal(0, L2 * 0.18)
        mx, my = mx + nx * off, my + ny * off
        self.bolt(x0, y0, mx, my, depth - 1, pts)
        self.bolt(mx, my, x1, y1, depth - 1, pts)

    def draw_lightning(self, P, a, g, add, alpha):
        if not hasattr(P, "ax") or g <= 0.01:
            return
        key = id(P)
        fi = int(round(self.t * FPS))
        if key not in self.bolts or fi % 2 == 0:                       # يتبدّل كل فريمين — يطقطق
            segs = []
            for _ in range(self.rng.integers(2, 5)):
                ang = self.rng.uniform(0, 2 * math.pi)
                ln = self.rng.uniform(1.2, 3.2) * P.hs
                pts = [(P.ax, P.ay)]
                self.bolt(P.ax, P.ay, P.ax + math.cos(ang) * ln, P.ay + math.sin(ang) * ln, 5, pts)
                segs.append(pts)
                if self.rng.random() < .5:                              # فرع
                    j = len(pts) // 2
                    bx, by = pts[j]; a2 = ang + self.rng.normal(0, .7)
                    br = [(bx, by)]
                    self.bolt(bx, by, bx + math.cos(a2) * ln * .5, by + math.sin(a2) * ln * .5, 4, br)
                    segs.append(br)
            self.bolts[key] = segs
        core = np.zeros((HH, HW), np.float32)
        for pts in self.bolts[key]:
            q = (np.array(pts) * 0.5).astype(np.int32)
            cv2.polylines(core, [q], False, 1.0, max(1, int(P.hs * .012)), cv2.LINE_AA)
        fl = g * (0.7 + 0.3 * self.rng.random())
        glow = cv2.GaussianBlur(core, (0, 0), P.hs * .03) * 3 + cv2.GaussianBlur(core, (0, 0), P.hs * .1) * 6
        add += core[..., None] * np.array([1, 1, 1], np.float32) * fl * 1.5
        add += glow[..., None] * self.col * fl
        radial(add, P.ax, P.ay, P.hs * 1.1, self.col, .3 * fl)

    # ── دخان ──
    def emit_smoke(self, P, x, y, hs, g):
        n = self.rng.poisson(3 * g)
        r = self.rng
        P.emit(np.stack([x + r.normal(0, .15 * hs, n), y + r.normal(0, .1 * hs, n) - .3 * hs, r.normal(0, .15 * hs, n),
                         -r.uniform(.4, .9, n) * hs, np.zeros(n), r.uniform(1.2, 2.2, n),
                         r.uniform(.2, .35, n) * hs, r.uniform(0, 6.28, n)], 1))
        P.hs = hs

    def draw_smoke(self, P, a, g, add, alpha):
        A = P.a
        if len(A) == 0:
            return
        A[:, 2] += np.sin(A[:, 4] * 2 + A[:, 7]) * .3 * P.hs * DT
        u = A[:, 4] / A[:, 5]
        k = (np.sin(np.pi * np.clip(u * 1.3, 0, 1)) * .012)[:, None].repeat(3, 1)
        size = A[:, 6] * (1 + 2.5 * u)
        sm = np.zeros_like(alpha)
        for lo, hi in ((0, .5), (.5, 9)):
            m = (size >= lo * P.hs) & (size < hi * P.hs)
            if m.any():
                splat(sm, A[m, 0], A[m, 1], k[m], float(np.mean(size[m])) * .45)
        tex = flow(self.t, P.hs * .25, P.hs * .05)
        alpha += sm * cv2.GaussianBlur(2.4 * tex ** 3, (0, 0), 4)[..., None]  # خيوط ناعمة، مو قرص

    # ── لمعة / سحر ──
    def emit_sparkle(self, P, x, y, hs, g):
        n = self.rng.poisson(7 * g)
        r = self.rng
        ang = r.uniform(0, 6.28, n); rad = r.uniform(.2, 1.1, n) * hs
        P.emit(np.stack([x + np.cos(ang) * rad, y + np.sin(ang) * rad, r.normal(0, .2 * hs, n),
                         -r.uniform(.2, .7, n) * hs, np.zeros(n), r.uniform(.5, 1.1, n),
                         r.uniform(.02, .05, n) * hs, r.uniform(0, 6.28, n)], 1))
        P.hs = hs

    def draw_sparkle(self, P, a, g, add, alpha):
        A = P.a
        if len(A) == 0:
            return
        u = A[:, 4] / A[:, 5]
        tw = (0.55 + 0.45 * np.sin(A[:, 4] * 18 + A[:, 7])) * np.sin(np.pi * u)
        white = np.clip(self.col * .4 + .6, 0, 1)
        splat(add, A[:, 0], A[:, 1], white[None] * tw[:, None] * 1.2, max(.8, P.hs * .012))
        splat(add, A[:, 0], A[:, 1], self.col[None] * tw[:, None] * .5, P.hs * .05)
        big = tw > .85                                                  # نجمة بأربع أشعة للمعات القوية
        for x, y, s in zip(A[big, 0] * .5, A[big, 1] * .5, A[big, 6] * 1.4):
            cv2.line(add, (int(x - s), int(y)), (int(x + s), int(y)), (1, 1, 1), 1, cv2.LINE_AA)
            cv2.line(add, (int(x), int(y - s)), (int(x), int(y + s)), (1, 1, 1), 1, cv2.LINE_AA)
        if a:
            radial(add, a[0], a[1], P.hs * .8, self.col, .12 * g)

    # ── كرة طاقة ──
    def emit_energy(self, P, x, y, hs, g):
        cy = y - .45 * hs
        self.emit_sparkle(P, x, cy, hs * .9, g * .8)
        P.cx, P.cy, P.hs, P.g = x, cy, hs, g

    def draw_energy(self, P, a, g, add, alpha):
        self.draw_sparkle(P, None, 0, add, alpha)
        if not hasattr(P, "cx") or g <= .01:
            return
        R = P.hs * .5 * .55 * (1 + .06 * math.sin(self.t * 9)) * (.4 + .6 * g)
        x, y = P.cx * .5, P.cy * .5
        x0, x1, y0, y1 = int(max(0, x - 3 * R)), int(min(HW, x + 3 * R)), int(max(0, y - 3 * R)), int(min(HH, y + 3 * R))
        if x1 <= x0 or y1 <= y0:
            return
        dx, dy = XX[y0:y1, x0:x1] - x, YY[y0:y1, x0:x1] - y
        d = np.sqrt(dx * dx + dy * dy) / R
        ang = np.arctan2(dy, dx)
        swirl = .5 + .5 * np.sin(ang * 5 + self.t * 12 + d * 6)
        core = np.exp(-(d / .55) ** 2)
        rim = np.exp(-((d - 1) / .18) ** 2) * (.5 + .7 * swirl)
        halo = np.exp(-(d / 2.2) ** 2) * .35
        roi = add[y0:y1, x0:x1]
        roi += (core * 1.3)[..., None] * np.array([1, 1, 1], np.float32) * g
        roi += (rim + halo)[..., None] * self.col * g


# ─────────────── مؤثرات الإطار (اللحظية) ───────────────
def cam_fx(img, t):
    """img float32 0..1 كامل الدقة"""
    for ev in EVENTS:
        if ev["type"] not in INSTANT or not active(ev, t):
            continue
        u = (t - ev["t"]) / ev["dur"]
        rng = np.random.default_rng(zlib.crc32(f"{ev['id']}{int(t * FPS)}".encode()))
        if ev["type"] == "flash":
            k = float(ev.get("strength", .85)) * (1 - u) ** 2
            img = img * (1 - k) + hexrgb(ev.get("color"), "#ffffff") * k
        elif ev["type"] in ("shake", "punch"):
            if ev["type"] == "shake":
                amp = float(ev.get("amp", 28)) * (1 - u) ** 1.5
                dx, dy = rng.normal(0, amp, 2)
                s = 1.0 + amp / VW * 2.4
            else:
                z = float(ev.get("zoom", 1.12))
                s = 1 + (z - 1) * (min(1, u / .18) if u < .18 else (1 - (u - .18) / .82) ** 2)
                dx = dy = 0.0
            M = cv2.getRotationMatrix2D((VW / 2, VH * .45), float(rng.normal(0, .4)) if ev["type"] == "shake" else 0, s)
            M[:, 2] += (dx, dy)
            img = cv2.warpAffine(img, M, (VW, VH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        elif ev["type"] == "glitch":
            img = glitch(img, float(ev.get("amp", 1.0)) * (1 - u * .6), rng)
    return img


def glitch(img, k, rng):
    sh = int(18 * k)
    out = img.copy()
    out[:, :, 0] = np.roll(img[:, :, 0], sh, 1)
    out[:, :, 2] = np.roll(img[:, :, 2], -sh, 1)
    for _ in range(int(6 * k)):
        y = int(rng.integers(0, VH - 40)); h = int(rng.integers(10, 90))
        out[y:y + h] = np.roll(out[y:y + h], int(rng.normal(0, 60 * k)), 1)
    return out


# ─────────────── النقل لمكان ثاني ───────────────
class Teleport:
    def __init__(self, ev):
        self.ev = ev
        self.src = os.path.join(W, ev["bg"])
        self.cap = None
        ext = os.path.splitext(self.src)[1].lower()
        if ext in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
            self.cap = cv2.VideoCapture(self.src)
        else:
            im = cv2.imread(self.src, cv2.IMREAD_COLOR)
            self.still = L.cover(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), VW, VH).astype(np.float32) / 255
        self.mask = None
        self.tr = ev.get("transition", "flash")
        self.td = float(ev.get("tdur", .35))
        self.cover_sum = self.frames = 0

    def bg(self):
        if self.cap is None:
            return self.still
        ok, f = self.cap.read()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, f = self.cap.read()
        return L.cover(cv2.cvtColor(f, cv2.COLOR_BGR2RGB), VW, VH).astype(np.float32) / 255

    def feed_mask(self, m, small):
        m = cv2.resize(m, (HW, HH), interpolation=cv2.INTER_LINEAR)
        g = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
        m = np.clip(guided(g, m, 10, 2e-3), 0, 1)
        # سدّ الثقوب: أي بقعة «خلفية» محاطة بالشخص من كل جهة (كم لبس فاتح، انعكاس) ترجع شخص
        ff = np.pad((m > .5).astype(np.uint8), 1)          # إطار خلفية حوالين الكادر: كل خلفية تلمس الحافة تنوصل
        cv2.floodFill(ff, np.zeros((HH + 4, HW + 4), np.uint8), (0, 0), 1)
        holes = cv2.dilate((ff[1:-1, 1:-1] == 0).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        if holes.any():
            m[holes] = 1.0
            m = cv2.GaussianBlur(m, (0, 0), 1.2)
        self.mask = m if self.mask is None else self.mask * .3 + m * .7        # تنعيم زمني — ما يرجف
        self.cover_sum += float(m.mean()); self.frames += 1

    def apply(self, img, t, rng):
        if self.mask is None:
            return img
        m = cv2.resize(self.mask, (VW, VH), interpolation=cv2.INTER_LINEAR)
        m = np.clip((m - .3) / .4, 0, 1)
        m = (m * m * (3 - 2 * m))[..., None]                                   # حافة ناعمة
        comp = img * m + self.bg() * (1 - m)
        s, e, td = self.ev["s"], self.ev["e"], self.td
        # الانتقال عند الدخول والخروج
        edge = min(t - s, e - t)
        if edge >= td or self.tr == "cut":
            return comp
        u = max(0.0, edge) / td                                                 # 0 عند الحد → 1 داخل
        if self.tr == "dissolve":
            return img * (1 - u) + comp * u
        if self.tr == "glitch":
            base = comp if rng.random() < .5 + u * .5 else img
            return glitch(base, 1 - u, rng)
        k = (1 - u) ** 2 * .9                                                   # flash
        return comp * (1 - k) + k


# ─────────────── التشغيل ───────────────
def main():
    fxs = [HandFX(e) for e in hand_evs]
    tps = [Teleport(e) for e in tp_evs]
    ai_caps = {}
    for a in ais:
        p = os.path.join(W, a["file"])
        if os.path.exists(p):
            c = cv2.VideoCapture(p)
            fr = []
            while True:
                ok, f = c.read()
                if not ok:
                    break
                fr.append(L.cover(cv2.cvtColor(f, cv2.COLOR_BGR2RGB), VW, VH))
            ai_caps[a["id"]] = fr
            print(f"  توليد {a['id']}: {len(fr)} فريم")

    if CHECK or PREVIEW:
        writer = None
    else:
        tmp = os.path.join(W, ".cutz_fx.tmp.mp4")
        writer = L.Writer(tmp, VW, VH, FPS, audio_from=SRC)
    if PREVIEW:
        os.makedirs(os.path.join(W, "fx_preview"), exist_ok=True)
    want = [round(t * FPS) for t in PREVIEW]
    last = max(want) if want else NF + 10
    any_live = lambda t, pad=0: any(active(e, t, pad) for e in EVENTS)

    for i, fr in enumerate(L.frames(SRC, VW, VH)):
        if i > last:
            break
        t = i / FPS
        ms = int(t * 1000)
        if not any_live(t, 0.6):                                                # خارج كل المؤثرات — يمر كما هو
            if writer:
                writer.write(fr)
            if i in want:
                cv2.imwrite(os.path.join(W, "fx_preview", f"{t:07.2f}.jpg"), cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
            if i % 150 == 0:
                print(f"\r  {t:6.1f}/{NF / FPS:.1f}ث", end="", flush=True)
            continue
        small = None
        hands = None
        if HANDS and any(active(e, t, .3) for e in hand_evs):
            small = cv2.resize(fr, (HW, HH), interpolation=cv2.INTER_AREA)
            hands = detect_hands(small, ms)
        for tp in tps:
            if active(tp.ev, t, .1):
                small = small if small is not None else cv2.resize(fr, (HW, HH), interpolation=cv2.INTER_AREA)
                tp.feed_mask(person_mask(small, ms), small)
        if CHECK:
            for f in fxs:
                if active(f.ev, t):
                    f.frames += 1; f.hands_seen += bool(hands)
            continue

        img = fr.astype(np.float32) / 255
        rng = np.random.default_rng(i)
        for a in ais:                                                           # ١) التوليد يبدّل الفريم
            if active(a, t) and ai_caps.get(a["id"]):
                seq = ai_caps[a["id"]]
                u = (t - a["s"]) / (a["e"] - a["s"])
                g = seq[min(len(seq) - 1, int(u * len(seq)))].astype(np.float32) / 255
                xf = min(1.0, (t - a["s"]) / .12, (a["e"] - t) / .12)
                img = img * (1 - xf) + g * xf
        for tp in tps:                                                          # ٢) المكان
            if active(tp.ev, t):
                img = tp.apply(img, t, rng)
        if fxs:                                                                 # ٣) مؤثرات اليد
            add = np.zeros((HH, HW, 3), np.float32)
            alpha = np.zeros((HH, HW, 3), np.float32)
            for f in fxs:
                f.frame(t, hands, add, alpha)
            if add.any():
                lay = 1 - np.exp(-add * 1.6)                                    # تشبّع ناعم: القلب يبيضّ
                lay += cv2.GaussianBlur(lay, (0, 0), 18) * .45                  # توهّج
                lay = cv2.resize(np.clip(lay, 0, 1), (VW, VH), interpolation=cv2.INTER_LINEAR)
                img = 1 - (1 - img) * (1 - lay)                                 # دمج «شاشة» — ما يحرق الألوان
            if alpha.any():
                a1 = cv2.resize(np.clip(alpha[..., 0] * 4, 0, .6), (VW, VH))[..., None]
                img = img * (1 - a1) + .78 * a1
        img = cam_fx(img, t)                                                    # ٤) وميض · هزّة · زوم · خربطة
        out = (np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)
        if writer:
            writer.write(out)
        if i in want:
            cv2.imwrite(os.path.join(W, "fx_preview", f"{t:07.2f}.jpg"), cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
        if i % 30 == 0:
            print(f"\r  {t:6.1f}/{NF / FPS:.1f}ث  (مؤثرات)", end="", flush=True)
    print()

    bad = 0
    for f in fxs:
        pct = 100 * f.hands_seen / max(1, f.frames)
        ok = pct >= 70
        bad += not ok
        print(f"  {'✅' if ok else '⚠️'} {f.ev['id']} ({f.k}): اليد انلقطت {pct:.0f}٪ من {f.frames} فريم"
              + ("" if ok else " — يده برّا الكادر أو مغطّاة؟ قصّر النافذة أو غيّر side"))
    for tp in tps:
        cov = 100 * tp.cover_sum / max(1, tp.frames)
        ok = 5 <= cov <= 90
        bad += not ok
        print(f"  {'✅' if ok else '⚠️'} {tp.ev['id']} (نقل): الشخص يغطي {cov:.0f}٪ من الكادر"
              + ("" if ok else " — القص مو واثق، شوف المعاينة"))

    if writer:
        if writer.close():
            sys.exit("❌ الترميز فشل")
        os.replace(tmp, os.path.join(W, "cutz.mp4"))
        L.mark_rendered(W)
        print(f"✅ cutz.mp4 فيه المؤثرات ({len(EVENTS)}) — الأصل محفوظ بـcutz_nofx.mp4")
        print("   الخطوة الجاية: 04b_remotion.sh <work> sync (أو studio) عشان ياخذ النسخة الجديدة")
    elif PREVIEW:
        print(f"✅ المعاينة: {os.path.join(W, 'fx_preview')}")
    sys.exit(3 if (bad and CHECK) else 0)


main()
