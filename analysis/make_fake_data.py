"""Generate SYNTHETIC CSI recordings to exercise the pipeline without hardware.
THIS IS NOT REAL DATA; it only verifies that the scripts run.
Never use it in reports or results.

The format matches the firmware/csi_recv (esp32c6) output exactly:
  128 subcarriers (256 values, imag/real), HT40, ~100 packets/s,
  null/guard carriers 0-5, 63-65, 123-127 are zero (taken from a real C6 capture).
The amplitude range is taken from a real capture; the motion model is ENTIRELY made up.

  python make_fake_data.py          -> data_fake/ directory
Then:  python baseline.py --calib data_fake/empty_s1.csv --test "data_fake/*_s2.csv"
"""
import os, numpy as np
os.makedirs("data_fake", exist_ok=True)
S, FS, DUR = 128, 100.0, 90        # subcarriers, packets/s, duration
NULL = list(range(0, 6)) + [63, 64, 65] + list(range(123, 128))
MAC = "1a:00:00:00:00:00"          # csi_send MAC

def make(label, sess, seed):
    r = np.random.default_rng(seed)
    n = int(FS * DUR); t = np.arange(n) / FS
    base = r.uniform(140, 380, S)
    amp = np.tile(base, (n, 1)) * (1 + 0.02 * r.standard_normal((n, S)))
    if label == "static":      # small slow variation (breathing-like)
        amp *= 1 + 0.03 * np.sin(2 * np.pi * 0.3 * t)[:, None] * r.uniform(.5, 1, S)
    if label == "walk":        # large 0.5-2 Hz fluctuation
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
print("data_fake/ created")
