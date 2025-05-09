# Panduan Deployment Bot Trading ke VPS

Dokumen ini berisi langkah-langkah detail untuk mendeploy Bot Trading Grid Binance ke VPS menggunakan GitHub.

## 1. Persiapkan repository GitHub

### Buat repository GitHub baru
1. Kunjungi https://github.com/new
2. Buat repository baru (sebaiknya private)
3. Jangan tambahkan README, .gitignore, atau license

### Siapkan repository lokal Anda
```bash
# Di direktori bot trading Anda (D:\Project\BOT_trading)
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/username/nama-repository.git
git push -u origin main
```

Ganti `username/nama-repository` dengan username GitHub dan nama repository Anda.

## 2. Siapkan VPS

### Login ke VPS
```bash
ssh username@alamat_ip_vps
```

### Instal dependensi yang diperlukan
```bash
sudo apt update
sudo apt install git python3 python3-pip python3-venv -y
```

### Clone repository dari GitHub
```bash
git clone https://github.com/username/nama-repository.git
cd nama-repository
```

### Setup environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Konfigurasi file .env
```bash
cp env.template .env
nano .env
```

Edit file dengan informasi API key Binance Anda:
```
API_KEY=your_binance_api_key_here
API_SECRET=your_binance_api_secret_here
BINANCE_TESTNET=False
DASHBOARD_USERNAME=your_secure_username
DASHBOARD_PASSWORD=your_secure_password
DASHBOARD_SECRET_KEY=generated_secret_key
```

Generate secret key dengan:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 3. Setup Systemd Service

### Buat file service
```bash
sudo nano /etc/systemd/system/grid-trading-bot.service
```

Isi dengan konfigurasi berikut:
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

Ganti `username` dan jalur dengan informasi akun VPS Anda.

### Aktifkan dan mulai service
```bash
sudo systemctl daemon-reload
sudo systemctl enable grid-trading-bot
sudo systemctl start grid-trading-bot
```

### Verifikasi status bot
```bash
sudo systemctl status grid-trading-bot
```

### Melihat log bot
```bash
sudo journalctl -u grid-trading-bot -f
```

## 4. Setup Reverse Proxy dengan Nginx (Opsional)

### Instal Nginx
```bash
sudo apt install nginx -y
```

### Konfigurasi Nginx
```bash
sudo nano /etc/nginx/sites-available/grid-trading-bot
```

Isi dengan:
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

### Aktifkan konfigurasi
```bash
sudo ln -s /etc/nginx/sites-available/grid-trading-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Setup SSL (Opsional)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your_domain.com
```

## 5. Keamanan VPS

### Konfigurasi Firewall
```bash
sudo apt install ufw -y
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

### Hapus port 5000 dari akses publik (jika menggunakan Nginx)
```bash
sudo ufw delete allow 5000
```

## 6. Memperbarui Bot dari GitHub

Saat ada update di GitHub:

```bash
cd nama-repository
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart grid-trading-bot
```

## 7. Monitoring dan Pemeliharaan

### Cek status bot secara berkala
```bash
sudo systemctl status grid-trading-bot
```

### Melihat log trading
```bash
tail -f bot.log
```

### Backup data penting
```bash
# Backup configuration dan state
cp .env .env.backup
cp grid_state_ADAUSDT.json grid_state_ADAUSDT.json.backup
```

## 8. Pemecahan Masalah

### Bot tidak berjalan
```bash
sudo systemctl status grid-trading-bot
sudo journalctl -u grid-trading-bot -n 50
```

### Dashboard tidak dapat diakses
```bash
sudo systemctl status nginx
sudo nginx -t
curl http://localhost:5000
```

### Issue dengan API Binance
1. Periksa status Binance API di https://www.binance.com/en/binance-api-status
2. Pastikan API key memiliki permission yang benar
3. Jika menggunakan IP restriction, tambahkan IP VPS ke whitelist Binance 