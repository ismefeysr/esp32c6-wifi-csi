"""Alici ESP32-C6'dan seri porttan CSI satirlarini etiketli dosyaya kaydeder.

Kullanim:
  pip install pyserial
  python log_csi.py -p COM5 -l empty  -s s1 -d 120      # 120 sn bos oda
  python log_csi.py -p COM5 -l static -s s1 -d 120      # sabit duran kisi
  python log_csi.py -p COM5 -l walk   -s s1 -d 120      # yuruyen kisi
Cikti: data/<etiket>_<oturum>.csv   (satir: host_zamani;ham_csi_satiri)

Not: idf.py monitor acikken port mesgul olur; once monitoru kapat.
"""
import argparse, os, time
import serial

ap = argparse.ArgumentParser()
ap.add_argument("-p", "--port", required=True)
ap.add_argument("-b", "--baud", type=int, default=921600)
ap.add_argument("-l", "--label", required=True, choices=["empty", "static", "walk"])
ap.add_argument("-s", "--session", required=True, help="ornek: s1, s2 ...")
ap.add_argument("-d", "--duration", type=float, default=120)
ap.add_argument("--countdown", type=int, default=5, help="kayit oncesi hazirlik suresi (sn)")
a = ap.parse_args()

os.makedirs("data", exist_ok=True)
out = f"data/{a.label}_{a.session}.csv"
if os.path.exists(out):
    raise SystemExit(f"{out} zaten var; baska oturum adi sec (kayit ustune yazilmaz).")

for i in range(a.countdown, 0, -1):
    print(f"Baslamaya {i} sn...", end="\r", flush=True)
    time.sleep(1)
print(f"\nKayit basladi: {out}  ({a.duration:.0f} sn)")

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
                print(f"{n} paket, ~{n/(time.time()-t0):.1f} paket/sn", end="\r", flush=True)

rate = n / max(time.time() - t0, 1e-9)
print(f"\nBitti: {n} paket, ortalama {rate:.1f} paket/sn -> {out}")
if n < 20:
    print("UYARI: cok az paket. Gonderici (csi_send) calisiyor mu, ayni kanalda mi?")
