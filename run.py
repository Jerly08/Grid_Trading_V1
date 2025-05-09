import sys
import threading
import time
import logging
from grid_bot import GridTradingBot
from dashboard import run_dashboard

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

def run_bot():
    """Jalankan bot trading grid"""
    try:
        bot = GridTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Error dalam bot trading: {e}")

def run_dashboard_thread():
    """Jalankan dashboard web dalam thread terpisah"""
    try:
        run_dashboard()
    except Exception as e:
        logger.error(f"Error dalam dashboard: {e}")

def main():
    """Fungsi utama untuk menjalankan bot dan dashboard"""
    # Parse command line arguments
    mode = "both"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    if mode == "bot":
        # Hanya jalankan bot
        logger.info("Menjalankan bot trading tanpa dashboard")
        run_bot()
    elif mode == "dashboard":
        # Hanya jalankan dashboard
        logger.info("Menjalankan dashboard tanpa bot trading")
        run_dashboard_thread()
    else:
        # Jalankan keduanya
        logger.info("Menjalankan bot trading dan dashboard")
        
        # Jalankan dashboard dalam thread terpisah
        dashboard_thread = threading.Thread(target=run_dashboard_thread)
        dashboard_thread.daemon = True
        dashboard_thread.start()
        
        logger.info("Dashboard berhasil dimulai di http://localhost:5000")
        
        # Jalankan bot dalam thread utama
        time.sleep(2)  # Tunggu dashboard dimulai
        run_bot()

if __name__ == "__main__":
    main() 