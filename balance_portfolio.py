#!/usr/bin/env python
"""
Script untuk menyeimbangkan portfolio trading dengan membeli ADA
dari USDT yang tersedia tanpa harus melalui aksi manual.

Penggunaan:
    python balance_portfolio.py [--aggressive]
    
    --aggressive: Gunakan lebih banyak USDT untuk pembelian ADA (90% vs 50%)
"""

import logging
import argparse
from auto_balancer import AutoBalancer

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Otomatis menyeimbangkan portfolio dengan membeli ADA')
    parser.add_argument('--aggressive', action='store_true', help='Gunakan lebih banyak USDT (90% vs 50%)')
    args = parser.parse_args()
    
    # Set safe mode berdasarkan parameter aggressive
    safe_mode = not args.aggressive
    
    # Jalankan auto balancer
    logger.info("=== AUTO PORTFOLIO BALANCER ===")
    if args.aggressive:
        logger.info("Mode: AGGRESSIVE (menggunakan hingga 90% USDT free)")
    else:
        logger.info("Mode: SAFE (menggunakan hingga 50% USDT free)")
    
    try:
        balancer = AutoBalancer()
        result = balancer.check_balance_needed()
        
        if not result['need_balance_adjustment']:
            logger.info("Tidak perlu penyeimbangan. Portfolio sudah seimbang.")
            logger.info(f"Free USDT: {result['free_usdt']}")
            return
            
        logger.info(f"Kebutuhan penyeimbangan terdeteksi:")
        logger.info(f"Free USDT: {result['free_usdt']}")
        logger.info(f"ADA dibutuhkan: {result['needed_base_asset']}")
        logger.info(f"Harga ADA saat ini: {result['base_asset_price']} USDT")
        
        # Konfirmasi dari pengguna
        confirm = input("Jalankan penyeimbangan portfolio sekarang? (y/n): ")
        if confirm.lower() != 'y':
            logger.info("Penyeimbangan dibatalkan oleh pengguna")
            return
            
        # Jalankan penyeimbangan
        success = balancer.execute_auto_balance(safe_mode=safe_mode)
        
        if success:
            logger.info("Penyeimbangan portfolio berhasil!")
        else:
            logger.error("Penyeimbangan portfolio gagal")
            
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    main() 