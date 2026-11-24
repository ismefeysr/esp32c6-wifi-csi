"""Tests for analysis/live_detector.py: packet parsing and the crossing state machine."""
import numpy as np

from live_detector import CrossingDetector, parse_packet, replay_source

FS = 87.0


def test_parse_packet_reads_rssi_and_amplitudes(c6_capture):
    raw = c6_capture.open().readline().strip().split(";", 1)[1]
    rssi, amp = parse_packet(raw)
    assert rssi == -62
    assert amp.ndim == 1 and len(amp) > 50 and (amp >= 0).all()
    assert parse_packet("not a csi line") is None


def feed(det, seconds, rssi, rng, t0, motion=0.0):
    """Push `seconds` of synthetic packets; returns (last time, list of states)."""
    states, n_sub = [], 52
    base = 20 + 5 * np.linspace(0, 1, n_sub)
    n = int(seconds * FS)
    for i in range(n):
        t = t0 + i / FS
        wave = motion * np.sin(2 * np.pi * 1.5 * t) * np.sin(np.linspace(0, 3 * np.pi, n_sub))
        det.push(t, rssi + rng.choice([0, 0, 0, -1]), base + wave + rng.normal(0, 0.2, n_sub))
        if i % 8 == 0:
            st = det.update()
            if st is not None:
                states.append(st)
    return t0 + n / FS, states


def test_calibrates_then_counts_one_passage_per_rssi_dip():
    rng = np.random.default_rng(0)
    det = CrossingDetector(cal_seconds=5)
    t, cal = feed(det, 6, -65, rng, 0.0)
    assert cal[0]["phase"] == "calibrating" and cal[-1]["phase"] == "detecting"
    t, quiet = feed(det, 5, -65, rng, t)
    assert not any(s["crossing"] for s in quiet)
    for _ in range(3):                                   # three separate crossings
        t, dip = feed(det, 1.0, -75, rng, t)
        assert any(s["crossing"] for s in dip)
        t, after = feed(det, 3, -65, rng, t)
        assert not after[-1]["crossing"]                 # back to CLEAR after the hold time
    assert after[-1]["passages"] == 3


def test_slow_rssi_shift_is_not_a_passage():
    # Someone standing next to the link lowers the RSSI by a few dB for a long time: the rolling
    # baseline follows it, so only the first second could look like a dip, and 3 dB is below k_rssi.
    rng = np.random.default_rng(2)
    det = CrossingDetector(cal_seconds=5)
    t, _ = feed(det, 6, -65, rng, 0.0)
    t, standing = feed(det, 10, -68, rng, t)
    assert standing[-1]["passages"] == 0 and not standing[-1]["crossing"]
    t, dip = feed(det, 0.6, -76, rng, t)                  # then a crossing on top of the shifted level
    assert dip[-1]["passages"] == 1


def test_motion_index_only_counts_with_use_motion():
    rng = np.random.default_rng(1)
    for use_motion in (True, False):
        det = CrossingDetector(cal_seconds=5, use_motion=use_motion)
        t, _ = feed(det, 6, -65, rng, 0.0)
        _, moving = feed(det, 3, -65, rng, t, motion=3.0)    # strong multipath change, no RSSI drop
        assert any(s["crossing"] for s in moving) is use_motion


def test_replay_concatenates_files_on_one_time_axis(c6_capture, tmp_path):
    second = tmp_path / "b.csv"
    second.write_text(c6_capture.read_text())
    ts = [t for t, _ in replay_source([c6_capture, second], speed=1e6)]
    assert len(ts) == 80
    assert all(b > a for a, b in zip(ts, ts[1:]))


def test_ui_page_is_served_with_a_query_string():
    import threading, urllib.request
    from http.server import ThreadingHTTPServer
    from live_detector import Hub, make_handler
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Hub(), "<html>ok</html>"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/?lang=tr"
        assert urllib.request.urlopen(url, timeout=5).read() == b"<html>ok</html>"
    finally:
        server.shutdown()
