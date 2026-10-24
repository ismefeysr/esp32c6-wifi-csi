# Analysis toolkit

Host-side Python tools for the router-less ESP32-C6 CSI sensing link: link quality checks, labelled data collection, preprocessing, a threshold baseline and a lightweight ML classifier.

| Script | Purpose | Work package |
|---|---|---|
| `link_check.py` | Measure packet rate, loss, RSSI/SNR and serial line utilisation; diagnose the cause of loss | WP1 |
| `log_csi.py` | Record labelled CSI sessions from the receiver to `data/<label>_<session>.csv` | WP2 |
| `csi_common.py` | Shared helpers: log parsing, amplitude extraction, Hampel filtering, normalisation, windowing | – |
| `baseline.py` | Threshold detector calibrated on empty-room recordings | WP2 |
| `ml_classifier.py` | Feature extraction, decision tree / random forest with session-based split, C export | WP3 |
| `make_fake_data.py` | Synthetic data in the exact receiver format, for testing code without hardware | – |

## Setup

```bash
# from the repository root
python3 -m venv .venv
.venv/bin/pip install -r analysis/requirements.txt
source .venv/bin/activate
cd analysis
```

The receiver must be connected through its **UART** USB-C port (see [`firmware/csi_recv`](../firmware/csi_recv/README.md)). Close `idf.py monitor` before running any tool, since it keeps the serial port busy. The tools default to the receiver's 2 Mbaud console; use `-b` to override it.

## 1. Link check (WP1)

Verify that the link is healthy before collecting data:

```bash
python link_check.py -p <RECEIVER_PORT> -d 30 --save data/link_<place>.log
```

The tool reports the packet rate, the loss computed from the sender's sequence counter (robust to sender resets), RSSI/SNR and serial line utilisation. It then prints a diagnosis: healthy, serial bottleneck or weak signal. Target: **loss < 5 %**.

Measurements so far (24 October 2026, crowded environment, 921600 baud):

| Placement | Median RSSI | Rate | Loss | Diagnosis |
|---|---|---|---|---|
| Initial (far) | −90 dBm | 20 Hz | 78 % | weak signal |
| Close | −62 dBm | 79 Hz | 13.5 % | serial bottleneck (line ~99 % utilised) |

The console speed was then raised to 2 Mbaud; the link has not yet been re-measured at that rate.

## 2. Data collection (WP2)

```bash
python log_csi.py -p <RECEIVER_PORT> -l empty -s s1 -d 120   # empty room
python log_csi.py -p <RECEIVER_PORT> -l walk  -s s1 -d 120   # person walking through
# repeat as s2, s3, ... on different days / times / placements
```

- File names must follow `<label>_sN.csv`. Supported labels: `empty`, `static`, `walk`.
- Collect **at least three sessions**: training and test sets are always taken from different sessions.
- Existing recordings are never overwritten.

## 3. Baseline and ML (WP2–WP3)

```bash
python baseline.py --calib data/empty_s1.csv --k 4 --test "data/*_s2.csv" --win 100 --step 50
python ml_classifier.py --test-sessions s3 --win 100 --step 50 --export-c tree_model.h
```

- At ~100 packets/s, `--win 100` corresponds to a 1 s window. The window length should be chosen against real data.
- Reports only include the classes present in the data, e.g. `empty` and `walk`.
- `--export-c` writes the decision tree as a dependency-free C function for on-device inference (WP4). Class indices are fixed: `0=empty`, `1=static`, `2=walk`.

## 4. Dry run with synthetic data

```bash
python make_fake_data.py
python baseline.py --calib data_fake/empty_s1.csv --test "data_fake/*_s2.csv" --win 100 --step 50
python ml_classifier.py --data "data_fake/*_s*.csv" --test-sessions s3 --win 100 --step 50
```

> **Synthetic results are not real results and are never reported.** The generator copies the receiver's line format, subcarrier layout and amplitude range from a real capture, but its motion model is invented.

## Validation status and known limitations

- **Firmware:** built and flashed on two ESP32-C6 boards; the CSI stream was verified end to end.
- **`link_check.py`:** tested against real receiver captures; it reproduced the expected diagnosis for both placements.
- **`csi_common.py`:** parses real ESP32-C6 output correctly (128 subcarriers, of which the 14 null/guard carriers are masked).
- **Baseline and ML:** so far only exercised end to end on synthetic data. Accuracy on real data is expected to be lower, and that is a result worth reporting.
- **Unit tests:** see [`tests/`](../tests).
