# esp32c6-wifi-csi

[![CI](https://github.com/ismefeysr/esp32c6-wifi-csi/actions/workflows/ci.yml/badge.svg)](https://github.com/ismefeysr/esp32c6-wifi-csi/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![ESP-IDF v5.5](https://img.shields.io/badge/ESP--IDF-v5.5-red)
![Target: ESP32-C6](https://img.shields.io/badge/target-ESP32--C6-orange)

**Router-less human presence and motion detection using Wi-Fi Channel State Information (CSI) on two ESP32-C6 boards.**

This repository is my final project for the **Embedded Systems** course in Electrical and Electronics Engineering (EEE). I am completing it to pass the course.

---

## Motivation

When a person moves through a room, the way Wi-Fi signals bounce off walls, furniture and the human body changes. These changes show up in the **Channel State Information**: the per-subcarrier amplitude and phase that a Wi-Fi receiver estimates for every packet. By analysing how CSI changes over time, a system can tell whether a room is empty or whether someone is moving in it. No camera, wearable or extra sensor is needed.

Most CSI sensing setups rely on a Wi-Fi router. This project uses **no router**. One ESP32-C6 broadcasts ESP-NOW packets and a second ESP32-C6 captures the CSI of every packet it receives. The result is a small, cheap, self-contained sensing link that can be placed anywhere.

## Objectives

1. Build a stable router-less CSI link between two ESP32-C6 boards.
2. Collect labelled CSI datasets, starting with an **empty room** and a **person walking through**, across several independent sessions.
3. Implement a **threshold-based baseline detector** and a **lightweight machine-learning classifier**, then compare them under a session-based train/test split. This comparison is the core research question of the project.
4. Run the chosen detector on the receiver itself as an embedded FreeRTOS application. When a person passing through is detected, an **OLED display** connected to the receiver shows it, so the system works without a computer.
5. Evaluate the system experimentally and document the results in a final report.

## System overview

```
 ┌──────────────────┐   ESP-NOW broadcast    ┌──────────────────┐   UART (2 Mbaud)   ┌───────────────────┐
 │  ESP32-C6 #1     │   ch 11, HT40, 100 Hz  │  ESP32-C6 #2     │   CSI_DATA lines   │  Host (Python)    │
 │  csi_send        │ ─────────────────────► │  csi_recv        │ ─────────────────► │  logging, base-   │
 │  status LED: 🟢  │                        │  status LED: 🔵  │                    │  line, ML         │
 └──────────────────┘                        └──────────────────┘                    └───────────────────┘
```

- **Sender (`firmware/csi_send`)** broadcasts ESP-NOW frames at 100 packets/s on channel 11 (HT40). It carries a sequence counter so the receiver can measure packet loss.
- **Receiver (`firmware/csi_recv`)** captures the CSI of each frame (128 subcarriers) and streams it over UART as CSV lines.
- **Host tools (`analysis/`)** handle link quality checks, labelled data logging, preprocessing, the baseline detector and the ML classifier. The ML classifier can export a decision tree as C code for on-device inference.
- **Planned: OLED display on the receiver.** Once the detector runs on the ESP32-C6, the receiver will show the detection result ("empty" / "person passing") on an OLED screen in real time.

The onboard RGB LED identifies each board at a glance: **green = sender**, **blue = receiver**.

## Hardware and software

| Item | Details |
|---|---|
| Boards | 2 × ESP32-C6 development board |
| Display (planned) | OLED module on the receiver for showing detections |
| Framework | ESP-IDF v5.5 (target `esp32c6`) |
| CSI stack | [Espressif esp-csi](https://github.com/espressif/esp-csi) (git submodule) |
| Host | Python 3.10+, numpy, scipy, scikit-learn, pyserial |

## Repository structure

```
.
├── firmware/
│   ├── csi_send/            # sender application (ESP-NOW broadcaster)
│   ├── csi_recv/            # receiver application (CSI capture + UART output)
│   └── components/
│       └── status_led/      # shared onboard RGB LED driver (board identification)
├── analysis/                # Python tools: link check, logging, baseline, ML (see analysis/README.md)
├── tests/                   # pytest suite, incl. a fixture captured from the real receiver
├── docs/                    # experiment setup and recording log
├── external/esp-csi/        # Espressif esp-csi, used as an unmodified upstream reference
├── .github/workflows/       # CI: Python tests + firmware builds for esp32c6
└── data/                    # recorded datasets, created locally (not tracked in git)
```

## Getting started

```bash
# 1. Clone with the esp-csi submodule
git clone --recursive https://github.com/ismefeysr/esp32c6-wifi-csi.git
cd esp32c6-wifi-csi

# 2. Build and flash both boards (ESP-IDF v5.5 must be installed)
. ~/esp/esp-idf/export.sh
cd firmware/csi_send && idf.py set-target esp32c6 build flash -p <SENDER_PORT>  && cd ../..
cd firmware/csi_recv && idf.py set-target esp32c6 build flash -p <RECEIVER_PORT> && cd ../..

# 3. Set up the Python environment and run the tests
python3 -m venv .venv
.venv/bin/pip install -r analysis/requirements-dev.txt
.venv/bin/python -m pytest

# 4. Verify the link (receiver connected through its UART USB-C port)
.venv/bin/python analysis/link_check.py -p <RECEIVER_PORT> -d 30
```

Data collection, the baseline detector and the ML classifier are documented in [`analysis/README.md`](analysis/README.md).

## Project status

| Work package | Description | Status |
|---|---|---|
| WP1 | Router-less CSI link | ✅ Done: 3.1 % loss, −65 dBm in a quiet room at 2 Mbaud |
| WP2 | Baseline detector and data collection | 🔄 Sessions 1 and 2 recorded (empty + walk); session 3 next |
| WP3 | Machine-learning classifier | 🔄 Pipeline ready; trained and evaluated once session 3 is recorded |
| WP4 | On-device detection (FreeRTOS) with an OLED display showing detected passages | ⏳ Planned |
| WP5 | Experiments and final report | ⏳ Planned |

### Measurements so far

First link test (24 October 2026, crowded and noisy environment, receiver at 921600 baud):

| Placement | Median RSSI | Packet rate | Loss | Diagnosis |
|---|---|---|---|---|
| Initial (far) | −90 dBm | 20 Hz | 78 % | weak signal |
| Close | −62 dBm | 79 Hz | 13.5 % | serial bottleneck (line ~99 % utilised) |

To remove the serial bottleneck, the receiver's console speed was then raised to 2 Mbaud.

Link test at 2 Mbaud (24 October 2026, quiet 5 m × 3 m room, boards 2 m apart at ~1 m height, facing each other):

| Placement | Median RSSI | Packet rate | Loss | Diagnosis |
|---|---|---|---|---|
| Boards lying flat, person in the room | −74 dBm | 85 Hz | 6.4 % | no clear cause |
| Boards upright, room empty | −65 dBm | 88 Hz | 3.1 % | link is healthy (serial line 45 % utilised) |

Standing the boards upright made the biggest difference. The full setup and the recording log are in [`docs/experiment-setup.md`](docs/experiment-setup.md).

### Recorded sessions

Each session has one 120 s recording per label, taken with the same board placement (positions marked with tape). Statistics come from `log_quality()` in `analysis/csi_common.py`; loss is computed from the sender's sequence counter.

| Session | Date | Label | Packets | Rate | Loss | Largest gap |
|---|---|---|---|---|---|---|
| s1 | 2026-10-24 | empty | 10 437 | 87.0 Hz | 4.3 % | 5 packets |
| s1 | 2026-10-24 | walk | 10 571 | 88.1 Hz | 3.1 % | 2 packets |
| s2 | 2026-11-23, evening | empty | 10 121 | 84.4 Hz | 7.2 % | 5 packets |
| s2 | 2026-11-23, evening | walk | 10 133 | 84.5 Hz | 7.1 % | 6 packets |

One s2 recording was rejected because the host laptop went to sleep mid-recording; recordings now run under `caffeinate`. Details are in [`docs/experiment-setup.md`](docs/experiment-setup.md).

### Preliminary results: threshold baseline across sessions

The baseline is calibrated on the empty-room recording of one session and tested on the other session (1 s windows: `--win 100 --step 50`). A window is flagged as motion when its motion index exceeds mean + k·std of the calibration windows.

| Calibrated on → tested on | k | False alarms (empty) | Detection (walk) |
|---|---|---|---|
| s1 → s2 | 3 | 9.0 % | 100 % |
| s1 → s2 | 5 | 6.0 % | 100 % |
| s1 → s2 | 10 | 1.0 % | 100 % |
| s2 → s1 | 3 | 0.0 % | 51.9 % |
| s2 → s1 | 5 | 0.0 % | 34.8 % |
| s2 → s1 | 10 | 0.0 % | 21.9 % |

**What this shows so far:** a threshold calibrated in one session does not transfer cleanly to another. The motion index of the empty room differs between sessions (median 1.30e-3 in s1, 8.1e-4 in s2, with occasional spikes in s2), and walking produced a much stronger response in s2 than in s1. A threshold set on s1 therefore gives false alarms on s2, while a threshold set on s2 misses about half of the walking windows in s1. This is the motivation for the ML classifier and for session-based evaluation.

These numbers come from two sessions only and are not final. The full comparison of the baseline and the ML classifier will use three or more sessions.

## Methodology principles

- **No fabricated results.** Every reported number comes from real measurements on the hardware.
- **Synthetic data is for testing code only.** `analysis/make_fake_data.py` generates data in the exact receiver format so the pipeline can be tested without hardware. Its output is never used in reported results.
- **Session-based evaluation.** Training and test data come from different recording sessions, which prevents optimistic results caused by data leakage.
- **Upstream stays untouched.** `external/esp-csi` is not modified. All project changes live in `firmware/` and `analysis/`.

## Testing and CI

The pytest suite (31 tests) runs without hardware. Parsing tests use a fixture of 40 packets captured from the real receiver (`tests/fixtures/c6_capture.csv`); end-to-end tests use synthetic data in the same format.

| Test file | What it covers |
|---|---|
| `tests/test_csi_common.py` | CSI line parsing (incl. truncated serial lines), amplitude extraction, null/guard carrier masking, Hampel filter and normalisation, windowing, motion index, file naming, sequence-based loss with sender resets, recording quality summary |
| `tests/test_link_check.py` | Loss from the sender's sequence counter, sender reset handling, clean failure without CSI lines |
| `tests/test_ml_classifier.py` | Window feature vector, and a check that the exported C decision tree, compiled with `cc`, predicts exactly like scikit-learn |
| `tests/test_pipeline.py` | Synthetic data generator, baseline run, two-class classifier with C export |

```bash
.venv/bin/python -m pytest        # from the repository root
```

Every push runs [GitHub Actions](.github/workflows/ci.yml):

- **Python tests** on Python 3.10 and 3.12.
- **Firmware builds**: both applications are built for `esp32c6` with ESP-IDF v5.5.

## Contributing

Issues and suggestions are welcome. See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for the development setup and pull request guidelines, and the [Code of Conduct](.github/CODE_OF_CONDUCT.md). Security issues should be reported privately as described in [SECURITY.md](.github/SECURITY.md).

## License

This project is released under the [MIT License](LICENSE). The firmware in `firmware/` is derived from the get-started examples of [Espressif esp-csi](https://github.com/espressif/esp-csi) and keeps its Apache-2.0 license headers; see [LICENSE](LICENSE) for details.
