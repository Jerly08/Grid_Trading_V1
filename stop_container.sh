#!/bin/bash

echo "===== Mematikan Container binance-grid-bot ====="

# Menghentikan container
echo "Menghentikan container binance-grid-bot..."
docker stop binance-grid-bot

# Menghapus container
echo "Menghapus container binance-grid-bot..."
docker rm binance-grid-bot

# Memastikan port 5000 sudah bebas
echo "Memeriksa apakah port 5000 sudah bebas..."
if netstat -tulpn | grep :5000 || lsof -i :5000; then
  echo "Port 5000 masih digunakan oleh proses lain."
  
  # Mencari PID yang menggunakan port 5000
  PID=$(lsof -t -i:5000 2>/dev/null)
  if [ -n "$PID" ]; then
    echo "Ditemukan proses yang masih menggunakan port 5000: PID $PID"
    echo "Menghentikan proses tersebut..."
    kill -9 $PID
    sleep 2
    echo "Proses dihentikan."
  fi
else
  echo "Port 5000 sudah bebas dan siap digunakan."
fi

# Menampilkan status container yang sedang berjalan
echo "Daftar container yang masih berjalan:"
docker ps

echo "===== Container berhasil dihentikan ====="
echo "Port 5000 sekarang bebas dan siap digunakan untuk aplikasi lain." 