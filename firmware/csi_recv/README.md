# csi_recv — CSI receiver

Firmware for the **receiving** ESP32-C6. It listens for the frames broadcast by `../csi_send`, captures the Channel State Information of each frame and streams it to the host over UART.

## Behaviour

| Setting | Value |
|---|---|
| Channel / bandwidth | 11, HT40 (must match the sender) |
| Frame filter | only frames from the sender MAC `1a:00:00:00:00:00` |
| CSI | 128 subcarriers per frame (256 signed values, imag/real interleaved) |
| Gain handling | AGC/FFT gain compensation via `esp_csi_gain_ctrl` |
| Console | UART0 (TX GPIO16 / RX GPIO17), **2 000 000 baud** |
| Status LED | onboard RGB LED lights **blue** at boot |

> Connect the receiver through the board's **UART** USB-C port. The CSI stream is printed on the UART console and does not appear on the native USB-Serial/JTAG port.

## Output format

One CSV line per received frame. A header line is printed before the first frame:

```
type,seq,mac,rssi,rate,noise_floor,fft_gain,agc_gain,channel,local_timestamp,sig_len,rx_format,len,first_word,data
CSI_DATA,23422,1a:00:00:00:00:00,-62,11,-97,22,46,11,143248031,47,2,256,0,"[0,0,...,-109,-10,...]"
```

- `seq`: the sender's sequence counter, so gaps mean lost frames
- `local_timestamp`: receiver time in µs
- `data`: 256 values; subcarriers 0–5, 63–65 and 123–127 are null/guard carriers and are always zero

The host tools in [`../../analysis`](../../analysis) parse this format directly.

## Build and flash

```bash
. ~/esp/esp-idf/export.sh          # ESP-IDF v5.5
idf.py set-target esp32c6
idf.py build flash -p <RECEIVER_PORT> monitor
```

## Origin

Derived from the `get-started/csi_recv` example of [Espressif esp-csi](https://github.com/espressif/esp-csi) (Apache-2.0). Project changes: 2 Mbaud console, per-frame gain log demoted to DEBUG, status LED (shared `../components/status_led`) and project-specific documentation.
