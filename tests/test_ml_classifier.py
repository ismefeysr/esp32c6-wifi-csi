"""Tests for analysis/ml_classifier.py: features and the exported C decision tree."""
import shutil
import subprocess

import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier

from ml_classifier import FEATS, tree_to_c, window_features


def test_window_features_length_and_band_energies():
    fs = 100.0
    t = np.arange(100) / fs
    W = 1 + 0.1 * np.sin(2 * np.pi * 2.0 * t)[:, None] * np.ones((1, 8))   # 2 Hz motion
    f = window_features(W, fs)
    assert len(f) == len(FEATS)
    bands = dict(zip(FEATS, f))
    assert bands["E_1-3Hz"] > 0.9                                     # energy in the 1-3 Hz band
    assert bands["E_0.3-1Hz"] < 0.05 and bands["E_3-8Hz"] < 0.05


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
