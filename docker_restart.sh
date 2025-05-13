#!/bin/bash

# Script untuk merestart aplikasi Docker setelah pull dari GitHub
# Jalankan script ini dari direktori proyek (tempat docker-compose.yml berada)

echo "===== Memulai proses update dan restart Docker container ====="

# 1. Backup file konfigurasi penting (jaga-jaga)
echo "Membuat backup file konfigurasi..."
cp -f .env .env.backup 2>/dev/null || echo "File .env tidak ditemukan"
cp -f grid_state_ADAUSDT.json grid_state_ADAUSDT.json.backup 2>/dev/null || echo "File grid_state tidak ditemukan"

# 2. Pull perubahan terbaru dari GitHub
echo "Pulling perubahan terbaru dari GitHub..."
git fetch origin main

# Cek jika ada perubahan
if git diff --quiet HEAD origin/main; then
    echo "Tidak ada perubahan baru di GitHub. Tidak perlu rebuild."
    CHANGES_DETECTED=false
else
    echo "Perubahan terdeteksi, melakukan git pull..."
    git pull origin main
    CHANGES_DETECTED=true
fi

# 3. Jika ada error dengan pull, coba cara alternatif
if [ $? -ne 0 ]; then
    echo "Error saat melakukan git pull. Mencoba cara alternatif..."
    
    # Backup file penting
    echo "Membuat backup tambahan..."
    mkdir -p ../bot_backup_$(date +%Y%m%d)
    cp -f .env ../bot_backup_$(date +%Y%m%d)/ 2>/dev/null
    cp -f grid_state_ADAUSDT.json ../bot_backup_$(date +%Y%m%d)/ 2>/dev/null
    cp -f bot.log ../bot_backup_$(date +%Y%m%d)/ 2>/dev/null
    
    # Reset hard dan pull ulang
    echo "Melakukan hard reset..."
    git reset --hard HEAD
    git clean -fd
    git pull origin main
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Masih gagal melakukan pull. Process dihentikan."
        exit 1
    fi
    
    # Kembalikan file konfigurasi penting
    echo "Mengembalikan file konfigurasi dari backup..."
    cp -f ../bot_backup_$(date +%Y%m%d)/.env . 2>/dev/null
    cp -f ../bot_backup_$(date +%Y%m%d)/grid_state_ADAUSDT.json . 2>/dev/null
    
    CHANGES_DETECTED=true
fi

# 4. Rebuild dan restart container dengan Docker Compose
if [ "$CHANGES_DETECTED" = true ] || [ "$1" = "--force" ]; then
    echo "Rebuilding Docker image..."
    docker-compose build
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Gagal melakukan build Docker image. Process dihentikan."
        exit 1
    fi
fi

echo "Merestart Docker container..."
docker-compose down
docker-compose up -d

if [ $? -ne 0 ]; then
    echo "ERROR: Gagal merestart Docker container. Process dihentikan."
    exit 1
fi

# 5. Menampilkan status container dan log terbaru
echo "Menampilkan status container:"
docker-compose ps

echo "Menampilkan 20 baris log terakhir:"
docker-compose logs --tail=20

echo "===== Proses update dan restart selesai ====="
echo "Untuk melihat log secara real-time, jalankan: docker-compose logs -f" 