# Analysis toolkit

Host-side Python tools for the router-less ESP32-C6 CSI sensing link: link quality checks, labelled data collection, preprocessing, a threshold baseline and a lightweight ML classifier.

| Script | Purpose | Work package |
|---|---|---|
| `link_check.py` | Measure packet rate, loss, RSSI/SNR and serial line utilisation; diagnose the cause of loss | WP1 |
| `log_csi.py` | Record labelled CSI sessions from the receiver to `data/<label>_<session>.csv` | WP2 |
| `record_session.py` | Record a whole session (link check, empty, walk) in one run, with sound cues and a quality report | WP2 |
| `csi_common.py` | Shared helpers: log parsing, amplitude extraction, Hampel filtering, normalisation, windowing | – |
| `baseline.py` | Threshold detector calibrated on empty-room recordings | WP2 |
| `ml_classifier.py` | Feature extraction, decision tree / random forest with session-based split, C export | WP3 |
| `live_detector.py` + `live_ui.html` | Live crossing detector with a browser UI (CROSSING / CLEAR, passage counter, RSSI and score traces); also replays recorded files | WP4 prototype |
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

For a whole session in one run (link check → `empty` → `walk`, with sounds at the start and end of each recording and a quality report), use:

```bash
python record_session.py -s s2 --note "evening, door closed"   # port auto-detected
```

It writes `data/link_s2.log`, `data/empty_s2.csv`, `data/walk_s2.csv` and appends one line per recording (start time, packet rate, sequence loss, largest gap, note) to `data/sessions.jsonl`.

- File names must follow `<label>_sN.csv`. Supported labels: `empty`, `static`, `walk`.
- Collect **at least three sessions**: training and test sets are always taken from different sessions.
- Existing recordings are never overwritten.

## 3. Baseline and ML (WP2–WP3)

```bash
python baseline.py --calib data/empty_s1.csv --k 4 --test "data/*_s2.csv" --win 100 --step 50
python ml_classifier.py --loso                                     # hold out each session in turn
python ml_classifier.py --test-sessions s3 --export-c tree_model.h
```

- Defaults: `--win 100 --step 25` (~1.15 s windows at ~87 packets/s), decision tree depth 4.
- Features are computed per subcarrier and then pooled. `preprocess` divides each packet by its subcarrier mean, so a mean over subcarriers carries no information.
- Empty-room calibration: the first `--cal-seconds` (default 30) of each session's `empty` recording are the reference, and every feature of that session is scaled as (value − median) / IQR of the reference. These windows are never tested on. Every session therefore needs an `empty_sN.csv`; `--cal-seconds 0` turns calibration off.
- Reports only include the classes present in the data, e.g. `empty` and `walk`.
- `--export-c` writes the decision tree as a dependency-free C function for on-device inference (WP4). Class indices are fixed: `0=empty`, `1=static`, `2=walk`.

## Live crossing detector

```bash
python live_detector.py --save ../data/live_test.log      # receiver auto-detected; open http://localhost:8000
python live_detector.py --replay ../data/empty_s4.csv ../data/walk_s4.csv     # recorded files, real time
```

- A body crossing the link blocks the direct path for ~0.5 s: the RSSI dips sharply by 5–8 dB. Someone standing
  next to the link only lowers it slowly by 3–4 dB. The detector therefore compares the mean RSSI of the last
  ~0.17 s with a rolling baseline (median of 3.5 s to 0.5 s ago) and counts a passage when the dip reaches
  `--k-rssi` dB (default 5). One crossing often breaks into two dips ~1.5–2 s apart, so no new passage is counted
  for `--refractory` seconds (default 2.2); two real crossings closer than that count as one.
- The first `--cal` seconds (default 10) are a warm-up: nobody crosses the link.
- `--use-motion` also scores the subcarrier motion index; it reacts to any movement near the link and is off by default.
- `http://localhost:8000/?lang=tr` shows the UI in Turkish. `--save file.log` also records the stream.

Checks so far (2026-11-24):

| Data | Passages counted | Expected |
|---|---|---|
| Live test 1 (`data/live_test1.log`, boards 1.8 m apart at 1.1 m, person in the room during warm-up) | 11 | 11 crossings, counted by the walker |
| Live test 2 (`data/live_test2.log`, same placement, a second person standing still in the room) | 11 | 10 |
| Empty-room recordings s1–s4 | 0, 0, 0, 0 | 0 |
| Walk recordings s1–s4 (120 s each) | 21, 23, 24, 24 | ~24–30 (crossing every ~4–5 s; exact times not recorded) |

The first version (fixed reference, 0.6 s median, 4 dB) counted 8 of the 11 crossings of live test 1. With a 1.2 s
refractory time live test 2 gave 14 instead of 10: single crossings split into two dips. The threshold, update rate
and refractory time were chosen on these two tests (21 crossings), so they still have to be confirmed on new data.

## 4. Dry run with synthetic data

```bash
python make_fake_data.py
python baseline.py --calib data_fake/empty_s1.csv --test "data_fake/*_s2.csv" --win 100 --step 50
python ml_classifier.py --data "data_fake/*_s*.csv" --loso
```

> **Synthetic results are not real results and are never reported.** The generator copies the receiver's line format, subcarrier layout and amplitude range from a real capture, but its motion model is invented.

## Validation status and known limitations

- **Firmware:** built and flashed on two ESP32-C6 boards; the CSI stream was verified end to end.
- **`link_check.py`:** tested against real receiver captures; it reproduced the expected diagnosis for both placements.
- **`csi_common.py`:** parses real ESP32-C6 output correctly (128 subcarriers, of which the 14 null/guard carriers are masked).
- **Baseline:** run on real data from sessions s1 and s2; cross-session results are in the [main README](../README.md#preliminary-results-threshold-baseline-across-sessions).
- **ML classifier:** so far only exercised end to end on synthetic data; it will be evaluated once session s3 is recorded.
- **Unit tests:** see [`tests/`](../tests).
