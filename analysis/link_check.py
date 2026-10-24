"""WP1 link check: listen to the receiver's CSI stream and report packet rate / loss / RSSI.

Usage:
  pip install -r requirements.txt
  python link_check.py -p /dev/cu.usbmodemXXXX               # 15 s measurement
  python link_check.py -p /dev/cu.usbmodemXXXX -d 60 --save data/link_home_empty.log

Loss is computed from the sender's packet counter (the seq field of each CSI_DATA line).
If the sender restarts during the measurement, the counter resets; each segment is
counted separately.
If serial line utilisation exceeds 90%, loss is most likely caused by the serial link (not RF).

Note: the port is busy while idf.py monitor is open; close the monitor first.
The receiver must be connected through the UART USB-C port (the console is on UART).
"""
import argparse, csv, io, statistics as st, time
import serial

# esp32c6 csi_recv header line:
# type,seq,mac,rssi,rate,noise_floor,fft_gain,agc_gain,channel,local_timestamp,...,data
SEQ, RSSI, NOISE = 1, 3, 5

ap = argparse.ArgumentParser()
ap.add_argument("-p", "--port", required=True)
ap.add_argument("-b", "--baud", type=int, default=2000000)
ap.add_argument("-d", "--duration", type=float, default=15)
ap.add_argument("--send-rate", type=float, default=100, help="sender rate (Hz)")
ap.add_argument("--save", help="write the raw serial output to this file")
a = ap.parse_args()

print(f"Measuring: {a.port} @ {a.baud} baud, {a.duration:.0f} s ...")
buf = b""
with serial.Serial(a.port, a.baud, timeout=0.2) as ser:
    ser.reset_input_buffer()
    t0 = time.time()
    while time.time() - t0 < a.duration:
        buf += ser.read(65536)
    elapsed = time.time() - t0

text = buf.decode("utf8", errors="replace")
if a.save:
    with open(a.save, "w", encoding="utf8") as f:
        f.write(text)

seq, rssi, noise = [], [], []
for ln in text.splitlines():
    ln = ln.strip()
    if not (ln.startswith("CSI_DATA,") and ln.endswith(']"')):    # drop partial lines
        continue
    try:
        row = next(csv.reader(io.StringIO(ln)))
        seq.append(int(row[SEQ])); rssi.append(int(row[RSSI])); noise.append(int(row[NOISE]))
    except (ValueError, IndexError):
        continue

if len(seq) < 2:
    raise SystemExit(f"Not enough CSI lines ({len(seq)}), {len(buf)} bytes received. "
                     "Is the sender running? Is the receiver on the UART port? Is the baud rate correct?")

# sender reset -> seq goes backwards; count segments separately
expected, gaps, resets = 0, [], 0
start = prev = seq[0]
for s in seq[1:]:
    if s <= prev:
        expected += prev - start + 1
        start, resets = s, resets + 1
    elif s - prev > 1:
        gaps.append(s - prev - 1)
    prev = s
expected += prev - start + 1

rate = len(seq) / elapsed
loss = 100 * (1 - len(seq) / expected)
line_util = 100 * len(buf) / elapsed / (a.baud / 10)          # 8N1: 10 bits per byte
nf = st.median(noise)

print(f"\nPackets : {len(seq)} received / {expected} sent, {rate:.1f} Hz (target {a.send_rate:.0f})")
print(f"Loss    : {loss:.1f}%  ({len(gaps)} gaps, largest {max(gaps, default=0)} packets"
      + (f", {resets} sender resets" if resets else "") + ")")
print(f"RSSI    : min {min(rssi)} / median {st.median(rssi):.0f} / max {max(rssi)} dBm, "
      f"std {st.pstdev(rssi):.1f}")
print(f"SNR     : ~{st.median(rssi) - nf:.0f} dB (noise floor {nf:.0f} dBm)")
print(f"Serial  : {len(buf) / elapsed / 1024:.1f} KB/s, utilisation {line_util:.0f}%")

print("\nDiagnosis:", end=" ")
if loss < 5:
    print("link is healthy.")
elif line_util > 90:
    print("loss is most likely a SERIAL BOTTLENECK (line saturated). Raise the baud rate or reduce output volume.")
elif st.median(rssi) - nf < 15:
    print("WEAK SIGNAL. Check distance, antennas and placement.")
else:
    print("loss present without an obvious cause; possibly interference, change channel or repeat the measurement.")
