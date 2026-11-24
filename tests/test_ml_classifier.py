"""Tests for analysis/ml_classifier.py: features and the exported C decision tree."""
import shutil
import subprocess

import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier

from csi_common import preprocess
from ml_classifier import FEATS, calibrate, tree_to_c, window_features


def test_window_features_length_and_band_energies():
    fs = 100.0
    t = np.arange(100) / fs
    W = 1 + 0.1 * np.sin(2 * np.pi * 2.0 * t)[:, None] * np.ones((1, 8))   # 2 Hz motion
    f = window_features(W, fs)
    assert len(f) == len(FEATS)
    bands = dict(zip(FEATS, f))
    assert bands["E_1-3Hz"] > 0.9                                     # energy in the 1-3 Hz band
    assert bands["E_0.3-1Hz"] < 0.05 and bands["E_3-8Hz"] < 0.05
    assert bands["adj_corr"] > 0.99                                   # all subcarriers move together


def test_features_respond_to_motion_after_per_packet_normalisation():
    # Regression: features built on the subcarrier mean were constant on preprocess output,
    # because preprocess divides every packet by that mean.
    rng = np.random.default_rng(1)
    T, S, fs = 200, 52, 87.0
    t = np.arange(T) / fs
    base = 20 + 5 * rng.random(S)
    still = base + rng.normal(0, 0.3, (T, S))
    motion = np.sin(2 * np.pi * 1.5 * t)[:, None] * np.sin(np.linspace(0, 3 * np.pi, S))[None, :]
    moving = still + 3 * motion
    fs_still = dict(zip(FEATS, window_features(preprocess(still)[0], fs)))
    fs_moving = dict(zip(FEATS, window_features(preprocess(moving)[0], fs)))
    assert fs_moving["var_sc_mean"] > 5 * fs_still["var_sc_mean"]
    assert fs_moving["adj_corr"] > fs_still["adj_corr"] + 0.3
    assert fs_moving["E_1-3Hz"] > fs_still["E_1-3Hz"]


def test_calibration_removes_session_offset():
    X = np.array([[1.0], [1.2], [0.8], [1.1], [0.9], [3.0],      # session a, reference + one motion window
                  [11.0], [11.2], [10.8], [11.1], [10.9], [13.0]])  # session b: same, shifted by +10
    g = np.array(["a"] * 6 + ["b"] * 6)
    cal = np.array([True] * 5 + [False] + [True] * 5 + [False])
    Z = calibrate(X, g, cal)
    np.testing.assert_allclose(Z[:6], Z[6:])
    assert Z[5, 0] > 5


@pytest.mark.skipif(shutil.which("cc") is None, reason="no C compiler available")
def test_exported_c_tree_matches_sklearn(tmp_path):
    rng = np.random.default_rng(0)
    X = rng.standard_normal((300, len(FEATS)))
    y = np.select([X[:, 0] > 0.5, X[:, 3] < -0.5], [2, 1], 0)
    clf = DecisionTreeClassifier(max_depth=5, random_state=0).fit(X, y)

    rows = ",\n".join("{" + ",".join(f"{v:.9e}f" for v in x) + "}" for x in X)
    src = tmp_path / "tree_test.c"
    src.write_text(f"""#include <stdio.h>
{tree_to_c(clf)}
static const float X[{len(X)}][{len(FEATS)}] = {{
{rows}
}};
int main(void) {{
    for (int i = 0; i < {len(X)}; i++) printf("%d\\n", csi_tree_predict(X[i]));
    return 0;
}}
""")
    exe = tmp_path / "tree_test"
    subprocess.run(["cc", "-std=c99", "-Wall", "-Werror", "-o", str(exe), str(src)], check=True)
    out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.split()

    c_pred = np.array(out, dtype=int)
    np.testing.assert_array_equal(c_pred, clf.predict(X.astype(np.float32)))
