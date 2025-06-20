#!/usr/bin/env python
"""
Script non-interaktif untuk menyeimbangkan portfolio trading
Didesain untuk dijalankan secara terjadwal (crontab/scheduled tasks)

Penggunaan:
    python auto_balance.py [--aggressive]
    
    --aggressive: Gunakan lebih banyak USDT untuk pembelian ADA (90% vs 50%)
    --force: Jalankan tanpa konfirmasi bahkan jika tidak terdeteksi kebutuhan
"""

import logging
import argparse
import sys
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
    parser = argparse.ArgumentParser(description='Otomatis menyeimbangkan portfolio tanpa interaksi user')
    parser.add_argument('--aggressive', action='store_true', help='Gunakan lebih banyak USDT (90% vs 50%)')
    parser.add_argument('--force', action='store_true', help='Paksa menjalankan meskipun tidak terdeteksi kebutuhan')
    args = parser.parse_args()
    
    # Set safe mode berdasarkan parameter aggressive
    safe_mode = not args.aggressive
    
    # Jalankan auto balancer
    logger.info("=== AUTO PORTFOLIO BALANCER (NON-INTERACTIVE) ===")
    if args.aggressive:
        logger.info("Mode: AGGRESSIVE (menggunakan hingga 90% USDT free)")
    else:
        logger.info("Mode: SAFE (menggunakan hingga 50% USDT free)")
    
    try:
        balancer = AutoBalancer()
        result = balancer.check_balance_needed()
        
        if not result['need_balance_adjustment'] and not args.force:
            logger.info("Tidak perlu penyeimbangan. Portfolio sudah seimbang.")
            logger.info(f"Free USDT: {result['free_usdt']}")
            return 0
            
        if result['need_balance_adjustment']:
            logger.info(f"Kebutuhan penyeimbangan terdeteksi:")
            logger.info(f"Free USDT: {result['free_usdt']}")
            logger.info(f"ADA dibutuhkan: {result['needed_base_asset']}")
            logger.info(f"Harga ADA saat ini: {result['base_asset_price']} USDT")
        else:
            logger.info(f"Force mode aktif. Menjalankan auto balance meskipun tidak terdeteksi kebutuhan.")
            
        # Langsung jalankan penyeimbangan (tidak ada interaksi)
        success = balancer.execute_auto_balance(safe_mode=safe_mode)
        
        if success:
            logger.info("Penyeimbangan portfolio berhasil!")
            return 0
        else:
            logger.error("Penyeimbangan portfolio gagal")
            return 1
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return 2

if __name__ == "__main__":
    sys.exit(main()) 