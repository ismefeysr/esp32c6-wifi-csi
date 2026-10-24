"""Donanim olmadan hatti denemek icin SENTETIK CSI kaydi uretir.
GERCEK VERI DEGILDIR; sadece betiklerin calistigini dogrulamak icindir.
Rapora/sonuclara asla koyma.

Bicim, firmware/csi_recv (esp32c6) ciktisiyla birebir ayni:
  128 alt tasiyici (256 deger, imag/real), HT40, ~100 paket/sn,
  null/guard tasiyicilar 0-5, 63-65, 123-127 sifir (gercek C6 kaydindan).
Genlik araligi gercek kayda gore secildi; hareket modeli ise TAMAMEN uydurmadir.

  python make_fake_data.py          -> data_fake/ klasoru
Sonra:  python baseline.py --calib data_fake/empty_s1.csv --test "data_fake/*_s2.csv"
"""
import os, numpy as np
os.makedirs("data_fake", exist_ok=True)
S, FS, DUR = 128, 100.0, 90        # alt tasiyici, paket/sn, sure
NULL = list(range(0, 6)) + [63, 64, 65] + list(range(123, 128))
MAC = "1a:00:00:00:00:00"          # csi_send MAC'i

def make(label, sess, seed):
    r = np.random.default_rng(seed)
    n = int(FS * DUR); t = np.arange(n) / FS
    base = r.uniform(140, 380, S)
    amp = np.tile(base, (n, 1)) * (1 + 0.02 * r.standard_normal((n, S)))
    if label == "static":      # kucuk yavas degisim (nefes benzeri)
        amp *= 1 + 0.03 * np.sin(2 * np.pi * 0.3 * t)[:, None] * r.uniform(.5, 1, S)
    if label == "walk":        # buyuk, 0.5-2 Hz dalgalanma
        f = r.uniform(0.5, 2.0)
        amp *= 1 + 0.15 * np.sin(2 * np.pi * f * t[:, None] + r.uniform(0, 6, S)) * r.uniform(.5, 1, (n, S))
    amp[:, NULL] = 0
    ph = r.uniform(0, 2 * np.pi, S)
    imag, real = (amp * np.sin(ph)).round().astype(int), (amp * np.cos(ph)).round().astype(int)
    rssi = -62 + r.integers(-2, 3, n)
    with open(f"data_fake/{label}_{sess}.csv", "w") as f:
        for i in range(n):
            vals = np.empty(2 * S, int); vals[0::2] = imag[i]; vals[1::2] = real[i]
            ts_us = int(t[i] * 1e6)
            # type,seq,mac,rssi,rate,noise_floor,fft_gain,agc_gain,channel,local_timestamp,sig_len,rx_format,len,first_word,data
            f.write(f'{1000 + t[i]:.4f};CSI_DATA,{i},{MAC},{rssi[i]},11,-97,22,46,11,{ts_us},47,2,{2*S},0,'
                    f'"[{",".join(map(str, vals))}]"\n')

seed = 0
for sess in ["s1", "s2", "s3"]:
    for label in ["empty", "static", "walk"]:
        seed += 1; make(label, sess, seed)
print("data_fake/ olustu")
