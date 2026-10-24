"""End-to-end smoke test: synthetic data -> baseline -> classifier, run as the CLI scripts."""
import subprocess
import sys

import pytest


@pytest.fixture(scope="module")
def synthetic_dir(tmp_path_factory, analysis_dir):
    d = tmp_path_factory.mktemp("pipeline")
    subprocess.run([sys.executable, str(analysis_dir / "make_fake_data.py")], cwd=d, check=True,
                   capture_output=True)
    return d


def run(script, args, cwd, analysis_dir):
    res = subprocess.run([sys.executable, str(analysis_dir / script), *args], cwd=cwd,
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return res.stdout


def test_generator_writes_receiver_format(synthetic_dir):
    files = sorted(p.name for p in (synthetic_dir / "data_fake").glob("*.csv"))
    assert len(files) == 9
    first = (synthetic_dir / "data_fake" / "empty_s1.csv").open().readline()
    fields = first.split(";", 1)[1].split(",", 14)
    assert fields[0] == "CSI_DATA" and fields[2] == "1a:00:00:00:00:00" and fields[12] == "256"


def test_baseline_runs(synthetic_dir, analysis_dir):
    out = run("baseline.py", ["--calib", "data_fake/empty_s1.csv", "--test", "data_fake/*_s2.csv",
                              "--win", "100", "--step", "50"], synthetic_dir, analysis_dir)
    assert "False alarm rate" in out and "Motion detection rate" in out


def test_classifier_two_classes_and_c_export(synthetic_dir, analysis_dir):
    two = synthetic_dir / "two"
    two.mkdir(exist_ok=True)
    for p in (synthetic_dir / "data_fake").glob("*.csv"):
        if not p.name.startswith("static"):
            (two / p.name).write_text(p.read_text())

    out = run("ml_classifier.py", ["--data", "two/*_s*.csv", "--test-sessions", "s3",
                                   "--win", "100", "--step", "50", "--export-c", "tree.h"],
              synthetic_dir, analysis_dir)

    assert "order ['empty', 'walk']" in out          # absent classes are not reported
    assert "static" not in out.split("C output written")[0]
    assert "csi_tree_predict" in (synthetic_dir / "tree.h").read_text()
