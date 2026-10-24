"""Tests for analysis/link_check.py, replaying a real receiver capture through a fake serial port."""
import subprocess
import sys
import textwrap

import pytest

FAKE_SERIAL = textwrap.dedent("""
    import os

    class Serial:
        def __init__(self, *args, **kwargs):
            with open(os.environ["FAKE_SERIAL_DATA"], "rb") as f:
                self._data = f.read()
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def reset_input_buffer(self):
            pass
        def read(self, n):
            chunk, self._data = self._data[:n], self._data[n:]
            return chunk
""")


@pytest.fixture
def run_link_check(tmp_path, analysis_dir):
    (tmp_path / "serial.py").write_text(FAKE_SERIAL)

    def run(stream: bytes):
        data = tmp_path / "stream.bin"
        data.write_bytes(stream)
        env = {"PYTHONPATH": str(tmp_path), "FAKE_SERIAL_DATA": str(data), "PATH": ""}
        return subprocess.run([sys.executable, str(analysis_dir / "link_check.py"), "-p", "fake", "-d", "0.3"],
                              capture_output=True, text=True, env=env)
    return run


def raw_lines(capture):
    return [ln.split(";", 1)[1] for ln in capture.read_text().splitlines()]


def test_reports_loss_from_sender_sequence(run_link_check, c6_capture):
    lines = raw_lines(c6_capture)
    seq = [int(ln.split(",")[1]) for ln in lines]
    expected = seq[-1] - seq[0] + 1

    res = run_link_check(("I (100) boot: noise before the stream\n" + "\n".join(lines) + "\n").encode())

    assert res.returncode == 0, res.stderr
    assert f"{len(lines)} received / {expected} sent" in res.stdout
    assert "RSSI    : min" in res.stdout


def test_handles_sender_reset(run_link_check, c6_capture):
    lines = raw_lines(c6_capture)[:10]
    restarted = [ln.replace(f",{ln.split(',')[1]},", f",{i},", 1) for i, ln in enumerate(lines)]

    res = run_link_check(("\n".join(lines + restarted) + "\n").encode())

    assert res.returncode == 0, res.stderr
    assert "1 sender resets" in res.stdout


def test_fails_cleanly_without_csi(run_link_check):
    res = run_link_check(b"I (100) boot: no CSI here\n")
    assert res.returncode != 0
    assert "Not enough CSI lines" in res.stderr
