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
| s3 | 2026-11-24 21:28 | empty | `data/empty_s3.csv` | 9 451 | 110 s | Evening; 85.8 Hz, loss 5.6 %, largest gap 3 pkt; first 10 s trimmed (see notes) |
| s3 | 2026-11-24 21:31 | walk | `data/walk_s3.csv` | 10 358 | 120 s | Evening; 86.3 Hz, loss 5.0 %, largest gap 3 pkt |
| s4 | 2026-11-24 22:02 | empty | `data/empty_s4.csv` | 10 443 | 120 s | `h110d180`; 87.0 Hz, loss 4.3 %, largest gap 3 pkt |
| s4 | 2026-11-24 22:05 | walk | `data/walk_s4.csv` | 10 319 | 120 s | `h110d180`; 86.0 Hz, loss 5.4 %, largest gap 4 pkt |

Per-recording statistics are also appended to `data/sessions.jsonl` by `record_session.py`.

### Rejected recordings

| File | Reason |
|---|---|
| `data/rejected/empty_s2_mac_sleep.csv` | Host laptop idle-slept after ~90 s (on battery); no packets for 118 s. Recordings now run under `caffeinate`. |
| `data/rejected/link_s4_aborted.log` | First s4 attempt: link check loss 6.2 % (> 5 %, RSSI -65 dBm, largest gap 2 pkt) made the recorder abort before any recording. Re-run unchanged and continued at 6.3 %. |

### Notes

- **Amplitude scale differs between sessions.** The receiver multiplies the CSI by a gain
  compensation factor derived from the first 100 packets after boot. In s1 the values carry a
  roughly x10 factor (max |v| 216, most values multiples of 10); in s2 they are raw int8 (max |v| 23).
  The per-packet normalisation in `preprocess` removes a constant scale. To keep sessions comparable,
  reset the receiver in place (boards at their marks, sender already running) before each session.
- s2 link check (person in the room): 85.9 Hz, loss 5.5 %, median RSSI -69 dBm (s1: -65 dBm).
- s3: receiver reset in place before the session; afterwards max |v| was 60 (not multiples of 10), so the gain
  compensation factor differs again from s1 and s2. Link check: 87.3 Hz, loss 3.9 %, median RSSI -63 dBm.
- s3 empty: the recording started before the room was empty; leaving shows as a burst at 4-6 s. The first 10 s were
  cut; the untrimmed file is kept in `data/untrimmed/empty_s3.csv`.
- s3 walk: the crossings are visible as peaks every ~4-5 s, but much weaker than in s2 (mean per-subcarrier std of
  the normalised amplitude: s1 1.9x, s2 4.6x, s3 1.3x the empty level). The baseline empty level is also higher
  (0.05 vs 0.03 in s2). Same marks and condition, so this is session-to-session variation the classifier has to handle.

## Planned sessions

Sessions are grouped by placement (`condition` in `data/sessions.jsonl`). Each condition gets at least
two sessions so that it can be held out for testing; between two sessions of the same condition the
boards are lifted, placed again and the receiver is reset.

| Condition | Distance | Board height | Sessions |
|---|---|---|---|
| `home2m` | ~2 m | ~1 m | s1, s2, s3 |
| `h110d180` | ~1.8 m | ~1.1 m (closest achievable to `torso` in the room) | s4, s5 |
| `torso` | ~1 m | ~1.1 m (chest/waist, as in the live demo) | later (demo rehearsal) |
| `leg` | ~1 m | ~0.45 m (on chairs) | s6, s7 |

`h110d180` was added because a 1 m link at 1.1 m height cannot be set up in the room. It differs from `home2m`
mainly in height, so it shows the effect of raising the boards; `torso` stays reserved for the demo distance.

The live demo uses ~1 m with the boards held by two people at chest/waist height, chips facing each other.
