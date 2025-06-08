# Fitur Auto-Config untuk BOT Trading

Fitur Auto-Config adalah solusi otomatis untuk mengoptimalkan parameter trading bot Anda berdasarkan kondisi pasar saat ini dan modal yang tersedia. Dengan fitur ini, bot akan secara otomatis menyesuaikan rentang harga, jumlah grid, dan kuantitas order untuk hasil yang optimal.

## Keuntungan Auto-Config

1. **Rentang Harga Optimal** - Selalu disesuaikan dengan harga pasar saat ini
2. **Jumlah Grid yang Sesuai** - Dioptimalkan berdasarkan volatilitas pasar dan modal Anda
3. **Kuantitas Order yang Tepat** - Dihitung berdasarkan ketersediaan saldo Anda
4. **Adaptasi Otomatis terhadap Kondisi Pasar** - Menyesuaikan strategi berdasarkan tren pasar (sideways, bullish, bearish)
5. **Perlindungan Modal** - Memastikan parameter tidak melebihi batas ketersediaan saldo Anda

## Cara Menggunakan Auto-Config

### Metode 1: Menggunakan Command Line

Jalankan perintah berikut di terminal:

```
python run.py auto-config
```

Bot akan:
1. Menganalisis kondisi pasar saat ini (harga, volatilitas, tren)
2. Menganalisis saldo dan modal Anda yang tersedia
3. Menghitung parameter grid yang optimal
4. Menampilkan konfigurasi yang direkomendasikan
5. Meminta konfirmasi Anda sebelum menerapkan perubahan

### Metode 2: Menjalankan File Auto-Config Langsung

Anda juga dapat menjalankan file auto_config.py secara langsung:

```
python auto_config.py
```

## Kapan Sebaiknya Menggunakan Auto-Config?

Gunakan fitur Auto-Config dalam situasi berikut:

1. **Saat Memulai Bot** - Untuk konfigurasi awal yang optimal
2. **Setelah Perubahan Harga Signifikan** - Ketika harga telah bergerak keluar dari rentang grid Anda
3. **Saat Menambah/Mengurangi Modal** - Setelah deposit atau withdrawal
4. **Perubahan Volatilitas Pasar** - Ketika pasar menjadi lebih/kurang volatil

## Parameter yang Disesuaikan

Auto-Config akan menyesuaikan parameter berikut:

- **UPPER_PRICE** - Batas atas rentang harga grid
- **LOWER_PRICE** - Batas bawah rentang harga grid
- **GRID_NUMBER** - Jumlah grid (level harga)
- **QUANTITY** - Jumlah aset per order

## Contoh Hasil Auto-Config

Berikut contoh output dari Auto-Config:

```
==== KONFIGURASI OPTIMAL YANG DIHASILKAN ====
Symbol: ADAUSDT
Rentang harga: 0.6321 - 0.6963
Jumlah grid: 5
Quantity per order: 20 ADA
==========================================

Terapkan konfigurasi ini? (y/n): 
```

## Tips Penggunaan Auto-Config

1. **Jalankan di Waktu yang Tepat** - Sebaiknya jalankan Auto-Config saat pasar dalam kondisi relatif stabil
2. **Periksa Konfigurasi Sebelum Menyetujui** - Selalu review konfigurasi yang direkomendasikan
3. **Restart Bot Setelah Konfigurasi** - Agar perubahan diterapkan dengan benar
4. **Gunakan Secara Berkala** - Jalankan Auto-Config secara berkala (1-2 minggu sekali) untuk menjaga konfigurasi tetap optimal

## Mengatasi Masalah

Jika Anda mengalami masalah dengan Auto-Config:

1. **Error Koneksi API** - Pastikan koneksi internet stabil dan API Binance dapat diakses
2. **Hasil Tidak Sesuai Harapan** - Anda dapat menolak konfigurasi dan menyesuaikan parameter secara manual
3. **Error Konfigurasi** - Jika terjadi error, Auto-Config akan otomatis menggunakan nilai default dari config.py

---

Dengan fitur Auto-Config, trading grid Anda akan selalu dioptimalkan untuk kondisi pasar saat ini dan ketersediaan modal, membantu Anda mencapai hasil trading yang lebih konsisten dan profit yang lebih optimal. 