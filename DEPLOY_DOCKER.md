# Panduan Deployment Bot Trading ke VPS Menggunakan Docker

Panduan ini menjelaskan cara mendeploy Binance Grid Trading Bot ke VPS menggunakan Docker.

## 1. Persiapan Repository GitHub

### Buat repository GitHub baru
1. Kunjungi https://github.com/new
2. Buat repository baru (sebaiknya private)
3. Jangan tambahkan README, .gitignore, atau license

### Upload kode ke GitHub
```bash
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

### Install Docker dan Docker Compose
```bash
# Install Docker
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update
sudo apt install -y docker-ce

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Tambahkan user ke grup docker (agar bisa menjalankan docker tanpa sudo)
sudo usermod -aG docker $USER
```

### Clone repository dari GitHub
```bash
git clone https://github.com/username/nama-repository.git
cd nama-repository
```

## 3. Konfigurasi Bot

### Setup file .env
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
docker run --rm python:3.10-slim python -c "import secrets; print(secrets.token_hex(32))"
```

### Buat direktori untuk data persistent
```bash
mkdir -p grid_state logs
```

## 4. Build dan Jalankan dengan Docker Compose

### Build dan jalankan container
```bash
docker-compose up -d --build
```

### Cek status container
```bash
docker-compose ps
```

### Lihat log secara real-time
```bash
docker-compose logs -f
```

## 5. Akses Dashboard

Setelah container berjalan, Anda dapat mengakses dashboard bot di:

```
http://ip_vps:5000
```

Gunakan username dan password yang telah dikonfigurasi di file .env.

## 6. Setup Reverse Proxy dengan Nginx (Opsional)

### Install Nginx
```bash
sudo apt install nginx -y
```

### Konfigurasi Nginx
```bash
sudo nano /etc/nginx/sites-available/grid-trading-bot
```

Tambahkan konfigurasi berikut:
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

## 7. Memperbarui Bot

Jika ada update kode baru di GitHub:

```bash
# Pull kode terbaru
git pull

# Rebuild dan restart container
docker-compose down
docker-compose up -d --build
```

## 8. Perintah Docker yang Berguna

### Menghentikan bot
```bash
docker-compose down
```

### Melihat logs
```bash
docker-compose logs -f
```

### Masuk ke shell container
```bash
docker exec -it binance-grid-bot bash
```

### Melihat status container
```bash
docker ps
```

### Lihat penggunaan resource
```bash
docker stats
```

## 9. Keamanan

### Konfigurasi Firewall
```bash
sudo apt install ufw -y
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

### Nonaktifkan akses langsung ke port 5000 (jika menggunakan Nginx)
```bash
sudo ufw delete allow 5000
```

## 10. Backup Data

### Backup data grid state
```bash
# Pastikan Anda berada di direktori project
cd /path/to/nama-repository
cp -r grid_state grid_state_backup_$(date +%Y%m%d)
```

### Backup konfigurasi
```bash
cp .env .env.backup_$(date +%Y%m%d)
```

## 11. Pemecahan Masalah

### Container tidak berjalan
```bash
docker-compose ps
docker-compose logs
```

### Memeriksa error dalam logs
```bash
docker-compose logs -f
```

### Restart container
```bash
docker-compose restart
```

### Rebuild jika ada perubahan pada Dockerfile
```bash
docker-compose up -d --build
``` 