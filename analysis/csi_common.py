"""Ortak yardimcilar: CSI log okuma, on isleme, pencereleme.

Beklenen satir bicimi (esp-csi csi_recv ciktisi):
  CSI_DATA,<alanlar...>,"[imag0,real0,imag1,real1,...]"
Alan sayisi cipe/surume gore degisir; bu yuzden SON alani veri dizisi olarak aliriz.
Log dosyamizin formati:  host_time_s;<ham csi satiri>
"""
import csv, json, io, glob, os, re
import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d


def parse_line(line):
    """Ham 'CSI_DATA,...' satirindan int dizisi dondurur (yoksa None)."""
    if not line.startswith("CSI_DATA"):
        return None
    try:
        row = next(csv.reader(io.StringIO(line)))
        vals = json.loads(row[-1])
        return np.array(vals, dtype=np.int16)
    except Exception:
        return None


def load_log(path):
    """-> (t, A): t (T,) saniye, A (T,S) alt tasiyici genlikleri.
    Paket uzunluklari karisiksa en sik gorulen uzunluk tutulur."""
    ts, raws = [], []
    with open(path, encoding="utf8", errors="ignore") as f:
        for ln in f:
            ln = ln.strip()
            if ";" not in ln:
                continue
            t, raw = ln.split(";", 1)
            v = parse_line(raw)
            if v is None or len(v) < 8 or len(v) % 2:
                continue
            try:
                ts.append(float(t))
            except ValueError:
                continue
            raws.append(v)
    if not raws:
        raise ValueError(f"{path}: gecerli CSI satiri yok")
    lens = np.array([len(r) for r in raws])
    modal = np.bincount(lens).argmax()
    keep = lens == modal
    t = np.array(ts)[keep]
    X = np.stack([r for r, k in zip(raws, keep) if k]).astype(float)
    imag, real = X[:, 0::2], X[:, 1::2]          # ESP-IDF: once imag, sonra real
    return t, np.hypot(imag, real)


def preprocess(A, hampel_k=7, smooth=3, mask=None):
    """Kullanilmayan alt tasiyicilari at, Hampel + hareketli ortalama, paket basina normalize."""
    if mask is None:
        mask = A.std(axis=0) > 0                  # tamamen sabit (null/guard) tasiyicilar
    A = A[:, mask]
    med = median_filter(A, size=(hampel_k, 1), mode="nearest")
    mad = median_filter(np.abs(A - med), size=(hampel_k, 1), mode="nearest")
    out = np.abs(A - med) > 3 * 1.4826 * np.maximum(mad, 1e-9)
    A = np.where(out, med, A)
    if smooth > 1:
        A = uniform_filter1d(A, size=smooth, axis=0, mode="nearest")
    A = A / np.maximum(A.mean(axis=1, keepdims=True), 1e-9)   # AGC/guc degisimini sil
    return A, mask


def windows(n, win, step):
    for s in range(0, n - win + 1, step):
        yield s, s + win


def motion_index(A, win=50, step=25):
    """Pencere basina: alt tasiyici varyanslarinin ortalamasi."""
    return np.array([A[a:b].var(axis=0).mean() for a, b in windows(len(A), win, step)])


def file_meta(path):
    """data/<etiket>_<oturum>.csv  ->  (etiket, oturum)   ornek: walk_s2.csv"""
    m = re.match(r"([a-zA-Z]+)_(s\d+)\.csv$", os.path.basename(path))
    if not m:
        raise ValueError(f"Dosya adi etiket_sN.csv olmali: {path}")
    return m.group(1).lower(), m.group(2)


def list_logs(pattern="data/*_s*.csv"):
    return sorted(glob.glob(pattern))
