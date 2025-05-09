# Panduan Deployment Bot Trading ADAUSDT ke VPS Menggunakan Docker

Panduan ini menjelaskan cara mendeploy Binance Grid Trading Bot untuk ADAUSDT ke VPS menggunakan Docker.

## 1. Persiapan Deployment

### Mengupload Kode ke GitHub
```bash
git add .
git commit -m "Add Docker support for Grid Trading Bot"
git push
```

## 2. Setup VPS

### Login ke VPS
```bash
ssh username@alamat_ip_vps
```

### Install Docker dan Docker Compose
```bash
# Update sistem
sudo apt update
sudo apt upgrade -y

# Install Docker
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update
sudo apt install -y docker-ce

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Tambahkan user ke grup docker
sudo usermod -aG docker $USER
newgrp docker
```

### Clone Repository
```bash
git clone https://github.com/username/nama-repository.git
cd nama-repository
```

## 3. Menjalankan Bot

### Konfigurasi API Keys (Jika belum ada file .env)
Bot akan otomatis membuat file .env dari template, atau Anda bisa membuat secara manual:
```bash
# Buat file .env
nano .env
```

Isi dengan API key Binance Anda:
```
API_KEY=your_binance_api_key_here
API_SECRET=your_binance_api_secret_here
BINANCE_TESTNET=False
DASHBOARD_USERNAME=your_username
DASHBOARD_PASSWORD=your_secure_password
DASHBOARD_SECRET_KEY=generated_secret_key
```

### Build dan Jalankan Container
```bash
docker-compose up -d --build
```

### Cek Status Container
```bash
docker-compose ps
```

### Lihat Logs
```bash
docker-compose logs -f
```

## 4. Monitoring dan Pengelolaan Bot

### Akses Dashboard
Buka browser dan akses:
```
http://ip_vps:5000
```

### Melihat Profit dan Status
Profit dan status trading di-track secara otomatis pada file grid_state_ADAUSDT.json dan bisa dilihat pada dashboard.

### Melihat Log Secara Real-time
```bash
docker-compose logs -f
```

## 5. Keamanan (Direkomendasikan)

### Setup Reverse Proxy dengan Nginx
```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/grid-trading-bot
```

Konfigurasi Nginx:
```
server {
    listen 80;
    server_name your_ip_or_domain;

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

Aktifkan dan restart:
```bash
sudo ln -s /etc/nginx/sites-available/grid-trading-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Tambahkan SSL (Opsional tapi direkomendasikan)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

### Konfigurasi Firewall
```bash
sudo apt install ufw -y
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

## 6. Memperbarui Bot

### Update dari GitHub
```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Pantau Log Setelah Update
```bash
docker-compose logs -f
```

## 7. Troubleshooting

### Bot Tidak Bisa Melakukan Trading
Cek log untuk pesan error:
```bash
docker-compose logs -f
```

Jika muncul "Insufficient balance error", pastikan:
1. Anda memiliki saldo USDT yang cukup di akun Binance
2. API key memiliki permission untuk trading

### Restart Bot
```bash
docker-compose restart
```

### Restart dengan Konfigurasi Baru
```bash
docker-compose down
docker-compose up -d --build
```

### Akses Shell Container
```bash
docker exec -it binance-grid-bot bash
``` 