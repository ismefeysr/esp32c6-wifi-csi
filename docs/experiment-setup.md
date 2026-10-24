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

Planned: s2 and s3 at different times of day with the same setup.
