"""Donanim olmadan hatti denemek icin SENTETIK CSI kaydi uretir.
GERCEK VERI DEGILDIR; sadece betiklerin calistigini dogrulamak icindir.
Rapora/sonuclara asla koyma.

  python make_fake_data.py          -> data_fake/ klasoru
Sonra:  python baseline.py --calib data_fake/empty_s1.csv --test "data_fake/*_s2.csv"
"""
import os, numpy as np
rng = np.random.default_rng(0)
os.makedirs("data_fake", exist_ok=True)
S, FS, DUR = 52, 50.0, 90          # alt tasiyici, paket/sn, sure

def make(label, sess, seed):
    r = np.random.default_rng(seed)
    n = int(FS * DUR); t = np.arange(n) / FS
    base = r.uniform(20, 40, S)
    amp = np.tile(base, (n, 1)) * (1 + 0.01 * r.standard_normal((n, S)))
    if label == "static":      # kucuk yavas degisim (nefes benzeri)
        amp *= 1 + 0.03 * np.sin(2 * np.pi * 0.3 * t)[:, None] * r.uniform(.5, 1, S)
    if label == "walk":        # buyuk, 0.5-2 Hz dalgalanma
        f = r.uniform(0.5, 2.0)
        amp *= 1 + 0.15 * np.sin(2 * np.pi * f * t[:, None] + r.uniform(0, 6, S)) * r.uniform(.5, 1, (n, S))
    ph = r.uniform(0, 2 * np.pi, S)
    imag, real = (amp * np.sin(ph)).round(), (amp * np.cos(ph)).round()
    with open(f"data_fake/{label}_{sess}.csv", "w") as f:
        for i in range(n):
            vals = np.empty(2 * S, int); vals[0::2] = imag[i]; vals[1::2] = real[i]
            f.write(f'{1000 + t[i]:.4f};CSI_DATA,{i},aa:bb:cc:dd:ee:ff,-50,11,0,0,0,0,0,0,0,0,0,-90,0,1,0,0,0,{2*S},0,{2*S},0,"[{",".join(map(str, vals))}]"\n')

seed = 0
for sess in ["s1", "s2", "s3"]:
    for label in ["empty", "static", "walk"]:
        seed += 1; make(label, sess, seed)
print("data_fake/ olustu")
