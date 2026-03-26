"""
train_voice_model.py  (fast edition)
────────────────────────────────────────────────────────────────
Same rich augmentation, but the classifier stack is redesigned
to finish in minutes, not hours:

  • GradientBoosting  REMOVED  (O(n²), not parallelizable)
  • RandomForest      kept, capped at 200 trees
  • LogisticRegression kept
  • NEW: SGDClassifier (SVM-style, extremely fast on large data)
  • Negative set is capped at 3× positives (class ratio preserved)
  • Cross-val uses 3 folds instead of 5 (still honest, 3× faster)
"""

import os, pickle, warnings
import numpy as np
from pathlib import Path
from scipy.signal import butter, sosfilt, fftconvolve
from openwakeword.utils import AudioFeatures
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report
from sklearn.utils import resample

warnings.filterwarnings("ignore")

SR  = 24_000
rng = np.random.default_rng(42)
fe  = AudioFeatures()


# ══════════════════════════════════════════════════════════════════════════
#  Augmentation primitives
# ══════════════════════════════════════════════════════════════════════════

def _norm(c):   return c.astype(np.float32) / 32768.0
def _i16(c):    return np.clip(c * 32768, -32768, 32767).astype(np.int16)
def _fix(c, n=SR):
    if len(c) < n: return np.pad(c, (0, n - len(c)))
    return c[:n]

def aug_volume(c, lo=0.5, hi=1.4):
    return _i16(_fix(_norm(c) * rng.uniform(lo, hi)))

def aug_gaussian(c, lo=0.002, hi=0.025):
    return _i16(_fix(_norm(c) + rng.normal(0, rng.uniform(lo, hi), SR)))

def _pink(n):
    f = np.fft.rfftfreq(n); f[0] = 1e-6
    s = (rng.standard_normal(len(f)) + 1j*rng.standard_normal(len(f))) / np.sqrt(f)
    return np.fft.irfft(s, n=n).astype(np.float32)

def aug_pink(c, lv=0.03):
    return _i16(_fix(_norm(c) + _pink(SR)*rng.uniform(0.005, lv)))

def aug_brown(c, lv=0.03):
    b = np.cumsum(rng.standard_normal(SR).astype(np.float32))
    b -= b.mean(); b /= (np.abs(b).max()+1e-9)
    return _i16(_fix(_norm(c) + b*rng.uniform(0.005, lv)))

def aug_pitch(c, st=None):
    if st is None: st = rng.uniform(-4, 4)
    spd = 2**(st/12.0)
    idx = np.round(np.arange(0, SR, spd)).astype(int); idx = idx[idx < SR]
    return _i16(_fix(_norm(c)[idx]))

def aug_stretch(c, rate=None):
    if rate is None: rate = rng.uniform(0.85, 1.15)
    idx = np.round(np.arange(0, SR, rate)).astype(int); idx = idx[idx < SR]
    return _i16(_fix(_norm(c)[idx]))

def aug_reverb(c, decay=None, delay_ms=None):
    if decay    is None: decay    = rng.uniform(0.2, 0.6)
    if delay_ms is None: delay_ms = rng.integers(20, 120)
    x = _norm(c)
    ds = int(SR * delay_ms / 1000)
    k  = np.zeros(ds+1, np.float32); k[0]=1.0; k[-1]=decay
    r  = fftconvolve(x, k)[:SR].astype(np.float32)
    m  = x + 0.4*_fix(r); m /= (np.abs(m).max()+1e-9)
    return _i16(_fix(m))

def aug_clip(c, thr=None):
    if thr is None: thr = rng.uniform(0.5, 0.95)
    x = np.clip(_norm(c), -thr, thr) / thr
    return _i16(_fix(x))

def aug_bandpass(c, lo=None, hi=None):
    if lo is None: lo = rng.integers(200, 500)
    if hi is None: hi = rng.integers(3000, 7000)
    x = _norm(c).astype(np.float64)
    sos = butter(4, [lo, hi], btype="band", fs=SR, output="sos")
    x = sosfilt(sos, x).astype(np.float32)
    x /= (np.abs(x).max()+1e-9)
    return _i16(_fix(x))

def aug_dc(c):
    return _i16(_fix(_norm(c) + rng.uniform(-0.05, 0.05)))

AUGS = [aug_volume, aug_gaussian, aug_pink, aug_brown,
        aug_pitch, aug_stretch, aug_reverb, aug_clip, aug_bandpass, aug_dc]

def augment_clip(clip, n=20):
    out = []
    for st in (+2, -2, +4, -4):
        out.append(aug_pitch(clip, st=st))
    out.append(aug_reverb(clip, decay=0.4, delay_ms=60))
    out.append(aug_bandpass(clip, lo=300, hi=3400))
    out.append(aug_gaussian(clip, lo=0.01, hi=0.03))
    out.append(aug_clip(clip, thr=0.7))
    while len(out) < n:
        k   = rng.choice([1,2,3], p=[0.33,0.40,0.27])
        fns = list(rng.choice(AUGS, size=k, replace=False))
        x   = clip.copy()
        for fn in fns: x = fn(x)
        out.append(x)
    return out[:n]


# ══════════════════════════════════════════════════════════════════════════
#  Data loading
# ══════════════════════════════════════════════════════════════════════════

def load_folder(folder):
    clips = []
    p = Path(folder)
    if not p.exists():
        print(f"  ⚠  not found: {folder}"); return clips
    for f in sorted(p.glob("*.npy")):
        arr = np.load(f).flatten().astype(np.float32)/32768.0
        clips.append(_i16(_fix(arr)))
    return clips


# ══════════════════════════════════════════════════════════════════════════
#  Synthetic negatives
# ══════════════════════════════════════════════════════════════════════════

def make_synth_negs(n=200):
    out = []
    for _ in range(n//4):
        out.append(_i16(_fix(rng.normal(0,0.02,SR).astype(np.float32))))
    for _ in range(n//4):
        out.append(_i16(_fix(_pink(SR)*0.05)))
    for _ in range(n//4):
        c = np.zeros(SR, np.float32)
        for _ in range(rng.integers(1,5)):
            s = rng.integers(0, SR-1000)
            c[s:s+500] = rng.normal(0,0.1,500)
        out.append(_i16(_fix(c)))
    for _ in range(n//4):
        t = np.linspace(0,1,SR)
        c = (np.sin(2*np.pi*rng.uniform(100,3000)*t)*0.3).astype(np.float32)
        out.append(_i16(_fix(c)))
    return out


# ══════════════════════════════════════════════════════════════════════════
#  Feature extraction
# ══════════════════════════════════════════════════════════════════════════

def extract(clips, batch=64, label=""):
    feats = []
    n = len(clips)
    for i in range(0, n, batch):
        b = np.stack(clips[i:i+batch])
        feats.append(fe.embed_clips(b).reshape(len(b), -1))
        print(f"  [{label}] {min(i+batch,n)}/{n}", end="\r")
    print()
    return np.vstack(feats)


# ══════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    N_VARIANTS   = 20    # augmented copies per raw clip
    NEG_RATIO    = 3     # cap negatives at N× positives

    # ── Load ──────────────────────────────────────────────────────────────
    print("\n📂 Loading clips...")
    pos_clips = load_folder("training_data/positive")
    neg_clips = load_folder("training_data/negative")
    print(f"   Positives (raw): {len(pos_clips)}")
    print(f"   Negatives (raw): {len(neg_clips)}")

    # ── Augment positives ─────────────────────────────────────────────────
    print(f"\n🎛  Augmenting positives ({N_VARIANTS} variants each)...")
    pos_aug = []
    for c in pos_clips:
        pos_aug.append(c)
        pos_aug.extend(augment_clip(c, n=N_VARIANTS))
    print(f"   Positives after aug: {len(pos_aug)}")

    # ── Augment + cap negatives ───────────────────────────────────────────
    print(f"\n🎛  Augmenting negatives (capping at {NEG_RATIO}× positives)...")
    neg_aug = []
    for c in neg_clips:
        neg_aug.append(c)
        neg_aug.extend(augment_clip(c, n=N_VARIANTS))
    neg_aug.extend(make_synth_negs(n=200))

    cap = len(pos_aug) * NEG_RATIO
    if len(neg_aug) > cap:
        neg_aug = resample(neg_aug, n_samples=cap, replace=False, random_state=42)
        print(f"   Negatives capped at : {len(neg_aug)}")
    else:
        print(f"   Negatives after aug : {len(neg_aug)}")

    # ── Extract features ──────────────────────────────────────────────────
    print("\n🔬 Extracting features...")
    pos_feats = extract(pos_aug, label="pos")
    neg_feats = extract(neg_aug, label="neg")

    X = np.vstack([pos_feats, neg_feats])
    y = np.array([1]*len(pos_feats) + [0]*len(neg_feats))
    print(f"\n   Dataset shape : {X.shape}")
    print(f"   Positives     : {len(pos_feats)}")
    print(f"   Negatives     : {len(neg_feats)}")

    # ── Fast ensemble: SGD + LR + RF  (no GradientBoosting) ──────────────
    print("\n🤖 Building ensemble (SGD + LR + RF)...")

    sgd = Pipeline([
        ("sc", StandardScaler()),
        ("cl", SGDClassifier(loss="modified_huber", max_iter=1000,
                             class_weight="balanced", random_state=42, n_jobs=-1))
    ])

    lr = Pipeline([
        ("sc", StandardScaler()),
        ("cl", LogisticRegression(C=0.5, max_iter=2000,
                                  class_weight="balanced", n_jobs=-1))
    ])

    rf = RandomForestClassifier(
        n_estimators=200, max_depth=12, min_samples_leaf=2,
        class_weight="balanced", n_jobs=-1, random_state=42
    )

    ensemble = VotingClassifier(
        estimators=[("sgd", sgd), ("lr", lr), ("rf", rf)],
        voting="soft",
        weights=[1, 1, 2],
        n_jobs=-1
    )

    # ── Cross-validate (3-fold) ───────────────────────────────────────────
    print("\n📊 Cross-validating (3-fold)...")
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    for metric in ["f1", "precision", "recall", "roc_auc"]:
        scores = cross_val_score(ensemble, X, y, cv=cv, scoring=metric, n_jobs=-1)
        print(f"   {metric:12s}: {scores.mean():.3f} ± {scores.std():.3f}")

    # ── Final fit ─────────────────────────────────────────────────────────
    print("\n🏋  Training final model...")
    ensemble.fit(X, y)

    y_pred = ensemble.predict(X)
    print("\n📋 Train-set report:")
    print(classification_report(y, y_pred, target_names=["negative","positive"]))

    # ── Save ──────────────────────────────────────────────────────────────
    os.makedirs("voice_models", exist_ok=True)
    out = "voice_models/sentee_naal_clf.pkl"
    with open(out, "wb") as fh: pickle.dump(ensemble, fh)
    print(f"✅ Saved → {out}")

    meta = dict(sr=SR, n_pos_raw=len(pos_clips), n_neg_raw=len(neg_clips),
                n_pos_aug=len(pos_feats), n_neg_aug=len(neg_feats),
                n_variants=N_VARIANTS, neg_ratio=NEG_RATIO,
                classifiers=["SGD","LogisticRegression","RandomForest"])
    with open("voice_models/sentee_naal_meta.pkl","wb") as fh: pickle.dump(meta, fh)
    print("✅ Saved metadata → voice_models/sentee_naal_meta.pkl\n")