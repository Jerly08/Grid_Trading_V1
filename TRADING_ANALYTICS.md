# Trading Analytics for Binance Grid Bot

## Gambaran Umum

Modul Trading Analytics yang baru ditambahkan menyediakan pencatatan transaksi dan performa trading yang lebih detail untuk membantu analisis profit dan optimasi strategi grid trading Anda.

## Fitur Utama

1. **Pencatatan Transaksi Terperinci**
   - Setiap transaksi (BUY/SELL) dicatat dengan detail lengkap
   - Informasi profit per transaksi dan statistik kumulatif
   - Pelacakan harga entry dan exit untuk setiap posisi

2. **Pelacakan Performa Harian**
   - Laporan profit harian otomatis
   - Statistik win rate (rasio transaksi profit vs loss)
   - Perhitungan ROI (Return on Investment) dari investasi awal

3. **Pencatatan Harga dan Saldo**
   - Histori harga pasar yang lebih detail
   - Pelacakan nilai portfolio dalam USDT dan IDR
   - Data untuk analisis volatilitas dan pergerakan pasar

4. **Struktur Data Log Terorganisir**
   - File log terpisah untuk transaksi, harga, dan saldo
   - Format JSON dan CSV untuk memudahkan analisis eksternal
   - Integrasi dengan dashboard untuk visualisasi

## File Log yang Tersedia

Semua file log disimpan di folder `trading_logs/` dengan struktur sebagai berikut:

- **transactions_{symbol}.json**: Riwayat transaksi lengkap
- **price_history_{symbol}.csv**: Data historis harga dan nilai tukar
- **balance_history.json**: Perubahan saldo dari waktu ke waktu
- **performance_metrics_{symbol}.json**: Metrik performa trading

## Cara Menggunakan Data untuk Analisis

### 1. Analisis Transaksi

File transactions log (`trading_logs/transactions_ADAUSDT.json`) berisi detail transaksi seperti:
- Waktu transaksi
- Jenis (BUY/SELL)
- Harga
- Quantity
- Profit yang dihasilkan (untuk transaksi SELL)
- Total profit kumulatif
- Level grid tempat transaksi terjadi
- Kondisi pasar saat transaksi

Gunakan data ini untuk menganalisis:
- Pada level grid mana profit paling sering terjadi
- Berapa rata-rata profit per transaksi
- Pada waktu apa transaksi paling aktif terjadi

### 2. Laporan Harian

Bot akan menghasilkan laporan harian otomatis yang mencakup:
- Profit hari ini vs hari sebelumnya
- Jumlah transaksi hari ini
- Win rate keseluruhan
- ROI saat ini
- Total profit hingga saat ini

Informasi ini membantu Anda melacak performa bot secara konsisten dan melihat tren jangka panjang.

### 3. Perbandingan dengan Nilai Tukar IDR

Data USDT/IDR dan nilai portfolio dalam IDR disimpan untuk membantu kontekstualisasi profit dalam mata uang lokal.

## Tips Optimasi dari Data Analytics

1. **Analisis Grid Level Produktif**
   - Identifikasi level grid mana yang menghasilkan profit paling banyak
   - Pertimbangkan untuk mengubah range grid untuk fokus pada area tersebut

2. **Analisis Waktu Trading Optimal**
   - Periksa pada pola waktu kapan transaksi paling banyak terjadi
   - Sesuaikan strategi untuk volatilitas pada waktu-waktu tertentu

3. **Analisis ROI untuk Penyesuaian Modal**
   - Gunakan data ROI untuk evaluasi apakah perlu menambah atau mengurangi modal

4. **Optimasi Quantity Berdasarkan Performance**
   - Analisis profit per transaksi dan win rate untuk menentukan quantity optimal

## Mengintegrasikan dengan Tools Eksternal

Data yang disimpan dalam format JSON dan CSV dapat dengan mudah diimpor ke tools analisis seperti:

1. **Excel/Google Sheets**
   - Import CSV price history untuk analisis grafik
   - Hitung statistik menggunakan pivot tables

2. **Python Data Analysis**
   - Gunakan pandas untuk analisis data mendalam
   - Buat visualisasi dengan matplotlib atau seaborn

3. **Tableau/Power BI**
   - Buat dashboard visual dari data transaksi dan performa

## Contoh Analisis Sederhana

Anda dapat melihat total profit harian dan mengidentifikasi tren dengan membaca `performance_metrics_ADAUSDT.json` dan memeriksa bagian `daily_profits`. Data ini menunjukkan hari-hari apa saja yang menguntungkan dan berapa profitnya.

## Kesimpulan

Dengan fitur Trading Analytics yang baru, Anda mendapatkan insight yang lebih dalam tentang performa bot trading dan dapat membuat keputusan berbasis data untuk mengoptimalkan strategi grid trading Anda.

Gunakan data ini untuk terus menyesuaikan parameter seperti grid range, jumlah grid, dan quantity untuk memaksimalkan profit sesuai dengan kondisi pasar terkini. 