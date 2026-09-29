# -*- coding: utf-8 -*-
"""وضع المؤثرات — المقاطع اللي تحتاج نموذج ذكاء اصطناعي للفيديو («حوّلني عضلات»، «غيّر لبسي»…).
    python3 28_fx_ai.py <workdir> [--only <id>] [--force]

لكل مؤثر نوعه "ai" بـfx.json:
  ١) يقصّ المقطع من cutz_nofx.mp4 (s → e) لـfx_ai/<id>_in.mp4، ويكتب الطلب لـfx_ai/<id>_prompt.txt
  ٢) لو فيه مفتاح خدمة (تحت) → يرسله للنموذج، ينتظر، وينزّل النتيجة لـfx_ai/<id>.mp4
     لو ما فيه → يطبع للمستخدم وش يسوي بيده: يرفع <id>_in.mp4 مع الطلب لأي أداة توليد فيديو عنده،
     ويحط الناتج باسم fx_ai/<id>.mp4 — وبعدها 27_fx_render.py يركّبه مكانه.
  النتيجة تنمطّ على نفس مدة النافذة، فلو النموذج رجّع طول غير — ما يخرب التوقيت.

الإعداد (مرة وحدة، بمجلد بياناته):
  المفتاح : متغيّر البيئة FAL_KEY ، أو <بياناته>/keys.json ← {"fal": "..."}   ⛔ لا تكتبه بأي ملف داخل المشروع
  النموذج : profile.json ← "fx": {"aiModel": "<معرّف نموذج فيديو-إلى-فيديو>",
                                  "aiVideoKey": "video_url", "aiPromptKey": "prompt", "aiParams": {…}}
  المعرّف والمفاتيح من صفحة النموذج بالخدمة — يختلفون من نموذج لنموذج، فلا تخمّنهم.
"""
import os, sys, json, time, base64, subprocess, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fxlib as L
import _paths

W = os.path.abspath(sys.argv[1])
ARGS = sys.argv[2:]
ONLY = ARGS[ARGS.index("--only") + 1] if "--only" in ARGS else None
FORCE = "--force" in ARGS

FX = L.load_fx(W)
evs = [e for e in FX.get("events", []) if e.get("type") == "ai" and (not ONLY or e.get("id") == ONLY)]
if not evs:
    sys.exit("ما فيه مؤثرات ai بـfx.json")
SRC = L.base_video(W)
OUT = os.path.join(W, "fx_ai")
os.makedirs(OUT, exist_ok=True)

prof = _paths.load("profile.json", {})
cfg = prof.get("fx", {}) if isinstance(prof, dict) else {}
keys = _paths.load("keys.json", {})
KEY = os.environ.get("FAL_KEY") or keys.get("fal")
MODEL = os.environ.get("VEB_AI_MODEL") or cfg.get("aiModel")

KEEP = ("Keep the exact same person, face, identity, skin tone, camera framing, background, lighting "
        "and body motion as the input video. Photorealistic, no text, no logos. Only change: ")


def cut(ev, path):
    """المقطع بدقة ٧٢٠×١٢٨٠ — كافية للنماذج وأخف بالرفع. الصوت ينشال (الصوت الأصلي يبقى بالمونتاج)."""
    s, e = float(ev["s"]), float(ev["e"])
    rc = subprocess.call(["ffmpeg", "-v", "error", "-ss", f"{s:.3f}", "-i", SRC, "-t", f"{e - s:.3f}",
                          "-vf", "scale=720:1280", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                          "-movflags", "+faststart", "-y", path])
    if rc:
        sys.exit(f"❌ ما قدرت أقص {ev['id']}")


def req(url, data=None, method=None):
    h = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}
    r = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                               headers=h, method=method or ("POST" if data is not None else "GET"))
    with urllib.request.urlopen(r, timeout=120) as f:
        return json.loads(f.read().decode())


def find_video(o):
    """أول رابط فيديو بالرد — كل نموذج يرجّعه بمفتاح مختلف"""
    if isinstance(o, str) and o.startswith("http") and any(x in o.lower() for x in (".mp4", ".mov", ".webm")):
        return o
    if isinstance(o, dict):
        if isinstance(o.get("url"), str) and "video" in json.dumps(o).lower():
            return o["url"]
        o = list(o.values())
    if isinstance(o, list):
        for v in o:
            r = find_video(v)
            if r:
                return r
    return None


def run_remote(ev, inp, dst):
    b64 = base64.b64encode(open(inp, "rb").read()).decode()
    body = dict(cfg.get("aiParams", {}))
    body[cfg.get("aiVideoKey", "video_url")] = "data:video/mp4;base64," + b64
    body[cfg.get("aiPromptKey", "prompt")] = KEEP + ev["prompt"]
    print(f"  ⏫ {ev['id']}: أرسلته للنموذج…")
    q = req(f"https://queue.fal.run/{MODEL}", body)
    st_url = q.get("status_url") or f"https://queue.fal.run/{MODEL}/requests/{q['request_id']}/status"
    res_url = q.get("response_url") or f"https://queue.fal.run/{MODEL}/requests/{q['request_id']}"
    t0 = time.time()
    while True:
        st = req(st_url)
        s = st.get("status")
        if s == "COMPLETED":
            break
        if s not in ("IN_QUEUE", "IN_PROGRESS"):
            sys.exit(f"❌ {ev['id']}: النموذج رجّع حالة «{s}» — {json.dumps(st)[:300]}")
        if time.time() - t0 > 1800:
            sys.exit(f"❌ {ev['id']}: طوّل أكثر من ٣٠ دقيقة — جرّب بعدين")
        print(f"\r  ⏳ {ev['id']}: {s} ({int(time.time() - t0)}ث)", end="", flush=True)
        time.sleep(8)
    print()
    url = find_video(req(res_url))
    if not url:
        sys.exit(f"❌ {ev['id']}: ما لقيت رابط فيديو بالرد")
    urllib.request.urlretrieve(url, dst + ".dl")
    os.replace(dst + ".dl", dst)


manual = []
for ev in evs:
    if not ev.get("prompt"):
        sys.exit(f"❌ {ev['id']}: ناقص prompt (بالإنجليزي — وش يتغيّر بالضبط)")
    ev.setdefault("file", f"fx_ai/{ev['id']}.mp4")
    dst = os.path.join(W, ev["file"])
    if os.path.exists(dst) and not FORCE:
        print(f"  ✓ {ev['id']}: موجود ({ev['file']}) — --force لإعادة التوليد")
        continue
    inp = os.path.join(OUT, f"{ev['id']}_in.mp4")
    cut(ev, inp)
    open(os.path.join(OUT, f"{ev['id']}_prompt.txt"), "w", encoding="utf-8").write(KEEP + ev["prompt"] + "\n")
    if KEY and MODEL:
        try:
            run_remote(ev, inp, dst)
            print(f"  ✅ {ev['id']} → {ev['file']}")
        except urllib.error.HTTPError as e:
            sys.exit(f"❌ {ev['id']}: الخدمة رفضت ({e.code}) — {e.read().decode()[:300]}")
    else:
        manual.append((ev, inp))

if manual:
    why = "ما فيه مفتاح خدمة" if not KEY else "ما فيه نموذج محدد (profile.json ← fx.aiModel)"
    print(f"\n✋ {why} — هذي المقاطع تنولّد باليد:")
    for ev, inp in manual:
        print(f"  • {ev['id']}  ({ev['s']}–{ev['e']}ث)\n    المقطع: {inp}\n    الطلب : {os.path.join(OUT, ev['id'] + '_prompt.txt')}"
              f"\n    الناتج يتحط باسم: {os.path.join(W, ev['file'])}")
    sys.exit(2)
print("✅ مقاطع التوليد جاهزة — كمّل بـ27_fx_render.py")
