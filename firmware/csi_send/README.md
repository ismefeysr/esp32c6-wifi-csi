# csi_send — ESP-NOW CSI sender

Firmware for the **transmitting** ESP32-C6. It continuously broadcasts small ESP-NOW frames so that the receiver (`../csi_recv`) can estimate the Channel State Information of every frame.

## Behaviour

| Setting | Value |
|---|---|
| Transport | ESP-NOW broadcast (`ff:ff:ff:ff:ff:ff`), no router |
| Channel / bandwidth | 11, HT40 (secondary channel below) |
| PHY rate | MCS0, long guard interval |
| Frame rate | 100 frames/s |
| Payload | 32-bit sequence counter (used by the receiver to measure loss) |
| Station MAC | `1a:00:00:00:00:00` (fixed, the receiver filters on it) |
| Status LED | onboard RGB LED lights **green** at boot |

The sender only needs power; it can run from a USB charger or power bank.

## Build and flash

```bash
. ~/esp/esp-idf/export.sh          # ESP-IDF v5.5
idf.py set-target esp32c6
idf.py build flash -p <SENDER_PORT> monitor
```

Expected boot log:

```
csi_send: ================ CSI SEND ================
csi_send: wifi_channel: 11, send_frequency: 100, mac: 1a:00:00:00:00:00
```

## Origin

Derived from the `get-started/csi_send` example of [Espressif esp-csi](https://github.com/espressif/esp-csi) (Apache-2.0). Project changes: status LED (shared `../components/status_led`) and project-specific documentation.
