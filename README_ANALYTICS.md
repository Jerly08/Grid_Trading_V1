# Grid Trading Analytics Guide

## Gambaran Umum

Fitur Analytics yang baru ditambahkan memungkinkan Anda melacak dan menganalisis performa trading bot secara detail. Fitur ini memberikan insight yang lebih dalam untuk membantu mengoptimalkan strategi grid trading Anda.

## Cara Menggunakan Fitur Analytics

### 1. Melihat Log yang Ditingkatkan

Bot trading sekarang mencatat informasi yang lebih detail dalam beberapa file log:

- **Transaksi**: Detail setiap transaksi buy/sell
- **Harga**: Historis pergerakan harga dan nilai tukar USDT/IDR 
- **Saldo**: Perubahan saldo aset dari waktu ke waktu
- **Performa**: Metrik kinerja seperti win rate, ROI, dan statistik profit

Log-log ini secara otomatis disimpan di folder `trading_logs/`.

### 2. Menjalankan Analisis Log

Untuk menganalisis log trading dan mendapatkan insight, gunakan script `analyze_logs.py`:

```bash
python analyze_logs.py
```

Script ini akan:
1. Membaca semua data log dari folder `trading_logs/`
2. Menganalisis transaksi, harga, dan performa
3. Menampilkan ringkasan dan statistik penting
4. Membuat grafik visual yang disimpan di folder `analysis_charts/`

#### Parameter tambahan:

```bash
python analyze_logs.py --symbol BTCUSDT  # Analisis simbol yang berbeda
python analyze_logs.py --no-plots        # Jalankan analisis tanpa membuat grafik
```

### 3. Laporan Harian Otomatis

Bot sekarang menghasilkan laporan harian yang berisi:
- Profit hari ini vs hari kemarin
- Jumlah transaksi pada hari tersebut
- Win rate keseluruhan
- ROI saat ini

Laporan ini dicatat dalam `bot.log` dengan tag `[DAILY REPORT]`.

## Meningkatkan Strategi dengan Data Analytics

### Analisis Transaksi

- **Grid Level Paling Profitable**: Identifikasi level grid mana yang menghasilkan profit tertinggi
- **Win Rate**: Pantau rasio transaksi profitable vs unprofitable
- **Pola Waktu**: Cek jam-jam mana yang menghasilkan aktivitas trading terbanyak

### Analisis Performa

- **ROI (Return on Investment)**: Evaluasi performa keseluruhan dibandingkan modal awal
- **Statistik Harian**: Identifikasi hari-hari terbaik dan terburuk
- **Volatilitas Harga**: Sesuaikan grid range berdasarkan data volatilitas historis

### Analisis Saldo

- **Perubahan Nilai Portfolio**: Pantau perubahan nilai keseluruhan dari waktu ke waktu
- **Rasio Aset**: Evaluasi distribusi antara base asset (ADA) dan quote asset (USDT)

## Contoh Workflow Optimasi

1. Jalankan bot dengan parameter awal (UPPER_PRICE, LOWER_PRICE, GRID_NUMBER, QUANTITY)
2. Biarkan berjalan selama minimal 24-48 jam untuk mengumpulkan data
3. Jalankan `python analyze_logs.py` untuk mendapatkan insight
4. Sesuaikan parameter berdasarkan hasil analisis:
   - Jika sebagian besar profit terjadi di range tertentu, pertimbangkan untuk menyempitkan grid
   - Jika win rate rendah, pertimbangkan untuk memperlebar jarak antar grid
   - Jika sering terjadi "insufficient balance", sesuaikan QUANTITY atau MAX_INVESTMENT
5. Jalankan bot dengan parameter yang dioptimasi dan ulangi proses

## Sharing Data untuk Analisis Eksternal

Data dalam format JSON dan CSV dapat dengan mudah diekspor ke tools analisis lain:

- **Excel/Google Sheets**: Import file CSV untuk analisis lebih lanjut
- **Jupyter Notebook**: Proses data secara mendalam dengan pandas dan matplotlib
- **Power BI/Tableau**: Buat dashboard visual dari data performa trading

## Penggunaan Lanjutan

### Mengganti Directory Log

Secara default, log disimpan di folder `trading_logs/`. Untuk menggunakan folder lain:

1. Buka file `trading_analytics.py`
2. Ubah parameter `log_dir` di constructor: 
   ```python
   def __init__(self, symbol, log_dir="custom_logs"):
   ```

### Menyesuaikan Frekuensi Logging

Untuk mengubah seberapa sering data disimpan:

1. Log harga: Data disimpan setiap 100 data point, ubah di metode `log_price_data`
2. Laporan harian: Dibuat setiap pergantian hari, sesuaikan di metode `run` di `grid_bot.py` 