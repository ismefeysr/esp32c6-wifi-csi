"""WP3 - Feature extraction + lightweight model training (session-based split).

Usage:
  python ml_classifier.py --loso                                  # hold out each session in turn
  python ml_classifier.py --test-sessions s3
  python ml_classifier.py --test-sessions s3 --export-c tree_model.h --max-depth 4

Data: data/<empty|static|walk>_<sN>.csv   (log_csi.py output format)
Windows come from a single session; train and test sets are taken from DIFFERENT
sessions to prevent data leakage.

Calibration: absolute feature levels shift between sessions (gain compensation factor,
placement, room). As in the live demo, each session starts with an empty-room phase: the
windows of the first --cal-seconds of its empty recording are the reference, and every
feature of that session is expressed as (value - reference median) / reference IQR. The
reference windows are never used as test windows. --cal-seconds 0 turns calibration off.
"""
import argparse, glob
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from csi_common import load_log, preprocess, windows, file_meta

LABELS = ["empty", "static", "walk"]
FEATS = ["var_sc_mean", "std_sc_p90", "ptp_sc_mean", "diff_std", "adj_corr",
         "E_0.3-1Hz", "E_1-3Hz", "E_3-8Hz"]


def window_features(W, fs):
    """W: (win, S) normalised amplitudes (preprocess output). Feature vector in FEATS order.

    Everything is computed per subcarrier and then pooled. A mean over subcarriers would be
    useless here: preprocess divides each packet by its subcarrier mean, so that mean is 1.
    """
    D = W - W.mean(axis=0)                      # per-subcarrier deviation within the window
    sd = D.std(axis=0)
    sp = (np.abs(np.fft.rfft(D, axis=0)) ** 2).sum(axis=1)      # spectrum pooled over subcarriers
    fr = np.fft.rfftfreq(len(D), d=1.0 / fs)
    total = sp[fr > 0].sum() + 1e-12
    band = lambda lo, hi: sp[(fr >= lo) & (fr < hi)].sum() / total
    a, b = D[:, :-1], D[:, 1:]                  # neighbouring subcarriers: motion moves them together,
    corr = (a * b).sum(0) / np.sqrt((a * a).sum(0) * (b * b).sum(0) + 1e-12)   # quantisation noise does not
    return [(sd ** 2).mean(), np.percentile(sd, 90), np.ptp(D, axis=0).mean(),
            np.diff(W, axis=0).std(), corr.mean(), band(0.3, 1), band(1, 3), band(3, 8)]


def build(paths, win, step, cal_seconds=30.0):
    """-> X, y, g (session), cal (True for empty-room reference windows)."""
    X, y, g, cal = [], [], [], []
    for p in paths:
        label, sess = file_meta(p)
        if label not in LABELS:
            continue
        t, A = load_log(p)
        fs = 1.0 / np.median(np.diff(t))
        t = t - t[0]
        Ap, _ = preprocess(A)
        for a, b in windows(len(Ap), win, step):
            X.append(window_features(Ap[a:b], fs)); y.append(LABELS.index(label)); g.append(sess)
            cal.append(label == "empty" and t[b - 1] < cal_seconds)
    return np.array(X), np.array(y), np.array(g), np.array(cal, dtype=bool)


def calibrate(X, g, cal):
    """Express each session's features relative to its own empty-room reference windows."""
    Z = X.copy()
    for s in np.unique(g):
        ref = X[(g == s) & cal]
        if len(ref) < 5:
            raise SystemExit(f"Session {s}: not enough empty-room reference windows for calibration "
                             f"(need an empty_{s}.csv; or pass --cal-seconds 0)")
        iqr = np.percentile(ref, 75, axis=0) - np.percentile(ref, 25, axis=0)
        Z[g == s] = (X[g == s] - np.median(ref, axis=0)) / np.maximum(iqr, 1e-9)
    return Z


def make_models(max_depth):
    return {
        "DecisionTree": DecisionTreeClassifier(max_depth=max_depth, random_state=0),
        "RandomForest": RandomForestClassifier(n_estimators=100, max_depth=6, random_state=0),
    }


def evaluate(X, y, g, cal, test_sessions, max_depth, verbose=True):
    """Train on the other sessions, test on test_sessions (reference windows excluded).
    -> {model name: (accuracy, fitted model)}"""
    te = np.isin(g, test_sessions) & ~cal
    tr = ~np.isin(g, test_sessions)
    assert te.any() and tr.any(), "Both training and test sessions are required"
    present = sorted(set(y))                      # only classes that have data (e.g. empty+walk)
    names = [LABELS[i] for i in present]
    if verbose:
        print(f"Windows: train={int(tr.sum())}  test={int(te.sum())}  | test sessions={list(test_sessions)}\n")
    res = {}
    for name, m in make_models(max_depth).items():
        m.fit(X[tr], y[tr])
        pred = m.predict(X[te])
        acc = accuracy_score(y[te], pred)
        res[name] = (acc, m)
        if verbose:
            print(f"== {name}: accuracy = {acc:.3f}")
            print("Confusion matrix (rows=true, cols=predicted), order", names)
            print(confusion_matrix(y[te], pred, labels=present))
            print(classification_report(y[te], pred, labels=present, target_names=names, zero_division=0))
    return res


def tree_to_c(clf, name="csi_tree_predict"):
    """Convert an sklearn decision tree into an if/else C function (for the ESP32)."""
    t = clf.tree_
    lines = [f"// Auto-generated. Input: float f[{len(FEATS)}] in order: {', '.join(FEATS)}",
             f"// (calibrated features: (value - empty-room median) / empty-room IQR, unless trained without)",
             f"// Output: 0=empty 1=static 2=walk",
             f"static inline int {name}(const float *f) {{"]
    def rec(n, ind):
        pad = "    " * ind
        if t.children_left[n] == -1:
            lines.append(f"{pad}return {int(np.argmax(t.value[n][0]))};")
        else:
            lines.append(f"{pad}if (f[{t.feature[n]}] <= {t.threshold[n]:.6e}f) {{")
            rec(t.children_left[n], ind + 1)
            lines.append(f"{pad}}} else {{")
            rec(t.children_right[n], ind + 1)
            lines.append(f"{pad}}}")
    rec(0, 1)
    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/*_s*.csv")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--test-sessions", nargs="+")
    grp.add_argument("--loso", action="store_true", help="leave-one-session-out over all sessions")
    ap.add_argument("--win", type=int, default=100, help="window length (packets, ~1.15 s at 87 Hz)")
    ap.add_argument("--step", type=int, default=25)
    ap.add_argument("--max-depth", type=int, default=4, help="decision tree depth")
    ap.add_argument("--cal-seconds", type=float, default=30.0,
                    help="empty-room reference at the start of each session's empty recording; 0 = off")
    ap.add_argument("--export-c")
    a = ap.parse_args()

    X, y, g, cal = build(sorted(glob.glob(a.data)), a.win, a.step, a.cal_seconds)
    if a.cal_seconds > 0:
        X = calibrate(X, g, cal)

    if a.loso:
        sessions = sorted(set(g), key=lambda s: int(s[1:]))
        rows = {s: evaluate(X, y, g, cal, [s], a.max_depth, verbose=False) for s in sessions}
        models = list(next(iter(rows.values())))
        print(f"Leave-one-session-out accuracy (win={a.win}, step={a.step}, "
              f"calibration={'off' if a.cal_seconds <= 0 else f'{a.cal_seconds:.0f} s'})\n")
        print(f"{'test session':<14}" + "".join(f"{m:>14}" for m in models))
        for s, r in rows.items():
            print(f"{s:<14}" + "".join(f"{r[m][0]:>14.3f}" for m in models))
        print(f"{'mean':<14}" + "".join(f"{np.mean([r[m][0] for r in rows.values()]):>14.3f}" for m in models))
    else:
        res = evaluate(X, y, g, cal, a.test_sessions, a.max_depth)
        if a.export_c:
            open(a.export_c, "w").write(tree_to_c(res["DecisionTree"][1]) + "\n")
            print("C output written:", a.export_c)
