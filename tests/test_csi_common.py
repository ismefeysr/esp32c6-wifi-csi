"""Unit tests for analysis/csi_common.py against a real ESP32-C6 receiver capture."""
import numpy as np
import pytest

from csi_common import file_meta, load_log, motion_index, parse_line, preprocess, windows

# Null/guard subcarriers reported by the ESP32-C6 in HT40 mode
C6_NULL_CARRIERS = list(range(0, 6)) + [63, 64, 65] + list(range(123, 128))


def test_parse_line_returns_all_values(c6_capture):
    raw = c6_capture.read_text().splitlines()[0].split(";", 1)[1]
    vals = parse_line(raw)
    assert vals is not None
    assert vals.dtype == np.int16
    assert len(vals) == 256                       # 128 subcarriers x (imag, real)


@pytest.mark.parametrize("line", ["", "garbage", "CSI_DATA,1,2,3", 'CSI_DATA,1,"[1,2,"'])
def test_parse_line_rejects_invalid_input(line):
    assert parse_line(line) is None


def test_load_log_shape_and_timestamps(c6_capture):
    t, A = load_log(c6_capture)
    assert A.shape == (40, 128)
    assert np.all(np.diff(t) > 0)
    assert np.all(A >= 0)                         # amplitudes


def test_load_log_identifies_null_carriers(c6_capture):
    _, A = load_log(c6_capture)
    null = np.where(A.std(axis=0) == 0)[0].tolist()
    assert null == C6_NULL_CARRIERS


def test_load_log_rejects_file_without_csi(tmp_path):
    p = tmp_path / "empty_s1.csv"
    p.write_text("1.0;I (123) boot: hello\n")
    with pytest.raises(ValueError):
        load_log(p)


def test_load_log_skips_truncated_serial_lines(tmp_path, c6_capture):
    lines = c6_capture.read_text().splitlines()[:5]
    truncated = "9.9;CSI_DATA,23500,1a:00:00:00:00:00,-62"   # serial line cut mid-way
    p = tmp_path / "empty_s1.csv"
    p.write_text("\n".join(lines[:2] + [truncated] + lines[2:]) + "\n")
    _, A = load_log(p)
    assert A.shape == (5, 128)


def test_load_log_keeps_most_common_packet_length(tmp_path):
    p = tmp_path / "mixed_s1.csv"
    p.write_text('1.0;CSI_DATA,0,"[1,2,3,4,5,6,7,8]"\n'
                 '2.0;CSI_DATA,1,"[1,2,3,4,5,6,7,8]"\n'
                 '3.0;CSI_DATA,2,"[1,2,3,4,5,6,7,8,9,10]"\n')
    t, A = load_log(p)
    assert A.shape == (2, 4)
    assert t.tolist() == [1.0, 2.0]


def test_preprocess_masks_null_carriers_and_normalises(c6_capture):
    _, A = load_log(c6_capture)
    Ap, mask = preprocess(A)
    assert Ap.shape == (40, 128 - len(C6_NULL_CARRIERS))
    assert not mask[C6_NULL_CARRIERS].any()
    assert np.isfinite(Ap).all()
    np.testing.assert_allclose(Ap.mean(axis=1), 1.0, rtol=1e-9)   # per-packet normalisation


def test_preprocess_reuses_given_mask(c6_capture):
    _, A = load_log(c6_capture)
    _, mask = preprocess(A)
    Ap, mask2 = preprocess(A, mask=mask)
    assert mask2 is mask
    assert Ap.shape[1] == mask.sum()


def test_windows_cover_signal_without_overflow():
    assert list(windows(10, 4, 3)) == [(0, 4), (3, 7), (6, 10)]
    assert list(windows(3, 4, 1)) == []


def test_motion_index_separates_still_and_moving_signal():
    rng = np.random.default_rng(0)
    still = 1 + 0.001 * rng.standard_normal((200, 10))
    moving = 1 + 0.1 * rng.standard_normal((200, 10))
    assert motion_index(moving, 50, 25).min() > motion_index(still, 50, 25).max()
    assert len(motion_index(still, 50, 25)) == 7


@pytest.mark.parametrize("name,expected", [("walk_s2.csv", ("walk", "s2")),
                                           ("data/Empty_s10.csv", ("empty", "s10"))])
def test_file_meta_parses_label_and_session(name, expected):
    assert file_meta(name) == expected


@pytest.mark.parametrize("name", ["walk.csv", "walk_2.csv", "walk_s2.log"])
def test_file_meta_rejects_bad_names(name):
    with pytest.raises(ValueError):
        file_meta(name)
