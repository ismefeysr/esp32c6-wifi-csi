"""Record CSI lines from the receiver ESP32-C6 serial port into a labelled file.

Usage:
  pip install -r requirements.txt
  python log_csi.py -p /dev/cu.usbmodemXXXX -l empty  -s s1 -d 120   # 120 s empty room
  python log_csi.py -p /dev/cu.usbmodemXXXX -l static -s s1 -d 120   # person standing still
  python log_csi.py -p /dev/cu.usbmodemXXXX -l walk   -s s1 -d 120   # person walking
Output: data/<label>_<session>.csv   (line: host_time;raw_csi_line)

Note: the port is busy while idf.py monitor is open; close the monitor first.
"""
import argparse, os, time
import serial

ap = argparse.ArgumentParser()
ap.add_argument("-p", "--port", required=True)
ap.add_argument("-b", "--baud", type=int, default=2000000)
ap.add_argument("-l", "--label", required=True, choices=["empty", "static", "walk"])
ap.add_argument("-s", "--session", required=True, help="e.g. s1, s2 ...")
ap.add_argument("-d", "--duration", type=float, default=120)
ap.add_argument("--countdown", type=int, default=5, help="preparation time before recording (s)")
a = ap.parse_args()

os.makedirs("data", exist_ok=True)
out = f"data/{a.label}_{a.session}.csv"
if os.path.exists(out):
    raise SystemExit(f"{out} already exists; choose another session name (recordings are never overwritten).")

for i in range(a.countdown, 0, -1):
    print(f"Starting in {i} s...", end="\r", flush=True)
    time.sleep(1)
print(f"\nRecording started: {out}  ({a.duration:.0f} s)")

n = 0
t0 = time.time()
with serial.Serial(a.port, a.baud, timeout=1) as ser, open(out, "w", encoding="utf8") as f:
    ser.reset_input_buffer()
    while time.time() - t0 < a.duration:
        raw = ser.readline().decode("utf8", errors="ignore").strip()
        if raw.startswith("CSI_DATA"):
            f.write(f"{time.time():.4f};{raw}\n")
            n += 1
            if n % 100 == 0:
                print(f"{n} packets, ~{n/(time.time()-t0):.1f} packets/s", end="\r", flush=True)

rate = n / max(time.time() - t0, 1e-9)
print(f"\nDone: {n} packets, average {rate:.1f} packets/s -> {out}")
if n < 20:
    print("WARNING: very few packets. Is the sender (csi_send) running on the same channel?")
