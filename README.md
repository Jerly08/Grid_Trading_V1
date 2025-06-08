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
- Dashboard web untuk monitoring bot
- Pengelolaan risiko terintegrasi
- Keamanan dashboard dengan login & penanganan IP
- **Auto Balancer** - Menyeimbangkan portfolio secara otomatis

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

## Cara Penggunaan

Jalankan bot dengan perintah:

```
python run.py
```

Bot secara otomatis akan menyeimbangkan portfolio Anda terlebih dahulu sebelum menjalankan grid trading.

Untuk menjalankan hanya bot tanpa dashboard:
```
python run.py bot
```

Untuk menjalankan hanya dashboard tanpa bot:
```
python run.py dashboard
```

### Mode Production Server

Untuk menjalankan dashboard dengan production server (direkomendasikan untuk deployment):
```
python run.py --production
```

Atau hanya dashboard production tanpa bot:
```
python run.py dashboard --production
```

Mode production menggunakan:
- **Windows**: Waitress sebagai WSGI server
- **Linux/Mac**: Gunicorn sebagai WSGI server

### Auto Balancer

Bot ini dilengkapi dengan fitur Auto Balancer untuk penyeimbangan portfolio secara otomatis:

1. **Auto Balancing saat startup**: Bot akan secara otomatis menyeimbangkan portfolio sebelum memulai grid trading
   
2. **Penyeimbangan manual secara interaktif**:
   ```
   python balance_portfolio.py
   ```
   Gunakan parameter `--aggressive` untuk menggunakan lebih banyak USDT (90% vs 50%):
   ```
   python balance_portfolio.py --aggressive
   ```

3. **Penyeimbangan non-interaktif** (untuk crontab/scheduled tasks):
   ```
   python auto_balance.py
   ```
   Parameter:
   - `--aggressive`: Gunakan lebih banyak USDT (90% vs 50%)
   - `--force`: Paksa menjalankan bahkan jika tidak terdeteksi kebutuhan penyeimbangan

#### Contoh Penggunaan Scheduled Task (Windows):

```powershell
# Buat scheduled task yang berjalan setiap jam untuk menyeimbangkan portfolio
schtasks /create /sc hourly /tn "Crypto Portfolio Balancer" /tr "D:\Project\BOT_trading\venv\python.exe D:\Project\BOT_trading\auto_balance.py --aggressive"
```

## Dashboard Monitoring

Bot ini dilengkapi dengan dashboard web untuk memantau aktivitas:

1. Buka browser dan akses `http://localhost:5000`
2. Login dengan kredensial default:
   - Username: `admin`
   - Password: `Grid@Trading123`

### Fitur Dashboard
- Memantau status bot dan harga terkini
- Grafik pergerakan harga real-time
- Riwayat trading
- Level grid yang aktif

## Mengatasi Masalah Umum

### "Invalid API-key, IP, or permissions"
1. Pastikan API key dan secret sudah benar (tanpa spasi tambahan)
2. Aktifkan izin "Enable Reading" dan "Enable Spot & Margin Trading" di Binance
3. Jika menggunakan pembatasan IP, tambahkan IP server Anda ke whitelist

### "Account has insufficient balance"
1. Pastikan Anda memiliki saldo yang cukup di akun Binance
2. Kurangi `QUANTITY` di file `config.py` untuk mengurangi kebutuhan saldo

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

## Deployment ke VPS Menggunakan GitHub

### 1. Persiapan Repository GitHub

1. Buat repository GitHub baru (private untuk keamanan lebih baik):
   ```
   https://github.com/new
   ```

2. Push code bot trading ke repository GitHub:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/username/nama-repository.git
   git push -u origin main
   ```

### 2. Persiapan VPS

1. Login ke VPS menggunakan SSH:
   ```
   ssh username@alamat_ip_vps
   ```

2. Install dependensi yang diperlukan:
   ```
   sudo apt update
   sudo apt install git python3 python3-pip python3-venv -y
   ```

3. Clone repository dari GitHub:
   ```
   git clone https://github.com/username/nama-repository.git
   cd nama-repository
   ```

4. Buat virtual environment dan install dependensi:
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. Setup file .env:
   ```
   cp env.template .env
   nano .env
   ```
   
   Isi dengan API key Binance dan setting yang sesuai:
   ```
   API_KEY=your_binance_api_key_here
   API_SECRET=your_binance_api_secret_here
   BINANCE_TESTNET=False
   DASHBOARD_USERNAME=your_secure_username
   DASHBOARD_PASSWORD=your_secure_password
   DASHBOARD_SECRET_KEY=generated_secret_key
   ```
   
   Generate secret key dengan:
   ```
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

### 3. Menjalankan Bot di Background dengan systemd

1. Buat file service systemd:
   ```
   sudo nano /etc/systemd/system/grid-trading-bot.service
   ```

2. Tambahkan konfigurasi berikut:
   ```
   [Unit]
   Description=Binance Grid Trading Bot
   After=network.target

   [Service]
   User=username
   WorkingDirectory=/home/username/nama-repository
   ExecStart=/home/username/nama-repository/venv/bin/python run.py --production
   Restart=always
   RestartSec=10
   StandardOutput=syslog
   StandardError=syslog
   SyslogIdentifier=grid-trading-bot
   Environment=PYTHONUNBUFFERED=1

   [Install]
   WantedBy=multi-user.target
   ```
   
   Ganti `username` dan `nama-repository` sesuai dengan setup VPS Anda.

3. Aktifkan dan jalankan service:
   ```
   sudo systemctl daemon-reload
   sudo systemctl enable grid-trading-bot
   sudo systemctl start grid-trading-bot
   ```

4. Cek status service:
   ```
   sudo systemctl status grid-trading-bot
   ```

5. Untuk melihat log:
   ```
   sudo journalctl -u grid-trading-bot -f
   ```

### 4. Mengamankan Dashboard Web

1. Gunakan Nginx sebagai reverse proxy (opsional tapi direkomendasikan):
   ```
   sudo apt install nginx -y
   sudo nano /etc/nginx/sites-available/grid-trading-bot
   ```

2. Konfigurasi Nginx:
   ```
   server {
     listen 80;
     server_name your_domain_or_ip;

     location / {
       proxy_pass http://localhost:5000;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection 'upgrade';
       proxy_set_header Host $host;
       proxy_cache_bypass $http_upgrade;
     }
   }
   ```

3. Aktifkan site dan restart Nginx:
   ```
   sudo ln -s /etc/nginx/sites-available/grid-trading-bot /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

4. (Opsional) Tambahkan SSL dengan Certbot:
   ```
   sudo apt install certbot python3-certbot-nginx -y
   sudo certbot --nginx -d your_domain.com
   ```

### 5. Update Bot dari GitHub

Jika ada pembaruan di repository, gunakan perintah berikut untuk memperbarui bot di VPS:

1. Login ke VPS dan masuk ke direktori bot:
   ```
   cd nama-repository
   ```

2. Pull perubahan terbaru:
   ```
   git pull
   ```

3. Update dependensi jika diperlukan:
   ```
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Restart service bot:
   ```
   sudo systemctl restart grid-trading-bot
   ```

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