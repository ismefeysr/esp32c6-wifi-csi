"""Record CSI lines from the receiver ESP32-C6 serial port into a labelled file.

Usage:
  pip install -r requirements.txt
  python log_csi.py -p /dev/cu.usbmodemXXXX -l empty  -s s1 -d 120   # 120 s empty room
  python log_csi.py -p /dev/cu.usbmodemXXXX -l static -s s1 -d 120   # person standing still
  python log_csi.py -p /dev/cu.usbmodemXXXX -l walk   -s s1 -d 120   # person walking
Output: data/<label>_<session>.csv   (line: host_time;raw_csi_line)
For a full session (link check + empty + walk) use record_session.py.

Note: the port is busy while idf.py monitor is open; close the monitor first.
"""
import argparse, os, time
import serial


def countdown(seconds, what="Starting"):
    for i in range(seconds, 0, -1):
        print(f"{what} in {i} s...   ", end="\r", flush=True)
        time.sleep(1)
    print()


def record(port, baud, out, duration):
    """Write CSI_DATA lines as host_time;raw_line to `out` for `duration` seconds. -> packet count"""
    n = 0
    t0 = time.time()
    with serial.Serial(port, baud, timeout=1) as ser, open(out, "w", encoding="utf8") as f:
        ser.reset_input_buffer()
        while time.time() - t0 < duration:
            raw = ser.readline().decode("utf8", errors="ignore").strip()
            if raw.startswith("CSI_DATA"):
                f.write(f"{time.time():.4f};{raw}\n")
                n += 1
                if n % 100 == 0:
                    left = duration - (time.time() - t0)
                    print(f"{n} packets, ~{n/(time.time()-t0):.1f} packets/s, {left:3.0f} s left",
                          end="\r", flush=True)
    print()
    return n


def main():
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

    countdown(a.countdown)
    print(f"Recording started: {out}  ({a.duration:.0f} s)")
    t0 = time.time()
    n = record(a.port, a.baud, out, a.duration)
    print(f"Done: {n} packets, average {n / max(time.time() - t0, 1e-9):.1f} packets/s -> {out}")
    if n < 20:
        print("WARNING: very few packets. Is the sender (csi_send) running on the same channel?")


if __name__ == "__main__":
    main()
