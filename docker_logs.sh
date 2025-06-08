#!/bin/bash

echo "===== Alat Untuk Melihat Log Docker ====="

# Fungsi untuk melihat log container
view_container_log() {
  container_name=$1
  lines=${2:-100}  # Default 100 baris
  follow=${3:-false}  # Default tidak follow
  
  echo "Menampilkan $lines baris log terakhir dari container $container_name"
  
  if [ "$follow" = true ]; then
    echo "Mode real-time (tekan Ctrl+C untuk keluar)..."
    docker logs --tail="$lines" -f "$container_name"
  else
    docker logs --tail="$lines" "$container_name"
  fi
}

# Menampilkan daftar container yang tersedia
echo "Daftar container yang sedang berjalan:"
docker ps

# Menampilkan container yang berhenti juga
echo -e "\nDaftar semua container (termasuk yang berhenti):"
docker ps -a

# Menu pilihan
echo -e "\nPilihan menu:"
echo "1) Lihat log container tertentu"
echo "2) Lihat log container binance-grid-bot (jika ada)"
echo "3) Lihat log secara real-time (follow mode)"
echo "4) Lihat semua container log (ringkas)"
echo "5) Keluar"

read -p "Pilih opsi (1-5): " choice

case $choice in
  1)
    read -p "Masukkan nama atau ID container: " container_name
    read -p "Berapa baris log yang ingin ditampilkan? (default: 100): " lines
    lines=${lines:-100}
    view_container_log "$container_name" "$lines" false
    ;;
  2)
    if docker ps -a | grep -q "binance-grid-bot"; then
      read -p "Berapa baris log yang ingin ditampilkan? (default: 100): " lines
      lines=${lines:-100}
      view_container_log "binance-grid-bot" "$lines" false
    else
      echo "Container binance-grid-bot tidak ditemukan."
      
      # Cek apakah ada container grid-trading-bot
      if docker ps -a | grep -q "grid-trading-bot"; then
        read -p "Container grid-trading-bot ditemukan. Lihat lognya? (y/n): " view_grid
        if [[ $view_grid == [yY] ]]; then
          read -p "Berapa baris log yang ingin ditampilkan? (default: 100): " lines
          lines=${lines:-100}
          view_container_log "grid-trading-bot" "$lines" false
        fi
      else
        echo "Tidak ada container terkait trading bot yang ditemukan."
      fi
    fi
    ;;
  3)
    read -p "Masukkan nama atau ID container untuk mode real-time: " container_name
    read -p "Berapa baris log terakhir yang ingin ditampilkan? (default: 100): " lines
    lines=${lines:-100}
    echo "Menampilkan log secara real-time (tekan Ctrl+C untuk keluar)..."
    view_container_log "$container_name" "$lines" true
    ;;
  4)
    echo "Menampilkan ringkasan log untuk semua container..."
    for container in $(docker ps -q); do
      container_name=$(docker inspect --format='{{.Name}}' "$container" | sed 's/\///')
      echo -e "\n===== Log untuk $container_name ====="
      docker logs --tail=20 "$container"
      echo -e "=====\n"
    done
    ;;
  5)
    echo "Keluar dari program."
    exit 0
    ;;
  *)
    echo "Pilihan tidak valid."
    exit 1
    ;;
esac

echo "===== Selesai =====" 