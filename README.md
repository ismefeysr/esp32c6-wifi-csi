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
| Host | Python 3.9+, numpy, scipy, scikit-learn, pyserial |

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
| WP1 | Router-less CSI link | ✅ Link established; 🔄 final quality measurement in a quiet room |
| WP2 | Baseline detector and data collection | 🔄 Tools ready, real data collection next |
| WP3 | Machine-learning classifier | 🔄 Pipeline ready, awaiting real data |
| WP4 | On-device detection (FreeRTOS) with an OLED display showing detected passages | ⏳ Planned |
| WP5 | Experiments and final report | ⏳ Planned |

### Measurements so far

First link test (24 October 2026, crowded and noisy environment, receiver at 921600 baud):

| Placement | Median RSSI | Packet rate | Loss | Diagnosis |
|---|---|---|---|---|
| Initial (far) | −90 dBm | 20 Hz | 78 % | weak signal |
| Close | −62 dBm | 79 Hz | 13.5 % | serial bottleneck (line ~99 % utilised) |

To remove the serial bottleneck, the receiver's console speed was then raised to 2 Mbaud. Link quality at the new rate has not been measured yet.

## Methodology principles

- **No fabricated results.** Every reported number comes from real measurements on the hardware.
- **Synthetic data is for testing code only.** `analysis/make_fake_data.py` generates data in the exact receiver format so the pipeline can be tested without hardware. Its output is never used in reported results.
- **Session-based evaluation.** Training and test data come from different recording sessions, which prevents optimistic results caused by data leakage.
- **Upstream stays untouched.** `external/esp-csi` is not modified. All project changes live in `firmware/` and `analysis/`.

## Testing and CI

Every push runs [GitHub Actions](.github/workflows/ci.yml):

- **Python tests** (Python 3.9 and 3.12): parsing and preprocessing against a capture from the real receiver, link-loss computation, an end-to-end pipeline run, and a check that the exported C decision tree, compiled with `cc`, predicts exactly like scikit-learn.
- **Firmware builds**: both applications are built for `esp32c6` with ESP-IDF v5.5.

## License

This project is released under the [MIT License](LICENSE). The firmware in `firmware/` is derived from the get-started examples of [Espressif esp-csi](https://github.com/espressif/esp-csi) and keeps its Apache-2.0 license headers; see [LICENSE](LICENSE) for details.
