"""WP2 - Threshold-based baseline detector.

Calibration: mean + k*std of the motion index over empty-room recordings.
Evaluation: per-window detection rate over all recordings.

Usage:
  python baseline.py --calib data/empty_s1.csv --k 4 --test "data/*_s2.csv" --win 50 --step 25
"""
import argparse, glob
import numpy as np
from csi_common import load_log, preprocess, motion_index, file_meta

ap = argparse.ArgumentParser()
ap.add_argument("--calib", nargs="+", required=True, help="empty-room recording(s)")
ap.add_argument("--test", default="data/*_s*.csv")
ap.add_argument("--k", type=float, default=4.0)
ap.add_argument("--win", type=int, default=50, help="window length (packets)")
ap.add_argument("--step", type=int, default=25)
a = ap.parse_args()

# ---- calibration
idx, mask = [], None
for p in a.calib:
    _, A = load_log(p)
    Ap, mask = preprocess(A, mask=mask)
    idx.append(motion_index(Ap, a.win, a.step))
idx = np.concatenate(idx)
thr = idx.mean() + a.k * idx.std()
print(f"Calibration: {len(idx)} windows | mean={idx.mean():.3e} std={idx.std():.3e} | threshold={thr:.3e}\n")

# ---- evaluation
print(f"{'file':<22}{'label':<8}{'windows':>8}{'above thr %':>13}")
res = {}
for p in sorted(glob.glob(a.test)):
    try:
        label, sess = file_meta(p)
        _, A = load_log(p)
    except Exception as e:
        print("skipped:", p, e); continue
    Ap, _ = preprocess(A, mask=mask if mask is not None and A.shape[1] == len(mask) else None)
    m = motion_index(Ap, a.win, a.step)
    frac = 100 * (m > thr).mean()
    res.setdefault(label, []).append(frac)
    print(f"{p.split('/')[-1]:<22}{label:<8}{len(m):>8}{frac:>12.1f}%")

print("\nSummary (fraction of windows above threshold):")
if "empty" in res:
    print(f"  False alarm rate (empty room)       : {np.mean(res['empty']):.1f}%")
if "walk" in res:
    print(f"  Motion detection rate (walking)     : {np.mean(res['walk']):.1f}%  -> miss rate = {100-np.mean(res['walk']):.1f}%")
if "static" in res:
    print(f"  Detection rate (person standing)    : {np.mean(res['static']):.1f}%")
print("\nNote: a variance threshold only answers 'motion / no motion'; it is weak at detecting a person standing still. The ML stage targets this.")
