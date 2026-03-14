import os, pickle
import numpy as np
from pathlib import Path
from openwakeword.utils import AudioFeatures
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score

fe  = AudioFeatures()
rng = np.random.default_rng(42)

# ── Augmentation ──────────────────────────────────────────────────────────
def augment(clip, n=5):
    """Generate n augmented versions of a clip."""
    results = [clip]
    for _ in range(n):
        c = clip.copy().astype(np.float32)

        # random volume 60%–130%
        c *= rng.uniform(0.6, 1.3)

        # additive background noise
        c += rng.normal(0, rng.uniform(0.001, 0.015), len(c))

        # random pitch shift via resampling (cheap approximation)
        speed = rng.uniform(0.92, 1.08)
        indices = np.round(np.arange(0, len(c), speed)).astype(int)
        indices = indices[indices < len(c)]
        c = c[indices]

        # pad or trim back to 24000
        if len(c) < 24000:
            c = np.pad(c, (0, 24000 - len(c)))
        else:
            c = c[:24000]

        results.append(np.clip(c, -32768, 32767).astype(np.int16))

    return results


def load_folder(folder):
    clips = []
    for f in sorted(Path(folder).glob("*.npy")):
        arr = np.load(f).flatten().astype(np.float32) / 32768.0
        if len(arr) < 24000:
            arr = np.pad(arr, (0, 24000 - len(arr)))
        else:
            arr = arr[:24000]
        clips.append((arr * 32768).astype(np.int16))
    return clips


# ── Load clips ────────────────────────────────────────────────────────────
print("Loading positive samples...")
pos_clips = load_folder("training_data/positive")
print(f"  {len(pos_clips)} raw positive clips")

print("Loading negative samples...")
neg_clips = load_folder("training_data/negative")
print(f"  {len(neg_clips)} raw negative clips")

# ── Augment ───────────────────────────────────────────────────────────────
print("Augmenting...")
pos_aug = []
for c in pos_clips:
    pos_aug.extend(augment(c, n=5))   # 201 × 6 = ~1200

neg_aug = []
for c in neg_clips:
    neg_aug.extend(augment(c, n=5))   # 100 × 6 = ~600

# add pure noise negatives too
for _ in range(300):
    noise = rng.normal(0, 0.02, 24000)
    neg_aug.append(np.clip(noise * 32768, -32768, 32767).astype(np.int16))

print(f"  positives after aug: {len(pos_aug)}")
print(f"  negatives after aug: {len(neg_aug)}")

# ── Extract features ──────────────────────────────────────────────────────
print("Extracting features (this may take a minute)...")

def extract_features(clips, batch=64):
    all_feats = []
    for i in range(0, len(clips), batch):
        batch_arr = np.stack(clips[i:i+batch])
        feats = fe.embed_clips(batch_arr).reshape(len(batch_arr), -1)
        all_feats.append(feats)
        print(f"  {min(i+batch, len(clips))}/{len(clips)}", end="\r")
    print()
    return np.vstack(all_feats)

pos_feats = extract_features(pos_aug)
neg_feats = extract_features(neg_aug)

X = np.vstack([pos_feats, neg_feats])
y = np.array([1]*len(pos_feats) + [0]*len(neg_feats))
print(f"Dataset: {X.shape}  pos={len(pos_feats)}  neg={len(neg_feats)}")

# ── Train ─────────────────────────────────────────────────────────────────
clf = Pipeline([
    ("scaler", StandardScaler()),
    ("lr",     LogisticRegression(C=1.0, max_iter=1000))  # C=0.1 = more regularization
])

scores = cross_val_score(clf, X, y, cv=5, scoring="f1")
print(f"Cross-val F1: {scores.mean():.3f} ± {scores.std():.3f}")

clf.fit(X, y)

os.makedirs("voice_models", exist_ok=True)
with open("voice_models/sentee_naal_clf.pkl", "wb") as fh:
    pickle.dump(clf, fh)

print("Saved → voice_models/sentee_naal_clf.pkl")