# ESP32-C6 ile Router'siz Wi-Fi CSI Insan Algilama - Baslangic Kiti

Donanim: 2x ESP32-C6 (biri gonderici, biri alici). Router YOK.

## 1) Firmware (`firmware/`, esp-csi get-started orneklerinden turetildi)

```bash
. ~/esp/esp-idf/export.sh            # veya: get_idf   (ESP-IDF v5.5)

# --- Gonderici kart (YESIL LED) ---
cd firmware/csi_send
idf.py set-target esp32c6
idf.py build flash -p <PORT_1>

# --- Alici kart (MAVI LED) ---
cd ../csi_recv
idf.py set-target esp32c6
idf.py build flash -p <PORT_2> monitor
```

Beklenen: alici kartin monitorunde `CSI_DATA,...` satirlari akar.
`csi_recv`, `csi_send`in paketlerini ozellikle yakalar; gonderici kapaliyken veri gelmez (normal).

Notlar
- Kartlar acilista dahili RGB LED ile kendini belli eder: gonderici yesil, alici mavi.
- Iki kart kanal 11, HT40'ta calisir; gonderici 100 paket/sn yayinlar.
- C6 devkitte iki USB-C girisi vardir ve ayni kart iki giriste farkli port adiyla gorunur.
  Alicinin konsolu UART'ta: CSI icin alici **UART** girisinden takilmali. Gonderiye sadece guc yeter.
- Kart kimligi icin port adi yerine cip MAC'ine bak: `esptool.py -p <PORT> read_mac`.
- Seri baud hizi: `csi_recv` ayarina bak (su an 2000000; ilk olcumler 921600 ile yapildi). Farkliysa `-b ...` kullan.
- Veri satirinin ek alanlari surume gore degisebilir; kit sadece SON alani (veri dizisi) kullanir.

## 1a) Python ortami (bir kez)

```bash
# repo kokunde
python3 -m venv .venv
.venv/bin/pip install -r analysis/requirements.txt
source .venv/bin/activate          # sonraki komutlar icin
cd analysis
```

## 1b) Link kontrolu (WP1)

Veri toplamadan once linkin saglikli oldugunu dogrula:

```bash
python link_check.py -p <PORT_2> -d 30 --save data/link_<yer>.log
```

Paket hizi, kayip (gondericinin sayacindan), RSSI/SNR ve seri hat dolulugunu raporlar,
kaybin sebebini (seri darbogaz / zayif sinyal) tahmin eder. Hedef: kayip < %5.

Olcum kaydi (2026-10-24, kalabalik ortam, 921600 baud):

| Yerlesim | RSSI medyan | Hiz | Kayip | Teshis |
|---|---|---|---|---|
| ilk (uzak) | -90 dBm | 20 Hz | %78 | zayif sinyal |
| yakin | -62 dBm | 79 Hz | %13.5 | seri darbogaz (hat %99 dolu) |

## 2) Veri toplama (WP2)

```bash
# .venv aktif (bkz. 1a); idf.py monitor'u KAPAT, sonra:
python log_csi.py -p <PORT_2> -l empty  -s s1 -d 120
python log_csi.py -p <PORT_2> -l static -s s1 -d 120
python log_csi.py -p <PORT_2> -l walk   -s s1 -d 120
# ayni uclu icin s2, s3 ... (farkli gun/saat/konum/kisi)
```
Dosya adi `etiket_sN.csv` olmali. Oturum bazli ayirma icin EN AZ 3 oturum topla.

## 3) Baseline (esik) ve ML

```bash
python baseline.py --calib data/empty_s1.csv --k 4 --test "data/*_s2.csv"
python ml_classifier.py --test-sessions s3 --export-c tree_model.h
```

## 4) Donanimsiz deneme (SENTETIK veri)

```bash
python make_fake_data.py
python baseline.py --calib data_fake/empty_s1.csv --test "data_fake/*_s2.csv"
python ml_classifier.py --data "data_fake/*_s*.csv" --test-sessions s3
```
Sentetik sonuclar GERCEK DEGILDIR; raporda kullanma.

## Dikkat / bilinen sinirlar
- Firmware iki C6 kartinda derlenip yuklendi ve CSI akisi dogrulandi (bkz. 1b). `link_check.py` gercek
  alici loglariyla test edildi. `csi_common.py` (load_log/preprocess/motion_index) gercek C6 satirlarini
  dogru okuyor: 128 alt tasiyici, 14 sabit/null tasiyici maskeleniyor. Baseline ve ML ise simdilik
  yalnizca sentetik veriyle uctan uca calistirildi.
- Sentetik veri (52 alt tasiyici, 50 Hz) gercek C6 formatindan (128 alt tasiyici, ~100 Hz) farklidir.
  `--win 50` gercek veride ~0.5 sn'ye karsilik gelir (sentetikte 1 sn); pencere boyu WP2'de secilmeli.
- esp-csi ornekleri guncelleniyor; CSV sutun sayisi veya ayar adlari degisebilir. Takilirsan `CSI_DATA` satirindan ornek bir satiri bana yapistir.
- Gercek verideki dogruluk sentetikten cok daha dusuk cikabilir; bu normaldir ve raporlanmasi gereken bir sonuctur.
