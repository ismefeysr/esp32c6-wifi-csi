# ESP32-C6 ile Router'siz Wi-Fi CSI Insan Algilama - Baslangic Kiti

Donanim: 2x ESP32-C6 (biri gonderici, biri alici). Router YOK.

## 1) Firmware (hazir, kaynak kodlu: Espressif esp-csi)

```bash
git clone https://github.com/espressif/esp-csi.git
# ESP-IDF kurulu ve aktif olmali (C6 destegi icin v5.1 veya uzeri; guncel v5.x onerilir)

# --- Gonderici kart ---
cd esp-csi/examples/get-started/csi_send
idf.py set-target esp32c6
idf.py build flash -p <PORT_1>

# --- Alici kart ---
cd ../csi_recv
idf.py set-target esp32c6
idf.py build flash -p <PORT_2> monitor
```

Beklenen: alici kartin monitorunde `CSI_DATA,...` satirlari akar.
`csi_recv`, `csi_send`in paketlerini ozellikle yakalar; gonderici kapaliyken veri gelmez (normal).

Notlar
- Iki kartin ayni kanalda olmasi gerekir (menuconfig / ornek ayarlari).
- C6 devkitte iki USB portu olur. Espressif ornekleri UART portunun kullanilmasini onerir.
- Seri baud hizi: `csi_recv` ayarina bak (genelde 921600). Farkliysa `log_csi.py -b ...` kullan.
- Veri satirinin ek alanlari surume gore degisebilir; kit sadece SON alani (veri dizisi) kullanir.

## 2) Veri toplama (WP2)

```bash
pip install pyserial numpy scipy scikit-learn
# idf.py monitor'u KAPAT, sonra:
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
- Firmware kismini (esp-csi) ve C6 uzerindeki gercek veriyi ben denemedim. Python betikleri sentetik veriyle test edildi.
- esp-csi ornekleri guncelleniyor; CSV sutun sayisi veya ayar adlari degisebilir. Takilirsan `CSI_DATA` satirindan ornek bir satiri bana yapistir.
- Gercek verideki dogruluk sentetikten cok daha dusuk cikabilir; bu normaldir ve raporlanmasi gereken bir sonuctur.
