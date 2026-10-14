"""WP2 - Esik tabanli baseline.

Kalibrasyon: bos oda kayitlarindan hareket indeksinin ortalama + k*std'si.
Degerlendirme: tum kayitlarda pencere bazli tespit orani.

Kullanim:
  python baseline.py --calib data/empty_s1.csv --k 4 --test "data/*_s2.csv" --win 50 --step 25
"""
import argparse, glob
import numpy as np
from csi_common import load_log, preprocess, motion_index, file_meta

ap = argparse.ArgumentParser()
ap.add_argument("--calib", nargs="+", required=True, help="bos oda kayit(lari)")
ap.add_argument("--test", default="data/*_s*.csv")
ap.add_argument("--k", type=float, default=4.0)
ap.add_argument("--win", type=int, default=50, help="pencere (paket)")
ap.add_argument("--step", type=int, default=25)
a = ap.parse_args()

# ---- kalibrasyon
idx, mask = [], None
for p in a.calib:
    _, A = load_log(p)
    Ap, mask = preprocess(A, mask=mask)
    idx.append(motion_index(Ap, a.win, a.step))
idx = np.concatenate(idx)
thr = idx.mean() + a.k * idx.std()
print(f"Kalibrasyon: {len(idx)} pencere | ort={idx.mean():.3e} std={idx.std():.3e} | esik={thr:.3e}\n")

# ---- degerlendirme
print(f"{'dosya':<22}{'etiket':<8}{'pencere':>8}{'esik ustu %':>13}")
res = {}
for p in sorted(glob.glob(a.test)):
    try:
        label, sess = file_meta(p)
        _, A = load_log(p)
    except Exception as e:
        print("atlandi:", p, e); continue
    Ap, _ = preprocess(A, mask=mask if mask is not None and A.shape[1] == len(mask) else None)
    m = motion_index(Ap, a.win, a.step)
    frac = 100 * (m > thr).mean()
    res.setdefault(label, []).append(frac)
    print(f"{p.split('/')[-1]:<22}{label:<8}{len(m):>8}{frac:>12.1f}%")

print("\nOzet (esik ustu pencere orani):")
if "empty" in res:
    print(f"  Yanlis alarm orani (bos oda)        : {np.mean(res['empty']):.1f}%")
if "walk" in res:
    print(f"  Hareket tespit orani (yuruyen)      : {np.mean(res['walk']):.1f}%  -> kacirma = {100-np.mean(res['walk']):.1f}%")
if "static" in res:
    print(f"  Sabit kisi tespit orani             : {np.mean(res['static']):.1f}%")
print("\nNot: varyans esigi 'hareket var/yok' der; sabit duran kisiyi ayirmakta zayiftir. ML asamasi bunu hedefler.")
