"""WP1 link kontrolu: alicidan CSI akisini dinler, paket hizi / kayip / RSSI raporlar.

Kullanim:
  pip install pyserial
  python link_check.py -p /dev/cu.usbmodemXXXX               # 15 sn olcum
  python link_check.py -p /dev/cu.usbmodemXXXX -d 60 --save data/link_ev_bosoda.log

Kayip, gondericinin paket sayacindan (CSI_DATA satirindaki seq alani) hesaplanir.
Gonderici olcum sirasinda yeniden baslarsa sayac sifirlanir; her parca ayri sayilir.
Seri hat dolulugu %90'i asarsa kayip buyuk olasilikla seri porttan kaynaklanir (RF degil).

Not: idf.py monitor acikken port mesgul olur; once monitoru kapat.
Alici, UART yazan USB-C girisinden takili olmali (konsol UART'ta).
"""
import argparse, csv, io, statistics as st, time
import serial

# esp32c6 csi_recv baslik satiri:
# type,seq,mac,rssi,rate,noise_floor,fft_gain,agc_gain,channel,local_timestamp,...,data
SEQ, RSSI, NOISE = 1, 3, 5

ap = argparse.ArgumentParser()
ap.add_argument("-p", "--port", required=True)
ap.add_argument("-b", "--baud", type=int, default=921600)
ap.add_argument("-d", "--duration", type=float, default=15)
ap.add_argument("--send-rate", type=float, default=100, help="gondericinin hizi (Hz)")
ap.add_argument("--save", help="ham seri ciktiyi bu dosyaya yaz")
a = ap.parse_args()

print(f"Olcum: {a.port} @ {a.baud} baud, {a.duration:.0f} sn ...")
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
    if not (ln.startswith("CSI_DATA,") and ln.endswith(']"')):    # yarim satirlari at
        continue
    try:
        row = next(csv.reader(io.StringIO(ln)))
        seq.append(int(row[SEQ])); rssi.append(int(row[RSSI])); noise.append(int(row[NOISE]))
    except (ValueError, IndexError):
        continue

if len(seq) < 2:
    raise SystemExit(f"Yetersiz CSI satiri ({len(seq)}), {len(buf)} bayt alindi. "
                     "Gonderici calisiyor mu? Alici UART girisinden mi takili? Baud dogru mu?")

# gonderici reset -> seq geriye duser; parcalari ayri say
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
line_util = 100 * len(buf) / elapsed / (a.baud / 10)          # 8N1: bayt basina 10 bit
nf = st.median(noise)

print(f"\nPaket   : {len(seq)} alindi / {expected} gonderildi, {rate:.1f} Hz (hedef {a.send_rate:.0f})")
print(f"Kayip   : %{loss:.1f}  ({len(gaps)} bosluk, en buyuk {max(gaps, default=0)} paket"
      + (f", {resets} gonderici reset" if resets else "") + ")")
print(f"RSSI    : min {min(rssi)} / medyan {st.median(rssi):.0f} / maks {max(rssi)} dBm, "
      f"std {st.pstdev(rssi):.1f}")
print(f"SNR     : ~{st.median(rssi) - nf:.0f} dB (gurultu tabani {nf:.0f} dBm)")
print(f"Seri hat: {len(buf) / elapsed / 1024:.1f} KB/s, doluluk %{line_util:.0f}")

print("\nTeshis  :", end=" ")
if loss < 5:
    print("link saglikli.")
elif line_util > 90:
    print("kayip buyuk olasilikla SERI DARBOGAZ (hat dolu). Baud'u artir veya cikti hacmini azalt.")
elif st.median(rssi) - nf < 15:
    print("SINYAL ZAYIF. Mesafe/anten/yerlesimi kontrol et.")
else:
    print("kayip var ama belirgin sebep yok; ortam girisimi olabilir, kanali/olcumu tekrarla.")
