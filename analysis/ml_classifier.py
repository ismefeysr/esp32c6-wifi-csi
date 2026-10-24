"""WP3 - Feature extraction + lightweight model training (session-based split).

Usage:
  python ml_classifier.py --test-sessions s3 --win 50 --step 25
  python ml_classifier.py --test-sessions s3 --export-c tree_model.h --max-depth 6

Data: data/<empty|static|walk>_<sN>.csv   (log_csi.py output format)
Windows come from a single session; train and test sets are taken from DIFFERENT
sessions to prevent data leakage.
"""
import argparse, glob
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from csi_common import load_log, preprocess, windows, file_meta

LABELS = ["empty", "static", "walk"]
FEATS = ["mean", "std", "range", "var_sc_mean", "diff_std", "E_0.3-1Hz", "E_1-3Hz", "E_3-8Hz"]


def window_features(W, fs):
    """W: (win, S) normalised amplitudes. Feature vector in FEATS order."""
    s = W.mean(axis=1)                         # mean over subcarriers (time series)
    sp = np.abs(np.fft.rfft(s - s.mean())) ** 2
    fr = np.fft.rfftfreq(len(s), d=1.0 / fs)
    band = lambda lo, hi: sp[(fr >= lo) & (fr < hi)].sum() / (sp.sum() + 1e-12)
    return [s.mean(), s.std(), np.ptp(s), W.var(axis=0).mean(),
            np.diff(W, axis=0).std(), band(0.3, 1), band(1, 3), band(3, 8)]


def build(paths, win, step):
    X, y, g = [], [], []
    for p in paths:
        label, sess = file_meta(p)
        if label not in LABELS:
            continue
        t, A = load_log(p)
        fs = 1.0 / np.median(np.diff(t))
        Ap, _ = preprocess(A)
        for a, b in windows(len(Ap), win, step):
            X.append(window_features(Ap[a:b], fs)); y.append(LABELS.index(label)); g.append(sess)
    return np.array(X), np.array(y), np.array(g)


def tree_to_c(clf, name="csi_tree_predict"):
    """Convert an sklearn decision tree into an if/else C function (for the ESP32)."""
    t = clf.tree_
    lines = [f"// Auto-generated. Input: float f[{len(FEATS)}] in order: {', '.join(FEATS)}",
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
    ap.add_argument("--test-sessions", nargs="+", required=True)
    ap.add_argument("--win", type=int, default=50)
    ap.add_argument("--step", type=int, default=25)
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--export-c")
    a = ap.parse_args()

    X, y, g = build(sorted(glob.glob(a.data)), a.win, a.step)
    te = np.isin(g, a.test_sessions)
    assert te.any() and (~te).any(), "Both training and test sessions are required"
    print(f"Windows: train={int((~te).sum())}  test={int(te.sum())}  | test sessions={a.test_sessions}\n")

    models = {
        "DecisionTree": DecisionTreeClassifier(max_depth=a.max_depth, random_state=0),
        "RandomForest": RandomForestClassifier(n_estimators=50, max_depth=a.max_depth, random_state=0),
    }
    present = sorted(set(y))                      # only classes that have data (e.g. empty+walk)
    names = [LABELS[i] for i in present]
    best = None
    for name, m in models.items():
        m.fit(X[~te], y[~te])
        pred = m.predict(X[te])
        acc = accuracy_score(y[te], pred)
        print(f"== {name}: accuracy = {acc:.3f}")
        print("Confusion matrix (rows=true, cols=predicted), order", names)
        print(confusion_matrix(y[te], pred, labels=present))
        print(classification_report(y[te], pred, labels=present, target_names=names, zero_division=0))
        if name == "DecisionTree":
            best = m
    if a.export_c:
        open(a.export_c, "w").write(tree_to_c(best) + "\n")
        print("C output written:", a.export_c)
