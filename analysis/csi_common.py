"""Shared helpers: CSI log loading, preprocessing and windowing.

Expected line format (output of firmware/csi_recv):
  CSI_DATA,<fields...>,"[imag0,real0,imag1,real1,...]"
The number of fields depends on the chip and IDF version, so the LAST field
is always taken as the data array.
Log file format written by log_csi.py:  host_time_s;<raw CSI line>
"""
import csv, json, io, glob, os, re
import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d


def parse_line(line):
    """Return the int array of a raw 'CSI_DATA,...' line (None if invalid)."""
    if not line.startswith("CSI_DATA"):
        return None
    try:
        row = next(csv.reader(io.StringIO(line)))
        vals = json.loads(row[-1])
        if not isinstance(vals, list):            # truncated line: last field is not the array
            return None
        return np.array(vals, dtype=np.int16)
    except Exception:
        return None


def load_log(path):
    """-> (t, A): t (T,) seconds, A (T,S) subcarrier amplitudes.
    If packet lengths are mixed, only the most common length is kept."""
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
        raise ValueError(f"{path}: no valid CSI lines")
    lens = np.array([len(r) for r in raws])
    modal = np.bincount(lens).argmax()
    keep = lens == modal
    t = np.array(ts)[keep]
    X = np.stack([r for r, k in zip(raws, keep) if k]).astype(float)
    imag, real = X[:, 0::2], X[:, 1::2]          # ESP-IDF order: imag first, then real
    return t, np.hypot(imag, real)


def preprocess(A, hampel_k=7, smooth=3, mask=None):
    """Drop unused subcarriers, apply Hampel filter + moving average, normalise per packet."""
    if mask is None:
        mask = A.std(axis=0) > 0                  # constant (null/guard) subcarriers
    A = A[:, mask]
    med = median_filter(A, size=(hampel_k, 1), mode="nearest")
    mad = median_filter(np.abs(A - med), size=(hampel_k, 1), mode="nearest")
    out = np.abs(A - med) > 3 * 1.4826 * np.maximum(mad, 1e-9)
    A = np.where(out, med, A)
    if smooth > 1:
        A = uniform_filter1d(A, size=smooth, axis=0, mode="nearest")
    A = A / np.maximum(A.mean(axis=1, keepdims=True), 1e-9)   # remove AGC/power changes
    return A, mask


def windows(n, win, step):
    for s in range(0, n - win + 1, step):
        yield s, s + win


def motion_index(A, win=50, step=25):
    """Per window: mean of the subcarrier variances."""
    return np.array([A[a:b].var(axis=0).mean() for a, b in windows(len(A), win, step)])


def file_meta(path):
    """data/<label>_<session>.csv  ->  (label, session)   e.g. walk_s2.csv"""
    m = re.match(r"([a-zA-Z]+)_(s\d+)\.csv$", os.path.basename(path))
    if not m:
        raise ValueError(f"File name must be <label>_sN.csv: {path}")
    return m.group(1).lower(), m.group(2)


def list_logs(pattern="data/*_s*.csv"):
    return sorted(glob.glob(pattern))


def seq_stats(seq):
    """Loss from the sender's packet counter. A counter that goes backwards is a
    sender reset; each segment is counted separately.
    -> dict(received, expected, loss_pct, gaps, max_gap, resets)"""
    if len(seq) < 2:
        return dict(received=len(seq), expected=len(seq), loss_pct=0.0, gaps=0, max_gap=0, resets=0)
    expected, gaps, resets = 0, [], 0
    start = prev = seq[0]
    for s in seq[1:]:
        if s <= prev:
            expected += prev - start + 1
            start, resets = s, resets + 1
        elif s - prev > 1:
            gaps.append(s - prev - 1)
        prev = s
    expected += prev - start + 1
    return dict(received=len(seq), expected=expected, loss_pct=100 * (1 - len(seq) / expected),
                gaps=len(gaps), max_gap=max(gaps, default=0), resets=resets)


def log_quality(path):
    """Recording health from a log_csi file: packet count, rate, seq loss, largest time gap."""
    ts, seq = [], []
    with open(path, encoding="utf8", errors="ignore") as f:
        for ln in f:
            t, _, raw = ln.strip().partition(";")
            if parse_line(raw) is None:
                continue
            try:
                ts.append(float(t))
                seq.append(int(raw.split(",", 2)[1]))
            except (ValueError, IndexError):
                continue
    q = seq_stats(seq)
    dur = ts[-1] - ts[0] if len(ts) > 1 else 0.0
    q.update(duration_s=dur, rate_hz=(len(ts) - 1) / dur if dur > 0 else 0.0,
             max_time_gap_s=float(np.diff(ts).max()) if len(ts) > 1 else 0.0)
    return q
