"""Live crossing detector with a browser UI: shows CROSSING / CLEAR, a passage counter and live traces.

Usage:
  python live_detector.py                                   # receiver auto-detected, http://localhost:8000
  python live_detector.py -p /dev/cu.usbmodemXXXX --save data/live_test.log
  python live_detector.py --replay data/empty_s4.csv data/walk_s4.csv     # recorded files, real time
  python live_detector.py --replay data/empty_s4.csv data/walk_s4.csv --speed 4

How it works:
  A body crossing the link blocks the direct path for ~0.5 s, which shows up as a sharp RSSI dip of
  5-8 dB. Someone standing or moving next to the link only shifts the RSSI slowly (a few dB), and people
  elsewhere in the room mainly change the reflections.
  0. Get ready: --delay seconds (default 15) of countdown before the receiver is read.
  1. Warm-up: the first --cal seconds fill the history; nobody should cross the link.
  2. Detection: every --every packets the mean RSSI of the last 15 packets (~0.17 s) is compared with a
     rolling baseline, the median RSSI between 3.5 s and 0.5 s ago. dip = baseline - current and
     score = dip / --k-rssi. A score >= 1 counts one passage and shows CROSSING for 0.8 s. A crossing
     often breaks into two dips ~1.5-2 s apart, so no new passage is counted for --refractory seconds.
  --use-motion also scores the motion index (mean subcarrier variance of the per-packet normalised
  amplitudes over 50 packets) against its warm-up level: score = max(dip / k_rssi, z / --k-motion).
  It reacts to any movement near the link, so it is off by default.
"""
import argparse, collections, glob, json, os, queue, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import numpy as np

from csi_common import parse_line

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_packet(raw):
    """raw 'CSI_DATA,...' line -> (rssi, amplitudes) or None."""
    v = parse_line(raw)
    if v is None or len(v) < 8 or len(v) % 2:
        return None
    try:
        rssi = float(raw.split(",", 4)[3])
    except (IndexError, ValueError):
        return None
    return rssi, np.hypot(v[0::2].astype(float), v[1::2].astype(float))


class CrossingDetector:
    """Feed packets with push(); update() returns the current state dict."""

    def __init__(self, cal_seconds=10.0, k_rssi=5.0, short=15, base_seconds=3.0, gap=0.5,
                 refractory=2.2, hold=0.8, use_motion=False, k_motion=8.0, win=50):
        self.cal_seconds, self.k_rssi, self.short = cal_seconds, k_rssi, short
        self.base_seconds, self.gap, self.refractory, self.hold = base_seconds, gap, refractory, hold
        self.use_motion, self.k_motion, self.win = use_motion, k_motion, win
        self.hist = collections.deque()       # (t, rssi) over the last base_seconds + gap
        self.amp = collections.deque(maxlen=win)
        self.t0 = self.t = None
        self.n_sub, self.mask = None, None
        self.cal_motion, self.motion_ref = [], None
        self.passages, self.last_event, self.last_high = 0, -1e9, -1e9

    def push(self, t, rssi, amp):
        if self.n_sub is None:
            self.n_sub = len(amp)
        if len(amp) != self.n_sub:            # mixed packet lengths: keep the first one seen
            return
        if self.t0 is None:
            self.t0 = t
        self.t = t
        self.hist.append((t, rssi))
        while self.hist and self.hist[0][0] < t - self.base_seconds - self.gap:
            self.hist.popleft()
        self.amp.append(amp)

    def _motion(self):
        A = np.array(self.amp)
        if self.mask is None:
            self.mask = A.std(axis=0) > 0
        A = A[:, self.mask]
        A = A / np.maximum(A.mean(axis=1, keepdims=True), 1e-9)
        return float(A.var(axis=0).mean())

    def update(self):
        """Call every few packets. -> state dict, or None before enough packets arrived."""
        if len(self.amp) < self.win or len(self.hist) < self.short:
            return None
        h = np.array(self.hist)
        current = float(h[-self.short:, 1].mean())
        older = h[h[:, 0] < self.t - self.gap, 1]
        baseline = float(np.median(older)) if len(older) else current
        elapsed = self.t - self.t0
        motion = self._motion() if self.use_motion else 0.0
        state = dict(t=round(elapsed, 2), rssi=current, ref_rssi=baseline, passages=self.passages)
        if elapsed < self.cal_seconds:
            if self.use_motion:
                self.cal_motion.append(motion)
            return dict(state, phase="calibrating", progress=min(elapsed / self.cal_seconds, 1.0),
                        crossing=False, score=0.0)
        if self.use_motion and self.motion_ref is None:
            m = np.array(self.cal_motion or [motion])
            scale = max(np.percentile(m, 75) - np.percentile(m, 25), 0.05 * np.median(m), 1e-12)
            self.motion_ref = (float(np.median(m)), float(scale))
        dip = baseline - current
        score = dip / self.k_rssi
        z = 0.0
        if self.use_motion:
            z = (motion - self.motion_ref[0]) / self.motion_ref[1]
            score = max(score, z / self.k_motion)
        if score >= 1:
            self.last_high = elapsed
            if elapsed - self.last_event > self.refractory:
                self.passages += 1
                self.last_event = elapsed
        crossing = elapsed - self.last_high <= self.hold
        return dict(state, phase="detecting", crossing=crossing, passages=self.passages,
                    score=float(score), rssi_drop=float(dip), z_motion=float(z))


# ---------------------------------------------------------------- packet sources

def serial_source(port, baud):
    import serial
    with serial.Serial(port, baud, timeout=1) as ser:
        ser.reset_input_buffer()
        while True:
            raw = ser.readline().decode("utf8", errors="ignore").strip()
            if raw.startswith("CSI_DATA"):
                yield time.time(), raw


def replay_source(paths, speed=1.0):
    """Replays log_csi.py files back to back at `speed` x real time (host timestamps)."""
    offset, start_wall, start_t, last = 0.0, time.time(), None, None
    for p in paths:
        first = None
        with open(p, encoding="utf8", errors="ignore") as f:
            for ln in f:
                if ";" not in ln:
                    continue
                ts, raw = ln.strip().split(";", 1)
                try:
                    t = float(ts)
                except ValueError:
                    continue
                if first is None:
                    first = t
                    if last is not None:          # continue the time axis seamlessly
                        offset = last + 0.012 - t
                t += offset
                if start_t is None:
                    start_t = t
                delay = (t - start_t) / speed - (time.time() - start_wall)
                if delay > 0:
                    time.sleep(delay)
                last = t
                yield t, raw


def find_port():
    ports = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")
                   + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    if len(ports) != 1:
        raise SystemExit(f"Cannot pick the receiver port automatically, pass -p. Candidates: {ports}")
    return ports[0]


# ---------------------------------------------------------------- web UI (server-sent events)

class Hub:
    def __init__(self):
        self.clients, self.lock = [], threading.Lock()

    def add(self):
        q = queue.Queue(maxsize=200)
        with self.lock:
            self.clients.append(q)
        return q

    def remove(self, q):
        with self.lock:
            self.clients.remove(q)

    def publish(self, msg):
        data = json.dumps(msg)
        with self.lock:
            for q in self.clients:
                try:
                    q.put_nowait(data)
                except queue.Full:
                    pass


def make_handler(hub, page):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path          # ignore the query string (?lang=tr)
            if path in ("/", "/index.html"):
                body = page.encode("utf8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                q = hub.add()
                try:
                    while True:
                        try:
                            data = q.get(timeout=5)
                            self.wfile.write(f"data: {data}\n\n".encode())
                        except queue.Empty:
                            self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    hub.remove(q)
            else:
                self.send_error(404)
    return Handler


def countdown(hub, seconds, tick=1.0):
    """Get-ready phase before anything is read: the UI shows the time left until warm-up starts."""
    end = time.time() + seconds
    while (left := end - time.time()) > 0:
        hub.publish(dict(phase="waiting", left=round(left), total=seconds))
        print(f"Warm-up starts in {left:3.0f} s", end="\r", flush=True)
        time.sleep(min(tick, left))
    if seconds > 0:
        print(" " * 30, end="\r", flush=True)


def run(source, det, hub, every, log_path=None):
    n, rate_t, rate_n, rate = 0, time.time(), 0, 0.0
    log = open(log_path, "w", encoding="utf8") if log_path else None
    for t, raw in source:
        if log:
            log.write(f"{t:.4f};{raw}\n")
        pkt = parse_packet(raw)
        if pkt is None:
            continue
        det.push(t, *pkt)
        n += 1; rate_n += 1
        if time.time() - rate_t >= 1.0:
            rate, rate_t, rate_n = rate_n / (time.time() - rate_t), time.time(), 0
        if n % every == 0:
            st = det.update()
            if st is not None:
                hub.publish(dict(st, rate=round(rate, 1)))
    if log:
        log.close()
    hub.publish(dict(phase="ended"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--port")
    ap.add_argument("-b", "--baud", type=int, default=2000000)
    ap.add_argument("--replay", nargs="+", help="log_csi.py files to replay instead of the serial port")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed factor")
    ap.add_argument("--http-port", type=int, default=8000)
    ap.add_argument("--delay", type=float, default=15.0,
                    help="get-ready seconds before the warm-up starts (0 = start at once)")
    ap.add_argument("--cal", type=float, default=10.0, help="warm-up seconds (nobody crosses)")
    ap.add_argument("--k-rssi", type=float, default=5.0, help="RSSI dip (dB) that counts as a crossing")
    ap.add_argument("--refractory", type=float, default=2.2,
                    help="seconds after a passage in which no new one is counted")
    ap.add_argument("--every", type=int, default=4, help="update every N packets (~20 Hz; dips last only ~0.5 s)")
    ap.add_argument("--use-motion", action="store_true", help="also score the motion index (any movement)")
    ap.add_argument("--k-motion", type=float, default=8.0)
    ap.add_argument("--save", help="also write the received packets to this log file")
    a = ap.parse_args()

    det = CrossingDetector(cal_seconds=a.cal, k_rssi=a.k_rssi, refractory=a.refractory, use_motion=a.use_motion, k_motion=a.k_motion)
    source = replay_source(a.replay, a.speed) if a.replay else serial_source(a.port or find_port(), a.baud)
    hub = Hub()
    page = open(os.path.join(HERE, "live_ui.html"), encoding="utf8").read()
    server = ThreadingHTTPServer(("127.0.0.1", a.http_port), make_handler(hub, page))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"UI: http://localhost:{a.http_port}  (source: {'replay ' + ' '.join(a.replay) if a.replay else 'serial'})", flush=True)
    try:
        countdown(hub, a.delay)
        run(source, det, hub, a.every, a.save)
        print("Source ended; UI stays up. Ctrl+C to quit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
