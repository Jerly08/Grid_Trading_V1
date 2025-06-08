# Auto Balancer - Fitur Penyeimbangan Portfolio

Auto Balancer adalah fitur yang memastikan keseimbangan optimal antara aset dasar (ADA) dan aset quote (USDT) untuk operasi grid trading yang efisien. Fitur ini sekarang mendukung penyeimbangan dua arah, memastikan bahwa bot selalu memiliki cukup ADA untuk menjual dan cukup USDT untuk membeli.

## Cara Kerja Auto Balancer

Auto Balancer beroperasi dengan dua mode penyeimbangan:

### 1. Mode "Beli ADA" (Buy Base Asset)

Diaktifkan ketika:
- ADA yang tersedia (free) kurang dari kebutuhan untuk menempatkan sell orders (biasanya 3x quantity)
- USDT yang tersedia mencukupi (minimal 10 USDT)

Dalam mode ini, Auto Balancer akan:
- Menghitung berapa ADA yang dibutuhkan untuk memenuhi sell orders
- Konversi sejumlah USDT menjadi ADA menggunakan market order
- Menyisakan buffer USDT untuk biaya trading dan fluktuasi harga

### 2. Mode "Jual ADA" (Sell Base Asset)

Diaktifkan ketika:
- USDT yang tersedia kurang dari kebutuhan untuk menempatkan buy orders
- ADA yang tersedia berlebih (lebih dari kebutuhan sell orders + buffer)

Dalam mode ini, Auto Balancer akan:
- Menghitung berapa USDT yang dibutuhkan untuk memenuhi buy orders
- Konversi sejumlah ADA yang berlebih menjadi USDT menggunakan market order
- Tetap menjaga cukup ADA untuk sell orders dan sejumlah buffer

## Cara Menjalankan Auto Balancer

Ada beberapa cara untuk menjalankan Auto Balancer:

### 1. Mode Independen

```
python run.py balance
```

Menjalankan Auto Balancer saja tanpa menjalankan bot trading atau dashboard. Berguna untuk penyeimbangan manual sebelum memulai trading.

### 2. Flag Bersama Mode Utama

```
python run.py both --balancer --production
```

Menjalankan Auto Balancer sekali di awal, sebelum bot trading dan dashboard dimulai. Auto Balancer tidak akan berjalan secara otomatis selama bot beroperasi.

Alternatif:
- `python run.py bot --balancer`: Menjalankan Auto Balancer + bot trading (tanpa dashboard)
- `python run.py dashboard --balancer`: Menjalankan Auto Balancer + dashboard (tanpa bot)

### 3. Eksekusi Manual

Anda juga bisa menjalankan Auto Balancer kapan saja tanpa mengganggu bot yang sedang berjalan:

```
python auto_balancer.py
```

## Parameter Keamanan

Auto Balancer memiliki parameter `safe_mode`:

- Dalam `safe_mode=True` (default): Menggunakan maksimal 50% dari saldo bebas untuk transaksi
- Dalam `safe_mode=False`: Menggunakan hingga 90% dari saldo bebas untuk transaksi

## Contoh Kasus

### Contoh 1: ADA Kurang

Kondisi:
- Tersedia: 20 ADA (free), 150 USDT (free)
- Kebutuhan: 90 ADA untuk 3 sell orders (dengan quantity=30)

Auto Balancer akan membeli sekitar 70 ADA menggunakan USDT yang tersedia.

### Contoh 2: USDT Kurang

Kondisi:
- Tersedia: 200 ADA (free), 15 USDT (free)
- Kebutuhan: 60 USDT untuk 3 buy orders (dengan quantity=30, harga=0.67)

Auto Balancer akan menjual sebagian ADA (sekitar 67 ADA) untuk mendapatkan 45 USDT tambahan.

## Tips Penggunaan

1. **Jalankan sebelum trading**: Selalu jalankan Auto Balancer sebelum memulai trading untuk memastikan keseimbangan optimal
2. **Cek setelah perubahan harga besar**: Jalankan Auto Balancer setelah perubahan harga signifikan untuk menyesuaikan jumlah aset
3. **Gunakan dengan auto-config**: Kombinasikan dengan auto-config untuk setup optimal (jalankan auto-config terlebih dahulu)
4. **VPN**: Jika Anda mengalami masalah koneksi saat mengakses API Binance, pertimbangkan untuk menggunakan VPN

## Catatan Penting

- Auto Balancer menggunakan market order yang dikenakan fee trading (~0.1%)
- Order minimal di Binance adalah 10 USDT, jadi pastikan ada cukup aset
- Auto Balancer tidak berjalan secara otomatis selama bot beroperasi, perlu dijalankan secara manual saat diperlukan 