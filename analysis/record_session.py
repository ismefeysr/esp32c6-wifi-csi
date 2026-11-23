"""Record one complete session in a single run: link check -> empty -> walk -> quality report.

Usage:
  python record_session.py -s s2 --note "evening, door closed"
  python record_session.py -s s3 -p /dev/cu.usbmodemXXXX -d 120 --countdown 15

Steps (each waits for Enter, so you can reposition between them):
  1. Link check: short recording to data/link_<session>.log; warns if loss >= 5 %.
  2. empty: countdown (leave the room), record, sound at start and end.
  3. walk:  countdown (go to the start of the path), record, sound at start and end.
  4. Quality of each file (packets, rate, seq loss, largest gap) and one JSON line
     per recording appended to data/sessions.jsonl for the report.

Sounds use macOS afplay; elsewhere the terminal bell is used. On macOS the script holds a
caffeinate assertion so the laptop cannot idle-sleep mid-recording (a sleeping host stops
reading the port and the recording is ruined); keep the lid open.
Recordings are never overwritten. Ctrl+C aborts and keeps already finished files.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time

from csi_common import log_quality
from log_csi import countdown, record

LOSS_LIMIT = 5.0          # % (WP1 target)
MIN_RATE = 70.0           # Hz; s1 ran at ~87 Hz
SOUNDS = {"start": "/System/Library/Sounds/Glass.aiff", "end": "/System/Library/Sounds/Hero.aiff"}


def beep(kind):
    path = SOUNDS[kind]
    if shutil.which("afplay") and os.path.exists(path):
        subprocess.Popen(["afplay", path])
    else:
        print("\a", end="", flush=True)


def find_port():
    ports = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")
                   + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    if len(ports) == 1:
        return ports[0]
    hint = "\n  ".join(ports) if ports else "(none found; is the receiver plugged in?)"
    raise SystemExit(f"Cannot pick the receiver port automatically, pass -p. Candidates:\n  {hint}")


def summary(q):
    return (f"{q['received']} packets, {q['duration_s']:.0f} s, {q['rate_hz']:.1f} Hz, "
            f"loss {q['loss_pct']:.1f}% (largest gap {q['max_gap']} pkt, "
            f"{q['max_time_gap_s'] * 1000:.0f} ms)" + (f", {q['resets']} sender resets" if q["resets"] else ""))


def wait(msg):
    input(f"\n>>> {msg} [Enter] ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--session", required=True, help="e.g. s2")
    ap.add_argument("-p", "--port", help="receiver port (auto-detected if only one USB serial port)")
    ap.add_argument("-b", "--baud", type=int, default=2000000)
    ap.add_argument("-d", "--duration", type=float, default=120, help="seconds per label")
    ap.add_argument("--countdown", type=int, default=15)
    ap.add_argument("--link-duration", type=float, default=15, help="0 skips the link check")
    ap.add_argument("--labels", nargs="+", default=["empty", "walk"], choices=["empty", "static", "walk"])
    ap.add_argument("--note", default="", help="free text stored with the session (time of day, door...)")
    ap.add_argument("--data", default="data")
    a = ap.parse_args()

    if shutil.which("caffeinate"):
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])   # released when we exit
    port = a.port or find_port()
    os.makedirs(a.data, exist_ok=True)
    outs = {lb: f"{a.data}/{lb}_{a.session}.csv" for lb in a.labels}
    existing = [p for p in outs.values() if os.path.exists(p)]
    if existing:
        raise SystemExit(f"Already recorded: {', '.join(existing)}. Choose another session name.")
    print(f"Session {a.session} on {port} @ {a.baud} baud: {', '.join(a.labels)} x {a.duration:.0f} s")

    if a.link_duration > 0:
        wait("Link check: room empty, both boards powered.")
        link = f"{a.data}/link_{a.session}.log"      # not *.csv: keeps it out of list_logs()
        record(port, a.baud, link, a.link_duration)
        q = log_quality(link)
        print("Link:", summary(q))
        if q["received"] < 20:
            raise SystemExit("Almost no packets. Is the sender running? Is the receiver on the UART port?")
        if q["loss_pct"] >= LOSS_LIMIT:
            ans = input(f"Loss is above {LOSS_LIMIT:.0f}%. Continue anyway? [y/N] ")
            if ans.strip().lower() != "y":
                raise SystemExit("Aborted. Check placement (boards upright, facing each other).")

    steps = {"empty": "EMPTY: start the countdown, then leave the room and close the door.",
             "static": "STATIC: stand still at the marked spot during the recording.",
             "walk": "WALK: go to the start of the path; walk continuously until the end sound."}
    results = []
    for lb in a.labels:
        wait(steps[lb])
        countdown(a.countdown, f"{lb} recording starts")
        beep("start")
        started = time.strftime("%Y-%m-%dT%H:%M:%S")
        record(port, a.baud, outs[lb], a.duration)
        beep("end")
        q = log_quality(outs[lb])
        print(f"{lb}: {summary(q)}")
        results.append(dict(session=a.session, label=lb, file=outs[lb], started=started,
                            port=port, baud=a.baud, note=a.note, **q))

    with open(f"{a.data}/sessions.jsonl", "a", encoding="utf8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"\n=== Session {a.session} ===")
    bad = False
    for r in results:
        flag = "OK " if r["loss_pct"] < LOSS_LIMIT and r["rate_hz"] >= MIN_RATE else "CHECK"
        bad |= flag != "OK "
        print(f"[{flag}] {r['label']:6s} {summary(r)}")
    print(f"Metadata appended to {a.data}/sessions.jsonl")
    if bad:
        print("Some recordings look weak; consider re-recording under a new session name.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nAborted; finished recordings were kept (the interrupted one may be partial).")
