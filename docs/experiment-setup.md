# Experiment setup and recording log

Raw recordings live in `data/` and are not tracked in git (see `.gitignore`).
This file records how they were taken so that every session can be reproduced.

## Setup

| Item | Value |
|---|---|
| Room | ~5 m x 3 m, home environment |
| Boards | 2x ESP32-C6 (sender: green LED, receiver: blue LED) |
| Link distance | ~2 m, line of sight |
| Height | ~1 m above the floor, both boards |
| Orientation | Boards standing upright, facing each other |
| Walking path | Perpendicular to the link, crossing its midpoint; turns ~1 m on either side |
| Receiver serial | 2 000 000 baud |
| Recording | `log_csi.py -d 120 --countdown 15` (room left during the countdown for `empty`) |

Board positions are marked with tape and kept fixed across sessions.

## Link check (2026-10-24)

`link_check.py -d 30`, room empty:

| Metric | Value |
|---|---|
| Packet loss | 3.1 % (largest gap 1 packet) |
| Packet rate | 88.1 Hz |
| RSSI (median) | -65 dBm, std 0.1 dB |
| SNR | ~31 dB |
| Serial utilisation | 45 % |

An earlier check with the boards lying flat and a person in the room gave
6.4 % loss and -74 dBm; standing the boards upright was the main improvement.

## Recordings

| Session | Date | Label | File | Packets | Duration | Notes |
|---|---|---|---|---|---|---|
| s1 | 2026-10-24 | empty | `data/empty_s1.csv` | 10 437 | 120 s | Room empty, door position fixed |
| s1 | 2026-10-24 | walk | `data/walk_s1.csv` | 10 571 | 120 s | Continuous walking along the path |
| s2 | 2026-11-23 22:03 | empty | `data/empty_s2.csv` | 10 121 | 120 s | Evening; 84.4 Hz, loss 7.2 %, largest gap 5 pkt |
| s2 | 2026-11-23 22:07 | walk | `data/walk_s2.csv` | 10 133 | 120 s | Evening; 84.5 Hz, loss 7.1 %, largest gap 6 pkt |

Per-recording statistics are also appended to `data/sessions.jsonl` by `record_session.py`.

### Rejected recordings

| File | Reason |
|---|---|
| `data/rejected/empty_s2_mac_sleep.csv` | Host laptop idle-slept after ~90 s (on battery); no packets for 118 s. Recordings now run under `caffeinate`. |

### Notes

- **Amplitude scale differs between sessions.** The receiver multiplies the CSI by a gain
  compensation factor derived from the first 100 packets after boot. In s1 the values carry a
  roughly x10 factor (max |v| 216, most values multiples of 10); in s2 they are raw int8 (max |v| 23).
  The per-packet normalisation in `preprocess` removes a constant scale. To keep sessions comparable,
  reset the receiver in place (boards at their marks, sender already running) before each session.
- s2 link check (person in the room): 85.9 Hz, loss 5.5 %, median RSSI -69 dBm (s1: -65 dBm).

## Planned sessions

Sessions are grouped by placement (`condition` in `data/sessions.jsonl`). Each condition gets at least
two sessions so that it can be held out for testing; between two sessions of the same condition the
boards are lifted, placed again and the receiver is reset.

| Condition | Distance | Board height | Sessions |
|---|---|---|---|
| `home2m` | ~2 m | ~1 m | s1, s2, s3 |
| `torso` | ~1 m | ~1.1 m (chest/waist, as in the live demo) | s4, s5 |
| `leg` | ~1 m | ~0.45 m (on chairs) | s6, s7 |

The live demo uses ~1 m with the boards held by two people at chest/waist height, chips facing each other.
