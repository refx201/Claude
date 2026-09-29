# -*- coding: utf-8 -*-
"""أدوات مشتركة لوضع المؤثرات (26 · 27 · 28): قراءة وكتابة الفيديو فريم فريم، ونماذج اليد والقص.

الفيديو يُقرأ ويُكتب عبر ffmpeg (أنابيب خام) — ما نحتاج ffprobe، والأبعاد والفريمات من opencv.
النماذج (اليد · قص الشخص) تنزل مرة وحدة لمجلد بياناته tools/ وتنعاد تستعمل.
"""
import os, sys, json, subprocess, urllib.request
os.environ.setdefault("GLOG_minloglevel", "2")          # نسكّت رسايل mediapipe الداخلية
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths

MODELS = {
    "hand": ("hand_landmarker.task",
             "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"),
    # متعدد الفئات (خلفية · شعر · بشرة · لبس) — حوافه وشعره أنظف بكثير من نموذج القص العادي
    "person": ("selfie_multiclass_256x256.tflite",
               "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite"),
}


def need_cv():
    try:
        import cv2  # noqa
        import mediapipe  # noqa
    except ImportError:
        print("⚠️ ناقص mediapipe أو opencv — شغّل: bash scripts/00_setup.sh --install")
        sys.exit(3)


def model(name):
    fn, url = MODELS[name]
    _paths.ensure()
    p = _paths.data("tools", fn)
    if not os.path.exists(p) or os.path.getsize(p) < 1000:
        print(f"⏬ نموذج {name} (مرة وحدة)…")
        urllib.request.urlretrieve(url, p + ".part")
        os.replace(p + ".part", p)
    return p


def probe(path):
    """(عرض، طول، fps، عدد الفريمات)"""
    import cv2
    c = cv2.VideoCapture(path)
    if not c.isOpened():
        sys.exit(f"❌ ما قدرت أفتح {path}")
    w, h = int(c.get(cv2.CAP_PROP_FRAME_WIDTH)), int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = c.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    c.release()
    return w, h, fps, n


def frames(path, w, h, size=None):
    """يولّد فريمات RGB (uint8) بالترتيب. size=(w,h) يصغّر أثناء الفك."""
    ow, oh = size or (w, h)
    vf = ["-vf", f"scale={ow}:{oh}"] if size else []
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, *vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    fsz = ow * oh * 3
    try:
        while True:
            b = p.stdout.read(fsz)
            if len(b) < fsz:
                break
            yield np.frombuffer(b, np.uint8).reshape(oh, ow, 3)
    finally:
        p.kill()                  # لو وقفنا بنص الفيديو (المعاينة) — بلا رسايل «أنبوب مكسور»
        p.stdout.close()
        p.wait()


class Writer:
    """يكتب فريمات RGB لفيديو، ويلصق صوت ملف ثاني كما هو (بلا إعادة ترميز)."""

    def __init__(self, out, w, h, fps, audio_from=None):
        a = ["-i", audio_from, "-map", "0:v", "-map", "1:a?", "-c:a", "copy"] if audio_from else []
        self.p = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
             "-r", f"{fps}", "-i", "-", *a, "-c:v", "libx264", "-preset", "medium", "-crf", "16",
             "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
             "-color_trc", "bt709", "-movflags", "+faststart", "-shortest", "-y", out],
            stdin=subprocess.PIPE)

    def write(self, f):
        self.p.stdin.write(np.ascontiguousarray(f, np.uint8).tobytes())

    def close(self):
        self.p.stdin.close()
        return self.p.wait()


def cover(img, w, h):
    """يعبّي الإطار بلا تشويه (يقص الزايد من الوسط) — مثل object-fit: cover."""
    import cv2
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    r = cv2.resize(img, (max(w, round(iw * s)), max(h, round(ih * s))), interpolation=cv2.INTER_AREA)
    y, x = (r.shape[0] - h) // 2, (r.shape[1] - w) // 2
    return r[y:y + h, x:x + w]


def load_fx(W):
    p = os.path.join(W, "fx.json")
    if not os.path.exists(p):
        sys.exit("❌ ما فيه fx.json — اكتبه أول (references/fx.md)")
    return json.load(open(p, encoding="utf-8"))


def base_video(W):
    """النسخة بلا مؤثرات: cutz_nofx.mp4. لو 03_cut_zoom طلّع cutz.mp4 جديد بعد آخر رندر مؤثرات، ننسخه."""
    cut, raw, st = (os.path.join(W, x) for x in ("cutz.mp4", "cutz_nofx.mp4", ".fx_state.json"))
    if not os.path.exists(cut) and not os.path.exists(raw):
        sys.exit("❌ ما فيه cutz.mp4 — شغّل 03_cut_zoom.py أول")
    ours = json.load(open(st)) if os.path.exists(st) else {}
    if os.path.exists(cut):
        sig = [os.path.getsize(cut), int(os.path.getmtime(cut))]
        if not os.path.exists(raw) or ours.get("sig") != sig:
            import shutil
            shutil.copy2(cut, raw)       # cutz.mp4 طازج من القص — هو الأصل الجديد
    return raw


def mark_rendered(W):
    cut = os.path.join(W, "cutz.mp4")
    json.dump({"sig": [os.path.getsize(cut), int(os.path.getmtime(cut))]},
              open(os.path.join(W, ".fx_state.json"), "w"))
