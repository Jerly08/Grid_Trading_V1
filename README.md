# Binance Grid Trading Bot

Bot trading grid untuk platform Binance yang dibuat menggunakan Python.

## Deskripsi

Bot ini menerapkan strategi trading grid pada platform Binance. Strategi trading grid bekerja dengan menempatkan serangkaian order beli dan jual pada interval harga yang telah ditentukan. Saat harga bergerak naik dan turun di dalam interval, bot akan secara otomatis membeli saat harga rendah dan menjual saat harga tinggi, menghasilkan profit dari volatilitas pasar.

## Fitur

- Konfigurasi batas harga atas dan bawah grid
- Jumlah grid yang dapat disesuaikan
- Dukungan untuk mode testnet Binance
- Logging komprehensif untuk semua aktivitas bot
- Penanganan kesalahan dan mekanisme retry
- Auto-rebalancing setelah order terpenuhi
- Mode simulasi untuk pengujian tanpa dana nyata
- Dashboard web untuk monitoring bot
- Pengelolaan risiko terintegrasi
- Keamanan dashboard dengan login & penanganan IP
- Auto-switching ke mode simulasi jika saldo tidak cukup

## Instalasi

1. Clone repositori ini:
```
git clone https://github.com/yourusername/binance-grid-trading-bot.git
cd binance-grid-trading-bot
```

2. Install dependensi yang diperlukan:
```
pip install -r requirements.txt
```

3. Buat file `.env` di direktori root dan tambahkan API key Binance Anda:
```
API_KEY=your_binance_api_key_here
API_SECRET=your_binance_api_secret_here
BINANCE_TESTNET=True  # Ubah menjadi False untuk trading di akun live
```

## Konfigurasi

Edit file `config.py` untuk menyesuaikan parameter trading grid:

```python
# Grid trading parameters
SYMBOL = 'ADAUSDT'  # Trading pair
UPPER_PRICE = 0.795  # Upper price boundary for grid (~2% above current price)
LOWER_PRICE = 0.765  # Lower price boundary for grid (~2% below current price)
GRID_NUMBER = 5      # Focus on 5 level grid for limited capital

# Order parameters
QUANTITY = 20  # Quantity of crypto to buy/sell at each grid level
```

## Penggunaan Biasa

Jalankan bot dengan perintah:

```
python run.py
```

## Penggunaan Mode Simulasi

Untuk menjalankan bot dalam mode simulasi (tanpa order sungguhan):

```
python run_simulation.py
```

Mode simulasi memungkinkan Anda menguji strategi grid tanpa dana nyata.

## Dashboard Monitoring

Bot ini dilengkapi dengan dashboard web untuk memantau aktivitas:

1. Buka browser dan akses `http://localhost:5000`
2. Login dengan kredensial default:
   - Username: `admin`
   - Password: `Grid@Trading123`

## Mengatasi Masalah Umum

### "Invalid API-key, IP, or permissions"
1. Pastikan API key dan secret sudah benar (tanpa spasi tambahan)
2. Aktifkan izin "Enable Reading" dan "Enable Spot & Margin Trading" di Binance
3. Jika menggunakan pembatasan IP, tambahkan IP server Anda ke whitelist

### "Account has insufficient balance"
1. Pastikan Anda memiliki saldo yang cukup di akun Binance
2. Gunakan mode simulasi untuk testing: `python run_simulation.py`
3. Kurangi `QUANTITY` di file `config.py` untuk mengurangi kebutuhan saldo

### Masalah Emoji di Dashboard
Jika mengalami masalah tampilan emoji di dashboard:
- Edit `config.py` dan set `EMOJI_SUPPORT = False`

## Keamanan untuk Deployment

Jika men-deploy bot di VPS, pastikan untuk:
1. Ubah password dashboard default di file `.env`
2. Generate secret key baru dengan: `python -c "import secrets; print(secrets.token_hex(32))"`
3. Gunakan HTTPS jika mengakses dashboard dari internet
4. Aktifkan firewall dan batasi akses port 5000

## Catatan Penting

- **Risiko Trading**: Trading cryptocurrency melibatkan risiko keuangan. Gunakan bot ini dengan risiko Anda sendiri.
- **API Keys**: Jangan pernah membagikan API key Binance Anda dengan siapa pun. Sebaiknya gunakan API key dengan izin hanya untuk trading.
- **Testnet**: Sangat disarankan untuk menguji bot di testnet Binance terlebih dahulu sebelum trading dengan dana sungguhan.

## Lisensi

MIT

## Kontribusi

Kontribusi, isu, dan permintaan fitur sangat diterima. Silakan buat issue atau pull request untuk berkontribusi. 