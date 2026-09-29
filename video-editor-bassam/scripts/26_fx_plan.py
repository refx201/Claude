# -*- coding: utf-8 -*-
"""وضع المؤثرات — الخطوة الأولى: وين طلب شي؟ ووين صقّف؟   python3 26_fx_plan.py <workdir>

يقرأ caps.json (كلامه بتوقيت كل كلمة على التايم-لاين المقصوص) وvoice.wav (أو cutz.mp4).
يطبع:
  ١) كل جملة بتوقيتها، والجمل اللي فيها أمر («حطلي نار»، «حوّلني»، «ودّيني»…) معلّمة بـ◀
  ٢) التصقيفات المكتشفة من الصوت: توقيتها ودرجة الثقة
ويكتب <work>/fx_detect.json — منه تكتب fx.json (references/fx.md) وتعرضه عليه قبل الرندر.
الاكتشاف اقتراح مو حكم: الأوامر يفهمها كلود من الكلام، والتصقيفة الضعيفة تتأكد منها بسماعها.
"""
import os, sys, json, re, subprocess
import numpy as np

W = os.path.abspath(sys.argv[1])
SR = 48000

# ─────────────── ١) الأوامر من الكلام ───────────────
def norm(s):
    s = re.sub(r"[ً-ْـ]", "", s)            # تشكيل وكشيدة
    s = re.sub("[إأآ]", "ا", s).replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"[^\w]", "", s)

# جذور أفعال الطلب وأسماء المؤثرات — بداية الكلمة (بعد شيل «و» و«ف» العاطفة)
TRIG = ["حط", "خلي", "حول", "انقل", "نقل", "ودي", "وصل", "خذ", "سوي", "اعمل", "عمل", "طلع", "ولع", "شعل",
        "صقف", "اصقف", "سقف", "طقطق", "فرقع", "كبر", "صغر", "طير", "اختف", "ظهر", "بدل", "غير", "لبس", "رجع",
        "نار", "برق", "كهرب", "دخان", "ثلج", "جليد", "عضل", "قوي", "سحر", "ضو", "نور", "طاق", "شرار", "نجوم"]
TRIG = [norm(x) for x in TRIG]
WHEN = {norm(x) for x in ["لما", "لمن", "اذا", "لو", "وقت", "بس", "كل ما"]}

def is_trig(w):
    n = norm(w)
    for pre in ("", "و", "ف"):
        if pre and not n.startswith(pre):
            continue
        m = n[len(pre):]
        if len(m) >= 2 and any(m.startswith(t) for t in TRIG):
            return True
    return False

caps = json.load(open(os.path.join(W, "caps.json"), encoding="utf-8"))
cmds = []
print("━━ كلامه (◀ = فيها طلب محتمل) ━━")
for c in caps["cards"]:
    hit = [w for w in c["w"] if is_trig(w["t"]) or norm(w["t"]) in WHEN]
    real = [w for w in hit if is_trig(w["t"])]
    mark = "◀" if real else " "
    txt = " ".join(w["t"] for w in c["w"])
    print(f"{mark} {c['s']:6.2f}–{c['e']:6.2f}  {txt}")
    if real:
        cmds.append({"s": c["s"], "e": c["e"], "text": txt,
                     "words": [{"t": w["t"], "s": w["s"], "e": w["e"]} for w in real]})

# ─────────────── ٢) التصقيف من الصوت ───────────────
src = os.path.join(W, "voice.wav")
if not os.path.exists(src):
    src = os.path.join(W, "cutz.mp4")
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                     capture_output=True).stdout
x = np.frombuffer(raw, np.float32).astype(np.float64)
claps = []
if len(x) > SR:
    HOP, WIN = 256, 1024
    hp = np.diff(x, prepend=0.0)                       # تمرير-عالي بسيط: التصقيفة حادّة والصوت البشري أنعم
    n = (len(x) - WIN) // HOP
    idx = np.arange(n)[:, None] * HOP + np.arange(WIN)[None, :]
    fr = hp[idx] * np.hanning(WIN)
    E = 10 * np.log10(np.mean(fr ** 2, axis=1) + 1e-12)
    spec = np.abs(np.fft.rfft(fr, axis=1))
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    cent = (spec * freqs).sum(1) / (spec.sum(1) + 1e-12)
    loud = np.percentile(E, 97)
    fps = SR / HOP
    b0, b1 = int(0.40 * fps), int(0.03 * fps)
    d0, d1 = int(0.06 * fps), int(0.14 * fps)
    for i in range(b0, n - d1):
        bg = np.median(E[i - b0:i - b1])
        rise = E[i] - bg
        jump = E[i] - E[i - 2]
        if rise < 14 or jump < 8 or E[i] < loud - 10:
            continue
        if E[i] < E[max(0, i - 3):i + 4].max():          # قمّة محلية بس
            continue
        decay = E[i] - E[i + d0:i + d1].max()            # التصقيفة تخمد خلال ~٦٠–١٤٠ ملّي، والحرف المتحرك يطوّل
        if decay < 9 or cent[i] < 1500:
            continue
        score = min(1.0, (rise - 14) / 16 * 0.4 + (decay - 9) / 12 * 0.35 + (cent[i] - 1500) / 3000 * 0.25)
        t = i * HOP / SR + WIN / 2 / SR
        if claps and t - claps[-1]["t"] < 0.15:
            if score > claps[-1]["score"]:
                claps[-1] = {"t": round(t, 3), "score": round(score, 2)}
            continue
        claps.append({"t": round(t, 3), "score": round(score, 2)})

print("\n━━ التصقيفات من الصوت ━━")
if not claps:
    print("  ما لقيت تصقيفة واضحة")
for c in claps:
    lvl = "واضحة" if c["score"] >= 0.5 else "محتملة — اسمعها قبل ما تعتمدها"
    print(f"  👏 {c['t']:6.2f}  ثقة {c['score']:.2f}  ({lvl})")

json.dump({"total": caps["total"], "commands": cmds, "claps": claps},
          open(os.path.join(W, "fx_detect.json"), "w"), ensure_ascii=False, indent=1)
print(f"\n✅ fx_detect.json — {len(cmds)} جملة فيها طلب · {len(claps)} تصقيفة")
